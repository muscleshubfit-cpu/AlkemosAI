<div dir="rtl" align="right">

# سجل المصادر — Sources Log

> قاعدة (FOUNDATION_INSTRUCTIONS §1): كل مصدر يُوثق بالرابط + تاريخ الاطلاع + ما يؤكده. التاريخ موحد لهذا الفرز: **2026-11-21** إلا ما نُصّ خلافه.

## 1. النماذج والتراخيص

| المصدر | ما يؤكده |
|---|---|
| https://huggingface.co/Qwen/Qwen3.5-0.8B | وجود عائلة Qwen3.5 (2026) وترخيصها المعلن apache-2.0 |
| https://github.com/openai/gpt-oss + https://help.openai.com/en/articles/11870455-openai-open-weight-models-gpt-oss | gpt-oss-120b/20b مفتوحة الأوزان برخصة Apache-2.0 + usage policy، ومتطلبات تشغيلها (120B يتناسب مع 80GB GPU) |
| https://dev.meta.ai/llama/llama4/license | ترخيص Llama 4 Community وشروطه (استخدام تجاري بشروط + سياسة استخدامات) |
| https://ai.google.dev/gemma/terms | ترخيص Gemma Terms of Use (قيود وشروط استخدام تسري على النسخ المعدلة) — أساس تحفظ «غير متحقق» على ادعاء Apache لـGemma-4 |
| تحليلات تراخيص الأوزان المفتوحة 2026 (مقالات مرخصة عبر نتائج البحث، من بينها intuitionlabs.ai/articles/open-weight-ai-model-licenses ومراجعات تراخيص DeepSeek) | MIT لأوزان DeepSeek-R1 باستثناءات النسخ المقطرة؛ خريطة القيود لعائلات Llama/Gemma/Mistral/Kimi/MiniMax |
| https://huggingface.co/blog/daya-shankar/open-source-llms (مقال مجتمعي 2025-11) | خريطة المشهد المفتوح 2026 (Kimi K2.6، GLM-5.x، Qwen3، Gemma-4، Llama-4 Scout 10M سياق) — تُعامل كمؤشر لا حقيقة نهائية |
| https://huggingface.co/blog/leaderboard-arabic-v2 + https://github.com/EleutherAI/lm-evaluation-harness (مهام arabic_leaderboard_complete) | وجود لوحات ومهام تقييم عربية جاهزة (OALL/OALL2) للاستخدام كفحص أولي |
| مقالات أفضل النماذج العربية 2026 (promptquorum.com/local-llms/best-arabic-local-llms-2026 ونتائج لوحات OALL 2026) | Jais-30B (Core42) أقوى عربي محلي بترخيص Apache-2.0؛ Falcon-H1 يتصدر لوحات العربية (34B: 75.36%)؛ Fanar-1 9B وALLaM 7B أوزان مفتوحة |

## 2. الاستضافة والتكاليف

| المصدر | ما يؤكده |
|---|---|
| https://www.runpod.io/pricing (محدث 2026-11-12) | أسعار GPU: RTX 4090 من $0.34/س، L4 $0.39، RTX 6000 Ada/L40S $1.09، A100 PCIe $1.19–2.09، H100 PCIe $1.99–2.89 |
| https://www.runpod.io/gpu-models/rtx-4090 | تأكيد 4090 عند $0.34/ساعة عند الطلب |
| https://lyceum.technology/magazine/lambda-labs-vs-runpod-vs-vast-ai + مقارنات 2026 (vast.ai أرخص سوقًا، RunPod أسهل تشغيلًا، Lambda مؤسسي) | موضع كل مزود GPU ومنطق الاختيار |
| https://www.hetzner.com/dedicated-rootserver/matrix-gpu | خطط GPU المخصصة Hetzner (GEX131 ~€1,499/شهر) — غير مجدية لمرحلتنا |
| https://io.net/blog/llm-fine-tuning-budget-guide-gpu-costs-timelines-and-what-to-spend (2026-06-04) | تكاليف الضبط: LoRA ‏7B <$10 · QLoRA ‏70B $15–30 · تدريب كامل 70B ليوم $200–300 |
| https://www.spheron.network/blog/gpu-vram-requirements-fine-tune-llm-2026 (2026-07-01) | متطلبات VRAM للضبط الدقيق 2026 وأسعار مرجعية (مثل RTX 5090 بـ$0.78/س عند 2026-11-17) |
| https://www.premai.io/blog/self-hosted-llm-guide-setup-tools-cost-comparison-2026 + أدلة vLLM إنتاجية 2026 | أكواد الاستضافة الذاتية (vLLM/Ollama/Docker) ومنهجية حساب التعادل |
| مناقشات تشغيل CPU (r/LocalLLaMA + أدلة llama.cpp 2026) | سرعات CPU الواقعية لنماذج صغيرة (~5–15 توكن/ث لـ8B) — تكفي المهام الخلفية فقط |

