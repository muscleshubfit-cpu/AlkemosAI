---
id: CARD-0004
title: توزيعات حاسبة الماكروز الخمسة والتحويل على 4/4/9
classification: حسابات المنصة
entity: حساب/توزيعات الماكروز الخمسة (حاسبة الماكروز)
version: v1.0
status: معتمدة
last_reviewed: 2026-11-22 (UTC)
supersedes: —
superseded_by: —
contradicts: []
source: alkemos-aws@32b6387:src/lib/content/macro-calculator.ts — اطلاع 2026-11-22 (UTC)
approved_via: G-K 2026-11-22 (UTC)
---

<div dir="rtl" align="right">

## الحقائق (عربية أساسًا + المصطلح الإنجليزي عند اللزوم)

- توزيعات الماكروز الخمسة في حاسبة الماكروز (بروتين/كارب/دهون كنسب من السعرات): متوازن 30/40/30 · منخفض الكارب 40/20/40 · عالي البروتين 45/35/20 · كيتو 25/5/70 · منخفض الدهون 35/55/10.
- تحويل الغرامات موحد على 4/4/9 سعرات لكل غرام (بروتين/كارب/دهون) بتقريب Math.round.
- كل رقم في النسخة مطابق للكود بعرافات (canaries) في ترويسة المصدر — لا انجراف صامت بين التوثيق والكود.

**EN:**

- The macro-calculator presets (P/C/F as percent of calories): balanced 30/40/30, low-carb 40/20/40, high-protein 45/35/20, keto 25/5/70, low-fat 35/55/10.
- Grams conversion at 4/4/9 kcal per gram (protein/carbs/fat), Math.round on each.
- Every number in the source header is pinned against the code with canaries - no silent drift.

## الأصل الكامل (provenance)

- **المنبع:** مستودع alkemos-aws العام (المصدر الأساسي — ADR-0012) على الالتزام `32b63874c2a2488b39bf449d83539fc930fe05a5` عبر raw.githubusercontent قراءة-فقط بلا مفاتيح (R-35).
- **ما استُشهد به:** ثابت MACRO_PRESETS وترويسته الموثقة (كل رقم مثبت بعرافات مقابل الكود).
- **الحقوق:** المصدر أصل مملوك لـAlkemos (مسجل في `references/data-rights.md` §2)؛ وهذه البطاقة «فارق مُتعلم مملوك» (data-rights §1) — إعادة بنائها حتمية عبر `scripts/gk_build_cards.py`.
- **تاريخ الاطلاع:** 2026-11-22 (UTC) · **الاعتماد:** G-K 2026-11-22 (UTC) (بوابة G-K — ADR-0017).

</div>
