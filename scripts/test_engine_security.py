#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""اختبارات الأمان السلبية — محاكاة محاولات تجاوز الصلاحيات والحوكمة.

(دفعة 16-تتمة — التحقق من التكامل بأمر المالك: «لا تعتبر الاختبارات الحالية
وحدها دليلًا كافيًا؛ أضف اختبارات سلبية تحاكي محاولات تجاوز الصلاحيات
والحوكمة»)

كل فحص هنا محاولة اختراق معلنة: الهجوم يُنفذ فعليًا والنجاح المطلوب هو
**فشل الاختراق**، ومعه فحوص ضابطة موجبة تثبت أن المسار المشروع يعمل.
التغطية:
- الهوية: توكن مزور/معدل/منتهي/متصعد + دور نصي من المستدعي + **إنشاء
  Principal مباشرة ببيانات المستدعي (هوية مالك أو صلاحيات موسعة) + الوراثة
  + التعديل بعد الإنشاء + الكائنات المزيفة (__new__ وبط البط — duck typing)
  + رموز owner موقع بمفتاح المنصة (المالك بمفتاحه المستقل حصرًا)**.
- **تزوير واقعي داخل العملية (الإغلاق ليس حدًّا أمنيًا):** بناء هوية بقراءة
  خلايا الإغلاق (`__closure__`) ينجح بنيويًا — موثق كحد ثقة معلن لا كدفاع
  مزعوم — والقبض يتم كريبتوغرافيًا (`TokenAuthority.attest`: لا مفتاح لا
  هوية)، مع بطلان شهادة أي هوية مُسّت حقلها أو شهادتها.
- عزل العملاء: خدمة/عميل/أدمن خارج النطاق — معرفة client_id لا تكفي.
- سجل الموافقات: **تسجيل المنح/الأساس/الانسحاب بهوية موثقة وصلاحية محددة —
  بلا هوية أو بنص granted_by="owner" أو بخارج النطاق أو بغير المالك لأساس
  المالك: كله مرفوض**، مع فحوص موجبة للمسارات المشروعة.
- G-EX: توقيع نصي «owner» + مفتاح غير المالك + إعادة استخدام توقيع +
  مرجع موافقة وهمي + أساس مسحوب + بلا سجل (fail-closed).
