#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""اختبارات المُصدِّر — وصفة التصدير الكامل والدوران (استيراد في بيئة نظيفة).

الخطة §3/§7: التصدير بصيغ مفتوحة (JSONL) + manifest ببصمات sha256 + تحقق
استيراد — إثبات عملي أن الطبقة أصل مملوك قابل للنقل (phase-05 م5-4).
"""
import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from engine import exporter as exp  # noqa: E402
from engine.memory import store as mstore  # noqa: E402

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CARDS_DIR = os.path.join(REPO_ROOT, "memory", "cards")


def main():
    results = []

    def check(name, cond, detail=""):
        results.append((name, bool(cond)))
        mark = "✓" if cond else "✗"
        print(f"  {mark} {name}" + (f" — {detail}" if (detail and not cond) else ""))

    exporter = exp.Exporter()

    with tempfile.TemporaryDirectory() as data_root, tempfile.TemporaryDirectory() as out_root:
        # مكونات المصدر: ذاكرة (3 حقائق) + البطاقات الحقيقية + أنماط + أمثلة
        mem = mstore.JsonlMemoryStore(data_root)
        now = "2026-11-24T00:00:00.000Z"
        for fact in ["يتمرن 4 أيام", "يفضل المساء", "يريد خسارة 10 كجم"]:
            mem.append_fact({"client_id": "c1", "fact": fact, "category": "lifestyle",
                             "is_active": True, "created_at": now, "updated_at": now,
                             "source": "chat_extraction"})

        examples_dir = os.path.join(data_root, "examples")
        os.makedirs(examples_dir, exist_ok=True)
        with open(os.path.join(examples_dir, "EX-0001.json"), "w", encoding="utf-8") as fh:
            json.dump({"example_id": "EX-0001", "content": "مثال"}, fh, ensure_ascii=False)

        patterns = [
            {"bucket": "calories_by_goal", "key": "fat-loss",
             "payload": {"count": 3, "avg": 1600, "min": 1500, "max": 1700}, "sample_size": 3},
            {"bucket": "meal_count", "key": "3", "payload": {"count": 5}, "sample_size": 5},
        ]

        out_dir = os.path.join(out_root, "export-v1")
        manifest = exporter.export_all(
            out_dir,
            memory_store=mem,
            cards_dir=CARDS_DIR,
            patterns_rows=patterns,
            examples_dir=examples_dir,
        )

        check("التصدير: manifest بأربعة ملفات", set(manifest["files"]) == {"memory.jsonl", "knowledge.jsonl", "patterns.jsonl", "examples.jsonl"})
        check("التصدير: طابع UTC في الـmanifest", manifest["generated_at"].endswith("Z"))
        check("التصدير: أعداد صحيحة (3 حقائق، 15 بطاقة، نمطان، مثال)", manifest["files"]["memory.jsonl"]["count"] == 3 and manifest["files"]["knowledge.jsonl"]["count"] == 15 and manifest["files"]["patterns.jsonl"]["count"] == 2 and manifest["files"]["examples.jsonl"]["count"] == 1)
        check("التصدير: بصمة sha256 لكل ملف (64 محرفًا)", all(len(m["sha256"]) == 64 for m in manifest["files"].values()))

        # الدوران: تحقق في بيئة نظيفة
        report = exporter.verify_round_trip(out_dir)
        check("الدوران: التحقق كامل النجاح في بيئة نظيفة", report["ok"] and all(f["ok"] for f in report["files"].values()))

        # المحتوى نفسه: قراءة الاستيراد تعيد البيانات الأصلية
        rows = exporter.read_jsonl(os.path.join(out_dir, "memory.jsonl"))
        check("الدوران: الحقائق الثلاث عادت كما هي", len(rows) == 3 and rows[0]["fact"] == "يتمرن 4 أيام")
        cards_rows = exporter.read_jsonl(os.path.join(out_dir, "knowledge.jsonl"))
        check("الدوران: البطاقات الـ15 عادت بمصادرها", len(cards_rows) == 15 and all(c["source"] for c in cards_rows))

        # العبث يُكتشف: أي تغيير بعد التصدير يكسر البصمة
        with open(os.path.join(out_dir, "patterns.jsonl"), "a", encoding="utf-8") as fh:
            fh.write(json.dumps({"bucket": "x"}, ensure_ascii=False) + "\n")
        report = exporter.verify_round_trip(out_dir)
        check("العبث: أي تعديل بعد التصدير يكسر التحقق", not report["ok"] and not report["files"]["patterns.jsonl"]["ok"])

        # التصدير حتمي للمحتوى: إعادة تصدير نفس المصدر تعيد نفس بصمة الملفات
        out_dir2 = os.path.join(out_root, "export-v2")
        manifest2 = exporter.export_all(out_dir2, memory_store=mem, cards_dir=CARDS_DIR,
                                        patterns_rows=patterns, examples_dir=examples_dir)
        same = all(
            manifest["files"][k]["sha256"] == manifest2["files"][k]["sha256"]
            for k in manifest["files"]
        )
        check("الحتمية: تصديران لنفس المصدر = بصمات متطابقة", same)

    passed = sum(1 for _, ok in results if ok)
    print(f"\n{passed}/{len(results)} اختبارًا ناجحًا")
    sys.exit(0 if passed == len(results) else 1)


if __name__ == "__main__":
    main()
