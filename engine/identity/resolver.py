#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""محلل الهوية: الحساب الموثق → هوية المحرك (دفعة 17 — ADR-0023).

المحلل هو **المترجم الوحيد** من حساب مصدر الهوية (Alkemos.com) إلى هوية
المحرك (`Principal` عبر `TokenAuthority.mint`): يفحص الحساب بنيويًا ثم
يترجم الدور والنطاق بأقل صلاحية، ويسكّ رمز محرك قصير العمر مفتاحه
المستخدم حسب النوع (رموز المالك بمفتاح المالك المستقل حصرًا — قانون
`engine/auth.py`).

قانون الترجمة (أقل صلاحية — لا اختراع آليات غير موجودة):
- **الملكية بربط الحساب لا بالبريد ولا بالدور:** الحساب الذي معرفه ضمن
  `owner_account_ids` (معرفات حسابات المالك من إعداد جهة الخدمة —
  `ALKEMOS_OWNER_ACCOUNT_IDS`) يترجم مالكًا **مهما كان دوره أو بريده في
  المنبع**؛ وما عداه لا يبلغ الملكية أبدًا — حساب ببريد المالك القديم
  ليس مالكًا لمجرد بريده (أمر المالك الصريح).
- **admin المنبع → أدمن محرك** بنطاق كل الحسابات (حوكمة) — بلا حذف نهائي
  وبلا كتابة ذاكرة (سقف نوع الأدمن في `engine/auth.py`).
- **coach المنبع → أدمن محرك بنطاق عملائه المسندون** من مصدر الهوية
  حصرًا؛ والمدرب بلا عملاء مسندين يترجم **عميلًا لنفسه فقط** (أقل صلاحية:
  لا مسندَين = لا نطاق حوكمة).
- **client المنبع → عميل محرك لنفسه فقط.**
- **عمر رمز المحرك لا يتجاوز جلسة المنبع:** انتهاء الجلسة المنبع سقف صلب
  (رمز محرك أطول من جلسة المستخدم = جلسة بلا مصدر) — والجلسة المنتهية
  أصلًا مرفوضة قبل السك.
