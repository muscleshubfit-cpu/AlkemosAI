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
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Dict, Iterable, List, Optional

from . import pure

FACTS_FILE = "memory.jsonl"
STATE_FILE = "state.json"


def utc_now_iso() -> str:
    """طابع UTC موحد بالصيغة ISO-8601 بلاحقة Z (ADR-0013)."""
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _assert_outside_git_tree(path: Path) -> None:
    """حارس المستوى أ: بيانات تحمل هوية العملاء لا تسكن مستودعًا عامًا أبدًا.

    يصعد في شجرة الأدلة باحثًا عن دليل .git؛ وجوده يعني أن المسار داخل شجرة عمل
    git (مستودع علني أو خاص) فيُرفض فورًا.
    """
    cur = path.resolve()
    for parent in [cur, *cur.parents]:
        if (parent / ".git").exists():
            raise ValueError(
                "مخزن المستوى أ (ذاكرة العملاء) خارج المستودع نهائيًا — "
                f"المسار '{path}' يقع داخل شجرة git في '{parent}'. "
                "اختر دليلًا خارج أي مستودع (الخطة §2-أ / SECURITY §3)."
            )


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
    """مخزن للاختبارات والداخل الذاكري — نفس العقد، بلا قرص."""

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
        self._seq += 1
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


class JsonlMemoryStore(MemoryStore):
    """مخزن ملفات مفتوحة (JSONL + JSON للحالة) في دليل مملوك خارج شجرة git.

    ملف واحد للحقائق (سطر لكل حقيقة — append للإضافة) وإعادة كتابة كاملة عند
    تعديل حالة (إلغاء تنشيط) أو حذف موثق — حجم المستوى أ في نطاقه الحالي يسمح
    بذلك بأمان، والتصدير بصيغة مفتوحة مضمون بالبناء.
    """

    def __init__(self, root: str | os.PathLike) -> None:
        root_path = Path(root)
        if not root_path.is_absolute():
            raise ValueError("مسار مخزن المستوى أ يجب أن يكون مطلقًا لتفادي الالتباس.")
        _assert_outside_git_tree(root_path)
        root_path.mkdir(parents=True, exist_ok=True)
        self.root = root_path
        self.facts_path = root_path / FACTS_FILE
        self.state_path = root_path / STATE_FILE
        if not self.facts_path.exists():
            self.facts_path.write_text("", encoding="utf-8")
        if not self.state_path.exists():
            self.state_path.write_text("{}", encoding="utf-8")

    # -- الحقائق ------------------------------------------------------------
    def _read_all(self) -> List[Dict]:
        rows: List[Dict] = []
        for line in self.facts_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line:
                rows.append(json.loads(line))
        return rows

    def _write_all(self, rows: Iterable[Dict]) -> None:
        text = "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows)
        self.facts_path.write_text(text, encoding="utf-8")

    def load_facts(self, client_id: str, active_only: bool = True) -> List[Dict]:
        rows = [r for r in self._read_all() if r.get("client_id") == client_id]
        if active_only:
            rows = [r for r in rows if r.get("is_active", True)]
        return rows

    def append_fact(self, record: Dict) -> Dict:
        rows = self._read_all()
        seq = len(rows) + 1
        row = dict(record)
        row["id"] = f"MF-{seq:06d}"
        rows.append(row)
        self._write_all(rows)
        return dict(row)

    def set_fact_active(self, client_id: str, fact_id: str, is_active: bool, now: str) -> bool:
        rows = self._read_all()
        hit = False
        for r in rows:
            if r.get("id") == fact_id and r.get("client_id") == client_id:
                r["is_active"] = is_active
                r["updated_at"] = now
                hit = True
        if hit:
            self._write_all(rows)
        return hit

    def delete_fact(self, client_id: str, fact_id: str) -> bool:
        rows = self._read_all()
        kept = [
            r for r in rows
            if not (r.get("id") == fact_id and r.get("client_id") == client_id)
        ]
        if len(kept) == len(rows):
            return False
        self._write_all(kept)
        return True

    def all_records(self) -> List[Dict]:
        return self._read_all()

    # -- عداد الاستخراج (نمط evo_memory_state — على الخادم فقط) --------------
    def _load_state(self) -> Dict:
        try:
            return json.loads(self.state_path.read_text(encoding="utf-8") or "{}")
        except (json.JSONDecodeError, OSError):
            return {}

    def _save_state(self, state: Dict) -> None:
        self.state_path.write_text(
            json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    def get_extract_count(self, client_id: str) -> int:
        counts = self._load_state().get("extract_counts", {})
        return int(counts.get(client_id, 0))

    def set_extract_count(self, client_id: str, count: int) -> None:
        state = self._load_state()
        state.setdefault("extract_counts", {})[client_id] = int(count)
        self._save_state(state)


def default_store_root_from_env() -> Optional[Path]:
    """جذر المخزن من متغير البيئة — لا قيمة افتراضية داخلية أبدًا (قانون الخارج)."""
    val = os.environ.get("ALKEMOS_MEMORY_DATA_DIR", "").strip()
    return Path(val) if val else None
