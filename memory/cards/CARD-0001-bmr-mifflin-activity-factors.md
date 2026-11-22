---
id: CARD-0001
title: معادلة Mifflin-St Jeor للأيض الأساسي ومعاملات النشاط الخمسة
classification: حسابات المنصة
entity: حساب/الأيض الأساسي (BMR) والإنفاق اليومي (TDEE)
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

- معدل الأيض الأساسي (BMR) يحسب بمعادلة Mifflin-St Jeor: للذكر 10×الوزن(كغ) + 6.25×الطول(سم) − 5×العمر(سنة) + 5؛ وللأنثى المعادلة نفسها بثابت −161 بدل +5.
- الإنفاق اليومي الكلي (TDEE) = تقريب Math.round لضرب BMR في معامل النشاط (ACTIVITY_FACTORS): خامل 1.2 · خفيف 1.375 · معتدل 1.55 · نشط 1.725 · نشط جدًا 1.9.
- قانون المصدر الواحد (AGENTS.md §12.8): الرياضيات البحتة تعيش في fitness-math.ts حصرًا، وإن تغيرت المعادلة تغيرت هناك ويسير السطحان (الأداة وصفحة المحتوى) خلفها في نفس المرحلة — الأرقام وحدها تتدفق منها.

**EN:**

- BMR uses the Mifflin-St Jeor equation: males 10*weight(kg) + 6.25*height(cm) - 5*age + 5; females the same with -161 instead of +5.
- TDEE = Math.round(BMR x activity factor) - ACTIVITY_FACTORS: sedentary 1.2, light 1.375, moderate 1.55, active 1.725, very_active 1.9.
- Single-source law (AGENTS.md §12.8): the pure math lives in fitness-math.ts only; if the formula ever changes it changes there, and both surfaces follow in the same phase.

## الأصل الكامل (provenance)

- **المنبع:** مستودع alkemos-aws العام (المصدر الأساسي — ADR-0012) على الالتزام `32b63874c2a2488b39bf449d83539fc930fe05a5` عبر raw.githubusercontent قراءة-فقط بلا مفاتيح (R-35).
- **ما استُشهد به:** دالة calculateCalorieTargets وثابت ACTIVITY_FACTORS وقانون المصدر الواحد في ترويسة الملف.
- **الحقوق:** المصدر أصل مملوك لـAlkemos (مسجل في `references/data-rights.md` §2)؛ وهذه البطاقة «فارق مُتعلم مملوك» (data-rights §1) — إعادة بنائها حتمية عبر `scripts/gk_build_cards.py`.
- **تاريخ الاطلاع:** 2026-11-22 (UTC) · **الاعتماد:** G-K 2026-11-22 (UTC) (بوابة G-K — ADR-0017).

</div>
