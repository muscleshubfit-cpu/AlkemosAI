#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
إعادة تصحيح المجسات المتأثرة بفحوص v1.2 (دفعة 15 — تتمة) — قراءة-فقط على النصوص المخزنة، بلا أي توليد.

المجسّان المتأثران (اللذان تغير فحصهما الآلي بين v1.1 وv1.2):
  • M2P-01 (ar-eg-calories): تسامح مطلق مضبوط لكل رقم (2/5/5 للسعرات و2/2/2 للماكروز)
    بدل تسامح 2% الفضفاض الذي مَرَّر تطابقات غير صحيحة موثقة (T29/T30).
  • M2P-10 (medical-referral): فحص الإحالة الطبية المصحح — doctor_coordination
    (بديل الفحص المسمى خطأً no_extreme_deficit الذي كان يحمل أنماط الطبيب) +
    med_dose_warning (جديد — غياب تحذير جرعات أدوية السكري لم يكن يُكشف إطلاقًا).

الأساس النصي (الإجابة الفعلية المنقّاة — أدق دليل متاح لكل نموذج):
  • النماذج الخمسة الموقعة: `output_v2` من evaluation/results/m2/rescore/m2-rescored-probes-<model>.jsonl
    (فحوص v2 — تنقية harmony/القنوات على الإجابات الفعلية).
  • Jais-3-7B: `output` من evaluation/results/m2/m2-probes-Jais-3-7B-Q4_K_M.jsonl
    (فحوص v2.1 — تنقية ifm-think المضمنة في العدّاء).

الصنفات الصادقة لكل سجل:
  • scored_on: "answer" إذا كان النص المسلَّم إجابة بلغة المجس فعلاً (نسبة عربية ≥0.2 للعربية)
    أو "thinking-only-no-answer" إذا كان النص المسلَّم تفكيرًا مسربًا بلا إجابة (مثل Ornith M2P-10
    المبتور عند 420 رمزًا) — فالمطابقات داخل التفكير لا تُعد إجابة.
  • truncated: finish_reason=length (النص مقطوع — ذيل الإجابة غير متاح للحكم).
  • نسبة العربية ar_ratio للشفافية.

