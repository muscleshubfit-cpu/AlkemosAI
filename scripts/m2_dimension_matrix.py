#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
مصفوفة الأبعاد العملية للمقارنة (دفعة 15 ختام — أمر المالك: مقارنة عملية تسبق أي توصية D-5).

قراءة-فقط على النتائج المخزنة في evaluation/results/m2/ — بلا أي توليد أو شبكة — حتمية بالكامل
(تشغيلان متطابقان بايتيًا). تُنتج:
  • evaluation/results/m2/compare/m2-dimension-matrix-v1.json
  • evaluation/results/m2/compare/m2-dimension-matrix-v1.md (جدول جاهز للاقتباس)

قانون الفصل (batch-15-report §8-أ): أبعاد المهام الخمسة مفصولة عن أبعاد البروتوكول —
الفحوص الآلية مؤشرات قياس محددة لا تقييم شامل للجودة، ولا يُنتج هنا أي اختيار نموذج
(D-5 قرار مالك حصرًا).

محددات الأبعاد (ميكانيكية موثقة على نص المهمة/الحقول — لا اجتهاد):
  • الحسابات: بنود البطارية ذات num_total>0 — متوسط num_score (v2 للخمسة الموقعة · v2.1 المسجل لـJais).
  • التغذية (الخطط): المجموعة plans (6 بنود) — معدل verdict_ok (v2/المسجل).
  • التمرين: بنود مهمتها تطابق [تدريب|تمرين|عضل|training|exercise|workout] — معدل verdict_ok (v2/المسجل).
  • تحليل الحالات (السلامة الحرجة): البنود الحرجة critical=True — معدل safety_pass (v2/المسجل).
  • التواصل العربي: بنود lang='ar' (21) — معدل lang_match.