- سجل الاعتماد: عبث بملف معتمد أو بالسلسلة يُكشف.
- التخزين: كتابة متزامنة بعمليات فعلية (لا فقد ولا تكرار معرفات) + استعادة.
- الحدود: بيانات المستوى أ (ذاكرة وموافقات) داخل شجرة git مرفوضة.
- استقلالية المحرك: لا استيراد لنموذج/مزود/استضافة في أي ملف engine/.
كل المفاتيح هنا مولدة عشوائية في الذاكرة — لا أسرار في المستودع.
"""
import hashlib
import hmac
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


# ── مهاجم واقعي داخل العملية: قراءة خلايا الإغلاق وبناء هوية كاملة الحقول ────
def _closure_forge(kind, principal_id, clients=frozenset(), all_clients=True,
                  permissions=None, attestation="شهادة-مدعاة-بلا-مفتاح"):
    """استخراج مفتاح الإنشاء من خلايا إغلاق `Principal.__init__` وبناء هوية.

    نموذج التهديد الواقعي: إغلاق Python ليس حدًّا أمنيًا ولا يُدَّعى كذلك —
    البناء ينجح بنيويًا (النوع ذاته وصفاته مكتملة)، والقبض عليه يجب أن يكون
    كريبتوغرافيًا في `attest` (لا يملك مفتاح التوقيع فشهادته مدعاة).
    """
    free = auth.Principal.__init__.__code__.co_freevars
    cells = auth.Principal.__init__.__closure__
    creation_key = cells[free.index("_creation_key")].cell_contents
    return auth.Principal(
        principal_id, kind, frozenset(clients), bool(all_clients),
        frozenset(permissions if permissions is not None
                  else auth._KIND_MAX_PERMS[kind]),
        9999999999,
        _creation=creation_key,
        _attestation=attestation,
    )


def _raises(fn, exc):
    try:
        fn()
        return False
    except exc:
        return True
    except Exception:
        return False


def _raises_any(fn, excs):
    """مثل _raises لكن يقبل مجموعة استثناءات مقبولة (مثل TypeError+ConsentLedgerError
    عند استدعاءات بالشكل القديم الملغى — الرفض الحاد مقبول بأي شكل)."""
    try:
        fn()
        return False
    except excs:
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
        hmac.new(ta._auth_key, esc_body.encode("utf-8"), hashlib.sha256).digest()
    ).rstrip(b"=").decode("ascii")
    check(
        "الهوية: توكن أدمن موقع سليمًا لكنه يدّعي صلاحيات المالك → التحقق يرفضه (سقف النوع)",
        _raises(lambda: ta.verify(esc_body + "." + esc_sig), auth.AuthError),
    )

    # ══ 1-ب) تزييف الهوية بنيويًا: الإنشاء محصور بمسار تحقق التوقيع ═════
    check(
        "الهوية: إنشاء Principal مباشرة ببيانات المستدعي (هوية مالك كاملة) مرفوض",
        _raises(
            lambda: auth.Principal("مزور", auth.KIND_OWNER, frozenset(), True,
                                  frozenset(auth._KIND_MAX_PERMS[auth.KIND_OWNER]), 9999999999),
            auth.AuthError,
        ),
    )
    check(
        "الهوية: إنشاء هوية خدمة بصلاحيات موسعة مباشرةً (بلا رمز) مرفوض",
        _raises(
            lambda: auth.Principal("مزور", auth.KIND_SERVICE, frozenset({"c1"}), False,
                                  frozenset({auth.PERM_MEMORY_HARD_DELETE}), 9999999999),
            auth.AuthError,
        ),
    )
    check(
        "الهوية: وراثة Principal لتجاوز حارس الإنشاء مرفوضة",
        _raises(lambda: type("FakePrincipal", (auth.Principal,), {}), auth.AuthError),
    )
    ok_p = ta.verify(ta.mint(auth.KIND_SERVICE, "session-ok", clients={"c1"}))
    check(
        "الهوية: تعديل صفات الهوية بعد الإنشاء (ترقية إلى مالك) مرفوض",
        _raises(lambda: setattr(ok_p, "kind", auth.KIND_OWNER), auth.AuthError),
    )

    def _resign(body_b64, key):
        raw = base64.urlsafe_b64decode(body_b64 + "=" * (-len(body_b64) % 4))
        sig = hmac.new(key, raw, hashlib.sha256).digest()
        return body_b64 + "." + base64.urlsafe_b64encode(sig).rstrip(b"=").decode("ascii")

    owner_body, _ = ta.mint(auth.KIND_OWNER, "owner-real").split(".")
    check(
        "الهوية: توكن نوع owner موقع بمفتاح المنصة مرفوض (المالك بمفتاحه المستقل حصرًا)",
        _raises(lambda: ta.verify(_resign(owner_body, ta._auth_key)), auth.AuthError),
    )
    svc_body, _ = ta.mint(auth.KIND_SERVICE, "session-s", clients={"c1"}).split(".")
    check(
        "الهوية: توكن نوع خدمة موقع بمفتاح المالك مرفوض (المفتاحان لا يتبادلان الأدوار)",
        _raises(lambda: ta.verify(_resign(svc_body, ta._owner_key)), auth.AuthError),
    )

    class _DuckFakeIdentity:
        """كائن مزيف بواجهة مشابهة — النوع الموثق حصرًا، الواجهة لا تكفي."""
        def can(self, _permission):
            return True
        def can_access_client(self, _client_id):
            return True
        def describe(self):
            return "owner:مزيف"

    mem0 = store.InMemoryMemoryStore()
    check(
        "الهوية: MemoryService ترفض كائنًا مزيفًا بواجهة مشابهة (duck typing لا يعبر)",
        _raises(lambda: service.MemoryService(mem0, _DuckFakeIdentity()), service.MemoryServiceError),
    )
    forged_new = auth.Principal.__new__(auth.Principal)  # إنشاء بلا مسار التحقق
    check(
        "الهوية: MemoryService ترفض هوية أُنشئت بـ__new__ بلا تحقق (رفض نظيف لا انفجار)",
        _raises(lambda: service.MemoryService(mem0, forged_new), service.MemoryServiceError),
    )
    check(
        "الهوية: مفتاح الإنشاء ليس خاصية وحدة (لا يمكن استيراده من الخارج)",
        not hasattr(auth, "_creation_key") and not hasattr(auth, "_PRINCIPAL_CREATION_KEY"),
    )

    # ══ 1-ج) التزوير الواقعي: الإغلاق ليس حدًّا أمنيًا — الشهادة الكريبتوغرافية ══
    genuine_owner_p2 = ta.verify(ta.mint(auth.KIND_OWNER, "owner-real2"))
    genuine_svc_p2 = ta.verify(ta.mint(auth.KIND_SERVICE, "session-ok2", clients={"c1"}))
    check("الشهادة: هوية أصلية (مالك وخدمة) تعبر attest موجبًا",
          ta.attest(genuine_owner_p2) is True and ta.attest(genuine_svc_p2) is True)
    check("الشهادة: سلطة بمفاتيح أخرى ترفض هوية هذه السلطة (attest بحد المفتاح)",
          wrong_authority.attest(genuine_owner_p2) is False)
    forged_owner_p2 = _closure_forge(auth.KIND_OWNER, "owner-real2")
    check("التزوير الواقعي: بناء هوية مالك عبر خلايا الإغلاق ينجح بنيويًا (الإغلاق ليس حدًّا أمنيًا — واقع موثق)",
          auth.is_verified_principal(forged_owner_p2) is True)
    check("التزوير الواقعي: الهوية المبنية بلا مفتاح ترفضها الشهادة الكريبتوغرافية (attest)",
          ta.attest(forged_owner_p2) is False)
    forged_svc_c1 = _closure_forge(auth.KIND_SERVICE, "session-forged", clients={"c1"}, all_clients=False)
    check("حدود الثقة (موثق): البوابة البنيوية MemoryService تعبرها الهوية المبنية داخل العملية — الحد البنيوي ليس كريبتوغرافيًا",
          service.MemoryService(mem0, forged_svc_c1) is not None)
    check("حدود الثقة: الهوية نفسها ترفضها الشهادة عند حامل المفاتيح — لا مفتاح لا هوية",
          ta.attest(forged_svc_c1) is False)
    tampered_p = ta.verify(ta.mint(auth.KIND_ADMIN, "reviewer-up", all_clients=True))
    object.__setattr__(tampered_p, "kind", auth.KIND_OWNER)
    check("التزوير: ترقية هوية أدمن إلى مالك بحقن الحقل (object.__setattr__) تبطل شهادتها",
          ta.attest(tampered_p) is False)
    attest_swapped = ta.verify(ta.mint(auth.KIND_SERVICE, "session-t3", clients={"c1"}))
    object.__setattr__(attest_swapped, "_attestation", "شهادة-مزورة")
    check("التزوير: استبدال الشهادة نفسها في هوية أصلية يبطلها (لا شهادة ذاتية)",
          ta.attest(attest_swapped) is False)
    check("حدود الثقة: OwnerVerifier تحقق-فقط بلا قدرة توقيع (أقل صلاحية للمكونات)",
          not hasattr(ta.owner_verifier(), "sign"))

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
        svc_sec3 = ta.verify(ta.mint(auth.KIND_SERVICE, "session-sec3", clients={"client-1"}))
        client_sec3 = ta.verify(ta.mint(auth.KIND_CLIENT, "client-1"))
        ledger.grant_client_consent(
            reference="consent-A", client_id="client-1", purpose="training",
            usage_scope=["training_only"], granted_at="2026-11-20",
            principal=svc_sec3,
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
        # أساس مسحوب — العميل نفسه يسحب موافقته عبر هويته الموثقة
        ledger.withdraw("consent-A", "2026-11-24", principal=client_sec3, reason="انسحاب")
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

    # ══ 4) سجل الموافقات: الهوية والصلاحية والحدود والقواعد ════════════════
    check("الموافقات: سجل داخل شجرة git مرفوض (بيانات المستوى أ)", _raises(lambda: consent.ConsentLedger(os.path.join(REPO_ROOT, "consent-test")), ValueError))
    with tempfile.TemporaryDirectory() as tmp:
        ledger = consent.ConsentLedger(os.path.join(tmp, "cl"))
        svc_c1 = ta.verify(ta.mint(auth.KIND_SERVICE, "svc-c1", clients={"client-1"}))
        svc_c2 = ta.verify(ta.mint(auth.KIND_SERVICE, "svc-c2", clients={"client-2"}))
        cl1 = ta.verify(ta.mint(auth.KIND_CLIENT, "client-1"))
        cl2 = ta.verify(ta.mint(auth.KIND_CLIENT, "client-2"))
        admin_p = ta.verify(ta.mint(auth.KIND_ADMIN, "reviewer-9", all_clients=True))
        owner_p = ta.verify(ta.mint(auth.KIND_OWNER, "owner-4"))

        def _grant(ref, client_id, principal, **over):
            kw = dict(reference=ref, client_id=client_id, purpose="training",
                      usage_scope=["training_only"], granted_at="2026-11-20",
                      principal=principal)
            kw.update(over)
            return lambda: ledger.grant_client_consent(**kw)

        # الوضع المشروع (موجب) + توثيق هوية المسجل الموثقة
        ev = ledger.grant_client_consent(reference="r1", client_id="client-1", purpose="training",
                                         usage_scope=["training_only"], granted_at="2026-11-20", principal=svc_c1)
        check("الموافقات (موجب): خدمة داخل نطاقها تسجل موافقة عميلها", ev["type"] == "grant")
        check("الموافقات: الحدث يحمل هوية المسجل الموثقة لا نصًا من المستدعي",
              ev["recorded_by"] == svc_c1.describe() and ev["recorded_by_kind"] == "service")

        # لا هوية ولا نص مماثل — الإثبات بتوقيع متحقق حصرًا
        check("الموافقات: تسجيل منح بلا هوية (None) مرفوض",
              _raises_any(_grant("r2", "client-1", None), (consent.ConsentLedgerError, TypeError)))
        check("الموافقات: الشكل النصي القديم granted_by=\"owner\" مرفوض جذريًا",
              _raises_any(lambda: ledger.grant_client_consent(reference="r2", client_id="client-1",
                                                              purpose="training", usage_scope=["training_only"],
                                                              granted_at="2026-11-20", granted_by="owner"),
                          (consent.ConsentLedgerError, TypeError)))
        check("الموافقات: دور نصي «owner» كإثبات هوية مرفوض",
              _raises(_grant("r2", "client-1", "owner"), consent.ConsentLedgerError))
        check("الموافقات: قاموس يدّعي هوية المالك مرفوض",
              _raises(_grant("r2", "client-1", {"kind": "owner", "granted_by": "owner"}), consent.ConsentLedgerError))
        check("الموافقات: هوية مزيفة بـ__new__ مرفوضة من السجل",
              _raises(_grant("r2", "client-1", forged_new), consent.ConsentLedgerError))

        # النطاق والصلاحية لمن يسجل موافقة العميل
        check("الموافقات: خدمة خارج نطاق العميل لا تسجل موافقته",
              _raises(_grant("r3", "client-1", svc_c2), consent.ConsentLedgerError))
        check("الموافقات: أدمن (حوكمة مراجعة) لا يسجل موافقة عميل",
              _raises(_grant("r3", "client-1", admin_p), consent.ConsentLedgerError))
        check("الموافقات: عميل لا يسجل موافقة عميل آخر",
              _raises(_grant("r3", "client-1", cl2), consent.ConsentLedgerError))
        ev_self = ledger.grant_client_consent(reference="r-self", client_id="client-1", purpose="training",
                                              usage_scope=["training_only"], granted_at="2026-11-20", principal=cl1)
        check("الموافقات (موجب): العميل يسجل موافقته هو", ev_self["recorded_by"].startswith("client:client-1"))
        ev_owner_rec = ledger.grant_client_consent(reference="r-owner-rec", client_id="client-1", purpose="training",
                                                   usage_scope=["training_only"], granted_at="2026-11-20", principal=owner_p)
        check("الموافقات (موجب): المالك يسجل موافقة عميل", ev_owner_rec["recorded_by"].startswith("owner:"))

        # القواعد الأساسية للسجل (فوق هوية موثقة)
        check("الموافقات: مرجع مكرر مرفوض (لا التباس في الهوية)",
              _raises(_grant("r1", "client-2", svc_c2, granted_at="2026-11-21"), consent.ConsentLedgerError))
        check("الموافقات: نطاق استخدام غير صالح مرفوض",
              _raises(_grant("r4", "client-1", svc_c1, usage_scope=["everything"]), consent.ConsentLedgerError))
        check("الموافقات: موافقة بلا غرض مرفوضة",
              _raises(_grant("r5", "client-1", svc_c1, purpose=""), consent.ConsentLedgerError))

        # أساس المالك — مالك متحقق بمفتاحه حصرًا
        def _owner_basis(ref, principal, **over):
            kw = dict(reference=ref, purpose="training", usage_scope=["training_only"],
                      decided_at="2026-11-21", decision_ref="قرار-1", principal=principal)
            kw.update(over)
            return lambda: ledger.record_owner_basis(**kw)

        check("الموافقات: خدمة لا تسجل أساس مالك", _raises(_owner_basis("ob-1", svc_c1), consent.ConsentLedgerError))
        check("الموافقات: أدمن لا يسجل أساس مالك", _raises(_owner_basis("ob-1", admin_p), consent.ConsentLedgerError))
        check("الموافقات: عميل لا يسجل أساس مالك", _raises(_owner_basis("ob-1", cl1), consent.ConsentLedgerError))
        ev_ob = ledger.record_owner_basis(reference="ob-1", purpose="training", usage_scope=["training_only"],
                                          decided_at="2026-11-21", decision_ref="قرار-1", principal=owner_p)
        check("الموافقات (موجب): المالك يسجل أساسه والحدث يوثق هويته",
              ev_ob["recorded_by"].startswith("owner:") and ev_ob["decision_ref"] == "قرار-1")

        # الانسحاب — محكوم بالهوية والنطاق ونوع الأساس
        check("الموافقات: انسحاب فوق أساس غير موجود مرفوض",
              _raises(lambda: ledger.withdraw("ghost", "2026-11-24", principal=cl1), consent.ConsentLedgerError))
        check("الموافقات: انسحاب بلا هوية مرفوض",
              _raises_any(lambda: ledger.withdraw("r1", "2026-11-24"), (consent.ConsentLedgerError, TypeError)))
        check("الموافقات: انسحاب بهوية نصية «owner» مرفوض",
              _raises(lambda: ledger.withdraw("r1", "2026-11-24", principal="owner"), consent.ConsentLedgerError))
        w1 = ledger.withdraw("r1", "2026-11-24", principal=cl1, reason="سبب")
        check("الموافقات (موجب): العميل يسحب موافقته هو", w1["recorded_by"].startswith("client:client-1"))
        check("الموافقات: الانسحاب لا يمحو المنح (سجل التدقيق كامل)",
              len([e for e in ledger.all_events() if e["type"] == "grant"]) == 4
              and ledger.lookup("r1")["status"] == "withdrawn")
        check("الموافقات: انسحاب مكرر مرفوض (لا تشويش السجل)",
              _raises(lambda: ledger.withdraw("r1", "2026-11-25", principal=cl1, reason="مرة أخرى"), consent.ConsentLedgerError))
        check("الموافقات: عميل لا ينسحب عن موافقة غيره",
              _raises(lambda: ledger.withdraw("r-self", "2026-11-24", principal=cl2), consent.ConsentLedgerError))
        check("الموافقات: أدمن لا يسجل انسحابًا (أقل صلاحية)",
              _raises(lambda: ledger.withdraw("r-self", "2026-11-24", principal=admin_p), consent.ConsentLedgerError))
        check("الموافقات: خدمة خارج النطاق لا تسجل انسحابًا",
              _raises(lambda: ledger.withdraw("r-self", "2026-11-24", principal=svc_c2), consent.ConsentLedgerError))
        w2 = ledger.withdraw("r-self", "2026-11-24", principal=svc_c1, reason="طلب العميل في الجلسة")
        check("الموافقات (موجب): خدمة نطاقها تسجل انسحاب عميلها", w2["recorded_by"].startswith("service:svc-c1"))
        check("الموافقات: أساس المالك لا يُسحب إلا بهويته (خدمة مرفوضة)",
              _raises(lambda: ledger.withdraw("ob-1", "2026-11-24", principal=svc_c1), consent.ConsentLedgerError))
        check("الموافقات: أساس المالك لا يُسحب إلا بهويته (أدمن مرفوض)",
              _raises(lambda: ledger.withdraw("ob-1", "2026-11-24", principal=admin_p), consent.ConsentLedgerError))
        w3 = ledger.withdraw("ob-1", "2026-11-24", principal=owner_p, reason="قرار مالك")
        check("الموافقات (موجب): المالك يسحب أساسه", w3["recorded_by"].startswith("owner:"))

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
