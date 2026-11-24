#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""إعدادات المحرك — الهوية الموحدة من مصدر حساب Alkemos (دفعة 17 — ADR-0023).

(دفعة 16 كانت تعتمد بريد المالك هويةً للمحرك — **أُلغي بدفعة 17 بقرار
المالك: نظام الحساب الموحد**. البريد لم يعد هوية ولا يمنح ملكية؛ الملكية
ترتبط بمعرف حساب قانوني من مصدر الهوية.)

القوانين:
- **Alkemos.com مصدر الهوية الأساسي:** لا مصادقة مستقلة في المحرك —
  الإعدادات هنا تختار مزود التحقق وتربط معرفات حسابات المالك، وكل القيم
  من متغيرات البيئة (SECURITY §1: لا أسرار ولا إعدادات إنتاج في المستودع).
- **الملكية بمعرف الحساب لا بالبريد:** ``ALKEMOS_OWNER_ACCOUNT_IDS`` قائمة
  معرفات UUID (مفصولة بفواصل) لحسابات المالك — كانونية عند القراءة،
  والقائمة الفارغة = لا مالك متاح (فشل مغلق للعمليات الملكية حتى يضبطها
  المالك — فجوة إقلاع موثقة في ADR-0023).
- **مفتاح النشر (anon key) ليس سرًّا:** قيمة معلنة يستعملها مزود الاستعلام
  في نداءات التحقق — تعيش في البيئة لا في المستودع (سياسة الأسرار §1
  تخص الأسرار؛ هذا إعداد عام غير سري).
- **لا تجاوز بديلًا:** تغيير معرفات حسابات المالك قرار مالك موثق (DECISIONS)
  — القيم تقرأ من البيئة عند الاستيراد والمرجع الوحيد للاستهلاك هو
  ``adapters/identity`` وخدمة الهوية.
- **فشل مغلق:** الإعدادات الناقصة لا تسقط لقيم افتراضية مبتورة — جذر
  التركيب يرفض البناء بصوت عالٍ عند النقص.
