#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""اختبار طفرة لفحوص بوابة G-K في gk_build_cards.py (دفعة 9 + مراجعتها).

يشغل الفحوص على نسخ مؤقتة معدولة (بلا مساس بالبطاقات الحقيقية) ويتحقق أن كل
طفرة تُلتقط بالخطأ المتوقع — والسليم يمر بصفر أخطاء. المنهج نفسه اختبار طفرة
مراجعة دفعة 8 (8/8) على مولّد M1.

مراجعة دفعة 9 (بأمر المالك) — توسيع الفحص إلى ما كان ادعاءً توثيقيًا فقط:
بوابة G-K تتحقق **فعليًا** من تطابق SHA المصدر وتاريخ الاطلاع في نص كل بطاقة
(الجديدة التي ستُكتب والمعتمدة القائمة على القرص معًا) — T11..T20 تثبت رفض:
SHA إصدار سابق/مزيف، بصمة كاملة معدولة، تاريخ اطلاع غير صحيح/تالف الصيغة،
تاريخ مراجعة متنافر مع التوقيع، بطاقة معتمدة بلا نص — وأن البطاقات الحقيقية
الـ15 القائمة تعبر البوابة المحدثة (عقد إعادة البناء).
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from scripts import gk_build_cards as gk  # noqa: E402
from scripts.m1_build_datasets import collect_source_rules, fetch_source, extract_export  # noqa: E402

SCRIPTS = os.path.dirname(os.path.abspath(__file__))
PATHS = set(gk.CARD_SOURCE_FILES)


def setup():
    cache = os.path.join(SCRIPTS, ".source-cache")
    sources = {p: fetch_source(p, cache) for p in gk.CARD_SOURCE_FILES}
    rules = collect_source_rules(sources)
    rules["diet_levels"] = list(extract_export(sources[gk.S["matrix"]], "DIET_LEVELS"))
    rules["matrix_splits"] = {s["slug"]: s["split"] for s in
                              extract_export(sources[gk.S["matrix"]], "DIET_SYSTEMS")}
    gk.pin_card_facts(sources)
    return gk.build_card_specs(rules)


def run_gate(cards, existing, paths, rendered=None):
    return gk.gate_checks(cards, existing, paths, rendered)


