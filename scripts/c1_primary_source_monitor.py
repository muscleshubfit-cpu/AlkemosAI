#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
C1 — مراقب المصدر الأساسي (ADR-0012) — قراءة-فقط عبر GitHub API العام.

القوانين الملزمة (research/README + FOUNDATION_INSTRUCTIONS §3 + PLAN §5.2):
- قراءة-فقط دائمًا للمصدر الأساسي (muscleshubfit-cpu/alkemos-aws) — لا كتابة إلى أي نظام تابع لـAlkemos.
- لا أسرار ولا مفاتيح: واجهة عامة بلا مصادقة في سير عمل عام (R-35).
- المخرجات «مرشحة» فقط: digest لكل دفعة معالجة في research/source-watch/digests/
  والمسارات المعرفية وحدها تدخل memory/inbox/monitor/ — الاعتماد عبر بوابة G-K فقط (لا اعتماد تلقائي أبدًا).
- لقطات المحتوى اليومية (musclehubeg-backups) غير مفعّلة — بانتظار قرار D-15.
- كل الطوابع UTC (ADR-0013).

قانون عدم الفقد (دفعة 7 — إصلاح جوهري بأمر المالك بعد اكتشاف عيب الاقتطاع الصامت):
1. لا يفقد أي التزام جديد مهما تجاوزت دفعته حد المعالجة (20) أو صفحة الجرد (50):
   الدفعات الكبيرة تُعالج من الأقدم إلى الأحدث على أجزاء من 20 التزامًا في التشغيل الواحد
   (حماية لحصة الواجهة غير المصادقة: 60 طلبًا/ساعة)، وما لم يُعالج يبقى فوق المؤشر
   فيجمعه التشغيل المجدول التالي تلقائيًا (كل 6 ساعات UTC أو يدويًا) — بلا اقتطاع وبلا تكرار.
2. المؤشر (state.last_seen_sha) لا يتقدم إلا إلى أحدث التزام عولج فعلًا بالكامل
   (تفاصيله منشورة داخل digest)، فلا يقفز فوق أي التزام غير معالج أبدًا —
   هذا هو الضمان الهيكلي: كل التزام أحدث من المؤشر مضمون المعالجة لاحقًا،
   وكل التزام عولج لا يُعاد ولا يُفقد.
3. إذا تجاوز الرصيد غير المعالج سقف الجرد (30 صفحة × 50 = 1,500 التزامًا) أو اختفى المؤشر
   (إعادة كتابة تاريخ المصدر) تُوثق «فجوة صريحة» بنطاقها الدقيق في state.json وفي الـdigest —
   لا اقتطاع صامت أبدًا.

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
MAX_DETAIL_CALLS = 20                            # أقصى التزامات تُعالج تفاصيلها في التشغيل الواحد (حصة الواجهة غير المصادقة)
LIST_PAGE = 50                                   # حجم صفحة جرد الالتزامات من الواجهة
MAX_LIST_PAGES = 30                              # سقف صفحات الجرد في التشغيل (1,500 التزامًا) — بعده فجوة موثقة لا اقتطاع صامت

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

def fetch_commits(last_seen):
    """جرد الالتزامات بصفحات (الأحدث أولًا) حتى العثور على المؤشر أو بلوغ السقف.

    يعيد (commits, anchor_found): commits مرتبة من الأحدث إلى الأقدم (بلا تكرار)،
    وanchor_found=True إذا وُجد المؤشر داخل النطاق المجرود.
    خط الأساس (لا مؤشر بعد): صفحة واحدة تكفي — HEAD فقط.
    """
    commits = []
    anchor_found = False
    max_pages = 1 if last_seen is None else MAX_LIST_PAGES
    for page in range(1, max_pages + 1):
        batch = api_get(f"{API}/commits?per_page={LIST_PAGE}&page={page}")
        if not batch:
            break
        commits.extend(batch)
        if last_seen and any(c["sha"] == last_seen for c in batch):
            anchor_found = True
            break
        if len(batch) < LIST_PAGE:
            break  # نهاية التاريخ ولم يُعثر على المؤشر (إعادة كتابة تاريخ محتملة)
    # إزالة أي تكرار (قد تتزحزح الصفحات إذا دُفعت التزامات أثناء الجرد — قانون عدم الفقد يغطيها)
    seen = {}
    for c in commits:
        seen.setdefault(c["sha"], c)
    return list(seen.values()), anchor_found

