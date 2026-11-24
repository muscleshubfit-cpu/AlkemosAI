#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""برهان الخادم لبوابة جلسة الخدمة — حد الثقة بين الموقع والمحرك.

(مراجعة دفعة 17 — أمر المالك: «لا يجوز إصدار هوية service ذات صلاحية
كتابة الذاكرة بمجرد امتلاك رمز جلسة العميل، دون إثبات أن الاستدعاء صادر
من خادم موثوق. صمّم حد ثقة واضحًا بين الموقع والمحرك، واختبر رفض
الاستدعاءات غير الموثوقة، دون تنفيذ ربط إنتاجي أو إنشاء واجهة».)

المشكلة التي يعالجها هذا الملف: رمز جلسة العميل (Supabase) يملكه العميل
نفسه — فأي حائز له (المتصفح مثلًا) يستطيع نظريًا منادات بوابة الخدمة إن
قبلت المحرك الرمز وحده. **برهان الخادم** هو الطبقة الثانية التي تثبت أن
الاستدعاء صادر من خادم الموقع الموثوق:

    خادم الموقع (يحمل رمز جلسة المستخدم + مفتاح توقيع الخادم الخاص)
      → يبني برهانًا قصير العمر موقّعًا RS256:
        {"aud": "alkemos-engine-service",
         "sub": <معرف حساب المستخدم>,
         "tok": <sha256 لرمز الجلسة — ربط البرهان بهذا الرمز بعينه>,
         "iat": ..., "exp": ...}
      → المحرك يتحقق: التوقيع بمفتاح خادم الموقع **العام المثبت** +
         الجمهور + الحساب + ربط الرمز + العمر القصير.

خصائص الحد (كلها مختبرة):
- **غير متماثل — لا سر مشترك:** المحرك يتحقق بالمفتاح العام المثبت في
  إعداده (`ALKEMOS_SERVICE_CALLER_KEYS`) فقط؛ مفتاح التوقيع الخاص يقيم
  عند خادم الموقع حصرًا ولا يدخل المحرك أبدًا (نفس فلسفة ADR-0023).
- **مرتبط بالرمز والحساب:** البرهان يخص رمز الجلسة بعينه (بصمة sha256)
  وحسابه (sub) — فلا يعاد استخدامه لرمز آخر ولا لحساب آخر.
- **قصير العمر إلزاميًا:** عمر البرهان ≤ ``PROOF_MAX_TTL_SECONDS`` (300ث)
  — لا برهان طويل العمر يُخزَّن ويعاد استخدامه.
- **أحادي الاستخدام (jti — استكمال المراجعة):** كل برهان يحمل ``jti``
  (هويته الفريدة) **إلزاميًا**؛ أول تحقق ناجح يستهلك الـjti في
  ``ProofReplayCache`` (``engine/identity/replay.py`` — ذاكرة آمنة محدودة
  زمنيًا تنجو من إعادة التشغيل) وكل إعادة استخدام للبرهان نفسه خلال
  صلاحيته مرفوضة بصوت عالٍ — والاستهلاك يقع **بعد نجاح التحقق كله**
  (التوقيع والربط والصلاحية) فلا برهان فاسد يحرق هوية برهان سواه ولا
  يسمّم الذاكرة.
- **fail-closed:** بلا مفاتيح خادم مثبتة في المحرك = بوابة الخدمة معطلة
  كليًا (`UnifiedIdentityService.authenticate_service` ترفض كل استدعاء).
- **سياسة المفاتيح نفسها:** مفتاح الخادم العام يقبل فقط إن كان معياره
  ≥ ``RSA_MIN_BITS`` (2048 بت — مطابق لسياسة مفاتيح JWKS) وأسّه سليمًا.

هذه الوحدة نقية (stdlib حصرًا، لا شبكة) داخل ``engine/identity`` — رياضيات
تحقق RSA مكررة هنا عمدًا من ``adapters/identity/jwks.py`` لأن المحرك لا
يستورد adapters (قانون صفر استيراد شبكي داخل engine/).

النشر (فجوة G-07 موثقة — لا ربط إنتاجي في هذه الدفعة): توليد زوج مفاتيح
الخادم، إقامة الخاص عند خادم الموقع، وتثبيت العام في بيئة المحرك — كلها
خطوات تشغيل بقرار المالك عند الربط الحي (D-17).
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
from typing import Dict, Optional, Tuple

from .contract import IdentityError, canonical_account_id
from .replay import JTI_MAX_LENGTH, ProofReplayCache, ProofReplayError

#: الجمهور الإلزامي لبرهان الخادم — لا يشاركه أي برهان آخر
PROOF_AUDIENCE = "alkemos-engine-service"

