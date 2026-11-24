#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""مخزن ذاكرة العملاء (R1) — المستوى أ: تخزين مملوك خارج المستودع العام نهائيًا.

الخطة §2-أ: «التخزين: Postgres مملوك + تصدير JSONL؛ خارج المستودع العام نهائيًا».
تُنفَّذ هنا صيغة الملفات المفتوحة (JSONL) كأصل أول (الخطة §1: التخزين ملفات مفتوحة
+ قاعدة بيانات مملوكة)، وadaptor الـPostgres مؤجل بقرار مالك (تزويد قاعدة + متغير
بيئة بلا أسرار في المستودع — SECURITY §1) — لا يُشحن كود غير مختبر.

الحوكمة المنفذة في الكود:
- حارس المسار: يرفض أي مخزن داخل شجرة git (بما فيها هذا المستودع العام) —
  تطبيق فعلي لقاعدة «خارج المستودع العام نهائيًا».
- الإلغاء بدل الحذف (is_active) — قرار D2 الموروث.
- الحذف النهائي بأمر مالك موثق فقط (نمط D2) — في service.py.
- عداد الاستخراج لكل عميل على «الخادم» فقط (نمط evo_memory_state/0078 المضاد للعبث).
- كل الطوابع UTC ISO-8601 بلاحقة Z (ADR-0013).

(دفعة 16-تتمة — تحصين سلامة التخزين بأمر المالك):
- **كتابة ذرية** لكل تحديث (fsafety.atomic_write) — انقطاع العملية لا يبتلع الملف.
- **قفل flock حصري** حول كل دورة قراءة-تعديل-كتابة — الكتابة المتزامنة (عمليات
  متعددة) لا تضيع تحديثات بعضها ولا تكرر معرفات.
- **معرفات أحادية لا تُعاد أبدًا:** عدّاد تسلسلي خادمي (state.next_fact_seq) بأرضية
  دائمة من أعلى معرف قائم — الحذف النهائي لا يفسح إعادة استخدام المعرف.
- **استعادة آمنة:** السطر الأخير المبتور (أثر انقطاع) يُستعاد بنسخة محجوزة؛
  تلف الوسط يُعلن FileCorruptionError بصوت عالٍ — لا إسقاط صامت لبيانات.
- ملف state تالف: نسخة محجوزة + إعادة اشتقاق آمنة (العدادات من الصفر والمعرفات
  من أعلى قائم) — الحقائق نفسها لا تُمس.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Dict, Iterable, List, Optional

from ..fsafety import (
    FileCorruptionError,
    FileLock,
    append_recovery_note,
    assert_outside_git_tree,
    atomic_append_line,
    atomic_write_text,
    read_jsonl_with_recovery,
    utc_now_iso,
)
from . import pure

FACTS_FILE = "memory.jsonl"
STATE_FILE = "state.json"
LOCK_FILE = "store.lock"


class MemoryStore:
    """عقد المخزن (Repository) — أي تنفيذ لاحق (Postgres مثلاً) يلتزم به حرفيًا.

    نقطة الوصول للتخزين هي الاستبدال الوحيد المسموح عند نقل الوحدات النقية
    (خريطة الدمج §4) — المنطق النقي فوقها لا يتغير.
    """

    def load_facts(self, client_id: str, active_only: bool = True) -> List[Dict]:
        raise NotImplementedError

    def append_fact(self, record: Dict) -> Dict:
        raise NotImplementedError

    def set_fact_active(self, client_id: str, fact_id: str, is_active: bool, now: str) -> bool:
        raise NotImplementedError

    def delete_fact(self, client_id: str, fact_id: str) -> bool:
        raise NotImplementedError

    def get_extract_count(self, client_id: str) -> int:
        raise NotImplementedError

    def set_extract_count(self, client_id: str, count: int) -> None:
        raise NotImplementedError

    def all_records(self) -> List[Dict]:
        raise NotImplementedError


