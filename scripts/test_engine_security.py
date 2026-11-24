#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""اختبارات الأمان السلبية — محاكاة محاولات تجاوز الصلاحيات والحوكمة.

(دفعة 16-تتمة — التحقق من التكامل بأمر المالك: «لا تعتبر الاختبارات الحالية
وحدها دليلًا كافيًا؛ أضف اختبارات سلبية تحاكي محاولات تجاوز الصلاحيات
والحوكمة»)

كل فحص هنا محاولة اختراق معلنة: الهجوم يُنفذ فعليًا والنجاح المطلوب هو
**فشل الاختراق**. تغطية:
- الهوية: توكن مزور/معدل/منتهي/متصعد + دور نصي من المستدعي.
- عزل العملاء: خدمة/عميل/أدمن خارج النطاق — معرفة client_id لا تكفي.
- G-EX: توقيع نصي «owner» + مفتاح غير المالك + إعادة استخدام توقيع +
  مرجع موافقة وهمي + أساس مسحوب + بلا سجل (fail-closed).
- سجل الاعتماد: عبث بملف معتمد أو بالسلسلة يُكشف.
- التخزين: كتابة متزامنة بعمليات فعلية (لا فقد ولا تكرار معرفات) + استعادة.
- الحدود: بيانات المستوى أ (ذاكرة وموافقات) داخل شجرة git مرفوضة.
- استقلالية المحرك: لا استيراد لنموذج/مزود/استضافة في أي ملف engine/.
كل المفاتيح هنا مولدة عشوائية في الذاكرة — لا أسرار في المستودع.
"""
import hashlib
import json
import multiprocessing as mp
import os
import secrets
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from engine import auth  # noqa: E402
from engine.fsafety import FileCorruptionError  # noqa: E402
from engine.learning import consent, gateway  # noqa: E402
from engine.memory import service, store  # noqa: E402

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NOW = "2026-11-24T00:00:00.000Z"


def _raises(fn, exc):
    try:
        fn()
        return False
    except exc:
        return True
    except Exception:
        return False


# ── عامل التزامن: يعمل في عملية مستقلة ويكتب حقائق على المخزن نفسه ─────────
def _concurrent_append_worker(args):
    root, worker_id, n = args
    st = store.JsonlMemoryStore(root)
    for i in range(n):
        st.append_fact({
            "client_id": f"c{worker_id}",
            "fact": f"حقيقة عامل {worker_id} رقم {i}",
            "category": "other", "is_active": True,
            "created_at": NOW, "updated_at": NOW, "source": "chat_extraction",
        })
    return worker_id, n


def main():
    results = []

    def check(name, cond, detail=""):
        results.append((name, bool(cond)))
        mark = "✓" if cond else "✗"
        print(f"  {mark} {name}" + (f" — {detail}" if (detail and not cond) else ""))

    ta = auth.TokenAuthority(secrets.token_bytes(32), secrets.token_bytes(32))
    wrong_authority = auth.TokenAuthority(secrets.token_bytes(32), secrets.token_bytes(32))

    # ══ 1) الهوية: التوكن ════════════════════════════════════════════════
    good = ta.mint(auth.KIND_SERVICE, "session-1", clients={"c1"})
    forged = wrong_authority.mint(auth.KIND_SERVICE, "session-evil", clients={"c1"})
    check("الهوية: توكن موقعة بمفتاح آخر مرفوض", _raises(lambda: ta.verify(forged), auth.AuthError))

    body, sig = good.split(".")
    import base64
    pad = "=" * (-len(body) % 4)
    payload = json.loads(base64.urlsafe_b64decode(body + pad))
    payload["clients"] = ["c2", "c3"]  # تصعيد النطاق بعد التوقيع
    tampered_body = base64.urlsafe_b64encode(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).rstrip(b"=").decode("ascii")
    check("الهوية: تعديل حمولة التوكن (توسيع النطاق) يبطل التوقيع", _raises(lambda: ta.verify(tampered_body + "." + sig), auth.AuthError))

    expired = ta.mint(auth.KIND_SERVICE, "session-old", clients={"c1"}, ttl_seconds=60, now=10_000_000)
    check("الهوية: التوكن المنتهي مرفوض حتى بتوقيع سليم", _raises(lambda: ta.verify(expired, now=10_000_500), auth.AuthError))

    check(
        "الهوية: سك رمز خدمة يدّعي صلاحية الحذف النهائي مرفوض من المصدر",
        _raises(lambda: ta.mint(auth.KIND_SERVICE, "session-x", clients={"c1"}, permissions={"memory:hard_delete"}), auth.AuthError),
    )
    esc = ta.mint(auth.KIND_ADMIN, "reviewer-x", all_clients=True)
    body2, sig2 = esc.split(".")
    pad2 = "=" * (-len(body2) % 4)
    p2 = json.loads(base64.urlsafe_b64decode(body2 + pad2))
    p2["perms"] = ["memory:hard_delete"]  # أدمن يحاول سرقة صلاحية المالك
    esc_body = base64.urlsafe_b64encode(
        json.dumps(p2, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).rstrip(b"=").decode("ascii")
    esc_sig = base64.urlsafe_b64encode(
        __import__("hmac").new(ta._auth_key, esc_body.encode("utf-8"), hashlib.sha256).digest()
    ).rstrip(b"=").decode("ascii")
    check(
        "الهوية: توكن أدمن موقع سليمًا لكنه يدّعي صلاحيات المالك → التحقق يرفضه (سقف النوع)",
        _raises(lambda: ta.verify(esc_body + "." + esc_sig), auth.AuthError),
    )

    # ══ 2) عزل العملاء ════════════════════════════════════════════════════
    mem = store.InMemoryMemoryStore()
    svc_c1 = service.MemoryService(mem, ta.verify(ta.mint(auth.KIND_SERVICE, "session-1", clients={"c1"})))
    # نكتب حقيقة لـ c1 عبر المالك (أسرع من دورة العشر رسائل)
    owner = service.MemoryService(mem, ta.verify(ta.mint(auth.KIND_OWNER, "owner-1")))
    owner.store.append_fact({"client_id": "c1", "fact": "سر العميل الأول", "category": "goal", "is_active": True, "created_at": NOW, "updated_at": NOW, "source": "chat_extraction"})
    owner.store.append_fact({"client_id": "c2", "fact": "سر العميل الثاني", "category": "goal", "is_active": True, "created_at": NOW, "updated_at": NOW, "source": "chat_extraction"})

    check("العزل: خدمة c1 تقرأ c1 طبيعيًا", "سر العميل الأول" in svc_c1.get_injectable_context("c1"))
    check("العزل: خدمة c1 لا تبلغ ذاكرة c2 (حقن) — معرفة المعرف لا تكفي", _raises(lambda: svc_c1.get_injectable_context("c2"), service.AccessDenied))
    check("العزل: خدمة c1 لا تكتب إلى c2 (دورة استخراج)", _raises(lambda: svc_c1.record_exchange("c2", [], "س", "ر", []), service.AccessDenied))
    check("العزل: خدمة c1 لا تراجع حقائق c2", _raises(lambda: svc_c1.review_facts("c2"), service.AccessDenied))
    check("العزل: خدمة c1 لا تلغي تنشيط حقيقة c2", _raises(lambda: svc_c1.deactivate_fact("c2", "MF-000002"), service.AccessDenied))

    client_p = service.MemoryService(mem, ta.verify(ta.mint(auth.KIND_CLIENT, "c1")))
    check("العزل: العميل c1 يرى ذاكرته", "سر العميل الأول" in client_p.get_injectable_context("c1"))
    check("العزل: العميل c1 لا يرى ذاكرة c2", _raises(lambda: client_p.get_injectable_context("c2"), service.AccessDenied))
    check("العزل: العميل لا يكتب دورة استخراج (أقل صلاحية)", _raises(lambda: client_p.record_exchange("c1", [], "س", "ر", []), service.AccessDenied))

    admin_scoped = service.MemoryService(mem, ta.verify(ta.mint(auth.KIND_ADMIN, "reviewer-1", clients={"c1"})))
    check("العزل: أدمن نطاقه c1 يراجع c1", len(admin_scoped.review_facts("c1")) >= 1)
    check("العزل: أدمن نطاقه c1 لا يراجع c2", _raises(lambda: admin_scoped.review_facts("c2"), service.AccessDenied))
    check("العزل: أدمن لا يكتب دورة استخراج", _raises(lambda: admin_scoped.record_exchange("c1", [], "س", "ر", []), service.AccessDenied))
    check("العزل: أدمن لا يحذف نهائيًا (حتى في نطاقه)", _raises(lambda: admin_scoped.hard_delete_fact("c1", "MF-000001", "أمر"), service.AccessDenied))
    check("العزل: خدمة لا تحذف نهائيًا", _raises(lambda: svc_c1.hard_delete_fact("c1", "MF-000001", "أمر"), service.AccessDenied))
    check("العزل: العميل لا يحذف نهائيًا", _raises(lambda: client_p.hard_delete_fact("c1", "MF-000001", "أمر"), service.AccessDenied))

    # ══ 3) G-EX: تجاوز التوقيع والأساس ═══════════════════════════════════
    with tempfile.TemporaryDirectory() as tmp:
        ledger = consent.ConsentLedger(os.path.join(tmp, "consent"))
        ledger.grant_client_consent(
            reference="consent-A", client_id="client-1", purpose="training",
            usage_scope=["training_only"], granted_at="2026-11-20",
        )
        src = os.path.join(tmp, "src.json")
        json.dump({"plan": 1}, open(src, "w", encoding="utf-8"))

        def cand(**over):
            base = {
                "content": json.dumps({"k": 1}, ensure_ascii=False),
                "origin": {"path": src, "sha256": hashlib.sha256(open(src, "rb").read()).hexdigest(), "inspected_at": "2026-11-24"},
                "deid": {"human_review_passed": True, "reviewer": "owner", "reviewed_at": "2026-11-24"},
                "basis": {"kind": "client_consent", "reference": "consent-A"},
                "quality": {"kind": "judge_score", "score": 9},
                "conflicts_resolved": True,
                "usage": "training_only",
            }
            base.update(over)
            return base

        verifier = ta.owner_verifier()
        gw = gateway.ExampleGateway(
            os.path.join(tmp, "approved"), os.path.join(tmp, "archive"),
            consent_ledger=ledger, owner_verifier=verifier,
        )

        # التوقيع النصي القديم — الثغرة الأصلية
        check("G-EX: التوقيع النصي {signer: owner} لا يعتمد شيئًا (الثغرة الأصلية)", _raises(lambda: gw.approve(cand(), {"signer": "owner", "signed_at": "2026-11-24", "decision_ref": "x"}), gateway.GatewayError))
        # مفتاح غير المالك
        wrong_doc = auth.gex_approval_document("قرار", "2026-11-24", hashlib.sha256(cand()["content"].encode()).hexdigest(), cand()["origin"]["sha256"])
        wrong_sig = {"document": wrong_doc, "signature": wrong_authority.owner_sign(wrong_doc)}
        check("G-EX: توقيع بمفتاح ليس مفتاح المالك مرفوض", _raises(lambda: gw.approve(cand(), wrong_sig), gateway.GatewayError))
        # بلا آلية تحقق أصلًا
        gw_noVerifier = gateway.ExampleGateway(os.path.join(tmp, "ap2"), os.path.join(tmp, "ar2"), consent_ledger=ledger)
        check("G-EX: بلا آلية تحقق مالك الاعتماد مرفوض (fail-closed)", _raises(lambda: gw_noVerifier.approve(cand(), {}), gateway.GatewayError))
        # اعتماد مشروع واحد للاستخدام لاحقًا
        c1 = cand()
        doc1 = auth.gex_approval_document("قرار-1", "2026-11-24", hashlib.sha256(c1["content"].encode()).hexdigest(), c1["origin"]["sha256"])
        gw.approve(c1, {"document": doc1, "signature": ta.owner_sign(doc1)})
        # إعادة استخدام التوقيع لمثال آخر
        c2 = cand(content=json.dumps({"k": 2}, ensure_ascii=False))
        check("G-EX: توقيع EX-0001 لا يُعاد استخدامه لاعتماد EX-0002", _raises(lambda: gw.approve(c2, {"document": doc1, "signature": ta.owner_sign(doc1)}), gateway.GatewayError))
        # مرجع وهمي
        check("G-EX: مرجع موافقة مخترع (غير موجود بالسجل) يرفض", not gw.submit(cand(basis={"kind": "client_consent", "reference": "consent-ghost"}))["passed"])
        # أساس مسحوب
        ledger.withdraw("consent-A", "2026-11-24", "انسحاب")
        d2 = auth.gex_approval_document("قرار-2", "2026-11-24", hashlib.sha256(json.dumps({"k": 3}, ensure_ascii=False).encode()).hexdigest(), cand()["origin"]["sha256"])
        check("G-EX: أساس مسحوب بالسجل يمنع الاعتماد الجديد حتى بتوقيع سليم", _raises(lambda: gw.approve(cand(content=json.dumps({"k": 3}, ensure_ascii=False)), {"document": d2, "signature": ta.owner_sign(d2)}), gateway.GatewayError))
        check("G-EX: الأمثلة القديمة للأساس المسحوب تبقى للتدقيق وتُستبعد من الدفعات", gw.check_withdrawal("consent-A") == ["EX-0001"] and os.path.exists(os.path.join(tmp, "approved", "EX-0001.json")))

        # عبث بملف معتمد
        ex1 = os.path.join(tmp, "approved", "EX-0001.json")
        rec = json.loads(open(ex1, encoding="utf-8").read())
        rec["usage"] = "retrieval_only"  # محاولة تعديل ختم الاستخدام
        json.dump(rec, open(ex1, "w", encoding="utf-8"), ensure_ascii=False)
        cov = gw.verify_integrity()
        check("G-EX: تعديل ختم تصنيف الاستخدام بعد الاعتماد يُكشف", not cov["ok"] and any("تصنيف الاستخدام" in m["problem"] for m in cov["coverage"]["fingerprint_mismatches"]))

    # ══ 4) سجل الموافقات: الحدود والقواعد ════════════════════════════════
    check("الموافقات: سجل داخل شجرة git مرفوض (بيانات المستوى أ)", _raises(lambda: consent.ConsentLedger(os.path.join(REPO_ROOT, "consent-test")), ValueError))
    with tempfile.TemporaryDirectory() as tmp:
        ledger = consent.ConsentLedger(os.path.join(tmp, "cl"))
        ledger.grant_client_consent(reference="r1", client_id="client-1", purpose="training", usage_scope=["training_only"], granted_at="2026-11-20")
        check("الموافقات: مرجع مكرر مرفوض (لا التباس في الهوية)", _raises(lambda: ledger.grant_client_consent(reference="r1", client_id="client-2", purpose="training", usage_scope=["training_only"], granted_at="2026-11-21"), consent.ConsentLedgerError))
        check("الموافقات: نطاق استخدام غير صالح مرفوض", _raises(lambda: ledger.grant_client_consent(reference="r2", client_id="client-1", purpose="training", usage_scope=["everything"], granted_at="2026-11-20"), consent.ConsentLedgerError))
        check("الموافقات: موافقة بلا غرض مرفوضة", _raises(lambda: ledger.grant_client_consent(reference="r3", client_id="client-1", purpose="", usage_scope=["training_only"], granted_at="2026-11-20"), consent.ConsentLedgerError))
        check("الموافقات: انسحاب فوق أساس غير موجود مرفوض", _raises(lambda: ledger.withdraw("ghost", "2026-11-24", ""), consent.ConsentLedgerError))
        ledger.withdraw("r1", "2026-11-24", "سبب")
        check("الموافقات: الانسحاب لا يمحو المنح (سجل التدقيق كامل)", len([e for e in ledger.all_events() if e["type"] == "grant"]) == 1 and ledger.lookup("r1")["status"] == "withdrawn")
        check("الموافقات: انسحاب مكرر مرفوض (لا تشويش السجل)", _raises(lambda: ledger.withdraw("r1", "2026-11-25", "مرة أخرى"), consent.ConsentLedgerError))

    # ══ 5) التخزين: تزامن فعلي بعمليات متعددة + استعادة ══════════════════
    with tempfile.TemporaryDirectory() as tmp:
        root = os.path.join(tmp, "memstore")
        store.JsonlMemoryStore(root)  # تهيئة
        workers, per_worker = 4, 25
        with mp.get_context("fork").Pool(workers) as pool:
            pool.map(_concurrent_append_worker, [(root, w, per_worker) for w in range(workers)])
        st = store.JsonlMemoryStore(root)
        rows = st.all_records()
        ids = [r["id"] for r in rows]
        check(f"التخزين: {workers}×{per_worker} كتابة متزامنة بلا فقد (100/100)", len(rows) == workers * per_worker)
        check("التخزين: لا معرفات مكررة تحت التزامن", len(ids) == len(set(ids)))
        clients_seen = {r["client_id"] for r in rows}
        check("التخزين: كل عامل رأى بياناته (لا خلط بين العملاء)", clients_seen == {f"c{w}" for w in range(workers)})

        # استعادة انقطاع كتابة تحت ملف حقيقي
        with open(st.facts_path, "ab") as fh:
            fh.write('{"client_id": "c0", "fact": "مبتو'.encode("utf-8"))
        st_rec = store.JsonlMemoryStore(root)
        check("التخزين: استعادة سطر مبتور بعد حملة تزامن (الـ100 سليمة)", len(st_rec.all_records()) == workers * per_worker)
        check("التخزين: تلف الوسط يبقى صوتًا عاليًا (لا إسقاط صامت)", _raises(_mid_corrupt(st_rec), FileCorruptionError))

    # ══ 6) استقلالية المحرك (قانون §1) ════════════════════════════════════
    forbidden = ("openai", "anthropic", "gemini", "google", "vertex", "bedrock", "boto",
                 "supabase", "cloudflare", "vercel", "requests", "httpx", "urllib",
                 "socket", "azure", "kaggle", "huggingface")
    violations = []
    for dirpath, _dirs, files in os.walk(os.path.join(REPO_ROOT, "engine")):
        for fn in files:
            if not fn.endswith(".py"):
                continue
            path = os.path.join(dirpath, fn)
            text = open(path, encoding="utf-8").read()
            for bad in forbidden:
                if f"import {bad}" in text or f"from {bad}" in text:
                    violations.append(f"{path}: {bad}")
    check("الاستقلالية: صفر استيراد لنموذج/مزود/استضافة في engine/ كلها", violations == [])

    passed = sum(1 for _, ok in results if ok)
    print(f"\n{passed}/{len(results)} اختبارًا ناجحًا")
    sys.exit(0 if passed == len(results) else 1)


def _mid_corrupt(st):
    def run():
        lines = open(st.facts_path, encoding="utf-8").read().splitlines()
        if len(lines) > 2:
            lines[1] = '{"تالف":'
            open(st.facts_path, "w", encoding="utf-8").write("\n".join(lines) + "\n")
        store.JsonlMemoryStore(st.root).all_records()
    return run


if __name__ == "__main__":
    main()
