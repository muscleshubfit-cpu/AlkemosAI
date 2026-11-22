---
id: CARD-0002
title: تعديل هدف السعرات حسب الهدف: خسارة −500 وزيادة +400
classification: حسابات المنصة
entity: حساب/هدف السعرات اليومي (تعديل الهدف)
version: v1.0
status: معتمدة
last_reviewed: 2026-11-22 (UTC)
supersedes: —
superseded_by: —
contradicts: []
source: alkemos-aws@32b6387:src/lib/fitness-math.ts — اطلاع 2026-11-22 (UTC)
approved_via: G-K 2026-11-22 (UTC)
---

<div dir="rtl" align="right">

## الحقائق (عربية أساسًا + المصطلح الإنجليزي عند اللزوم)

- هدف السعرات الافتراضي عند الحفاظ على الوزن = الإنفاق اليومي الكلي (TDEE) نفسه بلا تعديل.
- هدف خسارة الوزن = TDEE − 500 سعرة، وهدف زيادة الوزن = TDEE + 400 سعرة — كلاهما بتقريب Math.round.
- التعديل يطبق بعد ضرب الأيض الأساسي في معامل النشاط (لا قبله)، فيبقى التعديلان ثابتين مهما كان النشاط أو الجنس.

**EN:**

- The default calorie target (maintain) equals TDEE with no adjustment.
- The lose goal: target = Math.round(TDEE - 500); the gain goal: target = Math.round(TDEE + 400).
- The adjustment applies after multiplying BMR by the activity factor, so both deltas stay constant across sex and activity levels.

## الأصل الكامل (provenance)

- **المنبع:** مستودع alkemos-aws العام (المصدر الأساسي — ADR-0012) على الالتزام `32b63874c2a2488b39bf449d83539fc930fe05a5` عبر raw.githubusercontent قراءة-فقط بلا مفاتيح (R-35).
- **ما استُشهد به:** فرعا goal داخل calculateCalorieTargets.
- **الحقوق:** المصدر أصل مملوك لـAlkemos (مسجل في `references/data-rights.md` §2)؛ وهذه البطاقة «فارق مُتعلم مملوك» (data-rights §1) — إعادة بنائها حتمية عبر `scripts/gk_build_cards.py`.
- **تاريخ الاطلاع:** 2026-11-22 (UTC) · **الاعتماد:** G-K 2026-11-22 (UTC) (بوابة G-K — ADR-0017).

</div>