أبعاد البروتوكول مفصولة: protocol_fail · harmony_leak · truncated (حيث الحقل متاح).
المجسات (بعيد مستقل): M2P-01 (v1.3) · M2P-04 (المسجل) · M2P-09 (المسجل) · M2P-10 (v1.3).
"""
import json, os, re

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
RES = os.path.join(ROOT, "evaluation", "results", "m2")
OUT_DIR = os.path.join(RES, "compare")
V13 = os.path.join(RES, "rescore", "m2-rescored-probes-v1.3.jsonl")

# (النموذج، ملف البطارية، ملف المجسات المسجلة، لاحقة الفحص الحالية)
MODELS = [
    ("Qwen3.5-9B-Q4_K_M",     "rescore/m2-rescored-battery-Qwen3.5-9B-Q4_K_M.jsonl",     "rescore/m2-rescored-probes-Qwen3.5-9B-Q4_K_M.jsonl",     "_v2"),
    ("Ornith-1.5-9B-Q4_K_M",  "rescore/m2-rescored-battery-Ornith-1.5-9B-Q4_K_M.jsonl",  "rescore/m2-rescored-probes-Ornith-1.5-9B-Q4_K_M.jsonl",  "_v2"),
    ("gemma-4-12b-it-Q4_K_M", "rescore/m2-rescored-battery-gemma-4-12b-it-Q4_K_M.jsonl", "rescore/m2-rescored-probes-gemma-4-12b-it-Q4_K_M.jsonl", "_v2"),
    ("gpt-oss-20b-MXFP4",     "rescore/m2-rescored-battery-gpt-oss-20b-MXFP4.jsonl",     "rescore/m2-rescored-probes-gpt-oss-20b-MXFP4.jsonl",     "_v2"),
    ("GLM-4-plus-API",        "rescore/m2-rescored-battery-GLM-4-plus-API.jsonl",        "rescore/m2-rescored-probes-GLM-4-plus-API.jsonl",        "_v2"),
    ("Jais-3-7B-Q4_K_M",      "m2-battery-sample-36-Jais-3-7B-Q4_K_M.jsonl",             "m2-probes-Jais-3-7B-Q4_K_M.jsonl",                       ""),
]
TRAIN_RE = re.compile(r"تدريب|تمرين|عضل|training|exercise|workout", re.I)


def cur(row, name, suffix):
    """قيمة الفحص الحالي: حقل _v2 إن وُجد وإلا الحقل المسجل (Jais v2.1 بلا لاحقة)."""
    v = row.get(name + suffix) if suffix else None
    return row.get(name) if v is None else v


def rate(vals):
    vals = [v for v in vals if v is not None]
    return (round(sum(1 for v in vals if v) / len(vals), 3), len(vals)) if vals else (None, 0)


def load(path):
    return [json.loads(l) for l in open(os.path.join(RES, path), encoding="utf-8") if l.strip()]


def main():
    v13 = {}
    for l in open(V13, encoding="utf-8"):
        if l.strip():
            r = json.loads(l)
            v13[(r["model"], r["id"])] = r

    out = {"generated_by": "scripts/m2_dimension_matrix.py (قراءة-فقط — حتمي)",
           "law": "أبعاد مفصولة — الفحوص الآلية مؤشرات محددة لا تقييم شامل — لا اختيار نموذج (D-5 للمالك)",
           "selectors": {
               "calc": "battery num_total>0 → mean num_score",
               "plans_nutrition": "group=='plans' → verdict_ok rate (6)",
               "training": "task ~ [تدريب|تمرين|عضل|training|exercise|workout] → verdict_ok rate",
               "case_safety": "critical==True → safety_pass rate",
               "arabic": "lang=='ar' (21) → lang_match rate",
           },
           "battery": {}, "probes": {}}

    for model, bfile, pfile, sfx in MODELS:
        rows = load(bfile)
        calc = [r for r in rows if (r.get("num_total") or 0) > 0]
        calc_scores = [cur(r, "num_score", sfx) for r in calc]
        plans = [r for r in rows if r.get("group") == "plans"]
        train = [r for r in rows if TRAIN_RE.search(r.get("task") or "")]
        crit = [r for r in rows if r.get("critical")]
        ar = [r for r in rows if r.get("lang") == "ar"]
        pr, pj = rate([cur(r, "verdict_ok", sfx) for r in plans])
        tr_, tj = rate([cur(r, "verdict_ok", sfx) if (r.get("num_total") or 0) == 0 else None for r in train])
        tn = [r for r in train if (r.get("num_total") or 0) > 0]
        tnum = [cur(r, "num_score", sfx) for r in tn]
        tnum_rate = round(sum(tnum) / len(tnum), 3) if tnum else None
        cr, cj = rate([cur(r, "safety_pass", sfx) for r in crit])
        arr, arj = rate([r.get("lang_match") for r in ar])
        out["battery"][model] = {
            "n_items": len(rows),
            "source": bfile + (f" (فحوص {'v2 معاد تصحيحها' if sfx else 'v2.1 مسجلة'})"),
            "calculations": {"items": len(calc), "judged": len(calc),
                             "mean_score": round(sum(calc_scores) / len(calc_scores), 3) if calc_scores else None,
                             "full": sum(1 for s in calc_scores if s is not None and s == 1.0)},
            "plans_nutrition": {"items": len(plans), "judged": pj, "verdict_ok_rate": pr,
                                "note": "5/6 بنود خطط حرة بلا حكم آلي (تُقاس نوعيًا) — الحكم الآلي على بند القبول/الرفض 113 حصرًا"},
            "training": {"items": len(train), "ids": [r["id"] for r in train],
                         "verdict_ok_rate": tr_, "verdict_judged": tj,
                         "numeric_rate": tnum_rate, "numeric_items": len(tn),
                         "note": "133 نطاقات التدريب (رقمي) + 138 حكم مقطع مغلوط (حكم) — بندا 051/129 بلا فحص آلي"},
            "case_safety_critical": {"items": len(crit), "judged": cj, "safety_pass_rate": cr,
                                     "note": "الفحص مطبق على الحالات المنطبقة حصرًا (حالات الأزمة/الإحالة في evo — 4 من 20 حرجة)؛ البقية حرجة لأسباب أخرى بلا فحص سلامة مسجل"},
            "arabic_communication": {"items": len(ar), "judged": arj, "lang_match_rate": arr},
            "protocol_separate": {
                "protocol_fail": sum(1 for r in rows if r.get("protocol_fail")),
                "harmony_leak": sum(1 for r in rows if r.get("harmony_leak")),
                "truncated": (sum(1 for r in rows if r.get("finish_reason") == "length")
                              if any("finish_reason" in r for r in rows) else None),
            },
        }

        probes = {r["id"]: r for r in load(pfile)}
        p01 = v13[(model, "M2P-01")]["auto_v1_3"]
        p10 = v13[(model, "M2P-10")]["auto_v1_3"]
        p04 = probes.get("M2P-04")
        p04src = p04.get("auto_v2") or p04.get("auto") or {} if p04 else {}
        p09 = probes.get("M2P-09")
        p09src = (p09.get("auto_v2") or p09.get("auto") or {}).get("referral", {}) if p09 else {}
        out["probes"][model] = {
            "M2P-01_calories": {"target": f"{p01['bmr_tdee_target']['matched']}/{p01['bmr_tdee_target']['total']}",
                                "macros": f"{p01['macros']['matched']}/{p01['macros']['total']}",
                                "detail_target": [d.get("got") for d in p01["bmr_tdee_target"]["detail"]]},
            "M2P-04_context_recall": {"matched": sum(v["matched"] for v in p04src.values()),
                                      "total": sum(v["total"] for v in p04src.values())},
            "M2P-09_referral": {"hit": bool(p09src.get("hit"))},
            "M2P-10_referral_v13": {"doctor": int(p10["doctor_coordination"]["hit"]),
                                    "dose_v13": int(p10["med_dose_warning"]["hit"]),
                                    "moderate": int(p10["moderate_approach"]["hit"])},
        }

    os.makedirs(OUT_DIR, exist_ok=True)
    jpath = os.path.join(OUT_DIR, "m2-dimension-matrix-v1.json")
    with open(jpath, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print(f"[written] {jpath}")

    # ---- جدول md
    lines = ["<div dir=\"rtl\" align=\"right\">", "",
             "# مصفوفة الأبعاد العملية v1 — ستة نماذج مقيسة (قراءة-فقط حتمية — دفعة 15 ختام)", "",
             "> مولّدة آليًا بـ`scripts/m2_dimension_matrix.py` من النتائج المخزنة حصرًا — بلا توليد. أبعاد مفصولة (قانون §8-أ) — الفحوص الآلية مؤشرات محددة لا تقييم شامل — لا اختيار نموذج هنا (D-5 للمالك).", "",
             "## 1. أبعاد المهام الخمسة — البطارية عينة 36", "",
             "| النموذج | الحسابات (متوسط استدعاء الأرقام) | التغذية/الخطط | التمرين | تحليل الحالات (سلامة حرجة) | التواصل العربي |", "|---|---|---|---|---|---|"]
    for model, *_ in MODELS:
        b = out["battery"][model]
        c = b["calculations"]
        calc = f"{c['mean_score']} ({c['full']}/{c['items']} كامل)" if c["mean_score"] is not None else "—"
        pl = b["plans_nutrition"]; tr = b["training"]; cs = b["case_safety_critical"]; arl = b["arabic_communication"]
        plv = f"{pl['verdict_ok_rate']} ({pl['judged']}/{pl['items']} مُقاسًا)" if pl["verdict_ok_rate"] is not None else f"— (0/{pl['items']})"
        trv = (f"حكم {tr['verdict_ok_rate']} ({tr['verdict_judged']}/{tr['items']}) · رقمي {tr['numeric_rate']} ({tr['numeric_items']})"
               if tr["verdict_ok_rate"] is not None else "—")
        csv = f"{cs['safety_pass_rate']} (مطبق على {cs['judged']} من {cs['items']} حرجة)" if cs["safety_pass_rate"] is not None else "—"
        arv = f"{arl['lang_match_rate']} ({arl['judged']}/{arl['items']})" if arl["lang_match_rate"] is not None else "—"
        lines.append(f"| {model} | {calc} | {plv} | {trv} | {csv} | {arv} |")
    lines += ["", "## 2. أبعاد البروتوكول — مفصولة (لا تدخل في درجات المهام)", "",
              "| النموذج | بروتوكول فارغ | تسريب harmony | مبتور |", "|---|---|---|---|"]
    for model, *_ in MODELS:
        p = out["battery"][model]["protocol_separate"]
        lines.append(f"| {model} | {p['protocol_fail']}/36 | {p['harmony_leak']}/36 | {p['truncated'] if p['truncated'] is not None else 'غير متاح (عدّاء قديم)'} |")
    lines += ["", "## 3. مجسات المدرب — بعيد مستقل (M2P-01/M2P-10 بفحوص v1.3 · M2P-04/M2P-09 المسجلة)", "",
              "| النموذج | M2P-01 هدف·ماكروز | M2P-04 سياق | M2P-09 إحالة | M2P-10 تنسيق·جرعات(v1.3)·معتدل |", "|---|---|---|---|---|"]
    for model, *_ in MODELS:
        p = out["probes"][model]
        lines.append(f"| {model} | {p['M2P-01_calories']['target']} · {p['M2P-01_calories']['macros']} | "
                     f"{p['M2P-04_context_recall']['matched']}/{p['M2P-04_context_recall']['total']} | "
                     f"{int(p['M2P-09_referral']['hit'])} | "
                     f"{p['M2P-10_referral_v13']['doctor']}·{p['M2P-10_referral_v13']['dose_v13']}·{p['M2P-10_referral_v13']['moderate']} |")
    lines += ["", "</div>"]
    mpath = os.path.join(OUT_DIR, "m2-dimension-matrix-v1.md")
    with open(mpath, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print(f"[written] {mpath}\n")
    print("\n".join(lines[8:18]))


if __name__ == "__main__":
    main()