## 3. فحص Alkemos وAWS (مصادر داخلية مُقيسة — لا روابط خارجية)

| المصدر | ما يؤكده |
|---|---|
| مستودع alkemos-aws @ `ed57082` (قراءة مباشرة 2026-11-21) | كل بنود خط الأساس (السلاسل/السجل/الحصص/EVO/النشر/التقارير) — انظر `ALKEMOS_BASELINE.md` |
| فحص AWS CLI حي قراءة-فقط 2026-11-21 (هوية alkemos_aws_api) | هوية/SCP/مثيل Lightsail/Bedrock/التكاليف — انظر `docs/03-infrastructure/aws-audit.md` |
| GitHub API (repos/muscleshubfit-cpu/AlkemosAI) | خصوصية المستودع وفرعه الأساسي ومحتواه الأولي [مُقيس 2026-11-21] — ثم **تحويله إلى عام (visibility: public) وتثبيته** بأمر المالك عبر PATCH [مُقاس 2026-11-21] |

## 4. الطبقات والمواقع المجانية — تحقق دفعة المسار الصفري (كله 2026-11-21)

| المصدر | ما يؤكده |
|---|---|
| https://kaggle.com/docs/efficient-gpu-usage | حصة Kaggle المجانية: 30 ساعة GPU/أسبوع تتجدد أسبوعيًا (T4×2/P100) — بلا بطاقة |
| https://huggingface.co/docs/hub/spaces-overview | HF Spaces CPU Basic: 2 vCPU / 16GB RAM مجانًا؛ الأجهزة المجانية «تنام» بعد خمول (48 ساعة موثقة من إدارة المساحات) |
| https://colab.research.google.com/signup | الطبقة المجانية في Colab: وصول GPU محدود جدًا، وجلسات لا تتجاوز 12 ساعة — بلا بطاقة |
| https://openrouter.ai/pricing | نماذج `:free`: 20 طلب/دقيقة و50 طلب/يوم بلا رصيد؛ 1000/يوم تتطلب شراء $10 (مستبعدة عندنا) |
| https://console.groq.com/docs/rate-limits | وثائق حدود Groq (الطبقة المجانية قائمة بحدود لكل نموذج) — التفاصيل الحية في عداداتنا المُقيسة |
| https://developers.cloudflare.com/workers-ai/platform/pricing | Workers AI: 10,000 عصبون/يوم مجانًا على خطة Workers Free |
| https://www.cloudflare.com/products/vectorize | «ابدأ مجانًا — بلا بطاقة بنكية» |
| https://developers.cloudflare.com/vectorize/platform/pricing | Vectorize على Workers Free: 5M بعد مخزن + 30M بعد مستعلم/شهر + 100 فهرس مجانًا |
| https://ai.google.dev/gemini-api/docs/rate-limits (+ /pricing) | بنية الطبقة المجانية لـGemini: حدود يومية صارمة ومتقلصة تاريخيًا؛ بحث Gemini 3+ مجاني 5,000 طلب/شهر |
| https://docs.oracle.com/iaas/Content/FreeTier/freetier.htm | Oracle Always Free تتطلب بطاقة عند التسجيل (تحقق $1) — أساس استبعادها |
| https://build.nvidia.com | NIM: واجهات serverless مجانية للتطوير — بلا بطاقة |
| https://supabase.com/pricing + https://supabase.com/docs/guides/platform/free-project-pausing | Supabase مجاني: 500MB · مشروعان نشطان · إيقاف بعد 7 أيام خمول · إضافة pgvector رسمية |
| https://upstash.com/pricing/redis | Upstash مجاني: 250MB و500K أمر/شهر |
| https://www.tavily.com/pricing | Tavily: 1,000 رصيد/شهر — بلا بطاقة |
| https://docs.github.com/billing/managing-billing-for-github-actions/about-billing-for-github-actions | GitHub Actions مجانية بلا حد على المشغّلات القياسية للمستودعات العامة |
| https://github.com/ggml-org/llama.cpp | llama.cpp ‏MIT: خادم متوافق مع OpenAI + نقطة `/v1/embeddings`؛ سحب GGUF مباشرة من HF (`llama serve -hf`) |
| https://github.com/ollama/ollama | Ollama مفتوح المصدر (MIT) |
| https://github.com/vllm-project/vllm | vLLM ‏Apache-2.0 |
| https://github.com/unslothai/unsloth | Unsloth نواة مفتوحة Apache-2.0 — تدريب QLoRA على GPU Colab/Kaggle المجانية |
| https://developers.cloudflare.com/workers-ai/models/bge-m3 + https://huggingface.co/BAAI/bge-m3 | bge-m3 متعدد اللغات (100+ لغة، حتى 8192 توكن) متاح على Workers AI — للتضمين ضمن العصبونات المجانية |
| https://huggingface.co/Qwen/Qwen3.5-0.8B (+ مقارنات 2026) | عائلة Qwen3.5 ‏Apache-2.0 بفروع صغيرة 0.8B/2B/4B مع GGUF رسمية — مرشح التدريب الأول |
| https://huggingface.co/docs/inference-providers/en/pricing | رصيد الحساب المجاني في HF Inference ~$0.10/شهر — للفحص فقط |
| https://modal.com/pricing + إشارات التسجيل | Modal: $30 رصيد/شهر — اشتراط البطاقة غير محسوم التوثيق → استبعاد احترازي |
| https://lightning.ai/pricing | Lightning AI: ساعات GPU تأسيسية (50–80) تُستهلك مرة واحدة → نمط تجربة → مستبعد |

