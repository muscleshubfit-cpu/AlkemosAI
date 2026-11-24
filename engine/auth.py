#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""طبقة المصادقة والهوية — هوية موثقة لا قيم يمررها المستدعي.

(دفعة 16-تتمة — بأمر المالك: «اربط صلاحيات الوصول بهوية موثقة من طبقة
المصادقة، وليس بقيمة role يمررها مستدعي MemoryService»)

التصميم:
- **الهوية تُثبت بتوقيع لا بالادعاء:** رمز الوصول = حمولة كانونية (JSON) +
  توقيع HMAC-SHA256 بمفتاح توقيع المنصة. أي عبث بالحمولة يبطل التوقيع.
- **مفتاحان منفصلان لا يغطي أحدهما الآخر:**
  - مفتاح المنصة (`ALKEMOS_MEMORY_AUTH_KEY`): يسكّ رموز service/admin/client.
  - مفتاح المالك (`ALKEMOS_MEMORY_OWNER_KEY`): يوقّ رموز owner ووثائق اعتماد
    G-EX وحده — حتى لو انكشف مفتاح المنصة لا تُزوَّر هوية المالك (والعكس).
  كلاهما من متغير بيئة أو ملف مفتاح عبر متغير بيئة — **لا مفتاح داخل
  المستودع أبدًا** (SECURITY §1). الاختبارات تولّد مفاتيح عشوائية في الذاكرة.
- **فصل الأدوار بأقل صلاحية (سقف نوع فردي):** كل نوع كيان له سقف صلاحيات
  أقصى يُفرض عند التحقق — رمز يدّعي صلاحية فوق سقف نوعه يُرفض حتى لو كان
  التوقيع سليمًا (لا تصعيد من داخل الحمولة).
- **رموز المالك توقّع بمفتاح المالك (استكمال 16-تتمة):** توقيع رمز owner
  يصدر عن مفتاح المالك المستقل حصرًا — توكن نوع owner موقع بمفتاح المنصة
  يُرفض، وتوكن نوع غير المالك موقع بمفتاح المالك يُرفض (المفتاحان لا
  يتبادلان الأدوار) — حتى لو انكشف مفتاح المنصة لا تُزوَّر هوية المالك.
- **الإنشاء محصور بمسار التحقق (استكمال 16-تتمة):** `Principal` تُنشأ حصرًا
  من `TokenAuthority.verify` — المنشئ محروس بمفتاح إنشاء يعيش داخل إغلاق
  (closure) لا يُصدَّر كخاصية وحدة إطلاقًا، والوراثة ممنوعة، والتعديل بعد
  الإنشاء مرفوض. أي محاولة لبناء هوية مباشرة ببيانات يحددها المستدعي
  (هوية مالك أو صلاحيات موسعة) تفشل.
- **نطاق عملاء إلزامي:** رمز service يصدر لعميل محدد (جلسة) فلا يبلغ ذاكرة
  عميل آخر مهما عرف معرفه؛ رمز client لا يبلغ إلا ذاكرته هو؛ admin يصدر
  بنطاق صريح (عملاء محددون أو كل العملاء للحوكمة)؛ owner على الكل.
- **عمر محدود:** كل رمز يحمل iat/exp — المنتهي يُرفض. أقصى عمر افتراضي 7 أيام.
- هذه الطبقة مستقلة عن النموذج والمزود والاستضافة كقانون المحرك (§1) — لا
  تعرف شيئًا عن أي منصة خارجية؛ ربطها بمصادقة الإنتاج الحقيقي (Supabase
  مثلًا) يتم بمحول خارج هذه الحزمة عند D-17.

الصلاحيات المعرّفة (أقل صلاحية):
- memory:read        — قراءة الحقائق النشطة والحقن (service/client/owner).
- memory:write       — دورة الاستخراج والتخزين (service/owner حصرًا).
- memory:review      — مراجعة كل الحقائق بما فيها الملغاة (admin/owner).
- memory:deactivate  — إلغاء/إعادة تنشيط حقيقة (admin/owner).
- memory:hard_delete — الحذف النهائي (owner وحده).
- consent:record     — توثيق منح موافقة عميل (service بنطاقها · العميل
  لنفسه · owner) — سجل الموافقات لا يقبل حدثًا بلا هوية موثقة تحملها.
