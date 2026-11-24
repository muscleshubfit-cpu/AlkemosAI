#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""سجل الاعتماد غير القابل للتعديل العادي — سلسلة بصمات hash-chained.

(دفعة 16-تتمة — توقيع المالك بأمر المالك: «اربط الاعتماد بسجل تدقيق غير قابل
للتعديل العادي، يتضمن هوية المعتمد وبصمة العنصر ووقت الاعتماد»)

التصميم:
- كل قيد اعتماد يحمل: هوية المعتمد (المالك — المتحقق منها بمفتاحه)، بصمة
  المحتوى وبصمة الأصل (تمنع الخلط بين العناصر)، مرجع القرار، تاريخ التوقيع،
  وقت التسجيل، بصمة القيد السابق، وبصمته هو.
- **بصمة القيد = sha256(تمثيل كانوني للقيد بلا حقل البصمة)** — أي تعديل لاحق
  على أي قيد يكسر السلسلة كلها من بعده، فيكشفه `verify_chain()` فورًا.
- **إلحاقي تحت قفل + كتابة ذرية** (fsafety) — لا فقد قيود عند التزامن.
- `coverage()` يقاطع الملفات المعتمدة EX-xxxx مع القيود: ملف بلا قيد أو قيد
  بلا ملف = انحراف معلن (يكشف انقطاعًا بين خطوتي الكتابة أو حذفًا لاحقًا).
- هذا «غير قابل للتعديل العادي» بحكم البنية (أي تعديل يُكشف حسابيًا)؛
  التثبيت المطلق (إرساء البصمة الرأسية خارج النظام لدى المالك) عملية خارج
  الكود موثقة في توثيق الدفعة — لا تحتاج قرارًا لتشغيل الكود.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Optional

from ..fsafety import (
    FileLock,
    append_recovery_note,
    atomic_append_line,
    canonical_json,
    read_jsonl_with_recovery,
    sha256_hex,
    utc_now_iso,
)

LEDGER_NAME = "adoption-ledger.jsonl"
GENESIS = "GENESIS"


class AdoptionLedgerError(RuntimeError):
    pass


def entry_fingerprint(entry: Dict) -> str:
    """بصمة القيد — على كل حقوله ما عدا بصمته هو (تشمل بصمة السابق)."""
    payload = {k: v for k, v in entry.items() if k != "entry_hash"}
    return sha256_hex(canonical_json(payload).encode("utf-8"))