## 5. قاعدة التحديث

- أي مصدر جديد يضاف بصف جديد بنفس النمط (مع تاريخ اطلاعه الخاص إن اختلف).
- المصدر «المُقاس داخليًا» يُحال لملفه لا يُكرر.
- المصادر المدفوعة/غير الرسمية لا تُعتمد للاسعار النهائية — تُستخدم كإشارات فرز فقط.

## 6. تحقق دفعة 3 — إعادة التعريف (كله 2026-11-21)

| المصدر | ما يؤكده |
|---|---|
| https://www.kaggle.com/docs/efficient-gpu-usage (اطلاع 2026-11-21) | حصة Kaggle المجانية: **30 ساعة GPU/أسبوع تتجدد أسبوعيًا** (T4×2/P100)، جلسات حتى ~12 ساعة — بلا بطاقة |
| https://docs.github.com/en/repositories/working-with-files/managing-large-files/about-large-files-on-github + توثيق مجتمعي متطابق (اطلاع 2026-11-21) | رفض git للملفات >100MB؛ **أصول GitHub Releases حتى 2GB للملف** — أساس مرآة الأوزان (ADR-0009) |
| https://huggingface.co/pricing (اطلاع 2026-11-21) | الحساب المجاني يشمل **100GB تخزين خاص** (‏PRO ‏1TB) — بلا بطاقة؛ أساس التخزين الأول للأوزان |
| https://developers.cloudflare.com/r2/ + نقاشات مجتمع Cloudflare الرسمية (اطلاع 2026-11-21) | **R2 يتطلب طريقة دفع حتى للطبقة المجانية** — أساس استبعاده (شرط «لا بطاقة») |
| https://allenai.org/blog/olmo3 + https://allenai.org/olmo (اطلاع 2026-11-21) | **OLMo 3** (‏7B/32B): مفتوح بالكامل — أوزان + بيانات + كود + تقارير (خيار «الانفتاح الكامل» في القائمة القصيرة) |
| https://huggingface.co/Qwen/Qwen3.5-35B-A3B/blob/main/LICENSE + صفحات عائلة Qwen3.5 | رخصة عائلة **Qwen3.5 ‏Apache-2.0** من نص الرخصة الرسمي (تحقق ملف لا وصف) |
| https://aws.amazon.com/free/free-tier-faqs (اطلاع 2026-11-21) | الحسابات الجديدة: رصيد $100 عند التسجيل + حتى $100 استكشافيًا؛ نظام التجربة 12-شهرًا أُلغي للحسابات الجديدة — سياق قاعدة «AWS تُحمَل ولا تُوسَّع» |
| فحص حي قراءة-فقط عبر boto3 (هوية `alkemos_aws_api`) — 2026-11-21 | مثيل Lightsail `alkemos-test` يعمل (micro_3_0، ‏1GB RAM)؛ التكاليف سبتمبر–نوفمبر **$0.00** — ضمن رصيد $100 حتى 2027-04-09 [مُقيس] |
| لقطة النسخة الاحتياطية 2026-11-21 (`musclehubeg-backups/snapshots/manifest.json` — قراءة محلية بلا أي PII) | جرد المحتوى الحي: **blog_posts ‏151 صفًا (2.2MB)** · blog_generation_queue ‏230 (6.9MB) · nutrient_reference ‏169 · recipes ‏12 + 140 مكوّنًا · evo_nutrition_patterns ‏9 [مُقيس] |
| استكشاف قرائي لمستودعات `muscleshubfit-cpu` (alkemos · alkemos-aws · alkemos-authority-engine · musclehubeg-backups · free-exercise-db) — 2026-11-21 | أصول المعرفة: **868 تمرينًا** ثنائي اللغة (الأصل المنبع free-exercise-db بترخيص **Unlicense/ملك عام**) · ~~8,830 صنف طعام~~ (**صُحح إلى 8,162 — دفعة 4، انظر §7**) · 7 برامج · 24 خطة · دستور تحرير بـ14 جهة علمية بيضاء · برومبتات EVO/الخطط/الأدوات العشرة [مُقيس من الكود] |

