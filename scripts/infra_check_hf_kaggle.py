#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
infra_check_hf_kaggle.py — فحص اتصال وصلاحيات Hugging Face وKaggle (دفعة 10 — ADR-0020)

قوانين هذا السكربت (ملزمة):
  1. قراءة-فقط: لا يستهلك أي موارد (لا توليد استدلال، لا GPU، لا كتابة في أي خدمة).
  2. لا أسرار في الكود: كل الاعتماديات من متغيرات البيئة فقط
     (HF_TOKEN, KAGGLE_USERNAME, KAGGLE_KEY) — ولا يطبع أي قيمة سرية أبدًا
     (الأسماء فقط، والحصص، وحالات الاستجابة) — R-35/SECURITY §1 و§8.
  3. الفحوص الصلبة (hard) تخفق السكربت عند فشلها؛ الفحوص المرنة (soft) تحذر فقط.

الفحوص:
  HF-1 (صلب)  : GET https://huggingface.co/api/whoami-v2 (Bearer)
                → صلاحية التوكن + اسم الحساب + امتلاك نطاق repo.write
  HF-2 (صلب)  : GET https://huggingface.co/api/models/Alkemos/alkemosai-weights (Bearer)
                → مستودع الأوزان الخاص موجود وخاص فعلًا (الساق 1 من ثلاثية ADR-0009)
  HF-3 (مرن)  : GET https://router.huggingface.co/v1/models (Bearer)
                → وصول طبقة موفري الاستدلال (سرد فقط — لا يستهلك أي رصيد توليد)
  KG-1 (صلب)  : POST https://api.kaggle.com/v1/security.OAuthService/IntrospectToken (Basic)
                → صلاحية مفتاح KGAT (active=true + اسم المستخدم + النطاق)
                (ملاحظة موثقة: نتيجة سلبية للمفتاح الخاطئ = 404 وليست 200)
  KG-2 (صلب)  : POST https://api.kaggle.com/v1/kernels.KernelsApiService/GetAcceleratorQuotaStatistics
                (Bearer بمفتاح KGAT — خدمة kernels تقبل Bearer فقط لا Basic)
                → وصول خدمة kernels وقراءة حصة GPU/TPU الحية (قراءة-فقط بلا استهلاك)

الاستخدام:
  HF_TOKEN=... KAGGLE_USERNAME=... KAGGLE_KEY=... python3 scripts/infra_check_hf_kaggle.py
  (داخل GitHub Actions تُمرَّر من Repository Secrets بنفس الأسماء — ADR-0020)
