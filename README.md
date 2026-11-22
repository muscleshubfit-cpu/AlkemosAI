# AlkemosAI

**AlkemosAI — مشروع مستقل لبناء نظام معرفي مملوك يتعلم ويتراكم، تخصصه الحاكم (ADR-0021) مدرب لياقة شخصي ذكي بمستوى احترافي عالمي (عربي فصحى/مصري + إنجليزي) | A standalone project building an owned, accumulative intelligence system — an AI personal trainer at world-class professional level (MSA/Egyptian Arabic + English)**

<div dir="rtl" align="right">

## ما هذا المستودع؟ (مراجعة v2.2 — 2026-11-22 UTC)

هذا هو المقر الدائم لمشروع **AlkemosAI**: مشروع مستقل هدفه بناء **نظام معرفي مملوك يتعلم ويتراكم، تخصصه الحاكم (القرار الاستراتيجي ADR-0021 — دفعة 11) أن يعمل النموذج مدرب لياقة شخصيًا ذكيًا بمستوى احترافي عالمي** — يفهم علوم التغذية والتدريب، ويحسب السعرات والماكروز بدقة، ويصمم أنظمة غذائية وبرامج تدريبية شخصية، ويحلل حالة العميل وتقدمه ويكتشف أخطاء خططه، ويحاور عملاءه بالعربية الفصحى والمصرية والإنجليزية ويتابعهم ويعدل خططهم كمدرب محترف حقيقي. نموذج يتعلم على دفعات فوق نماذج مفتوحة بتراخيص تسمح بالتملك (Apache-2.0/MIT فقط)، محاطًا بأربع طبقات تراكم مملوكة (معرفة وبيانات · ذاكرة · **مهارات** · أوزان)، يستمد معرفته أساسًا من **مستودع Alkemos الأساسي (`alkemos-aws`)** عبر **مراقب اكتشاف تلقائي** لكل إضافة أو تعديل مستقبلي، ويبني **بحثًا خارجيًا مستقلًا** (فصل صارم بين الجمع والاعتماد) — ويعتمد كل تعلم جديدًا فقط عبر **بوابات تقييم ثنائية اللغة** (G-K/G-S/G-Q). كل الأصول في ملفات مملوكة قابلة للنقل بين الاستضافات. **كتابة المقالات وSEO/GEO/AEO وإنتاج المحتوى مؤجلة إلى مرحلة لاحقة بعد نضج النموذج (سجل تأجيل موحد — بلا حذف أي أصل).**

**ما ليس عليه هذا المشروع (غير الأهداف — ADR-0007):** لا يُشغَّل لخدمة المستخدمين، ولا يستبدل أو يعدّل نظام الذكاء الاصطناعي الحالي في Alkemos، ولا يمس إنتاج Alkemos أو خوادمه أو قواعد بياناته أو مزوديه (ولا حتى تعديلات «تحسين SEO» — مخرجات الخبرة توصيات فقط)، وليس واجهة لتجميع واجهات برمجية. **العلنية مؤقتة للمراجعة فقط، ويتحول المستودع إلى خاص عند اكتمال المشروع (ADR-0019/D-14).**

## الوثيقة المركزية

