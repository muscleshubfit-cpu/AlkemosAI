#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""سجل الموافقات والانسحابات الموثوق — مصدر الحقيقة الوحيد لأساس الاستخدام.

(دفعة 16-تتمة — حوكمة الموافقة والانسحاب بأمر المالك: «أنشئ سجلًا موثوقًا
للموافقات والانسحابات، مرتبطًا بهوية العميل والغرض ونطاق الاستخدام والتاريخ…
اجعل التحقق من أساس الاستخدام يعتمد على هذا السجل، لا على قيم يرسلها المرشح»)

القوانين:
- **إلحاقي فقط (append-only):** المنح والانسحاب أحداث تُلحق ولا تُعدل — سجل
  التدقيق كامل دائمًا حتى بعد الانسحاب (الانسحاب لا يمحو الموافقة بل يعلوها).
- **مرتبط بالهوية والغرض والنطاق والتاريخ:** كل منح يحمل معرف العميل والغرض
  ونطاق الاستخدام المصرح (تصنيفات G-EX) وتاريخ المنح ومنحه.
- **خارج المستودع العام:** سجل يحمل هوية العملاء = بيانات المستوى أ — حارس
  المسار نفسه يرفض أي جذر داخل شجرة git (الخطة §2-أ / SECURITY §3).
- **الكتابة ذرية تحت قفل** (fsafety) — لا فقد أحداث عند التزامن أو الانقطاع.
- البوابة G-EX تتحقق من هنا حصرًا؛ حقل withdrawn داخل المرشح يُتجاهل كليًا
  (لم يعد مصدرًا للحقيقة — كان الثغرة الثانية في مراجعة المحرك).
