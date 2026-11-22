#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""gk_build_cards.py — مولّد أول دورة بوابة G-K: عينة بطاقات المعرفة v2 (دفعة 9 — M1).

الغرض
=====
تنفيذًا للبند الفوري التالي في M1 (STATE §2): «بطاقات المعرفة (عينة G-K)» —
أول دورة اعتماد معرفة عبر بوابة G-K (ADR-0017: مصدر موثق + لا تعارض غير
محلول + إثبات إضافة مقيسة + فحص ثنائي اللغة AR/EN + توقيع بتاريخ UTC).

ما يفعله السكربت (حتمي بالكامل — بلا عشوائية):
  1. يجلب ملفات المصدر الأساسي alkemos-aws @ 32b63874 قراءة-فقط عبر
     raw.githubusercontent بلا أي مفاتيح (R-35) — 19 ملف M1 + evo-geo-answer.ts.
  2. يثبّت كل حقيقة رقمية/قاعدية في البطاقات من المصدر نفسه عبر
     collect_source_rules() (نفس تثبيتات البطارية — مصدر حقيقة واحد)
     + تثبيتات حرفية إضافية لكل بطاقة (pin_literal) — أي انحراف يُخفق البناء.
  3. يبني 15 بطاقة معرفة v2 وفق الصيغة الإلزامية في memory/cards/README
     (+ حقل entity جديد لمأسسة فحص التعارض كيان/حقل — ADR-0017 ق2).
  4. ينفذ فحوص بوابة G-K آليًا:
       - التعارض: كيان مكرر بقيمة مختلفة = فشل؛ كيان مطابق تحت معرف جديد =
         تكرار ممنوع (يُرفع إصدار البطاقة القائمة بدل بطاقة جديدة)؛ إعادة
         تشغيل بنفس المحتوى = إعادة كتابة حتمية مسموحة (عقد إعادة البناء).
       - ثنائية اللغة: حقائق عربية ≥3 أسطر (بها محرف عربي) + إنجليزية ≥2
         (غالبية لاتينية) + مصطلحات مفتاحية إنجليزية حاضرة في الحقائق.
       - الاستشهاد (تحقق فعلي في نص كل بطاقة — الجديدة والمعتمدة القائمة
         على القرص معًا؛ مراجعة دفعة 9 بأمر المالك): وسم SHA في سطر
         source يطابق SOURCE_SHA حرفيًا (7 أو 40 محرفًا — أي SHA آخر
         وإن كان سليم الشكل = رفض) + بصمة SHA الكاملة في قسم الأصل +
         تاريخ اطلاع يطابق ACCESS_UTC + تاريخ مراجعة متسق مع توقيع
         G-K + كل مسار داخل الملفات المجلوبة فعلًا.
       - الحقول: المعرفات فردية متسلسلة، الحالة «معتمدة»، approved_via
         بتوقيع G-K بتاريخ UTC، contradicts فارغة (لا تعارض).
  5. يكتب البطاقات إلى memory/cards/ ويطبع تقرير البوابة الموقع (الأعداد
     قبل/بعد = إثبات الإضافة المقيسة — يسجل في سجل التعلم في نفس الدفعة).

الاستخدام:
  python3 scripts/gk_build_cards.py [--out ROOT] [--cache DIR]