class InMemoryMemoryStore(MemoryStore):
    """مخزن للاختبارات والداخل الذاكري — نفس العقد، بلا قرص (بلا قفل: عملية واحدة)."""

    def __init__(self) -> None:
        self._facts: List[Dict] = []
        self._counts: Dict[str, int] = {}
        self._seq = 0

    def load_facts(self, client_id: str, active_only: bool = True) -> List[Dict]:
        rows = [f for f in self._facts if f["client_id"] == client_id]
        if active_only:
            rows = [f for f in rows if f["is_active"]]
        return [dict(f) for f in rows]

    def append_fact(self, record: Dict) -> Dict:
        self._seq += 1  # أحادي تصاعدي — لا إعادة استخدام بعد الحذف
        row = dict(record)
        row["id"] = f"MF-{self._seq:06d}"
        self._facts.append(row)
        return dict(row)

    def set_fact_active(self, client_id: str, fact_id: str, is_active: bool, now: str) -> bool:
        for f in self._facts:
            if f["id"] == fact_id and f["client_id"] == client_id:
                f["is_active"] = is_active
                f["updated_at"] = now
                return True
        return False

    def delete_fact(self, client_id: str, fact_id: str) -> bool:
        before = len(self._facts)
        self._facts = [
            f for f in self._facts if not (f["id"] == fact_id and f["client_id"] == client_id)
        ]
        return len(self._facts) < before

    def get_extract_count(self, client_id: str) -> int:
        return self._counts.get(client_id, 0)

    def set_extract_count(self, client_id: str, count: int) -> None:
        self._counts[client_id] = count

    def all_records(self) -> List[Dict]:
        return [dict(f) for f in self._facts]


def _max_fact_seq(rows: List[Dict]) -> int:
    """أرضية المعرفات: أعلى رقم لاحقة MF-xxxxxx قائم (حتى مع حذف وسطي سابق)."""
    best = 0
    for r in rows:
        rid = str(r.get("id", ""))
        if rid.startswith("MF-") and rid[3:].isdigit():
            best = max(best, int(rid[3:]))
    return best


