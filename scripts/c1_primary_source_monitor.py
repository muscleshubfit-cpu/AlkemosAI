#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
C1 — مراقب المصدر الأساسي (ADR-0012) — قراءة-فقط عبر GitHub API العام.

القوانين الملزمة (research/README + FOUNDATION_INSTRUCTIONS §3 + PLAN §5.2):
- قراءة-فقط دائمًا للمصدر الأساسي (muscleshubfit-cpu/alkemos-aws) — لا كتابة إلى أي نظام تابع لـAlkemos.
- لا أسرار ولا مفاتيح: واجهة عامة بلا مصادقة في سير عمل عام (R-35).
- المخرجات «مرشحة» فقط: digest لكل دفعة commits في research/source-watch/digests/
  والمسارات المعرفية وحدها تدخل memory/inbox/monitor/ — الاعتماد عبر بوابة G-K فقط (لا اعتماد تلقائي أبدًا).
- لقطات المحتوى اليومية (musclehubeg-backups) غير مفعّلة — بانتظار قرار D-15.
- كل الطوابع UTC (ADR-0013).

الخروج: 0 = تشغيل نظيف (مع أو بلا digest جديد) · 1 = خطأ (يظهر في سجل Actions وتعيد الجدولة المحاولة).
"""
import json
import os
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

REPO = "muscleshubfit-cpu/alkemos-aws"          # المصدر الأساسي — قراءة-فقط
API = f"https://api.github.com/repos/{REPO}"
ROOT = Path(__file__).resolve().parents[1]       # جذر مستودع AlkemosAI
STATE_PATH = ROOT / "research/source-watch/state.json"
DIGESTS_DIR = ROOT / "research/source-watch/digests"
INBOX_DIR = ROOT / "memory/inbox/monitor"
MAX_DETAIL_CALLS = 20                            # سقف استدعاءات التفاصيل حمايةً لحصة الواجهة العامة
LIST_PAGE = 50                                   # أقصى التزامات تُفحص في التشغيل الواحد

# تصنيف المسارات (research/README ق3 — القرار النهائي للمراجعة البشرية دائمًا)
GOVERNANCE_FILES = {"STATE.md", "AGENTS.md", "worklog.md"}

def classify(path: str) -> str:
    if path in GOVERNANCE_FILES:
        return "حوكمة"
    if path.startswith("src/lib/"):
        return "معرفي-مرشح"      # كود المعرفة — أهليته المعرفية تحسمها المراجعة
    if path.startswith("docs/") and path.endswith(".md"):
        return "معرفي"
    if path.startswith("supabase/migrations/"):
        return "معرفي"
    return "غير-معرفي"           # يوثق في الـdigest ولا يدخل صناديق المراجعة

def api_get(url: str):
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "alkemosai-c1-monitor",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    # توكن اختياري عبر متغير بيئة فقط (للتشغيل المحلي عند تجاوز حصة IP) —
    # لا يُخزن في المستودع ولا يُضبط في سير العمل العام أبدًا (R-35 — لا أسرار في سير عام).
    token = os.environ.get("C1_GITHUB_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))

def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

def commit_date_utc(commit: dict) -> str:
    # طابع الالتزام في git هو المرجع عند أي التباس (ADR-0013)
    return (commit.get("commit", {}).get("committer", {}).get("date") or "").replace("Z", " UTC")

def main() -> int:
    state = json.loads(STATE_PATH.read_text(encoding="utf-8"))
    last_seen = state.get("last_seen_sha")

    commits = api_get(f"{API}/commits?per_page={LIST_PAGE}")
    if not commits:
        print("المصدر الأساسي بلا التزامات — لا شيء للفحص.")
        return 0
    head = commits[0]

    if last_seen == head["sha"]:
        print(f"لا جديد — HEAD ما زال {head['sha'][:7]} (قراءة-فقط، لا تغييرات تُحفظ).")
        return 0

    # اجمع الالتزامات الجديدة (من الأحدث إلى الأقدم حتى آخر SHA مُشاهد)
    new_commits = []
    truncated = False
    for c in commits:
        if c["sha"] == last_seen:
            break
        new_commits.append(c)
    if last_seen and not any(c["sha"] == last_seen for c in commits):
        truncated = True  # التزامات أكثر من صفحة الفحص — نأخذ الأحدث ونوثق الاقتطاع

    baseline = last_seen is None
    if baseline:
        new_commits = [head]  # خط الأساس: HEAD فقط — التاريخ الكامل موثق في المصدر نفسه

    # تفاصيل الملفات (بسقف حمايةً للحصة)
    details = []
    for c in new_commits[:MAX_DETAIL_CALLS]:
        d = api_get(f"{API}/commits/{c['sha']}")
        details.append({
            "sha": c["sha"],
            "date": commit_date_utc(c),
            "msg": (c.get("commit", {}).get("message") or "").splitlines()[0][:160],
            "files": [(f.get("filename", "?"), f.get("status", "?")) for f in d.get("files", [])],
        })
    skipped = len(new_commits) - len(details)

    newest = details[0]
    short = newest["sha"][:7]
    day = newest["date"][:10]
    run_utc = utc_now_iso()

    # ============ digest (research/source-watch/digests/) ============
    DIGESTS_DIR.mkdir(parents=True, exist_ok=True)
    rng = "خط الأساس (أول تشغيل)" if baseline else f"من {last_seen[:7]} إلى {short}"
    lines = []
    lines.append("---")
    lines.append(f"digest: {day}-{short}")
    lines.append(f"generated_utc: {run_utc}")
    lines.append(f"primary_source: {REPO} (قراءة-فقط)")
    lines.append(f"range: {rng}")
    lines.append("---")
    lines.append("")
    lines.append(f"# Digest — {rng}")
    lines.append("")
    lines.append("> **مرشحون فقط — لا اعتماد إلا عبر بوابة G-K** (مصدر موثق + لا تعارض غير محلول + إثبات إضافة + ثنائي اللغة — ADR-0017).")
    lines.append("")
    lines.append("## الالتزامات الجديدة")
    lines.append("")
    lines.append("| # | SHA | طابع الالتزام (UTC) | العنوان |")
    lines.append("|---|---|---|---|")
    for i, d in enumerate(details, 1):
        lines.append(f"| {i} | `{d['sha'][:7]}` | {d['date']} | {d['msg']} |")
    if skipped > 0:
        lines.append("")
        lines.append(f"*(اقتطاع: {skipped} التزامًا أقدم لم تُفحص تفاصيلها هذا التشغيل حمايةً لحصة الواجهة — تُغطى في الـdigest التالي أو يدويًا عند الحاجة.)*")
    if truncated:
        lines.append("")
        lines.append("*(تنبيه: عدد الالتزامات الجديدة تجاوز صفحة الفحص الواحدة — راجع تاريخ المصدر كاملًا عند الحاجة.)*")
    lines.append("")
    lines.append("## الملفات المصنفة")
    lines.append("")
    lines.append("| الالتزام | الملف | الحالة | التصنيف |")
    lines.append("|---|---|---|---|")
    cognitive = []
    for d in details:
        for fname, status in d["files"]:
            bucket = classify(fname)
            if bucket != "غير-معرفي":
                cognitive.append((d["sha"][:7], fname, bucket))
            lines.append(f"| `{d['sha'][:7]}` | `{fname}` | {status} | {bucket} |")
    lines.append("")
    lines.append("## حدود هذا التشغيل")
    lines.append("")
    lines.append("- قراءة-فقط عبر GitHub API العام — لا كتابة إلى أي نظام تابع لـAlkemos (ADR-0012).")
    lines.append("- لقطات المحتوى اليومية (musclehubeg-backups) **غير مفعّلة** — بانتظار تأكيد القائمة البيضاء (D-15).")
    lines.append("- كل الطوابع UTC (ADR-0013).")
    lines.append("")
    digest_path = DIGESTS_DIR / f"{day}-{short}.md"
    digest_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"digest: {digest_path.relative_to(ROOT)}")

    # ============ مرشحو المراجعة (memory/inbox/monitor/) ============
    if cognitive:
        INBOX_DIR.mkdir(parents=True, exist_ok=True)
        ilines = []
        ilines.append(f"# مرشحو المراجعة من المراقب — {day} (`{short}`)")
        ilines.append("")
        ilines.append(f"> المصدر: `research/source-watch/digests/{day}-{short}.md` · وُلّد {run_utc}")
        ilines.append("> **كل ما هنا «مرشح» — لا يعتمد شيء إلا عبر بوابة G-K** (فحص تعارض + مصدر + عينة + إثبات إضافة + فحص ثنائي اللغة).")
        ilines.append("")
        ilines.append("| الالتزام | الملف | التصنيف |")
        ilines.append("|---|---|---|")
        for sha7, fname, bucket in cognitive:
            ilines.append(f"| `{sha7}` | `{fname}` | {bucket} |")
        ilines.append("")
        inbox_path = INBOX_DIR / f"{day}-{short}-candidates.md"
        inbox_path.write_text("\n".join(ilines) + "\n", encoding="utf-8")
        print(f"inbox:  {inbox_path.relative_to(ROOT)} ({len(cognitive)} ملفًا معرفيًا/حوكمة)")
    else:
        print("لا مسارات معرفية في هذه الدفعة — لا مرشحين.")

    # ============ تحديث الحالة ============
    state["last_seen_sha"] = head["sha"]
    if baseline:
        state["baseline_established_utc"] = run_utc
        state["baseline_sha"] = head["sha"]
    STATE_PATH.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"state:  last_seen_sha = {head['sha'][:7]}")
    return 0

if __name__ == "__main__":
    try:
        sys.exit(main())
    except urllib.error.HTTPError as e:
        print(f"HTTP {e.code} من GitHub API — يُعاد بالمحاولة المجدولة التالية.", file=sys.stderr)
        sys.exit(1)
    except Exception as e:  # لا اجتهاد فوق المخطط — الفشل يُوثق في سجل Actions
        print(f"خطأ: {e}", file=sys.stderr)
        sys.exit(1)
