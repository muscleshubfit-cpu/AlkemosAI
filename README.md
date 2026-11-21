# AlkemosAI

**AlkemosAI — مشروع مستقل لبناء نظام معرفي مملوك يتعلم ويتراكم (نموذج + مهارات + خبرة SEO/GEO/AEO · عربي/إنجليزي) | A standalone project building an owned, accumulative intelligence system (model + skills + SEO/GEO/AEO expertise · AR/EN)**

<div dir="rtl" align="right">

## ما هذا المستودع؟ (مراجعة v2.1 — 2026-11-21 UTC)

هذا هو المقر الدائم لمشروع **AlkemosAI**: مشروع مستقل هدفه بناء **نظام معرفي مملوك يتعلم ويتراكم** — نموذج ذكاء اصطناعي متخصص (لياقة/تغذية/علوم رياضة، عربي/إنجليزي) يتعلم على دفعات فوق نماذج مفتوحة بتراخيص تسمح بالتملك (Apache-2.0/MIT فقط)، محاطًا بأربع طبقات تراكم مملوكة (معرفة وبيانات · ذاكرة · **مهارات** · أوزان)، يستمد معرفته أساسًا من **مستودع Alkemos الأساسي (`alkemos-aws`)** عبر **مراقب اكتشاف تلقائي** لكل إضافة أو تعديل مستقبلي، ويبني **بحثًا خارجيًا مستقلًا** (فصل صارم بين الجمع والاعتماد) و**خبرة SEO/GEO/AEO متراكمة** — ويعتمد كل تعلم جديدًا فقط عبر **بوابات تقييم ثنائية اللغة** (G-K/G-S/G-Q). كل الأصول في ملفات مملوكة قابلة للنقل بين الاستضافات.

**ما ليس عليه هذا المشروع (غير الأهداف — ADR-0007):** لا يُشغَّل لخدمة المستخدمين، ولا يستبدل أو يعدّل نظام الذكاء الاصطناعي الحالي في Alkemos، ولا يمس إنتاج Alkemos أو خوادمه أو قواعد بياناته أو مزوديه (ولا حتى تعديلات «تحسين SEO» — مخرجات الخبرة توصيات فقط)، وليس واجهة لتجميع واجهات برمجية. **العلنية مؤقتة للمراجعة فقط، ويتحول المستودع إلى خاص عند اكتمال المشروع (ADR-0019/D-14).**

## الوثيقة المركزية

| الملف | الغرض |
|---|---|
| [`PLAN.md`](PLAN.md) | **الخطة المعمارية والتنفيذية v2.1.1** — أربع طبقات + منظومتا دخول + مسارات M + C + بوابة T1. **معتمدة بقرار D-11 (2026-11-21 UTC) — التنفيذ بدأ: M1 + C1 نشطان (دفعة 6)** |
| [`STATE.md`](STATE.md) | **أول ملف تقرؤه في أي جلسة** — الحالة الحية والقرارات المعلقة |
| [`VISION.md`](VISION.md) | الرؤية، أعمدة الملكية (11)، سلّما النمو A0–A5 والاستقلالية Aut0–Aut3 |
| [`MASTER_ROADMAP.md`](MASTER_ROADMAP.md) | خارطة الطريق: المسارات M/C والبوابات والختم T1 |
| [`DECISIONS.md`](DECISIONS.md) | سجل القرارات (مع `decisions/ADR/` — ADR-0001 حتى ADR-0019) |
| [`COST_MODEL.md`](COST_MODEL.md) | نموذج التكاليف — **صفر التزامات حاليًا** + فرز «مجاني الآن مقابل موارد مستقبلية» |
| [`ZERO_COST_PLAN.md`](ZERO_COST_PLAN.md) | بحث المواقع المجانية وحدودها (مرجع ساري) |
| [`ALKEMOS_BASELINE.md`](ALKEMOS_BASELINE.md) | خط أساس Alkemos المُقيس (مرجع ساري + فحص لاحق 2026-11-21) |
| [`RISK_REGISTER.md`](RISK_REGISTER.md) | سجل المخاطر (R-01 حتى R-37) |
| [`SECURITY.md`](SECURITY.md) | سياسات الأسرار والخصوصية والرصد والبحث |

## هيكل المستودع (طبقات التراكم الأربع + خط الدخول)

```
datasets/     الطبقة أ — المعرفة والبيانات المملوكة (JSONL + بطاقات، موثقة الترخيص)
memory/       الطبقة ب — الذاكرة v2 (بطاقات بتعارضات ونسخ + سجل التعلم + صناديق مراجعة)
skills/       الطبقة د — المهارات المكتسبة (SKILL.md موثقة مقيمة الجودة — بوابة G-S)
training/     إعدادات وتقارير دفعات التدريب (تُنشأ عند M3)
evaluation/   بطارية التقييم ثنائية اللغة + النتائج الموقعة (بوابة كل تعلم)
registry/     سجل النماذج: إصدارات ← أصول (HF/Releases) + المؤشر الأفضل
research/     خط الدخول: مراقب المصدر الأساسي (alkemos-aws) + البحث الخارجي (مرشحون فقط)
```

