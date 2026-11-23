#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
إعادة تصحيح مجسّي M2P-01/M2P-10 بفحوص v1.3 (دفعة 15 ختام — أمر المالك) — قراءة-فقط على النصوص المخزنة، بلا أي توليد.

الخلل المُصلَح حصرًا — med_dose_warning في M2P-10 (الإحالة الطبية):
  v1.2 كان يضيء التحذير بأي كلمة دوائية عامة («أدوية»، «علاجك»، «جرعة» مجردة، "medication"،
  "dose"، "meds"، "hypoglycem") — لكن ذكر الدواء لا يعني تحذير تغيير الجرعات.
  البرهان الفعلي (فحص الإجابة الفعلية): gpt-oss-20b M2P-10 سجّل dose=1 في v1.2 عبر
  «تتناول أدوية للسكري (مثلاً الإنسولين أو أدوية خفض الجلوكوز)» — ذكرُ أدويةٍ لا تحذيرَ جرعات:
  إيجابية زائفة. v1.3 تتطلب ربطًا صريحًا بين كلمة جرعة وفعل تغيير/تعديل/ضبط/مراجعة
  (أنماط مركّبة: «لا تغير جرعات أدويتك» · «تعديل الجرعة» · "adjust your dose" ...) —
  ولا تُعدل نصوص المجسات الـ14 ولا بقية الفحوص (doctor_coordination/moderate_approach كما هي).

الأساس النصي (الإجابة الفعلية المنقّاة — أدق دليل متاح لكل نموذج — نفس أساس v1.2 بلا تغيير):
  • النماذج الخمسة الموقعة: `output_v2` من evaluation/results/m2/rescore/m2-rescored-probes-<model>.jsonl
  • Jais-3-7B: `output` من evaluation/results/m2/m2-probes-Jais-3-7B-Q4_K_M.jsonl

الصنفات الصادقة لكل سجل (نفس منطق v1.2):
  • scored_on: "answer" | "thinking-only-no-answer" | "empty-no-answer" — لا قياس على غير الإجابة.
  • truncated: finish_reason=length.
  • auto_v1_3: الفحص المصحح · auto_v1_2_recorded: المسجل سابقًا في m2-rescored-probes-v1.2.jsonl
    (للتوثيق المباشر للانقلاب — المتوقع حصرًا: gpt-oss M2P-10 dose 1→0).

