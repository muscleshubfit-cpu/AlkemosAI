#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# =============================================================================
# m2_kaggle_battery.py — دفتر قياس M2 على Kaggle GPU (فئة 20B+) — دفعة 14
# =============================================================================
# الغرض: قياس مرشحي الفئة 20B+ على بطارية AlkemosAI (عينة 36 أو الكاملة 162)
# عبر llama-cpp-python بتمرير GPU (T4×2) — دون أي أسرار (R-35):
# المستودع عام يُستنسخ بلا توكن، والنماذج عامة من HF بلا توكن.
#
# التشغيل (Kaggle → New Notebook → File → Import Script، أو لصق هذا الملف):
#   1) فعّل GPU T4×2 (Settings → Accelerator) والإنترنت (Settings → Internet ON)
#   2) عدّل MODEL_KEY في قسم الإعدادات أدناه (أو أضف نموذجًا بروابط مقيسة)
#   3) Run All — النتائج تُحفظ في /kaggle/working/m2-results/ + ملف مضغوط
#
# بعد الجلسة: نزّل الملف المضغوط وألحق ملفاته بمجلد evaluation/results/m2/
# في المستودع (بنفس تسمية سير GHA) — انظر docs/03-infrastructure/kaggle-m2-runbook.md
#
# القواعد النافذة: D-11 (مجاني حصرًا · لا تدريب أوزان · لا التزام مالي) ·
# R-41 (جدولة موسمية: تقييم M2 أولًا) · البطارية القانونية قراءة-فقط.
# =============================================================================

# ----------------------------- الإعدادات (عدّل هنا) --------------------------
MODEL_KEY = "qwen3.6-35b-a3b"   # من جدول MODELS أدناه
FULL_162 = False                 # False = عينة 36 · True = البطارية الكاملة 162
RESUME = True                    # استئناف تشغيل سابق إن وُجد ملف نتائج (R-41: انقطاع الجلسات)
REPO_SHA = ""                    # "" = main الحي · أو ثبّت SHA لغرض إعادة الإنتاج
N_CTX = 4096

# مرشحو الفئة 20B+ — روابط مقيسة حية من HF API بتاريخ 2026-11-23 (ترخيص + حجم بايت):
# (المصدر الموثق: references/sources-log.md §11 — أي تغيير وسم/حجم يُعاد قياسه وتوثيقه)
MODELS = {
    "qwen3.6-35b-a3b": {
        "alias": "Qwen3.6-35B-A3B-Q4_K_M",
        "url": "https://huggingface.co/unsloth/Qwen3.6-35B-A3B-GGUF/resolve/main/Qwen3.6-35B-A3B-UD-Q4_K_M.gguf",
        "size_bytes": 22134528992, "license": "apache-2.0", "params": "35.95B (MoE A3B)",
    },
    "qwen3.8-27b": {
        "alias": "Qwen3.8-27B-Q4_K_M",
        "url": "https://huggingface.co/unsloth/Qwen3.8-27B-GGUF/resolve/main/Qwen3.8-27B-UD-Q4_K_M.gguf",
        "size_bytes": 16564259744, "license": "apache-2.0", "params": "27.78B",
    },
    "gemma-4-26b-a4b": {
        "alias": "gemma-4-26B-A4B-it-Q4_K_M",
        "url": "https://huggingface.co/unsloth/gemma-4-26B-A4B-it-GGUF/resolve/main/gemma-4-26B-A4B-it-UD-Q4_K_M.gguf",
        "size_bytes": 16947541728, "license": "apache-2.0", "params": "26B (A4B)",
    },
    "jais-3-32b": {
        "alias": "Jais-3-32B-Q4_K_M",
        "url": "https://huggingface.co/IFM/Jais-3-32B-GGUF/resolve/main/Jais-3-32B-Q4_K_M.gguf",
        "size_bytes": 21075786688, "license": "apache-2.0", "params": "34.78B",
    },
    # (اختياري — نموذج مساعد صغير لاختبار فرضية D-5 الثنائية)
    "jais-3-7b": {
        "alias": "Jais-3-7B-Q4_K_M",
        "url": "https://huggingface.co/IFM/Jais-3-7B-GGUF/resolve/main/Jais-3-7B-Q4_K_M.gguf",
        "size_bytes": 5592226016, "license": "apache-2.0", "params": "9.0B",
    },
}
# -----------------------------------------------------------------------------

import glob
import json
import os
import shutil
import subprocess
import sys
import time

T0 = time.time()


def run(cmd, cwd=None, check=True, shell=False):
    print(f"\n$ {cmd if isinstance(cmd, str) else ' '.join(cmd)}", flush=True)
    r = subprocess.run(cmd, cwd=cwd, check=False, shell=shell)
    if check and r.returncode != 0:
        raise RuntimeError(f"فشل الأمر (رمز {r.returncode}): {cmd}")
    return r


def step(msg):
    print(f"\n{'=' * 70}\n== {msg}\n{'=' * 70}", flush=True)


# 1) توثيق البيئة (دراسة الموارد §5: قياس nvidia-smi أول الجلسة وتوثيقه)
step("1) توثيق GPU والبيئة (P100 مفردة لا تتسع لفئة 35B — يفضل T4×2)")
run("nvidia-smi", check=False)
run("nvcc --version || true", check=False, shell=True)

# 2) استنساخ المستودع (عام — بلا توكن — R-35)
step("2) استنساخ مستودع AlkemosAI (عام، بلا أسرار)")
REPO = "/tmp/AlkemosAI"
if os.path.exists(REPO):
    shutil.rmtree(REPO)