#: أقصى عمر لبرهان الخادم (ثوانٍ) — برهان طويل العمر يُرفض
PROOF_MAX_TTL_SECONDS = 300

#: الحد الأدنى لطول معيار RSA (بت) لمفاتيح خادم الموقع — نفس سياسة JWKS
RSA_MIN_BITS = 2048

#: سماحية انحراف الساعة على iat (ثوانٍ)
PROOF_CLOCK_SKEW_SECONDS = 60

#: الخوارزمية الوحيدة المقبولة للبرهان (تثبيت الخوارزمية — لا التباس)
PROOF_ALG = "RS256"

# DigestInfo المرمّز DER لـ SHA-256 (PKCS#1 v1.5) — نفس ثابت jwks.py
_SHA256_DIGEST_INFO_PREFIX = bytes.fromhex(
    "3031300d060960864801650304020105000420"
)


class ServiceProofError(IdentityError):
    """رفض برهان الخادم — الاستدعاء غير موثوق أو البوابة معطلة (فشل مغلق)."""


def _b64d(text: str) -> bytes:
    pad = "=" * (-len(text) % 4)
    return base64.urlsafe_b64decode(text + pad)


def _rsa_pkcs1v15_sha256_verify(n: int, e: int, signature: bytes, message: bytes) -> bool:
    """تحقق RSA PKCS#1 v1.5 + SHA-256 — رياضي خالص (نفس jwks.py، مقصود)."""
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


def _check_key_pair(kid: str, n: int, e: int) -> Tuple[int, int]:
    """سياسة مفتاح خادم الموقع العام — نفس قوانين مفاتيح JWKS حرفيًا."""
    if not isinstance(kid, str) or not kid.strip():
        raise ServiceProofError("kid مطلوب غير فارغ لكل مفتاح خادم")
    if not isinstance(n, int) or not isinstance(e, int):
        raise ServiceProofError(f"مفتاح الخادم '{kid}': n/e يجب أن يكونا أعدادًا صحيحة")
    if n < 3 or n % 2 == 0:
        raise ServiceProofError(f"مفتاح الخادم '{kid}': معيار غير سليم (زوجي أو أصغر من 3)")
    if n.bit_length() < RSA_MIN_BITS:
        raise ServiceProofError(
            f"مفتاح الخادم '{kid}' بطول {n.bit_length()} بت أضعف من الحد الأدنى "
            f"{RSA_MIN_BITS} بت — مرفوض (سياسة مفاتيح RS256 نفسها)"
        )
    if e < 3 or e % 2 == 0 or e >= 2 ** 32:
        raise ServiceProofError(
            f"مفتاح الخادم '{kid}': أس عام غير سليم (زوجي أو خارج 3..2^32)"
        )
    return n, e


def parse_service_caller_keys(raw: str) -> Dict[str, Tuple[int, int]]:
    """تحليل مفاتيح خادم الموقع العامة من إعداد بيئة نصي إلى خريطة kid→(n,e).

    الصيغة: عناصر مفصولة بفواصل، كل عنصر ``kid:n_hex:e_hex`` (n وe بصيغة
    hex). القيمة الفارغة تعيد خريطة فارغة = البوابة معطلة (fail-closed —
    الغرض اختياري بقرار نشر). أي قيمة ملتبسة أو مفتاح ضعيف يُرفض بصوت
    عالٍ (لا إسقاط صامت).
    """
    keys: Dict[str, Tuple[int, int]] = {}
    for entry in (raw or "").split(","):
        entry = entry.strip()
        if not entry:
            continue
        parts = [p.strip() for p in entry.split(":")]
        if len(parts) != 3 or not parts[0] or not parts[1] or not parts[2]:
            raise ServiceProofError(
                f"إدخال مفتاح خادم غير صالح: {entry!r} — الصيغة kid:n_hex:e_hex"
            )
        kid, n_hex, e_hex = parts
        if kid in keys:
            raise ServiceProofError(f"kid مكرر لمفاتيح الخادم: {kid!r}")
        try:
            n = int(n_hex, 16)
            e = int(e_hex, 16)
        except ValueError as exc:
            raise ServiceProofError(
                f"مفتاح الخادم '{kid}': n/e ليسا hex قانونيًا"
            ) from exc
        keys[kid] = _check_key_pair(kid, n, e)
    return keys


