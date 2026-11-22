---
id: CARD-0010
title: عقد مخطط التمارين الذكي وقانون تطابق التمارين
classification: مدققات AI
entity: مدقق/عقد مخطط التمارين وتطابق المكتبة
version: v1.0
status: معتمدة
last_reviewed: 2026-11-22 (UTC)
supersedes: —
superseded_by: —
contradicts: []
source: alkemos-aws@32b6387:src/lib/ai-workout-planner.ts · src/lib/ai-workout-exercise-match.ts — اطلاع 2026-11-22 (UTC)
approved_via: G-K 2026-11-22 (UTC)
---

<div dir="rtl" align="right">

## الحقائق (عربية أساسًا + المصطلح الإنجليزي عند اللزوم)

- قواعد البرومبت: 2 إلى 6 مجموعات من 5 إلى 20 تكرارًا لكل تمرين، والحركات المركبة (compound) تُبرمج أولًا.
- كل اسم يوم تدريبي وعضلاته المستهدفة وكل اسم تمرين يُكتب بالإنجليزية في مخرجات المخطط.
- الحجم الأسبوعي الموثق: 10–20 مجموعة أسبوعيًا لكل عضلة كبيرة (صدر/ظهر/أرجل/أكتاف) و6–12 لكل عضلة صغيرة.
- المدقق: المجموعات عدد صحيح بين 1 و10، والتكرارات بين 1 و50 أو مدى مثل 8–12، وتمارين اليوم 3–8.
- مطابقة تمارين المخطط مع مكتبة التمارين تقبل عند تغطية ≥0.6 مع ≥2 رمزًا متطابقًا.

**EN:**

- Prompt rules: 2 to 6 sets of 5 to 20 reps per exercise; compound movements FIRST.
- Write every day name, its target muscles, and every exercise name in English.
- Documented weekly volume bands: 10-20 weekly sets per large muscle (chest/back/legs/shoulders) and 6-12 per small one.
- Validator: sets an integer 1-10; reps 1-50 or a range; day exercises 3-8.
- Exercise-to-library matching accepts at coverage >= 0.6 with >= 2 matched tokens.

## الأصل الكامل (provenance)

- **المنبع:** مستودع alkemos-aws العام (المصدر الأساسي — ADR-0012) على الالتزام `32b63874c2a2488b39bf449d83539fc930fe05a5` عبر raw.githubusercontent قراءة-فقط بلا مفاتيح (R-35).
- **ما استُشهد به:** قواعد البرومبت ومدقق التحقق في ai-workout-planner.ts + قانون التغطية في ai-workout-exercise-match.ts.
- **الحقوق:** المصدر أصل مملوك لـAlkemos (مسجل في `references/data-rights.md` §2)؛ وهذه البطاقة «فارق مُتعلم مملوك» (data-rights §1) — إعادة بنائها حتمية عبر `scripts/gk_build_cards.py`.
- **تاريخ الاطلاع:** 2026-11-22 (UTC) · **الاعتماد:** G-K 2026-11-22 (UTC) (بوابة G-K — ADR-0017).

</div>
