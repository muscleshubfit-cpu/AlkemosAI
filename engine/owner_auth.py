#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""مصادقة المالك: بريد + كلمة مرور + رمز تحقق عبر البريد + استعادة الوصول.

(دفعة 16 — أمر المالك: اعتماد هوية المالك الأساسية الوحيدة في إعدادات
المحرك، وتجهيز آلية مصادقة آمنة للمالك بالبريد وكلمة المرور مع رمز تحقق
إضافي عبر البريد، وتصميم صلاحيات المالك واستعادة الوصول وإدارة بيانات
المصادقة — كلها قابلة للربط بواجهة مستقبلية، **دون أي واجهة مستخدم الآن**.)

التصميم (كل الأرقام هنا سياسات وحدة قابلة للحقن في الاختبارات):
- **هوية واحدة من الإعدادات:** حساب المالك واحد لا غير — بريد المالك الأساسي
  من `engine.settings.OWNER_EMAIL_PRIMARY`. إنشاء حساب أو دخول أو استعادة
  لغيره مرفوض جذريًا (لا تعدد مالكين ولا بريد بديل).
- **كلمة المرور لا تُخزن أبدًا:** scrypt (صعب الذاكرة) بملح عشوائي 16 بايت؛
  يُخزن {alg, salt, n, r, p, dklen, hash} فقط — والتحقق بمقارنة زمن-ثابت
  بمعاملات السجل نفسها (ترقية المعاملات مستقبلًا لا تكسر سجلات قديمة).
- **رمز تحقق عبر البريد (خطوة ثانية):** 6 أرقام · عمر 10 دقائق · أحادي
  الاستخدام · يُخزن بصمته (sha256+ملح) لا نصه · حد 5 محاولات ثم يُبطل
  ويُطلب رمز جديد. **المحرك لا يرسل بريدًا** (قانون الاستقلالية §1 — لا
  مزود خارجي): الرمز يُسلّم للمضيف مرة واحدة (في القيمة المرجعة أو عبر
  `email_sender` يُحقن عند البناء) ليوصله المضيف عبر قناته — قناة التسليم
  مسؤولية المضيف لا المحرك (موثق في نموذج التهديد).
- **قفل تدريجي بعد الفشل:** 5 محاولات فاشلة (كلمة مرور أو رمز استعادة)
  تقفل الحساب مؤقتًا 300 ثانية تتضاعف بكل قفل متتالٍ حتى سقف 3600 ثانية —
  والعدادات تعيش المخزن فتبقى عبر إعادة التشغيل، وتصفَّر بالنجاح.
- **أخطاء موحدة (anti-enumeration):** البريد غير المعروف وكلمة المرور
  الخاطئة والرمز الخاطئ ترفض برسالة واحدة لا تميّز بينها.
- **استعادة الوصول:** بريد + أحد رموز الاستعادة (8 رموز تُولد مرة عند
  الإعداد/التدوير/بعد الاستعادة، تُخزن بصماتها، أحادية الاستخدام) + كلمة
  المرور الجديدة — في معاملة واحدة تحت القفل: الرمز يُستهلك، وتُستبدل
  كلمة المرور، وتُولد رموز استعادة جديدة (تُعرض مرة واحدة)، ويصفَّر القفل.
- **الصلاحيات الحساسة تقتضي إثبات كريبتوغرافيًا:** تغيير كلمة المرور وتدوير
  رموز الاستعادة تتطلب هوية مالك موثقة تثبت بـ`TokenAuthority.attest`
  (الشهادة الكريبتوغرافية — تزييف كائن بنيويًا بلا مفتاح لا يكفي: الإغلاق
  حارس صحة لا حد أمني) **و** هوية البريد الأساسي نفسه — لا تصعيد من
  هوية خدمة/أدمن/عميل ولا من رمز مالك بمعرّف غير البريد الأساسي.
- **الهوية الناتجة:** `TokenAuthority` يسكّ رمز owner موقعًا **بمفتاح
  المالك المستقل** حصرًا، `sub` = البريد الأساسي — والرمز يعبر `verify`
  كأي هوية مالك شرعية (صلاحيات النوع كاملة).