class AdoptionLedger:
    """سجل اعتماد G-EX — سلسلة بصمات إلحاقية فوق مسار يعده المتصل."""

    def __init__(self, path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.lock_path = self.path.with_name(self.path.name + ".lock")
        if not self.path.exists():
            self.path.write_text("", encoding="utf-8")

    # -- القراءة ---------------------------------------------------------------
    def _read_locked(self) -> List[Dict]:
        rows, recovery = read_jsonl_with_recovery(
            self.path, self.path.parent / "recovery", label=f"سجل الاعتماد ({self.path.name})"
        )
        if recovery:
            append_recovery_note(self.path.parent, {"event": "adoption_recovery", **recovery})
        return rows

    def entries(self) -> List[Dict]:
        with FileLock(self.lock_path):
            return self._read_locked()

    # -- الكتابة -----------------------------------------------------------------
    def append(
        self,
        example_id: str,
        content_sha256: str,
        origin_sha256: str,
        adopter: str,
        decision_ref: str,
        signed_at: str,
        usage: str = "",
        recorded_at: Optional[str] = None,
    ) -> Dict:
        """إلحاق قيد اعتماد — يبني على آخر بصمة تحت القفل فلا تشعب للسلسلة."""
        with FileLock(self.lock_path):
            rows = self._read_locked()
            prev_hash = rows[-1]["entry_hash"] if rows else GENESIS
            entry = {
                "seq": (rows[-1]["seq"] + 1) if rows else 1,
                "example_id": example_id,
                "content_sha256": content_sha256,
                "origin_sha256": origin_sha256,
                "usage": usage,
                "adopter": adopter,
                "decision_ref": decision_ref,
                "signed_at": signed_at,
                "recorded_at": recorded_at or utc_now_iso(),
                "prev_hash": prev_hash,
            }
            entry["entry_hash"] = entry_fingerprint(entry)
            atomic_append_line(self.path, json.dumps(entry, ensure_ascii=False))
            return dict(entry)

    # -- التحقق -------------------------------------------------------------------
    def verify_chain(self) -> Dict:
        """سلامة السلسلة: يعيد {ok, entries, first_bad} — أي تعديل يُكشف."""
        rows = self.entries()
        prev = GENESIS
        for i, entry in enumerate(rows):
            if entry.get("prev_hash") != prev:
                return {"ok": False, "entries": len(rows), "first_bad": i + 1,
                        "reason": "بصمة السابق لا تطابق — قيد مُعدل أو محذوف"}
            if entry.get("entry_hash") != entry_fingerprint(entry):
                return {"ok": False, "entries": len(rows), "first_bad": i + 1,
                        "reason": "بصمة القيد لا تطابق محتواه — تعديل لاحق"}
            if entry.get("seq") != i + 1:
                return {"ok": False, "entries": len(rows), "first_bad": i + 1,
                        "reason": "تسلسل القيد مكسور"}
            prev = entry["entry_hash"]
        return {"ok": True, "entries": len(rows), "first_bad": None, "reason": None}

    def coverage(self, examples_dir) -> Dict:
        """تقاطع الملفات المعتمدة مع القيود — كل انحراف معلن بذكره.

        الفحص ثلاثي: بصمة المحتوى **محسوبة من المحتوى الفعلي** (لا من حقل
        يوثقه المعدّل) يجب أن تطابق حقل الملف وقيد السجل معًا، وبصمة الأصل
        وتصنيف الاستخدام يطابقان القيد — فأي تعديل لاحق على الملف المعتمد
        (محتوى أو تصنيف) يُكشف حسابيًا.
        """
        import hashlib

        entries = self.entries()
        by_example: Dict[str, Dict] = {}
        for e in entries:
            by_example.setdefault(e["example_id"], e)
        examples = sorted(Path(examples_dir).glob("EX-*.json")) if Path(examples_dir).exists() else []
        example_ids = {p.stem for p in examples}
        orphan_examples = sorted(example_ids - set(by_example.keys()))
        orphan_entries = sorted(set(by_example.keys()) - example_ids)
        mismatches = []
        for p in examples:
            entry = by_example.get(p.stem)
            if entry is None:
                continue
            try:
                rec = json.loads(p.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                mismatches.append({"example_id": p.stem, "problem": "ملف غير قابل للقراءة"})
                continue
            actual = hashlib.sha256(str(rec.get("content", "")).encode("utf-8")).hexdigest()
            if actual != rec.get("content_sha256"):
                mismatches.append({"example_id": p.stem, "problem": "بصمة المحتوى المحسوبة لا تطابق حقل الملف — محتوى معدل بعد الاعتماد"})
            elif actual != entry.get("content_sha256"):
                mismatches.append({"example_id": p.stem, "problem": "بصمة المحتوى في الملف لا تطابق قيد الاعتماد"})
            if (rec.get("origin") or {}).get("sha256") != entry.get("origin_sha256"):
                mismatches.append({"example_id": p.stem, "problem": "بصمة الأصل لا تطابق قيد الاعتماد"})
            if rec.get("usage") != entry.get("usage"):
                mismatches.append({"example_id": p.stem, "problem": "تصنيف الاستخدام معدل بعد الاعتماد (لا يُعدل)"})
        return {
            "ok": not orphan_examples and not orphan_entries and not mismatches,
            "orphan_examples": orphan_examples,
            "orphan_entries": orphan_entries,
            "fingerprint_mismatches": mismatches,
        }