- الدور غير المعروف مرفوض (فشل مغلق) — لا افتراض دور افتراضي مجهول.
"""
from __future__ import annotations

import time
from typing import Dict, FrozenSet, Iterable, Optional

from .. import auth
from .contract import (
    AccountContractError,
    IdentityError,
    ROLE_ADMIN,
    ROLE_CLIENT,
    ROLE_COACH,
    VerifiedAccount,
    canonical_account_id,
    is_verified_account,
)

DEFAULT_ENGINE_TOKEN_TTL_SECONDS = auth.DEFAULT_TTL_SECONDS


def _unix_now() -> int:
    return int(time.time())


class IdentityResolver:
    """مترجم الحساب الموثق إلى هوية محرك — بلا أي مدخل من المستدعي.

    يُبنى بصلاحيات جهة الخدمة (المضيف) ويستهلكه
    `UnifiedIdentityService`؛ لا يستقبل بريدًا ولا دورًا من المستدعي
    أبدًا — مدخله `VerifiedAccount` من مزود موثق حصرًا.
    """

    def __init__(
        self,
        authority: auth.TokenAuthority,
        *,
        owner_account_ids: Iterable[str] = (),
        engine_token_ttl_seconds: Optional[int] = None,
    ) -> None:
        if not isinstance(authority, auth.TokenAuthority):
            raise IdentityError(
                "المحلل يتطلب TokenAuthority — لا سكّ هوية بلا مفاتيح المحرك"
            )
        self._authority = authority
        owner_ids = frozenset(
            canonical_account_id(a) for a in (owner_account_ids or ())
        )
        self._owner_account_ids: FrozenSet[str] = owner_ids
        ttl = int(engine_token_ttl_seconds or DEFAULT_ENGINE_TOKEN_TTL_SECONDS)
        if ttl <= 0 or ttl > auth.MAX_TTL_SECONDS:
            raise IdentityError(
                f"عمر رمز المحرك يجب أن يكون بين ثانية و{auth.MAX_TTL_SECONDS} ثانية"
            )
        self._ttl = ttl

    # -- أدوات ---------------------------------------------------------------
    @property
    def owner_account_ids(self) -> FrozenSet[str]:
        """معرفات حسابات المالك (كانونية) — ربط حساب لا بريد."""
        return self._owner_account_ids

    def is_owner_account(self, account_id: str) -> bool:
        try:
            return canonical_account_id(account_id) in self._owner_account_ids
        except IdentityError:
            return False

    def _effective_expiry(self, account: VerifiedAccount, now: int) -> int:
        """انتهاء رمز المحرك: الأقصر بين العمر الافتراضي وجلسة المنبع."""
        expires_at = now + self._ttl
        if account.expires_at is not None:
            upstream = int(account.expires_at)
            if upstream <= now:
                raise IdentityError(
                    "جلسة المنبع منتهية — لا هوية محرك بجلسة ميتة"
                )
            expires_at = min(expires_at, upstream)
        if expires_at <= now:
            raise IdentityError("العمر المحسوب غير موجب — مرفوض")
        return expires_at

    def _mint(self, kind: str, account: VerifiedAccount, now: int,
              *, clients=None, all_clients: bool = False, as_service: bool = False) -> Dict:
        expires_at = self._effective_expiry(account, now)
        principal_id = account.account_id  # المعرف الموثوق الثابت — لا البريد
        token = self._authority.mint(
            kind,
            principal_id,
            clients=clients,
            all_clients=all_clients,
            ttl_seconds=expires_at - now,
            now=now,
        )
        principal = self._authority.verify(token, now=now)
        return {
            "status": "authenticated",
            "provider": account.provider,
            "account_id": account.account_id,
            "upstream_role": account.role,
            "email": account.email,           # معلومات عرض فقط — لا هوية
            "principal": principal,           # للتمرير إلى MemoryService ونحوه
            "principal_desc": principal.describe(),
            "token": token,                   # للمضيف/الواجهة (تخزينه مسؤوليتهما)
            "token_kind": kind,
            "expires_at": principal.expires_at,
            "expires_in": principal.expires_at - now,
        }

    # -- الترجمة ---------------------------------------------------------------
    def resolve(self, account, *, now: Optional[int] = None) -> Dict:
        """ترجمة حساب موثق إلى هوية محرك نهائية (client/admin/owner)."""
        if not is_verified_account(account):
            raise IdentityError(
                "المحلل يقبل حسابًا موثقًا من مزود حصرًا — لا قيم من المستدعي"
            )
        current = int(now if now is not None else _unix_now())
        # الملكية بربط الحساب أولًا — قبل الدور وقبل البريد (أمر المالك):
        # لا بريد يصنع مالكًا ولا دور منبع يمنح الملكية.
        if self.is_owner_account(account.account_id):
            return self._mint(auth.KIND_OWNER, account, current, all_clients=True)
        if account.role == ROLE_ADMIN:
            return self._mint(auth.KIND_ADMIN, account, current, all_clients=True)
        if account.role == ROLE_COACH:
            if account.scope:
                return self._mint(
                    auth.KIND_ADMIN, account, current, clients=set(account.scope)
                )
            # مدرب بلا عملاء مسندين: أقل صلاحية — عميل لنفسه فقط.
            return self._mint(auth.KIND_CLIENT, account, current)
        if account.role == ROLE_CLIENT:
            return self._mint(auth.KIND_CLIENT, account, current)
        raise IdentityError(
            f"دور حساب غير معروف من مصدر الهوية: {account.role!r} — فشل مغلق"
        )

    def resolve_service(self, account, *, now: Optional[int] = None) -> Dict:
        """ترجمة حساب موثق إلى **جلسة خدمة** نطاقها الحساب نفسه.

        هذا عقد خدمة المنصة (الواجهة الخلفية للموقع تعمل نيابة عن جلسة
        المستخدم): كتابة الذاكرة والتوثيق باسم الحساب — نطاقها ذلك الحساب
        وحده، فلا تبلغ ذاكرة غيره مهما عُرف معرفه. الحساب هنا يجب أن يكون
        موثقًا من المنبع بنفس مسار التحقق (لا خدمة بلا حساب موثق).
        """
        if not is_verified_account(account):
            raise IdentityError(
                "المحلل يقبل حسابًا موثقًا من مزود حصرًا — لا قيم من المستدعي"
            )
        current = int(now if now is not None else _unix_now())
        return self._mint(
            auth.KIND_SERVICE, account, current,
            clients={account.account_id}, as_service=True,
        )