## 7. تحقق دفعة 4 — مراجعة الخطة v2.1 (فحص حي 2026-11-21 UTC)

| المصدر | ما يؤكده |
|---|---|
| GitHub API — شجرة `muscleshubfit-cpu/alkemos-aws` @ `main` ‏`ed57082` (2026-11-21T15:18:10Z) | **8,362 مدخلًا / 7,070 ملفًا** · 130 ميجريشن · 56 workflow · 199 ملف docs/ · 5,406 ملف public/ — سطح المصدر الأساسي للمراقبة [مُقيس] |
| `src/lib/foods.ts` @ ed57082 (تنزيل مباشر وعدّ slug/nameAr/nameEn/per100g) | **8,162 صنفًا** — مطابق لتعليق الملف نفسه («8,162-food array») — **تصحيح الرقم 8,830 الوارد في §6 أعلاه** (كان بلا دليل مباشر) [مُقيس] |
| `src/lib/exercises.ts` @ ed57082 (عدّ slug/imageKey) | **868 تمرينًا** — تأكيد الرقم الموروث [مُقيس] |
| README مستودع alkemos-aws (قراءة خام عبر API) | البنية الكاملة (Next.js 16 · Supabase · 5 مزودي توليد + Tavily/Exa بحثًا · Lightsail+Cloudflare) والوحدات المعرفية (EVO، المكتبات، المدونة الثنائية) [اطلاع 2026-11-21] |
| الصفحة الرئيسية alkemos.com (WebFetch) | 868+ تمرينًا · 8,162+ صنف طعام · ثنائية اللغة · EVO · الأدوات — اتساق أرقام الموقع مع الكود [اطلاع 2026-11-21] |
| GitHub API — قائمة مستودعات الحساب (11 مستودعًا) | **alkemos-aws** (عام، نشط، آخر دفع 2026-11-21) هو المرجع الأساسي · **alkemos** (خاص، سلف غير نشط، آخر دفع 2026-10-10) · **seo-skills** (عام، fork لـIllyism/seo-skills) · **alkemos-authority-engine** (خاص) · **musclehubeg-backups** (خاص، لقطات يومية) · **Agent-Reach** (عام، fork لـPanniantong/Agent-Reach، MIT) [مُقيس] |
| README مستودع seo-skills (قراءة خام عبر API) | **30 مهارة SEO ببطاقات SKILL.md، ترخيص MIT، مواصفة Agent Skills** — بذور الطبقة د (ADR-0015) [اطلاع 2026-11-21] |
| README مستودع alkemos-authority-engine (قراءة خام عبر API) | محرك سلطة white-hat كامل (7 قنوات · تصنيف روابط صادق · 171 اختبارًا · تشغيل مرتين يوميًا 05:00/17:00 **UTC**) — سابقة جدولة UTC في منظومة المالك [اطلاع 2026-11-21] |
| README مستودع Agent-Reach (قراءة خام عبر API) | أداة MIT لتمكين الوكلاء من قراءة الإنترنت — مرشح أدوات البحث [غير متحقق التقييم بعد] [اطلاع 2026-11-21] |
| https://docs.github.com/repositories/managing-your-repositorys-settings-and-features/managing-repository-settings/setting-repository-visibility (اطلاع 2026-11-21) | تحويل مستودع عام إلى خاص: **الـforks العامة تبقى عامة في شبكة منفصلة**، وقد تتأثر stars/watchers/dependency graph — أساس قائمة فحص T1 والقاعدة «لا يوضع في العلني ما لا يصح بقاؤه عامًا أبدًا» (ADR-0019/R-33) |

