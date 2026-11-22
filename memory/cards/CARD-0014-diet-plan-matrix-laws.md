---
id: CARD-0014
title: مصفوفة الخطط الغذائية: ستة مستويات × أربعة أنظمة وقانون الإغلاق ±10
classification: مصفوفة الخطط
entity: خطط/مصفوفة الخطط وقانون الإغلاق
version: v1.0
status: معتمدة
last_reviewed: 2026-11-22 (UTC)
supersedes: —
superseded_by: —
contradicts: []
source: alkemos-aws@32b6387:src/lib/diet-plan-matrix.ts — اطلاع 2026-11-22 (UTC)
approved_via: G-K 2026-11-22 (UTC)
---

<div dir="rtl" align="right">

## الحقائق (عربية أساسًا + المصطلح الإنجليزي عند اللزوم)

- ستة مستويات سعرية: 1,200 · 1,500 · 1,800 · 2,000 · 2,500 · 3,000 سعرة.
- أربعة أنظمة بتوزيعاتها (بروتين/كارب/دهون): متوازن 30/40/30 · عالي البروتين 45/35/20 · كيتو 25/5/70 · نباتي 25/50/25.
- كل وجبة في المصفوفة مغلقة حسابيًا ضمن ±10 كالوري من مستواها السعري.
- توزيع النباتي 25/50/25 موثق كتوزيع المصفوفة وحدها — ليس من توزيعات حاسبة الماكروز.
- قيم الأطعمة في المصفوفة لكل 100 غرام، مقربة على USDA بتحضير بسيط.

**EN:**

- Six calorie levels: 1,200, 1,500, 1,800, 2,000, 2,500, 3,000 kcal.
- Four systems with P/C/F splits: Balanced 30/40/30, High-Protein 45/35/20, Keto 25/5/70, Vegetarian 25/50/25.
- Every matrix meal closes within +/- 10 kcal of its level.
- The vegetarian 25/50/25 split is documented as the site's matrix-only preset - not from the macro calculator.
- Matrix food values are per-100 g, USDA-rounded, plain preparation.

## الأصل الكامل (provenance)

- **المنبع:** مستودع alkemos-aws العام (المصدر الأساسي — ADR-0012) على الالتزام `32b63874c2a2488b39bf449d83539fc930fe05a5` عبر raw.githubusercontent قراءة-فقط بلا مفاتيح (R-35).
- **ما استُشهد به:** DIET_LEVELS وDIET_SYSTEMS وتوزيعاتهما وقانونا الإغلاق والقيم في diet-plan-matrix.ts.
- **الحقوق:** المصدر أصل مملوك لـAlkemos (مسجل في `references/data-rights.md` §2)؛ وهذه البطاقة «فارق مُتعلم مملوك» (data-rights §1) — إعادة بنائها حتمية عبر `scripts/gk_build_cards.py`.
- **تاريخ الاطلاع:** 2026-11-22 (UTC) · **الاعتماد:** G-K 2026-11-22 (UTC) (بوابة G-K — ADR-0017).

</div>
