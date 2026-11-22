---
id: CARD-0003
title: التوزيع الافتتاحي للماكروز في حاسبة السعرات (30/40/30 المسمى 40/30/30)
classification: حسابات المنصة
entity: حساب/التوزيع الافتتاحي للماكروز في حاسبة السعرات
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

- التوزيع الافتتاحي للماكروز في حاسبة السعرات: بروتين 30% / كربوهيدرات 40% / دهون 30% من السعرات — ويسميه المصدر «التوزيع 40/30/30».
- التحويل إلى غرامات: البروتين (الهدف×0.3)÷4 والكربوهيدرات (الهدف×0.4)÷4 والدهون (الهدف×0.3)÷9 — بتقريب Math.round.
- هذا التوزيع خاص بحاسبة السعرات، ومستقل عن توزيعات حاسبة الماكروز الخمسة (بطاقة منفصلة).

**EN:**

- The calorie calculator starter split is protein 30% / carbs 40% / fat 30% of calories - the source labels it the "40/30/30" macro split.
- Grams: protein target*0.3/4, carbs target*0.4/4, fat target*0.3/9 (Math.round on each).
- This starter split belongs to the calorie calculator only and is independent of the macro-calculator five presets (separate card).

## الأصل الكامل (provenance)

- **المنبع:** مستودع alkemos-aws العام (المصدر الأساسي — ADR-0012) على الالتزام `32b63874c2a2488b39bf449d83539fc930fe05a5` عبر raw.githubusercontent قراءة-فقط بلا مفاتيح (R-35).
- **ما استُشهد به:** أسطر protein/carbs/fat داخل calculateCalorieTargets + الترويسة الموثقة.
- **الحقوق:** المصدر أصل مملوك لـAlkemos (مسجل في `references/data-rights.md` §2)؛ وهذه البطاقة «فارق مُتعلم مملوك» (data-rights §1) — إعادة بنائها حتمية عبر `scripts/gk_build_cards.py`.
- **تاريخ الاطلاع:** 2026-11-22 (UTC) · **الاعتماد:** G-K 2026-11-22 (UTC) (بوابة G-K — ADR-0017).

</div>
