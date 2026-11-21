# AlkemosAI

**AlkemosAI — مشروع مستقل لبناء نموذج ذكاء اصطناعي مملوك يتعلم ويتراكم (لياقة · تغذية · علوم رياضة · عربي/إنجليزي) | A standalone project building an owned AI model that learns and accumulates**

<div dir="rtl" align="right">

## ما هذا المستودع؟ (إعادة التعريف — 2026-11-22)

هذا هو المقر الدائم لمشروع **AlkemosAI** بعد إعادة تعريفه بتوجيه المالك: **مشروع مستقل هدفه بناء نموذج ذكاء اصطناعي مملوك يتعلم ويتراكم ويتطور باستمرار** — يُبنى فوق نماذج مفتوحة بتراخيص تسمح بالتملك والتعديل (Apache-2.0/MIT فقط)، ويتعلم **على دفعات** بلا تشغيل دائم ولا خادم استدلال ولا GPU مستمر، وكل ما يكتسبه (معرفة، بيانات، ذاكرة، أوزان، سجلات تعلم) يعيش في **ملفات وأصول مملوكة قابلة للنقل بين الاستضافات**.

**ما ليس عليه هذا المشروع (غير الأهداف — ADR-0007):** لا يُشغَّل لخدمة المستخدمين، ولا يستبدل أو يعدّل نظام الذكاء الاصطناعي الحالي في Alkemos، ولا يمس إنتاج Alkemos أو خوادمه أو قواعد بياناته أو مزوديه، وليس واجهة لتجميع واجهات برمجية.

## الوثيقة المركزية

| الملف | الغرض |
|---|---|
| [`PLAN.md`](PLAN.md) | **الخطة المعمارية والتنفيذية v2.0** — معمارية التعلم التراكمي، المراحل M0–M5، الحدود الصادقة. بانتظار الاعتماد (D-11) |
| [`STATE.md`](STATE.md) | **أول ملف تقرؤه في أي جلسة** — الحالة الحية والقرارات المعلقة |
| [`VISION.md`](VISION.md) | الرؤية، أعمدة الملكية، سلّم نمو النموذج A0–A5 |
| [`MASTER_ROADMAP.md`](MASTER_ROADMAP.md) | خارطة الطريق: المراحل والبوابات وخريطة الاستبدال من الخطة القديمة |
| [`DECISIONS.md`](DECISIONS.md) | سجل القرارات (مع `decisions/ADR/` — ADR-0001 حتى ADR-0011) |
| [`COST_MODEL.md`](COST_MODEL.md) | نموذج التكاليف — الخطة الحالية صفر التزامات مالية |
| [`ZERO_COST_PLAN.md`](ZERO_COST_PLAN.md) | بحث المواقع المجانية وحدودها (مرجع ساري؛ خطة F0–F5 مُستبدلة بمراحل M) |
| [`ALKEMOS_BASELINE.md`](ALKEMOS_BASELINE.md) | خط أساس Alkemos الحقيقي المُقيس من الكود (مرجع ساري) |
| [`RISK_REGISTER.md`](RISK_REGISTER.md) | سجل المخاطر (R-01 حتى R-26) |
| [`SECURITY.md`](SECURITY.md) | سياسات الأسرار والخصوصية |

## هيكل المستودع (الطبقات الثلاث للتراكم)

```
datasets/     الطبقة أ — المعرفة والبيانات المملوكة (JSONL + بطاقات، موثقة الترخيص)
memory/       الطبقة ب — الذاكرة (بطاقات معرفة + سجل التعلم + صندوق ملاحظات)
training/     الطبقة ج — إعدادات وتقارير دفعات التدريب (تُنشأ عند M3)
evaluation/   بطارية التقييم ثنائية اللغة + النتائج الموقعة (بوابة كل تعلم)
registry/     سجل النماذج: إصدارات ← أصول (HF/Releases) + المؤشر الأفضل
```

## نقطة الانطلاق (مُقيس 2026-11-22)

المشروع لا يبدأ من فراغ — أصول معرفية فعلية جاهزة للتوظيف (جُردت من مستودعات Alkemos والنسخ الاحتياطية وفحص AWS الحي اليوم):

- **868 تمرينًا** ثنائي اللغة · **8,830 صنف طعام** · **7 برامج تدريبية** · **24 خطة غذائية**
- **151 مقالًا** منشورًا (2.2MB) + **230 سجل توليد** · **169 مرجعًا غذائيًا** · دستور تحرير بـ14 جهة علمية بيضاء
- بيئات مجانية مثبتة: **Kaggle ‏30 GPU-س/أسبوع** · **GHA بلا حد** · **HF ‏100GB تخزين خاص** · **GitHub Releases ≤2GB/ملف** — بلا بطاقة بنكية
- **AWS:** مثيل الإنتاج يعمل بتكلفة **$0** (مُقيس سبتمبر–نوفمبر) — يُحمَل ولا يُوسَّع (ADR-0010)

## الحوكمة

- **المالك:** أحمد (`muscleshubfit@gmail.com`) — كل قرار تنفيذي يمس الإنتاج أو الميزانية يحتاج موافقته الموثقة.
- **الحالة الحالية:** المشروع تخطيطي/توثيقي — **لا تنفيذ قبل اعتماد الخطة v2.0 (قرار D-11)**.
- مسموح: البحث، التخطيط، التوثيق، الفحص القرائي للإنتاج. ممنوع دون موافقة مستقلة: تعديل كود Alkemos أو مزوديه أو خوادمه، الشراء أو الاشتراكات، أي خدمة تتطلب بطاقة بنكية، بدء التدريب.
- **لا أسرار هنا أبدًا** — انظر `SECURITY.md`.

## كيف تعمل أي جلسة جديدة؟

1. اقرأ `STATE.md` (الحالة والقرارات المعلقة).
2. اقرأ `PLAN.md` (الخطة المعتمدة/المعروضة) وملف المرحلة ذات الصلة.
3. عند إنجاز أي دفعة: حدّث `STATE.md` + سجّل القرار (ADR عند الحاجة) + commit/push إلى `main`.

</div>

---

# AlkemosAI (English)

**What this repository is:** the permanent home of the AlkemosAI project after its owner-directed redefinition (2026-11-22): a **standalone project building an owned AI model that learns and accumulates** — specialized in fitness, nutrition and sports science (Arabic/English), built on open-weight models under ownership-friendly licenses (Apache-2.0/MIT only), trained **in gated batches** with no continuous serving, no permanent inference server and no always-on GPU. Everything the model learns (knowledge, data, memory, weights, learning logs) lives in **owned, portable files and assets** transferable between hosts.

**Explicit non-goals (ADR-0007):** not run to serve users; not a replacement for (or modification of) Alkemos's current AI system; never touches Alkemos production, servers, databases or providers; not an API-aggregation facade.

**Status:** planning/documentation phase — the v2.0 plan (`PLAN.md`) awaits owner approval (decision D-11) before any execution begins. **Governance:** owner Ahmed approves every production- or budget-affecting decision; no secrets ever (`SECURITY.md`); new sessions start at `STATE.md`.