"""
from __future__ import annotations

import json
from typing import Dict, List, Optional

from ..fsafety import (
    FileLock,
    append_recovery_note,
    assert_outside_git_tree,
    atomic_append_line,
    read_jsonl_with_recovery,
    utc_now_iso,
)

BASIS_CLIENT_CONSENT = "client_consent"   # موافقة العميل الصريحة الموثقة (opt-in)
BASIS_OWNER_DECIDED = "owner_basis"       # أساس موثق يقرره المالك
BASIS_KINDS = (BASIS_CLIENT_CONSENT, BASIS_OWNER_DECIDED)

STATUS_ACTIVE = "active"
STATUS_WITHDRAWN = "withdrawn"
STATUS_UNKNOWN = "unknown"

USAGE_TRAINING_ONLY = "training_only"
USAGE_TRAINING_RETRIEVAL = "training_retrieval"
USAGE_RETRIEVAL_ONLY = "retrieval_only"
USAGE_CLASSES = (USAGE_TRAINING_ONLY, USAGE_TRAINING_RETRIEVAL, USAGE_RETRIEVAL_ONLY)

LEDGER_FILE = "consent-ledger.jsonl"
LOCK_FILE = "consent.lock"


class ConsentLedgerError(RuntimeError):
    """رفض سجل الموافقات — مرجع مكرر/نطاق غير صالح/حدث غير منطقي."""


def _valid_usage_scope(scope) -> bool:
    if not isinstance(scope, (list, tuple)) or not scope:
        return False
    return all(u in USAGE_CLASSES for u in scope)


class ConsentLedger:
    """سجل موثوق للموافقات والانسحابات — فوق دليل مملوك خارج شجرة git."""

    def __init__(self, root) -> None:
        from pathlib import Path
        root_path = Path(root)
        if not root_path.is_absolute():
            raise ConsentLedgerError("مسار سجل الموافقات يجب أن يكون مطلقًا.")
        assert_outside_git_tree(root_path)
        root_path.mkdir(parents=True, exist_ok=True)
        self.root = root_path
        self.ledger_path = root_path / LEDGER_FILE
        self.lock_path = root_path / LOCK_FILE
        if not self.ledger_path.exists():
            self.ledger_path.write_text("", encoding="utf-8")

    # -- القراءة ---------------------------------------------------------------
    def _read_events_locked(self) -> List[Dict]:
        rows, recovery = read_jsonl_with_recovery(
            self.ledger_path, self.root / "recovery", label=f"سجل الموافقات ({LEDGER_FILE})"
        )
        if recovery:
            append_recovery_note(self.root, {"event": "consent_recovery", **recovery})
        return rows

    def all_events(self) -> List[Dict]:
        with FileLock(self.lock_path):
            return self._read_events_locked()

    # -- الكتابة (إلحاقية فقط) ---------------------------------------------------
    def _append_event_locked(self, event: Dict) -> Dict:
        atomic_append_line(self.ledger_path, json.dumps(event, ensure_ascii=False))
        return dict(event)

    def grant_client_consent(
        self,
        reference: str,
        client_id: str,
        purpose: str,
        usage_scope,
        granted_at: str,
        granted_by: str = "owner",
        notes: str = "",
    ) -> Dict:
        """توثيق منح موافقة عميل صريحة (opt-in) — مرجع فريد لا يُعاد استخدامه."""
        reference = (reference or "").strip()
        if not reference:
            raise ConsentLedgerError("مرجع الموافقة مطلوب")
        if not (client_id or "").strip():
            raise ConsentLedgerError("معرف العميل مطلوب — الموافقة مرتبطة بهوية")
        if not (purpose or "").strip():
            raise ConsentLedgerError("غرض الاستخدام مطلوب (مثلًا: training)")
        if not _valid_usage_scope(usage_scope):
            raise ConsentLedgerError(
                f"نطاق الاستخدام يجب أن يكون قائمة غير فارغة من {USAGE_CLASSES}"
            )
        with FileLock(self.lock_path):
            events = self._read_events_locked()
            for ev in events:
                if ev.get("type") == "grant" and ev.get("reference") == reference:
                    raise ConsentLedgerError(
                        f"المرجع '{reference}' مسجل منحًا سابقًا — المراجع فردية لا تتكرر"
                    )
            event = {
                "type": "grant",
                "kind": BASIS_CLIENT_CONSENT,
                "reference": reference,
                "client_id": client_id,
                "purpose": purpose,
                "usage_scope": sorted(set(usage_scope)),
                "granted_at": granted_at,
                "granted_by": granted_by,
                "notes": notes,
                "recorded_at": utc_now_iso(),
            }
            return self._append_event_locked(event)

    def record_owner_basis(
        self,
        reference: str,
        purpose: str,
        usage_scope,
        decided_at: str,
        decision_ref: str,
    ) -> Dict:
        """توثيق أساس استخدام يقرره المالك (ليس موافقة عميل) — يوثق بقراره."""
        reference = (reference or "").strip()
        if not reference:
            raise ConsentLedgerError("مرجع الأساس مطلوب")
        if not (decision_ref or "").strip():
            raise ConsentLedgerError("مرجع قرار المالك مطلوب — لا أساس بلا قرار موثق")
        if not (purpose or "").strip():
            raise ConsentLedgerError("غرض الاستخدام مطلوب")
        if not _valid_usage_scope(usage_scope):
            raise ConsentLedgerError(
                f"نطاق الاستخدام يجب أن يكون قائمة غير فارغة من {USAGE_CLASSES}"
            )
        with FileLock(self.lock_path):
            events = self._read_events_locked()
            for ev in events:
                if ev.get("type") == "grant" and ev.get("reference") == reference:
                    raise ConsentLedgerError(
                        f"المرجع '{reference}' مسجل منحًا سابقًا — المراجع فردية لا تتكرر"
                    )
            event = {
                "type": "grant",
                "kind": BASIS_OWNER_DECIDED,
                "reference": reference,
                "client_id": None,  # أساس المالك غير مرتبط بعميل بعينه
                "purpose": purpose,
                "usage_scope": sorted(set(usage_scope)),
                "granted_at": decided_at,
                "granted_by": "owner",
                "decision_ref": decision_ref,
                "recorded_at": utc_now_iso(),
            }
            return self._append_event_locked(event)

    def withdraw(self, reference: str, withdrawn_at: str, reason: str = "") -> Dict:
        """توثيق انسحاب — حدث يعلو المنح ولا يمحه (سجل التدقيق يبقى كاملًا).

        يمكن للمالك سحب أساس owner_basis بنفس الآلية (السحب يعم كل الأنواع).
        """
        reference = (reference or "").strip()
        if not reference:
            raise ConsentLedgerError("مرجع الأساس المسحوب مطلوب")
        with FileLock(self.lock_path):
            events = self._read_events_locked()
            grant = next(
                (ev for ev in events if ev.get("type") == "grant" and ev.get("reference") == reference),
                None,
            )
            if grant is None:
                raise ConsentLedgerError(
                    f"لا منح مسجل بالمرجع '{reference}' — لا انسحاب فوق أساس غير موجود"
                )
            already = any(
                ev.get("type") == "withdrawal" and ev.get("reference") == reference
                for ev in events
            )
            if already:
                raise ConsentLedgerError(f"الأساس '{reference}' مسحوب سابقًا — لا تكرار للحدث")
            event = {
                "type": "withdrawal",
                "reference": reference,
                "kind": grant.get("kind"),
                "withdrawn_at": withdrawn_at,
                "reason": reason,
                "recorded_at": utc_now_iso(),
            }
            return self._append_event_locked(event)

    # -- الحالة (مصدر حقيقة البوابة) -------------------------------------------
    def lookup(self, reference: str) -> Dict:
        """حالة الأساس كما في السجل حصرًا — لا قيمة من خارج السجل تُقبل.

        يعيد {status: active|withdrawn|unknown, kind, client_id, purpose,
        usage_scope, granted_at, withdrawn_at, events:[...]}.
        """
        reference = (reference or "").strip()
        events = self.all_events()
        grant = next(
            (ev for ev in events if ev.get("type") == "grant" and ev.get("reference") == reference),
            None,
        )
        if grant is None:
            return {"status": STATUS_UNKNOWN, "reference": reference, "events": []}
        withdrawal = next(
            (ev for ev in events if ev.get("type") == "withdrawal" and ev.get("reference") == reference),
            None,
        )
        return {
            "status": STATUS_WITHDRAWN if withdrawal else STATUS_ACTIVE,
            "reference": reference,
            "kind": grant.get("kind"),
            "client_id": grant.get("client_id"),
            "purpose": grant.get("purpose"),
            "usage_scope": grant.get("usage_scope", []),
            "granted_at": grant.get("granted_at"),
            "withdrawn_at": (withdrawal or {}).get("withdrawn_at"),
            "withdrawal_reason": (withdrawal or {}).get("reason"),
            "events": [ev for ev in events if ev.get("reference") == reference],
        }

    def is_usable(self, reference: str, kind: str, usage: str) -> Optional[str]:
        """فحص البوابة الجاهز: يعيد None عند الصلاحية أو سبب الرفض نصًّا."""
        rec = self.lookup(reference)
        if rec["status"] == STATUS_UNKNOWN:
            return f"المرجع '{reference}' غير موجود في سجل الموافقات — لا أساس بلا سجل"
        if rec["kind"] != kind:
            return (
                f"نوع الأساس في السجل ({rec['kind']}) لا يطابق المدعى ({kind}) — "
                "مرجع موافقة عميل لا يُستعمل أساس مالك ولا العكس"
            )
        if rec["status"] == STATUS_WITHDRAWN:
            return (
                f"الأساس '{reference}' مسحوب في {rec['withdrawn_at']} — "
                "ممنوع من أي اعتماد جديد (سجل التدقيق محفوظ)"
            )
        if usage not in (rec.get("usage_scope") or []):
            return (
                f"نطاق الاستخدام '{usage}' خارج الموافقة (المصرح: {rec.get('usage_scope')})"
            )
        return None
