---
id: CARD-0005
title: مؤشر كتلة الجسم وفئات WHO المثبتة (18.5/25/30)
classification: حسابات المنصة
entity: حساب/BMI وفئات الوزن
version: v1.0
status: معتمدة
last_reviewed: 2026-11-22 (UTC)
supersedes: —
superseded_by: —
contradicts: []
source: alkemos-aws@32b6387:src/lib/content/bmi-calculator.ts — اطلاع 2026-11-22 (UTC)
approved_via: G-K 2026-11-22 (UTC)
---

<div dir="rtl" align="right">

## الحقائق (عربية أساسًا + المصطلح الإنجليزي عند اللزوم)

- مؤشر كتلة الجسم (BMI) = الوزن بالكيلوغرام مقسومًا على مربع الطول بالأمتار.
- فئات منظمة الصحة العالمية (WHO) المعتمدة في الحاسبة: نقص وزن أقل من 18.5 · وزن طبيعي 18.5–24.9 · زيادة وزن 25–29.9 · سمنة 30 فأكثر.
- الحدود الفاصلة 18.5/25/30 مثبتة في ترويسة المصدر بعرافات (canaries) — الكود لا ينحرف عنها صامتًا.

**EN:**

- BMI = weight (kg) divided by height (m) squared.
- WHO cutoffs used by the calculator: underweight below 18.5, normal 18.5-24.9, overweight 25-29.9, obese 30 and above.
- The 18.5 / 25 / 30 cutoffs are pinned in the source header with canaries so the code cannot drift from them.

## الأصل الكامل (provenance)

- **المنبع:** مستودع alkemos-aws العام (المصدر الأساسي — ADR-0012) على الالتزام `32b63874c2a2488b39bf449d83539fc930fe05a5` عبر raw.githubusercontent قراءة-فقط بلا مفاتيح (R-35).
- **ما استُشهد به:** معادلة المؤشر وحدود الفئات في bmi-calculator.ts + عرافات الترويسة.
- **الحقوق:** المصدر أصل مملوك لـAlkemos (مسجل في `references/data-rights.md` §2)؛ وهذه البطاقة «فارق مُتعلم مملوك» (data-rights §1) — إعادة بنائها حتمية عبر `scripts/gk_build_cards.py`.
- **تاريخ الاطلاع:** 2026-11-22 (UTC) · **الاعتماد:** G-K 2026-11-22 (UTC) (بوابة G-K — ADR-0017).

</div>