"""
from __future__ import annotations

import os
from typing import FrozenSet, Optional, Tuple

from .identity.contract import canonical_account_id, parse_claim_path
from .identity.server_proof import parse_service_caller_keys


class IdentitySettingsError(RuntimeError):
    """إعداد هوية ناقص أو غير قانوني — صوت عالٍ لا قيم افتراضية داخلية."""


def _int_env(name: str, default: int) -> int:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return int(default)
    try:
        return int(raw)
    except ValueError as exc:
        raise IdentitySettingsError(f"{name} يجب أن يكون عددًا صحيحًا — {raw!r}") from exc


def _parse_owner_ids(raw: str) -> FrozenSet[str]:
    """تقنين قائمة معرفات حسابات المالك من البيئة إلى UUID كانوني مجمد.

    أي قيمة غير قانونية ترفض بصوت عالٍ (لا إسقاط صامت: معرف مالك تالف
    قرار تصحيح لا تجاهل). البريد مرفوض هنا صراحة — ليس معرف حساب.
    """
    ids = set()
    for part in (raw or "").split(","):
        part = part.strip()
        if not part:
            continue
        try:
            ids.add(canonical_account_id(part))
        except Exception as exc:
            raise IdentitySettingsError(
                f"ALKEMOS_OWNER_ACCOUNT_IDS تحوي قيمة غير قانونية ({part!r}): "
                "المطلوب UUID من مصدر الحساب — البريد ليس معرف حساب (فشل مغلق)"
            ) from exc
    return frozenset(ids)


#: اسم مزود التحقق من الهوية (قابل للتبديل بلا تغيير المستهلكين):
#: supabase-introspection (الافتراضي — الاستعلام عند مصدر الحساب القائم)
#: أو jwks (تحقق محلي بتوقيع غير متماثل عبر مفاتيح عامة منشورة).
IDENTITY_PROVIDER: str = (
    os.environ.get("ALKEMOS_IDENTITY_PROVIDER", "").strip() or "supabase-introspection"
)

#: رابط مصدر الحساب (مثال الإنتاج: رابط HTTPS لمشروع Supabase) — إلزامي
#: لمزود الاستعلام، ويعمل قيمة iss المتوقعة لمزود JWKS.
IDENTITY_ISSUER: str = os.environ.get("ALKEMOS_IDENTITY_ISSUER", "").strip()

#: مفتاح النشر العام لمصدر الحساب (anon/publishable key) — **ليس سرًّا**
#: (معلن في واجهة الموقع أصلًا)؛ يستخدمه مزود الاستعلام في نداءات التحقق.
IDENTITY_ANON_KEY: str = os.environ.get("ALKEMOS_IDENTITY_ANON_KEY", "").strip()

#: رابط مجموعة المفاتيح العامة (JWKS) — إلزامي لمزود jwks فقط.
IDENTITY_JWKS_URL: str = os.environ.get("ALKEMOS_IDENTITY_JWKS_URL", "").strip()

#: الجمهور المتوقع (aud) لرموز المنبع — اختياري (لمزود jwks).
IDENTITY_AUDIENCE: Optional[str] = (
    os.environ.get("ALKEMOS_IDENTITY_AUDIENCE", "").strip() or None
)

#: مسار مطالبة الدور داخل رمز المنبع (مفاتيح مفصولة بفواصل — اختياري لمزود
#: jwks؛ يجب أن يكون مطالبة متحكمًا بها جهة الخدمة مثل app_metadata —
#: المسارات المبدوءة بـuser_metadata ترفض في العقد).
IDENTITY_ROLE_CLAIM_PATH: Optional[Tuple[str, ...]] = parse_claim_path(
    os.environ.get("ALKEMOS_IDENTITY_ROLE_CLAIM_PATH", "").strip() or None
)

#: مسار مطالبة نطاق المدرب داخل رمز المنبع — اختياري لمزود jwks.
IDENTITY_SCOPE_CLAIM_PATH: Optional[Tuple[str, ...]] = parse_claim_path(
    os.environ.get("ALKEMOS_IDENTITY_SCOPE_CLAIM_PATH", "").strip() or None
)

#: مهلة نداءات التحقق (ثوانٍ) — فشل المهلة فشل مغلق.
IDENTITY_HTTP_TIMEOUT_SECONDS: int = _int_env(
    "ALKEMOS_IDENTITY_HTTP_TIMEOUT_SECONDS", 10
)

#: عمر رمز المحرك الافتراضي (ثوانٍ) — لا يتجاوز جلسة المنبع أبدًا
#: (يسقّه المحلل) ولا سقف نوع الرمز في engine/auth.py.
IDENTITY_ENGINE_TOKEN_TTL_SECONDS: int = _int_env(
    "ALKEMOS_IDENTITY_ENGINE_TOKEN_TTL_SECONDS", 12 * 3600
)

#: معرفات حسابات المالك (UUID قانونية) — الملكية بمعرف الحساب لا بالبريد.
#: الفارغة = لا عمليات ملكية متاحة (فشل مغلق) حتى يضبطها المالك.
OWNER_ACCOUNT_IDS: FrozenSet[str] = _parse_owner_ids(
    os.environ.get("ALKEMOS_OWNER_ACCOUNT_IDS", "")
)

#: مفاتيح خادم الموقع العامة لبوابة جلسة الخدمة (برهان الخادم — مراجعة
#: دفعة 17). الصيغة: عناصر مفصولة بفواصل، كل عنصر ``kid:n_hex:e_hex``.
#: هذه مفاتيح **عامة** (تحقق فقط) لا أسرار؛ المفتاح الخاص يقيم عند
#: خادم الموقع حصرًا. القيمة الفارغة = بوابة جلسة الخدمة معطلة كليًا
#: (فشل مغلق — امتلاك رمز جلسة العميل وحده لا يفتحها أبدًا). أي قيمة
#: ملتبسة أو مفتاح أضعف من 2048 بت يُرفض بصوت عالٍ عند الاستيراد.
SERVICE_CALLER_KEYS = parse_service_caller_keys(
    os.environ.get("ALKEMOS_SERVICE_CALLER_KEYS", "")
)

#: جذر ذاكرة استهلاك براهين الخادم (jti — استكمال مراجعة الدفعة 17):
#: مسار **مطلق خارج شجرة git** (مستوى أ — بيانات تشغيلية) تحفظ فيه
#: هويات البراهين المستهلكة حتى انتهاء صلاحيته؛ فإعادة استخدام البرهان
#: مرفوضة حتى عبر إعادة تشغيل المحرك. **إلزامي عند تفعيل مفاتيح الخادم**
#: (جذر التركيب يرفض البناء بصوت عالٍ بدونه — فشل مغلق: بوابة خدمة بلا
#: ذاكرة استهلاك باقية عبر إعادة التشغيل = نافذة إعادة استخدام عند كل
#: إقلاع). يُرفض المسار النسبي أو داخل شجرة git عند البناء.
SERVICE_PROOF_REPLAY_ROOT: str = (
    os.environ.get("ALKEMOS_SERVICE_PROOF_REPLAY_ROOT", "").strip()
)


def is_owner_account_id(account_id: str) -> bool:
    """هل المعرف ضمن معرفات حسابات المالك؟ (بعد التقنين — بلا رفع استثناء)."""
    try:
        return canonical_account_id(account_id) in OWNER_ACCOUNT_IDS
    except Exception:  # noqa: BLE001 — عقد المعرف: القيم غير القانونية ليست مالكًا
        return False