| الملف | الغرض |
|---|---|
| [`PLAN.md`](PLAN.md) | **الخطة المعمارية والتنفيذية v2.2** — أربع طبقات + منظومتا دخول + مسارات M + C + سجل التأجيل (ADR-0021). **معتمدة بقرار D-11 (2026-11-21 UTC) ومحدّدة بالقرار الاستراتيجي ADR-0021 (2026-11-22 UTC)** — التنفيذ جارٍ: M1 (بيانات + بطارية — دفعة 8 · أول دورة G-K — دفعة 9) + C1 نشط · C4 مؤجل |
| [`STATE.md`](STATE.md) | **أول ملف تقرؤه في أي جلسة** — الحالة الحية والقرارات المعلقة |
| [`VISION.md`](VISION.md) | الرؤية، أعمدة الملكية (11)، سلّما النمو A0–A5 والاستقلالية Aut0–Aut3 |
| [`MASTER_ROADMAP.md`](MASTER_ROADMAP.md) | خارطة الطريق: المسارات M/C والبوابات والختم T1 |
| [`DECISIONS.md`](DECISIONS.md) | سجل القرارات (مع `decisions/ADR/` — ADR-0001 حتى ADR-0021) |
| [`COST_MODEL.md`](COST_MODEL.md) | نموذج التكاليف — **صفر التزامات حاليًا** + فرز «مجاني الآن مقابل موارد مستقبلية» |
| [`ZERO_COST_PLAN.md`](ZERO_COST_PLAN.md) | بحث المواقع المجانية وحدودها (مرجع ساري) |
| [`ALKEMOS_BASELINE.md`](ALKEMOS_BASELINE.md) | خط أساس Alkemos المُقيس (مرجع ساري + فحص لاحق 2026-11-21) |
| [`RISK_REGISTER.md`](RISK_REGISTER.md) | سجل المخاطر (R-01 حتى R-40) |
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
- **كوربوس SEO/GEO/AEO حقيقي في المصدر الأساسي:** مخططات SEO-GEO وتدقيقات GSC وEEAT وسكيما + وحدة إجابات GEO إنتاجية — أصل محفوظ لمسار الخبرة **المؤجل** (ADR-0021).
- **أصول النظام البيئي:** 30 مهارة SEO جاهزة (MIT — استيرادها مؤجل بقرار ADR-0021) · محرك سلطة white-hat كامل (خاص) · أداة قراءة إنترنت للوكلاء (MIT).
- **بيئات مجانية مثبتة (حصص قابلة للتغيير من مزوديها — ليست ضمانات):** Kaggle 30 GPU-س/أسبوع (بلا SLA) · GHA بلا حد **للمستودع العام** (بعد التخصيص: 2,000 دقيقة/شهر) · HF ‏100GB تخزين خاص (سقف الخطة المجانية) · Releases ≤2GB/ملف — بلا بطاقة بنكية.
- **AWS:** الإنتاج يعمل بتكلفة $0 مُقيس — يُحمَل ولا يُوسَّع.

## الحوكمة

- **المالك:** أحمد (`muscleshubfit@gmail.com`) — كل قرار تنفيذي يمس الإنتاج أو الميزانية يحتاج موافقته الموثقة.
- **الحالة الحالية (دفعة 11 — القرار الاستراتيجي ADR-0021):** التنفيذ جارٍ بأمر المالك (**D-11 صدر 2026-11-21 UTC**): M1 نشطة — أُنتجت بياناتها (دفعة 8: `sft-exercises-ar/en.jsonl` ‏2,604 لكل لغة · `sft-foods-ar.jsonl` ‏8,162 · `sft-programs.jsonl` ‏62) وبطاريتها (162 حالة منها 87 حرجة) بمولّد حتمي، وأُنجزت أول دورة G-K (دفعة 9: 15 بطاقة معرفة معتمدة + مراجعتاها) — **أركان G-M1 الثلاثة متحققة والإغلاق الرسمي بالدفعة التنفيذية التالية** (بند `sft-blog-style-ar` صار مؤجلًا استراتيجيًا) · C1 نشط (مراقب قراءة-فقط كل 6 ساعات UTC) · دفعة 10 (ADR-0020): حسابا HF ‏(`Alkemos`) وKaggle ‏(`AlkemosAI`) مفعّلان ومتحقق منهما مقيسًا — جاهزية M2 بلا تدريب. **دفعة 11 (ADR-0021 — القرار الاستراتيجي بأمر المالك 2026-11-22 UTC):** الأولوية الحالية لبناء النموذج كمدرب لياقة شخصي ذكي بمستوى احترافي عالمي (تغذية + تدريب + تحليل حالات + حوار فصحى/مصري/إنجليزي + متابعة وتعديل) — أولويات معرفة بست درجات (PLAN §5.6) وخريطة توسيع البطارية بعشرة أبعاد (الجودة والدقة والتفكير معايير قبول لا تُخفض) — وتأجيل المقالات وSEO/GEO/AEO وإنتاج المحتوى إلى ما بعد نضج النموذج (سجل تأجيل بلا حذف: C4 كاملًا · بذور seo-skills · `sft-blog-style-ar` · D-12) — **وتسلسل بناء النموذج بلا تغيير** (M1 ← M2 ← D-5 ← M3 ← M4) وقائمة المرشحين كما هي. التفاصيل: [تقرير دفعة 11](docs/01-strategy/batch-11-priority-shift-report.md). **لا تدريب أوزان بدأ** (بعد M1 وقياس M2) ولا نموذج شُغل ولا أي التزام مالي أُنشئ ولا مساس بإنتاج Alkemos.
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

