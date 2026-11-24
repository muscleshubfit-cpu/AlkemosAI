#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""مزود الاستعلام عند مصدر الحساب الحالي (Alkemos.com — Supabase Auth).

هذا المزود يعيش **خارج engine/** (قانون الاستقلالية: لا أسماء منصات داخل
حزمة المحرك) وهو تنفيذ عقد `engine/identity` لمصدر الحساب القائم فعلًا
(تفتيش دفعة 17 — docs/04-architecture/unified-identity-architecture):

- **التسجيل والدخول والجلسة** في Alkemos.com يقودها Supabase Auth
  (GoTrue): دخول بريد/كلمة مرور + OAuth (Google) عبر `@supabase/ssr`،
  والجلسة تخزن في كوكيز ويجدد Middleware الموقع.
- **معرف المستخدم** = `auth.users.id` (UUID) — مرجع `profiles.id`.
- **الأدوار** في جدول `profiles.role` (client/coach/admin) — قراءتها من
  جهة الخدمة عبر REST تحت RLS، **لا من الرمز** ولا من المستدعي.
- **نطاق المدرب** = عملاؤه المسندون في `coach_assignments` (client_id/
  coach_id — قراءتها بالرمز نفسه تحت RLS: المدرب يقرأ مسنديه).
- الموقع نفسه يتحقق من الجلسة جهة الخدمة بنداء `supabase.auth.getUser()`
  (src/lib/auth-server.ts) — هذا المزود يستخدم **نفس آلية التحقق**
  (نقطة نهاية userinfo) فيكون متوافقًا مع واقع الموقع حرفيًا.

التحقق هنا **استعلام (introspection) لا مشاركة مفاتيح**: لا مفتاح سري
مشترك مع الموقع — نداءات موثوقة بـHTTPS تحمل رمز المستخدم نفسه + مفتاح
النشر العام (anon key — مفتاح معلَن لا سر؛ SECURITY §1). فشل أي نداء =
فشل مغلق بلا امتيازات.

عمر رمز المحرك: يُقرأ `exp` من رأس الرمز **قراءة قياسية بلا تحقق توقيع
محلي** (الهوية تثبتها نداءات الخدمة أعلاه؛ القيمة تستخدم سقف عمر فقط —
أي عبث بها يضر صاحبه وحده: يقصّر جلسته). الرموز المعتمة (بلا JWT) تعطي
العمر الافتراضي.

كل السلوك قابل للحقن للاختبار: `http_get_json` قابل للاستبدال، وسمس
الاختبار المتكامل (scripts/test_engine_identity_integration.py) يشغّل
المزود الحقيقي ضد خادم محاكاة محلي (loopback) بلا أي اتصال إنتاجي.
"""
from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Callable, Dict, List, Optional

from engine.identity import contract
from engine.identity.contract import (
    ACCOUNT_ROLES,
    IdentityVerificationError,
    ROLE_CLIENT,
    ROLE_COACH,
    VerifiedAccount,
    canonical_account_id,
)
from engine.identity.contract import _mint_verified_account
from .jwks import require_https_url

PROVIDER_NAME = "supabase-introspection"
DEFAULT_HTTP_TIMEOUT_SECONDS = 10

_USERINFO_PATH = "/auth/v1/userinfo"
_PROFILES_PATH = "/rest/v1/profiles"
_COACH_ASSIGNMENTS_PATH = "/rest/v1/coach_assignments"
_MAX_TOKEN_LENGTH = 8192


def _unix_now() -> int:
    return int(time.time())


def _default_http_get_json(url: str, headers: Dict[str, str], timeout: int) -> Dict:
    """نداء HTTPS واحد يعيد JSON — بلا تحويلات وبلا أسرار في السجل."""
    req = urllib.request.Request(url, headers=dict(headers), method="GET")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read()
    except urllib.error.HTTPError as exc:
        try:
            detail = exc.read().decode("utf-8", "replace")[:200]
        except Exception:  # noqa: BLE001 — تشخيص فقط
            detail = ""
        raise IdentityVerificationError(
            f"مصدر الحساب رفض الطلب ({exc.code}) — فشل مغلق: {detail}"
        ) from exc
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise IdentityVerificationError(
            f"تعذر بلوغ مصدر الحساب للتحقق: {exc} — فشل مغلق"
        ) from exc
    try:
        return json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise IdentityVerificationError("رد مصدر الحساب غير قابل للقراءة") from exc


class SupabaseIntrospectionProvider:
    """مزود الهوية الموحد لمصدر حساب Alkemos.com القائم (Supabase Auth).

    التحقق من رمز جلسة المنبع عبر:
    1. `GET {issuer}/auth/v1/userinfo` — هوية المستخدم (id/email) من خدمة
       المصادقة نفسها (نفس ما يتحقق به الموقع جهة خدمته).
    2. `GET {issuer}/rest/v1/profiles?select=id,role&id=eq.{uuid}` — الدور
       من جدول profiles تحت RLS (المستخدم يقرأ صفه).
    3. للمدرب فقط: `GET {issuer}/rest/v1/coach_assignments?select=client_id
       &coach_id=eq.{uuid}` — عملاؤه المسندون (RLS: المدرب يقرأ مسنديه).

    لا يقبل المزود أي بريد أو دور من المستدعي — مدخله الرمز فقط، وكل
    الهوية والدور والنطاق تقرأ من ردود الخدمة.
    """

    def __init__(
        self,
        *,
        issuer: str,
        anon_key: str,
        http_timeout_seconds: int = DEFAULT_HTTP_TIMEOUT_SECONDS,
        allow_insecure_loopback: bool = False,
        http_get_json: Optional[Callable] = None,
    ) -> None:
        self._issuer = require_https_url(
            issuer.rstrip("/"),
            allow_insecure_loopback=allow_insecure_loopback,
            what="issuer (مصدر الحساب)",
        )
        if not isinstance(anon_key, str) or not anon_key.strip():
            raise contract.AccountContractError(
                "مفتاح النشر العام (anon key) مطلوب للمزود — من الإعداد "
                "(ALKEMOS_IDENTITY_ANON_KEY)، ليس سرًّا ولا يسكن المستودع"
            )
        self._anon_key = anon_key.strip()
        self._timeout = int(http_timeout_seconds)
        self._get_json = http_get_json or _default_http_get_json
        self.name = PROVIDER_NAME

    # -- أدوات داخلية -------------------------------------------------------
    def _headers(self, upstream_token: str) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {upstream_token}",
            "apikey": self._anon_key,
            "Accept": "application/json",
        }

    def _call(self, path: str, query: Dict[str, str], upstream_token: str) -> Dict:
        url = self._issuer + path + "?" + urllib.parse.urlencode(query)
        return self._get_json(url, self._headers(upstream_token), self._timeout)

    def _userinfo(self, upstream_token: str) -> Dict:
        data = self._call(_USERINFO_PATH, {}, upstream_token)
        if not isinstance(data, dict):
            raise IdentityVerificationError("رد userinfo غير قانوني")
        return data

    def _role_from_profiles(self, account_id: str, upstream_token: str) -> str:
        rows = self._call(
            _PROFILES_PATH,
            {"select": "id,role", "id": f"eq.{account_id}"},
            upstream_token,
        )
        if not isinstance(rows, list) or len(rows) != 1:
            raise IdentityVerificationError(
                "الحساب بلا صف دور في مصدر الهوية (profiles) — لا هوية محرك "
                "بلا دور موثق (فشل مغلق)"
            )
        role = rows[0].get("role")
        if role not in ACCOUNT_ROLES:
            raise IdentityVerificationError(
                f"دور غير معروف من مصدر الهوية: {role!r} — فشل مغلق"
            )
        return role

    def _coach_scope(self, account_id: str, upstream_token: str):
        rows = self._call(
            _COACH_ASSIGNMENTS_PATH,
            {"select": "client_id", "coach_id": f"eq.{account_id}"},
            upstream_token,
        )
        if not isinstance(rows, list):
            raise IdentityVerificationError(
                "رد نطاق المدرب غير قانوني — فشل مغلق (لا افتراض نطاق)"
            )
        scope = set()
        for row in rows:
            client_id = row.get("client_id") if isinstance(row, dict) else None
            if client_id:
                scope.add(canonical_account_id(client_id))
        return frozenset(scope)

    @staticmethod
    def _read_exp_hint(upstream_token: str) -> Optional[int]:
        """قراءة exp من رمز JWT المنبع — سقف عمر فقط لا إثبات هوية.

        قراءة بلا تحقق توقيع محلي: الهوية تثبتها نداءات الخدمة أعلاه؛
        هذه القيمة تقصّر عمر رمز المحرك فقط (لا تمدده أبدًا).
        """
        try:
            payload_b64 = upstream_token.split(".")[1]
            import base64

            pad = "=" * (-len(payload_b64) % 4)
            payload = json.loads(
                base64.urlsafe_b64decode(payload_b64 + pad).decode("utf-8")
            )
            exp = payload.get("exp")
            return int(exp) if isinstance(exp, (int, float)) else None
        except Exception:  # noqa: BLE001 — رمز معتم أو بلا exp → الافتراضي
            return None

    # -- عقد IdentityProvider ---------------------------------------------------
    def verify_upstream_token(self, token: str, *, now: Optional[int] = None) -> VerifiedAccount:
        """تحقق كامل من جلسة المنبع عند مصدر الحساب — فشل مغلق بلا امتيازات."""
        if not isinstance(token, str) or not token.strip():
            raise IdentityVerificationError("رمز جلسة المنبع مطلوب")
        if len(token) > _MAX_TOKEN_LENGTH:
            raise IdentityVerificationError("رمز جلسة المنبع أطول من الحد — مرفوض")
        # رموز الجلسات ASCII مطبوعة بلا فراغات — أي شيء آخر مدخل معطوب يرفض
        # مبكرًا (قبل أي نداء شبكي) برسالة موحدة.
        try:
            token.encode("ascii")
        except UnicodeEncodeError as exc:
            raise IdentityVerificationError("رمز جلسة المنبع غير صالح") from exc
        if any(ch.isspace() or ord(ch) < 0x21 for ch in token):
            raise IdentityVerificationError("رمز جلسة المنبع غير صالح")
        current = int(now if now is not None else _unix_now())

        user = self._userinfo(token)
        try:
            account_id = canonical_account_id(user.get("id"))
        except contract.AccountContractError as exc:
            raise IdentityVerificationError(
                "مصدر الحساب لم يثبت معرف حساب قانونيًا (UUID) — فشل مغلق"
            ) from exc
        email = user.get("email")
        role = self._role_from_profiles(account_id, token)
        scope = frozenset()
        if role == ROLE_COACH:
            scope = self._coach_scope(account_id, token)

        return _mint_verified_account(
            PROVIDER_NAME,
            account_id,
            role,
            scope=scope,
            email=email if isinstance(email, str) else None,
            expires_at=self._read_exp_hint(token),
            verified_at=current,
        )
