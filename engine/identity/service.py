#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""خدمة الهوية الموحدة — الباب العام الوحيد لهوية Alkemos في المحرك (دفعة 17).

هذه هي الواجهة التي يستهلكها المضيف/محول الإنتاج: كل دخول يمر عبر
`authenticate(upstream_token)` — **رمز منبع معتم (نص) فقط**، لا بريد ولا دور
ولا أي بيانات هوية من المستدعي. المسار:

    رمز جلسة Alkemos.com (يقدمه الموقع جهة الخدمة)
      → المزود يتحقق من مصدر الحساب (شبكة موثوقة أو توقيع غير متماثل)
      → VerifiedAccount (معرف الحساب + الدور من جهة الخدمة)
      → المحلل يسكّ رمز محرك قصير العمر (TokenAuthority)
      → جلسة {principal, token, expires_at} للاستهلاك الداخلي

قوانين الباب:
- **رمز الخدمة للموقع + برهان الخادم (مراجعة دفعة 17):**
  `authenticate_service` تصدر جلسة خدمة نطاقها حساب المستخدم نفسه (كتابة
  الذاكرة نيابة عنه) — للواجهة الخلفية للموقع فقط. **امتلاك رمز جلسة
  العميل وحده لا يكفي أبدًا**: على المستدعي تقديم **برهان خادم**
  (`server_proof`) موقعًا RS256 بمفتاح خادم الموقع الخاص ومرتبطًا بهذا
  الرمز وهذا الحساب (تحقق بالمفتاح العام المثبت —
  `engine/identity/server_proof.py`)؛ وبلا مفاتيح خادم مثبتة البوابة
  معطلة كليًا (فشل مغلق). حد الثقة مُصمم ومختبر، ولا ربط إنتاجي هنا.
- **ترتيب العمليات (استكمال المراجعة):** لا تسجيل في فهرس الحسابات ولا
  أحداث ولا أي أثر جانبي قبل نجاح التحقق الكامل — في بوابة الخدمة:
  التحقق من المنبع ثم برهان الخادم ثم سكّ الجلسة **ثم** التسجيل؛
  الاستدعاء المرفوض لا يترك أثرًا (مختبر). والبرهان أحادي الاستخدام
  (jti — `engine/identity/replay.py`): استهلاك jti بعد نجاح التحقق كله
  ورفض إعادة الاستخدام خلال الصلاحية (مختبر مع التزامن وإعادة التشغيل).
- **verify_engine_token**: التحقق من رمز محرك قائم (للمستهلكين/الواجهة
  المستقبلية) — نفس `TokenAuthority.verify` بلا مسار جديد.
- **فهرس الحسابات** (إن وُفر): يسجل ظهور الحساب (بيانات هوية منفصلة عن
  بيانات النموذج — `accounts.AccountIndex`).
- **لا واجهة مستخدم هنا**: عقود جاهزة للتمرير (قواميس JSON-قابلة-للتمثيل)
  — واجهة AlkemosAI المستقلة المستقبلية تستهلكها كما هي (ADR-0023 §الخطة).
