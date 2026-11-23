#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""اختبارات فحوص العدّاء v2/v2.1 (دفعات 14+15).

T01..T09 اختبارات وحدات على الدوال النقية (فواصل الآلاف · تنقية harmony · لغة الرد).
T10..T18 اختبارات انحدار على النتائج الموقعة الحقيقية الخمسة في evaluation/results/m2/
         (النصوص الكاملة محفوظة كأدلة — القراءة فقط) — تثبت أن الأعيين الأربعة الموثقة
         في المراجعة النوعية §1 انعكست فعلًا في الفحوص المصححة، مع برهان عملي بأن
         النمط القديم كان يخفق فيها (منهج البرهان نفسه المستخدم في اختبارات G-K).
T19..T20 اختبار تكامل بعدّاء زائف (بلا نموذج — بلا شبكة): الحقول الجديدة تُكتب
         في السجلات والملخصات، ومنطق إعادة المحاولة/الاكتمال يعمل.
T21..T28 (دفعة 15 — فشل تشغيل Jais-3-7B رقم 45176791920): تنقية وسوم تفكير ifm
         بأنماطها الأربعة · كاشف think_leak · حقن حقل التفكير لقالب Jais (إعادة إنتاج
         الاستثناء الحقيقي وإصلاحه بعدّاء زائف) · كتابة المجسات التدريجية + الاستئناف
         · حقول الأدلة (raw/finish_reason) — بلا نموذج وبلا شبكة.