run(["git", "clone", "--depth", "1", "https://github.com/muscleshubfit-cpu/AlkemosAI.git", REPO])
if REPO_SHA:
    run(["git", "fetch", "--depth", "1", "origin", REPO_SHA], cwd=REPO)
    run(["git", "checkout", REPO_SHA], cwd=REPO)
print(open(os.path.join(REPO, "STATE.md"), encoding="utf-8").readline())

# 3) تثبيت llama-cpp-python بتمرير CUDA (عجلة مبنية مسبقًا أولًا ثم بناء من المصدر)
step("3) تثبيت llama-cpp-python (CUDA)")
try:
    import llama_cpp  # noqa: F401
    print("llama-cpp-python موجود مسبقًا")
except ImportError:
    installed = False
    for idx in ("cu124", "cu121"):
        r = run([sys.executable, "-m", "pip", "install", "--quiet", "--no-cache-dir",
                 "--extra-index-url", f"https://abetlen.github.io/llama-cpp-python/whl/{idx}",
                 "llama-cpp-python"], check=False)
        if r.returncode == 0:
            try:
                import llama_cpp  # noqa: F401
                print(f"ثُبت من العجلة المبنية مسبقًا ({idx})")
                installed = True
                break
            except Exception:
                continue
    if not installed:
        print("البناء من المصدر بتمرير CUDA (10–25 دقيقة)...")
        env = dict(os.environ, CMAKE_ARGS="-DGGML_CUDA=on", FORCE_CMAKE="1")
        r = subprocess.run([sys.executable, "-m", "pip", "install", "--no-cache-dir",
                            "--force-reinstall", "llama-cpp-python", "--no-binary", ":all:"],
                           env=env)
        if r.returncode != 0:
            raise RuntimeError("فشل تثبيت llama-cpp-python — راجع دليل التشغيل §استكشاف الأخطاء")
    import llama_cpp  # noqa: F401
print("llama-cpp-python جاهز")

# 4) تنزيل GGUF (عام — بلا توكن — استئناف تلقائي عند الانقطاع)
step("4) تنزيل النموذج (روابط مقيسة 2026-11-23)")
cfg = MODELS[MODEL_KEY]
gguf = f"/tmp/models/{cfg['alias']}.gguf"
os.makedirs("/tmp/models", exist_ok=True)
for attempt in range(4):
    run(["curl", "-sL", "--retry", "4", "--retry-delay", "5", "-C", "-", "-o", gguf, cfg["url"]], check=False)
    got = os.path.getsize(gguf) if os.path.exists(gguf) else 0
    if got >= cfg["size_bytes"] * 0.995:
        break
    print(f"تنزيل ناقص ({got/1e9:.2f}GB من {cfg['size_bytes']/1e9:.2f}GB) — إعادة المحاولة {attempt+1}/4")
else:
    raise RuntimeError(f"تعذر استكمال تنزيل {cfg['alias']} — أعد التشغيل (الاستئناف مدعوم بـ -C -)")
print(f"{cfg['alias']}: {os.path.getsize(gguf)/1e9:.2f}GB · ترخيص {cfg['license']} · {cfg['params']}")

# 5) تشغيل البطارية (عينة 36 أو 162) — فحوص v2 (دفعة 14) تعمل تلقائيًا
step(f"5) تشغيل البطارية ({'162 كاملة' if FULL_162 else 'عينة 36'}) + مجسات المدرب v1.1")
OUT = "/kaggle/working/m2-results"
os.makedirs(OUT, exist_ok=True)
common = ["--channel", "gguf", "--model", gguf, "--out-dir", OUT,
          "--tag", cfg["alias"], "--n-gpu-layers", "99", "--n-ctx", str(N_CTX)]
battery_cmd = [sys.executable, "scripts/m2_run_battery.py"] + common + \
    (["--full"] if FULL_162 else ["--sample-n", "36"]) + (["--resume"] if RESUME else [])
run(battery_cmd, cwd=REPO)
probes_cmd = [sys.executable, "scripts/m2_run_battery.py"] + common + ["--probes", "--max-tokens", "420"]
run(probes_cmd, cwd=REPO)

# 6) ضغط النتائج وتوثيق الجلسة
step("6) حفظ النتائج")
meta = {
    "model_key": MODEL_KEY, "alias": cfg["alias"], "url": cfg["url"],
    "size_bytes": cfg["size_bytes"], "license": cfg["license"],
    "full_162": FULL_162, "n_ctx": N_CTX, "repo_sha": REPO_SHA or "main@HEAD",
    "runner_checks": "v2 (دفعة 14 — المراجعة النوعية §7)",
    "probes": "v1.1 ثنائية اللغة",
    "utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    "elapsed_min": round((time.time() - T0) / 60, 1),
}
with open(os.path.join(OUT, "kaggle-session-meta.json"), "w", encoding="utf-8") as f:
    json.dump(meta, f, ensure_ascii=False, indent=1)
shutil.make_archive(f"/kaggle/working/m2-results-{cfg['alias']}", "zip", OUT)

print("\n" + "=" * 70)
print(f"تم في {meta['elapsed_min']} دقيقة — الملفات:")
for p in sorted(glob.glob(os.path.join(OUT, "*"))):
    print("  -", os.path.basename(p))
print(f"\nالمضغوط: /kaggle/working/m2-results-{cfg['alias']}.zip")
print("الخطوة التالية: ألحق الملفات بـ evaluation/results/m2/ في المستودع (دليل التشغيل §6).")