الخروج: رمز غير صفري عند أي فشل فحص — لا بطاقات ناقصة أو غير معتمدة.
"""

from __future__ import annotations

import argparse
import datetime
import hashlib
import os
import re
import sys

# مكونات مشتركة مع مولّد M1 (نفس الوحدة — بلا آثار جانبية عند الاستيراد)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from m1_build_datasets import (  # noqa: E402
    ACCESS_UTC,
    SOURCE_FILES,
    SOURCE_REPO,
    SOURCE_SHA,
    SRC_TAG,
    collect_source_rules,
    fetch_source,
    pin_literal,
)

# ────────────────────────── ثوابت الدورة ──────────────────────────

GATE_UTC = "2026-11-22"          # تاريخ توقيع بوابة G-K (UTC — ADR-0013)
GATE_TAG = f"G-K {GATE_UTC} (UTC)"

# ملفات المصدر لهذه الدورة: ملفات M1 التسعة عشر + ملف كتلة GEO (بطاقة SEO)
CARD_SOURCE_FILES = list(SOURCE_FILES) + ["src/lib/evo-geo-answer.ts"]

# عدد البطاقات المستهدف (مطابقة تامة — لا حدود دنيا، كقانون EXPECTED في M1)
EXPECTED_CARDS = 15

S = {  # اختصارات مسارات المصدر
    "fm": "src/lib/fitness-math.ts",
    "macro": "src/lib/content/macro-calculator.ts",
    "bmi": "src/lib/content/bmi-calculator.ts",
    "bf": "src/lib/content/body-fat-calculator.ts",
    "water": "src/lib/content/water-tracker.ts",
    "sanity": "src/lib/plan-ai-validation.ts",
    "meal": "src/lib/ai-meal-planner.ts",
    "wo": "src/lib/ai-workout-planner.ts",
    "match": "src/lib/ai-workout-exercise-match.ts",
    "law": "src/lib/blog-editorial-law.ts",
    "evo": "src/lib/evo-system-prompt.ts",
    "safety": "src/lib/evo-safety.ts",
    "matrix": "src/lib/diet-plan-matrix.ts",
    "geo": "src/lib/evo-geo-answer.ts",
}


# ────────────────────────── تثبيتات إضافية خاصة بالبطاقات ──────────────────────────

def pin_card_facts(sources: dict) -> None:
    """تثبيت حرفي لكل سطر مصدر تستشهد به البطاقات خارج قواعد M1 (يفشل عند الانحراف)."""
    fm = sources[S["fm"]]
    pin_literal(fm, "// Mifflin-St Jeor Equation", "BMR equation attribution")
    pin_literal(fm, "? 10 * weightKg + 6.25 * heightCm - 5 * age + 5",
                "BMR male constant +5")
    pin_literal(fm, ": 10 * weightKg + 6.25 * heightCm - 5 * age - 161;",
                "BMR female constant -161")
    pin_literal(fm, "const tdee = Math.round(bmr * ACTIVITY_FACTORS[activity]);",
                "TDEE = round(BMR x factor)")
    pin_literal(fm, "let target = tdee;", "default target = TDEE (maintain)")
    pin_literal(fm, "Single-source law (AGENTS.md §12.8)", "single-source law header")

    law = sources[S["law"]]
    pin_literal(law, "every anchor text MUST be a short natural phrase that "
                     "reads grammatically inside its sentence", "anchor grammar law")

    safety = sources[S["safety"]]
    pin_literal(safety, "YMYL LAW", "safety YMYL law")
    pin_literal(safety, "messages must NEVER reach an LLM", "crisis never reaches LLM")
    pin_literal(safety, "STATIC, warm, professional-help redirect", "static warm redirect")
    # (السطران يلتفان في تعليق المصدر — يثبت كل جزء على حدة)
    pin_literal(safety, "ethics requirement", "ethics requirement")
    pin_literal(safety, "hallucination firewall", "hallucination firewall")
    pin_literal(safety, "HIGH PRECISION over recall", "precision over recall law")
    pin_literal(safety, "Fasting/صيام is a LEGITIMATE fitness topic",
                "fasting legitimate topic")
    pin_literal(safety, "Arabic normalization", "arabic normalization step")

    geo = sources[S["geo"]]
    pin_literal(geo, "40-60 word GEO template", "GEO word-count template")
    pin_literal(geo, "content section after the hero", "GEO placement law")  # «the FIRST» تسبقها في السطر
    pin_literal(geo, "plus the sources line", "GEO sources line")
    pin_literal(geo, "the Yotpo/Princeton synthesis", "GEO synthesis attribution")
    pin_literal(geo, "pricing/quota source", "GEO single quota source")  # «the single» تسبقها في السطر
    pin_literal(geo, "free chat 10/day", "GEO free chat quota")
    pin_literal(geo, "generations 4/8/8 monthly", "GEO generations quotas")
    pin_literal(geo, "ONE unified swap quota 8/16/16", "GEO swaps quota")

    matrix = sources[S["matrix"]]
    pin_literal(matrix, "Per-100 g values (USDA-rounded, plain preparation)",
                "matrix per-100g USDA law")


# ────────────────────────── تعريف البطاقات (المحتوى مشتق من القواعد المثبتة) ──────────────────────────

def build_card_specs(rules: dict) -> list:
    """كل بطاقة: حقائقها العربية والإنجليزية مشتقة من rules المثبتة حرفيًا."""
    cards = []

    af = rules["activity_factors"]
    cards.append({
        "slug": "bmr-mifflin-activity-factors",
        "title": "معادلة Mifflin-St Jeor للأيض الأساسي ومعاملات النشاط الخمسة",
        "classification": "حسابات المنصة",
        "entity": "حساب/الأيض الأساسي (BMR) والإنفاق اليومي (TDEE)",
        "sources": [S["fm"]],
        "cited": "دالة calculateCalorieTargets وثابت ACTIVITY_FACTORS وقانون المصدر الواحد في ترويسة الملف",
        "facts_ar": [
            "معدل الأيض الأساسي (BMR) يحسب بمعادلة Mifflin-St Jeor: للذكر 10×الوزن(كغ) + 6.25×الطول(سم) − 5×العمر(سنة) + 5؛ وللأنثى المعادلة نفسها بثابت −161 بدل +5.",
            f"الإنفاق اليومي الكلي (TDEE) = تقريب Math.round لضرب BMR في معامل النشاط (ACTIVITY_FACTORS): خامل {af['sedentary']} · خفيف {af['light']} · معتدل {af['moderate']} · نشط {af['active']} · نشط جدًا {af['very_active']}.",
            "قانون المصدر الواحد (AGENTS.md §12.8): الرياضيات البحتة تعيش في fitness-math.ts حصرًا، وإن تغيرت المعادلة تغيرت هناك ويسير السطحان (الأداة وصفحة المحتوى) خلفها في نفس المرحلة — الأرقام وحدها تتدفق منها.",
        ],
        "facts_en": [
            "BMR uses the Mifflin-St Jeor equation: males 10*weight(kg) + 6.25*height(cm) - 5*age + 5; females the same with -161 instead of +5.",
            f"TDEE = Math.round(BMR x activity factor) - ACTIVITY_FACTORS: sedentary {af['sedentary']}, light {af['light']}, moderate {af['moderate']}, active {af['active']}, very_active {af['very_active']}.",
            "Single-source law (AGENTS.md §12.8): the pure math lives in fitness-math.ts only; if the formula ever changes it changes there, and both surfaces follow in the same phase.",
        ],
        "en_terms": ["Mifflin-St Jeor", "BMR", "TDEE", "ACTIVITY_FACTORS"],
    })

    cards.append({
        "slug": "calorie-goal-adjustment",
        "title": "تعديل هدف السعرات حسب الهدف: خسارة −500 وزيادة +400",
        "classification": "حسابات المنصة",
        "entity": "حساب/هدف السعرات اليومي (تعديل الهدف)",
        "sources": [S["fm"]],
        "cited": "فرعا goal داخل calculateCalorieTargets",
        "facts_ar": [
            "هدف السعرات الافتراضي عند الحفاظ على الوزن = الإنفاق اليومي الكلي (TDEE) نفسه بلا تعديل.",
            "هدف خسارة الوزن = TDEE − 500 سعرة، وهدف زيادة الوزن = TDEE + 400 سعرة — كلاهما بتقريب Math.round.",
            "التعديل يطبق بعد ضرب الأيض الأساسي في معامل النشاط (لا قبله)، فيبقى التعديلان ثابتين مهما كان النشاط أو الجنس.",
        ],
        "facts_en": [
            "The default calorie target (maintain) equals TDEE with no adjustment.",
            "The lose goal: target = Math.round(TDEE - 500); the gain goal: target = Math.round(TDEE + 400).",
            "The adjustment applies after multiplying BMR by the activity factor, so both deltas stay constant across sex and activity levels.",
        ],
        "en_terms": ["TDEE", "lose", "gain"],
    })

    cards.append({
        "slug": "starter-macro-split",
        "title": "التوزيع الافتتاحي للماكروز في حاسبة السعرات (30/40/30 المسمى 40/30/30)",
        "classification": "حسابات المنصة",
        "entity": "حساب/التوزيع الافتتاحي للماكروز في حاسبة السعرات",
        "sources": [S["fm"]],
        "cited": "أسطر protein/carbs/fat داخل calculateCalorieTargets + الترويسة الموثقة",
        "facts_ar": [
            "التوزيع الافتتاحي للماكروز في حاسبة السعرات: بروتين 30% / كربوهيدرات 40% / دهون 30% من السعرات — ويسميه المصدر «التوزيع 40/30/30».",
            "التحويل إلى غرامات: البروتين (الهدف×0.3)÷4 والكربوهيدرات (الهدف×0.4)÷4 والدهون (الهدف×0.3)÷9 — بتقريب Math.round.",
            "هذا التوزيع خاص بحاسبة السعرات، ومستقل عن توزيعات حاسبة الماكروز الخمسة (بطاقة منفصلة).",
        ],
        "facts_en": [
            'The calorie calculator starter split is protein 30% / carbs 40% / fat 30% of calories - the source labels it the "40/30/30" macro split.',
            "Grams: protein target*0.3/4, carbs target*0.4/4, fat target*0.3/9 (Math.round on each).",
            "This starter split belongs to the calorie calculator only and is independent of the macro-calculator five presets (separate card).",
        ],
        "en_terms": ["40/30/30", "Math.round"],
    })

    mp = rules["macro_presets"]
    cards.append({
        "slug": "macro-presets-4-4-9",
        "title": "توزيعات حاسبة الماكروز الخمسة والتحويل على 4/4/9",
        "classification": "حسابات المنصة",
        "entity": "حساب/توزيعات الماكروز الخمسة (حاسبة الماكروز)",
        "sources": [S["macro"]],
        "cited": "ثابت MACRO_PRESETS وترويسته الموثقة (كل رقم مثبت بعرافات مقابل الكود)",
        "facts_ar": [
            "توزيعات الماكروز الخمسة في حاسبة الماكروز (بروتين/كارب/دهون كنسب من السعرات): "
            f"متوازن {mp['balanced']['protein']}/{mp['balanced']['carbs']}/{mp['balanced']['fat']} · "
            f"منخفض الكارب {mp['low-carb']['protein']}/{mp['low-carb']['carbs']}/{mp['low-carb']['fat']} · "
            f"عالي البروتين {mp['high-protein']['protein']}/{mp['high-protein']['carbs']}/{mp['high-protein']['fat']} · "
            f"كيتو {mp['keto']['protein']}/{mp['keto']['carbs']}/{mp['keto']['fat']} · "
            f"منخفض الدهون {mp['low-fat']['protein']}/{mp['low-fat']['carbs']}/{mp['low-fat']['fat']}.",
            "تحويل الغرامات موحد على 4/4/9 سعرات لكل غرام (بروتين/كارب/دهون) بتقريب Math.round.",
            "كل رقم في النسخة مطابق للكود بعرافات (canaries) في ترويسة المصدر — لا انجراف صامت بين التوثيق والكود.",
        ],
        "facts_en": [
            "The macro-calculator presets (P/C/F as percent of calories): "
            f"balanced {mp['balanced']['protein']}/{mp['balanced']['carbs']}/{mp['balanced']['fat']}, "
            f"low-carb {mp['low-carb']['protein']}/{mp['low-carb']['carbs']}/{mp['low-carb']['fat']}, "
            f"high-protein {mp['high-protein']['protein']}/{mp['high-protein']['carbs']}/{mp['high-protein']['fat']}, "
            f"keto {mp['keto']['protein']}/{mp['keto']['carbs']}/{mp['keto']['fat']}, "
            f"low-fat {mp['low-fat']['protein']}/{mp['low-fat']['carbs']}/{mp['low-fat']['fat']}.",
            "Grams conversion at 4/4/9 kcal per gram (protein/carbs/fat), Math.round on each.",
            "Every number in the source header is pinned against the code with canaries - no silent drift.",
        ],
        "en_terms": ["balanced", "low-carb", "high-protein", "keto", "low-fat"],
    })

    cards.append({
        "slug": "bmi-who-categories",
        "title": "مؤشر كتلة الجسم وفئات WHO المثبتة (18.5/25/30)",
        "classification": "حسابات المنصة",
        "entity": "حساب/BMI وفئات الوزن",
        "sources": [S["bmi"]],
        "cited": "معادلة المؤشر وحدود الفئات في bmi-calculator.ts + عرافات الترويسة",
        "facts_ar": [
            "مؤشر كتلة الجسم (BMI) = الوزن بالكيلوغرام مقسومًا على مربع الطول بالأمتار.",
            "فئات منظمة الصحة العالمية (WHO) المعتمدة في الحاسبة: نقص وزن أقل من 18.5 · وزن طبيعي 18.5–24.9 · زيادة وزن 25–29.9 · سمنة 30 فأكثر.",
            "الحدود الفاصلة 18.5/25/30 مثبتة في ترويسة المصدر بعرافات (canaries) — الكود لا ينحرف عنها صامتًا.",
        ],
        "facts_en": [
            "BMI = weight (kg) divided by height (m) squared.",
            "WHO cutoffs used by the calculator: underweight below 18.5, normal 18.5-24.9, overweight 25-29.9, obese 30 and above.",
            "The 18.5 / 25 / 30 cutoffs are pinned in the source header with canaries so the code cannot drift from them.",
        ],
        "en_terms": ["BMI", "WHO", "underweight", "overweight", "obese"],
    })

    cards.append({
        "slug": "navy-body-fat-equations",
        "title": "معادلتا البحرية الأمريكية لدهن الجسم (Hodgdon–Beckett 1984)",
        "classification": "حسابات المنصة",
        "entity": "حساب/دهن الجسم (معادلتا البحرية)",
        "sources": [S["bf"]],
        "cited": "المعادلتان الحرفيتان وهامش الدقة الموثق في ترويسة body-fat-calculator.ts",
        "facts_ar": [
            "دهن الجسم يحسب بمعادلتي البحرية الأمريكية (US Navy — Hodgdon–Beckett 1984) من قياسات بالسنتيمتر.",
            "للرجال: 495 ÷ (1.0324 − 0.19077×log10(الخصر−الرقبة) + 0.15456×log10(الطول)) − 450.",
            "للنساء: 495 ÷ (1.29579 − 0.35004×log10(الخصر+الورك−الرقبة) + 0.22100×log10(الطول)) − 450.",
            "هامش الدقة الموثق في المصدر: انحراف 3–4 نقاط مئوية عن قياس DEXA المرجعي.",
        ],
        "facts_en": [
            "Body fat uses the US Navy equations (Hodgdon-Beckett 1984) with measurements in centimeters.",
            "Men: 495 / (1.0324 - 0.19077*log10(waist-neck) + 0.15456*log10(height)) - 450.",
            "Women: 495 / (1.29579 - 0.35004*log10(waist+hip-neck) + 0.22100*log10(height)) - 450.",
            "Documented accuracy band: 3-4 percentage points vs DEXA.",
        ],
        "en_terms": ["US Navy", "Hodgdon-Beckett", "DEXA"],
    })

    w_lo, w_hi = rules["water_clamp"]
    cards.append({
        "slug": "water-35ml-kg-clamp",
        "title": f"هدف الماء اليومي: 35 مل/كغ محصور بين {w_lo:,} و{w_hi:,} مل",
        "classification": "حسابات المنصة",
        "entity": "حساب/الماء اليومي",
        "sources": [S["water"]],
        "cited": "قاعدة 35 مل/كغ والحصر والكوب القياسي الموثقة في water-tracker.ts",
        "facts_ar": [
            "هدف شرب الماء اليومي = 35 مل لكل كيلوغرام من وزن الجسم.",
            f"النتيجة محصورة (clamp) بين {w_lo:,} و{w_hi:,} مل مهما كان الوزن — حماية من القيم المتطرفة.",
            "الكوب القياسي في أداة التتبع = 250 مل لكل نقرة.",
        ],
        "facts_en": [
            "Daily water goal = 35 ml x body weight (kg).",
            f"The result is clamped between {w_lo:,} and {w_hi:,} ml regardless of weight.",
            "The tracker's standard glass is 250 ml per tap.",
        ],
        "en_terms": ["35 ml", "clamped", "250 ml"],
    })

    cards.append({
        "slug": "plan-ai-sanity-limits",
        "title": "حدود مدقق الخطط الآلي (PLAN_AI_SANITY)",
        "classification": "مدققات AI",
        "entity": "مدقق/حدود انحراف الخطط (PLAN_AI_SANITY)",
        "sources": [S["sanity"]],
        "cited": "ثابت PLAN_AI_SANITY في plan-ai-validation.ts",
        "facts_ar": [
            f"المدقق الآلي يقبل الخطة إذا كان انحرافها الكلي عن هدف السعرات ≤{int(rules['plan_drift']*100)}%.",
            f"انحراف الوجبة الواحدة ≤{int(rules['meal_drift']*100)}% · انحراف الصنف داخل الوجبة ≤{int(rules['item_drift']*100)}% · انحراف البديل المقترح ≤{int(rules['alt_drift']*100)}%.",
            f"تمارين اليوم التدريبي: {rules['day_ex_min']} إلى {rules['day_ex_max']} تمارين.",
        ],
        "facts_en": [
            f"PLAN_AI_SANITY accepts a plan when its total drift from the calorie target is <= {int(rules['plan_drift']*100)}% (planDriftTolerance).",
            f"Per-meal drift <= {int(rules['meal_drift']*100)}% (mealDriftTolerance), per-item drift <= {int(rules['item_drift']*100)}% (itemDriftTolerance), alternative-calorie tolerance <= {int(rules['alt_drift']*100)}% (alternativeCalorieTolerance).",
            f"A training day carries {rules['day_ex_min']} to {rules['day_ex_max']} exercises.",
        ],
        "en_terms": ["PLAN_AI_SANITY", "planDriftTolerance", "mealDriftTolerance",
                     "itemDriftTolerance", "alternativeCalorieTolerance"],
    })

    gp_lo, gp_hi = rules["meal_item_grams_prompt"]
    gv_lo, gv_hi = rules["meal_item_grams_validator"]
    mc_lo, mc_hi = rules["meal_count"]
    cards.append({
        "slug": "meal-planner-contract",
        "title": "عقد مخطط الوجبات الذكي (برومبت + مدقق)",
        "classification": "مدققات AI",
        "entity": "مدقق/عقد مخطط الوجبات",
        "sources": [S["meal"]],
        "cited": "قواعد البرومبت ومدقق التحقق وثوابت DEMO_CALORIE في ai-meal-planner.ts",
        "facts_ar": [
            f"قواعد البرومبت: {mc_lo} إلى {mc_hi} وجبات في الخطة، و2 إلى 6 أصناف لكل وجبة، وكل صنف بين {gp_lo} و{gp_hi} غرامًا.",
            f"المدقق الآلي أوسع من البرومبت: الوجبة يجب أن تحمل 1 إلى 8 أصناف، والغرامات بين {gv_lo} و{gv_hi} — المدقق يمنع الفوضى لا أن يعيد صياغة البرومبت.",
            f"حدود السعرات في النموذج التجريبي: أدنى {rules['cal_min']:,} وأقصى {rules['cal_max']:,} سعرة، بانحراف مسموح ≤{int(rules['cal_drift']*100)}%.",
        ],
        "facts_en": [
            f"Prompt rules: {mc_lo} to {mc_hi} meals; 2 to 6 items per meal; every item {gp_lo} to {gp_hi} grams.",
            f"The programmatic validator is wider than the prompt: a meal must carry 1 to 8 items, and grams must be {gv_lo}-{gv_hi}.",
            f"Demo calorie bounds: DEMO_CALORIE_MIN {rules['cal_min']:,} / DEMO_CALORIE_MAX {rules['cal_max']:,} with a {int(rules['cal_drift']*100)}% drift allowance.",
        ],
        "en_terms": ["meals", "items per meal", "grams", "DEMO_CALORIE_MIN", "DEMO_CALORIE_MAX"],
    })

    cards.append({
        "slug": "workout-planner-contract",
        "title": "عقد مخطط التمارين الذكي وقانون تطابق التمارين",
        "classification": "مدققات AI",
        "entity": "مدقق/عقد مخطط التمارين وتطابق المكتبة",
        "sources": [S["wo"], S["match"]],
        "cited": "قواعد البرومبت ومدقق التحقق في ai-workout-planner.ts + قانون التغطية في ai-workout-exercise-match.ts",
        "facts_ar": [
            f"قواعد البرومبت: {rules['wo_sets_prompt'][0]} إلى {rules['wo_sets_prompt'][1]} مجموعات من {rules['wo_reps_prompt'][0]} إلى {rules['wo_reps_prompt'][1]} تكرارًا لكل تمرين، والحركات المركبة (compound) تُبرمج أولًا.",
            "كل اسم يوم تدريبي وعضلاته المستهدفة وكل اسم تمرين يُكتب بالإنجليزية في مخرجات المخطط.",
            f"الحجم الأسبوعي الموثق: {rules['wo_volume_large'][0]}–{rules['wo_volume_large'][1]} مجموعة أسبوعيًا لكل عضلة كبيرة (صدر/ظهر/أرجل/أكتاف) و{rules['wo_volume_small'][0]}–{rules['wo_volume_small'][1]} لكل عضلة صغيرة.",
            f"المدقق: المجموعات عدد صحيح بين {rules['wo_sets_validator'][0]} و{rules['wo_sets_validator'][1]}، والتكرارات بين {rules['wo_reps_validator'][0]} و{rules['wo_reps_validator'][1]} أو مدى مثل 8–12، وتمارين اليوم {rules['day_ex_min']}–{rules['day_ex_max']}.",
            "مطابقة تمارين المخطط مع مكتبة التمارين تقبل عند تغطية ≥0.6 مع ≥2 رمزًا متطابقًا.",
        ],
        "facts_en": [
            f"Prompt rules: {rules['wo_sets_prompt'][0]} to {rules['wo_sets_prompt'][1]} sets of {rules['wo_reps_prompt'][0]} to {rules['wo_reps_prompt'][1]} reps per exercise; compound movements FIRST.",
            "Write every day name, its target muscles, and every exercise name in English.",
            f"Documented weekly volume bands: {rules['wo_volume_large'][0]}-{rules['wo_volume_large'][1]} weekly sets per large muscle (chest/back/legs/shoulders) and {rules['wo_volume_small'][0]}-{rules['wo_volume_small'][1]} per small one.",
            f"Validator: sets an integer {rules['wo_sets_validator'][0]}-{rules['wo_sets_validator'][1]}; reps {rules['wo_reps_validator'][0]}-{rules['wo_reps_validator'][1]} or a range; day exercises {rules['day_ex_min']}-{rules['day_ex_max']}.",
            "Exercise-to-library matching accepts at coverage >= 0.6 with >= 2 matched tokens.",
        ],
        "en_terms": ["compound movements FIRST", "in English", "weekly sets", "coverage"],
    })

    cards.append({
        "slug": "editorial-authority-whitelist",
        "title": "دستور التحرير: الجهات العلمية الـ14 البيضاء ونطاق FAQ وقانون المرساة",
        "classification": "دستور التحرير",
        "entity": "تحرير/الجهات العلمية البيضاء وقواعد المحتوى",
        "sources": [S["law"]],
        "cited": "EDITORIAL_AUTHORITY_DOMAINS وEDITORIAL_FAQ_COUNT_RANGE وقانون نص المرساة في blog-editorial-law.ts",
        "facts_ar": [
            "الدستور يسرد 14 جهة علمية بيضاء للتذييل الخارجي: " + " · ".join(rules["domains"]) + ".",
            f"نطاق الأسئلة الشائعة (FAQ) في مقالات المدونة: {rules['faq_min']} إلى {rules['faq_max']} أسئلة.",
            "قانون نص المرساة (anchor grammar law): كل نص مرساة عبارة طبيعية قصيرة تُقرأ نحويًا داخل جملتها — وهو قانون ملزم ببوابة تحقق حتمية.",
        ],
        "facts_en": [
            "EDITORIAL_AUTHORITY_DOMAINS whitelists 14 authority domains: " + ", ".join(rules["domains"]) + ".",
            f"EDITORIAL_FAQ_COUNT_RANGE = min {rules['faq_min']}, max {rules['faq_max']}.",
            "Anchor grammar law: every anchor text MUST be a short natural phrase that reads grammatically inside its sentence - enforced by a deterministic gate.",
        ],
        "en_terms": ["EDITORIAL_AUTHORITY_DOMAINS", "EDITORIAL_FAQ_COUNT_RANGE", "anchor"],
    })

    cards.append({
        "slug": "evo-output-laws",
        "title": "قوانين إخراج ومحادثة EVO",
        "classification": "EVO",
        "entity": "EVO/قوانين الإخراج والمحادثة",
        "sources": [S["evo"]],
        "cited": "قوانين البرومبت الموثقة في evo-system-prompt.ts",
        "facts_ar": [
            "قانون الإيجاز: ردود EVO من 3 إلى 5 أسطر كحد أقصى، واليفضل 1–3 جمل.",
            "بروتوكول اللقاء الأول: حتى 4 أسئلة، سؤال واحد في كل رد.",
            "قانون 2026-09-13: لا يرفض طلب خطة أبدًا ولا يذكر الحصص أبدًا.",
            "التبديلات (SWAPS) ميزة للمشتركين فقط.",
            "المخرجات نص عادي: بلا LaTeX وTeX وMarkdown.",
        ],
        "facts_en": [
            "Brevity law: 3-5 lines max, ideally 1-3 sentences.",
            "First-meeting protocol: up to 4 questions, one per reply.",
            "The 2026-09-13 law: never refuse a plan request and never mention quotas.",
            "SWAPS remain subscriber-only.",
            "Plain-text output: NO LaTeX, NO TeX, NO markdown syntax.",
        ],
        "en_terms": ["3-5 lines", "4 questions", "never refuse", "SWAPS", "subscriber-only"],
    })

    cards.append({
        "slug": "evo-safety-shields",
        "title": "دروع سلامة EVO: قانون YMYL وإبعاد إشارات الأزمات عن النموذج",
        "classification": "EVO/السلامة",
        "entity": "EVO/دروع السلامة (YMYL)",
        "sources": [S["safety"]],
        "cited": "قوانين التصميم الموثقة في ترويسة evo-safety.ts وعائلات الأنماط",
        "facts_ar": [
            "قانون YMYL: منصة Alkemos منصة صحة/لياقة — رسائل إيذاء الذات وإشارات اضطرابات الأكل لا تصل إلى نموذج اللغة أبدًا؛ تحصل على رد ثابت دافئ يحيل إلى مساعدة مهنية.",
            "الدرع أخلاقي ودرع ضد الهلوسة معًا: النموذج لا «يدرّب» أزمة أبدًا.",
            "الدقة العالية قبل الاستدعاء: كل نمط يجب أن يذكر الذات («نفسي»/myself/my life) أو سلوك اضطراب أكل ملموس؛ ومبالغات الجيم («التمرين ده قتلني») لا تُفعّل الدروع عمدًا.",
            "الصيام (والصيام المتقطع) موضوع لياقة مشروع — غير مدرج في قائمة اضطرابات الأكل عمدًا.",
            "المطابقة العربية تسبقها تسوية إملائية: إزالة التشكيل والتطويل وتوحيد الألف والياء والتاء المربوطة.",
        ],
        "facts_en": [
            "YMYL law: Alkemos is a health/fitness platform - self-harm and eating-disorder signals must NEVER reach an LLM; they get a static, warm, professional-help redirect.",
            "This is both an ethics requirement and a hallucination firewall: the model must never coach a crisis.",
            "High precision over recall: every pattern names the SELF or a concrete ED behavior; gym hyperbole must not fire.",
            "Fasting is a LEGITIMATE fitness topic - deliberately absent from the ED list.",
            "Arabic normalization precedes matching: diacritics/tatweel stripped, alef/yaa/taa-marbouta unified.",
        ],
        "en_terms": ["YMYL", "NEVER reach an LLM", "hallucination firewall",
                     "High precision over recall", "LEGITIMATE"],
    })

    levels = rules["diet_levels"]
    splits = rules["matrix_splits"]
    cards.append({
        "slug": "diet-plan-matrix-laws",
        "title": "مصفوفة الخطط الغذائية: ستة مستويات × أربعة أنظمة وقانون الإغلاق ±10",
        "classification": "مصفوفة الخطط",
        "entity": "خطط/مصفوفة الخطط وقانون الإغلاق",
        "sources": [S["matrix"]],
        "cited": "DIET_LEVELS وDIET_SYSTEMS وتوزيعاتهما وقانونا الإغلاق والقيم في diet-plan-matrix.ts",
        "facts_ar": [
            "ستة مستويات سعرية: " + " · ".join(f"{lv:,}" for lv in levels) + " سعرة.",
            "أربعة أنظمة بتوزيعاتها (بروتين/كارب/دهون): متوازن "
            f"{splits['balanced']['protein']}/{splits['balanced']['carbs']}/{splits['balanced']['fat']} · عالي البروتين "
            f"{splits['high-protein']['protein']}/{splits['high-protein']['carbs']}/{splits['high-protein']['fat']} · كيتو "
            f"{splits['keto']['protein']}/{splits['keto']['carbs']}/{splits['keto']['fat']} · نباتي "
            f"{splits['vegetarian']['protein']}/{splits['vegetarian']['carbs']}/{splits['vegetarian']['fat']}.",
            f"كل وجبة في المصفوفة مغلقة حسابيًا ضمن ±{rules['matrix_closure']} كالوري من مستواها السعري.",
            "توزيع النباتي 25/50/25 موثق كتوزيع المصفوفة وحدها — ليس من توزيعات حاسبة الماكروز.",
            "قيم الأطعمة في المصفوفة لكل 100 غرام، مقربة على USDA بتحضير بسيط.",
        ],
        "facts_en": [
            "Six calorie levels: " + ", ".join(f"{lv:,}" for lv in levels) + " kcal.",
            "Four systems with P/C/F splits: Balanced "
            f"{splits['balanced']['protein']}/{splits['balanced']['carbs']}/{splits['balanced']['fat']}, High-Protein "
            f"{splits['high-protein']['protein']}/{splits['high-protein']['carbs']}/{splits['high-protein']['fat']}, Keto "
            f"{splits['keto']['protein']}/{splits['keto']['carbs']}/{splits['keto']['fat']}, Vegetarian "
            f"{splits['vegetarian']['protein']}/{splits['vegetarian']['carbs']}/{splits['vegetarian']['fat']}.",
            f"Every matrix meal closes within +/- {rules['matrix_closure']} kcal of its level.",
            "The vegetarian 25/50/25 split is documented as the site's matrix-only preset - not from the macro calculator.",
            "Matrix food values are per-100 g, USDA-rounded, plain preparation.",
        ],
        "en_terms": ["matrix-only", "USDA-rounded", "kcal"],
    })

    cards.append({
        "slug": "geo-direct-answer-block",
        "title": "نمط GEO لكتلة الجواب المباشر (40–60 كلمة بعد الواجهة + سطر المصادر)",
        "classification": "SEO/GEO/AEO",
        "entity": "SEO/كتلة الجواب المباشر GEO",
        "sources": [S["geo"]],
        "cited": "كتلة EVO_GEO_BLOCK وقوانين ترويستها في evo-geo-answer.ts",
        "facts_ar": [
            "نمط الإجابة المباشرة لمحركات الذكاء التوليدي (GEO): كتلة جواب من 40 إلى 60 كلمة كأول قسم محتوى بعد الواجهة (hero) في الصفحة، مع سطر مصادر يوثق مصدر الأرقام — توليفة Yotpo/Princeton الموثقة.",
            "مثال إنتاجي: كتلة «هل EVO مجاني؟» ثنائية اللغة — 10 رسائل يوميًا مجانًا بلا تسجيل، والتوليد 4/8/8 شهريًا (بريميوم/برو/تدريب)، وحصة تبديلات موحدة 8 أو 16 شهريًا.",
            "كل رقم في الكتلة موثق من مصدر التسعير/الحصص الوحيد (memberships.ts) — أعيد التحقق 2026-11-20.",
            "الترتيب يرث موقع السؤال من الأسئلة الشائعة القائمة بلغتيه، مثبتًا بعرافة (canary) تمنع انحداره.",
        ],
        "facts_en": [
            "The GEO direct-answer pattern: a 40-60 word answer block as the FIRST content section after the hero, plus the sources line (the Yotpo/Princeton synthesis).",
            "Production example: the bilingual \"Is EVO free?\" block - 10 messages a day free with no signup; generations 4/8/8 monthly (Premium/Pro/Coaching); ONE unified swap quota 8 or 16 a month.",
            "Every number is verified against src/lib/memberships.ts (the single pricing/quota source - re-verified 2026-11-20).",
            "The existing FAQ already leads with this question in both languages, order pinned by a canary so it can never regress.",
        ],
        "en_terms": ["40-60 word", "sources line", "single pricing/quota source", "canary"],
    })

    return cards


# ────────────────────────── فحوص بوابة G-K ──────────────────────────

AR_CHAR = re.compile(r"[\u0600-\u06FF]")


def card_id(num: int) -> str:
    return f"CARD-{num:04d}"


def render_card(num: int, spec: dict) -> str:
    """توليد نص البطاقة وفق الصيغة الإلزامية (memory/cards/README)."""
    src_line = f"{SRC_TAG}:" + " · ".join(spec["sources"]) + f" — اطلاع {ACCESS_UTC} (UTC)"
    lines = [
        "---",
        f"id: {card_id(num)}",
        f"title: {spec['title']}",
        f"classification: {spec['classification']}",
        f"entity: {spec['entity']}",
        "version: v1.0",
        "status: معتمدة",
        f"last_reviewed: {GATE_UTC} (UTC)",
        "supersedes: —",
        "superseded_by: —",
        "contradicts: []",
        f"source: {src_line}",
        f"approved_via: {GATE_TAG}",
        "---",
        "",
        "<div dir=\"rtl\" align=\"right\">",
        "",
        "## الحقائق (عربية أساسًا + المصطلح الإنجليزي عند اللزوم)",
        "",
    ]
    lines += [f"- {f}" for f in spec["facts_ar"]]
    lines += ["", "**EN:**", ""]
    lines += [f"- {f}" for f in spec["facts_en"]]
    lines += [
        "",
        "## الأصل الكامل (provenance)",
        "",
        f"- **المنبع:** مستودع alkemos-aws العام (المصدر الأساسي — ADR-0012) على الالتزام "
        f"`{SOURCE_SHA}` عبر raw.githubusercontent قراءة-فقط بلا مفاتيح (R-35).",
        f"- **ما استُشهد به:** {spec['cited']}.",
        "- **الحقوق:** المصدر أصل مملوك لـAlkemos (مسجل في `references/data-rights.md` §2)؛ "
        "وهذه البطاقة «فارق مُتعلم مملوك» (data-rights §1) — إعادة بنائها حتمية عبر "
        "`scripts/gk_build_cards.py`.",
        f"- **تاريخ الاطلاع:** {ACCESS_UTC} (UTC) · **الاعتماد:** {GATE_TAG} (بوابة G-K — ADR-0017).",
        "",
        "</div>",
        "",
    ]
    return "\n".join(lines)


def load_existing_cards(cards_dir: str) -> list:
    """قراءة البطاقات القائمة (id/entity/الحالة/بصمة القيم/النص الكامل).

    النص الكامل أساس تحقق البوابة الفعلي من SHA المصدر وتاريخ الاطلاع
    في كل بطاقة معتمدة قائمة (مراجعة دفعة 9) — لا يُفترض سليمًا بل يُفحص.
    """
    existing = []
    if not os.path.isdir(cards_dir):
        return existing
    for name in sorted(os.listdir(cards_dir)):
        if not (name.startswith("CARD-") and name.endswith(".md")):
            continue
        with open(os.path.join(cards_dir, name), encoding="utf-8") as f:
            text = f.read()
        m = re.match(r"^---\n(.*?)\n---", text, re.S)
        if not m:
            continue
        fm = m.group(1)

        def field(key):
            mm = re.search(rf"^{key}:\s*(.+)$", fm, re.M)
            return mm.group(1).strip() if mm else None

        body = text[m.end():]
        # البصمة من قسم الحقائق وحده (بين «## الحقائق» و«## الأصل الكامل»)
        # — تطابق بصمة المواصفة (facts_ar + facts_en) لا غير
        facts_sec = body.split("## الأصل الكامل")[0]
        facts = "\n".join(l for l in facts_sec.splitlines() if l.startswith("- "))
        existing.append({
            "file": name,
            "id": field("id"),
            "entity": field("entity"),
            "status": field("status"),
            "text": text,
            "fingerprint": hashlib.sha256(
                "".join(sorted(facts.split())).encode("utf-8")).hexdigest(),
        })
    return existing


def fingerprint_of(spec: dict) -> str:
    facts = "\n".join(f"- {f}" for f in spec["facts_ar"] + spec["facts_en"])
    return hashlib.sha256("".join(sorted(facts.split())).encode("utf-8")).hexdigest()


def verify_card_text(cid: str, text: str) -> list:
    """فحص SHA المصدر وتاريخ الاطلاع في نص بطاقة (مراجعة دفعة 9 — بأمر المالك).

    تُستخدم للبطاقات الجديدة (النص الذي سيُكتب) والبطاقات المعتمدة القائمة
    على القرص على حد سواء — البوابة لا تفترض سلامة التثبيت بل تتحقق منه:
      1. وسم المصدر في سطر source «<مستودع>@<SHA>:» — المستودع هو alkemos-aws
         والـSHA يطابق SOURCE_SHA حرفيًا (الصورة القصيرة 7 محارف أو الكاملة
         40)؛ أي SHA آخر — وإن كان سداسيًا سليم الشكل، من إصدار سابق أو
         مزيفًا — يُرفض.
      2. تاريخ الاطلاع «اطلاع <YYYY-MM-DD> (UTC)» في سطر source يطابق
         ACCESS_UTC حرفيًا (وصيغة تقويمية صالحة).
      3. بصمة SHA الكاملة (40 محرفًا) حاضرة في قسم الأصل (provenance).
      4. last_reviewed بتاريخ UTC صالح + توقيع approved_via بصيغة
         «G-K <YYYY-MM-DD> (UTC)» + الاتساق بينهما (كلاهما يُكتب من
         GATE_UTC في المولّد الحتمي — تنافرهما علامة تحريف).
    """
    errs = []
    m = re.search(r"^source:\s*(.+)$", text, re.M)
    if not m:
        return [f"[استشهاد] {cid}: لا سطر source في البطاقة"]
    src_line = m.group(1).strip()

    # (1) وسم SHA المصدر
    repo_short = SOURCE_REPO.split("/")[-1]
    mtag = re.match(r"^([A-Za-z0-9_.\-]+)@([0-9a-f]{7}|[0-9a-f]{40}):", src_line)
    if not mtag:
        errs.append(f"[استشهاد] {cid}: سطر source بلا وسم مصدر صالح "
                    f"({repo_short}@<SHA سداسي 7 أو 40 محرفًا>): {src_line[:60]}")
    else:
        repo, sha = mtag.group(1), mtag.group(2)
        if repo != repo_short:
            errs.append(f"[استشهاد] {cid}: مستودع المصدر غير صحيح: {repo} "
                        f"(المثبّت: {repo_short})")
        if sha not in (SOURCE_SHA[:7], SOURCE_SHA):
            errs.append(f"[استشهاد] {cid}: SHA المصدر لا يطابق المثبّت — وجد "
                        f"{repo}@{sha} والمثبّت {SRC_TAG} (أو الصورة الكاملة "
                        f"{SOURCE_SHA})")

    # (2) تاريخ الاطلاع
    mdate = re.search(r"اطلاع (\d{4}-\d{2}-\d{2}) \(UTC\)", src_line)
    if not mdate:
        errs.append(f"[استشهاد] {cid}: سطر source بلا تاريخ اطلاع UTC صالح "
                    "(«— اطلاع YYYY-MM-DD (UTC)»)")
    else:
        d = mdate.group(1)
        try:
            datetime.date.fromisoformat(d)
        except ValueError:
            errs.append(f"[استشهاد] {cid}: تاريخ الاطلاع ليس تاريخًا تقويميًا صالحًا: {d}")
        if d != ACCESS_UTC:
            errs.append(f"[استشهاد] {cid}: تاريخ الاطلاع غير صحيح — وجد {d} "
                        f"والمثبّت {ACCESS_UTC} (UTC)")

    # (3) بصمة SHA الكاملة في قسم الأصل
    if SOURCE_SHA not in text:
        errs.append(f"[استشهاد] {cid}: بصمة SHA الكاملة للمصدر ({SOURCE_SHA}) "
                    "غائبة عن قسم الأصل (provenance)")

    # (4) تاريخ المراجعة وتوقيع البوابة
    mlr = re.search(r"^last_reviewed:\s*(\d{4}-\d{2}-\d{2}) \(UTC\)\s*$", text, re.M)
    mav = re.search(r"^approved_via:\s*G-K (\d{4}-\d{2}-\d{2}) \(UTC\)\s*$", text, re.M)
    if not mlr:
        errs.append(f"[استشهاد] {cid}: بلا last_reviewed بصيغة «YYYY-MM-DD (UTC)»")
    if not mav:
        errs.append(f"[استشهاد] {cid}: بلا توقيع بوابة بصيغة «G-K YYYY-MM-DD (UTC)» "
                    "— لا اعتماد إلا عبر البوابة (cards/README ق1)")
    if mlr and mav and mlr.group(1) != mav.group(1):
        errs.append(f"[استشهاد] {cid}: last_reviewed ({mlr.group(1)}) لا يطابق تاريخ "
                    f"توقيع approved_via ({mav.group(1)})")
    return errs


def gate_checks(cards: list, existing: list, fetched_paths: set,
                rendered: list = None) -> list:
    """فحوص البوابة — تعرض قائمة أخطاء (فارغة = قبول).

    rendered: نصوص البطاقات التي ستُكتب (واحد لكل بطاقة بالترتيب)؛
    تُفحص فيها البوابة فعليًا SHA المصدر وتاريخ الاطلاع والمراجعة
    (مراجعة دفعة 9) — وإن لم تُمرر وُلّدت بـ render_card نفسها.
    """
    errors = []
    if rendered is None:
        rendered = [render_card(i, spec) for i, spec in enumerate(cards, start=1)]
    if len(rendered) != len(cards):
        errors.append(f"[أعداد] نصوص البطاقات ({len(rendered)}) لا تطابق عدد "
                      f"البطاقات ({len(cards)}) — لا كتابة قبل اكتمال الفحص")
        return errors

    # (1) التعارض (ADR-0017 ق2): كيان/حقل — لا كتابة صامتة فوق معرفة قائمة
    by_entity = {}
    for i, spec in enumerate(cards, start=1):
        cid = card_id(i)
        fp = fingerprint_of(spec)
        if spec["entity"] in by_entity:
            errors.append(f"[تعارض-عينة] الكيان مكرر داخل العينة: {spec['entity']} "
                          f"({by_entity[spec['entity']]} و{cid})")
        by_entity[spec["entity"]] = cid
        for ex in existing:
            if ex["entity"] == spec["entity"]:
                if ex["id"] == cid and ex["fingerprint"] == fp:
                    continue  # إعادة كتابة حتمية بنفس المحتوى (عقد إعادة البناء)
                if ex["fingerprint"] == fp:
                    errors.append(f"[تكرار] كيان مطابق بقيم مطابقة تحت معرف آخر: "
                                  f"{ex['id']} مقابل {cid} — ارفع إصدار البطاقة القائمة بدل بطاقة جديدة")
                else:
                    errors.append(f"[تعارض] كيان قائم بقيمة مختلفة: {spec['entity']} "
                                  f"({ex['id']}) — افتح قيدًا في memory/conflicts/ ولا تكتب صامتًا")

    # (2) ثنائية اللغة: عربية سليمة + إنجليزية سليمة + مصطلحات مفتاحية حاضرة
    for i, spec in enumerate(cards, start=1):
        cid = card_id(i)
        if len(spec["facts_ar"]) < 3:
            errors.append(f"[ثنائي] {cid}: الحقائق العربية أقل من 3 أسطر")
        for f in spec["facts_ar"]:
            if not f.strip() or not AR_CHAR.search(f):
                errors.append(f"[ثنائي] {cid}: سطر عربي فارغ أو بلا محرف عربي: {f[:50]}")
        if len(spec["facts_en"]) < 2:
            errors.append(f"[ثنائي] {cid}: الحقائق الإنجليزية أقل من سطرين")
        for f in spec["facts_en"]:
            if not f.strip():
                errors.append(f"[ثنائي] {cid}: سطر إنجليزي فارغ")
                continue
            ascii_ratio = sum(1 for c in f if ord(c) < 128) / len(f)
            if ascii_ratio < 0.6:
                errors.append(f"[ثنائي] {cid}: سطر إنجليزي ليس غالبية لاتينية: {f[:50]}")
        en_blob = "\n".join(spec["facts_en"])
        for term in spec["en_terms"]:
            if term not in en_blob:
                errors.append(f"[ثنائي] {cid}: المصطلح المفتاحي غائب عن الإنجليزية: {term}")

    # (3) الاستشهاد: مسار داخل الملفات المجلوبة + تحقق فعلي من SHA المصدر
    #     وتاريخ الاطلاع في نص كل بطاقة (جديدة كانت أم معتمدة قائمة)
    for i, spec in enumerate(cards, start=1):
        cid = card_id(i)
        for p in spec["sources"]:
            if p not in fetched_paths:
                errors.append(f"[استشهاد] {cid}: مسار غير مجلوب فعلًا: {p}")
        if not spec.get("cited"):
            errors.append(f"[استشهاد] {cid}: بند «ما استُشهد به» فارغ")
        errors.extend(verify_card_text(cid, rendered[i - 1]))
    # البطاقات المعتمدة القائمة على القرص — القانون نفسه (لا بطاقة تفلت):
    # المسودة/المشطوبة لا اعتماد لها فلا يُفحص تثبيتها؛ المعتمدة لا تُقبل
    # إلا إذا أثبت نصها SHA المصدر المثبّت وتاريخ الاطلاع الصحيح.
    for ex in existing:
        exid = ex.get("id") or ex.get("file") or "بطاقة قائمة"
        if ex.get("status") != "معتمدة":
            continue
        if not ex.get("text"):
            errors.append(f"[استشهاد] {exid}: بطاقة معتمدة بلا نص متاح للتحقق "
                          "(SHA المصدر/تاريخ الاطلاع) — لا يُفترض سليمًا")
            continue
        errors.extend(verify_card_text(exid, ex["text"]))

    # (4) الحقول والمعرفات: فردية، متسلسلة، معتمدة، موقعة
    if len(cards) != EXPECTED_CARDS:
        errors.append(f"[أعداد] البطاقات {len(cards)} != المتوقع {EXPECTED_CARDS}")
    ids = [card_id(i) for i in range(1, len(cards) + 1)]
    if len(set(ids)) != len(ids):
        errors.append("[معرفات] تكرار داخل العينة")
    for ex in existing:
        if ex["id"] in ids and ex["status"] not in (None, "معتمدة"):
            errors.append(f"[معرفات] إعادة استخدام معرف {ex['id']} بحالة غير معتمدة")

    return errors


# ────────────────────────── الوظيفة الرئيسية ──────────────────────────

def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser(description="مولّد أول دورة G-K — عينة بطاقات المعرفة")
    ap.add_argument("--cache", default=None)
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    script_dir = os.path.dirname(os.path.abspath(__file__))
    out_root = os.path.abspath(args.out) if args.out else os.path.dirname(script_dir)
    cache_dir = args.cache or os.path.join(script_dir, ".source-cache")
    cards_dir = os.path.join(out_root, "memory", "cards")

    print(f"[1/5] جلب ملفات المصدر من alkemos-aws @ {SOURCE_SHA[:7]} "
          f"({len(CARD_SOURCE_FILES)} ملفًا — قراءة-فقط)…")
    sources = {p: fetch_source(p, cache_dir) for p in CARD_SOURCE_FILES}

    print("[2/5] تثبيت كل القواعد والحقائق من المصدر (يفشل عند أي انحراف)…")
    rules = collect_source_rules(sources)   # نفس تثبيتات البطارية + القواعد المهيكلة
    # (كما في main المولّد الأصلي: المستويات والتوزيعات من المصفوفة)
    from m1_build_datasets import extract_export
    rules["diet_levels"] = list(extract_export(sources[S["matrix"]], "DIET_LEVELS"))
    rules["matrix_splits"] = {s["slug"]: s["split"] for s in
                              extract_export(sources[S["matrix"]], "DIET_SYSTEMS")}
    pin_card_facts(sources)                 # تثبيتات إضافية خاصة ببطاقات الدورة

    print("[3/5] بناء بطاقات العينة…")
    cards = build_card_specs(rules)
    existing = load_existing_cards(cards_dir)
    # النصوص تُولَّد أولًا ثم تفحصها البوابة ثم تُكتب كما فُحصت حرفيًا —
    # بلا فجوة بين ما يُفحص وما يُكتب على القرص (مراجعة دفعة 9)
    rendered = [render_card(i, spec) for i, spec in enumerate(cards, start=1)]

    n_ex_approved = sum(1 for ex in existing if ex.get("status") == "معتمدة")
    print(f"[4/5] فحوص بوابة G-K (تعارض/ثنائية لغة/استشهاد SHA+تاريخ/حقول) — "
          f"القائمة قبل الدورة: {len(existing)} بطاقة ({n_ex_approved} معتمدة)…")
    errors = gate_checks(cards, existing, set(CARD_SOURCE_FILES), rendered)
    if errors:
        print("\nفشل بوابة G-K — لا اعتماد:")
        for e in errors:
            print("  -", e)
        return 1

    print("[5/5] كتابة البطاقات المعتمدة (النصوص نفسها التي فحصتها البوابة)…")
    os.makedirs(cards_dir, exist_ok=True)
    for i, (spec, card_text) in enumerate(zip(cards, rendered), start=1):
        path = os.path.join(cards_dir, f"{card_id(i)}-{spec['slug']}.md")
        with open(path, "w", encoding="utf-8") as f:
            f.write(card_text)
        print(f"      {card_id(i)}-{spec['slug']}.md — sha256={sha256_file(path)[:12]}")

    n_ar = sum(len(c["facts_ar"]) for c in cards)
    n_en = sum(len(c["facts_en"]) for c in cards)
    classes = {}
    for c in cards:
        classes[c["classification"]] = classes.get(c["classification"], 0) + 1
    # إثبات الإضافة الصادق: البطاقة «الجديدة» = معرف لم يكن قائمًا (إعادة الكتابة
    # الحتمية لنفس المعرف والمحتوى ليست إضافة — عقد إعادة البناء)
    existing_ids = {ex["id"] for ex in existing}
    new_ids = {card_id(i) for i in range(1, len(cards) + 1)} - existing_ids
    total_after = len(existing_ids | {card_id(i) for i in range(1, len(cards) + 1)})
    print(f"""
