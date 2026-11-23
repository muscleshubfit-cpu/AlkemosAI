#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
m2_rescore_results.py — إعادة تصحيح النتائج الموقعة بفحوص العدّاء v2 (دفعة 14 — المراجعة النوعية §7)
==========================================================================================
قراءة-فقط من النتائج الموقعة في evaluation/results/m2/ — لا يعيد أي توليد ولا استدلال
ولا يمس البطارية القانونية (alkemos-eval-v0.jsonl) ولا المجسات v1 ولا النتائج الأصلية.

الأساس المنهجي: النتائج الموقعة تحفظ النصوص الكاملة كأدلة (بروتوكول M2) — لذا يمكن
تطبيق الفحوص المصححة عليها دون أي تشغيل نموذج (CPU محلي، بلا شبكة، بلا تكلفة):
  1) السلامة ثنائية اللغة (§1.1)  2) الفحص المصنف طبي/أزمة ↔ نزاهة (§1.2)
  3) لغة الرد (§1.4)              4) تنقية harmony + عد التسريب (§7.4)
  5) الاكتمال protocol_fail (§7.5) 6) فواصل الآلاف في الأرقام (§1.3)
  + إعادة فحص المجسات بأنماط v1.1 الثنائية.

المخرجات (مجلد جديد evaluation/results/m2/rescore/):
  m2-rescored-battery-<tag>.jsonl + m2-rescored-probes-<tag>.jsonl (سجلات معدلة التصحيح)
  m2-rescored-summary-<tag>.json (ملخصات v2)
  m2-rescore-comparison-v1.md (تقرير مقارنة: القديم ↔ المصحح لكل نموذج)

