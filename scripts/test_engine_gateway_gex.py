#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""اختبارات بوابة G-EX — الشروط الستة + توقيع المالك المتحقق + السجل + الانسحاب + الأرشفة.

القوانين تحت الاختبار (الخطة §6 + تحصين 16-تتمة):
- لا مثال يعبر إلا باكتمال الشروط الستة مجتمعة — كل شرط له اختبار إخلال.
- الشرط 3 من سجل الموافقات الموثوق حصرًا — قيم المرشح (withdrawn) لا تُقبل
  إثباتًا، وتُختبر الكذبة في الاتجاهين (مرشح يدّعي السحب والسجل نشط = يعبر؛
  مرشح يدّعي النشاط والسجل مسحوب = يُرفض).
- الاعتماد بتوقيع مالك متحقق HMAC بمفتاحه المستقل — النص «owner» لا يمنح
  شيئًا، والتوقيع مقيد ببصمة المثال (لا إعادة استخدام لمثال آخر).
- كل اعتماد يقيد في سجل اعتماد بسلسلة بصمات — والعبث يُكشف.
- سحب الموافقة يمنع أي اعتماد جديد على الأساس المسحوب مع بقاء سجل التدقيق.
- الرفض مؤرشف بسبب موثق — لا حذف أبدًا.
كل الأمثلة هنا اصطناعية (fixtures) — لا بيانات عملاء حقيقية في هذا المستودع.
"""
import hashlib
import json
import os
import secrets
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from engine import auth  # noqa: E402
from engine.learning import consent, denier, gateway  # noqa: E402

CONSENT_REF = "consent-2026-11-24-001"
OWNER_BASIS_REF = "basis-owner-002"


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
        "basis": {"kind": "client_consent", "reference": CONSENT_REF, "withdrawn": False},
        "quality": {"kind": "judge_score", "score": 8},
        "conflicts_resolved": True,
        "usage": "training_only",
    }
    cand.update(overrides)
    return cand


def _owner_signature(ta, cand, decision_ref="أمر اعتماد 2026-11-24", signed_at="2026-11-24"):
    doc = auth.gex_approval_document(
        decision_ref=decision_ref,
        signed_at=signed_at,
        content_sha256=hashlib.sha256(cand["content"].encode()).hexdigest(),
        origin_sha256=cand["origin"]["sha256"],
    )
    return {"document": doc, "signature": ta.owner_sign(doc)}


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
        ledger_root = os.path.join(tmp, "consent")  # خارج شجرة git (المستوى أ)
        ledger = consent.ConsentLedger(ledger_root)
        ledger.grant_client_consent(
            reference=CONSENT_REF, client_id="client-77", purpose="training",
            usage_scope=["training_only", "training_retrieval"], granted_at="2026-11-20",
        )
        ledger.record_owner_basis(
            reference=OWNER_BASIS_REF, purpose="training",
            usage_scope=["training_only"], decided_at="2026-11-21", decision_ref="قرار مالك-أساس-002",
        )
        ta = auth.TokenAuthority(secrets.token_bytes(32), secrets.token_bytes(32))
        verifier = ta.owner_verifier()
        gw = gateway.ExampleGateway(
            approved_dir, archive_dir,
            consent_ledger=ledger, owner_verifier=verifier,
        )

        # ── الدورة الكاملة الناجحة ─────────────────────────────────────────
        cand = _candidate(tmp)
        report = gw.submit(cand)
        check("التقديم: المرشح المكتمل يجتاز الفحوص الستة (الأساس من السجل)", report["passed"] and report["errors"] == [])
        result = gw.approve(cand, _owner_signature(ta, cand))
        ex_file = os.path.join(approved_dir, "EX-0001.json")
        check("الاعتماد: ملف EX-0001 كُتب", os.path.exists(ex_file))
        rec = json.loads(open(ex_file, encoding="utf-8").read())
        check("الاعتماد: بصمة المحتوى sha256 صحيحة", rec["content_sha256"] == hashlib.sha256(cand["content"].encode()).hexdigest())
        check("الاعتماد: الأصل كامل (المسار والبصمة وتاريخ الاطلاع)", rec["origin"]["path"] == cand["origin"]["path"] and rec["origin"]["sha256"] == cand["origin"]["sha256"] and rec["origin"]["inspected_at"] == "2026-11-24")
        check("الاعتماد: توقيع المالك موثق داخل الملف (متاحق بمفتاحه)", rec["owner_signature"]["verified_by"].startswith("owner-key") and rec["owner_signature"]["decision_ref"] and rec["owner_signature"]["content_sha256"] == rec["content_sha256"])
        check("الاعتماد: الأساس موثق بمصدره (سجل الموافقات)", rec["basis"]["verified_via"] == "consent-ledger")
        check("الاعتماد: تصنيف استخدام واحد مختم", rec["usage"] == "training_only" and rec["version"] == "v1.0")
        check("الاعتماد: قيد تعلم جاهز بصيغة learning-log", "G-EX" in result["log_entry"] and "EX-0001" in result["log_entry"] and "kind: أوزان" in result["log_entry"])
        check("الاعتماد: قيد في سجل الاعتماد ببصمة وسلسلة سليمة", gw.adoption_ledger.verify_chain()["ok"] and len(gw.adoption_ledger.entries()) == 1)

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
        bad = gw.submit(_candidate(tmp, basis={"kind": "client_consent", "reference": "r", "withdrawn": False}))
        check("شرط 3: مرجع غير موجود في السجل يرفض (لا أساس بلا سجل)", not bad["passed"] and any("غير موجود في سجل الموافقات" in e for e in bad["errors"]))
        bad = gw.submit(_candidate(tmp, basis={"kind": "owner_basis", "reference": CONSENT_REF, "withdrawn": False}))
        check("شرط 3: مرجع موافقة عميل لا يُستعمل أساس مالك (عدم تطابق النوع)", not bad["passed"] and any("لا يطابق المدعى" in e for e in bad["errors"]))
        bad = gw.submit(_candidate(tmp, usage="retrieval_only"))
        check("شرط 3: نطاق استخدام خارج الموافقة يرفض", not bad["passed"] and any("خارج الموافقة" in e for e in bad["errors"]))
        # الكذبة في الاتجاهين: السجل هو مصدر الحقيقة لا قيم المرشح
        liar = _candidate(tmp, src_name="source-liar.json", basis={"kind": "client_consent", "reference": CONSENT_REF, "withdrawn": True})
        check("شرط 3: مرشح يدّعي السحب والسجل نشط → يعبر (السجل مصدر الحقيقة)", gw.submit(liar)["passed"])

        bad = gw.submit(_candidate(tmp, quality={"kind": "judge_score", "score": 5}))
        check("شرط 4: درجة القاضي دون العتبة (5<7) ترفض", not bad["passed"] and any("شرط 4" in e for e in bad["errors"]))
        bad = gw.submit(_candidate(tmp, quality={"kind": "safety_pass", "passed": False}))
        check("شرط 4: إخفاق بوابات السلامة يرفض", not bad["passed"] and any("السلامة" in e for e in bad["errors"]))

        bad = gw.submit(_candidate(tmp, conflicts_resolved=False))
        check("شرط 5: إقرار حل التعارضات غير موثق يرفض", not bad["passed"] and any("شرط 5" in e for e in bad["errors"]))
        cand2 = _candidate(tmp, src_name="source-plan-2.json")
        gw.approve(cand2, _owner_signature(ta, cand2))  # أصل مختلف يعتمد مشروعًا (EX-0002)
        bad = gw.submit(cand2)
        check("شرط 5: الأصل نفسه لا يُعتمد مرتين (تكرار)", not bad["passed"] and any("معتمد سابقًا" in e for e in bad["errors"]))
        check("شرط 5: محاولة إعادة اعتماد الأصل نفسه ترفض", _raises(lambda: gw.approve(cand2, _owner_signature(ta, cand2)), gateway.GatewayError))

        bad = gw.submit(_candidate(tmp, usage="everywhere"))
        check("شرط 6: تصنيف استخدام خارج النطاق يرفض", not bad["passed"] and any("شرط 6" in e for e in bad["errors"]))

        # ── التوقيع: تحقق حقيقي لا نص «owner» ─────────────────────────────
        fresh = _candidate(tmp, src_name="source-plan-3.json", content=json.dumps({"daily_calories": 1800}, ensure_ascii=False), basis={"kind": "owner_basis", "reference": OWNER_BASIS_REF, "withdrawn": False})
        check("التوقيع: بلا توقيع مالك لا اعتماد", _raises(lambda: gw.approve(fresh, {}), gateway.GatewayError))
        check("التوقيع: الشكل النصي القديم signer=owner مرفوض جذريًا", _raises(lambda: gw.approve(fresh, {"signer": "owner", "signed_at": "2026-11-24", "decision_ref": "x"}), gateway.GatewayError))
        forged_key = auth.TokenAuthority(secrets.token_bytes(32), secrets.token_bytes(32))
        forged = _owner_signature(forged_key, fresh)
        check("التوقيع: توقيع بمفتاح غير مفتاح المالك يُرفض", _raises(lambda: gw.approve(fresh, forged), gateway.GatewayError))
        sig_ok_for_fresh = _owner_signature(ta, fresh)
        other_cand = _candidate(tmp, src_name="source-plan-4.json", content=json.dumps({"daily_calories": 2000}, ensure_ascii=False), basis={"kind": "owner_basis", "reference": OWNER_BASIS_REF, "withdrawn": False})
        check("التوقيع: توقيع مثال لا يُعاد استخدامه لمثال آخر (بصمة المحتوى)", _raises(lambda: gw.approve(other_cand, sig_ok_for_fresh), gateway.GatewayError))
        tampered_doc = dict(sig_ok_for_fresh)
        tampered_doc["document"] = {**sig_ok_for_fresh["document"], "decision_ref": "أمر مزور"}
        check("التوقيع: العبث بوثيقة التوقيع بعد التوقيع يبطلها", _raises(lambda: gw.approve(fresh, tampered_doc), gateway.GatewayError))

        # ── الانسحاب يمنع أي اعتماد جديد ويحفظ التدقيق ─────────────────────
        gw.approve(fresh, _owner_signature(ta, fresh))  # EX-0003 على أساس المالك
        affected = gw.check_withdrawal(CONSENT_REF)
        check("الانسحاب: أمثلة الأساس المسحوب تُدرج للاستبعاد", set(affected) == {"EX-0001", "EX-0002"})
        check("الانسحاب: أساس بلا أمثلة = قائمة فارغة", gw.check_withdrawal("basis-nonexistent") == [])
        ledger.withdraw(CONSENT_REF, "2026-11-24", "طلب العميل الانسحاب")
        post = _candidate(tmp, src_name="source-post-withdraw.json", basis={"kind": "client_consent", "reference": CONSENT_REF, "withdrawn": False})
        check("الانسحاب: مرشح يدّعي النشاط والسجل مسحوب → يُرفض", not gw.submit(post)["passed"] and any("مسحوب" in e for e in gw.submit(post)["errors"]))
        check("الانسحاب: محاولة اعتماد على الأساس المسحوب ترفض", _raises(lambda: gw.approve(post, _owner_signature(ta, post)), gateway.GatewayError))
        still_on_disk = [f for f in os.listdir(approved_dir) if f.startswith("EX-")]
        check("الانسحاب: سجل التدقيق محفوظ (الأمثلة القديمة على القرص)", set(still_on_disk) == {f"EX-{i:04d}.json" for i in (1, 2, 3)} and len(ledger.all_events()) == 3)  # منحان + انسحاب

        # ── fail-closed: بلا سجل موافقات لا تحقق أساس ─────────────────────
        gw_nol = gateway.ExampleGateway(os.path.join(tmp, "ap2"), os.path.join(tmp, "ar2"))
        check("fail-closed: بلا سجل موافقات الشرط 3 يرفض كل مرشح", not gw_nol.submit(_candidate(tmp))["passed"] and any("fail-closed" in e for e in gw_nol.submit(_candidate(tmp))["errors"]))
        check("fail-closed: بلا سجل موافقات الاعتماد مرفوض", _raises(lambda: gw_nol.approve(_candidate(tmp), _owner_signature(ta, _candidate(tmp))), gateway.GatewayError))

        # ── الرفض المؤرشف ──────────────────────────────────────────────────
        rejected = gw.reject(_candidate(tmp, usage="bad"), "تصنيف الاستخدام خارج النطاق")
        rej_file = os.path.join(archive_dir, "REJ-0001.json")
        check("الرفض: يؤرشف بسبب موثق — لا حذف أبدًا", os.path.exists(rej_file) and rejected["reason"] == "تصنيف الاستخدام خارج النطاق" and rejected["checks_report"]["passed"] is False)
        check("الرفض: رفض بلا سبب مرفوض", _raises(lambda: gw.reject(_candidate(tmp), "  "), gateway.GatewayError))
        check("العدّ: 3 معتمدة وأرشيف واحد", len([f for f in os.listdir(approved_dir) if f.startswith("EX-")]) == 3 and len(os.listdir(archive_dir)) == 1)

        # ── سلامة الاعتماد: السلسلة والتقاطع ───────────────────────────────
        integ = gw.verify_integrity()
        check("السلامة: السلسلة والتقاطع سليمان بعد 3 اعتمادات", integ["ok"] and integ["chain"]["entries"] == 3)
        # عبث بملف معتمد: بصمة المحتوى لا تطابق قيده
        ex3_path = os.path.join(approved_dir, "EX-0003.json")
        rec3 = json.loads(open(ex3_path, encoding="utf-8").read())
        rec3["content"] = "محتوى مزور بعد الاعتماد"
        json.dump(rec3, open(ex3_path, "w", encoding="utf-8"), ensure_ascii=False)
        integ2 = gw.verify_integrity()
        check("السلامة: العبث بملف معتمد يُكشف (بصمة لا تطابق القيد)", not integ2["ok"] and any(m["example_id"] == "EX-0003" for m in integ2["coverage"]["fingerprint_mismatches"]))
        # عبث بسجل الاعتماد نفسه: تعديل قيد يكسر السلسلة
        led_lines = open(gw.adoption_ledger.path, encoding="utf-8").read().splitlines()
        entry = json.loads(led_lines[0])
        entry["decision_ref"] = "قرار مزور"
        led_lines[0] = json.dumps(entry, ensure_ascii=False)
        open(gw.adoption_ledger.path, "w", encoding="utf-8").write("\n".join(led_lines) + "\n")
        check("السلامة: العبث بسجل الاعتماد يكسر سلسلة البصمات", not gw.adoption_ledger.verify_chain()["ok"])

    passed = sum(1 for _, ok in results if ok)
    print(f"\n{passed}/{len(results)} اختبارًا ناجحًا")
    sys.exit(0 if passed == len(results) else 1)


if __name__ == "__main__":
    main()
