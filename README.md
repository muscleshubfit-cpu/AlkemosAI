# AlkemosAI

**AlkemosAI — مشروع منظومة ذكاء اصطناعي مستقلة ومملوكة بالكامل (نموذج، أوزان، بيانات، ذاكرة، معرفة) لخدمات اللياقة والتغذية والصحة بالعربية والإنجليزية | Independent fully-owned AI system for fitness, nutrition and health (AR/EN)**

<div dir="rtl" align="right">

## ما هذا المستودع؟

هذا هو **المقر الدائم لمشروع AlkemosAI** — مستودع خاص يحمل الرؤية وخط الأساس والخطة الكاملة لبناء منظومة ذكاء اصطناعي **نملكها نحن**: أوزانها وكودها وبياناتها وذاكرتها ومعرفتها، قابلة للنقل بين الاستضافات، وصولًا إلى العمل دون أي اعتماد دائم على مزودي نماذج خارجيين.

المستودع **تخطيطي/بحثي/توثيقي** في هذه المرحلة: لا يحتوي كود تطبيق، ولا يمس إنتاج Alkemos (المستودع المرجعي: `muscleshubfit-cpu/alkemos-aws` — يُفحص قراءةً فقط).

## نقطة البداية (خط الأساس — 2026-11-22)

فُحص مستودع Alkemos الفعلي بالكامل (الالتزام `ed57082`)، والنتيجة الموثقة في [`ALKEMOS_BASELINE.md`](ALKEMOS_BASELINE.md):

- منظومة AI موحدة نسبيًا: 5 مزودي توليد (OpenRouter، Groq، NVIDIA NIM، Gemini ذيلًا فقط، Cloudflare) + مزودا بحث (Tavily، Exa) — **كلها طبقات مجانية**.
- طبقة توجيه مركزية مجربة (Registry + Router + تراجع بمتغير واحد) وسجل مهام وحصص وتبريد صادق.
- الإنتاج: AWS Lightsail (eu-north-1) + Supabase (eu-central-1) + GitHub Actions كحوسبة دفعية، بتكلفة صافية $0/شهر حاليًا.
- الفجوة الجوهرية: **صفر ملكية للنماذج أو الأوزان** واعتماد وجودي على APIs خارجية — وهذا ما وُجد المشروع لعلاجه.

## الوثائق الجذرية

| الملف | الغرض |
|---|---|
| [`STATE.md`](STATE.md) | **أول ملف تقرؤه في أي جلسة** — الحالة الحية والقرارات المعلقة |
| [`ALKEMOS_BASELINE.md`](ALKEMOS_BASELINE.md) | خط أساس Alkemos الحقيقي المُقيس من الكود |
| [`VISION.md`](VISION.md) | الرؤية وأعمدة الملكية العشرة وسلّم النضج L0–L5 |
| [`MASTER_ROADMAP.md`](MASTER_ROADMAP.md) | الخطة الرئيسية: المراحل 0–10 والتبعيات والمعايير |
| [`DECISIONS.md`](DECISIONS.md) | سجل القرارات (مع `decisions/ADR/`) |
| [`COST_MODEL.md`](COST_MODEL.md) | نموذج التكاليف ونقطة التعادل |
| [`RISK_REGISTER.md`](RISK_REGISTER.md) | سجل المخاطر |
| [`SECURITY.md`](SECURITY.md) | سياسات الأسرار والخصوصية |

خطة المراحل الكاملة في `docs/00-foundation/` حتى `docs/10-final-report/` — كل مرحلة بملف واحد يضم: الهدف، النطاق، المهام التفصيلية، الأوامر المرجعية، المخرجات، معايير النجاح، المخاطر، التبعيات، والحالة. التعليمات المشتركة الموحدة في `docs/00-foundation/FOUNDATION_INSTRUCTIONS.md` (لا تكرر في كل مرحلة).

## المسار المبدئي الموصى به (قابل للاعتماد)

**مسار هجين متدرج:** البقاء على APIs الحالية (مجانية) مع بناء محرك AlkemosAI بواجهة موحدة متوافقة مع OpenAI، ثم تشغيل نموذج مفتوح الأوزان ذاتيًا على GPU مؤجرة عند الطلب للمهام عالية الحجم والمنضبطة (الخطط الغذائية/التدريبية أولًا)، وتوسيع الحصة الذاتية كلما أثبت التقييم تعادل الجودة — حتى يصبح الاستدلال الخارجي استثناءً مضبوطًا. التفاصيل والأرقام في `docs/10-final-report/final-report-v0.1.md`.

## الحوكمة

- **المالك:** أحمد (`muscleshubfit@gmail.com`) — كل قرار تنفيذي يمس الإنتاج أو الميزانية يحتاج موافقته الموثقة.
- مسموح في هذا المستودع: البحث، التخطيط، التوثيق، الفحص القرائي للإنتاج.
- ممنوع دون موافقة مستقلة: تعديل كود Alkemos، تغيير مزودي الإنتاج، تعديل الخوادم/القواعد، الشراء أو تفعيل اشتراكات، تدريب مكلف، تحويل المستودع لعام. القائمة الكاملة في `docs/00-foundation/FOUNDATION_INSTRUCTIONS.md` §3.
- **لا أسرار هنا أبدًا** — انظر `SECURITY.md`.

## كيف تعمل أي جلسة جديدة؟

1. اقرأ `STATE.md` (الحالة والقرارات المعلقة).
2. اقرأ ملف المرحلة ذات الصلة من `docs/`.
3. التزم بـ `docs/00-foundation/FOUNDATION_INSTRUCTIONS.md` (المنهجية والمصادر والتوثيق).
4. عند إنجاز أي دفعة: حدّث `STATE.md` + سجّل القرار + commit/push إلى `main`.

</div>

---

# AlkemosAI (English)

**What this repository is:** the permanent home of the AlkemosAI project — a private, planning-and-research repository for building a fully-owned AI system (weights, code, data, memory, knowledge) for fitness, nutrition and health in Arabic and English, portable across hosts, progressing toward zero permanent dependency on external model providers.

**Starting point (baseline, 2026-11-22):** the existing Alkemos production repo was examined in full (code-level, read-only). Verified: a unified-ish AI layer (5 generation providers + 2 search providers, all free-tier), a battle-tested central router with one-env-var rollback, quota/cooldown/metering systems, and an AWS Lightsail + Supabase + GitHub Actions production stack at ~$0/month. The core gap: **zero model ownership** — total existential dependency on external APIs. Full details: [`ALKEMOS_BASELINE.md`](ALKEMOS_BASELINE.md).

**Initial recommended path (pending owner approval):** a staged hybrid — keep current free APIs while building the AlkemosAI engine behind an OpenAI-compatible unified interface, then self-host an open-weights model on on-demand GPUs for high-volume, well-bounded tasks (meal/training plans first), expanding the self-hosted share only as bilingual evals prove parity. Numbers: `docs/10-final-report/final-report-v0.1.md`.

**Governance:** owner Ahmed (`muscleshubfit@gmail.com`) approves every production-affecting or budget-affecting decision. This repo holds research, plans and documentation only. No secrets, ever (`SECURITY.md`). New sessions start at `STATE.md`, follow `docs/00-foundation/FOUNDATION_INSTRUCTIONS.md`, and always end with `STATE.md` refreshed and work committed to `main`.