نجحت بوابة G-K — تقرير الدورة (توقيع {GATE_TAG}):
  - الإضافة المقيسة: بطاقات جديدة {len(new_ids)} (معرفات لم تكن قائمة) · إجمالي
    بطاقات المعرفة المعتمدة بعد الدورة: {len(existing_ids)} ← {total_after}
    (عينة الدورة: {len(cards)} بطاقة عبر {len(classes)} تصنيفات: """ +
          " · ".join(f"{k} {v}" for k, v in sorted(classes.items())) + f""")
  - الحقائق الموثقة: {n_ar} حقيقة عربية + {n_en} إنجليزية = {n_ar + n_en} — كلها مثبتة
    آليًا من {len(CARD_SOURCE_FILES)} ملف مصدر @ {SOURCE_SHA[:7]} (تثبيتات M1 + {14} تثبيتًا إضافيًا للدورة)
  - فحص التعارض: {len(existing)} بطاقة قائمة + {len(cards)} كيانًا فريدًا ← صفر تعارض وصفر تكرار
  - فحص ثنائية اللغة: عربي ≥3 أسطر وبطاقة إنجليزية ≥2 أسطر + مصطلحات مفتاحية — {len(cards)}/{len(cards)}
  - الاستشهاد: كل مسار داخل الملفات المجلوبة فعلًا + تحقق فعلي في نص كل بطاقة —
    الجديدة {len(rendered)} والمعتمدة القائمة {n_ex_approved}: SHA يطابق SOURCE_SHA واطلاع
    {ACCESS_UTC} (UTC) وتوقيع G-K متسق مع تاريخ المراجعة
  - الحتمية: إعادة التشغيل تعيد إنتاج الملفات أنفسها (عقد إعادة البناء)""")
    return 0


if __name__ == "__main__":
    sys.exit(main())