- **بيانات المصادقة = بيانات المستوى أ:** المخزن خارج شجرة git نهائيًا
  (حارس fsafety) · كتابة ذرية تحت قفل flock · سجل تدقيق إلحاقي لكل حدث
  (نجاح/فشل/قفل/رمز/استعادة — بلا أي نص سر قط).
- **الربط بواجهة مستقبلية:** كل الدوال ترجع قواميس JSON-قابلة-للتمثيل
  (status/account/code_required/...) — الواجهة القادمة تستهلك هذه العقد
  كما هي؛ `status()` قناع آمن (لا بصمات ولا نصوص سرية أبدًا).
- **لا واجهة مستخدم هنا:** هذه طبقة خدمة للمضيف فقط — بلا صفحات ولا
  مسارات HTTP ولا قوالب — وأي ربط مستقبلي يتم بمحول خارج المحرك.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import secrets
import time
from pathlib import Path
from typing import Callable, Dict, List, Optional

from . import settings
from .auth import (
    KIND_OWNER,
    TokenAuthority,
    is_verified_principal,
)
from .fsafety import (
    FileLock,
    assert_outside_git_tree,
    atomic_append_line,
    atomic_write_text,
    utc_now_iso,
)

# ── السياسات (أرقام الوحدة) ────────────────────────────────────────────────
PASSWORD_MIN_LEN = 12          # حد أدنى لكلمة مرور المالك
PASSWORD_MAX_LEN = 1024        # سقف عقلاني لحجم الإدخال (لا هجمات حجم)
SCRYPT_N = 2 ** 15             # معامل صعوبة الذاكرة (32MB) — قابلة للحقن بالاختبارات
SCRYPT_R = 8
SCRYPT_P = 1
SCRYPT_DKLEN = 64
CODE_DIGITS = 6                # رمز تحقق البريد: 6 أرقام
CODE_TTL_SECONDS = 600         # عمر الرمز: 10 دقائق
CODE_MAX_ATTEMPTS = 5          # محاولات خاطئة قبل إبطال الرمز
LOGIN_MAX_FAILURES = 5         # محاولات فاشلة قبل القفل
LOCKOUT_BASE_SECONDS = 300     # 5 دقائق، تتضاعف حتى السقف
LOCKOUT_MAX_SECONDS = 3600     # ساعة واحدة
RECOVERY_CODES_COUNT = 8       # رموز الاستعادة
RECOVERY_CODE_BYTES = 10       # 20 حرفًا سداسيًا عشوائيًا

STATE_SCHEMA = "alkemos.owner-auth/1"
STATE_FILE = "owner-account.json"
LOCK_FILE = "owner-auth.lock"
EVENTS_FILE = "owner-auth-events.jsonl"


class OwnerAuthError(RuntimeError):
    """رفض مصادقة المالك — رسالة موحدة لا تميّز الحساب أو السبب (anti-enumeration)."""


class OwnerAuthDataError(RuntimeError):
    """خلل في بيانات المصادقة المخزنة — صوت عالٍ لا إعادة تعيين صامتة."""


_MSG_CREDENTIALS = "بيانات اعتماد غير صالحة"


# ── دوال kdf / بصمات (نقية، قابلة للاختبار وحدها) ─────────────────────────
def hash_password(password: str, *, n: int = SCRYPT_N, r: int = SCRYPT_R,
                  p: int = SCRYPT_P, dklen: int = SCRYPT_DKLEN,
                  salt: Optional[bytes] = None) -> Dict:
    """بصمة كلمة المرور: scrypt بملح عشوائي — يعيد سجل المعاملات والبصمة."""
    salt = salt if salt is not None else secrets.token_bytes(16)
    if len(salt) < 16:
        raise OwnerAuthError("ملح كلمة المرور يجب أن يكون ≥16 بايت")
    digest = hashlib.scrypt(
        password.encode("utf-8"), salt=salt, n=n, r=r, p=p, dklen=dklen
    )
    return {
        "alg": "scrypt",
        "salt": salt.hex(),
        "n": int(n), "r": int(r), "p": int(p), "dklen": int(dklen),
        "hash": digest.hex(),
    }