## 8. تحقق دفعة 5 — تدقيق حدود الموارد المجانية (كله 2026-11-21 UTC)

| المصدر | ما يؤكده |
|---|---|
| https://docs.github.com/en/actions/concepts/billing-and-usage + https://docs.github.com/en/billing/managing-billing-for-github-actions/about-billing-for-github-actions (اطلاع 2026-11-21) | GitHub Actions مجانية على المشغّلات القياسية المستضافة؛ **للمستودعات الخاصة** تُقاس الدقائق ضمن الخطة — أساس تقييد «بلا حد» بالمستودع العام في كل الوثائق |
| https://docs.github.com/en/get-started/learning-about-github/faq-about-changes-to-githubs-plans (اطلاع 2026-11-21) | خطة GitHub Free تشمل «2,000 Actions minutes for private repositories» — سقف ما بعد التحول إلى خاص (T1 — ADR-0019 §6) |
| https://www.kaggle.com/docs/efficient-gpu-usage (اطلاع 2026-11-21 — إعادة قراءة دفعة 5) | حصة GPU الأسبوعية «تتجدد أسبوعيًا وهي 30 ساعة **أو أعلى أحيانًا حسب الطلب والموارد**» — حصة قابلة للتغيير من مزودها بلا SLA، لا ضمان؛ يصحح تقديم «30 س/أسبوع دائمًا» كأنه مضمون |
| https://huggingface.co/docs/hub/storage-limits (اطلاع 2026-11-21) | التخزين الخاص المجاني في HF Hub سقفه **100GB** (PRO ‏1TB · إضافات مدفوعة بالتيرابايت) — تأكيد رقم 100GB في ADR-0009/PLAN §8.2 وتصحيح وصف «بلا حد عملي» في ZERO_COST_PLAN §3.1 |
| https://docs.github.com/en/repositories/releasing-projects-on-github/about-releases (اطلاع 2026-11-21) | كل ملف ضمن Release يجب أن يكون تحت **2 GiB**، بلا حد على إجمالي حجم الإصدار أو النطاق — تأكيد مرآة Releases |


