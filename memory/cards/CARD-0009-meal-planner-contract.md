---
id: CARD-0009
title: عقد مخطط الوجبات الذكي (برومبت + مدقق)
classification: مدققات AI
entity: مدقق/عقد مخطط الوجبات
version: v1.0
status: معتمدة
last_reviewed: 2026-11-22 (UTC)
supersedes: —
superseded_by: —
contradicts: []
source: alkemos-aws@32b6387:src/lib/ai-meal-planner.ts — اطلاع 2026-11-22 (UTC)
approved_via: G-K 2026-11-22 (UTC)
---

<div dir="rtl" align="right">

## الحقائق (عربية أساسًا + المصطلح الإنجليزي عند اللزوم)

- قواعد البرومبت: 3 إلى 5 وجبات في الخطة، و2 إلى 6 أصناف لكل وجبة، وكل صنف بين 5 و600 غرامًا.
- المدقق الآلي أوسع من البرومبت: الوجبة يجب أن تحمل 1 إلى 8 أصناف، والغرامات بين 5 و900 — المدقق يمنع الفوضى لا أن يعيد صياغة البرومبت.
- حدود السعرات في النموذج التجريبي: أدنى 1,200 وأقصى 4,000 سعرة، بانحراف مسموح ≤20%.

**EN:**

- Prompt rules: 3 to 5 meals; 2 to 6 items per meal; every item 5 to 600 grams.
- The programmatic validator is wider than the prompt: a meal must carry 1 to 8 items, and grams must be 5-900.
- Demo calorie bounds: DEMO_CALORIE_MIN 1,200 / DEMO_CALORIE_MAX 4,000 with a 20% drift allowance.

## الأصل الكامل (provenance)

- **المنبع:** مستودع alkemos-aws العام (المصدر الأساسي — ADR-0012) على الالتزام `32b63874c2a2488b39bf449d83539fc930fe05a5` عبر raw.githubusercontent قراءة-فقط بلا مفاتيح (R-35).
- **ما استُشهد به:** قواعد البرومبت ومدقق التحقق وثوابت DEMO_CALORIE في ai-meal-planner.ts.
- **الحقوق:** المصدر أصل مملوك لـAlkemos (مسجل في `references/data-rights.md` §2)؛ وهذه البطاقة «فارق مُتعلم مملوك» (data-rights §1) — إعادة بنائها حتمية عبر `scripts/gk_build_cards.py`.
- **تاريخ الاطلاع:** 2026-11-22 (UTC) · **الاعتماد:** G-K 2026-11-22 (UTC) (بوابة G-K — ADR-0017).

</div>
