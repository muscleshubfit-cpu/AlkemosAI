#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""فهرس حسابات المحرك — بيانات الهوية منفصلة عن بيانات النموذج (دفعة 17).

القانون (أمر المالك): «فصل بيانات الهوية عن بيانات النموذج: لكل مستخدم
داخل AlkemosAI سجل مستقل (محادثات، ذاكرة، تفضيلات، استخدام) مرتبط بمعرف
الحساب الموحد». هذا الفهرس هو **سجل الهوية** لكل حساب:

- `first_seen/last_seen` — أول وآخر ظهور للحساب في المحرك.
- `roles_seen` — الأدوار المشاهدة من مصدر الهوية (رصد التغيير).
- `sessions_count` — عداد الجلسات (استخدام المحرك لكل حساب).
- `preferences` — تفضيلات الحساب داخل المحرك (بيانات هوية/خدمة، لا ذاكرة
  نموذج) — قراءتها وكتابتها محكومة بنطاق هوية موثقة (نفس عقد الذاكرة).
- `email_at_last_seen` — معلومة عرض أرشيفية فقط (البريد ليس هوية).

الفصل البنيوي عن بيانات النموذج:
- بيانات **الهوية** هنا: ملف واحد `accounts-state.json` + سجل أحداث إلحاقي
  `accounts-events.jsonl` (مستوى أ — خارج شجرة git بحارس المسار).
- بيانات **النموذج** (ذاكرة/موافقات) في مخازنها بمفتاح معرف الحساب نفسه
  (`client_id` = معرف الحساب الكانوني عبر `Principal.principal_id`) —
  ملفات وادلة مختلفة تمامًا، ولا يمس أحدهما الآخر.
- المحادثات (المستوى ج) تعيش اليوم في موقع Alkemos.com؛ عند بناء تخزين
  محادثات داخل المحرك مستقبلًا يكون مفتاحه معرف الحساب نفسه (موثق في
  ADR-0023 §خطة الواجهة المستقبلية).

سلامة التخزين (نفس قوانين المستودع): كتابة ذرية تحت قفل flock · بصمة
تكامل ذاتية تكشف **التلف** بصوت عالٍ (لا إسقاط صامت) · خارج المستودع
نهائيًا · كل الطوابع UTC ISO-8601 بلاحقة Z (ADR-0013).

**حدود سلامة معلنة بصدق (مراجعة دفعة 17 — أمر المالك):**
- **بصمة SHA-256 لل حالة تكشف التلف لا العبث المتعمد:** تلتقط انقطاع
  الكتابة وانحراف الملف والتعديل الجزئي بلا إعادة حساب؛ لكن من يملك
  حق الكتابة على الملف يستطيع إعادة كتابته **وإعادة حساب البصمة
  نفسها** فتمرّ — لا ادعاء كريبتوغرافي هنا. سلامة البيانات أمام خصم
  مالك حق الكتابة مسؤولية الطبقة التشغيلية (دليل مملوك خارج git بحارس
  المسار + صلاحيات الملفات + النسخ الاحتياطي).
- **سجل الأحداث (accounts-events.jsonl) إلحاقي بلا سلسلة ولا توقيع:**
  يكشف الفساد الصريح عند القراءة فقط (JSON غير قابل للقراءة) — أما
  الاقتطاع أو الحذف الصامت أو إعادة الكتابة فلا تكشفها الشيفرة إطلاقًا
  (حد معلن: التدقيق الحقيقي للسجل عند التشغيل يعتمد الطبقة التشغيلية
  نفسها). لا يُستخدم السجل لإثبات أي شيء أمني.
- **بيانات الفهرس ليست مصدر إثبات هوية أو صلاحيات أبدًا:** سجلات
  الحسابات وroles_seen وعدادات الاستخدام والتفضيلات بيانات خدمية
  للأرشيف والعرض — الهوية الحية تثبت بتحقق المزود من المنبع حصرًا
  (``UnifiedIdentityService``) والصلاحيات بسكّ ``TokenAuthority`` عبر
  المحلل بأقل صلاحية؛ لا مسار واحد يقرأ الفهرس ليمنح هوية أو صلاحية
  (مختبر سالبًا في حزمة الهوية).