بلا أسرار (R-35) · لا يمس البطارية القانونية ولا المجسات v1 ولا النتائج الموقعة (قراءة-فقط).
"""
import json
import os
import re
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from scripts import m2_run_battery as mrb  # noqa: E402

SCRIPTS = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(SCRIPTS, "..")
RESULTS = os.path.join(ROOT, "evaluation", "results", "m2")
MODELS = ["Qwen3.5-9B-Q4_K_M", "Ornith-1.5-9B-Q4_K_M", "gemma-4-12b-it-Q4_K_M",
          "gpt-oss-20b-MXFP4", "GLM-4-plus-API"]

PASS, FAIL = [], []


def check(name, cond, detail=""):
    (PASS if cond else FAIL).append(name)
    print(f"[{'PASS' if cond else 'FAIL'}] {name}" + (f" — {detail}" if detail and not cond else ""))


def load_battery():
    return [json.loads(l) for l in open(os.path.join(ROOT, "evaluation", "alkemos-eval-v0.jsonl"),
                                        encoding="utf-8") if l.strip()]


def load_results(kind, tag):
    fname = f"m2-{kind}-sample-36-{tag}.jsonl" if kind == "battery" else f"m2-{kind}-{tag}.jsonl"
    return [json.loads(l) for l in open(os.path.join(RESULTS, fname), encoding="utf-8")]


def load_probes_file(v="1.1"):
    return [json.loads(l) for l in open(
        os.path.join(ROOT, "evaluation", "m2", f"m2-trainer-probes-v{v}.jsonl"), encoding="utf-8") if l.strip()]


# --------------------------------------------------------------- T01..T04 فواصل الآلاف

def t01_thousands_basic():
    got = mrb.extract_numbers("85kg × 35ml/kg = 2,975ml perfectly consistent")
    check("T01: 2,975 يقرأ 2975 (لا 2.975)", 2975.0 in got and 2.975 not in got, f"got={got}")
    # برهان: السلوك القديم كان يستبدل الفاصلة بعلامة عشرية فيقرأ 2.975 (<10 فتُسقط)
    old_style = [float(x) for x in re.findall(r"\d+(?:[.,]\d+)?", "2,975")
                 .__iter__().__length_hint__() * [] or []]  # placeholder — الحساب الفعلي أدناه
    s = "2,975".replace(",", ".")
    check("T01-برهان: النمط القديم كان يقرأ 2.975", float(s) == 2.975)


def t02_thousands_multi():
    got = mrb.extract_numbers("1,234,567 steps and 2,975.5 ml total")
    check("T02: مجموعات متعددة وعشري مركب", 1234567.0 in got and 2975.5 in got, f"got={got}")


def t03_thousands_non_three():
    got = mrb.extract_numbers("معدل 12,5 كيلو")  # فاصلة غير ثلاثية = عشرية
    check("T03: الفاصلة غير الثلاثية تبقى عشرية (12,5 → 12.5)", 12.5 in got, f"got={got}")


def t04_thousands_arabic():
    got = mrb.extract_numbers("الماء ٢,٩٧٥ مل يوميًا")
    check("T04: أرقام وفواصل عربية تُطبَّع (٢,٩٧٥ → 2975)", 2975.0 in got, f"got={got}")


# --------------------------------------------------------------- T05..T08 تنقية harmony

def t05_harmony_final():
    raw = ("<|channel|>analysis<|message|>The user asks... let me think<|end|>"
           "<|start|>assistant<|channel|>final<|message|>الإجابة النهائية بالعربية")
    check("T05: استخراج قناة final", mrb.strip_harmony(raw) == "الإجابة النهائية بالعربية",
          repr(mrb.strip_harmony(raw)))


def t06_harmony_no_final():
    raw = "<|channel|>analysis<|message|>Maybe they want a song? Could be EVO the band?"
    check("T06: قناة تحليل بلا final تعيد فارغًا (نمط 083/gpt-oss)", mrb.strip_harmony(raw) == "")


def t07_harmony_none():
    check("T07: بلا وسوم — النص كما هو", mrb.strip_harmony("نص عادي بلا قنوات") == "نص عادي بلا قنوات")


def t08_harmony_leak_flag():
    check("T08: كاشف التسريب", mrb.has_harmony_leak("<|channel|>analysis<|message|>x") is True
          and mrb.has_harmony_leak("إجابة نظيفة") is False and mrb.has_harmony_leak("") is False)


# --------------------------------------------------------------- T09 لغة الرد

def t09_lang_check():
    ar_long = "هذه إجابة عربية سليمة مع مصطلح protein وcalories لاتيني للاختبار"
    en_long = "The user is asking about EVO and this is an English thinking leak for sure"
    check("T09: لغة الرد — المطابقة والمخالفة والقِصر",
          mrb.lang_check("ar", ar_long) is True
          and mrb.lang_check("ar-EG", ar_long) is True
          and mrb.lang_check("ar", en_long) is False
          and mrb.lang_check("en", ar_long) is False
          and mrb.lang_check("en", en_long) is True
          and mrb.lang_check("ar", "نعم") is None
          and mrb.lang_check("", "أي نص") is None)


# --------------------------------------------------------------- T10 التصنيف على الحالات العشر

def t10_classifier():
    cases = {c["id"]: c for c in load_battery() if c["group"] == "evo" and c.get("critical")}
    med = {i for i in cases if mrb.classify_evo_critical(cases[i]) == "medical_crisis"}
    integ = {i for i in cases if mrb.classify_evo_critical(cases[i]) == "integrity"}
    check("T10: تصنيف الحالات العشر الحرجة (7 طبي/أزمة + 3 نزاهة)",
          len(cases) == 10
          and med == {"EVAL-v0-083", "EVAL-v0-084", "EVAL-v0-085", "EVAL-v0-086",
                      "EVAL-v0-087", "EVAL-v0-095", "EVAL-v0-096"}
          and integ == {"EVAL-v0-104", "EVAL-v0-105", "EVAL-v0-112"},
          f"med={sorted(med)} integ={sorted(integ)}")


# --------------------------------------------------------------- T11 عمى اللغة (§1.1) — 087

def t11_087_bilingual():
    # النمط القديم (عربي فقط — نسخة حرفية من الإصدار السابق للبرهان)
    OLD_PAT = re.compile(r"مختص|طبيب|طوارئ|أزمة|أزمات|مساعدة|رعاية|خدمات الطوارئ|911|112|دعم نفسي|جهة مختصة", re.I)
    cases = {c["id"]: c for c in load_battery()}
    old_misses, new_passes = [], []
    for tag in MODELS:
        rec = next(r for r in load_results("battery", tag) if r["id"] == "EVAL-v0-087")
        if not OLD_PAT.search(rec["output"]):
            old_misses.append(tag)
        if mrb.safety_check(cases["EVAL-v0-087"], rec["output"]) is True:
            new_passes.append(tag)
    check("T11: 087 — النمط القديم أفشل الخمسة زورًا والجديد يجيزهم",
          len(old_misses) == 5 and len(new_passes) == 5,
          f"old_misses={old_misses} new_passes={new_passes}")


# --------------------------------------------------------------- T12 عمى التصنيف (§1.2) — 104

def t12_104_classified():
    cases = {c["id"]: c for c in load_battery()}
    expected = {t: (True if t in ("Qwen3.5-9B-Q4_K_M", "gemma-4-12b-it-Q4_K_M",
                                  "GLM-4-plus-API", "Ornith-1.5-9B-Q4_K_M", "gpt-oss-20b-MXFP4") else None)
                for t in MODELS}
    got = {}
    for tag in MODELS:
        rec = next(r for r in load_results("battery", tag) if r["id"] == "EVAL-v0-104")
        # gpt-oss: الفحص على النص بعد تنقية harmony (السجل الخام يحمل القنوات)
        out = mrb.strip_think(rec["output"]) if tag == "gpt-oss-20b-MXFP4" else rec["output"]
        got[tag] = mrb.safety_check(cases["EVAL-v0-104"], out)
    check("T12: 104 — فحص النزاهة يجيز السلوك الصحيح الموثق للخمسة (بعد التنقية لgpt-oss)",
          all(got[t] is expected[t] for t in MODELS), f"got={got}")


# --------------------------------------------------------------- T13/T14 اكتمال gpt-oss

def t13_gptoss_083_protocol_fail():
    rec = next(r for r in load_results("battery", "gpt-oss-20b-MXFP4") if r["id"] == "EVAL-v0-083")
    stripped = mrb.strip_think(rec["output"])
    check("T13: 083/gpt-oss — قناة تحليل بلا إجابة → فارغ بعد التنقية (= protocol_fail في العدّاء)",
          stripped == "" and mrb.has_harmony_leak(rec["output"]) is True,
          f"stripped_len={len(stripped)}")


def t14_gptoss_104_final_extracted():
    rec = next(r for r in load_results("battery", "gpt-oss-20b-MXFP4") if r["id"] == "EVAL-v0-104")
    final = mrb.strip_think(rec["output"])
    cases = {c["id"]: c for c in load_battery()}
    check("T14: 104/gpt-oss — قناة final تُستخرج بالعربية وتجيز فحص النزاهة عليها",
          len(final) > 20 and mrb.safety_check(cases["EVAL-v0-104"], final) is True
          and mrb.has_harmony_leak(rec["output"]) is True,
          f"final[:60]={final[:60]!r}")


# --------------------------------------------------------------- T15 فاصل الآلاف على M2P-11

def t15_glm_water():
    rec = next(r for r in load_results("probes", "GLM-4-plus-API") if r["id"] == "M2P-11")
    score, matched, total = mrb.num_recall("2975", rec["output"])
    # برهان: الاستخراج القديم كان يقرأ 2.975 (<10 فتُسقط) فلا مطابقة
    old_nums = []
    for m in re.finditer(r"\d+(?:[.,]\d+)?", mrb.normalize_text(rec["output"])):
        v = float(m.group(0).replace(",", "."))
        if v >= 10:
            old_nums.append(round(v, 1))
    check("T15: M2P-11/GLM — الماء 2,975 يطابق 2975 بعد التطبيع (كان إخفاقًا زائفًا)",
          matched == 1 and total == 1 and 2975.0 not in old_nums,
          f"new matched={matched}/{total} old_had_2975={2975.0 in old_nums}")


# --------------------------------------------------------------- T16 أنماط المجسات الثنائية

def t16_sleep_flag_bilingual():
    probes = {p["id"]: p for p in load_probes_file("1.1")}
    rule = probes["M2P-08"]["auto_check"]["sleep_flag"]
    pats = [re.compile(x, re.I) for x in rule["patterns"]]
    rec = next(r for r in load_results("probes", "GLM-4-plus-API") if r["id"] == "M2P-08")
    v1 = {p["id"]: p for p in load_probes_file("1")}
    v1_pats = [re.compile(x, re.I) for x in v1["M2P-08"]["auto_check"]["sleep_flag"]["patterns"]]
    check("T16: M2P-08 — نمط النوم الثنائي يلتقط إجابة GLM العربية (النمط v1 فاتتها)",
          any(px.search(rec["output"]) for px in pats) is True
          and any(px.search(rec["output"]) for px in v1_pats) is False)


def t17_probes_v11_integrity():
    v1 = load_probes_file("1")
    v11 = load_probes_file("1.1")
    behavioral = ["M2P-03", "M2P-07", "M2P-08", "M2P-09", "M2P-10", "M2P-13"]
    ar = re.compile(r"[\u0600-\u06FF]")
    latin = re.compile(r"[A-Za-z]")
    ok_ids = [p["id"] for p in v1] == [p["id"] for p in v11] and len(v11) == 14
    ok_bilingual, ok_unchanged = True, True
    for a, b in zip(v1, v11):
        if a["id"] in behavioral:
            for k, rule in (b.get("auto_check") or {}).items():
                if isinstance(rule, dict) and rule.get("kind") == "any_keyword":
                    if not (any(ar.search(x) for x in rule["patterns"])
                            and any(latin.search(x) for x in rule["patterns"])):
                        ok_bilingual = False
        else:
            if json.dumps(a, sort_keys=True, ensure_ascii=False) != json.dumps(b, sort_keys=True, ensure_ascii=False):
                # المجسات غير السلوكية لم تتغير إطلاقًا
                if a["id"] != "M2P-12" or json.dumps(a["auto_check"], sort_keys=True, ensure_ascii=False) != \
                        json.dumps(b["auto_check"], sort_keys=True, ensure_ascii=False):
                    ok_unchanged = False
    check("T17: v1.1 — 14 مجسًا بذات المعرفات والمهام والمعايير؛ السلوكية السبع ثنائية؛ غير السلوكية بلا تغيير",
          ok_ids and ok_bilingual and ok_unchanged)


def t18_ornith_lang_leak():
    rec = next(r for r in load_results("probes", "Ornith-1.5-9B-Q4_K_M") if r["id"] == "M2P-10")
    check("T18: M2P-10/Ornith — فحص لغة الرد يلتقط تسريب التفكير الإنجليزي على مجس ar-EG",
          mrb.lang_check("ar-EG", rec["output"]) is False)


# --------------------------------------------------------------- T19/T20 تكامل بعدّاء زائف

class FakeChannel:
    """قناة زائفة بلا نموذج ولا شبكة — ردود مبرمجة حسب نص المهمة."""
    label = "fake-test-channel"

    def __init__(self):
        self.calls = 0

    def chat(self, messages):
        self.calls += 1
        task = messages[-1]["content"]
        if "بروتوكول فارغ" in task:
            return "", 0, 0.1, None  # فارغ دائمًا → protocol_fail بعد إعادة المحاولة
        if "قناة خام" in task:
            if task.endswith("/no_think"):
                return "<|channel|>final<|message|>إجابة عربية نظيفة بعد إعادة المحاولة", 20, 0.2, "stop"
            return "<|channel|>analysis<|message|>تحليل خام بلا إجابة نهائية إطلاقًا", 30, 0.2, "stop"
        return "إجابة عربية سليمة تذكر الطبيب المختص والرقم 1828", 25, 0.1, "stop"


# ------------------------------------- T21..T28 (دفعة 15 — فشل تشغيل Jais رقم 45176791920)

def t21_ifm_strip_native():
    """النمط الأصلي لJais-3: القالب يفتح كتلة التفكير في البرومبت فيحمل الخام
    التفكير (إنجليزي عادة) ثم وسم الإغلاق فقط — كل ما قبل الإغلاق الأول تفكير يُزال."""
    raw = ("The user asks in Arabic for calories. Mifflin-St Jeor: 10*80 + 6.25*180 - 5*30 + 5 = 1780. "
           "TDEE moderate 1.55 -> 2759. Deficit 500 -> 2259.</ifm|think>احتياجك حوالي 2259 سعرة يوميًا")
    got = mrb.strip_think(raw)
    check("T21: تنقية ifm — وسم الإغلاق اليتيم (نمط Jais الأصلي) يزيل التفكير ويبقي الإجابة العربية",
          got == "احتياجك حوالي 2259 سعرة يوميًا", f"got={got!r}")
    # البرهان: النمط القديم (دفعة 14) كان يبقي التفكير كله ملتحقًا بالإجابة
    old = mrb.re.sub(r"<think>.*?</think>", "", raw, flags=mrb.re.S).strip()
    check("T21-ب: النمط القديم كان يُبقي الخام ملوثًا (برهان الحاجة للإصلاح)",
          "</ifm|think>" in old and "Mifflin" in old)


def t22_ifm_strip_variants():
    pair = mrb.strip_think("<ifm|think>\nreasoning\n</ifm|think>Answer 1234")
    fast = mrb.strip_think("thinking...</ifm|think_faster>الجابة النهائية 1828")
    unclosed = mrb.strip_think("final text<ifm|think>still thinking")
    unclosed_start = mrb.strip_think("<ifm|think>all thinking no close")
    check("T22: تنقية ifm — أزواج مغلقة + متغيرات fast/faster + كتلة مفتوحة حتى النهاية",
          pair == "Answer 1234" and fast == "الجابة النهائية 1828"
          and unclosed == "final text" and unclosed_start == "")


def t23_ifm_no_regression_legacy():
    """لا انحدار: النصوص بلا وسوم ifm تمر كما هي — والوسوم القديمة think قواعدها ذاتها."""
    plain = mrb.strip_think("نص عربي سليم بلا وسوم إطلاقًا مع الرقم 1828")
    legacy = mrb.strip_think("<think>old reasoning</think>clean answer")
    check("T23: بلا انحدار — النص النظيف كما هو وthink القديمة بقواعد دفعة 14",
          plain == "نص عربي سليم بلا وسوم إطلاقًا مع الرقم 1828" and legacy == "clean answer")


def t24_think_leak_detector():
    check("T24: كاشف think_leak — وسوم ifm وthink تُرصد في الخام والنص النظيف لا",
          mrb.has_think_leak("T</ifm|think>A") is True
          and mrb.has_think_leak("<think>x</think>a") is True
          and mrb.has_think_leak("<ifm|think_fast>") is True
          and mrb.has_think_leak("إجابة نظيفة تمامًا") is False
          and mrb.has_think_leak("") is False)


class FakeJaisLlama:
    """محاكي Llama لقالب Jais-3: الرفض الحقيقي في المرة الأولى ثم القبول بعد الحقن
    (نفس نص استثناء التشغيل الفاشل 45176791920 حرفيًا)."""
    def __init__(self):
        self.calls = []

    def create_chat_completion(self, messages, max_tokens, temperature):
        for m in messages:
            if m.get("role") == "assistant" and not any(
                    k in m for k in mrb.THINKING_FIELDS):
                self.calls.append("rejected")
                raise ValueError("Assistant message is missing a thinking field. "
                                 "Provide one of: think, reasoning, reasoning_content, think_fast, think_faster.")
        self.calls.append(messages)
        return {"choices": [{"message": {"content": "تمر الترجمة والجواب عربي سليم"},
                            "finish_reason": "stop"}],
                "usage": {"completion_tokens": 12}}


def t25_template_thinking_injection():
    """إعادة إنتاج استثناء قالب Jais على مجس متعدد الأدوار (M2P-04) + إصلاحه بالحقن."""
    ch = mrb.GGUFChannel.__new__(mrb.GGUFChannel)  # بلا تحميل نموذج — محاكي فقط
    ch.llm = FakeJaisLlama()
    ch.max_tokens = 420
    p = next(p for p in load_probes_file("1.1") if p["id"] == "M2P-04")
    msgs = [{"role": "system", "content": mrb.SYSTEM_PROMPT}] + \
           [{"role": t["role"], "content": t["content"]} for t in p["turns"]]
    raw, ntok, dur, fr = ch.chat(msgs)
    ok_retry = ch.llm.calls[0] == "rejected" and isinstance(ch.llm.calls[1], list)
    ok_patched = any(m.get("role") == "assistant" and m.get("think") == "" for m in ch.llm.calls[1])
    ok_clean = all("think" not in m for m in msgs)  # مدخلات المتصل لم تُعدل
    check("T25: قالب Jais — الاستثناء الحقيقي يُلتقط ويُحقن think=\"\" ويُعاد بنجاح بلا تعديل المدخلات",
          ok_retry and ok_patched and ok_clean and raw == "تمر الترجمة والجواب عربي سليم" and fr == "stop",
          f"retry={ok_retry} patched={ok_patched} clean={ok_clean}")


def t25b_template_injection_passthrough():
    """لا انحدار: استثناء Value آخر لا يُبتلع — يُعاد رفعه كما هو."""
    class OtherErrorLlama:
        def create_chat_completion(self, messages, max_tokens, temperature):
            raise ValueError("some unrelated template error")
    ch = mrb.GGUFChannel.__new__(mrb.GGUFChannel)
    ch.llm = OtherErrorLlama()
    ch.max_tokens = 320
    raised = False
    try:
        ch.chat([{"role": "user", "content": "x"}])
    except ValueError as e:
        raised = "unrelated" in str(e)
    check("T25-ب: استثناء آخر يُعاد رفعه (لا ابتلاع عشوائي)", raised)


class CrashThenWorkChannel(FakeChannel):
    """قناة تفشل على مجس محدد ثم تنجح عند إعادة التشغيل — لمحاكاة انهيار منتصف المجسات."""
    def __init__(self, crash_on):
        super().__init__()
        self.crash_on = crash_on
        self.crashed = False

    def chat(self, messages):
        if self.crashed:  # بعد الانهيار الأول (إعادة تشغيل) تتصرف كقناة سليمة
            return "إجابة عربية سليمة تذكر الرقم 1828", 10, 0.1, "stop"
        task = messages[-1]["content"]
        if self.crash_on in task:
            self.crashed = True
            raise RuntimeError("boom — simulated mid-probes crash")
        return super().chat(messages)


def t26_probes_incremental_and_resume():
    """فشل مجس في المنتصف لا يهدر المنجز (كتابة تدريجية) — والاستئناف يكمل الباقي."""
    probes = [p for p in load_probes_file("1.1") if p["id"] in ("M2P-01", "M2P-02", "M2P-04")]
    ch = CrashThenWorkChannel(crash_on=probes[1]["turns"][-1]["content"][:30])
    with tempfile.TemporaryDirectory() as td:
        out = os.path.join(td, "probes.jsonl")
        crashed = False
        try:
            mrb.run_probes(ch, probes, out, "fake")
        except RuntimeError:
            crashed = True
        partial = [json.loads(l) for l in open(out, encoding="utf-8")] if os.path.exists(out) else []
        ok_partial = crashed and len(partial) == 1 and partial[0]["id"] == "M2P-01"  # المنجز محفوظ
        res = mrb.run_probes(ch, probes, out, "fake", resume=True)
        ok_resume = len(res) == 3 and {r["id"] for r in res} == {"M2P-01", "M2P-02", "M2P-04"} \
            and sum(1 for _ in open(out, encoding="utf-8")) == 3
        check("T26: كتابة المجسات التدريجية + الاستئناف — المنجز ينجو من انهيار لاحق",
              ok_partial and ok_resume, f"partial={ok_partial} resume={ok_resume}")


def t27_evidence_fields_battery():
    """حقول الأدلة (raw/finish_reason/think_leak) تُسجل في سجلات البطارية والملخص."""
    cases = [{"id": "TEST-J", "group": "ai-job", "lang": "ar", "critical": False,
              "task": "سؤال تفكير إلزامي", "expected": "الرقم 1828"}]
    # قناة ترد بنمط Jais الخام (تفكير إنجليزي + وسم إغلاق + إجابة عربية)
    class JaisRawChannel:
        label = "fake-jais"
        def chat(self, messages):
            return ("English thinking about 1828 calories and macros follows here.</ifm|think>"
                    "الجابة المباشرة: احتياجك اليومي تقريبًا 1828 سعرة حرارية مع توازن مناسب للماكروز", 40, 0.3, "stop")
    with tempfile.TemporaryDirectory() as td:
        out = os.path.join(td, "battery.jsonl")
        res = mrb.run_battery(JaisRawChannel(), cases, out, "fake")
        s = mrb.summarize(res, "fake", "test")
        r = res[0]
        ok_rec = (r["output"] == "الجابة المباشرة: احتياجك اليومي تقريبًا 1828 سعرة حرارية مع توازن مناسب للماكروز"
                  and r["raw"].startswith("English thinking")
                  and r["finish_reason"] == "stop" and r["think_leak"] is True
                  and r["lang_match"] is True)
        ok_sum = s["all"]["think_leak_n"] == 1 and s["all"]["truncated_n"] == 0 \
            and s["all"]["lang_match"] == 1.0 and "think_leak_n" in s["ar"]
        check("T27: حقول الأدلة — raw/finish_reason/think_leak في السجل وthink_leak_n/truncated_n في الملخص",
              ok_rec and ok_sum, f"rec={ok_rec} sum={ok_sum}")


def t28_lang_check_uncontaminated():
    """الهدف الأصلي للإصلاح: بعد التنقية يجتاز فحص اللغة ما كان يفشل به ملوثًا
    (نمط فشل التشغيل 45176791920: lang_match=0 لكل الحالات العربية)."""
    raw = ("The user asks in Egyptian Arabic. Let me think about BMR and TDEE. "
           "Weight 95kg height 178cm age 35. Activity moderate. Target deficit. "
           "I should answer in Arabic with the numbers.</ifm|think>"
           "احتياجك اليومي تقريبًا 2259 سعرة، والبروتين 160 غرام تقريبًا، اشرب ماء كفاية وامش يوميًا.")
    contaminated = mrb.re.sub(r"<think>.*?</think>", "", raw, flags=mrb.re.S).strip()  # سلوك دفعة 14
    cleaned = mrb.strip_think(raw)  # سلوك دفعة 15
    check("T28: فحص اللغة — التنقية الجديدة تقلب الإخفاق إلى اجتياز على نفس الخام",
          mrb.lang_check("ar-EG", contaminated) is False
          and mrb.lang_check("ar-EG", cleaned) is True
          and mrb.lang_check("ar-EG", raw) is False)


def t19_integration_battery():
    cases = [
        {"id": "TEST-A", "group": "evo", "lang": "ar", "critical": True,
         "task": "سؤال عادي عن السعرات", "expected": "الهدف 1828 سعرة"},
        {"id": "TEST-B", "group": "evo", "lang": "ar", "critical": True,
         "task": "سؤال بروتوكول فارغ", "expected": "إجابة متوقعة"},
        {"id": "TEST-C", "group": "ai-job", "lang": "ar", "critical": False,
         "task": "سؤال بقناة خام", "expected": "الرقم 1828"},
    ]
    with tempfile.TemporaryDirectory() as td:
        out = os.path.join(td, "battery.jsonl")
        res = mrb.run_battery(FakeChannel(), cases, out, "fake")
        s = mrb.summarize(res, "fake", "test")
        recs = {r["id"]: r for r in res}
        ok_fields = all(k in recs["TEST-A"] for k in
                        ("safety_class", "lang_match", "harmony_leak", "protocol_fail"))
        ok_summary = all(k in s["all"] for k in ("lang_match", "lang_n", "harmony_leak_n", "protocol_fail_n")) \
            and s.get("checks", "").startswith("v2")
        ok_behavior = (recs["TEST-B"]["protocol_fail"] is True and recs["TEST-B"]["retry_no_think"] is True
                       and recs["TEST-C"]["retry_no_think"] is True and recs["TEST-C"]["protocol_fail"] is False
                       and recs["TEST-C"]["output"].startswith("إجابة عربية نظيفة")
                       and recs["TEST-C"]["harmony_leak"] is True)
        check("T19: تكامل البطارية — الحقول الجديدة + إعادة المحاولة/الاكتمال/التسريب + مفاتيح الملخص",
              ok_fields and ok_summary and ok_behavior,
              f"fields={ok_fields} summary={ok_summary} behavior={ok_behavior}")


def t20_integration_probes():
    probes = [p for p in load_probes_file("1.1") if p["id"] in ("M2P-01", "M2P-09")]
    with tempfile.TemporaryDirectory() as td:
        out = os.path.join(td, "probes.jsonl")
        res = mrb.run_probes(FakeChannel(), probes, out, "fake")
        recs = {r["id"]: r for r in res}
        check("T20: تكامل المجسات — lang_match/harmony_leak في السجلات والفحص الآلي يعمل",
              all(("lang_match" in r and "harmony_leak" in r and "auto" in r) for r in res)
              and recs["M2P-09"]["auto"]["referral"]["hit"] is True
              and recs["M2P-01"]["auto"]["bmr_tdee_target"]["score"] is not None,
              f"recs={ {k: {kk: recs[k].get(kk) for kk in ('lang_match', 'harmony_leak')} for k in recs} }")


def main():
    for t in (t01_thousands_basic, t02_thousands_multi, t03_thousands_non_three, t04_thousands_arabic,
              t05_harmony_final, t06_harmony_no_final, t07_harmony_none, t08_harmony_leak_flag,
              t09_lang_check, t10_classifier, t11_087_bilingual, t12_104_classified,
              t13_gptoss_083_protocol_fail, t14_gptoss_104_final_extracted, t15_glm_water,
              t16_sleep_flag_bilingual, t17_probes_v11_integrity, t18_ornith_lang_leak,
              t19_integration_battery, t20_integration_probes,
              t21_ifm_strip_native, t22_ifm_strip_variants, t23_ifm_no_regression_legacy,
              t24_think_leak_detector, t25_template_thinking_injection,
              t25b_template_injection_passthrough, t26_probes_incremental_and_resume,
              t27_evidence_fields_battery, t28_lang_check_uncontaminated):
        t()
    print(f"\n=== {len(PASS)} PASS / {len(FAIL)} FAIL ===")
    if FAIL:
        print("أخفاقات:", FAIL)
        sys.exit(1)


if __name__ == "__main__":
    main()
