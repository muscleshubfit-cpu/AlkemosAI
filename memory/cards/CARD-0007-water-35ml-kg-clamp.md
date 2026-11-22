---
id: CARD-0007
title: هدف الماء اليومي: 35 مل/كغ محصور بين 2,000 و4,500 مل
classification: حسابات المنصة
entity: حساب/الماء اليومي
version: v1.0
status: معتمدة
last_reviewed: 2026-11-22 (UTC)
supersedes: —
superseded_by: —
contradicts: []
source: alkemos-aws@32b6387:src/lib/content/water-tracker.ts — اطلاع 2026-11-22 (UTC)
approved_via: G-K 2026-11-22 (UTC)
---

<div dir="rtl" align="right">

## الحقائق (عربية أساسًا + المصطلح الإنجليزي عند اللزوم)

- هدف شرب الماء اليومي = 35 مل لكل كيلوغرام من وزن الجسم.
- النتيجة محصورة (clamp) بين 2,000 و4,500 مل مهما كان الوزن — حماية من القيم المتطرفة.
- الكوب القياسي في أداة التتبع = 250 مل لكل نقرة.

**EN:**

- Daily water goal = 35 ml x body weight (kg).
- The result is clamped between 2,000 and 4,500 ml regardless of weight.
- The tracker's standard glass is 250 ml per tap.

## الأصل الكامل (provenance)

- **المنبع:** مستودع alkemos-aws العام (المصدر الأساسي — ADR-0012) على الالتزام `32b63874c2a2488b39bf449d83539fc930fe05a5` عبر raw.githubusercontent قراءة-فقط بلا مفاتيح (R-35).
- **ما استُشهد به:** قاعدة 35 مل/كغ والحصر والكوب القياسي الموثقة في water-tracker.ts.
- **الحقوق:** المصدر أصل مملوك لـAlkemos (مسجل في `references/data-rights.md` §2)؛ وهذه البطاقة «فارق مُتعلم مملوك» (data-rights §1) — إعادة بنائها حتمية عبر `scripts/gk_build_cards.py`.
- **تاريخ الاطلاع:** 2026-11-22 (UTC) · **الاعتماد:** G-K 2026-11-22 (UTC) (بوابة G-K — ADR-0017).

</div>
