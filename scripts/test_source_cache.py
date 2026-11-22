#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""اختبار عزل كاش المصادر (مراجعة دفعة 9 — الملاحظة 2 بأمر المالك).

يثبت أن كاش المصدر في m1_build_datasets.py مربوط بالـSHA المثبّت ولا يسمح
باستخدام محتوى من إصدار سابق — بأربع طفرات على مجلدات مؤقتة (بلا مساس
بكاش الدورة الفعلي):
  C1   كاش إصدار سابق — التخطيط المسطح القديم (دفعة 8) + مجلد SHA آخر —
       لا يُقرأ أبدًا؛ المرجع الشبكة على الـSHA المثبّت.
  C2   محتوى معدول داخل مجلد الـSHA الصحيح = بصمة لا تطابق البيان →
       رفضه وإعادة الجلب ثم إصلاح الكاش والبيان.
  C3   بيان (_manifest.json) غائب = إعادة الجلب وإعادة بناء البيان.
  C4   بيان معدول (يحمل SHA آخر) = يُتجاهل كأنه غائب.
"""
import hashlib
import json
import os
import shutil
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from scripts.m1_build_datasets import (  # noqa: E402
    CACHE_MANIFEST_NAME,
    SOURCE_SHA,
    fetch_source,
)

SCRIPTS = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(SCRIPTS, ".source-cache")
PATH = "src/lib/fitness-math.ts"
NAME = PATH.replace("/", "__")


def main() -> int:
    results = []

    def check(name, cond):
        results.append((name, bool(cond)))
        if not cond:
            print(f"  FAIL — {name}")

    # المحتوى الصحيح المثبّت (مرجع المقارنة — من كاش الدورة أو الشبكة)
    good = fetch_source(PATH, CACHE)
    assert good and "Mifflin" in good, "فشل جلب ملف المرجع"

    tmp = tempfile.mkdtemp(prefix="alkemos-cache-test-")
    try:
        # C1: كاش بإصدار سابق — التخطيط المسطح القديم + مجلد SHA آخر — لا يُقرأ
        with open(os.path.join(tmp, NAME), "w", encoding="utf-8") as f:
            f.write("// محتوى إصدار سابق — التخطيط المسطح القديم (دفعة 8)")
        old_sha_dir = os.path.join(tmp, "e" * 40)
        os.makedirs(old_sha_dir, exist_ok=True)
        with open(os.path.join(old_sha_dir, NAME), "w", encoding="utf-8") as f:
            f.write("// محتوى إصدار سابق — مجلد SHA آخر")
        got = fetch_source(PATH, tmp)
        check("C1 كاش إصدار سابق (مسطح + مجلد SHA آخر) يُتجاهل", got == good)

        # C2: محتوى معدول داخل مجلد الـSHA الصحيح = إعادة الجلب وإصلاح الكاش
        sha_dir = os.path.join(tmp, SOURCE_SHA)
        with open(os.path.join(sha_dir, NAME), "w", encoding="utf-8") as f:
            f.write("// محتوى معدول — بصمة لا تطابق البيان")
        got = fetch_source(PATH, tmp)
        check("C2 محتوى معدول يُرفض ويُعاد جلبه من الشبكة", got == good)
        with open(os.path.join(sha_dir, CACHE_MANIFEST_NAME), encoding="utf-8") as f:
            m = json.load(f)
        digest = hashlib.sha256(got.encode("utf-8")).hexdigest()
        check("C2-ب الكاش أُصلح وبصمته حُدثت في البيان", m["files"].get(NAME) == digest)

        # C3: بيان غائب = إعادة الجلب وإعادة بناء البيان
        os.remove(os.path.join(sha_dir, CACHE_MANIFEST_NAME))
        got = fetch_source(PATH, tmp)
        check("C3 بيان غائب = إعادة الجلب", got == good)
        with open(os.path.join(sha_dir, CACHE_MANIFEST_NAME), encoding="utf-8") as f:
            m = json.load(f)
        check("C3-ب البيان أُعيد بناؤه بالمستودع والـSHA المثبّت",
              m.get("repo", "").endswith("/alkemos-aws") and m.get("sha") == SOURCE_SHA)

        # C4: بيان معدول (يحمل SHA آخر) يُتجاهل كأنه غائب
        with open(os.path.join(sha_dir, CACHE_MANIFEST_NAME), "w", encoding="utf-8") as f:
            json.dump({"repo": "muscleshubfit-cpu/alkemos-aws", "sha": "f" * 40,
                       "files": {NAME: hashlib.sha256(b"stale").hexdigest()}}, f)
        got = fetch_source(PATH, tmp)
        check("C4 بيان معدول بSHA آخر يُتجاهل", got == good)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    print()
    for name, ok in results:
        print(f"  {'PASS' if ok else 'FAIL'} — {name}")
    passed = sum(1 for _, ok in results if ok)
    print(f"\nنتيجة اختبار الكاش: {passed}/{len(results)}")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
