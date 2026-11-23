#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""M4 — دورة التعلم المرشحة: تشغيل E1+E2+E3 فوق مصادر خطط JSONL (مرشحون فقط).

الخطوة 2-3 من دورة التعلم السبعية (الخطة §4): تجميع حتمي بلا LLM + استخلاص
النموذج المرجعي + إشارات الاستبدال — والمخرجات «مرشحة» حصرًا: لا تدخل المعرفة
العامة (المستوى ب) إلا عبر بوابة G-K (للأنماط) أو بوابة G-EX (للنموذج المرجعي
وأمثلة التدريب) بتوقيع المالك — لا اعتماد تلقائي أبدًا.

المدخل:
  --input   ملف JSONL لصفوف المصادر (شكل NutritionPlanSource):
            {"origin": "plans|meal_plans|external_plans", "approved": bool,
             "goalText": str|null, "content": {...}, "totals": {...}|null}
  --swaps   (اختياري) ملف JSONL لأحداث الاستبدال: {"old": {...}, "new": {...}}
  --out     مسار تقرير المرشحين (الافتراضي: memory/inbox/learning/<تاريخ>-<بصمة8>-candidates.md)

حدود الأمان:
- أداة قراءة-فقط فوق ملفات يعدها المتصل — لا تلمس EVO ولا أي قاعدة بيانات.
- أرضية الصدق محكومة داخل الوحدات النقية (sample_size ≥ 3 للتجميعات).
- النص الحر (overview/notes) لا يدول أبدًا — مجهولية بالبناء (تدقيق §3).

الخروج: 0 نظيف (مع أو بلا مرشحين) · 1 خطأ مدخل.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from engine.learning import nutrition as nut  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parent.parent


def _utc_today() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _read_jsonl(path: Path) -> list:
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            rows.append(json.loads(line))
    return rows


def run_cycle(sources: list, swap_events: list | None = None):
    """تشغيل E1+E2+E3 فوق المصادر — يعيد (مسودات الأنماط، الهيكل المرجعي، دلاء الاستبدال)."""
    drafts = nut.aggregate_nutrition_patterns(sources)
    exemplar_src = nut.pick_exemplar_source(sources)
    skeleton = nut.build_exemplar_skeleton(exemplar_src["content"]) if exemplar_src else None
    swap_drafts = []
    for event in swap_events or []:
        diff = nut.diff_food_names(event.get("old"), event.get("new"))
        for ref in diff["removed"]:
            swap_drafts.append({"bucket": "swap_removed", "key": ref["key"],
                                "payload": {"count": 1, "display": ref["display"]}, "sample_size": 1})
        for ref in diff["added"]:
            swap_drafts.append({"bucket": "swap_added", "key": ref["key"],
                                "payload": {"count": 1, "display": ref["display"]}, "sample_size": 1})
    return drafts, skeleton, swap_drafts


