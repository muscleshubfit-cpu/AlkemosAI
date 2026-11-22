#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""اختبار طفرة لفحوص بوابة G-K في gk_build_cards.py (دفعة 9).

يشغل الفحوص على نسخ مؤقتة معدلة (بلا مساس بالبطاقات الحقيقية) ويتحقق أن كل
طفرة تُلتقط بالخطأ المتوقع — والسليم يمر بصفر أخطاء. المنهج نفسه اختبار طفرة
مراجعة دفعة 8 (8/8) على مولّد M1.
"""
import os
import shutil
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from scripts import gk_build_cards as gk  # noqa: E402
from scripts.m1_build_datasets import collect_source_rules, fetch_source, extract_export  # noqa: E402

SCRIPTS = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(SCRIPTS, ".source-cache")


def setup():
    sources = {p: fetch_source(p, CACHE) for p in gk.CARD_SOURCE_FILES}
    rules = collect_source_rules(sources)
    rules["diet_levels"] = list(extract_export(sources[gk.S["matrix"]], "DIET_LEVELS"))
    rules["matrix_splits"] = {s["slug"]: s["split"] for s in
                              extract_export(sources[gk.S["matrix"]], "DIET_SYSTEMS")}
    gk.pin_card_facts(sources)
    return gk.build_card_specs(rules), sources


def run_gate(cards, existing, paths):
    return gk.gate_checks(cards, existing, paths)


def main():
    cards, _ = setup()
    base = run_gate(cards, [], set(gk.CARD_SOURCE_FILES))
    assert base == [], f"السليم يجب أن يمر بصفر أخطاء — وجد: {base}"
    results = []

    def check(name, cond, expect_substr):
        ok = (not cond) and any(expect_substr in e for e in cond) if cond else (cond is not None and False)
        # cond = قائمة أخطاء الفحص للطفرة؛ نجاح الاختبار = أخطاء غير فارغة وفيها الوسم
        ok = bool(cond) and any(expect_substr in e for e in cond)
        results.append((name, ok, cond[:2] if cond else []))

    # T1: تعارض حقيقي — بطاقة قائمة بنفس الكيان بقيمة مختلفة
    fake_existing = [{
        "file": "CARD-0001-x.md", "id": "CARD-9999",
        "entity": cards[0]["entity"], "status": "معتمدة",
        "fingerprint": "deadbeef" * 8,
    }]
    check("T1 تعارض كيان بقيمة مختلفة",
          run_gate(cards, fake_existing, set(gk.CARD_SOURCE_FILES)), "[تعارض]")

    # T2: تكرار — كيان بقيمة مطابقة تحت معرف مختلف (يجب رفع إصدار القائمة)
    fp0 = gk.fingerprint_of(cards[0])
    fake_dup = [{
        "file": "CARD-0001-x.md", "id": "CARD-9999",
        "entity": cards[0]["entity"], "status": "معتمدة",
        "fingerprint": fp0,
    }]
    check("T2 تكرار قيمة مطابقة تحت معرف آخر",
          run_gate(cards, fake_dup, set(gk.CARD_SOURCE_FILES)), "[تكرار]")

    # T3: كيان مكرر داخل العينة نفسها
    mutated = [dict(c) for c in cards]
    mutated[5]["entity"] = mutated[0]["entity"]  # البطاقة 6 تأخذ كيان البطاقة 1
    check("T3 كيان مكرر داخل العينة",
          run_gate(mutated, [], set(gk.CARD_SOURCE_FILES)), "[تعارض-عينة]")

    # T4: ثنائية اللغة — حذف الحقائق الإنجليزية من بطاقة
    mutated = [dict(c) for c in cards]
    mutated[2] = dict(mutated[2])
    mutated[2]["facts_en"] = []
    check("T4 بتر الحقائق الإنجليزية",
          run_gate(mutated, [], set(gk.CARD_SOURCE_FILES)), "[ثنائي]")

    # T5: ثنائية اللغة — سطر إنجليزي صار عربيًا خالصًا
    mutated = [dict(c) for c in cards]
    mutated[3] = dict(mutated[3])
    mutated[3]["facts_en"] = ["هذا سطر عربي بالكامل وليس إنجليزيًا إطلاقًا"] + mutated[3]["facts_en"][1:]
    check("T5 سطر إنجليزي بلا لاتينية",
          run_gate(mutated, [], set(gk.CARD_SOURCE_FILES)), "[ثنائي]")

    # T6: مصطلح مفتاحي غائب
    mutated = [dict(c) for c in cards]
    mutated[10] = dict(mutated[10])
    mutated[10]["en_terms"] = ["TOTALLY-ABSENT-TERM"]
    check("T6 مصطلح مفتاحي غائب عن الإنجليزية",
          run_gate(mutated, [], set(gk.CARD_SOURCE_FILES)), "[ثنائي]")

    # T7: استشهاد بمسار غير مجلوب
    mutated = [dict(c) for c in cards]
    mutated[6] = dict(mutated[6])
    mutated[6]["sources"] = ["src/lib/does-not-exist.ts"]
    check("T7 استشهاد بمسار وهمي",
          run_gate(mutated, [], set(gk.CARD_SOURCE_FILES)), "[استشهاد]")

    # T8: عدد بطاقات منحرف عن المتوقع
    mutated = cards[:14]
    check("T8 عدد البطاقات منحرف",
          run_gate(mutated, [], set(gk.CARD_SOURCE_FILES)), "[أعداد]")

    # T9: إعادة كتابة حتمية — نفس المعرف والكيان والبصمة = مسموحة (صفر أخطاء)
    fp_all = [{"file": f"CARD-{i:04d}-x.md", "id": f"CARD-{i:04d}",
               "entity": cards[i-1]["entity"], "status": "معتمدة",
               "fingerprint": gk.fingerprint_of(cards[i-1])} for i in range(1, 16)]
    rerun = run_gate(cards, fp_all, set(gk.CARD_SOURCE_FILES))
    results.append(("T9 إعادة كتابة حتمية بنفس المحتوى (يجب أن تمر)", rerun == [], rerun[:2]))

    # T10: حقيقة عربية بلا محرف عربي
    mutated = [dict(c) for c in cards]
    mutated[1] = dict(mutated[1])
    mutated[1]["facts_ar"] = ["pure ascii line no arabic"] + mutated[1]["facts_ar"][1:]
    check("T10 سطر عربي بلا محرف عربي",
          run_gate(mutated, [], set(gk.CARD_SOURCE_FILES)), "[ثنائي]")

    print()
    passed = sum(1 for _, ok, _ in results if ok)
    for name, ok, sample in results:
        print(f"  {'PASS' if ok else 'FAIL'} — {name}")
        if not ok and sample:
            print("        عينة الأخطاء:", sample)
    print(f"\nنتيجة اختبار الطفرة: {passed}/{len(results)}")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
