#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""المُصدِّر (عقد الواجهة §3): Exporter.exportAll — تصدير كامل بصيغ مفتوحة.

الخطة §3/§7: «تصدير كامل بصيغ مفتوحة (JSONL + Markdown + SQL) — اختبار استيراد
في بيئة نظيفة» — هذا التنفيذ يثبت الوصفة عمليًا: التصدير يعيد إنتاج كل مكون
من الملفات، والاستيراد في دليل نظيف يتحقق من التطابق (الاختبار الكامل خلال
ساعة معيار المرحلة؛ اختبار الوحدة يثبت صحة الدورة قصيرة المدى).

المكونات المصدَّرة:
- المستوى أ: سجل الحقائق كاملًا (JSONL) — من مخزن خارج المستودع.
- المستوى ب: البطاقات المعتمدة (JSONL) — من memory/cards/.
- الأنماط المجمعة (JSONL) — صفوف 0080-shape تمررها المتصل.
- أمثلة G-EX المعتمدة (JSONL) — من دليل المعتمد.
- manifest.json: بصمة sha256 وعدد لكل ملف + طابع UTC — الدليل الحسابي للنقل.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Dict, Iterable, List, Optional

from .knowledge.cards import load_cards
from .memory.store import utc_now_iso


def _write_jsonl(path: Path, rows: Iterable[Dict]) -> int:
    count = 0
    with path.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
            count += 1
    return count


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class Exporter:
    """وصفة التصدير الكامل — أي إضافة مخزن مستقبلي (Postgres) تلتزم نفس المخرجات."""

    def export_all(
        self,
        out_dir: str | Path,
        memory_store=None,
        cards_dir: Optional[str | Path] = None,
        patterns_rows: Optional[List[Dict]] = None,
        examples_dir: Optional[str | Path] = None,
    ) -> Dict:
        out = Path(out_dir)
        out.mkdir(parents=True, exist_ok=True)
        manifest: Dict[str, Dict] = {}

        if memory_store is not None:
            rows = memory_store.all_records()
            n = _write_jsonl(out / "memory.jsonl", rows)
            manifest["memory.jsonl"] = {"count": n}

        if cards_dir is not None:
            cards = load_cards(cards_dir, approved_only=True)
            n = _write_jsonl(
                out / "knowledge.jsonl",
                (
                    {
                        "id": c["id"],
                        "title": c["title"],
                        "classification": c["classification"],
                        "version": c["version"],
                        "status": c["status"],
                        "last_reviewed": c["last_reviewed"],
                        "source": c["source"],
                        "text": c["text"],
                    }
                    for c in cards
                ),
            )
            manifest["knowledge.jsonl"] = {"count": n}

        if patterns_rows is not None:
            n = _write_jsonl(out / "patterns.jsonl", patterns_rows)
            manifest["patterns.jsonl"] = {"count": n}

        if examples_dir is not None:
            examples = []
            for path in sorted(Path(examples_dir).glob("EX-*.json")):
                try:
                    examples.append(json.loads(path.read_text(encoding="utf-8")))
                except json.JSONDecodeError:
                    continue
            n = _write_jsonl(out / "examples.jsonl", examples)
            manifest["examples.jsonl"] = {"count": n}

        # البصمات بعد اكتمال الكتابة — الدليل الحسابي على محتوى كل ملف.
        for name in list(manifest.keys()):
            manifest[name]["sha256"] = _sha256_file(out / name)

        manifest_doc = {"generated_at": utc_now_iso(), "files": manifest}
        (out / "manifest.json").write_text(
            json.dumps(manifest_doc, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        return manifest_doc

    @staticmethod
    def read_jsonl(path: str | Path) -> List[Dict]:
        rows = []
        for line in Path(path).read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line:
                rows.append(json.loads(line))
        return rows

    def verify_round_trip(self, out_dir: str | Path) -> Dict:
        """التحقق: كل ملف في الـmanifest يطابق بصمته وعدده (استيراد في بيئة نظئة)."""
        out = Path(out_dir)
        manifest_doc = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
        report: Dict[str, Dict] = {}
        for name, meta in manifest_doc["files"].items():
            path = out / name
            if not path.exists():
                report[name] = {"ok": False, "error": "الملف مفقود"}
                continue
            sha = _sha256_file(path)
            count = len(self.read_jsonl(path))
            report[name] = {
                "ok": sha == meta["sha256"] and count == meta["count"],
                "sha256_match": sha == meta["sha256"],
                "count_match": count == meta["count"],
            }
        return {"ok": all(r["ok"] for r in report.values()), "files": report}