class ServiceProofVerifier:
    """مدقق برهان الخادم — يتحقق فقط (لا يوقّع أبدًا — المفتاح الخاص عند الموقع).

    ``replay_cache``: ذاكرة استهلاك الـjti — **حماية إعادة الاستخدام دائمًا
    مفعّلة** (لا يمكن إيقافها): إن لم تُمرر ذاكرة صريحة أُنشئت ذاكرة
    داخل العملية تلقائيًا؛ وللنشر الحي تُمرر ذاكرة ملفية من جذر التركيب
    (تنجو من إعادة التشغيل — انظر adapters/identity).
    """

    def __init__(
        self,
        public_keys: Dict[str, Tuple[int, int]],
        *,
        clock_skew_seconds: int = PROOF_CLOCK_SKEW_SECONDS,
        max_ttl_seconds: int = PROOF_MAX_TTL_SECONDS,
        replay_cache: Optional[ProofReplayCache] = None,
    ) -> None:
        if not isinstance(public_keys, dict) or not public_keys:
            raise ServiceProofError(
                "مدقق البرهان يتطلب مفتاح خادم عامًا واحدًا على الأقل — بلا "
                "مفاتيح لا بوابة خدمة (fail-closed)"
            )
        checked: Dict[str, Tuple[int, int]] = {}
        for kid, pair in public_keys.items():
            if not isinstance(pair, (tuple, list)) or len(pair) != 2:
                raise ServiceProofError(
                    f"مفتاح الخادم '{kid}' يجب أن يكون زوج (n, e)"
                )
            checked[kid] = _check_key_pair(kid, pair[0], pair[1])
        self._keys = checked
        self._skew = int(clock_skew_seconds)
        self._max_ttl = int(max_ttl_seconds)
        if replay_cache is not None and not isinstance(replay_cache, ProofReplayCache):
            raise ServiceProofError(
                "ذاكرة استهلاك البراهين يجب أن تكون ProofReplayCache — لا "
                "كائنات مجهولة عند حد الثقة"
            )
        # حماية إعادة الاستخدام لا تُوقف أبدًا: بلا ذاكرة صريحة = ذاكرة
        # داخل العملية (الحماية داخل العملية مضمونة دائمًا؛ النشر الحي
        # يمرر ذاكرة ملفية تنجو من إعادة التشغيل من جذر التركيب).
        self._replay = replay_cache if replay_cache is not None else ProofReplayCache()

    @property
    def key_ids(self) -> Tuple[str, ...]:
        return tuple(sorted(self._keys))

    def verify(
        self,
        proof,
        *,
        account_id: str,
        upstream_token: str,
        now: Optional[int] = None,
    ) -> None:
        """تحقق برهان الخادم مقابل (الحساب + رمز الجلسة) — يرفض بصوت عالٍ.

        النجاح لا يعيد شيئًا؛ كل فشل ``ServiceProofError`` (فشل مغلق — لا
        جلسة خدمة جزئية). البرهان لا يثبت شيئًا إلا إذا كان: موقعًا بمفتاح
        مثبت، بجمهور المحرك، للحساب نفسه، مرتبطًا برمز الجلسة نفسه (بصمة
        sha256)، غير منتهٍ، وعمره ضمن السقف.
        """
        import time as _time

        current = int(now if now is not None else _time.time())
        if not isinstance(proof, str) or not proof.strip() or proof.count(".") != 2:
            raise ServiceProofError(
                "برهان خادم مفقود أو غير صالح — بوابة الخدمة لا تفتح برمز "
                "جلسة العميل وحده (حد الثقة بين الموقع والمحرك)"
            )
        header_b64, payload_b64, sig_b64 = proof.split(".")
        try:
            header = json.loads(_b64d(header_b64).decode("utf-8"))
            payload = json.loads(_b64d(payload_b64).decode("utf-8"))
            signature = _b64d(sig_b64)
        except Exception as exc:
            raise ServiceProofError("ترميز برهان الخادم غير قابل للقراءة") from exc
        if not isinstance(header, dict) or not isinstance(payload, dict):
            raise ServiceProofError("ترويسة/حمولة البرهان يجب أن تكونا كائنين")

        # تثبيت الخوارزمية — لا التباس (none/HS256/ES256 مرفوضة)
        if header.get("alg") != PROOF_ALG:
            raise ServiceProofError(
                f"خوارزمية برهان الخادم غير مقبولة: {header.get('alg')!r} — "
                f"{PROOF_ALG} حصرًا (تثبيت الخوارزمية)"
            )
        typ = header.get("typ")
        if typ is not None and typ != "JWT":
            raise ServiceProofError(f"نوع البرهان غير مقبول: {typ!r}")

        kid = header.get("kid")
        if not isinstance(kid, str) or not kid.strip():
            raise ServiceProofError("kid مطلوب في برهان الخادم لاختيار المفتاح")
        key = self._keys.get(kid.strip())
        if key is None:
            raise ServiceProofError(
                f"مفتاح خادم غير معروف: {kid!r} — برهان بمفتاح غير مثبت "
                "(fail-closed: لا تحقق بمفتاح غير مهيأ)"
            )
        n, e = key

        # الجمهور: برهان المحرك حصرًا — لا يعاد استخدامه لغرض آخر
        if payload.get("aud") != PROOF_AUDIENCE:
            raise ServiceProofError(
                "جمهور برهان الخادم لا يطابق بوابة الخدمة — برهان غرض آخر"
            )

        # الحساب: البرهان يجب أن يكون لنفس حساب رمز الجلسة
        sub = payload.get("sub")
        try:
            proof_account = canonical_account_id(sub)
        except Exception as exc:
            raise ServiceProofError(
                "sub في برهان الخادم ليس معرف حساب قانونيًا (UUID)"
            ) from exc
        try:
            expected = canonical_account_id(account_id)
        except Exception as exc:
            raise ServiceProofError(
                "حساب رمز الجلسة غير قانوني — لا مطابقة برهان"
            ) from exc
        if proof_account != expected:
            raise ServiceProofError(
                "برهان الخادم لحساب غير حساب رمز الجلسة — مرفوض (الربط بالحساب)"
            )

        # ربط الرمز: بصمة sha256 لرمز الجلسة — البرهان لا يخدم رمزًا آخر
        tok = payload.get("tok")
        expected_tok = hashlib.sha256(
            (upstream_token or "").encode("utf-8")
        ).hexdigest()
        if not isinstance(tok, str) or not hmac.compare_digest(
            tok.lower(), expected_tok
        ):
            raise ServiceProofError(
                "برهان الخادم غير مرتبط برمز الجلسة هذا (بصمة الرمز لا تطابق) "
                "— لا إعادة استخدام برهان لرمز آخر"
            )

        # الزمن: عمر قصير إلزامي · منتهٍ مرفوض · مستقبلي مرفوض
        iat = payload.get("iat")
        exp = payload.get("exp")
        if not isinstance(iat, int) or not isinstance(exp, int):
            raise ServiceProofError("iat/exp في برهان الخادم أعداد صحيحة إلزامية")
        if exp <= current:
            raise ServiceProofError("برهان الخادم منتهي الصلاحية — مرفوض")
        if iat > current + self._skew:
            raise ServiceProofError("برهان خادم صادر في المستقبل — مرفوض")
        if exp - iat <= 0 or exp - iat > self._max_ttl:
            raise ServiceProofError(
                f"عمر برهان الخادم خارج السقف (الحد {self._max_ttl} ثانية) — "
                "البراهين قصيرة العمر حصرًا"
            )

        # التوقيع — قبل الاستهلاك حصرًا: لا يُسجَّل jti لبرهان لم يثبت أنه
        # موقع بمفتاح خادم الموقع المثبت (وإلا لأمكن حرق هويات براهين سواها)
        message = (
            header_b64.encode("ascii") + b"." + payload_b64.encode("ascii")
        )
        if not _rsa_pkcs1v15_sha256_verify(n, e, signature, message):
            raise ServiceProofError(
                "توقيع برهان الخادم غير صالح — لم يصدر عن خادم الموقع الموثوق"
            )

        # jti: هوية البرهان أحادية الاستخدام — إلزامية (فشل مغلق: لا برهان
        # بلا هوية فريدة يمكن استهلاكها ومنع إعادة استخدامه)
        jti = payload.get("jti")
        if (
            not isinstance(jti, str)
            or not jti.strip()
            or len(jti) > JTI_MAX_LENGTH
        ):
            raise ServiceProofError(
                f"jti في برهان الخادم مطلوب إلزاميًا (نص غير فارغ بطول "
                f"≤{JTI_MAX_LENGTH} حرفًا) — برهان بلا هوية أحادية الاستخدام "
                "مرفوض (منع إعادة الاستخدام)"
            )

        # الاستهلاك أحادي الاستخدام — **بعد نجاح التحقق كله حصرًا** (التوقيع
        # والربط والصلاحية): البراهين الفاسدة لا تحرق هويات سواها؛ إعادة
        # استخدام البرهان خلال صلاحيته (jti مستهلك) مرفوضة بصوت عالٍ.
        # أجل المدخل = انتهاء البرهان + سماحية الساعة (تغطية عقدة متأخرة
        # عن ساعة الموقع)؛ يسقط المدخل بعد أجله فورًا (ذاكرة محدودة زمنيًا).
        try:
            self._replay.consume(jti, valid_until=exp + self._skew, now=current)
        except ProofReplayError as exc:
            raise ServiceProofError(str(exc)) from exc
