#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""مزود JWKS — تحقق محلي بتوقيع غير متماثل (بروتوكول قياسي محايد للمزود).

هذا المزود يعيش **خارج engine/** مع مزود الاستعلام (adapters/identity/)
لأنه يلمس الشبكة (جلب المفاتيح العامة عبر HTTPS) — والمحرك قانونه صفر
استيراد شبكي داخل engine/ (فحص الاستقلالية §6 في test_engine_security.py).
عقد الحساب نفسه (VerifiedAccount) يعيش في engine/identity/contract.

هذا هو المسار الثاني في عقد الهوية الموحد (ADR-0023): بدل الاستعلام عند
مصدر الحساب مع كل دخول (adapters/identity)، يتحقق المحرك محليًا من رمز
منبع موقّع **توقيعًا غير متماثل** (RS256) عبر مجموعة مفاتيح عامة منشورة
(JWKS). لا سر هنا إطلاقًا: المفتاح العام ليس مفتاح توقيع، والتحقق المحلي
لا يشارك أي سر مع الموقع (قانون «لا مشاركة مفاتيح التوقيع»).

متى يستخدم: عندما يفعّل مصدر الحساب مفاتيح توقيع غير متماثلة لرموزه (فجوة
موثقة: تفعيلها على مشروع المنبع خطوة نشر بيد المالك — لم يتحقق منها هذه
الدفعة بلا اتصال إنتاجي)، أو مع أي مزود هوية مستقبلي ينشر JWKS قياسيًا
(واجهة AlkemosAI المستقلة المستقبلية تدخل من هنا بلا تغيير المستهلكين).

القوانين:
- **RS256 حصرًا الآن**: HS256 («none» وأخواتها) مرفوض، وES256 يرفض برسالة
  صريحة (فجوة موثقة — لا ادعاء دعم غير منفذ).
- **حد أدنى 2048 بت لمفاتيح RSA (مراجعة دفعة 17):** أي مفتاح JWKS معياره
  أقصر من ``RSA_MIN_BITS`` يُرفض **عند حلّ المفتاح قبل التحقق من
  التوقيع** — فلا يُستهلك توقيع أبدًا بمفتاح ضعيف مهما كان الرمز سليم
  الشكل (مختبر سالبًا: 512/1024/2047 بت كلها مرفوضة).
- **الفحوص الستة**: توقيع RSA (PKCS#1 v1.5 + SHA-256) · iss · aud (إن ضُبط)
  · exp · iat (لا مستقبل بتسامح ساعة) · nbf (إن وُجدت).
- **الدور من مطالبة متحكم بها جهة الخدمة فقط**: مسار المطالبة يضبط
  بالإعداد ويُرفض إن بدأ من `user_metadata` (كتابتها بيد المستخدم —
  `contract.parse_claim_path`). بلا مسار مضبوط: الحساب الناشئ يترجم
  **عميلًا** (نفس افتراض مصدر الحساب لأي تسجيل جديد — لا اختراع).
- **sub هو معرف الحساب**: يجب أن يكون UUID — لا يقبل بريدًا هوية.
- المفاتيح تُجلب عبر HTTPS (استثناء loopback صريح للاختبار المحلي فقط —
  بمعامل مستقل لا يُفعّل من إعداد الإنتاج).
- تنفيذ التحقق رياضي خالص بلا أي مكتبة خارجية (قانون المحرك: stdlib فقط)
  — RSAverify بالأسّ العام e على البصمة المعاد بناؤها وفق PKCS#1 v1.5.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
import urllib.error
import urllib.request
from typing import Callable, Dict, FrozenSet, Optional, Tuple

from engine.identity.contract import (
    AccountContractError,
    IdentityVerificationError,
    ROLE_CLIENT,
    ROLE_COACH,
    VerifiedAccount,
    canonical_account_id,
    parse_claim_path,
    read_claim,
)
from engine.identity.contract import _mint_verified_account

PROVIDER_NAME = "jwks"
DEFAULT_CACHE_TTL_SECONDS = 3600
DEFAULT_CLOCK_SKEW_SECONDS = 60
DEFAULT_HTTP_TIMEOUT_SECONDS = 10
SUPPORTED_ALGS = ("RS256",)

#: الحد الأدنى لطول معيار RSA (بت) لمفاتيح JWKS — مفروض قبل التحقق من
#: التوقيع (مراجعة دفعة 17 — أمر المالك). مطابق لسياسة مفاتيح خادم
#: الموقع في engine/identity/server_proof.py.
RSA_MIN_BITS = 2048

# DigestInfo المرمّز DER لـ SHA-256 (PKCS#1 v1.5 — التمثيل القانوني الوحيد)
_SHA256_DIGEST_INFO_PREFIX = bytes.fromhex("3031300d060960864801650304020105000420")

_LOOPBACK_HOSTS = ("127.0.0.1", "localhost", "::1")


def _b64d(text: str) -> bytes:
    pad = "=" * (-len(text) % 4)
    return base64.urlsafe_b64decode(text + pad)


def _unix_now() -> int:
    return int(time.time())


def require_https_url(url: str, *, allow_insecure_loopback: bool = False, what: str = "URL") -> str:
    """فرض HTTPS على عناوين المنبع — استثناء loopback صريح للاختبار فقط."""
    if not isinstance(url, str) or not url.strip():
        raise AccountContractError(f"{what} مطلوب (HTTPS)")
    stripped = url.strip()
    if stripped.startswith("https://"):
        return stripped
    if stripped.startswith("http://"):
        host = stripped[len("http://"):].split("/", 1)[0].split(":", 1)[0]
        if allow_insecure_loopback and host in _LOOPBACK_HOSTS:
            return stripped
    raise AccountContractError(
        f"{what} يجب أن يكون HTTPS (استثناء loopback الاختباري لا يُفعّل من "
        "إعداد الإنتاج) — رفضت {stripped!r}"
    )


def _rsa_pkcs1v15_sha256_verify(n: int, e: int, signature: bytes, message: bytes) -> bool:
    """تحقق RSA PKCS#1 v1.5 مع SHA-256 — رياضي خالص بلا مكتبات خارجية.

    يعيد بناء التمثيل المتوقع (EM) بالكامل ويقارن زمن-ثابت: أي خلل في
    الطول أو القيمة يرفض. لا «تحقق تقريبي» ولا مقارنة بادئات.
    """
    k = (n.bit_length() + 7) // 8
    if k < 64 or len(signature) != k:
        return False
    s = int.from_bytes(signature, "big")
    if s >= n:
        return False
    em = pow(s, e, n).to_bytes(k, "big")
    digest_info = _SHA256_DIGEST_INFO_PREFIX + hashlib.sha256(message).digest()
    if len(digest_info) + 11 > k:
        return False
    expected = (
        b"\x00\x01"
        + b"\xff" * (k - len(digest_info) - 3)
        + b"\x00"
        + digest_info
    )
    return hmac.compare_digest(em, expected)


class JwksProvider:
    """مزود هوية يتحقق محليًا من رموز RS256 عبر مفاتيح JWKS العامة.

    البناء:
    - `issuer`: قيمة iss المطلوبة حرفيًا (HTTPS).
    - `jwks_url` **أو** `jwks_fetcher` (قابل حقن للاختبار — يعيد قاموس JWKS).
    - `audience`: قيمة aud المطلوبة إن ضُبطت.
    - `role_claim_path` / `scope_claim_path`: مسارات مطالبات متحكم بها
      جهة الخدمة (يُرفض المسار المبدوء بـuser_metadata — كتابته بيد المستخدم).
    """

    def __init__(
        self,
        *,
        issuer: str,
        jwks_url: Optional[str] = None,
        jwks_fetcher: Optional[Callable[[], Dict]] = None,
        audience: Optional[str] = None,
        role_claim_path=None,
        scope_claim_path=None,
        cache_ttl_seconds: int = DEFAULT_CACHE_TTL_SECONDS,
        clock_skew_seconds: int = DEFAULT_CLOCK_SKEW_SECONDS,
        http_timeout_seconds: int = DEFAULT_HTTP_TIMEOUT_SECONDS,
        allow_insecure_loopback: bool = False,
    ) -> None:
        if jwks_url and jwks_fetcher:
            raise AccountContractError("jwks_url وjwks_fetcher لا يجتمعان — مصدر واحد")
        if not jwks_url and not jwks_fetcher:
            raise AccountContractError("مطلوب jwks_url أو jwks_fetcher لمصدر المفاتيح")
        self._issuer = require_https_url(
            issuer, allow_insecure_loopback=allow_insecure_loopback, what="issuer"
        )
        if jwks_url:
            self._jwks_url = require_https_url(
                jwks_url, allow_insecure_loopback=allow_insecure_loopback, what="jwks_url"
            )
        else:
            self._jwks_url = None
        self._jwks_fetcher = jwks_fetcher
        self._audience = audience if audience else None
        self._role_claim_path = parse_claim_path(role_claim_path)
        self._scope_claim_path = parse_claim_path(scope_claim_path)
        self._cache_ttl = int(cache_ttl_seconds)
        self._skew = int(clock_skew_seconds)
        self._timeout = int(http_timeout_seconds)
        self._allow_loopback = bool(allow_insecure_loopback)
        self._keys: Dict[str, Tuple[Dict, int]] = {}
        self._jwks_fetched_at = 0
        self.name = PROVIDER_NAME

    # -- جلب المفاتيح مع تخزين وتحديث ----------------------------------------
    def _fetch_jwks(self) -> Dict:
        if self._jwks_fetcher is not None:
            data = self._jwks_fetcher()
        else:
            req = urllib.request.Request(
                self._jwks_url,
                headers={"Accept": "application/json"},
                method="GET",
            )
            try:
                with urllib.request.urlopen(req, timeout=self._timeout) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
            except (urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
                raise IdentityVerificationError(
                    f"تعذر جلب مفاتيح JWKS من المنبع: {exc}"
                ) from exc
        if not isinstance(data, dict) or not isinstance(data.get("keys"), list):
            raise IdentityVerificationError("وثيقة JWKS غير قانونية (keys مفقودة)")
        return data

    def _key_for_kid(self, kid: Optional[str], now: int) -> Tuple[int, int]:
        cached = self._keys.get(kid) if kid else None
        if cached is not None and now - cached[1] < self._cache_ttl:
            jwk = cached[0]
        else:
            data = self._fetch_jwks()
            self._keys = {}
            self._jwks_fetched_at = now
            for jwk in data["keys"]:
                k = jwk.get("kid")
                if k:
                    self._keys[str(k)] = (jwk, now)
            cached = self._keys.get(kid) if kid else None
            if cached is None:
                raise IdentityVerificationError(
                    f"المفتاح العام {kid!r} غائب عن JWKS — رمز بمفتاح مجهول مرفوض"
                )
            jwk = cached[0]
        if jwk.get("kty") != "RSA" or jwk.get("alg") not in SUPPORTED_ALGS:
            raise IdentityVerificationError(
                f"مفتاح JWKS غير مدعوم (kty/alg): {jwk.get('kty')}/{jwk.get('alg')} — "
                f"المدعوم {list(SUPPORTED_ALGS)}"
            )
        try:
            n = int.from_bytes(_b64d(str(jwk["n"])), "big")
            e = int.from_bytes(_b64d(str(jwk["e"])), "big")
        except (KeyError, ValueError) as exc:
            raise IdentityVerificationError("مفتاح JWKS تالف (n/e)") from exc
        if n <= 0 or e <= 0:
            raise IdentityVerificationError("مفتاح JWKS غير قانوني (n/e)")
        # (مراجعة دفعة 17) سياسة قوة المفتاح — قبل التحقق من التوقيع:
        # المفتاح الأضعف من 2048 بت يُرفض هنا فلا يصل التوقيع أبدًا.
        if n.bit_length() < RSA_MIN_BITS:
            raise IdentityVerificationError(
                f"مفتاح JWKS {kid!r} بطول {n.bit_length()} بت أضعف من الحد "
                f"الأدنى {RSA_MIN_BITS} بت — مرفوض قبل التحقق من التوقيع "
                "(سياسة مفاتيح RS256)"
            )
        return n, e

    # -- التحقق من رمز المنبع ---------------------------------------------------
    def verify_upstream_token(self, token: str, *, now: Optional[int] = None) -> VerifiedAccount:
        """تحقق كامل محلي: توقيع RS256 + iss/aud/exp/iat/nbf + معرف الحساب."""
        if not isinstance(token, str) or not token.strip() or token.count(".") != 2:
            raise IdentityVerificationError("رمز منبع غير صالح (JWT بثلاثة أجزاء)")
        header_b64, payload_b64, sig_b64 = token.split(".")
        try:
            header = json.loads(_b64d(header_b64).decode("utf-8"))
            payload = json.loads(_b64d(payload_b64).decode("utf-8"))
            signature = _b64d(sig_b64)
        except Exception as exc:
            raise IdentityVerificationError("ترميز الرمز غير قابل للقراءة") from exc
        if not isinstance(header, dict) or not isinstance(payload, dict):
            raise IdentityVerificationError("حمولة/رأس الرمز غير قانونية")

        alg = header.get("alg")
        if alg not in SUPPORTED_ALGS:
            if alg == "ES256":
                raise IdentityVerificationError(
                    "ES256 غير مدعوم بعد (فجوة موثقة — ADR-0023): استخدم RS256"
                )
            raise IdentityVerificationError(
                f"خوارزمية توقيع غير مدعومة: {alg!r} — المسموح {list(SUPPORTED_ALGS)}"
            )

        current = int(now if now is not None else _unix_now())
        n, e = self._key_for_kid(header.get("kid"), current)
        signing_input = (
            header_b64.encode("ascii") + b"." + payload_b64.encode("ascii")
        )
        if not _rsa_pkcs1v15_sha256_verify(n, e, signature, signing_input):
            raise IdentityVerificationError("توقيع الرمز غير صالح — هوية غير موثقة")

        if payload.get("iss") != self._issuer:
            raise IdentityVerificationError("مصدر الرمز (iss) غير مطابق")
        if self._audience is not None:
            aud = payload.get("aud")
            aud_ok = aud == self._audience or (
                isinstance(aud, list) and self._audience in aud
            )
            if not aud_ok:
                raise IdentityVerificationError("جمهور الرمز (aud) غير مطابق")
        exp = payload.get("exp")
        if not isinstance(exp, (int, float)) or int(exp) <= current:
            raise IdentityVerificationError("الرمز منتهي الصلاحية — لا وصول برمز ميت")
        iat = payload.get("iat")
        if isinstance(iat, (int, float)) and int(iat) > current + self._skew:
            raise IdentityVerificationError("رمز صادر في المستقبل — مرفوض")
        nbf = payload.get("nbf")
        if isinstance(nbf, (int, float)) and int(nbf) > current + self._skew:
            raise IdentityVerificationError("الرمز غير سارٍ بعد (nbf) — مرفوض")

        sub = payload.get("sub")
        try:
            account_id = canonical_account_id(sub)
        except AccountContractError as exc:
            raise IdentityVerificationError(
                f"sub ليس معرف حساب قانونيًا (UUID): {sub!r} — البريد ليس هوية"
            ) from exc

        # الدور: مطالبة متحكم بها جهة الخدمة حصرًا — أو عميل (افتراض أي
        # حساب جديد في مصدر الهوية؛ لا اختراع آلية أدوار غير موجودة).
        role = None
        if self._role_claim_path:
            role = read_claim(payload, self._role_claim_path)
        if role is None:
            role = ROLE_CLIENT
        if role not in (ROLE_CLIENT, ROLE_COACH, "admin"):
            raise IdentityVerificationError(
                f"دور غير معروف من مطالبة الرمز: {role!r} — فشل مغلق"
            )
        scope = frozenset()
        if self._scope_claim_path and role == ROLE_COACH:
            raw_scope = read_claim(payload, self._scope_claim_path)
            if isinstance(raw_scope, (list, tuple)):
                scope = frozenset(
                    canonical_account_id(c) for c in raw_scope
                    if isinstance(c, str) and c.strip()
                )

        email = payload.get("email")
        return _mint_verified_account(
            PROVIDER_NAME,
            account_id,
            role,
            scope=scope,
            email=email if isinstance(email, str) else None,
            subject=str(sub) if sub else None,
            expires_at=int(exp),
            verified_at=current,
        )
