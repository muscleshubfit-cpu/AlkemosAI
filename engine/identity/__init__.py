#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""engine/identity/ — طبقة الهوية الموحدة (دفعة 17 — ADR-0023).

حساب Alkemos (Alkemos.com — مصدر الهوية الأساسي) هو الهوية الوحيدة:
لا مصادقة مستقلة في المحرك — تحقق جهة الخدمة من جلسة المنبع ثم سكّ هوية
محرك قصيرة العمر عبر `TokenAuthority`.

المكونات:
- `contract` — عقد الحساب الموثق (معرف UUID قانوني · أدوار المنبع · مسارات
  المطالبات المتحكم بها) + `VerifiedAccount` (إنشاء محروس بالإغلاق).
- `resolver` — ترجمة الحساب إلى هوية محرك بأقل صلاحية (الملكية بربط معرف
  الحساب لا بالبريد ولا بالدور).
- `service` — `UnifiedIdentityService`: الباب العام (رمز منبع معتم فقط).
- `accounts` — فهرس حسابات المحرك: بيانات الهوية منفصلة عن بيانات النموذج.
- `server_proof` — مدقق برهان الخادم لبوابة جلسة الخدمة (حد الثقة).
- `replay` — ذاكرة استهلاك براهين الخادم (jti): أحادية الاستخدام، آمنة
  للخيوط والعمليات، محدودة زمنيًا، تنجو من إعادة التشغيل (استكمال
  المراجعة — إغلاق فجوة إعادة استخدام البرهان).
- `providers.jwks` — تحقق محلي بتوقيع غير متماثل (بروتوكول قياسي محايد).
- `providers.static` — مزود محاكاة **للاختبار فقط** (لا يسجل للإنتاج).

مزود مصدر الحساب الحالي (الاستعلام عند خدمة المصادقة) يعيش خارج هذه
الحزمة في `adapters/identity/` احترامًا لقانون الاستقلالية (engine/__init__
§القانون الحاكم: لا أسماء منصات داخل engine/) — التركيب النهائي وإعداد
المزود من `engine/settings.py` يتم هناك (جذر التركيب).
"""
from .contract import (  # noqa: F401
    ACCOUNT_ROLES,
    AccountContractError,
    IdentityError,
    IdentityVerificationError,
    ROLE_ADMIN,
    ROLE_CLIENT,
    ROLE_COACH,
    VerifiedAccount,
    canonical_account_id,
    is_canonical_account_id,
    is_verified_account,
    parse_claim_path,
    read_claim,
)
from .resolver import IdentityResolver  # noqa: F401
from .service import UnifiedIdentityService  # noqa: F401
from .accounts import AccountIndex, AccountIndexError  # noqa: F401
from .replay import (  # noqa: F401
    CACHE_SCHEMA as PROOF_REPLAY_SCHEMA,  # noqa: F401
    JTI_MAX_LENGTH,
    ProofReplayCache,
    ProofReplayError,
)
from .server_proof import (  # noqa: F401
    PROOF_AUDIENCE,
    PROOF_MAX_TTL_SECONDS,
    RSA_MIN_BITS,
    ServiceProofError,
    ServiceProofVerifier,
    parse_service_caller_keys,
)
from .providers.static import StaticProvider  # noqa: F401

# (مزودا الإنتاج — الاستعلام عند مصدر الحساب وJWKS — يعيشان في adapters/identity
# لأنهما يلمسان الشبكة والمحرك قانونه صفر استيراد شبكي داخل engine/.)

__all__ = [
    "ACCOUNT_ROLES",
    "AccountContractError",
    "AccountIndex",
    "AccountIndexError",
    "IdentityError",
    "IdentityResolver",
    "IdentityVerificationError",
    "JTI_MAX_LENGTH",
    "PROOF_AUDIENCE",
    "PROOF_MAX_TTL_SECONDS",
    "PROOF_REPLAY_SCHEMA",
    "ProofReplayCache",
    "ProofReplayError",
    "RSA_MIN_BITS",
    "ROLE_ADMIN",
    "ROLE_CLIENT",
    "ROLE_COACH",
    "ServiceProofError",
    "ServiceProofVerifier",
    "StaticProvider",
    "UnifiedIdentityService",
    "VerifiedAccount",
    "canonical_account_id",
    "is_canonical_account_id",
    "is_verified_account",
    "parse_claim_path",
    "parse_service_caller_keys",
    "read_claim",
]