## نقطة الانطلاق (فحص حي 2026-11-21 UTC — المصدر الأساسي alkemos-aws @ `ed57082`)

- **أصول معرفية مُقيسة:** **868 تمرينًا** ثنائي اللغة · **8,162 صنف طعام** (تصحيح رقم سابق غير مثبت) · 7 برامج · 24 خطة غذائية · 151 مقالًا منشورًا · 169 مرجعًا غذائيًا · دستور تحرير بـ14 جهة علمية بيضاء.
- **كوربوس SEO/GEO/AEO حقيقي في المصدر الأساسي:** مخططات SEO-GEO وتدقيقات GSC وEEAT وسكيما + وحدة إجابات GEO إنتاجية — مادة تعلم لمسار الخبرة.
- **أصول النظام البيئي:** 30 مهارة SEO جاهزة (MIT) · محرك سلطة white-hat كامل (خاص) · أداة قراءة إنترنت للوكلاء (MIT).
- **بيئات مجانية مثبتة (حصص قابلة للتغيير من مزوديها — ليست ضمانات):** Kaggle 30 GPU-س/أسبوع (بلا SLA) · GHA بلا حد **للمستودع العام** (بعد التخصيص: 2,000 دقيقة/شهر) · HF ‏100GB تخزين خاص (سقف الخطة المجانية) · Releases ≤2GB/ملف — بلا بطاقة بنكية.
- **AWS:** الإنتاج يعمل بتكلفة $0 مُقيس — يُحمَل ولا يُوسَّع.

## الحوكمة

- **المالك:** أحمد (`muscleshubfit@gmail.com`) — كل قرار تنفيذي يمس الإنتاج أو الميزانية يحتاج موافقته الموثقة.
- **الحالة الحالية (دفعة 6):** التنفيذ بدأ بأمر المالك (**D-11 صدر 2026-11-21 UTC**): M1 نشطة (نواة المعرفة والذاكرة v0) وC1 نشط (مراقب قراءة-فقط كل 6 ساعات UTC). **لا تدريب أوزان بدأ** (بعد M1 وقياس M2) ولا نموذج شُغل ولا أي التزام مالي أُنشئ ولا مساس بإنتاج Alkemos.
- مسموح: البحث والتخطيط والتوثيق والفحص/الرصد القرائي قراءة-فقط. ممنوع دون موافقة مستقلة: تعديل كود Alkemos أو مزوديه أو خوادمه (أو إنتاجه ولو لتحسين SEO)، الشراء أو الاشتراكات، بدء التدريب.
- **قانون التوقيت (ADR-0013):** كل طابع مخزن UTC (ISO-8601 بلاحقة Z)؛ المحلي يوثق بإزاحته (المالك: Africa/Cairo).
- **العلنية مؤقتة للمراجعة** (ADR-0019): قاعدة «لا يوضع في العلني ما لا يصح بقاؤه عامًا أبدًا» — والتحول إلى خاص عند الاكتمال بقرار D-14.
- **لا أسرار هنا أبدًا** — انظر `SECURITY.md`.

## كيف تعمل أي جلسة جديدة؟

1. اقرأ `STATE.md` (الحالة والقرارات المعلقة).
2. اقرأ `PLAN.md` (الخطة المعروضة) وADR ذات الصلة.
3. عند إنجاز أي دفعة: حدّث `STATE.md` + سجّل القرار (ADR عند الحاجة) + commit/push إلى `main` (طوابع UTC).

</div>

---

# AlkemosAI (English)

**What this repository is:** the permanent home of the AlkemosAI project, now an **owned, accumulative intelligence system**: a specialized bilingual (AR/EN) model trained in gated batches on ownership-friendly open weights (Apache-2.0/MIT only), surrounded by **four owned accumulation layers** (data & knowledge · memory with conflict detection & versioning · **skills** · weights), fed primarily by the **main Alkemos production repository (`alkemos-aws`) through an automatic change-discovery watcher**, plus an **independent external-research pipeline** (strict separation between collection and adoption) and a compounding **SEO/GEO/AEO expertise track**. Every new learning — knowledge, skill, or weights — passes a **bilingual acceptance gate** (G-K/G-S/G-Q). All assets live in owned, portable files.

**Explicit non-goals (ADR-0007):** never run to serve users; never replace or modify Alkemos's current AI system; never touch Alkemos production, servers, databases or providers (including production SEO changes — the expertise track produces recommendations only); not an API-aggregation facade. **The repository is public temporarily for review only and converts to private at project completion (ADR-0019 / decision D-14).**

**Status (batch 6):** execution started by owner order (**D-11 granted 2026-11-21 UTC**): M1 (knowledge core + memory v0) and C1 (read-only source watcher, every 6h UTC) are active. No weights training yet (that follows M1 + M2 measurement); no model served; no financial commitment created; Alkemos production untouched. **Time law (ADR-0013):** all stored timestamps are UTC (ISO-8601, `Z` suffix); local times documented with their offset. **Governance:** owner Ahmed approves every production- or budget-affecting decision; no secrets ever (`SECURITY.md`); new sessions start at `STATE.md`.