"""

import base64
import json
import os
import sys
import time
import urllib.error
import urllib.request

HF_WHOAMI_URL = "https://huggingface.co/api/whoami-v2"
HF_WEIGHTS_REPO_API = "https://huggingface.co/api/models/Alkemos/alkemosai-weights"
HF_ROUTER_MODELS_URL = "https://router.huggingface.co/v1/models?limit=100"
KG_INTROSPECT_URL = "https://api.kaggle.com/v1/security.OAuthService/IntrospectToken"
KG_QUOTA_URL = "https://api.kaggle.com/v1/kernels.KernelsApiService/GetAcceleratorQuotaStatistics"

REQUEST_TIMEOUT = 30
MAX_ATTEMPTS = 3          # محاولة + إعادتان عند 429/5xx (قيد معدل عابر)
BACKOFF_SECONDS = 20

failures = []


def _http(url, method="GET", headers=None, body=None):
    """طلب HTTP يعيد (status, dict|None). يعيد المحاولة عند 429/5xx فقط."""
    last_error = None
    for attempt in range(1, MAX_ATTEMPTS + 1):
        req = urllib.request.Request(url, method=method)
        for k, v in (headers or {}).items():
            req.add_header(k, v)
        data = None
        if body is not None:
            req.add_header("Content-Type", "application/json")
            data = json.dumps(body).encode()
        try:
            with urllib.request.urlopen(req, data, timeout=REQUEST_TIMEOUT) as r:
                raw = r.read().decode()
                return r.status, (json.loads(raw) if raw.strip().startswith(("{", "[")) else None)
        except urllib.error.HTTPError as e:
            raw = ""
            try:
                raw = e.read().decode()[:300]
            except Exception:
                pass
            if e.code in (429, 500, 502, 503, 504) and attempt < MAX_ATTEMPTS:
                time.sleep(BACKOFF_SECONDS)
                last_error = f"HTTP {e.code} (محاولة {attempt}) — إعادة بعد مهلة"
                continue
            return e.code, None if not raw.strip().startswith(("{", "[")) else _try_json(raw)
        except (urllib.error.URLError, TimeoutError) as e:
            last_error = f"خطأ شبكة: {type(e).__name__}"
            if attempt < MAX_ATTEMPTS:
                time.sleep(BACKOFF_SECONDS)
                continue
    return -1, {"__last_error": last_error or "خطأ شبكة"}


def _try_json(raw):
    try:
        return json.loads(raw)
    except Exception:
        return None


def _seconds_to_hours(s):
    """'108000s' → 30.0 (ساعات)."""
    if not s:
        return None
    s = str(s).rstrip("s")
    if s.endswith("h"):
        return float(s.rstrip("h"))
    if s.endswith("m"):
        return float(s.rstrip("m")) / 60.0
    try:
        return float(s) / 3600.0
    except ValueError:
        return None


def check_hf_whoami():
    """HF-1 (صلب): صلاحية التوكن + نطاق repo.write."""
    status, d = _http(HF_WHOAMI_URL, headers={"Authorization": f"Bearer {os.environ['HF_TOKEN']}"})
    if status != 200 or not isinstance(d, dict) or "name" not in (d or {}):
        failures.append(f"HF-1 whoami فشل (HTTP {status}) — التوكن غير صالح أو الاتصال معطل")
        return
    token = (d.get("auth") or {}).get("accessToken") or {}
    scopes = []
    for sc in (token.get("fineGrained") or {}).get("scoped") or []:
        scopes.extend(sc.get("permissions") or [])
    scopes.extend((token.get("fineGrained") or {}).get("global") or [])
    has_repo_write = "repo.write" in scopes
    has_inference = any(s.startswith("inference.") for s in scopes)
    print(f"[HF-1] التوكن صالح — الحساب: {d.get('name')} · نوع التوكن: {token.get('role', 'classic')}")
    print(f"[HF-1] النطاقات: repo.write={'نعم' if has_repo_write else 'لا'} · inference={'نعم' if has_inference else 'لا'} · نطاقات كلها={len(set(scopes))}")
    if not has_repo_write:
        failures.append("HF-1: التوكن بلا نطاق repo.write — لا يمكنه إدارة مستودع الأوزان")


def check_hf_weights_repo():
    """HF-2 (صلب): مستودع الأوزان الخاص موجود وخاص فعلًا."""
    status, d = _http(HF_WEIGHTS_REPO_API, headers={"Authorization": f"Bearer {os.environ['HF_TOKEN']}"})
    if status != 200 or not isinstance(d, dict) or "id" not in (d or {}):
        failures.append(f"HF-2 مستودع الأوزان غير متاح (HTTP {status}) — الساق 1 من ثلاثية ADR-0009 مهددة")
        return
    private = bool(d.get("private"))
    print(f"[HF-2] مستودع الأوزان: {d.get('id')} · خاص={private} · رأس الالتزام: {str(d.get('sha'))[:12]}")
    if not private:
        failures.append("HF-2: المستودع ليس خاصًا — يجب تحويله خاصًا فورًا (ADR-0009)")


def check_hf_router():
    """HF-3 (مرن): وصول طبقة موفري الاستدلال (سرد نماذج فقط — لا توليد ولا استهلاك رصيد)."""
    status, d = _http(HF_ROUTER_MODELS_URL, headers={"Authorization": f"Bearer {os.environ['HF_TOKEN']}"})
    if status == 200 and isinstance(d, dict):
        n = len(d.get("data") or [])
        print(f"[HF-3] راوتر موفري الاستدلال متاح — عدد النماذج المسرودة (عينة): {n}")
    elif status in (429, -1):
        print(f"[HF-3] الراوتر غير قابل للوصول الآن (HTTP {status} — قيد معدل/شبكة) — فحص مرن، لا يخفق البناء")
    else:
        print(f"[HF-3] الراوتر أعاد HTTP {status} — فحص مرن، لا يخفق البناء")


def check_kaggle_introspect():
    """KG-1 (صلب): صلاحية مفتاح KGAT عبر الاستعلام عنه (النتيجة الفارغة/الخاطئة = 404)."""
    user = os.environ["KAGGLE_USERNAME"]
    key = os.environ["KAGGLE_KEY"]
    creds = base64.b64encode(f"{user}:{key}".encode()).decode()
    status, d = _http(
        KG_INTROSPECT_URL,
        method="POST",
        headers={"Authorization": f"Basic {creds}"},
        body={"token": key},
    )
    if status != 200 or not isinstance(d, dict) or not d.get("active"):
        failures.append(f"KG-1 مفتاح KGAT غير صالح/غير نشط (HTTP {status})")
        return
    canonical = str(d.get("username") or "")
    scope = d.get("scope")
    same = canonical.casefold() == user.casefold()
    print(f"[KG-1] مفتاح KGAT صالح ونشط — المستخدم: {canonical} (يطابق قيمة السر KAGGLE_USERNAME: {'نعم' if same else 'لا'}) · النطاق: {scope}")
    if not same:
        failures.append(f"KG-1: اسم المستخدم الكنسي ({canonical}) لا يطابق قيمة السر KAGGLE_USERNAME — يجب توحيد القيمة")


def check_kaggle_quota():
    """KG-2 (صلب): وصول خدمة kernels (Bearer) + قراءة الحصة الحية — قراءة-فقط بلا استهلاك."""
    key = os.environ["KAGGLE_KEY"]
    status, d = _http(KG_QUOTA_URL, method="POST", headers={"Authorization": f"Bearer {key}"}, body={})
    if status != 200 or not isinstance(d, dict) or "gpuQuota" not in (d or {}):
        failures.append(f"KG-2 قراءة حصة GPU فشلت (HTTP {status}) — خدمة kernels لا تقبل الاعتماديات")
        return
    g = d.get("gpuQuota") or {}
    t = d.get("tpuQuota") or {}
    used_h = _seconds_to_hours(g.get("timeUsed"))
    allowed_h = _seconds_to_hours(g.get("totalTimeAllowed"))
    tpu_allowed_h = _seconds_to_hours(t.get("totalTimeAllowed"))
    print(f"[KG-2] خدمة kernels متاحة (Bearer) — حصة GPU: {used_h} ساعة مستخدمة من {allowed_h} ساعة/أسبوع · TPU: {_seconds_to_hours(t.get('timeUsed'))} من {tpu_allowed_h} · التجديد: {d.get('quotaRefreshTime')}")
    if not allowed_h or allowed_h <= 0:
        failures.append("KG-2: الحصة الأسبوعية صفر أو غير مقروءة — راجع حالة الحساب قبل M2")
    elif used_h and used_h >= allowed_h:
        print("[KG-2] تحذير: الحصة الأسبوعية مستهلكة بالكامل — أي تدريب سينتظر التجديد")


def main():
    missing = [v for v in ("HF_TOKEN", "KAGGLE_USERNAME", "KAGGLE_KEY") if not os.environ.get(v)]
    if missing:
        print(f"متغيرات بيئة ناقصة: {', '.join(missing)} — لا أسرار في الكود؛ تُمرر من البيئة/الأسرار فقط", file=sys.stderr)
        sys.exit(2)
    print("== فحص اتصال وصلاحيات Hugging Face وKaggle (قراءة-فقط — دفعة 10/ADR-0020) ==")
    print("قانون: لا يطبع هذا السكربت أي قيمة سرية — الأسماء والحصص وحالات الاستجابة فقط")
    check_hf_whoami()
    check_hf_weights_repo()
    check_hf_router()
    check_kaggle_introspect()
    check_kaggle_quota()
    print("================================================================")
    if failures:
        print("نتيجة الفحص: فشل — الفحوص الصلبة التي خفقت:")
        for f in failures:
            print(f"  - {f}")
        sys.exit(1)
    print("نتيجة الفحص: نجاح — كل الفحوص الصلبة عبرت (بلا أي استهلاك موارد)")


if __name__ == "__main__":
    main()
