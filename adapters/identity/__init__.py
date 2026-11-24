#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""جذر تركيب الهوية الموحد — يبني الخدمة من إعدادات المحرك (دفعة 17).

التركيب النهائي خارج حزمة المحرك (قانون الاستقلالية): هذا الجذر يقرأ
`engine/settings.py` (متغيرات البيئة — لا أسرار في المستودع) ويسجل مزودات
الإنتاج المعروفة:

- ``supabase-introspection`` (الافتراضي): الاستعلام عند مصدر الحساب القائم
  (Alkemos.com — Supabase Auth) — نفس آلية تحقق الموقع جهة الخدمة.
- ``jwks``: تحقق محلي بتوقيع غير متماثل عبر مفاتيح عامة منشورة (يفعّل عند
  تفعيل مفاتيح التوقيع غير المتماثلة في المنبع — فجوة نشر موثقة).

``static-test`` **مرفوض هنا عمدًا**: مزود محاكاة للاختبار فقط ولا يظهر في
سجل الإنتاج أبدًا.

مفاتيح المحرك (ALKEMOS_MEMORY_AUTH_KEY/ALKEMOS_MEMORY_OWNER_KEY) تُقرأ من
البيئة عبر `TokenAuthority.from_env` — خاصة بالمحرك ولا تشارك الموقع.
"""
from __future__ import annotations

from engine import settings
from engine.auth import TokenAuthority
from engine.identity import UnifiedIdentityService
from .jwks import JwksProvider

PRODUCTION_PROVIDERS = ("supabase-introspection", "jwks")


def build_identity_service(*, environ=None) -> UnifiedIdentityService:
    """بناء خدمة الهوية الموحدة من إعدادات المحرك البيئية.

    تفشل بصوت عالٍ عند نقص أي إعداد لازم (فشل مغلق — لا قيم افتراضية
    داخلية لمصادر هوية).
    """
    provider_name = settings.IDENTITY_PROVIDER
    if provider_name not in PRODUCTION_PROVIDERS:
        raise settings.IdentitySettingsError(
            f"مزود هوية غير معروف للإنتاج: {provider_name!r} — المعروف "
            f"{list(PRODUCTION_PROVIDERS)} (مزود المحاكاة للاختبار فقط)"
        )

    if provider_name == "supabase-introspection":
        if not settings.IDENTITY_ISSUER:
            raise settings.IdentitySettingsError(
                "ALKEMOS_IDENTITY_ISSUER مطلوب لمزود الاستعلام عند مصدر الحساب "
                "(رابط HTTPS لمشروع Supabase) — لا قيمة افتراضية داخلية"
            )
        from .supabase_introspection import SupabaseIntrospectionProvider

        provider = SupabaseIntrospectionProvider(
            issuer=settings.IDENTITY_ISSUER,
            anon_key=settings.IDENTITY_ANON_KEY,
            http_timeout_seconds=settings.IDENTITY_HTTP_TIMEOUT_SECONDS,
        )
    else:  # jwks
        if not settings.IDENTITY_JWKS_URL:
            raise settings.IdentitySettingsError(
                "ALKEMOS_IDENTITY_JWKS_URL مطلوب لمزود JWKS — لا قيمة افتراضية داخلية"
            )
        provider = JwksProvider(
            issuer=settings.IDENTITY_ISSUER or settings.IDENTITY_JWKS_URL,
            jwks_url=settings.IDENTITY_JWKS_URL,
            audience=settings.IDENTITY_AUDIENCE,
            role_claim_path=settings.IDENTITY_ROLE_CLAIM_PATH,
            scope_claim_path=settings.IDENTITY_SCOPE_CLAIM_PATH,
            http_timeout_seconds=settings.IDENTITY_HTTP_TIMEOUT_SECONDS,
        )

    # مفاتيح المحرك تُقرأ بعد صحة إعداد المزود — خاصة بالمحرك ولا تشارك الموقع.
    authority = TokenAuthority.from_env()

    # (مراجعة دفعة 17) حد الثقة لبوابة جلسة الخدمة: مفاتيح خادم الموقع
    # العامة المثبتة تفعّل بوابة الخدمة؛ غيابها = البوابة معطلة (فشل مغلق
    # — امتلاك رمز جلسة العميل وحده لا يفتحها أبدًا).
    service_proof_verifier = None
    if settings.SERVICE_CALLER_KEYS:
        from engine.identity.server_proof import ServiceProofVerifier

        service_proof_verifier = ServiceProofVerifier(settings.SERVICE_CALLER_KEYS)

    return UnifiedIdentityService(
        provider,
        authority,
        owner_account_ids=settings.OWNER_ACCOUNT_IDS,
        engine_token_ttl_seconds=settings.IDENTITY_ENGINE_TOKEN_TTL_SECONDS,
        service_proof_verifier=service_proof_verifier,
    )
