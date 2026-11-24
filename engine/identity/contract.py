#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""عقد الهوية الموحدة — حساب Alkemos هو مصدر الهوية الوحيد (دفعة 17 — ADR-0023).

القرار (أمر المالك 2026-11-24): إنشاء نظام حساب موحد بين Alkemos.com
وAlkemosAI — **Alkemos.com هو مصدر الهوية الأساسي**؛ كل حساب Alkemos قائم أو
جديد يستخدم المحرك بلا تسجيل منفصل، والهوية نفسها تخدم واجهة Alkemos.com
الحالية وأي واجهة AlkemosAI مستقلة مستقبلًا.

القوانين الحاكمة لهذه الطبقة:
- **لا مصادقة مستقلة في المحرك:** المحرك لا يملك تسجيل دخول ولا حسابات ولا
  كلمات مرور — حذفت `engine/owner_auth.py` بأمر الدفعة 17 (كان نظام دخولًا
  مستقلًا). الدخول يحدث في مصدر الحساب وحده، والمحرك **يتحقق** من جلسة
  المنبع جهة الخدمة ثم يسكّ هوية محرك قصيرة العمر.
- **التحقق جهة الخدمة حصرًا:** الهوية والدور يثبتان بمصدر الحساب نفسه (نداء
  تحقق موثوق أو توقيع غير متماثل عبر JWKS) — **لا يقبل أبدًا** بريد أو دور
  أو بيانات هوية يمررها المستدعي إثباتًا لأي شيء.
- **المعرف الموثوق الثابت:** هوية كل مستخدم في المحرك = **معرف الحساب
  الكانوني (UUID) من مصدر الحساب** — لا البريد. البريد معلومات عرض لا
  هوية ولا يمنح شيئًا (الملكية لا تُستنبط من البريد أبدًا — قرار المالك).
- **عقد قابل لتبديل المزود:** `IdentityProvider` عقد موحد (بروتوكول واحد)
  تُبنى فوقه مزودات: الاستعلام عند مصدر الحساب الحالي (خارج engine/ —
  adapters/identity) أو التحقق المحلي بتوقيع غير متماثل (JWKS — بروتوكول
  قياسي محايد هنا) أو مزود محاكاة للاختبار. تبديل المزود = إعداد بلا تغيير
  المستهلكين.
- **لا مشاركة مفاتيح توقيع:** الموقع لا يوقع للمحرك والمحرك لا يتحقق بمفتاح
  سري للموقع — الثقة تمر عبر التحقق من مصدر الحساب (نداء موثوق أو مفتاح
  **عام**). مفاتيح المحرك (`TokenAuthority`) خاصة به وحده.
- **بيانات الهوية منفصلة عن بيانات النموذج:** فهرس حسابات المحرك
  (`accounts.py`) يحمل بيانات الهوية (أول ظهور · الأدوار المشاهدة ·
  التفضيلات) خارج شجرة git، بينما بيانات النموذج (ذاكرة/موافقات) مفتاحها
  معرف الحساب نفسه — عزل بنيوي بلا خلط.

حدود الثقة (نموذج التهديد — التفصيل في
docs/04-architecture/unified-identity-architecture-2026-11-24.md):
- **الحد الأمني الحاسم لامتيازات المحرك** هو توقيع HMAC لرمز المحرك
  (`TokenAuthority`) بعد تحقق المنبع — لا يملكه المستدعي.
- **إغلاق الإنشاء هنا حارس صحة لا حد أمني** (نفس عقيدة `engine/auth.py`):
  مهاجم داخل العملية يستطيع قراءة خلايا الإغلاق وبناء `VerifiedAccount`
  بنيويًا — لكن سكّ رموز المحرك يبقى بيد من يملك `TokenAuthority`، والدخول
  العام للمستهلكين يمر حصرًا عبر `UnifiedIdentityService.authenticate` الذي
  لا يقبل إلا رمز منبع معتم (نص). المهاجم داخل العملية خارج نموذج التهديد
  المعلن (موثق).
