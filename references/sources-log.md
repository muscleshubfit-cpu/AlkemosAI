<div dir="rtl" align="right">

# سجل المصادر — Sources Log

> قاعدة (FOUNDATION_INSTRUCTIONS §1): كل مصدر يُوثق بالرابط + تاريخ الاطلاع + ما يؤكده. التاريخ موحد لهذا الفرز: **2026-11-22** إلا ما نُصّ خلافه.

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
| مستودع alkemos-aws @ `ed57082` (قراءة مباشرة 2026-11-22) | كل بنود خط الأساس (السلاسل/السجل/الحصص/EVO/النشر/التقارير) — انظر `ALKEMOS_BASELINE.md` |
| فحص AWS CLI حي قراءة-فقط 2026-11-22 (هوية alkemos_aws_api) | هوية/SCP/مثيل Lightsail/Bedrock/التكاليف — انظر `docs/03-infrastructure/aws-audit.md` |
| GitHub API (repos/muscleshubfit-cpu/AlkemosAI) | خصوصية المستودع وفرعه الأساسي ومحتواه الأولي [مُقيس 2026-11-22] — ثم **تحويله إلى عام (visibility: public) وتثبيته** بأمر المالك عبر PATCH [مُقاس 2026-11-22] |

## 4. الطبقات والمواقع المجانية — تحقق دفعة المسار الصفري (كله 2026-11-22)

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