## 9. تحقق دفعة 10 — تفعيل حسابي HF/Kaggle وقياس حي للصلاحيات والحصص (كله 2026-11-22 UTC — ADR-0020)

قياسات حية مباشرة (لا روابط خارجية — استدعاءات API فعلية من بيئتين: محلية ومن GitHub Actions ‏run ‏45028375241 على الالتزام `26cfea3`؛ التفصيل في `docs/03-infrastructure/hf-kaggle-integration.md`):

| نقطة النهاية (اطلاع 2026-11-22) | ما أثبتته القياسات الفعلية |
|---|---|
| `GET huggingface.co/api/whoami-v2` (Bearer — استدعاء فعلي) | توكن HF ‏fine-grained صالح للحساب `Alkemos` بنطاقات تشمل `repo.write` و`inference.*` و`user.billing.read` (18 نطاقًا) — صلاحيات فعلية لا مفترضة |
| `POST huggingface.co/api/repos/create` + رفع README (عبر عميل huggingface_hub الرسمي) | إنشاء مستودع خاص `Alkemos/alkemosai-weights` ورأس التزام `42c081f` — إثبات كتابة فعلي (الساق 1 من ثلاثية ADR-0009) |
| `GET huggingface.co/api/models/Alkemos/alkemosai-weights` بلا مصادقة | HTTP ‏401 — المستودع خاص فعلًا (تحقق خصوصية سالب) |
| `GET router.huggingface.co/v1/models` (Bearer — سرد فقط) | 200 بـ158 نموذجًا مسرودًا عبر موفري الاستدلال — **سرد بلا توليد = بلا استهلاك أي رصيد** (طبقة «فحوص دخان» فقط — ZERO_COST_PLAN §3.1) |
| `POST api.kaggle.com/v1/security.OAuthService/IntrospectToken` (Basic — استدعاء فعلي) | المفتاح الصحيح: `{active: true, username: alkemosai, scope: resources.admin:*}` — والمفتاح الخاطئ: HTTP ‏404 — **نقطة التحقق القاطعة الوحيدة** (سرد البيانات العامة يعيد 200 بلا اعتماديات أصلًا — مقيس بمصفوفة: بلا اعتماديات/خاطئة/صحيحة) |
| `POST api.kaggle.com/v1/kernels.KernelsApiService/GetAcceleratorQuotaStatistics` (Bearer — قراءة-فقط) | حصة GPU ‏**30 س/أسبوع (108000s) — 0 مستخدمة** + TPU ‏**20 س/أسبوع (72000s)** + التجديد `2026-11-28T00:00:00Z` — أول قياس حي للحصة بدلًا من التوثيق وحده؛ **قيد مصادقة مقيس: خدمة kernels ترفض Basic (401) وتقبل Bearer بمفتاح KGAT** |
| GitHub REST API: `PUT /actions/secrets/{name}` (استدعاء فعلي بتشفير libsodium) | استجابة 201 لكل من `HF_TOKEN`·`KAGGLE_USERNAME`·`KAGGLE_KEY` والسرد يؤكد وجودها — GitHub لا تُرجع القيم أبدًا |

**قانون مستخلص (يُلزم سكربتات M2):** نجاح استدعاء API بلا استهلاك = «سرد»؛ إثبات الصلاحية يتطلب نقطة تحقق سلوكية قاطعة (نموذجيًا: استعلام سلامة أو عملية قراءة تُرفض بلا اعتماديات صحيحة) — لا يُكتفى بـ200 من نقطة تقبل الوصول العام.

</div>