"""
from __future__ import annotations

import uuid as _uuid
from typing import Dict, FrozenSet, Optional, Tuple

# ── أدوار الحساب في مصدر الهوية (Alkemos.com) ──────────────────────────────
ROLE_CLIENT = "client"   # عميل — نطاقه نفسه فقط (الافتراضي لأي حساب جديد)
ROLE_COACH = "coach"     # موظف منصة (مدرب) — نطاقه عملاؤه المسندون
ROLE_ADMIN = "admin"     # أدمن منصة — حوكمة على كل الحسابات
ACCOUNT_ROLES = (ROLE_CLIENT, ROLE_COACH, ROLE_ADMIN)

#: بادئة مسارات المطالبات المحظورة — كتابتها بيد المستخدم فلا تصلح مصدر دور
USER_WRITABLE_CLAIM_ROOTS = ("user_metadata",)


class IdentityError(RuntimeError):
    """خطأ في طبقة الهوية الموحدة — فشل مغلق بلا امتيازات."""


class IdentityVerificationError(IdentityError):
    """فشل التحقق من جلسة المنبع — الرمز غير صالح/منتهٍ أو المصدر رفضه."""


class AccountContractError(IdentityError):
    """خرق عقد الحساب الموثق — قيمة غير قانونية (معرف/دور/نطاق)."""


def canonical_account_id(value) -> str:
    """تقنين معرف الحساب إلى UUID الكانوني — المعرف الموثوق الثابت.

    يقبل الصور المكافئة (حروف كبيرة، بلا شرطات) ويعيد الصورة الكانونية
    الموحدة (شرطات · صغيرة). يرفض أي شيء ليس UUID — **البريد ليس معرف
    حساب** ولا يقبل هنا أبدًا.
    """
    if not isinstance(value, str) or not value.strip():
        raise AccountContractError("معرف الحساب مطلوب (UUID من مصدر الحساب)")
    try:
        parsed = _uuid.UUID(value.strip())
    except (ValueError, AttributeError) as exc:
        raise AccountContractError(
            f"معرف حساب غير قانوني ({value!r}): المطلوب UUID من مصدر الحساب — "
            "البريد وأي نص آخر ليس هوية"
        ) from exc
    return str(parsed)


def is_canonical_account_id(value) -> bool:
    """هل القيمة معرف حساب قانوني؟ (بلا رفع استثناء)."""
    try:
        canonical_account_id(value)
        return True
    except IdentityError:
        return False


def _define_verified_account():
    """تعريف VerifiedAccount ومسار إنشائها داخل إغلاق واحد.

    مفتاح الإنشاء يعيش داخل الإغلاق حصرًا (نفس نمط `engine/auth.py`):
    لا مصنع حساب عام — الإنشاء يتم عبر المصنع الداخلي الذي يستدعيه المزود
    بعد نجاح التحقق من المنبع. المستهلكون يتحققون بنيويًا عبر
    `is_verified_account` قبل أي استخدام.
    """
    _creation_key = object()

    class VerifiedAccount:
        """حساب موثق من مصدر الهوية — ناتج تحقق المزود حصرًا.

        الكائن مجمد عمليًا: لا وراثة ولا تعديل بعد الإنشاء. حقوله:
        - `account_id`: المعرف الموثوق الثابت (UUID قانوني) — هوية المحور.
        - `role`: دور الحساب في مصدر الهوية (client/coach/admin) — من جهة
          الخدمة حصرًا، لا من بيانات المستدعي.
        - `scope`: الحسابات التي يجوز للحساب العمل عليها (للمدرب: عملاؤه
          المسندون من مصدر الهوية) — فارغ لغير المدربين.
        - `email`: معلومات عرض فقط — لا تمنح هوية ولا دورًا ولا ملكية.
        - `subject`: معرف الموضوع في المنبع (عادة يساوي account_id).
        - `expires_at`: انتهاء جلسة المنبع (إن عُرف) — سقف عمر رمز المحرك.
        - `verified_at`: لحظة التحقق · `provider`: اسم المزود الموثق.
        """

        __slots__ = (
            "account_id", "role", "scope", "email", "subject",
            "expires_at", "verified_at", "provider",
        )

        def __init__(
            self,
            account_id: str,
            role: str,
            scope: FrozenSet[str],
            email: Optional[str],
            subject: str,
            expires_at: Optional[int],
            verified_at: int,
            provider: str,
            *,
            _creation=None,
        ) -> None:
            if _creation is not _creation_key:
                raise IdentityError(
                    "VerifiedAccount لا يُنشأ مباشرة ببيانات يحددها المستدعي — "
                    "الحساب الموثق ينشأ حصرًا داخل مزود هوية بعد التحقق من "
                    "مصدر الحساب (لا بريد ولا دور من المستدعي إثباتًا)"
                )
            object.__setattr__(self, "account_id", account_id)
            object.__setattr__(self, "role", role)
            object.__setattr__(self, "scope", scope)
            object.__setattr__(self, "email", email)
            object.__setattr__(self, "subject", subject)
            object.__setattr__(self, "expires_at", expires_at)
            object.__setattr__(self, "verified_at", verified_at)
            object.__setattr__(self, "provider", provider)

        def __init_subclass__(cls, **_kwargs) -> None:
            raise IdentityError("لا يُورَّث VerifiedAccount — الحساب الموثق من مسار التحقق حصرًا")

        def __setattr__(self, *_args) -> None:
            raise IdentityError("الحساب الموثق غير قابل للتعديل بعد الإنشاء")

        def describe(self) -> str:
            scope = ",".join(sorted(self.scope)) or "-"
            return f"{self.provider}:{self.account_id}({self.role}:{scope})"

        def __repr__(self) -> str:  # pragma: no cover — تشخيص فقط
            return f"VerifiedAccount({self.describe()})"

    def _mint_verified_account(
        provider: str,
        account_id: str,
        role: str,
        *,
        scope: FrozenSet[str] = frozenset(),
        email: Optional[str] = None,
        subject: Optional[str] = None,
        expires_at: Optional[int] = None,
        verified_at: int = 0,
    ) -> VerifiedAccount:
        """المصنع الداخلي — يستدعيه المزود بعد نجاح تحقق المنبع فقط.

        يطبق عقد الحساب كاملًا: معرف قانوني، دور معروف، نطاق حسابات قانونية.
        (خاصية داخلية بشرطة سفلية: المزودات الموثوقة وحدها تستوردها.)
        """
        canonical = canonical_account_id(account_id)
        if role not in ACCOUNT_ROLES:
            raise AccountContractError(
                f"دور حساب غير معروف من مصدر الهوية: {role!r} — "
                f"المعروف {list(ACCOUNT_ROLES)}"
            )
        clean_scope = frozenset(
            canonical_account_id(c) for c in (scope or frozenset())
        )
        return VerifiedAccount(
            account_id=canonical,
            role=role,
            scope=clean_scope,
            email=email if isinstance(email, str) and email.strip() else None,
            subject=subject if subject else canonical,
            expires_at=int(expires_at) if expires_at is not None else None,
            verified_at=int(verified_at),
            provider=str(provider or "unknown"),
            _creation=_creation_key,
        )

    return VerifiedAccount, _mint_verified_account


VerifiedAccount, _mint_verified_account = _define_verified_account()


def is_verified_account(value) -> bool:
    """بوابة المستهلكين: هل القيمة حسابًا موثقًا فعلًا (بنيويًا)؟

    يرفض النصوص والقواميس والأدوار المزعومة والأصناف البديلة أو الموروثة
    والكائنات الناقصة. (فحص بنيوي — الإثبات الحاسم لامتيازات المحرك يبقى
    توقيع `TokenAuthority` كما في `engine/auth.py`.)
    """
    if type(value) is not VerifiedAccount:
        return False
    try:
        value.describe()
        canonical_account_id(value.account_id)
        int(value.verified_at)
        if value.role not in ACCOUNT_ROLES:
            return False
    except Exception:
        return False
    return True


def parse_claim_path(path) -> Optional[Tuple[str, ...]]:
    """تقنين مسار مطالبة (claim path) من إعداد نصي إلى مسار قانوني أو بلا.

    الشكل: مفاتيح مفصولة بفواصل (مثل "app_metadata,engine_role"). يرفض
    المسارات التي تبدأ من بيانات المستخدم القابلة للكتابة (`user_metadata`)
    — كتابتها بيد المستخدم فلا تكون مصدر دور أبدًا.
    """
    if path is None:
        return None
    if isinstance(path, str):
        parts = tuple(p.strip() for p in path.split(",") if p.strip())
    elif isinstance(path, (list, tuple)):
        parts = tuple(str(p).strip() for p in path if str(p).strip())
    else:
        raise AccountContractError("مسار المطالبة يجب أن يكون نصًا أو قائمة مفاتيح")
    if not parts:
        return None
    if parts[0] in USER_WRITABLE_CLAIM_ROOTS:
        raise AccountContractError(
            f"مسار مطالبة يبدأ من {parts[0]!r} مرفوض — بيانات المستخدم القابلة "
            "للكتابة ليست مصدر دور أو نطاق (خطر تصعيد من المستدعي)"
        )
    return parts


def read_claim(payload: Dict, path: Optional[Tuple[str, ...]]):
    """قراءة مطالبة من حمولة موقعة عبر مسار مفاتيح — أو None إن غابت."""
    if not path:
        return None
    node = payload
    for key in path:
        if not isinstance(node, dict) or key not in node:
            return None
        node = node[key]
    return node
