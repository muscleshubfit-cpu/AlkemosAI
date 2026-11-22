---
id: CARD-0008
title: حدود مدقق الخطط الآلي (PLAN_AI_SANITY)
classification: مدققات AI
entity: مدقق/حدود انحراف الخطط (PLAN_AI_SANITY)
version: v1.0
status: معتمدة
last_reviewed: 2026-11-22 (UTC)
supersedes: —
superseded_by: —
contradicts: []
source: alkemos-aws@32b6387:src/lib/plan-ai-validation.ts — اطلاع 2026-11-22 (UTC)
approved_via: G-K 2026-11-22 (UTC)
---

<div dir="rtl" align="right">

## الحقائق (عربية أساسًا + المصطلح الإنجليزي عند اللزوم)

- المدقق الآلي يقبل الخطة إذا كان انحرافها الكلي عن هدف السعرات ≤25%.
- انحراف الوجبة الواحدة ≤20% · انحراف الصنف داخل الوجبة ≤15% · انحراف البديل المقترح ≤10%.
- تمارين اليوم التدريبي: 3 إلى 8 تمارين.

**EN:**

- PLAN_AI_SANITY accepts a plan when its total drift from the calorie target is <= 25% (planDriftTolerance).
- Per-meal drift <= 20% (mealDriftTolerance), per-item drift <= 15% (itemDriftTolerance), alternative-calorie tolerance <= 10% (alternativeCalorieTolerance).
- A training day carries 3 to 8 exercises.

## الأصل الكامل (provenance)

- **المنبع:** مستودع alkemos-aws العام (المصدر الأساسي — ADR-0012) على الالتزام `32b63874c2a2488b39bf449d83539fc930fe05a5` عبر raw.githubusercontent قراءة-فقط بلا مفاتيح (R-35).
- **ما استُشهد به:** ثابت PLAN_AI_SANITY في plan-ai-validation.ts.
- **الحقوق:** المصدر أصل مملوك لـAlkemos (مسجل في `references/data-rights.md` §2)؛ وهذه البطاقة «فارق مُتعلم مملوك» (data-rights §1) — إعادة بنائها حتمية عبر `scripts/gk_build_cards.py`.
- **تاريخ الاطلاع:** 2026-11-22 (UTC) · **الاعتماد:** G-K 2026-11-22 (UTC) (بوابة G-K — ADR-0017).

</div>