"""
from __future__ import annotations

import time
from typing import Dict, FrozenSet, Iterable, Optional

from .. import auth
from .accounts import AccountIndex
from .contract import (
    IdentityError,
    IdentityVerificationError,
    VerifiedAccount,
    canonical_account_id,
    is_verified_account,
)
from .resolver import IdentityResolver
from .server_proof import ServiceProofError, ServiceProofVerifier

MSG_UPSTREAM_TOKEN_ONLY = (
    "الدخول يقبل رمز جلسة المنبع (Alkemos.com) حصرًا — لا بريد ولا دور ولا "
    "بيانات هوية من المستدعي (التحقق جهة الخدمة عند مصدر الحساب)"
)


def _unix_now() -> int:
    return int(time.time())


class UnifiedIdentityService:
    """الباب الموحد: تحقق المنبع → هوية محرك — بلا أي مدخل هوية من المستدعي."""

    def __init__(
        self,
        provider,
        authority: auth.TokenAuthority,
        *,
        owner_account_ids: Iterable[str] = (),
        engine_token_ttl_seconds: Optional[int] = None,
        account_index: Optional[AccountIndex] = None,
        service_proof_verifier: Optional[ServiceProofVerifier] = None,
    ) -> None:
        verify_fn = getattr(provider, "verify_upstream_token", None)
        if not callable(verify_fn):
            raise IdentityError(
                "المزود يجب أن يطبق عقد IdentityProvider.verify_upstream_token"
            )
        if not isinstance(authority, auth.TokenAuthority):
            raise IdentityError(
                "الخدمة تتطلب TokenAuthority — مفاتيح المحرك شرط للسكّ"
            )
        if service_proof_verifier is not None and not isinstance(
            service_proof_verifier, ServiceProofVerifier
        ):
            raise IdentityError(
                "مدقق برهان الخادم يجب أن يكون ServiceProofVerifier — لا كائنات "
                "مجهولة عند حد الثقة"
            )
        self._provider = provider
        self._authority = authority
        self._resolver = IdentityResolver(
            authority,
            owner_account_ids=owner_account_ids,
            engine_token_ttl_seconds=engine_token_ttl_seconds,
        )
        self._account_index = account_index
        self._service_proof_verifier = service_proof_verifier

    # -- أدوات ---------------------------------------------------------------
    @property
    def provider_name(self) -> str:
        return str(getattr(self._provider, "name", "unknown"))

    @property
    def owner_account_ids(self) -> FrozenSet[str]:
        return self._resolver.owner_account_ids

    def describe(self) -> Dict:
        """قناع آمن للعرض/التشخيص — بلا مفاتيح ولا رموز."""
        return {
            "provider": self.provider_name,
            "owner_accounts_count": len(self._resolver.owner_account_ids),
            "account_index": self._account_index is not None,
        }

    def _verify_upstream(self, upstream_token, now: Optional[int]) -> VerifiedAccount:
        """تحقق المنبع **فقط — بلا أي أثر جانبي** (لا فهرس ولا أحداث).

        التسجيل في الفهرس مسؤولية الباب المُستدعى **بعد** نجاح تحققه الكامل
        (أمر مراجعة الدفعة 17-استكمال: لا تسجيل ولا أحداث قبل نجاح برهان
        الخادم في بوابة الخدمة؛ الأحداث أرشيف للظهور الموثق لا سجل محاولات).
        """
        if not isinstance(upstream_token, str) or not upstream_token.strip():
            raise IdentityVerificationError(MSG_UPSTREAM_TOKEN_ONLY)
        account = self._provider.verify_upstream_token(upstream_token, now=now)
        if not is_verified_account(account):
            raise IdentityError(
                "المزود أعاد قيمة ليست حسابًا موثقًا — خرق عقد المزود (فشل مغلق)"
            )
        return account

    def _record_account(self, account: VerifiedAccount) -> None:
        """تسجيل الحساب في الفهرس (بيانات هوية فقط) — إن وُجد الفهرس."""
        if self._account_index is not None:
            self._account_index.record(account)

    # -- الأبواب العامة -------------------------------------------------------
    def authenticate(self, upstream_token: str, *, now: Optional[int] = None) -> Dict:
        """تحقق المنبع ثم جلسة هوية المحرك (عميل/أدمن/مالك بحسب الربط والدور).

        المدخل الوحيد: رمز جلسة المنبع. لا يقبل البريد ولا الدور ولا أي
        بيانات يحددها المستدعي — إثبات الهوية والدور من مصدر الحساب حصرًا.
        (السلوك الحالي محفوظ كما هو بأمر المالك: تسجيل الفهرس بعد نجاح
        تحقق المنبع مباشرة.)
        """
        account = self._verify_upstream(upstream_token, now)
        self._record_account(account)
        return self._resolver.resolve(account, now=now)

    def authenticate_service(
        self,
        upstream_token: str,
        *,
        server_proof: Optional[str] = None,
        now: Optional[int] = None,
    ) -> Dict:
        """بوابة جلسة الخدمة — رمز المنبع **+ برهان خادم موثوق** حصرًا.

        (مراجعة دفعة 17 — أمر المالك: لا هوية service ذات صلاحية كتابة
        الذاكرة بمجرد امتلاك رمز جلسة العميل.) للواجهة الخلفية للموقع
        تعمل نيابة عن جلسة مستخدم محقق — كتابة الذاكرة والتوثيق باسمه
        داخل نطاقه فقط، ولا تمنح نطاق أي حساب آخر.

        حد الثقة المعمول هنا: رمز المنبع وحده يثبت **الحساب** لا
        **المستدعي** — فالرمز يملكه العميل نفسه. إثبات أن الاستدعاء صادر
        من خادم الموقع الموثوق يأتي من ``server_proof``: برهان قصير العمر
        موقع RS256 بمفتاح الخادم الخاص (يقيم عند الموقع حصرًا) ومرتبط
        بهذا الرمز (بصمة sha256) وهذا الحساب (sub) وجمهور المحرك —
        والتحقق بالمفتاح العام المثبت في إعداد المحرك فقط (لا سر
        مشترك). بلا مفاتيح خادم مثبتة: البوابة معطلة كليًا (فشل مغلق)
        — لا استدعاء واحد يمر. الاستدعاءات غير الموثوقة (بلا برهان /
        برهان بمفتاح غير مثبت / برهان لرمز أو حساب آخر / منتهٍ / فوق
        سقف العمر / توقيع فاسد / jti مستهلك — إعادة استخدام) مرفوضة
        كلها بصوت عالٍ (مختبرة).

        **ترتيب العمليات (أمر المراجعة — استكمال):** لا تسجيل في
        AccountIndex ولا أحداث فهرس ولا أي أثر جانبي **قبل** نجاح
        التحقق الكامل — تحقق المنبع ثم برهان الخادم ثم سكّ الجلسة؛
        التسجيل يقع آخرًا بعد نجاح كل شيء، فالاستدعاء المرفوض (برهان
        مرفوض · بوابة معطلة · جلسة منبع منتهية) لا يترك أثرًا واحدًا:
        لا ظهور حساب ولا عدّاد جلسة ولا حدث. البرهان نفسه أحادي
        الاستخدام (jti — ``engine/identity/replay.py``): استهلاكه بعد
        نجاح التحقق كله، فإعادة استخدامه خلال صلاحيته مرفوضة.
        """
        account = self._verify_upstream(upstream_token, now)
        if self._service_proof_verifier is None:
            raise ServiceProofError(
                "بوابة جلسة الخدمة معطلة (فشل مغلق): لا مفاتيح برهان خادم "
                "مثبتة (ALKEMOS_SERVICE_CALLER_KEYS) — هوية الخدمة ذات كتابة "
                "الذاكرة لا تُمنح بامتلاك رمز جلسة العميل وحده أبدًا"
            )
        self._service_proof_verifier.verify(
            server_proof,
            account_id=account.account_id,
            upstream_token=upstream_token,
            now=now,
        )
        session = self._resolver.resolve_service(account, now=now)
        # الآثار الجانبية آخرًا — بعد نجاح التحقق الكامل حصرًا:
        # استدعاء مرفوض = لا فهرس ولا أحداث ولا عدّاد.
        self._record_account(account)
        return session

    def verify_engine_token(self, token: str, *, now: Optional[int] = None) -> auth.Principal:
        """التحقق من رمز محرك قائم — نفس سلطة التحقق بلا مسار جديد."""
        return self._authority.verify(token, now=now)

    def is_owner_account(self, account_id: str) -> bool:
        try:
            return canonical_account_id(account_id) in self._resolver.owner_account_ids
        except IdentityError:
            return False