def verify_password(password: str, record: Dict) -> bool:
    """تحقق زمن-ثابت من كلمة المرور بمعاملات السجل نفسها."""
    try:
        salt = bytes.fromhex(record["salt"])
        expected = bytes.fromhex(record["hash"])
        digest = hashlib.scrypt(
            password.encode("utf-8"), salt=salt,
            n=int(record["n"]), r=int(record["r"]), p=int(record["p"]),
            dklen=int(record.get("dklen", 64)),
        )
        return hmac.compare_digest(digest, expected)
    except (KeyError, ValueError, TypeError):
        return False


def _check_password_policy(password: str) -> None:
    if not isinstance(password, str) or len(password) < PASSWORD_MIN_LEN:
        raise OwnerAuthError(f"كلمة المرور يجب أن تكون {PASSWORD_MIN_LEN} حرفًا على الأقل")
    if len(password) > PASSWORD_MAX_LEN:
        raise OwnerAuthError("كلمة المرور أطول من الحد المسموح")
    local = settings.normalize_owner_email(settings.OWNER_EMAIL_PRIMARY).split("@")[0]
    if password.strip().lower() == local or settings.normalize_owner_email(
        settings.OWNER_EMAIL_PRIMARY
    ) in password.lower():
        raise OwnerAuthError("كلمة المرور لا تحتوي البريد أو جزئه المحلي")


def _code_hash(code: str, salt: str) -> str:
    return hashlib.sha256(f"{salt}:{code}".encode("utf-8")).hexdigest()


def _recovery_hash(code: str) -> str:
    return hashlib.sha256(f"recovery:{code}".encode("utf-8")).hexdigest()


def _gen_code() -> str:
    return f"{secrets.randbelow(10 ** CODE_DIGITS):0{CODE_DIGITS}d}"


def _gen_recovery_codes(count: int = RECOVERY_CODES_COUNT) -> List[str]:
    return [secrets.token_hex(RECOVERY_CODE_BYTES) for _ in range(count)]


