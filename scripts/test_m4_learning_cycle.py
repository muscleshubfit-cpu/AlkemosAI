#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""اختبارات أداة دورة التعلم المرشحة (scripts/m4_learning_cycle.py).

يثبت أن الأداة تعمل فعليًا فوق مدخل اصطناعي: مسودات بأنماط تتجاوز الأرضية،
هيكل مرجعي، حجب ما دون الأرضية، ومجهولية بالبناء (اسم العميل لا يظهر أبدًا).
"""
import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from scripts import m4_learning_cycle as cyc  # noqa: E402


def _plan(cal, goal="تخفيس الوزن", approved=True, origin="plans", overview="خطة العميل أحمد"):
    return {
        "origin": origin,
        "approved": approved,
        "goalText": goal,
        "content": {
            "overview": overview,
            "daily_calories": cal,
            "macros": {"protein_g": 120, "carbs_g": 150, "fat_g": 45},
            "meals": [
                {"name": "الإفطار", "total_calories": 500,
                 "items": [{"food": "بيض مسلوق", "amount": "3 بيضات", "calories": 234}]},
                {"name": "الغداء", "total_calories": 700,
                 "items": [{"food": "صدر دجاج مشوي", "calories": 250}]},
            ],
        },
    }


def main():
    results = []

    def check(name, cond, detail=""):
        results.append((name, bool(cond)))
        mark = "✓" if cond else "✗"
        print(f"  {mark} {name}" + (f" — {detail}" if (detail and not cond) else ""))

    with tempfile.TemporaryDirectory() as tmp:
        # مدخل فوق الأرضية (3 خطط هدف واحد + حدث استبدال واحد)
        src_path = os.path.join(tmp, "plans.jsonl")
        with open(src_path, "w", encoding="utf-8") as fh:
            for cal in (1600, 1500, 1700):
                fh.write(json.dumps(_plan(cal), ensure_ascii=False) + "\n")
        swaps_path = os.path.join(tmp, "swaps.jsonl")
        with open(swaps_path, "w", encoding="utf-8") as fh:
            fh.write(json.dumps({
                "old": _plan(1600)["content"],
                "new": {**_plan(1600)["content"], "meals": [
                    {"name": "الإفطار", "total_calories": 500, "items": [{"food": "بيض مسلوق", "calories": 234}]},
                    {"name": "الغداء", "total_calories": 700, "items": [{"food": "سمك مشوي", "calories": 250}]},
                ]},
            }, ensure_ascii=False) + "\n")

        out_path = os.path.join(tmp, "candidates.md")
        code = cyc.main(["--input", src_path, "--swaps", swaps_path, "--out", out_path])
        check("الأداة: تشغيل نظيف (خروج 0)", code == 0)
        report = open(out_path, encoding="utf-8").read()
        check("التقرير: كتب فعليًا وموسوم «مرشح حصرًا»", "مرشح" in report and "لا اعتماد تلقائي أبدًا" in report)
        check("التقرير: مسودة سعرات فوق الأرضية (متوسط 1600)", "calories_by_goal" in report and "1600" in report)
        check("التقرير: الهيكل المرجعي (E2) حاضر بمسار G-EX", "بوابة G-EX" in report and '"daily_calories": 1600' in report)
        check("التقرير: إشارة الاستبدال (E3) — سمك مشوي واصل", "سمك مشوي" in report and "swap_added" in report)
        check("التقرير: مجهولية بالبناء — اسم العميل غائب", "أحمد" not in report)
        check("التقرير: توثيق المدخل ببصمة sha256", "sha256" in report and "قراءة-فقط" in report)

        # مدخل دون الأرضية (خطتان)
        thin_path = os.path.join(tmp, "thin.jsonl")
        with open(thin_path, "w", encoding="utf-8") as fh:
            for cal in (1600, 1500):
                fh.write(json.dumps(_plan(cal), ensure_ascii=False) + "\n")
        thin_out = os.path.join(tmp, "thin-candidates.md")
        cyc.main(["--input", thin_path, "--out", thin_out])
        thin_report = open(thin_out, encoding="utf-8").read()
        check("الأرضية: خطتان = حجب عائلات الهدف (لا سعرات/ماكروز)", "calories_by_goal" not in thin_report and "macros_by_goal" not in thin_report)

        # مدخل مفقود
        check("الأداة: مدخل مفقود = خروج 1", cyc.main(["--input", os.path.join(tmp, "لا_يوجد.jsonl")]) == 1)

    passed = sum(1 for _, ok in results if ok)
    print(f"\n{passed}/{len(results)} اختبارًا ناجحًا")
    sys.exit(0 if passed == len(results) else 1)


if __name__ == "__main__":
    main()
