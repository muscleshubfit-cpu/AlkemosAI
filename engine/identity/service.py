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
- **رمز الخدمة للموقع**: `authenticate_service` يصدر جلسة خدمة نطاقها حساب
  المستخدم نفسه (كتابة الذاكرة نيابة عنه) — للواجهة الخلفية للموقع فقط
  بعد تحقق المنبع نفسه؛ لا جلسة خدمة بلا حساب موثق.
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
        self._provider = provider
        self._authority = authority
        self._resolver = IdentityResolver(
            authority,
            owner_account_ids=owner_account_ids,
            engine_token_ttl_seconds=engine_token_ttl_seconds,
        )
        self._account_index = account_index

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
        if not isinstance(upstream_token, str) or not upstream_token.strip():
            raise IdentityVerificationError(MSG_UPSTREAM_TOKEN_ONLY)
        account = self._provider.verify_upstream_token(upstream_token, now=now)
        if not is_verified_account(account):
            raise IdentityError(
                "المزود أعاد قيمة ليست حسابًا موثقًا — خرق عقد المزود (فشل مغلق)"
            )
        if self._account_index is not None:
            self._account_index.record(account)
        return account

    # -- الأبواب العامة -------------------------------------------------------
    def authenticate(self, upstream_token: str, *, now: Optional[int] = None) -> Dict:
        """تحقق المنبع ثم جلسة هوية المحرك (عميل/أدمن/مالك بحسب الربط والدور).

        المدخل الوحيد: رمز جلسة المنبع. لا يقبل البريد ولا الدور ولا أي
        بيانات يحددها المستدعي — إثبات الهوية والدور من مصدر الحساب حصرًا.
        """
        account = self._verify_upstream(upstream_token, now)
        return self._resolver.resolve(account, now=now)

    def authenticate_service(self, upstream_token: str, *, now: Optional[int] = None) -> Dict:
        """تحقق المنبع ثم جلسة خدمة نطاقها حساب المستخدم (لكبلة الموقع).

        للواجهة الخلفية للموقع تعمل نيابة عن جلسة مستخدم محقق — كتابة
        الذاكرة والتوثيق باسمه داخل نطاقه فقط. لا تمنح نطاق أي حساب آخر.
        """
        account = self._verify_upstream(upstream_token, now)
        return self._resolver.resolve_service(account, now=now)

    def verify_engine_token(self, token: str, *, now: Optional[int] = None) -> auth.Principal:
        """التحقق من رمز محرك قائم — نفس سلطة التحقق بلا مسار جديد."""
        return self._authority.verify(token, now=now)

    def is_owner_account(self, account_id: str) -> bool:
        try:
            return canonical_account_id(account_id) in self._resolver.owner_account_ids
        except IdentityError:
            return False