# ── المخزن ─────────────────────────────────────────────────────────────────
class OwnerAuthStore:
    """مخزن بيانات مصادقة المالك — خارج شجرة git، ذرّي، مقفل، مُدقَّق.

    ملفان فقط:
    - `owner-account.json`: حالة الحساب (بصمة كلمة المرور · رمز البريد
      المعلق بصمته · رموز الاستعادة بصماتها · عدادات الفشل والقفل) —
      كتابة ذرية دائمًا وتكامل ذاتي (بصمة المحتوى تكشف الفساد الصامت).
    - `owner-auth-events.jsonl`: سجل تدقيق إلحاقي لكل حدث.
    وقراءة/تعديل/كتابة الحالة كلها تحت قفل flock حصري.
    """

    def __init__(self, root) -> None:
        root_path = Path(root)
        if not root_path.is_absolute():
            raise OwnerAuthDataError("مسار بيانات مصادقة المالك يجب أن يكون مطلقًا")
        assert_outside_git_tree(root_path)   # بيانات المستوى أ: خارج المستودع نهائيًا
        root_path.mkdir(parents=True, exist_ok=True)
        self.root = root_path
        self.state_path = root_path / STATE_FILE
        self.lock_path = root_path / LOCK_FILE
        self.events_path = root_path / EVENTS_FILE

    # -- القراءة -------------------------------------------------------------
    def load_state(self) -> Optional[Dict]:
        """قراءة الحالة — بلا حساب يعيد None؛ التالف يُعلن بصوت عالٍ."""
        if not self.state_path.exists():
            return None
        raw = self.state_path.read_text(encoding="utf-8")
        try:
            state = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise OwnerAuthDataError(
                "ملف حساب المالك تالف (JSON غير قابل للقراءة) — لا إعادة تعيين "
                "صامتة: القرار بيد المالك من نسخة الاستعادة"
            ) from exc
        if state.get("schema") != STATE_SCHEMA:
            raise OwnerAuthDataError(
                f"مخطط بيانات المصادقة غير معروف: {state.get('schema')!r}"
            )
        if state.get("email") != settings.OWNER_EMAIL_PRIMARY:
            raise OwnerAuthDataError(
                "بريد الحساب المخزن لا يطابق هوية المالك الأساسية في إعدادات "
                "المحرك — مصالحة الإعدادات/الحساب قرار مالك موثق لا صمت"
            )
        if state.get("integrity") != _state_integrity(state):
            raise OwnerAuthDataError(
                "بصمة تكامل حالة الحساب لا تطابق المحتوى — تلف أو عبث: لا "
                "استمرار ببيانات غير موثوقة"
            )
        return state

    # -- الكتابة (ذرية تحت القفل) ---------------------------------------------
    def save_state(self, state: Dict) -> None:
        state = dict(state)
        state.pop("integrity", None)
        state["integrity"] = _state_integrity(state)
        atomic_write_text(
            self.state_path, json.dumps(state, ensure_ascii=False, indent=2)
        )

    # -- سجل التدقيق -----------------------------------------------------------
    def append_event(self, event: str, detail: Optional[Dict] = None) -> None:
        row = {"ts": utc_now_iso(), "event": event, "detail": detail or {}}
        atomic_append_line(self.events_path, json.dumps(row, ensure_ascii=False))

    def read_events(self) -> List[Dict]:
        if not self.events_path.exists():
            return []
        rows: List[Dict] = []
        for line in self.events_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            rows.append(json.loads(line))   # سجلنا نكتبه نحن سطرًا سطرًا
        return rows