class JsonlMemoryStore(MemoryStore):
    """مخزن ملفات مفتوحة (JSONL + JSON للحالة) في دليل مملوك خارج شجرة git.

    ملف واحد للحقائق (سطر لكل حقيقة) وإعادة كتابة كاملة عند تعديل حالة أو حذف
    موثق — حجم المستوى أ في نطاقه الحالي يسمح بذلك، والتصدير بصيغة مفتوحة
    مضمون بالبناء.

    كل عملية تتم تحت قفل `store.lock` حصري (بين العمليات والخيوط) وبكتابة ذرية —
    والإلحاق سطرًا واحدًا بنداء كتابة واحد. الاستعادة تتعامل مع انقطاع الكتابة
    (سطر أخير مبتور) وتُعلن تلف الوسط بصوت عالٍ (FileCorruptionError).
    """

    def __init__(self, root: str | os.PathLike) -> None:
        root_path = Path(root)
        if not root_path.is_absolute():
            raise ValueError("مسار مخزن المستوى أ يجب أن يكون مطلقًا لتفادي الالتباس.")
        assert_outside_git_tree(root_path)
        root_path.mkdir(parents=True, exist_ok=True)
        self.root = root_path
        self.facts_path = root_path / FACTS_FILE
        self.state_path = root_path / STATE_FILE
        self.lock_path = root_path / LOCK_FILE
        with self._locked():
            if not self.facts_path.exists():
                atomic_write_text(self.facts_path, "")
            if not self.state_path.exists():
                atomic_write_text(self.state_path, "{}")

    # -- القفل: كل دورة قراءة-تعديل-كتابة تحته -------------------------------
    def _locked(self) -> FileLock:
        return FileLock(self.lock_path)

    # -- الحقائق ------------------------------------------------------------
    def _read_all_locked(self) -> List[Dict]:
        rows, recovery = read_jsonl_with_recovery(
            self.facts_path, self.root / "recovery", label=f"حقائق الذاكرة ({self.facts_path.name})"
        )
        if recovery:
            append_recovery_note(self.root, {"event": "facts_recovery", **recovery})
        return rows

    def _write_all_locked(self, rows: Iterable[Dict]) -> None:
        text = "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows)
        atomic_write_text(self.facts_path, text)

    def load_facts(self, client_id: str, active_only: bool = True) -> List[Dict]:
        with self._locked():
            rows = [r for r in self._read_all_locked() if r.get("client_id") == client_id]
        if active_only:
            rows = [r for r in rows if r.get("is_active", True)]
        return rows

    def append_fact(self, record: Dict) -> Dict:
        with self._locked():
            rows = self._read_all_locked()
            state = self._load_state_locked()
            seq = max(int(state.get("next_fact_seq", 1)), _max_fact_seq(rows) + 1)
            row = dict(record)
            row["id"] = f"MF-{seq:06d}"
            # إلحاق سطر واحد بنداء كتابة واحد (ذرّي داخل القفل) — لا إعادة كتابة الملف كله.
            atomic_append_line(self.facts_path, json.dumps(row, ensure_ascii=False))
            state["next_fact_seq"] = seq + 1
            self._save_state_locked(state)
        return dict(row)

    def set_fact_active(self, client_id: str, fact_id: str, is_active: bool, now: str) -> bool:
        with self._locked():
            rows = self._read_all_locked()
            hit = False
            for r in rows:
                if r.get("id") == fact_id and r.get("client_id") == client_id:
                    r["is_active"] = is_active
                    r["updated_at"] = now
                    hit = True
            if hit:
                self._write_all_locked(rows)
        return hit

    def delete_fact(self, client_id: str, fact_id: str) -> bool:
        with self._locked():
            rows = self._read_all_locked()
            kept = [
                r for r in rows
                if not (r.get("id") == fact_id and r.get("client_id") == client_id)
            ]
            if len(kept) == len(rows):
                return False
            # الحذف النهائي يزيل السجل ولا يُنقص عداد التسلسل — المعرف لا يُعاد أبدًا.
            self._write_all_locked(kept)
        return True

    def all_records(self) -> List[Dict]:
        with self._locked():
            return self._read_all_locked()

    # -- عداد الاستخراج (نمط evo_memory_state — على الخادم فقط) --------------
    def _load_state_locked(self) -> Dict:
        try:
            text = self.state_path.read_text(encoding="utf-8") or "{}"
            state = json.loads(text)
            if not isinstance(state, dict):
                raise ValueError("state ليس كائنًا")
            return state
        except (json.JSONDecodeError, ValueError, OSError):
            # تلف حالة: نسخة محجوزة + اشتقاق آمن (العدادات من الصفر، المعرفات بأرضية القائم)
            from ..fsafety import quarantine_copy
            if self.state_path.exists():
                backup = quarantine_copy(self.state_path, self.root / "recovery")
                append_recovery_note(self.root, {
                    "event": "state_recovery",
                    "quarantine_backup": str(backup),
                    "note": "عدادات الاستخراج صُفّرت والمعرفات أعيدت لأرضية أعلى معرف قائم",
                })
            return {}

    def _save_state_locked(self, state: Dict) -> None:
        atomic_write_text(
            self.state_path, json.dumps(state, ensure_ascii=False, indent=2) + "\n"
        )

    def get_extract_count(self, client_id: str) -> int:
        with self._locked():
            state = self._load_state_locked()
        return int(state.get("extract_counts", {}).get(client_id, 0))

    def set_extract_count(self, client_id: str, count: int) -> None:
        with self._locked():
            state = self._load_state_locked()
            state.setdefault("extract_counts", {})[client_id] = int(count)
            self._save_state_locked(state)


def default_store_root_from_env() -> Optional[Path]:
    """جذر المخزن من متغير البيئة — لا قيمة افتراضية داخلية أبدًا (قانون الخارج)."""
    val = os.environ.get("ALKEMOS_MEMORY_DATA_DIR", "").strip()
    return Path(val) if val else None