- consent:withdraw   — توثيق انسحاب (service بنطاقها · العميل لموافقته ·
  owner لأي أساس بما فيه أساس المالك).
- consent:owner_basis — تسجيل أساس استخدام يقرره المالك (owner وحده —
  وهو توكن موقع بمفتاح المالك المستقل لا بمفتاح المنصة).
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
from pathlib import Path
from typing import Dict, FrozenSet, Optional, Set, Union

from .fsafety import canonical_json

KIND_SERVICE = "service"   # خدمة المنصة — جلسة مقيدة بعميل محدد
KIND_CLIENT = "client"     # العميل نفسه — ذاكرته وحده
KIND_ADMIN = "admin"       # مراجعة حوكمة — نطاق صريح
KIND_OWNER = "owner"       # المالك — تحقق بمفتاح المالك المستقل
KINDS = (KIND_SERVICE, KIND_CLIENT, KIND_ADMIN, KIND_OWNER)

PERM_MEMORY_READ = "memory:read"
PERM_MEMORY_WRITE = "memory:write"
PERM_MEMORY_REVIEW = "memory:review"
PERM_MEMORY_DEACTIVATE = "memory:deactivate"
PERM_MEMORY_HARD_DELETE = "memory:hard_delete"
PERM_CONSENT_RECORD = "consent:record"
PERM_CONSENT_WITHDRAW = "consent:withdraw"
PERM_CONSENT_OWNER_BASIS = "consent:owner_basis"

_KIND_MAX_PERMS: Dict[str, FrozenSet[str]] = {
    KIND_SERVICE: frozenset(
        {PERM_MEMORY_READ, PERM_MEMORY_WRITE,
         PERM_CONSENT_RECORD, PERM_CONSENT_WITHDRAW}
    ),
    KIND_CLIENT: frozenset(
        {PERM_MEMORY_READ, PERM_CONSENT_RECORD, PERM_CONSENT_WITHDRAW}
    ),
    KIND_ADMIN: frozenset({PERM_MEMORY_READ, PERM_MEMORY_REVIEW, PERM_MEMORY_DEACTIVATE}),
    KIND_OWNER: frozenset(
        {PERM_MEMORY_READ, PERM_MEMORY_WRITE, PERM_MEMORY_REVIEW,
         PERM_MEMORY_DEACTIVATE, PERM_MEMORY_HARD_DELETE,
         PERM_CONSENT_RECORD, PERM_CONSENT_WITHDRAW, PERM_CONSENT_OWNER_BASIS}
    ),
}

ISSUER = "alkemos-auth"
MAX_TTL_SECONDS = 7 * 24 * 3600  # أقصى عمر لرمز — ما فوقه يُرفض من السك نفسه
DEFAULT_TTL_SECONDS = 12 * 3600

GEX_APPROVE_SCOPE = "gex_approve"  # نطاق وثيقة اعتماد G-EX الموقعة من المالك


class AuthError(RuntimeError):
    """فشل التحقق من الهوية — لا امتيازات بلا إثبات."""


