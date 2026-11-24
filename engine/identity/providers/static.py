#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""مزود المحاكاة الثابت — **للاختبار والمحاكاة فقط، لا يُسجل للإنتاج أبدًا**.

يوفر حسابات موثقة من جدول رموز محلي (بدون شبكة) لاختبار المحلل والخدمة
وفهرس الحسابات عزلًا عن أي منبع شبكي — ونفس الغرض في محاكاة التكامل بين
النظامين. **لا يظهر في سجل مزودات الإنتاج** (adapters/identity يرفضه)،
والتسمية صريحة في `provider` = "static-test" حتى يظهر في سجلات التدقيق
أن الجلسة من محاكاة لا من مصدر حساب حقيقي.

هذا ليس باب مصادقة خلفيًا: من يملك جدول الرموز يملك المحاكاة فقط، ورموز
المحرك الناتجة تظل مقيدة بمفاتيح `TokenAuthority` وقوانين المحلل.
"""
from __future__ import annotations

import time
from typing import Callable, Dict, Optional

from ..contract import (
    ACCOUNT_ROLES,
    IdentityVerificationError,
    VerifiedAccount,
    canonical_account_id,
)
from ..contract import _mint_verified_account

PROVIDER_NAME = "static-test"


def _unix_now() -> int:
    return int(time.time())


class StaticProvider:
    """مزود محاكاة: رمز → {account_id, role, scope?, email?, expires_at?}.

    يقبل قاموسًا أو دالة resolver(token) -> dict. الرمز المجهول يرفض مثل أي
    منبع (رسالة موحدة — لا تعداد). كل الحسابات تمر بعقد
    `canonical_account_id`/`ACCOUNT_ROLES` نفسه.
    """

    def __init__(self, accounts) -> None:
        if callable(accounts):
            self._resolve = accounts
        elif isinstance(accounts, dict):
            def _from_dict(token: str) -> Optional[Dict]:
                return self._accounts.get(token)
            self._accounts = {
                str(k): dict(v) for k, v in accounts.items()
            }
            self._resolve = _from_dict
        else:
            raise ValueError("StaticProvider يقبل قاموسًا أو دالة")
        self.name = PROVIDER_NAME

    def verify_upstream_token(self, token: str, *, now: Optional[int] = None) -> VerifiedAccount:
        if not isinstance(token, str) or not token.strip():
            raise IdentityVerificationError("رمز منبع غير صالح")
        record = self._resolve(token)
        if record is None:
            raise IdentityVerificationError(
                "رمز المنبع غير صالح أو منتهٍ — رفض موحد (لا تعداد)"
            )
        role = record.get("role")
        if role not in ACCOUNT_ROLES:
            raise IdentityVerificationError(
                f"دور حساب غير معروف في المحاكاة: {role!r}"
            )
        scope = frozenset(
            canonical_account_id(c) for c in (record.get("scope") or ())
        )
        expires_at = record.get("expires_at")
        return _mint_verified_account(
            PROVIDER_NAME,
            canonical_account_id(record.get("account_id")),
            role,
            scope=scope,
            email=record.get("email"),
            expires_at=int(expires_at) if expires_at is not None else None,
            verified_at=int(now if now is not None else _unix_now()),
        )