def _state_integrity(state: Dict) -> str:
    """بصمة تكامل ذاتية للمحتوى دون حقل التكامل — تكشف الفساد/العبث الصامت."""
    body = dict(state)
    body.pop("integrity", None)
    body.pop("updated_at", None)
    canonical = json.dumps(body, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


# ── الخدمة ─────────────────────────────────────────────────────────────────
class OwnerAuthService:
    """خدمة مصادقة المالك — عقد جاهز للربط بمحول واجهة مستقبلية، بلا واجهة الآن.

    الاستعمال (المضيف): أنشئ السلطة من المفاتيح خارج المستودع، والمخزن في
    دليل بيانات خارج المستودع، وهذه الخدمة فوقهما. كل عمليات الحساب الحساسة
    (تغيير كلمة المرور/تدوير رموز الاستعادة) تقتضي `Principal` مالكًا
    يثبت كريبتوغرافيًا (`attest`) ويحمل بريد المالك الأساسي نفسه.
    """

    def __init__(
        self,
        authority: TokenAuthority,
        store: OwnerAuthStore,
        *,
        require_email_code: bool = True,
        email_sender: Optional[Callable[[str, str, str], None]] = None,
        kdf: Optional[Dict] = None,
        token_ttl_seconds: Optional[int] = None,
    ) -> None:
        if not isinstance(authority, TokenAuthority):
            raise OwnerAuthError("السلطة (TokenAuthority) مطلوبة — لا مصادقة بلا مفاتيح")
        self._authority = authority
        self._store = store
        self._require_code = bool(require_email_code)
        self._email_sender = email_sender
        self._kdf = dict(kdf or {})
        self._token_ttl = int(token_ttl_seconds) if token_ttl_seconds else None

    # -- أدوات داخلية -----------------------------------------------------------
    def _now(self, now: Optional[int]) -> int:
        return int(now if now is not None else time.time())

    def _hash_pw(self, password: str) -> Dict:
        kwargs = dict(self._kdf)
        kwargs.setdefault("salt", None)
        return hash_password(password, **kwargs)

    def _account_or_raise(self, state: Optional[Dict]) -> Dict:
        if state is None:
            raise OwnerAuthError(_MSG_CREDENTIALS)
        return state

    def _email_or_primary(self, email: str) -> str:
        if not settings.is_primary_owner_email(email or ""):
            # رسالة موحدة لا تكشف هل البريد خطأ أم الحساب غير موجود
            raise OwnerAuthError(_MSG_CREDENTIALS)
        return settings.normalize_owner_email(email)

    def _check_lockout(self, state: Dict, now: int) -> None:
        login_state = state.get("login_state") or {}
        until = login_state.get("locked_until")
        if until is not None and int(until) > now:
            raise OwnerAuthError(
                f"الحساب مقفل مؤقتًا بعد محاولات فاشلة — أعد المحاولة بعد {int(until) - now} ثانية"
            )

    def _register_failure(self, state: Dict, event: str, detail: Dict, now: int) -> Dict:
        """تسجيل فشل: عدّاد يتصاعد وقفل مضاعف عند السقف."""
        ls = state.get("login_state") or {}
        failed = int(ls.get("failed", 0)) + 1
        level = int(ls.get("lockout_level", 0))
        if failed >= LOGIN_MAX_FAILURES:
            until = now + min(LOCKOUT_BASE_SECONDS * (2 ** level), LOCKOUT_MAX_SECONDS)
            ls.update({"failed": 0, "lockout_level": level + 1, "locked_until": until})
            self._store.append_event("locked_out", {"until_unix": until, **detail})
        else:
            ls.update({"failed": failed, "locked_until": None})
        state["login_state"] = ls
        self._store.save_state(state)
        self._store.append_event(event, detail)
        return state

    def _register_success(self, state: Dict, event: str, detail: Dict) -> Dict:
        ls = state.get("login_state") or {}
        ls.update({"failed": 0, "lockout_level": 0, "locked_until": None})
        state["login_state"] = ls
        self._store.save_state(state)
        self._store.append_event(event, detail)
        return state

    def _mint_owner_identity(self, now: Optional[int] = None) -> Dict:
        """سكّ هوية المالك: رمز owner بمفتاح المالك المستقل، sub = البريد الأساسي."""
        token = self._authority.mint(
            KIND_OWNER, settings.OWNER_EMAIL_PRIMARY,
            ttl_seconds=self._token_ttl or 12 * 3600, now=now,
        )
        principal = self._authority.verify(token, now=now)
        return {
            "status": "authenticated",
            "principal": principal,          # للتمرير إلى MemoryService ونحوه
            "principal_desc": principal.describe(),
            "token": token,                  # للواجهة/المضيف (تخزينه مسؤوليتهما)
            "token_kind": KIND_OWNER,
            "subject": settings.OWNER_EMAIL_PRIMARY,
            "expires_at": principal.expires_at,
        }

    def _require_owner_action(self, principal) -> None:
        """بوابة العمليات الحساسة: إثبات كريبتوغرافي + نوع مالك + البريد الأساسي.

        هذا هو تطبيق «معالجة تزوير Principal وفق نموذج تهديد واقعي»:
        الفحص البنيوي وحده لا يكفي (الإغلاق حارس صحة لا حد أمني) — الشهادة
        الكريبتوغرافية (`attest`) هي التي تحسم: كائن بُني بلا مفتاح يُرفض
        حتى لو عبر كل الفحوص البنيوية.
        """
        if not is_verified_principal(principal):
            raise OwnerAuthError("العملية تقتضي هوية مالك موثقة (Principal)")
        if not self._authority.attest(principal):
            raise OwnerAuthError(
                "هوية المالك لا تثبت كريبتوغرافيًا — الشهادة لا تطابق المفتاح "
                "(تزييف بنيوي لا يمنح صلاحيات الحساب)"
            )
        if principal.kind != KIND_OWNER:
            raise OwnerAuthError("العملية للمالك حصرًا — لا تصعيد من هوية أخرى")
        if principal.principal_id != settings.OWNER_EMAIL_PRIMARY:
            raise OwnerAuthError(
                "هوية مالك بمعرّف غير البريد الأساسي لا تحكم هذا الحساب"
            )
        if principal.expires_at <= self._now(None):
            raise OwnerAuthError("انتهت صلاحية هوية المالك — أعد الدخول")

    # -- الإعداد الأول ------------------------------------------------------------
    def bootstrap_owner(self, password: str, *, now: Optional[int] = None) -> Dict:
        """إنشاء حساب المالك الوحيد — لا يعمل إلا مرة (لا حساب بديل بعده).

        يعيد رموز الاستعادة **مرة واحدة** — المضيف يعرضها/يخزنها للمالك
        بأمان (مدير كلمات مرور)؛ بعدها لا تُستخرج أبدًا (تُخزن بصماتها).
        """
        _check_password_policy(password)
        cur = int(now if now is not None else time.time())
        with FileLock(self._store.lock_path):
            state = self._store.load_state()
            if state is not None:
                raise OwnerAuthError(
                    "حساب المالك موجود أصلًا — لا إنشاء ثانٍ (التغيير عبر "
                    "تغيير كلمة المرور أو الاستعادة فقط)"
                )
            codes = _gen_recovery_codes()
            state = {
                "schema": STATE_SCHEMA,
                "email": settings.OWNER_EMAIL_PRIMARY,
                "password": self._hash_pw(password),
                "created_at": utc_now_iso(),
                "updated_at": utc_now_iso(),
                "login_state": {"failed": 0, "lockout_level": 0, "locked_until": None},
                "pending_code": None,
                "recovery_codes": [
                    {"sha256": _recovery_hash(c), "created_at": utc_now_iso(), "used_at": None}
                    for c in codes
                ],
            }
            self._store.save_state(state)
            self._store.append_event("account_bootstrapped", {"email": settings.OWNER_EMAIL_PRIMARY})
            return {
                "status": "bootstrapped",
                "email": settings.OWNER_EMAIL_PRIMARY,
                "recovery_codes": codes,   # تُعرض مرة واحدة فقط
            }

    # -- الدخول (كلمة المرور ثم رمز البريد) -----------------------------------------
    def begin_login(self, email: str, password: str, *, now: Optional[int] = None) -> Dict:
        """الخطوة الأولى: البريد + كلمة المرور.

        - كلمة المرور صحيحة ورمز البريد غير مطلوب → هوية كاملة فورًا.
        - كلمة المرور صحيحة ورمز البريد مطلوب (الافتراضي) → يُصدر رمز تحقق
          جديد (يبطل أي رمز معلق سابق) ويعيد {status: code_required} مع
          الرمز مرة واحدة (أو يسلّمه email_sender المُحقن إن وُجد — فلا يعود
          في القيمة المرجعة إطلاقًا).
        - أي فشل: رسالة موحدة + عدّاد يتصاعد + قفل تدريجي عند السقف.
        """
        email_norm = self._email_or_primary(email)
        cur = self._now(now)
        with FileLock(self._store.lock_path):
            state = self._store.load_state()
            state = self._account_or_raise(state)
            self._check_lockout(state, cur)
            if not verify_password(password, state.get("password") or {}):
                self._register_failure(state, "login_failed", {"email": email_norm}, cur)
                raise OwnerAuthError(_MSG_CREDENTIALS)
            # كلمة المرور صحيحة — صفّر عدادات الفشل
            ls = state.get("login_state") or {}
            ls.update({"failed": 0, "lockout_level": 0, "locked_until": None})
            state["login_state"] = ls
            if not self._require_code:
                self._store.save_state(state)
                self._store.append_event("login_ok", {"email": email_norm, "step": "password"})
                return self._mint_owner_identity(now=now)
            # أصدر رمز تحقق جديد (ملح وبصمة جديدان — لا علاقة برمز سابق)
            code = _gen_code()
            salt = secrets.token_hex(16)
            state["pending_code"] = {
                "salt": salt,
                "hash": _code_hash(code, salt),
                "issued_at_unix": cur,
                "expires_at_unix": cur + CODE_TTL_SECONDS,
                "attempts": 0,
            }
            state["updated_at"] = utc_now_iso()
            self._store.save_state(state)
            self._store.append_event(
                "email_code_issued", {"email": email_norm, "expires_in": CODE_TTL_SECONDS}
            )
            result = {
                "status": "code_required",
                "email": email_norm,
                "expires_in": CODE_TTL_SECONDS,
            }
            if self._email_sender is not None:
                self._email_sender(settings.OWNER_EMAIL_PRIMARY, "رمز تحقق دخول المالك", code)
            else:
                result["delivery_code"] = code  # للمضيف يوصله عبر بريده — مرة واحدة
            return result

    def complete_login(self, email: str, code: str, *, now: Optional[int] = None) -> Dict:
        """الخطوة الثانية: رمز التحقق المُوصى عبر البريد — أحادي الاستخدام."""
        email_norm = self._email_or_primary(email)
        cur = self._now(now)
        with FileLock(self._store.lock_path):
            state = self._store.load_state()
            state = self._account_or_raise(state)
            self._check_lockout(state, cur)
            pending = state.get("pending_code")
            if not pending:
                self._store.append_event("login_failed", {"email": email_norm, "reason": "no_pending_code"})
                raise OwnerAuthError(_MSG_CREDENTIALS)
            if int(pending.get("expires_at_unix", 0)) <= cur:
                state["pending_code"] = None
                state["updated_at"] = utc_now_iso()
                self._store.save_state(state)
                self._store.append_event("email_code_expired", {"email": email_norm})
                raise OwnerAuthError("انتهت صلاحية رمز التحقق — اطلب رمزًا جديدًا")
            if not hmac.compare_digest(
                _code_hash(str(code or ""), str(pending.get("salt", ""))),
                str(pending.get("hash", "")),
            ):
                pending["attempts"] = int(pending.get("attempts", 0)) + 1
                detail = {"email": email_norm}
                if pending["attempts"] >= CODE_MAX_ATTEMPTS:
                    state["pending_code"] = None
                    state["updated_at"] = utc_now_iso()
                    self._store.save_state(state)
                    self._store.append_event("email_code_invalidated", detail)
                    raise OwnerAuthError("استُنفدت محاولات الرمز — اطلب رمزًا جديدًا")
                state["pending_code"] = pending
                self._store.save_state(state)
                self._store.append_event("email_code_failed", detail)
                raise OwnerAuthError(_MSG_CREDENTIALS)
            # الرمز صحيح — استهلاكه أحاديًا وتسجيل الدخول
            state["pending_code"] = None
            state["updated_at"] = utc_now_iso()
            self._register_success(state, "login_ok", {"email": email_norm, "step": "password+email_code"})
            return self._mint_owner_identity(now=now)

    # -- عمليات الحساب الحساسة (تقتضي هوية مثبتة كريبتوغرافيًا) -----------------------
    def change_password(self, principal, current_password: str, new_password: str,
                        *, now: Optional[int] = None) -> Dict:
        """تغيير كلمة المرور — بهوية مالك مثبتة (attest) وكلمة المرور الحالية."""
        self._require_owner_action(principal)
        _check_password_policy(new_password)
        cur = self._now(now)
        with FileLock(self._store.lock_path):
            state = self._store.load_state()
            state = self._account_or_raise(state)
            self._check_lockout(state, cur)
            if not verify_password(current_password, state.get("password") or {}):
                self._register_failure(
                    state, "password_change_failed", {"email": settings.OWNER_EMAIL_PRIMARY}, cur
                )
                raise OwnerAuthError(_MSG_CREDENTIALS)
            state["password"] = self._hash_pw(new_password)
            state["pending_code"] = None     # أي رمز معلق يبطل
            state["updated_at"] = utc_now_iso()
            self._store.save_state(state)
            self._store.append_event("password_changed", {"email": settings.OWNER_EMAIL_PRIMARY})
            return {"status": "password_changed", "email": settings.OWNER_EMAIL_PRIMARY}

    def rotate_recovery_codes(self, principal) -> Dict:
        """تدوير رموز الاستعادة — بهوية مالك مثبتة؛ القديمة تبطل جميعًا."""
        self._require_owner_action(principal)
        with FileLock(self._store.lock_path):
            state = self._store.load_state()
            state = self._account_or_raise(state)
            codes = _gen_recovery_codes()
            state["recovery_codes"] = [
                {"sha256": _recovery_hash(c), "created_at": utc_now_iso(), "used_at": None}
                for c in codes
            ]
            state["updated_at"] = utc_now_iso()
            self._store.save_state(state)
            self._store.append_event("recovery_codes_rotated", {"email": settings.OWNER_EMAIL_PRIMARY})
            return {"status": "recovery_codes_rotated", "recovery_codes": codes}

    # -- استعادة الوصول (كلمة المرور مفقودة) ------------------------------------------
    def recover_access(self, email: str, recovery_code: str, new_password: str,
                       *, now: Optional[int] = None) -> Dict:
        """استعادة الوصول: بريد + رمز استعادة + كلمة مرور جديدة — معاملة واحدة.

        يستهلك الرمز (أحادي الاستخدام)، يستبدل كلمة المرور، **يولّد رموز
        استعادة جديدة** (القديمة كلها تبطل — تُعرض مرة واحدة في النتيجة)،
        ويصفر القفل والعدادات. كل فشل يسجل في التدقيق ويغذي عداد القفل
        (استنزاف رموز الاستادة بالتجربة يُقفل الحساب كمحاولات الدخول).
        """
        _check_password_policy(new_password)
        email_norm = self._email_or_primary(email)
        cur = self._now(now)
        with FileLock(self._store.lock_path):
            state = self._store.load_state()
            state = self._account_or_raise(state)
            self._check_lockout(state, cur)
            code_norm = (recovery_code or "").strip().lower()
            match = None
            for rec in state.get("recovery_codes") or []:
                if rec.get("used_at") is None and hmac.compare_digest(
                    _recovery_hash(code_norm), str(rec.get("sha256", ""))
                ):
                    match = rec
                    break
            if match is None:
                self._register_failure(
                    state, "recovery_failed", {"email": email_norm}, cur
                )
                raise OwnerAuthError(_MSG_CREDENTIALS)
            match["used_at"] = utc_now_iso()
            codes = _gen_recovery_codes()
            state["recovery_codes"] = [
                {"sha256": _recovery_hash(c), "created_at": utc_now_iso(), "used_at": None}
                for c in codes
            ]
            state["password"] = self._hash_pw(new_password)
            state["pending_code"] = None
            state["updated_at"] = utc_now_iso()
            self._register_success(state, "recovery_completed", {"email": email_norm})
            return {
                "status": "access_recovered",
                "email": email_norm,
                "recovery_codes": codes,   # المجموعة الجديدة — مرة واحدة
            }

    # -- الحالة والتدقيق (قناع آمن للواجهة المستقبلية) ---------------------------------
    def status(self) -> Dict:
        """حالة الحساب للعرض — قناع آمن: لا بصمات ولا نصوص سرية أبدًا."""
        state = self._store.load_state()
        if state is None:
            return {"account_exists": False, "primary_email": settings.OWNER_EMAIL_PRIMARY}
        ls = state.get("login_state") or {}
        return {
            "account_exists": True,
            "primary_email": settings.OWNER_EMAIL_PRIMARY,
            "created_at": state.get("created_at"),
            "updated_at": state.get("updated_at"),
            "locked": ls.get("locked_until") is not None
                      and int(ls.get("locked_until", 0)) > self._now(None),
            "locked_until": ls.get("locked_until"),
            "pending_code": bool(state.get("pending_code")),
            "recovery_codes_remaining": sum(
                1 for r in state.get("recovery_codes") or [] if r.get("used_at") is None
            ),
        }

    def audit_events(self) -> List[Dict]:
        """سجل التدقيق كاملًا (إلحاقي — لا حذف ولا تعديل)."""
        return self._store.read_events()