def _b64e(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64d(text: str) -> bytes:
    pad = "=" * (-len(text) % 4)
    return base64.urlsafe_b64decode(text + pad)


def _define_principal():
    """تعريف Principal ومسار إنشائها داخل إغلاق واحد — لا مصنع هوية عام.

    مفتاح الإنشاء (`_creation_key`) يعيش داخل هذا الإغلاق حصرًا: ليس خاصية
    وحدة ولا صنف ولا قيمة قابلة للاستيراد من خارج. والطريق الوحيد المنشور
    لإنشاء `Principal` هو دالة التحقق المعادة من هنا — وهي تنفذ التحقق
    كاملًا (توقيع/نوع/عمر/سقف صلاحيات/نطاق) قبل الإنشاء، فلا يوجد أي رمز
    يمكنه بناء هوية ببيانات يحددها المستدعي.
    """
    _creation_key = object()  # هوية مقارنة فقط — لا تخرج من الإغلاق

    class Principal:
        """هوية موثقة — تُنشأ حصرًا عبر TokenAuthority.verify بعد فحص التوقيع.

        كائن مجمد عمليًا: لا يُعدل بعد الإنشاء، ولا يُقبل مكان الدور النصي أبدًا
        (MemoryService يرفض أي قيمة ليست Principal موثقة). لا يُورث ولا يُنسخ
        — الوراثة ممنوعة (`__init_subclass__`) والتعديل مرفوض (`__setattr__`).
        """

        __slots__ = ("principal_id", "kind", "clients", "all_clients", "permissions", "expires_at")

        def __init__(
            self,
            principal_id: str,
            kind: str,
            clients: FrozenSet[str],
            all_clients: bool,
            permissions: FrozenSet[str],
            expires_at: int,
            *,
            _creation=None,
        ) -> None:
            if _creation is not _creation_key:
                raise AuthError(
                    "Principal لا تُنشأ مباشرة ببيانات يحددها المستدعي — "
                    "الهوية الموثقة تُنشأ حصرًا عبر TokenAuthority.verify بعد "
                    "تحقق التوقيع (لا إنشاء هوية مالك ولا توسيع صلاحيات بلا رمز صحيح)"
                )
            object.__setattr__(self, "principal_id", principal_id)
            object.__setattr__(self, "kind", kind)
            object.__setattr__(self, "clients", clients)
            object.__setattr__(self, "all_clients", all_clients)
            object.__setattr__(self, "permissions", permissions)
            object.__setattr__(self, "expires_at", expires_at)

        def __init_subclass__(cls, **_kwargs) -> None:
            raise AuthError(
                "لا يُورَّث Principal — الهوية الموثقة تنشأ من مسار التحقق حصرًا "
                "ولا تُستنسخ بصنف بديل"
            )

        def __setattr__(self, *_args) -> None:
            raise AuthError("الهوية الموثقة غير قابلة للتعديل بعد الإنشاء")

        def can(self, permission: str) -> bool:
            return permission in self.permissions

        def can_access_client(self, client_id: str) -> bool:
            """عزل العملاء: النطاق يحسم — معرفة client_id لا تمنح وصولًا بذاتها."""
            if self.all_clients:
                return True
            return client_id in self.clients

        def describe(self) -> str:
            scope = "كل العملاء" if self.all_clients else ",".join(sorted(self.clients))
            return f"{self.kind}:{self.principal_id}({scope})"

        def __repr__(self) -> str:  # pragma: no cover — تشخيص فقط
            return f"Principal({self.describe()})"

    def _verify_and_mint(authority, token, now):
        """التحقق الكامل ثم الإنشاء داخل الإغلاق — جسم TokenAuthority.verify.

        لا يقبل بيانات هوية حرة أبدًا: مدخله رمز موقّع، ولا تنشأ الهوية إلا
        بعد نجاح كل الفحوص (توقيع بمفتاح النوع المطابق + مصدر + عمر + سقف
        صلاحيات + سلامة النطاق).
        """
        if not isinstance(token, str) or token.count(".") != 1:
            raise AuthError("رمز وصول غير صالح")
        body_b64, sig_b64 = token.split(".")
        try:
            body = _b64d(body_b64)
            sig = _b64d(sig_b64)
        except Exception as exc:  # بيانات مشوهة — ليس استثناءً منطقيًا
            raise AuthError("ترميز الرمز غير صالح") from exc
        # التوقيع يُطابق على أحد المفتاحين — والنوع يحسم أيهما الصحيح لاحقًا:
        # owner بمفتاح المالك حصرًا، وما عداه بمفتاح المنصة حصرًا.
        matched = None
        for key, key_name in ((authority._auth_key, "platform"), (authority._owner_key, "owner")):
            expected = hmac.new(key, body, hashlib.sha256).digest()
            if hmac.compare_digest(sig, expected):
                matched = key_name
                break
        if matched is None:
            raise AuthError("توقيع الرمز غير صالح — هوية غير موثقة")

        try:
            payload = json.loads(body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise AuthError("حمولة الرمز غير قابلة للقراءة") from exc

        if payload.get("iss") != ISSUER:
            raise AuthError("مصدر الرمز غير معروف")
        kind = payload.get("kind")
        if kind not in KINDS:
            raise AuthError(f"نوع كيان غير معروف في الرمز: {kind}")
        # المفتاحان لا يتبادلان الأدوار: هوية المالك لا تصنع بتوقيع المنصة،
        # ومفتاح المالك لا يسك صلاحيات الخدمة/العميل/الأدمن.
        if matched == "platform" and kind == KIND_OWNER:
            raise AuthError(
                "رمز مالك يوقّع بمفتاح المالك المستقل حصرًا — توقيع مفتاح المنصة لا يصنع مالكًا"
            )
        if matched == "owner" and kind != KIND_OWNER:
            raise AuthError(
                "مفتاح المالك لرموز المالك وحده — لا يغطي أنواع الكيانات الأخرى"
            )
        current = int(now if now is not None else _unix_now())
        iat, exp = int(payload.get("iat", 0)), int(payload.get("exp", 0))
        if exp <= current:
            raise AuthError("الرمز منتهي الصلاحية — لا وصول برمز ميت")
        if iat > current:
            raise AuthError("رمز صادر في المستقبل — مرفوض")
        if exp - iat > MAX_TTL_SECONDS:
            raise AuthError("عمر الرمز فوق الحد الأقصى — مرفوض")

        perms = frozenset(payload.get("perms", []))
        if not perms <= _KIND_MAX_PERMS[kind]:
            raise AuthError(f"الرمز يدّعي صلاحيات فوق سقف نوعه ({kind}) — مرفوض")

        clients_raw = payload.get("clients", [])
        all_clients = clients_raw == "*"
        clients = frozenset(clients_raw) if not all_clients else frozenset()
        if kind == KIND_SERVICE and (all_clients or not clients):
            raise AuthError("رمز خدمة بلا نطاق عميل محدد — مرفوض")
        if kind == KIND_CLIENT and clients != frozenset({payload.get("sub", "")}):
            raise AuthError("رمز عميل لا يغطي غير ذاكرته — نطاق غير سليم")
        if kind == KIND_ADMIN and not all_clients and not clients:
            raise AuthError("رمز أدمن بلا نطاق صريح — مرفوض")

        return Principal(
            principal_id=str(payload.get("sub", "")),
            kind=kind,
            clients=clients,
            all_clients=all_clients,
            permissions=perms,
            expires_at=exp,
            _creation=_creation_key,
        )

    return Principal, _verify_and_mint


Principal, _verify_and_mint = _define_principal()


def is_verified_principal(value) -> bool:
    """بوابة المستهلكين: هل القيمة هوية موثقة فعلًا؟

    ترفض: النصوص والقواميس والأدوار المزعومة، وأصنافًا بديلة أو موروثة،
    وكائنات أنشئت بـ``__new__`` بلا مرور بالتحقق (صفاتها غير مكتملة).
    الاستهلاك الموثوق يبدأ بهذا الفحص (MemoryService وسجل الموافقات).
    """
    if type(value) is not Principal:
        return False
    try:
        value.describe()          # يمس الصفات الأساسية — غير المكتملة تُرفض
        int(value.expires_at)     # الطابع الزمني مكتمل وقابل للقراءة
    except Exception:
        return False
    return True


class TokenAuthority:
    """سكّ الرموز والتحقق منها — يحمل المفتاحين (منصة + مالك) من خارج المستودع.

    الاستخدام في الإنتاج: from_env() وحدَه (متغيرات بيئة أو ملفات مفاتيح عبر
    متغيرات بيئة — بلا أي قيمة افتراضية داخلية). الاختبارات تولّد مفاتيح
    عشوائية مباشرة (secrets) — لا أسرار في المستودع إطلاقًا.
    """

    def __init__(self, auth_key: bytes, owner_key: bytes) -> None:
        if len(auth_key) < 32 or len(owner_key) < 32:
            raise AuthError("المفاتيح يجب أن تكون ≥32 بايت — مفتاح قصير مرفوض")
        if hmac.compare_digest(auth_key, owner_key):
            raise AuthError("مفتاح المنصة ومفتاح المالك يجب أن يكونا مستقلين — المفتاح الواحد يكسر العزل")
        self._auth_key = auth_key
        self._owner_key = owner_key

    # -- التحميل من البيئة (لا قيمة افتراضية داخلية أبدًا) -------------------
    @staticmethod
    def _load_secret(value: str, name: str) -> bytes:
        value = (value or "").strip()
        if not value:
            raise AuthError(f"متغير البيئة {name} مطلوب — المفاتيح لا تسكن المستودع أبدًا")
        if value.startswith("file:"):
            keyfile = Path(value[5:])
            try:
                data = keyfile.read_bytes().strip()
            except OSError as exc:
                raise AuthError(f"تعذر قراءة ملف المفتاح لـ{name}: {exc}") from exc
            if len(data) < 32:
                raise AuthError(f"ملف مفتاح {name} أقصر من 32 بايت")
            return data
        try:
            data = bytes.fromhex(value)
        except ValueError as exc:
            raise AuthError(f"{name} يجب أن يكون hex أو file:<مسار> — قيمة غير صالحة") from exc
        if len(data) < 32:
            raise AuthError(f"{name} أقصر من 32 بايت (hex)")
        return data

    @classmethod
    def from_env(cls) -> "TokenAuthority":
        auth_key = cls._load_secret(os.environ.get("ALKEMOS_MEMORY_AUTH_KEY", ""), "ALKEMOS_MEMORY_AUTH_KEY")
        owner_key = cls._load_secret(os.environ.get("ALKEMOS_MEMORY_OWNER_KEY", ""), "ALKEMOS_MEMORY_OWNER_KEY")
        return cls(auth_key, owner_key)

    # -- سكّ الرموز ------------------------------------------------------------
    def mint(
        self,
        kind: str,
        principal_id: str,
        clients: Optional[Union[Set[str], FrozenSet[str], str]] = None,
        *,
        all_clients: bool = False,
        ttl_seconds: int = DEFAULT_TTL_SECONDS,
        now: Optional[int] = None,
        permissions: Optional[Union[Set[str], FrozenSet[str]]] = None,
    ) -> str:
        """سكّ رمز هوية — الصلاحيات تُسقف بسقف النوع (لا تصعيد من الحمولة)."""
        if kind not in KINDS:
            raise AuthError(f"نوع كيان غير معروف: {kind}")
        if not (principal_id or "").strip():
            raise AuthError("معرّف الكيان مطلوب")
        if ttl_seconds <= 0 or ttl_seconds > MAX_TTL_SECONDS:
            raise AuthError(f"عمر الرمز يجب أن يكون بين ثانية واحدة و{MAX_TTL_SECONDS} ثانية")

        if kind == KIND_CLIENT:
            # العميل لا يصدر إلا لنطاقه هو — لا يوقّع لعميل آخر أبدًا.
            clients = {principal_id}
            all_clients = False
        elif kind == KIND_OWNER:
            all_clients = True
            clients = None
        elif kind == KIND_SERVICE:
            if all_clients or not clients:
                raise AuthError(
                    "رمز الخدمة يصدر لعميل محدد (جلسة) — نطاق كل العملاء ممنوع لمبدأ أقل صلاحية"
                )
        elif kind == KIND_ADMIN:
            if not all_clients and not clients:
                raise AuthError("رمز الأدمن يصدر بنطاق صريح: عملاء محددون أو كل العملاء للحوكمة")

        max_perms = _KIND_MAX_PERMS[kind]
        perms = frozenset(permissions) if permissions is not None else max_perms
        if not perms <= max_perms:
            raise AuthError(
                f"صلاحيات فوق سقف النوع {kind}: المسموح {sorted(max_perms)} — لا تصعيد من الحمولة"
            )

        payload = {
            "iss": ISSUER,
            "sub": principal_id,
            "kind": kind,
            "clients": "*" if all_clients else sorted(set(clients or set())),
            "perms": sorted(perms),
            "iat": int(now if now is not None else _unix_now()),
            "exp": int(now if now is not None else _unix_now()) + int(ttl_seconds),
            "jti": secrets.token_hex(8),
        }
        body = canonical_json(payload).encode("utf-8")
        # رموز المالك توقّع بمفتاح المالك المستقل حصرًا — لا بمفتاح المنصة:
        # انكشاف مفتاح المنصة لا يسمح بسك هوية مالك (والعكس).
        signing_key = self._owner_key if kind == KIND_OWNER else self._auth_key
        sig = hmac.new(signing_key, body, hashlib.sha256).digest()
        return _b64e(body) + "." + _b64e(sig)

    # -- التحقق ---------------------------------------------------------------
    def verify(self, token: str, *, now: Optional[int] = None) -> Principal:
        """تحقق كامل: توقيع (بالمفتاح المطابق لنوع الكيان) + مصدر + عمر + سقف صلاحيات + سليمة النطاق.

        التنفيذ الداخلي مغلق داخل وحدة تعريف الهوية (`_define_principal`)
        بحيث لا يوجد مسار منشور ينشئ `Principal` ببيانات حرة — الإنشاء يتم
        حصرًا داخل الإغلاق بعد نجاح كل الفحوص.
        """
        return _verify_and_mint(self, token, now)

    # -- توقيع المالك لوثائق G-EX (مفتاح مستقل عن مفتاح المنصة) ---------------
    def owner_sign(self, document: Dict) -> str:
        """توقيع وثيقة بمفتاح المالك — لأداة المالك فقط، لا للمسار الخدمي."""
        return self.owner_verifier().sign(document)

    def owner_verify(self, document: Dict, signature: str) -> bool:
        return self.owner_verifier().verify(document, signature)

    def owner_verifier(self) -> "OwnerVerifier":
        """كائن تحقق فقط (لا يوقّع) — ما يُمرر للبوابة: أقل صلاحية للمكونات."""
        return OwnerVerifier(self._owner_key)


class OwnerVerifier:
    """تحقق من توقيع المالك حصرًا — لا يحمل أي قدرة سكّ أو توقيع.

    البوابة تستلم هذا الكائن فلا يمكنها — حتى لو خُترقت — توليد توقيع مالك
    جديد؛ التوقيع يصدر من أداة المالك خارج مسار الخدمة.
    """

    def __init__(self, owner_key: bytes) -> None:
        if len(owner_key) < 32:
            raise AuthError("مفتاح المالك يجب أن يكون ≥32 بايت")
        self._owner_key = owner_key

    def sign(self, document: Dict) -> str:
        body = canonical_json(document).encode("utf-8")
        return _b64e(hmac.new(self._owner_key, body, hashlib.sha256).digest())

    def verify(self, document: Dict, signature: str) -> bool:
        if not isinstance(signature, str) or not signature:
            return False
        try:
            sig = _b64d(signature)
        except Exception:
            return False
        body = canonical_json(document).encode("utf-8")
        expected = hmac.new(self._owner_key, body, hashlib.sha256).digest()
        return hmac.compare_digest(sig, expected)


def gex_approval_document(
    decision_ref: str, signed_at: str, content_sha256: str, origin_sha256: str
) -> Dict:
    """وثيقة اعتماد كانونية — البصمات تمنع إعادة استخدام التوقيع لمثال آخر."""
    return {
        "scope": GEX_APPROVE_SCOPE,
        "decision_ref": decision_ref,
        "signed_at": signed_at,
        "content_sha256": content_sha256,
        "origin_sha256": origin_sha256,
    }


def _unix_now() -> int:
    import time
    return int(time.time())