def main():
    cards = setup()
    texts = [gk.render_card(i, c) for i, c in enumerate(cards, start=1)]
    base = run_gate(cards, [], PATHS, texts)
    assert base == [], f"السليم يجب أن يمر بصفر أخطاء — وجد: {base}"
    results = []

    def check(name, cond, expect_substr):
        # cond = قائمة أخطاء الفحص للطفرة؛ نجاح الاختبار = أخطاء غير فارغة وفيها الوسم
        ok = bool(cond) and any(expect_substr in e for e in cond)
        results.append((name, ok, cond[:2] if cond else []))

    # ── فحوص دفعة 9 الأصلية (T1–T10) ──

    # T1: تعارض حقيقي — بطاقة قائمة بنفس الكيان بقيمة مختلفة
    fake_existing = [{
        "file": "CARD-0001-x.md", "id": "CARD-9999",
        "entity": cards[0]["entity"], "status": "معتمدة",
        "fingerprint": "deadbeef" * 8,
        "text": gk.render_card(1, cards[0]),
    }]
    check("T1 تعارض كيان بقيمة مختلفة",
          run_gate(cards, fake_existing, PATHS, texts), "[تعارض]")

    # T2: تكرار — كيان بقيمة مطابقة تحت معرف مختلف (يجب رفع إصدار القائمة)
    fp0 = gk.fingerprint_of(cards[0])
    fake_dup = [{
        "file": "CARD-0001-x.md", "id": "CARD-9999",
        "entity": cards[0]["entity"], "status": "معتمدة",
        "fingerprint": fp0,
        "text": gk.render_card(1, cards[0]),
    }]
    check("T2 تكرار قيمة مطابقة تحت معرف آخر",
          run_gate(cards, fake_dup, PATHS, texts), "[تكرار]")

    # T3: كيان مكرر داخل العينة نفسها
    mutated = [dict(c) for c in cards]
    mutated[5]["entity"] = mutated[0]["entity"]  # البطاقة 6 تأخذ كيان البطاقة 1
    check("T3 كيان مكرر داخل العينة",
          run_gate(mutated, [], PATHS), "[تعارض-عينة]")

    # T4: ثنائية اللغة — حذف الحقائق الإنجليزية من بطاقة
    mutated = [dict(c) for c in cards]
    mutated[2] = dict(mutated[2])
    mutated[2]["facts_en"] = []
    check("T4 بتر الحقائق الإنجليزية",
          run_gate(mutated, [], PATHS), "[ثنائي]")

    # T5: ثنائية اللغة — سطر إنجليزي صار عربيًا خالصًا
    mutated = [dict(c) for c in cards]
    mutated[3] = dict(mutated[3])
    mutated[3]["facts_en"] = ["هذا سطر عربي بالكامل وليس إنجليزيًا إطلاقًا"] + mutated[3]["facts_en"][1:]
    check("T5 سطر إنجليزي بلا لاتينية",
          run_gate(mutated, [], PATHS), "[ثنائي]")

    # T6: مصطلح مفتاحي غائب
    mutated = [dict(c) for c in cards]
    mutated[10] = dict(mutated[10])
    mutated[10]["en_terms"] = ["TOTALLY-ABSENT-TERM"]
    check("T6 مصطلح مفتاحي غائب عن الإنجليزية",
          run_gate(mutated, [], PATHS), "[ثنائي]")

    # T7: استشهاد بمسار غير مجلوب
    mutated = [dict(c) for c in cards]
    mutated[6] = dict(mutated[6])
    mutated[6]["sources"] = ["src/lib/does-not-exist.ts"]
    check("T7 استشهاد بمسار وهمي",
          run_gate(mutated, [], PATHS), "[استشهاد]")

    # T8: عدد بطاقات منحرف عن المتوقع
    mutated = cards[:14]
    check("T8 عدد البطاقات منحرف",
          run_gate(mutated, [], PATHS), "[أعداد]")

    # T9: إعادة كتابة حتمية — نفس المعرف والكيان والبصمة والنص = مسموحة
    fp_all = [{"file": f"CARD-{i:04d}-x.md", "id": f"CARD-{i:04d}",
               "entity": cards[i - 1]["entity"], "status": "معتمدة",
               "fingerprint": gk.fingerprint_of(cards[i - 1]),
               "text": texts[i - 1]} for i in range(1, 16)]
    rerun = run_gate(cards, fp_all, PATHS, texts)
    results.append(("T9 إعادة كتابة حتمية بنفس المحتوى (يجب أن تمر)", rerun == [], rerun[:2]))

    # T10: حقيقة عربية بلا محرف عربي
    mutated = [dict(c) for c in cards]
    mutated[1] = dict(mutated[1])
    mutated[1]["facts_ar"] = ["pure ascii line no arabic"] + mutated[1]["facts_ar"][1:]
    check("T10 سطر عربي بلا محرف عربي",
          run_gate(mutated, [], PATHS), "[ثنائي]")

    # ── مراجعة دفعة 9: تحقق فعلي من SHA المصدر وتاريخ الاطلاع (T11–T20) ──

    # T11: SHA إصدار سابق (ed57082) في سطر source لبطاقة جديدة
    bad = list(texts)
    bad[0] = bad[0].replace(f"{gk.SRC_TAG}:", "alkemos-aws@ed57082:", 1)
    check("T11 SHA إصدار سابق في بطاقة جديدة (ed57082)",
          run_gate(cards, [], PATHS, bad), "SHA المصدر لا يطابق")

    # T12: SHA مزيف كامل (40 محرفًا) في سطر source لبطاقة جديدة
    bad = list(texts)
    bad[1] = bad[1].replace(f"{gk.SRC_TAG}:", "alkemos-aws@" + "deadbeef" * 5 + ":", 1)
    check("T12 SHA مزيف (40 محرفًا) في بطاقة جديدة",
          run_gate(cards, [], PATHS, bad), "SHA المصدر لا يطابق")

    # T13: بصمة SHA الكاملة معدولة في قسم الأصل (وسم السطر القصير سليم)
    bad = list(texts)
    bad[2] = bad[2].replace(gk.SOURCE_SHA, "deadbeef" * 5, 1)
    check("T13 بصمة SHA الكاملة معدولة في قسم الأصل",
          run_gate(cards, [], PATHS, bad), "غائبة عن قسم الأصل")

    # T14: تاريخ اطلاع غير صحيح في بطاقة جديدة (2026-11-20 بدل المثبّت)
    bad = list(texts)
    bad[3] = bad[3].replace(f"اطلاع {gk.ACCESS_UTC} (UTC)", "اطلاع 2026-11-20 (UTC)", 1)
    check("T14 تاريخ اطلاع غير صحيح في بطاقة جديدة",
          run_gate(cards, [], PATHS, bad), "تاريخ الاطلاع غير صحيح")

    # T15: تاريخ اطلاع تالف الصيغة التقويمية (شهر 13 ويوم 45)
    bad = list(texts)
    bad[4] = bad[4].replace(f"اطلاع {gk.ACCESS_UTC} (UTC)", "اطلاع 2026-13-45 (UTC)", 1)
    check("T15 تاريخ اطلاع تالف الصيغة التقويمية",
          run_gate(cards, [], PATHS, bad), "تقويميًا صالحًا")

    # T16: بطاقة معتمدة قائمة على القرص تستشهد بSHA إصدار سابق
    tampered = gk.render_card(1, cards[0]).replace(f"{gk.SRC_TAG}:", "alkemos-aws@ed57082:", 1)
    fake_old_sha = [{"file": "CARD-9001-x.md", "id": "CARD-9001",
                     "entity": "كيان/طفرة-قرص-SHA", "status": "معتمدة",
                     "fingerprint": "0" * 64, "text": tampered}]
    check("T16 بطاقة معتمدة قائمة بSHA إصدار سابق",
          run_gate(cards, fake_old_sha, PATHS, texts), "SHA المصدر لا يطابق")

    # T17: بطاقة معتمدة قائمة على القرص بتاريخ اطلاع غير صحيح
    tampered = gk.render_card(1, cards[0]).replace(
        f"اطلاع {gk.ACCESS_UTC} (UTC)", "اطلاع 2026-11-20 (UTC)", 1)
    fake_old_date = [{"file": "CARD-9002-x.md", "id": "CARD-9002",
                      "entity": "كيان/طفرة-قرص-تاريخ", "status": "معتمدة",
                      "fingerprint": "0" * 64, "text": tampered}]
    check("T17 بطاقة معتمدة قائمة بتاريخ اطلاع غير صحيح",
          run_gate(cards, fake_old_date, PATHS, texts), "تاريخ الاطلاع غير صحيح")

    # T18: بطاقة معتمدة قائمة بلا نص متاح — لا بطاقة تفلت من التحقق
    fake_no_text = [{"file": "CARD-9003-x.md", "id": "CARD-9003",
                     "entity": "كيان/طفرة-بلا-نص", "status": "معتمدة",
                     "fingerprint": "0" * 64}]
    check("T18 بطاقة معتمدة قائمة بلا نص للتحقق",
          run_gate(cards, fake_no_text, PATHS, texts), "بلا نص متاح")

    # T19: last_reviewed متنافر مع تاريخ توقيع approved_via
    bad = list(texts)
    bad[5] = bad[5].replace(f"last_reviewed: {gk.GATE_UTC} (UTC)",
                            "last_reviewed: 2026-11-21 (UTC)", 1)
    check("T19 last_reviewed متنافر مع توقيع approved_via",
          run_gate(cards, [], PATHS, bad), "لا يطابق تاريخ توقيع")

    # T20 (اندماجي): البطاقات الـ15 الحقيقية على القرص عبر load_existing_cards
    #     + إعادة توليد العينة = إعادة كتابة حتمية تعبر البوابة المحدثة بصفر أخطاء
    cards_dir = os.path.join(os.path.dirname(SCRIPTS), "memory", "cards")
    real_existing = gk.load_existing_cards(cards_dir)
    assert len(real_existing) == 15, f"متوقع 15 بطاقة قائمة — وجد {len(real_existing)}"
    rerun = run_gate(cards, real_existing, PATHS, texts)
    results.append(("T20 البطاقات الحقيقية الـ15 تعبر البوابة المحدثة (صفر أخطاء)",
                    rerun == [], rerun[:2]))

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