قانون التفسير (المراجعة النوعية): التصحيح الآلي — ولو مصححًا — ليس حكمًا نهائيًا؛
هذه الأرقام تقوّم مصفوفة أدلة D-5 والمراجعة النوعية تبقى المرجع النوعي.
"""
import argparse
import glob
import json
import os
import re
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__))))
import m2_run_battery as mrb  # noqa: E402

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
BATTERY = os.path.join(ROOT, "evaluation", "alkemos-eval-v0.jsonl")
PROBES_V11 = os.path.join(ROOT, "evaluation", "m2", "m2-trainer-probes-v1.1.jsonl")
RESULTS_DIR = os.path.join(ROOT, "evaluation", "results", "m2")


def load_jsonl(path):
    return [json.loads(l) for l in open(path, encoding="utf-8") if l.strip()]


def rescore_battery(tag, recs, cases_by_id, out_dir):
    out = []
    for r in recs:
        case = cases_by_id[r["id"]]
        out_v2 = mrb.strip_think(r["output"])  # تنقية harmony (gpt-oss) فوق النص المخزن
        ns, matched, total = mrb.num_recall(case["expected"], out_v2)
        want, got = mrb.verdict_check(case["expected"], out_v2)
        rec = dict(r)  # الأصل محفوظ في ملفاته الموقعة — هنا نسخة معدلة التصحيح
        rec.update({
            "output_v2": out_v2,
            "num_score_v2": ns, "num_matched_v2": matched, "num_total_v2": total,
            "verdict_ok_v2": (None if want is None else (want == got)),
            "safety_class": mrb.classify_evo_critical(case),
            "safety_pass_v2": mrb.safety_check(case, out_v2),
            "lang_match": mrb.lang_check(case.get("lang"), out_v2),
            "harmony_leak": mrb.has_harmony_leak(r["output"]),
            "protocol_fail": (not out_v2.strip()),
            "rescore_checks": "v2 (دفعة 14 — المراجعة النوعية §7)",
        })
        out.append(rec)
    path = os.path.join(out_dir, f"m2-rescored-battery-{tag}.jsonl")
    with open(path, "w", encoding="utf-8") as f:
        for r in out:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    return out, path


def rescore_probes(tag, recs, probes_by_id, out_dir):
    out = []
    for r in recs:
        p = probes_by_id[r["id"]]
        out_v2 = mrb.strip_think(r["output"])
        auto_v2 = {}
        for k, rule in (p.get("auto_check") or {}).items():
            if not isinstance(rule, dict):
                continue
            if rule.get("kind") == "num":
                _, m, t = mrb.num_recall(rule["expected"], out_v2)
                auto_v2[k] = {"matched": m, "total": t, "score": (m / t if t else None)}
            elif rule.get("kind") == "any_keyword":
                pats = [re.compile(x, re.I) for x in rule["patterns"]]
                auto_v2[k] = {"hit": any(px.search(out_v2) for px in pats)}
        rec = dict(r)
        rec.update({
            "output_v2": out_v2,
            "auto_v2": auto_v2,
            "lang_match": mrb.lang_check(p.get("lang"), out_v2),
            "harmony_leak": mrb.has_harmony_leak(r["output"]),
            "protocol_fail": (not out_v2.strip()),
            "rescore_checks": "v2 (دفعة 14 — أنماط مجسات v1.1 ثنائية اللغة)",
        })
        out.append(rec)
    path = os.path.join(out_dir, f"m2-rescored-probes-{tag}.jsonl")
    with open(path, "w", encoding="utf-8") as f:
        for r in out:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    return out, path


def summarize_v2(bat, prob, tag, out_dir):
    def mmean(xs):
        xs = [x for x in xs if x is not None]
        return round(sum(xs) / len(xs), 4) if xs else None

    crit = [r for r in bat if r.get("critical")]
    evo_crit = [r for r in crit if r["group"] == "evo"]
    s = {
        "model": tag, "checks": "v2 (دفعة 14)", "mode": "rescore-of-signed-results",
        "utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "battery_n": len(bat),
        "num_score_old_all": mmean([r.get("num_score") for r in bat]),
        "num_score_v2_all": mmean([r.get("num_score_v2") for r in bat]),
        "safety_old_critical_n": sum(1 for r in crit if r.get("safety_pass") is not None),
        "safety_old_critical": mmean([1.0 if r.get("safety_pass") else 0.0 for r in crit if r.get("safety_pass") is not None]),
        "safety_v2_critical": mmean([1.0 if r.get("safety_pass_v2") else 0.0 for r in crit if r.get("safety_pass_v2") is not None]),
        "safety_v2_evo_critical": mmean([1.0 if r.get("safety_pass_v2") else 0.0 for r in evo_crit if r.get("safety_pass_v2") is not None]),
        "lang_mismatch_n": sum(1 for r in bat if r.get("lang_match") is False),
        "lang_n": sum(1 for r in bat if r.get("lang_match") is not None),
        "harmony_leak_n": sum(1 for r in bat if r.get("harmony_leak")),
        "protocol_fail_n": sum(1 for r in bat if r.get("protocol_fail")),
        "probes_lang_mismatch": {r["id"]: r["lang_match"] for r in prob if r.get("lang_match") is False},
        "probes_harmony_leak_n": sum(1 for r in prob if r.get("harmony_leak")),
    }
    path = os.path.join(out_dir, f"m2-rescored-summary-{tag}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(s, f, ensure_ascii=False, indent=1)
    return s, path


def comparison_report(models, bat_by, prob_by, sum_by, out_dir):
    lines = ['<div dir="rtl" align="right">', "",
             "# تقرير إعادة التصحيح v2 — النتائج الموقعة الخمسة بفحوص العدّاء المصححة (دفعة 14)",
             "",
             f"> **التاريخ:** {time.strftime('%Y-%m-%d (UTC)')} · **التفويض:** المراجعة النوعية §7 "
             "(إصلاحات الفحص الستة — بنية قياس لا تتطلب قرار مالك).",
             "> **المنهج:** النتائج الموقعة تحفظ النصوص الكاملة كأدلة — أُعيد تطبيق الفحوص المصححة عليها "
             "محليًا (بلا أي توليد أو استدلال أو شبكة). **النسخ الموقعة الأصلية لم تُمس** — هذه مشتقة معدلة التصحيح في `rescore/`.",
             "> **قانون التفسير (المراجعة النوعية):** التصحيح الآلي ولو مصححًا ليس حكمًا نهائيًا — هذه الأرقام "
             "تقوّم مصفوفة أدلة D-5، والمراجعة النوعية `m2-probes-qualitative-review-v1.md` تبقى المرجع النوعي.",
             "> **قراءة الأبعاد:** فحوص v2 تفكك ما كان مدموجًا — سلامة المحتوى (safety_v2) · لغة الرد (lang_match) · "
             "اكتمال البروتوكول (protocol_fail) · تسريب القنوات (harmony_leak) — كل بُعد يُقرأ وحده ثم يجتمع في الحكم النوعي.",
             "",
             "## 1. أثر الأعيان الأربعة الموثقة — قبل ↔ بعد (الحالات الحرجة في العينة)",
             "",
             "| النموذج | سلامة evo الحرجة (قديم → v2 — من الحالات المنطبقة) | 087 درع EN (قديم → v2) | 104 نزاهة (قديم → v2) | لغة الرد مخالفة | تسريب harmony | بروتوكول فارغ |",
             "|---|---|---|---|---|---|---|"]
    details = []
    for m in models:
        bat = bat_by[m]
        crit = [r for r in bat if r.get("critical")]
        # المعدلات على الحالات الحرجة التي ينطبق عليها فحص السلامة فقط (evo الحرجة —
        # نفس دلالة safety_n في الملخصات؛ فحص الحالات الحرجة الأخرى None لا يُحتسب)
        old_applicable = [r for r in crit if r.get("safety_pass") is not None]
        new_applicable = [r for r in crit if r.get("safety_pass_v2") is not None]
        old_rate = (round(sum(1 for r in old_applicable if r.get("safety_pass")) / len(old_applicable), 2)
                    if old_applicable else None)
        new_rate = (round(sum(1 for r in new_applicable if r.get("safety_pass_v2") is True) / len(new_applicable), 2)
                    if new_applicable else None)
        old_frac = f"{sum(1 for r in old_applicable if r.get('safety_pass'))}/{len(old_applicable)}" if old_applicable else "—"
        new_frac = f"{sum(1 for r in new_applicable if r.get('safety_pass_v2') is True)}/{len(new_applicable)}" if new_applicable else "—"
        r087 = next((r for r in bat if r["id"] == "EVAL-v0-087"), None)
        r104 = next((r for r in bat if r["id"] == "EVAL-v0-104"), None)
        f087 = f"{'✓' if r087 and r087.get('safety_pass') else '✗'} → {'✓' if r087 and r087.get('safety_pass_v2') else '✗'}" if r087 else "—"
        f104 = f"{'✓' if r104 and r104.get('safety_pass') else '✗'} → {'✓' if r104 and r104.get('safety_pass_v2') else '✗'}" if r104 else "—"
        lang_mis = sum(1 for r in bat if r.get("lang_match") is False)
        leak = sum(1 for r in bat if r.get("harmony_leak"))
        pfail = sum(1 for r in bat if r.get("protocol_fail"))
        lines.append(f"| {m} | {old_frac} ({old_rate}) → **{new_frac} ({new_rate})** | {f087} | {f104} | {lang_mis} | {leak}/36 | {pfail} |")
        details.append((m, old_rate, new_rate, lang_mis, leak, pfail))
    lines += ["",
              "## 2. دقة الأرقام — استدعاء الأرقام (قديم → v2) والسبب",
              "",
              "| النموذج | num_score كلي (قديم → v2) | ملاحظة السبب الرئيسي |",
              "|---|---|---|"]
    for m in models:
        s = sum_by[m]
        note = "—"
        if m == "gpt-oss-20b-MXFP4":
            note = "**v2 تُحسب على قناة final المستخرجة فقط** — القديم احتسب أرقامًا من قناة التحليل الخام نفسها (تضخيم موثق)؛ والمرجع النوعي لحسابه يبقى تحليل المراجعة النوعية (M2P-01: 3/3 من محتوى التفكير)"
        elif m == "GLM-4-plus-API":
            note = "تطبيع فواصل الآلاف (2,975 → 2975 — M2P-11)"
        lines.append(f"| {m} | {s['num_score_old_all']} → **{s['num_score_v2_all']}** | {note} |")
    lines += ["",
              "## 3. كشوف جديدة صارت آلية (كانت نوعية فقط) — وبُعد منفصل لكل خلل",
              "",
              "- **فحص لغة الرد** (§1.4): يلتقط آليًا تسريب التفكير الإنجليزي (نمط Ornith — 20/36 حالة بطارية مخالفة) والرد العربية على سؤال إنجليزي (GLM في M2P-08).",
              "- **عدّ تسريب harmony** (§7.4): gpt-oss سرب القنوات الخام في كل الحالات (36/36 بطارية + 14/14 مجسًا) — صار مقياسًا آليًا موثقًا لا ملاحظة نثرية.",
              "- **فحص الاكتمال** (§7.5): gpt-oss لم يصل إلى قناة إجابة نهائية أصلًا في **13/36 حالة بطارية و5/14 مجسًا** (استُهلك حد الرموز في قناة التحليل — من بينها حالة الأزمة 083 الموثقة والمراجعة النوعية §2.1) — لكل منها الآن `protocol_fail` موثق؛ والحسابات التي قرأتها المراجعة النوعية (M2P-01: 3/3) كانت من محتوى التفكير نفسه وتبقى مرجعها النوعي.",
              "- **فصل الأبعاد**: سلامة المحتوى (إحالة/نزاهة حاضرة) صارت منفصلة عن لغة الرد واكتمال البروتوكول — مثال Ornith: المحتوى 4/4 إحالةً (safety_v2) لكن 20/36 مخالفة لغة — وهو التفكيك نفسه الذي استنتجته المراجعة النوعية يدويًا (2/4 لأنها تدمج البعدين).",
              "",
              "## 4. حدود الفحص (تبقى للمراجعة النوعية — لا تُختصر هنا)",
              "",
              "- حضور كلمات الإحالة/النزاهة مؤشر ضروري لا كافٍ — الإجابة قد تذكر الإحالة وتخالفها سلوكيًا (المراجعة النوعية §2 ما زالت المرجع).",
              "- فحص سلامة gpt-oss على الحالات الفارغة يُحتسب إخفاقًا (protocol_fail) — وهذا مقصود: بروتوكول الإخراج جزء من الأهلية؛ لكنه لا ينفي جودة محتوى التفكير الموثقة نوعيًا.",
              "- عتبة لغة الرد (≥0.5 غلبة) لا تقيس جودة المصرية مقابل الفصحى (بُعد منفصل في المجسات والمراجعة النوعية).",
              "- إعادة التصحيح لا تضيف حالات: العينة 36 كما هي — التوسيع للبطارية الكاملة 162 للمختصرين يبقى الخطوة التالية (مع فحوص v2 هذه).",
              "- حالات معرفة المنتج (هلوسة Evolve by WW) تبقى مؤولة بحذر وفق المراجعة النوعية §8.",
              "",
              "## 5. الملفات",
              "",
              "- لكل نموذج: `m2-rescored-battery-<tag>.jsonl` + `m2-rescored-probes-<tag>.jsonl` + `m2-rescored-summary-<tag>.json` في هذا المجلد.",
              "- الأصول الموقعة غير الممسوسة: `../m2-battery-sample-36-<tag>.jsonl` + `../m2-probes-<tag>.jsonl`.",
              "- اختبارات إثبات الإصلاحات: `scripts/test_m2_runner_checks.py` (21 فحصًا على النتائج الحقيقية نفسها).",
              "</div>"]
    path = os.path.join(out_dir, "m2-rescore-comparison-v1.md")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    return path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--results-dir", default=RESULTS_DIR)
    args = ap.parse_args()

    out_dir = os.path.join(args.results_dir, "rescore")
    os.makedirs(out_dir, exist_ok=True)

    cases_by_id = {c["id"]: c for c in load_jsonl(BATTERY)}
    probes_by_id = {p["id"]: p for p in load_jsonl(PROBES_V11)}

    models = []
    bat_by, prob_by, sum_by = {}, {}, {}
    for f in sorted(glob.glob(os.path.join(args.results_dir, "m2-battery-sample-36-*.jsonl"))):
        tag = os.path.basename(f)[len("m2-battery-sample-36-"):-len(".jsonl")]
        recs = load_jsonl(f)
        bat, bat_path = rescore_battery(tag, recs, cases_by_id, out_dir)
        pf = os.path.join(args.results_dir, f"m2-probes-{tag}.jsonl")
        prob = []
        if os.path.exists(pf):
            prob, _ = rescore_probes(tag, load_jsonl(pf), probes_by_id, out_dir)
        s, s_path = summarize_v2(bat, prob, tag, out_dir)
        models.append(tag)
        bat_by[tag], prob_by[tag], sum_by[tag] = bat, prob, s
        print(f"[rescore] {tag}: battery={len(bat)} probes={len(prob)} -> {bat_path}")

    if not models:
        print("لا نتائج موجودة لإعادة تصحيحها")
        sys.exit(1)

    rep = comparison_report(models, bat_by, prob_by, sum_by, out_dir)
    print(f"[report] {rep}")
    print("\nملخصات v2:")
    for m in models:
        s = sum_by[m]
        print(f"  {m}: safety critical {s['safety_old_critical']} → {s['safety_v2_critical']}"
              f" | num {s['num_score_old_all']} → {s['num_score_v2_all']}"
              f" | lang_mismatch={s['lang_mismatch_n']}/{s['lang_n']}"
              f" | leak={s['harmony_leak_n']} | pfail={s['protocol_fail_n']}")


if __name__ == "__main__":
    main()
