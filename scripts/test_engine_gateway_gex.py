#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""اختبارات بوابة G-EX — الشروط الستة + توقيع المالك + الانسحاب + الأرشفة.

القوانين تحت الاختبار (الخطة §6):
- لا مثال يعبر إلا باكتمال الشروط الستة مجتمعة — كل شرط له اختبار إخلال.
- لا اعتماد بلا توقيع مالك موثق — ولا قيد تعلم إلا بملف معتمد كامل الأصل.
- سحب الموافقة يمنع استخدام الأمثلة في أي دفعة تالية (check_withdrawal).
- الرفض مؤرشف بسبب موثق — لا حذف أبدًا.
- المقبول يحمل بصمة sha256 للمحتوى وإصدارًا وتصنيف استخدام واحدًا لا يُعدل.
كل الأمثلة هنا اصطناعية (fixtures) — لا بيانات عملاء حقيقية في هذا المستودع.
"""
import hashlib
import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from engine.learning import denier, gateway  # noqa: E402


def _candidate(tmp, content=None, src_name="source-plan.json", src_body=None, **overrides):
    src_path = os.path.join(tmp, src_name)
    with open(src_path, "w", encoding="utf-8") as fh:
        json.dump(src_body or {"plan": "fixture", "src": src_name}, fh)
    cand = {
        "content": content or json.dumps({"daily_calories": 1600, "meals": [{"name": "فطور", "items": [{"food": "شوفان"}]}]}, ensure_ascii=False),
        "origin": {
            "path": src_path,
            "sha256": hashlib.sha256(open(src_path, "rb").read()).hexdigest(),
            "inspected_at": "2026-11-24",
        },
        "deid": {"human_review_passed": True, "reviewer": "owner", "reviewed_at": "2026-11-24"},
        "basis": {"kind": "client_consent", "reference": "consent-2026-11-24-001", "withdrawn": False},
        "quality": {"kind": "judge_score", "score": 8},
        "conflicts_resolved": True,
        "usage": "training_only",
    }
    cand.update(overrides)
    return cand


SIGNATURE = {"signer": "owner", "signed_at": "2026-11-24", "decision_ref": "أمر اعتماد 2026-11-24"}


def main():
    results = []

    def check(name, cond, detail=""):
        results.append((name, bool(cond)))
        mark = "✓" if cond else "✗"
        print(f"  {mark} {name}" + (f" — {detail}" if (detail and not cond) else ""))

    def _raises(fn, exc):
        try:
            fn()
            return False
        except exc:
            return True
        except Exception:
            return False

    # ── فاحص قائمة الحرمان (شرط 2 الآلي) ────────────────────────────────────
    scan = denier.scan_text("خطة متوازنة سعراتها 1600")
    check("الفاحص: نص نظيف يعبر", scan["passed"] and scan["hits"] == [])
    scan = denier.scan_text("راسلني على coach@example.com أو 0100 123 4567")
    check("الفاحص: بريد وهاتف يُكتشفان", not scan["passed"] and {h["kind"] for h in scan["hits"]} == {"email", "phone"})
    scan = denier.scan_text("يتناول المريض أدوية السكري")
    check("الفاحص: مفردات سريرية/دوائية تُرفض", not scan["passed"] and any(h["kind"] == "keyword" for h in scan["hits"]))
    scan = denier.scan_text("الرقم القومي 29001011234567 مسجل")
    check("الفاحص: الرقم القومي (14 رقمًا) يُرفض", not scan["passed"] and any(h["kind"] == "national_id" for h in scan["hits"]))

    with tempfile.TemporaryDirectory() as tmp:
        approved_dir = os.path.join(tmp, "approved")
        archive_dir = os.path.join(tmp, "archive")
        gw = gateway.ExampleGateway(approved_dir, archive_dir)

        # ── الدورة الكاملة الناجحة ─────────────────────────────────────────
        cand = _candidate(tmp)
        report = gw.submit(cand)
        check("التقديم: المرشح المكتمل يجتاز الفحوص الستة", report["passed"] and report["errors"] == [])
        result = gw.approve(cand, SIGNATURE)
        ex_file = os.path.join(approved_dir, "EX-0001.json")
        check("الاعتماد: ملف EX-0001 كُتب", os.path.exists(ex_file))
        rec = json.loads(open(ex_file, encoding="utf-8").read())
        check("الاعتماد: بصمة المحتوى sha256 صحيحة", rec["content_sha256"] == hashlib.sha256(cand["content"].encode()).hexdigest())
        check("الاعتماد: الأصل كامل (المسار والبصمة وتاريخ الاطلاع)", rec["origin"]["path"] == cand["origin"]["path"] and rec["origin"]["sha256"] == cand["origin"]["sha256"] and rec["origin"]["inspected_at"] == "2026-11-24")
        check("الاعتماد: توقيع المالك موثق داخل الملف", rec["owner_signature"]["signer"] == "owner" and rec["owner_signature"]["decision_ref"])
        check("الاعتماد: تصنيف استخدام واحد مختم", rec["usage"] == "training_only" and rec["version"] == "v1.0")
        check("الاعتماد: قيد تعلم جاهز بصيغة learning-log", "G-EX" in result["log_entry"] and "EX-0001" in result["log_entry"] and "kind: أوزان" in result["log_entry"])

        # ── إخلال كل شرط على حدة ───────────────────────────────────────────
        bad = gw.submit(_candidate(tmp, origin={"path": "/غير/موجود.json", "sha256": "x" * 64, "inspected_at": "2026-11-24"}))
        check("شرط 1: مصدر مفقود يرفض", not bad["passed"] and any("شرط 1" in e for e in bad["errors"]))
        src_path = os.path.join(tmp, "source-plan.json")
        bad = gw.submit(_candidate(tmp, origin={"path": src_path, "sha256": "0" * 64, "inspected_at": "2026-11-24"}))
        check("شرط 1: بصمة لا تطابق ترفض", not bad["passed"] and any("SHA256" in e for e in bad["errors"]))
        bad = gw.submit(_candidate(tmp, origin={"path": src_path, "sha256": hashlib.sha256(open(src_path, "rb").read()).hexdigest(), "inspected_at": "2026-02-30"}))
        check("شرط 1: تاريخ اطلاع غير صالح تقويميًا (30 فبراير) يرفض", not bad["passed"] and any("تاريخ الاطلاع" in e for e in bad["errors"]))

        bad = gw.submit(_candidate(tmp, content="خطة تحتوي بريد coach@example.com"))
        check("شرط 2: فحص الحرمان الآلي يرفض التسرب", not bad["passed"] and any("شرط 2" in e and "إصابة" in e for e in bad["errors"]))
        bad = gw.submit(_candidate(tmp, deid={"human_review_passed": False, "reviewer": "", "reviewed_at": ""}))
        check("شرط 2: غياب المراجعة البشرية يرفض", not bad["passed"] and any("المراجعة البشرية" in e for e in bad["errors"]))

        bad = gw.submit(_candidate(tmp, basis=None))
        check("شرط 3: غياب الأساس المصرح يرفض", not bad["passed"] and any("شرط 3" in e for e in bad["errors"]))
        bad = gw.submit(_candidate(tmp, basis={"kind": "client_consent", "reference": "r", "withdrawn": True}))
        check("شرط 3: الأساس المسحوب يرفض", not bad["passed"] and any("مسحوب" in e for e in bad["errors"]))

        bad = gw.submit(_candidate(tmp, quality={"kind": "judge_score", "score": 5}))
        check("شرط 4: درجة القاضي دون العتبة (5<7) ترفض", not bad["passed"] and any("شرط 4" in e for e in bad["errors"]))
        bad = gw.submit(_candidate(tmp, quality={"kind": "safety_pass", "passed": False}))
        check("شرط 4: إخفاق بوابات السلامة يرفض", not bad["passed"] and any("السلامة" in e for e in bad["errors"]))

        bad = gw.submit(_candidate(tmp, conflicts_resolved=False))
        check("شرط 5: إقرار حل التعارضات غير موثق يرفض", not bad["passed"] and any("شرط 5" in e for e in bad["errors"]))
        cand2 = _candidate(tmp, src_name="source-plan-2.json")
        gw.approve(cand2, SIGNATURE)  # أصل مختلف يعتمد مشروعًا (EX-0002)
        bad = gw.submit(cand2)
        check("شرط 5: الأصل نفسه لا يُعتمد مرتين (تكرار)", not bad["passed"] and any("معتمد سابقًا" in e for e in bad["errors"]))
        check("شرط 5: محاولة إعادة اعتماد الأصل نفسه ترفض", _raises(lambda: gw.approve(cand2, SIGNATURE), gateway.GatewayError))

        bad = gw.submit(_candidate(tmp, usage="everywhere"))
        check("شرط 6: تصنيف استخدام خارج النطاق يرفض", not bad["passed"] and any("شرط 6" in e for e in bad["errors"]))

        # ── التوقيع ─────────────────────────────────────────────────────────
        fresh = _candidate(tmp, src_name="source-plan-3.json", content=json.dumps({"daily_calories": 1800}, ensure_ascii=False), basis={"kind": "owner_basis", "reference": "basis-owner-002", "withdrawn": False})
        check("التوقيع: بلا توقيع مالك لا اعتماد", _raises(lambda: gw.approve(fresh, {}), gateway.GatewayError))
        check("التوقيع: الموقّع غير المالك مرفوض", _raises(lambda: gw.approve(fresh, {"signer": "agent", "signed_at": "2026-11-24", "decision_ref": "x"}), gateway.GatewayError))
        check("التوقيع: التاريخ غير الصالح يرفض", _raises(lambda: gw.approve(fresh, {"signer": "owner", "signed_at": "2026-13-40", "decision_ref": "x"}), gateway.GatewayError))

        # ── الانسحاب يمنع أي دفعة تالية ────────────────────────────────────
        gw.approve(fresh, SIGNATURE)
        affected = gw.check_withdrawal("consent-2026-11-24-001")
        check("الانسحاب: أمثلة الأساس المسحوب تُدرج للاستبعاد", set(affected) == {"EX-0001", "EX-0002"})
        check("الانسحاب: أساس بلا أمثلة = قائمة فارغة", gw.check_withdrawal("basis-nonexistent") == [])

        # ── الرفض المؤرشف ──────────────────────────────────────────────────
        rejected = gw.reject(_candidate(tmp, usage="bad"), "تصنيف الاستخدام خارج النطاق")
        rej_file = os.path.join(archive_dir, "REJ-0001.json")
        check("الرفض: يؤرشف بسبب موثق — لا حذف أبدًا", os.path.exists(rej_file) and rejected["reason"] == "تصنيف الاستخدام خارج النطاق" and rejected["checks_report"]["passed"] is False)
        check("الرفض: رفض بلا سبب مرفوض", _raises(lambda: gw.reject(_candidate(tmp), "  "), gateway.GatewayError))
        check("العدّ: 3 معتمدة وأرشيف واحد", len(os.listdir(approved_dir)) == 3 and len(os.listdir(archive_dir)) == 1)

    passed = sum(1 for _, ok in results if ok)
    print(f"\n{passed}/{len(results)} اختبارًا ناجحًا")
    sys.exit(0 if passed == len(results) else 1)


if __name__ == "__main__":
    main()