الخرج: evaluation/results/m2/rescore/m2-rescored-probes-v1.2.jsonl (سجل لكل نموذج×مجس —
يحمل فحوص v1.2 بالتفصيل رقمًا رقمًا + فحوص v1.1 القديمة للمقارنة + الصنفات) وجدول مقارنة على stdout.
"""
import json, os, re, sys

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, os.path.join(ROOT, "scripts"))
from m2_run_battery import num_recall, num_match_detail  # noqa: E402

PROBES_V12 = os.path.join(ROOT, "evaluation", "m2", "m2-trainer-probes-v1.2.jsonl")
RES = os.path.join(ROOT, "evaluation", "results", "m2")

# (النموذج، مسار السجلات، حقل النص الفعلي المنقّى)
MODELS = [
    ("Qwen3.5-9B-Q4_K_M",     "rescore/m2-rescored-probes-Qwen3.5-9B-Q4_K_M.jsonl",     "output_v2"),
    ("Ornith-1.5-9B-Q4_K_M",  "rescore/m2-rescored-probes-Ornith-1.5-9B-Q4_K_M.jsonl",  "output_v2"),
    ("gemma-4-12b-it-Q4_K_M", "rescore/m2-rescored-probes-gemma-4-12b-it-Q4_K_M.jsonl", "output_v2"),
    ("gpt-oss-20b-MXFP4",     "rescore/m2-rescored-probes-gpt-oss-20b-MXFP4.jsonl",     "output_v2"),
    ("GLM-4-plus-API",        "rescore/m2-rescored-probes-GLM-4-plus-API.jsonl",        "output_v2"),
    ("Jais-3-7B-Q4_K_M",      "m2-probes-Jais-3-7B-Q4_K_M.jsonl",                       "output"),
]
AFFECTED = ["M2P-01", "M2P-10"]

AR_RATIO = re.compile(r"[\u0600-\u06FF]")
OUT_PATH = os.path.join(RES, "rescore", "m2-rescored-probes-v1.2.jsonl")


def ar_ratio(t: str) -> float:
    if not t:
        return 0.0
    letters = [c for c in t if c.isalpha()]
    if not letters:
        return 0.0
    return sum(1 for c in letters if AR_RATIO.match(c)) / len(letters)


def main():
    probes = {json.loads(l)["id"]: json.loads(l) for l in open(PROBES_V12, encoding="utf-8") if l.strip()}
    rows = []
    for model, path, field in MODELS:
        recs = {}
        for l in open(os.path.join(RES, path), encoding="utf-8"):
            if l.strip():
                r = json.loads(l)
                recs[r["id"]] = r
        for pid in AFFECTED:
            p, r = probes[pid], recs.get(pid)
            if r is None:
                continue
            # صادق مع نفسه (T33 يحمي هذا): الأساس هو النص المنقّى حصرًا — لا رجوع للنص الخام
            # الملوث إطلاقًا (في gpt-oss M2P-01 كان output_v2 فارغًا protocol_fail والرجوع
            # إلى output الأصلي كان سيبعث أرقام قناة التحليل الملوثة كـ«إجابة»).
            text = r.get(field) or ""
            fr = r.get("finish_reason") or ("protocol_fail" if r.get("protocol_fail") else None)
            lang = r.get("lang_match")
            ratio = ar_ratio(text)
            if not text.strip():
                scored_on = "empty-no-answer"      # بلا أي نص مسلَّم (protocol_fail)
            elif ratio < 0.2:
                scored_on = "thinking-only-no-answer"  # النص المسلَّم تفكير مسرب بلا إجابة بلغة المجس
            else:
                scored_on = "answer"
            # بلا إجابة فعلية → أي مطابقات في التفكير تُصفَّر (الإجابة الوحيدة الصادقة: لا شيء سُلِّم)
            scoring_text = text if scored_on == "answer" else ""
            auto12 = {}
            for k, rule in (p.get("auto_check") or {}).items():
                if not isinstance(rule, dict):
                    continue
                if rule.get("kind") == "num":
                    ta = None
                    if rule.get("tol_abs") is not None:
                        ta = [float(x) for x in str(rule["tol_abs"]).split()] \
                            if isinstance(rule["tol_abs"], str) else rule["tol_abs"]
                    if ta is not None:
                        _, m, tt = num_recall(rule["expected"], scoring_text, tol_abs=ta)
                        det = num_match_detail(rule["expected"], scoring_text, tol_abs=ta)
                    else:
                        _, m, tt = num_recall(rule["expected"], scoring_text)
                        det = num_match_detail(rule["expected"], scoring_text)
                    auto12[k] = {"matched": m, "total": tt,
                                 "score": (m / tt if tt else None), "detail": det}
                elif rule.get("kind") == "any_keyword":
                    pats = [re.compile(x, re.I) for x in rule["patterns"]]
                    hits = [x for x in pats if x.search(scoring_text)]
                    auto12[k] = {"hit": bool(hits), "matched_patterns": [h.pattern for h in hits]}
            rows.append({
                "model": model, "id": pid, "dim": p["dim"], "lang": p.get("lang"),
                "scored_text_source": field, "scored_on": scored_on,
                "finish_reason": fr, "truncated": (fr == "length"),
                "protocol_fail": bool(r.get("protocol_fail")),
                "lang_match": lang, "ar_ratio": round(ratio, 3),
                "auto_v1_2": auto12,
                "auto_v1_1_recorded": r.get("auto") or r.get("auto_v2") or {},
                "checks": "v1.2 (دفعة 15 تتمة — فحوص مصححة + تسامح مضبوط — إعادة تصحيح قراءة-فقط على النصوص المخزنة)",
            })

    with open(OUT_PATH, "w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(f"[written] {OUT_PATH} — {len(rows)} سجلاً\n")

    # ---- جدول المقارنة على stdout
    print("| النموذج | المجس | اللغة المُسلَّمة | فحوص v1.2 | فحوص v1.1 المسجلة |")
    print("|---|---|---|---|---|")
    for row in rows:
        a = row["auto_v1_2"]
        if row["id"] == "M2P-01":
            b = a["bmr_tdee_target"]; mac = a["macros"]
            v12 = f"سعرات {b['matched']}/{b['total']} ({b['detail']}) · ماكروز {mac['matched']}/{mac['total']}"
        else:
            v12 = (f"تنسيق-طبي {int(a['doctor_coordination']['hit'])} · "
                   f"تحذير-جرعات {int(a['med_dose_warning']['hit'])} · "
                   f"معتدل {int(a['moderate_approach']['hit'])}")
        v11 = json.dumps(row["auto_v1_1_recorded"], ensure_ascii=False)
        flag = "" if row["scored_on"] == "answer" else " — ⚠ بلا إجابة مسلّمة (" + row["scored_on"] + ") — الفحوص على لا شيء"
        if row["truncated"]:
            flag += " — ⚠ مبتور"
        print(f"| {row['model']} | {row['id']} | ar_ratio={row['ar_ratio']}{flag} | {v12} | {v11} |")


if __name__ == "__main__":
    main()