def render_report(input_path: Path, input_sha: str, sources_count: int,
                  drafts: list, skeleton, swap_drafts: list, generated_at: str) -> str:
    lines = [
        '<div dir="rtl" align="right">',
        "",
        "# دورة تعلم مرشحة — تجميع E1/E2/E3 (M4)",
        "",
        f"> مولّد: `scripts/m4_learning_cycle.py` · التاريخ: **{generated_at} (UTC)** · المصادر: **{sources_count} خطة**",
        f"> المدخل: `{input_path.name}` @ sha256 `{input_sha[:16]}…` · الأداة قراءة-فقط ولا تلمس EVO.",
        "> **هذا التقرير «مرشح» حصرًا — لا يدخل المعرفة العامة إلا عبر بوابة G-K (الأنماط) أو بوابة G-EX (النموذج المرجعي) بتوقيع المالك — لا اعتماد تلقائي أبدًا.**",
        "",
    ]
    if not drafts:
        lines += ["- لا مسودات أنماط: المدخل دون أرضية الصدق (`sample_size ≥ 3`) أو بلا أرقام قابلة للاستخدام — العينة الرقيقة تُحجب ولا تُقدَّم كمعرفة.", ""]
    else:
        lines += [
            "## مسودات الأنماط (E1) — مرشحة لـ G-K",
            "",
            "| الدلو | المفتاح | حجم العينة | الحمولة |",
            "|---|---|---|---|",
        ]
        for d in sorted(drafts, key=lambda x: (x["bucket"], x["key"])):
            payload = json.dumps(d["payload"], ensure_ascii=False)
            lines.append(f"| `{d['bucket']}` | {d['key']} | {d['sample_size']} | `{payload}` |")
        lines.append("")
    if skeleton:
        lines += [
            "## النموذج المرجعي (E2) — مرشح لبوابة G-EX",
            "",
            "- **عينة واحدة لا تجميع** — دخوله المعرفة العامة مشروط بضوابط التجريد كاملة (حقول منظمة فقط بالبناء + فحص قائمة الحرمان + مراجعة بشرية + بوابة G-EX + توقيع مالك — الخطة §2-ب).",
            "- الهيكل (الشكل فقط — ممنوع نسخ أصنافه حرفيًا):",
            "",
            "```json",
            json.dumps(skeleton, ensure_ascii=False, indent=2),
            "```",
            "",
        ]
    else:
        lines += ["## النموذج المرجعي (E2)", "", "- لا خطة مؤهلة هذا الأسبوع (بنية ناقصة في كل المصادر).", ""]
    if swap_drafts:
        lines += [
            "## إشارات الاستبدال (E3) — مرشحة (عدّ واحد لكل حدث، أرضية الحقن 3)",
            "",
        ]
        for d in sorted(swap_drafts, key=lambda x: (x["bucket"], x["key"])):
            lines.append(f"- `{d['bucket']}` · {d['payload']['display']} (عدد مبدئي 1 — دون أرضية الحقن)")
        lines.append("")
    lines += [
        "---",
        "",
        "*أرضية الصدق محكومة داخل الوحدات النقية: كل تجميع دون 3 خطط حُجب تلقائيًا من هذا التقرير.*",
        "",
        "</div>",
        "",
    ]
    return "\n".join(lines)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="دورة التعلم المرشحة (E1+E2+E3) — مرشحون فقط")
    parser.add_argument("--input", required=True, help="ملف JSONL لمصادر الخطط")
    parser.add_argument("--swaps", default=None, help="ملف JSONL اختياري لأحداث الاستبدال")
    parser.add_argument("--out", default=None, help="مسار تقرير المرشحين")
    args = parser.parse_args(argv)

    input_path = Path(args.input)
    if not input_path.is_file():
        print(f"خطأ: ملف المدخل غير موجود: {input_path}", file=sys.stderr)
        return 1
    sources = _read_jsonl(input_path)
    swap_events = _read_jsonl(Path(args.swaps)) if args.swaps else []
    input_sha = hashlib.sha256(input_path.read_bytes()).hexdigest()
    generated_at = _utc_today()

    drafts, skeleton, swap_drafts = run_cycle(sources, swap_events)

    if args.out:
        out_path = Path(args.out)
    else:
        inbox = REPO_ROOT / "memory" / "inbox" / "learning"
        inbox.mkdir(parents=True, exist_ok=True)
        out_path = inbox / f"{generated_at}-{input_sha[:8]}-candidates.md"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        render_report(input_path, input_sha, len(sources), drafts, skeleton, swap_drafts, generated_at),
        encoding="utf-8",
    )
    print(f"دورة التعلم المرشحة: {len(sources)} مصدرًا → {len(drafts)} مسودة أنماط · "
          f"{'هيكل مرجعي واحد' if skeleton else 'بلا هيكل مرجعي'} · {len(swap_drafts)} إشارة استبدال")
    print(f"التقرير (مرشح فقط): {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