"""
from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Dict, List, Optional

from .. import auth
from ..fsafety import (
    FileLock,
    assert_outside_git_tree,
    atomic_append_line,
    atomic_write_text,
    utc_now_iso,
)
from .contract import VerifiedAccount, canonical_account_id, is_verified_account

STATE_SCHEMA = "alkemos.identity-accounts/1"
STATE_FILE = "accounts-state.json"
EVENTS_FILE = "accounts-events.jsonl"
LOCK_FILE = "accounts.lock"

PREFERENCES_MAX_KEYS = 64
PREFERENCES_MAX_BYTES = 16 * 1024

_DESC = "فهرس حسابات المحرك"


class AccountIndexError(RuntimeError):
    """خلل في فهرس الحسابات — صوت عالٍ لا صمت."""


def _state_integrity(body: Dict) -> str:
    payload = dict(body)
    payload.pop("integrity", None)
    payload.pop("updated_at", None)
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


class AccountIndex:
    """سجل هوية الحسابات — مستوى أ: خارج شجرة git، ذري، مقفل، مُدقَّق."""

    def __init__(self, root) -> None:
        root_path = Path(root)
        if not root_path.is_absolute():
            raise AccountIndexError("مسار فهرس الحسابات يجب أن يكون مطلقًا")
        assert_outside_git_tree(root_path)   # بيانات هوية = مستوى أ
        root_path.mkdir(parents=True, exist_ok=True)
        self.root = root_path
        self.state_path = root_path / STATE_FILE
        self.events_path = root_path / EVENTS_FILE
        self.lock_path = root_path / LOCK_FILE

    # -- الحالة -------------------------------------------------------------
    def _load_state_locked(self) -> Dict:
        if not self.state_path.exists():
            return {"schema": STATE_SCHEMA, "accounts": {}, "updated_at": utc_now_iso()}
        raw = self.state_path.read_text(encoding="utf-8")
        try:
            state = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise AccountIndexError(
                "ملف فهرس الحسابات تالف (JSON غير قابل للقراءة) — لا إعادة "
                "تعيين صامتة: القرار بيد المالك من نسخة استعادة"
            ) from exc
        if state.get("schema") != STATE_SCHEMA:
            raise AccountIndexError(
                f"مخطط فهرس الحسابات غير معروف: {state.get('schema')!r}"
            )
        if state.get("integrity") != _state_integrity(state):
            raise AccountIndexError(
                "بصمة تكامل فهرس الحسابات لا تطابق المحتوى — تلف (أو تعديل "
                "أعاد حساب البصمة: كشف التلف لا منع العبث — الحدود موثقة "
                "أعلاه)"
            )
        return state

    def _save_state_locked(self, state: Dict) -> None:
        state = dict(state)
        state["updated_at"] = utc_now_iso()
        state.pop("integrity", None)
        state["integrity"] = _state_integrity(state)
        atomic_write_text(
            self.state_path, json.dumps(state, ensure_ascii=False, indent=2)
        )

    def _append_event_locked(self, event: Dict) -> None:
        row = {"ts": utc_now_iso(), **event}
        atomic_append_line(self.events_path, json.dumps(row, ensure_ascii=False))

    # -- التسجيل ---------------------------------------------------------------
    def record(self, account) -> Dict:
        """تسجيل حساب موثق (أول ظهور أو ظهور لاحق) — بيانات هوية فقط.

        يحدث last_seen وsessions_count والأدوار المشاهدة، ويحدث البريد
        الأرشيفي (معلومة عرض) — لا يخزن أي بيانات نموذج.
        """
        if not is_verified_account(account):
            raise AccountIndexError(
                "التسجيل يقبل حسابًا موثقًا من مزود حصرًا — لا قيم من المستدعي"
            )
        with FileLock(self.lock_path):
            state = self._load_state_locked()
            accounts: Dict = state.setdefault("accounts", {})
            entry = accounts.get(account.account_id)
            if entry is None:
                accounts[account.account_id] = {
                    "account_id": account.account_id,
                    "first_seen": utc_now_iso(),
                    "last_seen": utc_now_iso(),
                    "roles_seen": [account.role],
                    "sessions_count": 1,
                    "email_at_last_seen": account.email,
                    "provider": account.provider,
                    "preferences": {},
                }
                event = {
                    "event": "account_first_seen",
                    "account_id": account.account_id,
                    "role": account.role,
                    "provider": account.provider,
                }
                self._append_event_locked(event)
            else:
                entry["last_seen"] = utc_now_iso()
                entry["sessions_count"] = int(entry.get("sessions_count", 0)) + 1
                if account.role not in (entry.get("roles_seen") or []):
                    entry.setdefault("roles_seen", []).append(account.role)
                entry["email_at_last_seen"] = account.email
                entry["provider"] = account.provider
                self._append_event_locked({
                    "event": "account_seen",
                    "account_id": account.account_id,
                    "role": account.role,
                    "sessions": entry["sessions_count"],
                })
            self._save_state_locked(state)
            return dict(accounts[account.account_id])

    # -- القراءة ---------------------------------------------------------------
    def get(self, account_id: str) -> Optional[Dict]:
        """سجل الحساب (بيانات هوية) أو None — بلا بيانات نموذج."""
        canonical = canonical_account_id(account_id)
        with FileLock(self.lock_path):
            state = self._load_state_locked()
            entry = (state.get("accounts") or {}).get(canonical)
            return dict(entry) if entry else None

    def usage(self, account_id: str) -> Dict:
        """ملخص استخدام المحرك للحساب (جلسات) — من بيانات الهوية."""
        entry = self.get(account_id)
        if entry is None:
            return {"account_id": canonical_account_id(account_id), "sessions_count": 0}
        return {
            "account_id": entry["account_id"],
            "sessions_count": int(entry.get("sessions_count", 0)),
            "first_seen": entry.get("first_seen"),
            "last_seen": entry.get("last_seen"),
        }

    def all_accounts(self) -> List[Dict]:
        with FileLock(self.lock_path):
            state = self._load_state_locked()
            return [dict(v) for v in (state.get("accounts") or {}).values()]

    # -- التفضيلات (بيانات هوية/خدمة لكل حساب) --------------------------------
    def get_preferences(self, account_id: str) -> Dict:
        entry = self.get(account_id)
        if entry is None:
            return {}
        prefs = entry.get("preferences") or {}
        return dict(prefs) if isinstance(prefs, dict) else {}

    def set_preferences(self, principal, account_id: str, preferences: Dict) -> Dict:
        """كتابة تفضيلات الحساب — بهوية موثقة يغطي نطاقها الحساب حصرًا.

        (نفس عقد الذاكرة: العميل لنفسه، الخدمة/الأدمن في نطاقهم، المالك للكل
        — البريد وأي قيمة نصية من المستدعي لا تمنح شيئًا.)
        """
        if not auth.is_verified_principal(principal):
            raise AccountIndexError(
                "كتابة التفضيلات تقتضي هوية موثقة (Principal) — لا قيم من المستدعي"
            )
        if not principal.can_access_client(canonical_account_id(account_id)):
            raise AccountIndexError(
                f"الهوية {principal.describe()} لا يغطي نطاقها الحساب "
                f"'{account_id}' — تفضيلات الحساب له ولمن في نطاقه حصرًا"
            )
        if not isinstance(preferences, dict):
            raise AccountIndexError("التفضيلات يجب أن تكون قاموسًا")
        if len(preferences) > PREFERENCES_MAX_KEYS:
            raise AccountIndexError(
                f"التفضيلات لا تتجاوز {PREFERENCES_MAX_KEYS} مفتاحًا"
            )
        blob = json.dumps(preferences, ensure_ascii=False)
        if len(blob.encode("utf-8")) > PREFERENCES_MAX_BYTES:
            raise AccountIndexError(
                f"حجم التفضيلات فوق الحد ({PREFERENCES_MAX_BYTES} بايت)"
            )
        for key in preferences:
            if not isinstance(key, str) or not key.strip():
                raise AccountIndexError("مفاتيح التفضيلات نصية غير فارغة")
        canonical = canonical_account_id(account_id)
        with FileLock(self.lock_path):
            state = self._load_state_locked()
            entry = (state.get("accounts") or {}).get(canonical)
            if entry is None:
                raise AccountIndexError(
                    "الحساب غير مسجل في الفهرس — سجّل الجلسة أولًا (record)"
                )
            entry["preferences"] = dict(preferences)
            self._save_state_locked(state)
            self._append_event_locked({
                "event": "preferences_updated",
                "account_id": canonical,
                "keys": sorted(preferences),
                "by": principal.describe(),
            })
            return dict(entry["preferences"])

    # -- التدقيق ---------------------------------------------------------------
    def events(self) -> List[Dict]:
        """أحداث الفهرس كما كُتبت — **بيانات تدقيق أرشيفية لا إثبات أمني**.

        (حدود السلامة موثقة في رأس الوحدة: السجل إلحاقي بلا سلسلة ولا
        توقيع — يكشف الفساد الصريح عند القراءة فقط، والاقتطاع/الحذف
        الصامت خارج قدرة الشيفرة. لا يُشتق منه أي هوية أو صلاحية.)
        """
        if not self.events_path.exists():
            return []
        rows: List[Dict] = []
        for line in self.events_path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                rows.append(json.loads(line))
        return rows