def main() -> int:
    state = json.loads(STATE_PATH.read_text(encoding="utf-8"))
    last_seen = state.get("last_seen_sha")
    run_utc = utc_now_iso()

    commits, anchor_found = fetch_commits(last_seen)
    if not commits:
        print("المصدر الأساسي بلا التزامات — لا شيء للفحص.")
        return 0
    head = commits[0]

    if last_seen == head["sha"]:
        print(f"لا جديد — HEAD ما زال {head['sha'][:7]} (قراءة-فقط، لا تغييرات تُحفظ).")
        return 0

    baseline = last_seen is None
    gap = None

    if baseline:
        # خط الأساس (أول تشغيل): HEAD فقط — التاريخ الكامل موثق في المصدر نفسه
        new_commits = [head]
    elif anchor_found:
        # اجمع الجديد كاملًا: من الأحدث نزولًا حتى المؤشر (دونه) — مهما كان العدد
        new_commits = []
        for c in commits:
            if c["sha"] == last_seen:
                break
            new_commits.append(c)
    else:
        # المؤشر خارج نطاق الجرد (>1,500 التزامًا جديدًا) أو اختفى (إعادة كتابة تاريخ):
        # عالج الأحدث 20 وقف المؤشر عند الرأس (عولج بالكامل ضمنها) ووثق فجوة صريحة بنطاقها — لا اقتطاع صامت.
        new_commits = commits
        window_full = len(commits) >= MAX_LIST_PAGES * LIST_PAGE
        gap = {
            "detected_utc": run_utc,
            "previous_anchor_sha": last_seen,
            "window_bottom_sha": commits[-1]["sha"] if commits else None,
            "first_unprocessed_sha": (commits[MAX_DETAIL_CALLS]["sha"]
                                      if len(commits) > MAX_DETAIL_CALLS else None),
            "reason": ("الرصيد الجديد تجاوز سقف الجرد (1,500) — الالتزامات من المؤشر السابق حتى "
                       "أقدم غير معالج تحتاج digest يدويًا واحدًا")
            if window_full
            else ("المؤشر السابق اختفى من تاريخ المصدر (إعادة كتابة تاريخ محتملة) — "
                  "قارن بالنطاق الموثق وأعد خط الأساس يدويًا إذا لزم"),
        }

    if gap:
        # وضع الفجوة: عالج الأحدث 20 (العلاقة بالمؤشر القديم غير معروفة فلا نعالج من الأسفل)
        to_process = new_commits[:MAX_DETAIL_CALLS]
    else:
        # الوضع الطبيعي: عالج الأقدم 20 الأقرب إلى المؤشر (اللحاق من الأقدم إلى الأحدث عبر التشغيلات)
        to_process = new_commits[-MAX_DETAIL_CALLS:]
    # قانون المؤشر (موحد في الحالتين): لا يتقدم إلا إلى أحدث التزام عولج فعلًا بالكامل —
    # الوضع الطبيعي: أعلى الجزء المعالج (وقد لا يكون الرأس بعد)؛ وضع الفجوة: الرأس نفسه (عولج ضمن الأحدث 20)
    cursor_sha = to_process[0]["sha"]
    remaining = len(new_commits) - len(to_process)

    # تفاصيل الملفات (بسقف حمايةً للحصة)
    details = []
    for c in to_process:
        d = api_get(f"{API}/commits/{c['sha']}")
        details.append({
            "sha": c["sha"],
            "date": commit_date_utc(c),
            "msg": (c.get("commit", {}).get("message") or "").splitlines()[0][:160],
            "files": [(f.get("filename", "?"), f.get("status", "?")) for f in d.get("files", [])],
        })

    newest = details[0]
    short = newest["sha"][:7]
    day = newest["date"][:10]

    # ============ digest (research/source-watch/digests/) ============
    DIGESTS_DIR.mkdir(parents=True, exist_ok=True)
    if baseline:
        rng = "خط الأساس (أول تشغيل)"
    elif gap:
        rng = (f"وضع فجوة موثقة: عولج الأحدث {len(to_process)} من {len(new_commits)} مجرودًا — "
               f"المؤشر تقدم إلى {cursor_sha[:7]} وفجوة موثقة أدناه")
    elif remaining > 0:
        rng = (f"من {last_seen[:7]} إلى {cursor_sha[:7]} — دفعة جزئية: عولج {len(to_process)} "
               f"من {len(new_commits)} جديدًا (المتبقي {remaining} يُعالج تلقائيًا في التشغيل التالي)")
    else:
        rng = f"من {last_seen[:7]} إلى {cursor_sha[:7]} — {len(new_commits)} جديدًا (اكتملت المعالجة)"
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
    if remaining > 0:
        lines.append("")
        lines.append(f"*(بقية الدفعة: {remaining} التزامًا أحدث من `{cursor_sha[:7]}` لم تُعالج بعد — "
                     f"المؤشر تقدم إلى `{cursor_sha[:7]}` فقط ولا يتجاوز أي التزام غير معالج، "
                     f"فيعالجها التشغيل المجدول التالي تلقائيًا [قانون عدم الفقد — دفعة 7].)*")
    if gap:
        fu = gap.get("first_unprocessed_sha")
        lines.append("")
        lines.append(f"> **تنبيه فجوة موثقة:** {gap['reason']}. "
                     f"النطاق غير المعالج: من المؤشر السابق `{gap['previous_anchor_sha'][:7]}` حتى أقدم التزام غير معالج "
                     f"`{fu[:7] if fu else '— (كل المجرود عولج)'}` "
                     f"(أعمق نقطة مجرودة: `{gap['window_bottom_sha'][:7] if gap['window_bottom_sha'] else '؟'}`) — "
                     f"مسجلة في `state.json` (`known_gaps`).")
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
    lines.append("- **قانون عدم الفقد (دفعة 7):** لا اقتطاع صامت — الدفعات الأكبر من 20 تعالج على أجزاء من الأقدم إلى الأحدث، والمؤشر لا يتقدم فوق أي التزام غير معالج.")
    lines.append("- لقطات المحتوى اليومية (musclehubeg-backups) **غير مفعّلة** — بانتظار تأكيد القائمة البيضاء (D-15).")
    lines.append("- كل الطوابع UTC (ADR-0013).")
    lines.append("")
    digest_path = DIGESTS_DIR / f"{day}-{short}.md"
    digest_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"digest: {digest_path.relative_to(ROOT)}")
    print(f"عولج هذا التشغيل: {len(to_process)} من {len(new_commits)} جديدًا · متبقٍ للتشغيلات التالية: {remaining}")

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
        if remaining > 0:
            ilines.append("")
            ilines.append(f"*(دفعة جزئية — {remaining} التزامًا أحدث تُعالج في التشغيل التالي وقد تضيف مرشحين.)*")
        if gap:
            ilines.append("")
            ilines.append(f"*(تنبيه: فجوة موثقة أدناه — راجع الـdigest و`state.json`.)*")
        ilines.append("")
        inbox_path = INBOX_DIR / f"{day}-{short}-candidates.md"
        inbox_path.write_text("\n".join(ilines) + "\n", encoding="utf-8")
        print(f"inbox:  {inbox_path.relative_to(ROOT)} ({len(cognitive)} ملفًا معرفيًا/حوكمة)")
    else:
        print("لا مسارات معرفية في هذه الدفعة — لا مرشحين.")

    # ============ تحديث الحالة — قانون المؤشر ============
    # لا يتقدم المؤشر إلا إلى أحدث التزام عولج فعلًا بالكامل (تفاصيله في الـdigest أعلاه).
    state["last_seen_sha"] = cursor_sha
    state["last_run_utc"] = run_utc
    if baseline:
        state["baseline_established_utc"] = run_utc
        state["baseline_sha"] = cursor_sha
    if gap:
        state.setdefault("known_gaps", []).append(gap)
    STATE_PATH.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"state:  last_seen_sha = {cursor_sha[:7]} (أحدث التزام عولج بالكامل — قانون عدم الفقد)")
    if gap:
        print(f"تحذير: فجوة موثقة في state.json (known_gaps) — {gap['reason']}")
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