**What this repository is:** the permanent home of the AlkemosAI project, now an **owned, accumulative intelligence system whose governing specialty (strategic decision ADR-0021) is an AI personal trainer at world-class professional level**: a specialized model (Modern Standard Arabic / Egyptian Arabic / English) trained in gated batches on ownership-friendly open weights (Apache-2.0/MIT only) — understanding nutrition and training science, calculating calories and macros precisely, designing personalized diet and training programs, analyzing client cases and progress, detecting plan errors and contradictions, and conversing with clients and following up like a real professional coach. It is surrounded by **four owned accumulation layers** (data & knowledge · memory with conflict detection & versioning · **skills** · weights), fed primarily by the **main Alkemos production repository (`alkemos-aws`) through an automatic change-discovery watcher**, plus an **independent external-research pipeline** (strict separation between collection and adoption). Every new learning — knowledge, skill, or weights — passes a **bilingual acceptance gate** (G-K/G-S/G-Q). All assets live in owned, portable files. **Article writing, SEO/GEO/AEO and content production are deferred to a later phase after model maturity (a unified deferral register — nothing deleted).**

**Explicit non-goals (ADR-0007):** never run to serve users; never replace or modify Alkemos's current AI system; never touch Alkemos production, servers, databases or providers (including production SEO changes — the expertise track produces recommendations only); not an API-aggregation facade. **The repository is public temporarily for review only and converts to private at project completion (ADR-0019 / decision D-14).**

**Status (batch 11 — strategic decision ADR-0021):** execution ongoing by owner order (**D-11 granted 2026-11-21 UTC**): M1 active — datasets produced (batch 8: `sft-exercises-ar/en.jsonl` 2,604 records each · `sft-foods-ar.jsonl` 8,162 · `sft-programs.jsonl` 62) plus the completed evaluation battery (`alkemos-eval-v0.jsonl` — 162 cases, 87 critical) via a deterministic builder; the first G-K gate cycle approved 15 knowledge cards (batch 9, with its two review continuations — mutation tests 26/26); C1 active (read-only source watcher every 6h UTC); batch 10 (ADR-0020) activated the Hugging Face (`Alkemos`) and Kaggle (`AlkemosAI`) accounts with live read-only verification — M2-ready without training. **Batch 11 (ADR-0021, owner strategic order 2026-11-22 UTC): the current priority is building the model as a world-class professional AI personal trainer** (nutrition + training + case analysis + MSA/Egyptian/English dialogue + follow-up and plan adjustment) — with a six-tier knowledge/data/skills priority order (PLAN §5.6) and a ten-dimension battery-expansion map (quality, accuracy and reasoning are non-negotiable acceptance criteria) — **while article writing, SEO/GEO/AEO expertise and content production are deferred to a post-maturity phase** (a deferral register, nothing deleted: the whole C4 track · the 30 seo-skills seeds · `sft-blog-style-ar` · decision D-12) — **and the model-building sequence is unchanged** (M1 → M2 → D-5 → M3 → M4) with the candidate list intact. Details: [batch-11 report](docs/01-strategy/batch-11-priority-shift-report.md). **No weights training yet** (after M1 and M2 measurement); no model served; no financial commitment created; Alkemos production untouched. **Time law (ADR-0013):** all stored timestamps are UTC (ISO-8601, `Z` suffix); local times documented with their offset. **Governance:** owner Ahmed approves every production- or budget-affecting decision; no secrets ever (`SECURITY.md`); new sessions start at `STATE.md`.