الخرج: evaluation/results/m2/rescore/m2-rescored-probes-v1.3.jsonl + جدول مقارنة على stdout.
"""
import json, os, re, sys

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, os.path.join(ROOT, "scripts"))
from m2_run_battery import num_recall, num_match_detail  # noqa: E402

PROBES_V13 = os.path.join(ROOT, "evaluation", "m2", "m2-trainer-probes-v1.3.jsonl")
RES = os.path.join(ROOT, "evaluation", "results", "m2")
PREV_V12 = os.path.join(RES, "rescore", "m2-rescored-probes-v1.2.jsonl")

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
OUT_PATH = os.path.join(RES, "rescore", "m2-rescored-probes-v1.3.jsonl")


def ar_ratio(t: str) -> float:
    if not t:
        return 0.0
    letters = [c for c in t if c.isalpha()]
    if not letters:
        return 0.0
    return sum(1 for c in letters if AR_RATIO.match(c)) / len(letters)


def apply_checks(probe, scoring_text):
    auto = {}
    for k, rule in (probe.get("auto_check") or {}).items():
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
            auto[k] = {"matched": m, "total": tt,
                       "score": (m / tt if tt else None), "detail": det}
        elif rule.get("kind") == "any_keyword":
            pats = [re.compile(x, re.I) for x in rule["patterns"]]
            hits = [x for x in pats if x.search(scoring_text)]
            auto[k] = {"hit": bool(hits), "matched_patterns": [h.pattern for h in hits]}
    return auto


def main():
    probes = {json.loads(l)["id"]: json.loads(l) for l in open(PROBES_V13, encoding="utf-8") if l.strip()}
    prev = {}
    for l in open(PREV_V12, encoding="utf-8"):
        if l.strip():
            r = json.loads(l)
            prev[(r["model"], r["id"])] = r.get("auto_v1_2") or {}
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
            # صادق مع نفسه (T33 يحمي هذا): الأساس هو النص المنقّى حصرًا — لا رجوع للنص الخام الملوث
            text = r.get(field) or ""
            fr = r.get("finish_reason") or ("protocol_fail" if r.get("protocol_fail") else None)
            lang = r.get("lang_match")
            ratio = ar_ratio(text)
            if not text.strip():
                scored_on = "empty-no-answer"
            elif ratio < 0.2:
                scored_on = "thinking-only-no-answer"
            else:
                scored_on = "answer"
            scoring_text = text if scored_on == "answer" else ""
            auto13 = apply_checks(p, scoring_text)
            rows.append({
                "model": model, "id": pid, "dim": p["dim"], "lang": p.get("lang"),
                "scored_text_source": field, "scored_on": scored_on,
                "finish_reason": fr, "truncated": (fr == "length"),
                "protocol_fail": bool(r.get("protocol_fail")),
                "lang_match": lang, "ar_ratio": round(ratio, 3),
                "auto_v1_3": auto13,
                "auto_v1_2_recorded": prev.get((model, pid), {}),
                "checks": "v1.3 (دفعة 15 ختام — إصلاح med_dose_warning: الكلمات العامة ليست دليل تحذير تغيير الجرعات — أنماط مركّبة — إعادة تصحيح قراءة-فقط على النصوص المخزنة)",
            })

    with open(OUT_PATH, "w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(f"[written] {OUT_PATH} — {len(rows)} سجلاً\n")

    # ---- جدول المقارنة على stdout (مع علامات الانقلاب مقابل v1.2 المسجل)
    print("| النموذج | المجس | اللغة المُسلَّمة | فحوص v1.3 | فحوص v1.2 المسجلة | الانقلاب |")
    print("|---|---|---|---|---|---|")
    for row in rows:
        a, b = row["auto_v1_3"], row["auto_v1_2_recorded"]
        flips = []
        if row["id"] == "M2P-01":
            bcur = a["bmr_tdee_target"]; mac = a["macros"]
            v13 = f"سعرات {bcur['matched']}/{bcur['total']} · ماكروز {mac['matched']}/{mac['total']}"
            pb = b.get("bmr_tdee_target", {}); pm = b.get("macros", {})
            if pb.get("matched") != bcur["matched"]:
                flips.append(f"سعرات {pb.get('matched')}→{bcur['matched']}")
            if pm.get("matched") != mac["matched"]:
                flips.append(f"ماكروز {pm.get('matched')}→{mac['matched']}")
            v12s = f"سعرات {pb.get('matched')} · ماكروز {pm.get('matched')}"
        else:
            dc, dw, mo = a["doctor_coordination"], a["med_dose_warning"], a["moderate_approach"]
            v13 = (f"تنسيق-طبي {int(dc['hit'])} · تحذير-جرعات {int(dw['hit'])} · معتدل {int(mo['hit'])}")
            pdw = b.get("med_dose_warning", {})
            for name, cur, old in (("تنسيق", dc, b.get("doctor_coordination", {})),
                                   ("جرعات", dw, pdw), ("معتدل", mo, b.get("moderate_approach", {}))):
                if old.get("hit") != cur["hit"]:
                    flips.append(f"{name} {int(bool(old.get('hit')))}→{int(cur['hit'])}")
            v12s = (f"تنسيق-طبي {int(bool(b.get('doctor_coordination', {}).get('hit')))} · "
                    f"تحذير-جرعات {int(bool(pdw.get('hit')))} · "
                    f"معتدل {int(bool(b.get('moderate_approach', {}).get('hit')))}")
        flag = "" if row["scored_on"] == "answer" else " — ⚠ بلا إجابة مسلّمة (" + row["scored_on"] + ") — الفحوص على لا شيء"
        if row["truncated"]:
            flag += " — ⚠ مبتور"
        flip = "، ".join(flips) if flips else "—"
        print(f"| {row['model']} | {row['id']} | ar_ratio={row['ar_ratio']}{flag} | {v13} | {v12s} | {flip} |")

    if flips_hint := [r for r in rows if any(
            (r["auto_v1_2_recorded"].get(k, {}).get("hit") if "hit" in r["auto_v1_2_recorded"].get(k, {}) else r["auto_v1_2_recorded"].get(k, {}).get("matched"))
            != (v["hit"] if "hit" in v else v["matched"])
            for k, v in r["auto_v1_3"].items())]:
        print(f"\n[flip] السجلات المتغيرة مقابل v1.2 المسجل: "
              + "، ".join(f"{r['model']}/{r['id']}" for r in flips_hint))


if __name__ == "__main__":
    main()
