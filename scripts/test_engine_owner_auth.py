#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""اختبارات أمن مصادقة المالك — الهوية والمصادقة والصلاحيات والتزوير والاستعادة.

(دفعة 16 — أمر المالك: اعتماد هوية المالك الأساسية الوحيدة + مصادقة آمنة
بالبريد وكلمة المرور مع رمز تحقق عبر البريد + استعادة الوصول + اختبارات
أمنية لمسارات المصادقة والصلاحيات والتزوير واستعادة الوصول)

كل فحص هنا إعلان صريح عن الهجوم أو المسار المشروع:
- **الهوية الوحيدة:** حساب واحد لبريد المالك الأساسي (engine/settings) —
  دخول/استعادة لغيره مرفوضة برسالة موحدة (anti-enumeration)، لا إنشاء
  ثانٍ، وحساب مخزن ببريد آخر يُرفض عند التحميل (لا مصالحة صامتة).
- **المصادقة:** كلمة مرور خاطئة · رمز خاطئ/مكرر/منتهي/مستنزف · إصدار رمز
  جديد يبطل القديم · بلا رمز (سياسة) الدخول الكامل مباشرة.
- **القفل التدريجي:** 5 إخفاقات تقفل؛ الدخول الصحيح داخل القفل مرفوع؛
  القفل ينتهي بمروره؛ العدادات تبقى عبر إعادة تحميل المخزن (إعادة تشغيل).
- **التزوير (نموذج تهديد واقعي — الإغلاق ليس حدًّا أمنيًا):** بناء هوية
  مالك كاملة الحقول بقراءة خلايا الإغلاق (`__closure__`) **ينجح بنيويًا**
  (هذا مقبول كواقع) لكنه **يُرفض كريبتوغرافيًا** في العمليات الحساسة
  (`attest` — لا مفتاح لا هوية)؛ وتعديل حقل هوية أصلية عبر
  `object.__setattr__` يبطل شهادتها.
- **الصلاحيات:** الخدمة/الأدمن/العميل لا يغيّرون كلمة المرور ولا يدوّرون
  الرموز؛ رمز مالك بمعرّف غير البريد الأساسي لا يحكم الحساب؛ الهوية
  المنتهية مرفوضة.
- **الاستعادة:** رمز استعادة خاطئ مرفوض؛ الصحيح يعيد الوصول ويستبدل
  كلمة المرور ويولّد رموزًا جديدة؛ الرمز المستهلك لا يُعاد؛ استنزاف
  الرموز بالتجربة يُقفل كالدخول.
- **حماية البيانات:** كلمة المرور/الرمز نصًّا لا يسكن أي ملف (بصمات فقط)؛
  الحالة المقنّنة بلا أسرار؛ العبث بالملف يُكشف (تكامل ذاتي)؛ JSON تالف
  صوت عالٍ لا إعادة تعيين صامتة؛ المخزن داخل شجرة git مرفوض.
كل المفاتيح وكلمات المرور هنا مولدة عشوائية/اصطناعية — لا أسرار في المستودع.
"""
import json
import os
import secrets
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from engine import auth, owner_auth, settings  # noqa: E402

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FAST_KDF = {"n": 2 ** 10, "r": 8, "p": 1}     # سريع للاختبارات فقط — السجل يحمل معاملاته
OWNER = settings.OWNER_EMAIL_PRIMARY
PASSWORD = "استراتيجية-قوية-2026!حقًا"
PASSWORD2 = "استراتيجية-أقوى-2026!حقًا"
NOW = 2_000_000_000


def _raises(fn, exc):
    try:
        fn()
        return None
    except exc as e:
        return e
    except Exception:
        return None


def _closure_forge_owner_principal():
    """مهاجم داخل العملية يقرأ خلايا الإغلاق ويبني هوية مالك كاملة الحقول.

    نموذج التهديد الواقعي: إغلاق Python ليس حدًّا أمنيًا — استخراج مفتاح
    الإنشاء من `Principal.__init__.__closure__` ممكن، فيُبنى كائن متين
    بنيويًا (هوية المالك الأساسية + كل الصلاحيات + عمر بعيد). النجاح
    المطلوب من الدفاع: رفضه **كريبتوغرافيًا** في `attest` (لا يملك
    مفتاح المالك فشهادته مدعاة).
    """
    free = auth.Principal.__init__.__code__.co_freevars
    cells = auth.Principal.__init__.__closure__
    creation_key = cells[free.index("_creation_key")].cell_contents
    return auth.Principal(
        OWNER, auth.KIND_OWNER, frozenset(), True,
        frozenset(auth._KIND_MAX_PERMS[auth.KIND_OWNER]), 9999999999,
        _creation=creation_key,
        _attestation="شهادة-مدعاة-بلا-مفتاح",
    )


def main():
    results = []

    def check(name, cond, detail=""):
        results.append((name, bool(cond)))
        mark = "✓" if cond else "✗"
        print(f"  {mark} {name}" + (f" — {detail}" if (detail and not cond) else ""))

    ta = auth.TokenAuthority(secrets.token_bytes(32), secrets.token_bytes(32))
    wrong_ta = auth.TokenAuthority(secrets.token_bytes(32), secrets.token_bytes(32))

    # ══ 0) الإعدادات: هوية المالك الأساسية الوحيدة ══════════════════════════
    check("الإعدادات: هوية المالك الأساسية الوحيدة هي بريد المالك المعتمد",
          settings.OWNER_EMAIL_PRIMARY == "speerr@gmail.com")
    check("الإعدادات: تقنين البريد يقبل حالة الأحرف والفراغات ويرفض غيره",
          settings.is_primary_owner_email("  SPEERR@GMAIL.COM ")
          and not settings.is_primary_owner_email("other@gmail.com")
          and not settings.is_primary_owner_email(""))

    # ══ 1) الإعداد الأول والحساب الوحيد ═════════════════════════════════════
    with tempfile.TemporaryDirectory() as tmp:
        root = os.path.join(tmp, "owner-auth")
        store = owner_auth.OwnerAuthStore(root)
        svc = owner_auth.OwnerAuthService(ta, store, kdf=FAST_KDF)

        r = svc.bootstrap_owner(PASSWORD)
        check("الإعداد: حساب المالك ينشأ لبريد المالك الأساسي فقط",
              r["status"] == "bootstrapped" and r["email"] == OWNER)
        check("الإعداد: رموز الاستعادة تولد مرة واحدة (8) وتُخزن بصماتها لا نصوصها",
              len(r["recovery_codes"]) == 8
              and all(len(c) == 20 for c in r["recovery_codes"]))
        check("الإعداد: bootstrap ثانٍ مرفوض — لا حساب بديل أبدًا",
              _raises(lambda: svc.bootstrap_owner(PASSWORD), owner_auth.OwnerAuthError) is not None)
        check("الإعداد: كلمة مرور قصيرة مرفوضة من المصدر",
              _raises(lambda: svc.bootstrap_owner("قصيرة"), owner_auth.OwnerAuthError) is not None)
        check("الإعداد: كلمة مرور تحوي البريد مرفوضة",
              _raises(lambda: svc.bootstrap_owner(OWNER), owner_auth.OwnerAuthError) is not None)

        # ══ 2) الدخول: كلمة المرور ثم رمز البريد ═══════════════════════════
        e_wrong = _raises(lambda: svc.begin_login(OWNER, "خطأ-كامل"), owner_auth.OwnerAuthError)
        e_unknown = _raises(lambda: svc.begin_login("x@gmail.com", PASSWORD), owner_auth.OwnerAuthError)
        check("الدخول: كلمة المرور الخاطئة مرفوضة برسالة موحدة",
              e_wrong is not None and str(e_wrong) == owner_auth._MSG_CREDENTIALS)
        check("الدخول: بريد غير المالك مرفوض بنفس الرسالة حرفيًا (anti-enumeration)",
              e_unknown is not None and str(e_unknown) == str(e_wrong))

        st = svc.begin_login("  SPEERR@GMAIL.COM ", PASSWORD)
        code = st.get("delivery_code")
        check("الدخول: كلمة المرور الصحيحة تطلب رمز البريد (خطوة ثانية)",
              st["status"] == "code_required" and code is not None and len(code) == 6)

        fin = svc.complete_login(OWNER, code)
        check("الدخول: الرمز الصحيح يسكّ هوية مالك موثقة sub=البريد الأساسي",
              fin["status"] == "authenticated"
              and fin["principal"].kind == auth.KIND_OWNER
              and fin["principal"].principal_id == OWNER)
        check("الدخول: الرمز الصادر موقع بمفتاح المالك المستقل (سلطة أخرى ترفضه)",
              _raises(lambda: wrong_ta.verify(fin["token"]), auth.AuthError) is not None
              and ta.verify(fin["token"]) is not None)

        p = fin["principal"]
        check("الدخول: الهوية تعبر الشهادة الكريبتوغرافية (attest موجب)",
              ta.attest(p) is True)

        check("الدخول: رمز البريد أحادي الاستخدام — إعادة استخدامه مرفوضة",
              _raises(lambda: svc.complete_login(OWNER, code), owner_auth.OwnerAuthError) is not None)

        # محاولات خاطئة على الرمز
        st2 = svc.begin_login(OWNER, PASSWORD)
        code2 = st2["delivery_code"]
        rejected, last_exc = True, None
        for _ in range(owner_auth.CODE_MAX_ATTEMPTS):
            e = _raises(lambda: svc.complete_login(OWNER, "000000" if code2 != "000000" else "111111"),
                         owner_auth.OwnerAuthError)
            rejected = rejected and e is not None
            last_exc = e
        check(f"الدخول: {owner_auth.CODE_MAX_ATTEMPTS} محاولات رمز خاطئة تستنزف الرمز (يُطلب جديد)",
              rejected and last_exc is not None and "رمزًا جديدًا" in str(last_exc))

        # إصدار جديد يبطل القديم
        st3 = svc.begin_login(OWNER, PASSWORD)
        old_code = st3["delivery_code"]
        st4 = svc.begin_login(OWNER, PASSWORD)
        new_code = st4["delivery_code"]
        check("الدخول: إصدار رمز جديد يبطل المعلق القديم (لا رمزان نشطان)",
              old_code != new_code
              and _raises(lambda: svc.complete_login(OWNER, old_code), owner_auth.OwnerAuthError) is not None
              and svc.complete_login(OWNER, new_code)["status"] == "authenticated")

        # رمز منتهي
        st5 = svc.begin_login(OWNER, PASSWORD, now=NOW)
        expired_e = _raises(
            lambda: svc.complete_login(OWNER, st5["delivery_code"], now=NOW + owner_auth.CODE_TTL_SECONDS + 1),
            owner_auth.OwnerAuthError)
        check("الدخول: رمز البريد المنتهي عمره مرفوض (10 دقائق)",
              expired_e is not None and "انتهت" in str(expired_e))

        # بلا رمز (سياسة أدنى): دخول كامل بالخطوة الأولى
        store2 = owner_auth.OwnerAuthStore(os.path.join(tmp, "owner-auth-nocode"))
        svc_nc = owner_auth.OwnerAuthService(
            ta, store2, require_email_code=False, kdf=FAST_KDF)
        svc_nc.bootstrap_owner(PASSWORD)
        direct = svc_nc.begin_login(OWNER, PASSWORD)
        check("الدخول (سياسة): بلا رمز بريد → هوية كاملة من الخطوة الأولى",
              direct["status"] == "authenticated" and ta.attest(direct["principal"]))

        # ══ 3) القفل التدريجي (محاولات فاشلة) ════════════════════════════════
        store3 = owner_auth.OwnerAuthStore(os.path.join(tmp, "owner-auth-lock"))
        svc_lock = owner_auth.OwnerAuthService(ta, store3, kdf=FAST_KDF)
        svc_lock.bootstrap_owner(PASSWORD)
        for _ in range(owner_auth.LOGIN_MAX_FAILURES):
            _raises(lambda: svc_lock.begin_login(OWNER, "خطأ"), owner_auth.OwnerAuthError)
        check("القفل: 5 إخفاقات كلمة مرور تقفل الحساب مؤقتًا",
              svc_lock.status()["locked"] is True)
        check("القفل: كلمة المرور الصحيحة داخل القفل مرفوضة أيضًا",
              _raises(lambda: svc_lock.begin_login(OWNER, PASSWORD), owner_auth.OwnerAuthError) is not None)
        # القفل ينتهي بمروره (حقن الزمن)
        ok_after = svc_lock.begin_login(OWNER, PASSWORD, now=NOW + owner_auth.LOCKOUT_BASE_SECONDS + 60)
        check("القفل: القفل ينتهي بمرور مدته فيقبل الدخول الصحيح",
              ok_after["status"] == "code_required")

        # العدادات عبر إعادة تحميل (محاكاة إعادة تشغيل)
        store4 = owner_auth.OwnerAuthStore(os.path.join(tmp, "owner-auth-persist"))
        svc_p1 = owner_auth.OwnerAuthService(ta, store4, kdf=FAST_KDF)
        svc_p1.bootstrap_owner(PASSWORD)
        for _ in range(owner_auth.LOGIN_MAX_FAILURES):
            _raises(lambda: svc_p1.begin_login(OWNER, "خطأ"), owner_auth.OwnerAuthError)
        svc_p2 = owner_auth.OwnerAuthService(
            ta, owner_auth.OwnerAuthStore(os.path.join(tmp, "owner-auth-persist")), kdf=FAST_KDF)
        check("القفل: حالة القفل تبقى عبر إعادة تحميل المخزن (إعادة تشغيل)",
              svc_p2.status()["locked"] is True
              and _raises(lambda: svc_p2.begin_login(OWNER, PASSWORD), owner_auth.OwnerAuthError) is not None)

        # ══ 4) التزوير: الإغلاق ليس حدًّا أمنيًا — القبض كريبتوغرافيًا ═══════
        forged = _closure_forge_owner_principal()
        check("التزوير: بناء هوية عبر قراءة خلايا الإغلاق ينجح بنيويًا (الإغلاق ليس حدًّا أمنيًا — واقع موثق)",
              auth.is_verified_principal(forged) is True)
        check("التزوير: الهوية المبنية بلا مفتاح تفشل الشهادة الكريبتوغرافية (attest يرفضها)",
              ta.attest(forged) is False)
        check("التزوير: العمليات الحساسة ترفض الهوية المزورة (تغيير كلمة المرور)",
              _raises(lambda: svc.change_password(forged, PASSWORD, PASSWORD2), owner_auth.OwnerAuthError) is not None)
        check("التزوير: العمليات الحساسة ترفض الهوية المزورة (تدوير رموز الاستعادة)",
              _raises(lambda: svc.rotate_recovery_codes(forged), owner_auth.OwnerAuthError) is not None)

        # تعديل حقل هوية أصلية عبر object.__setattr__ (تجاوز حارس التعديل)
        genuine = ta.verify(ta.mint(auth.KIND_OWNER, OWNER))
        tampered = ta.verify(ta.mint(auth.KIND_ADMIN, "reviewer-x", all_clients=True))
        object.__setattr__(tampered, "kind", auth.KIND_OWNER)
        check("التزوير: ترقية هوية أدمن إلى مالك بحقن الحقل تبطل شهادتها (attest يرفضها)",
              ta.attest(tampered) is False)
        check("التزوير: الهوية الأصلية غير الممسوسة تبقى مقبولة (تحكم موجب)",
              ta.attest(genuine) is True)

        # ══ 5) الصلاحيات: من يحكم الحساب الحساس ═════════════════════════════
        store5 = owner_auth.OwnerAuthStore(os.path.join(tmp, "owner-auth-perms"))
        svc5 = owner_auth.OwnerAuthService(ta, store5, kdf=FAST_KDF)
        svc5.bootstrap_owner(PASSWORD)
        svc_principal = ta.verify(ta.mint(auth.KIND_SERVICE, "session-1", clients={"c1"}))
        admin_principal = ta.verify(ta.mint(auth.KIND_ADMIN, "reviewer-1", all_clients=True))
        client_principal = ta.verify(ta.mint(auth.KIND_CLIENT, "c1"))
        other_owner = ta.verify(ta.mint(auth.KIND_OWNER, "not-the-owner@example.com"))
        check("الصلاحيات: هوية خدمة لا تغيّر كلمة مرور المالك",
              _raises(lambda: svc5.change_password(svc_principal, PASSWORD, PASSWORD2), owner_auth.OwnerAuthError) is not None)
        check("الصلاحيات: هوية أدمن لا تغيّر كلمة مرور المالك",
              _raises(lambda: svc5.change_password(admin_principal, PASSWORD, PASSWORD2), owner_auth.OwnerAuthError) is not None)
        check("الصلاحيات: هوية عميل لا تدوّر رموز استعادة المالك",
              _raises(lambda: svc5.rotate_recovery_codes(client_principal), owner_auth.OwnerAuthError) is not None)
        check("الصلاحيات: رمز مالك بمعرّف غير البريد الأساسي لا يحكم الحساب",
              _raises(lambda: svc5.change_password(other_owner, PASSWORD, PASSWORD2), owner_auth.OwnerAuthError) is not None)
        # هوية مالك صادرة في الماضي بعيدًا (صحيحة عند الإصدار ثم انتهت فعليًا)
        expired_owner = ta.verify(ta.mint(auth.KIND_OWNER, OWNER, now=10_000_000), now=10_000_001)
        check("الصلاحيات: هوية مالك منتهية عمرها مرفوضة للعمليات الحساسة",
              _raises(lambda: svc5.change_password(expired_owner, PASSWORD, PASSWORD2), owner_auth.OwnerAuthError) is not None)

        # تغيير كلمة المرور بالمسار الصحيح
        cp = svc5.change_password(genuine, PASSWORD, PASSWORD2)
        check("كلمة المرور (موجب): هوية المالك المثبتة تغيّرها بنجاح",
              cp["status"] == "password_changed")
        check("كلمة المرور: القديمة لا تعمل بعد التغيير والجديدة تعمل",
              _raises(lambda: svc5.begin_login(OWNER, PASSWORD), owner_auth.OwnerAuthError) is not None
              and svc5.begin_login(OWNER, PASSWORD2)["status"] == "code_required")
        check("كلمة المرور: تغيير بكلمة حالية خاطئة مرفوض",
              _raises(lambda: svc5.change_password(genuine, PASSWORD, "أخرى-قوية-2026!هذه"), owner_auth.OwnerAuthError) is not None)

        # ══ 6) استعادة الوصول ════════════════════════════════════════════════
        store6 = owner_auth.OwnerAuthStore(os.path.join(tmp, "owner-auth-rec"))
        svc6 = owner_auth.OwnerAuthService(ta, store6, kdf=FAST_KDF)
        boot = svc6.bootstrap_owner(PASSWORD)
        check("الاستعادة: بريد غير المالك لا يستعيد الوصول (رسالة موحدة)",
              _raises(lambda: svc6.recover_access("x@gmail.com", boot["recovery_codes"][0], PASSWORD2),
                       owner_auth.OwnerAuthError) is not None)
        check("الاستعادة: رمز استعادة خاطئ مرفوض برسالة موحدة",
              _raises(lambda: svc6.recover_access(OWNER, "deadbeef" * 3, PASSWORD2),
                       owner_auth.OwnerAuthError) is not None)
        rec = svc6.recover_access(OWNER, boot["recovery_codes"][3], PASSWORD2)
        check("الاستعادة (موجب): رمز صحيح + كلمة جديدة يعيدان الوصول",
              rec["status"] == "access_recovered"
              and len(rec["recovery_codes"]) == owner_auth.RECOVERY_CODES_COUNT)
        check("الاستعادة: كلمة المرور القديمة ملغاة والجديدة تعمل",
              _raises(lambda: svc6.begin_login(OWNER, PASSWORD), owner_auth.OwnerAuthError) is not None
              and svc6.begin_login(OWNER, PASSWORD2)["status"] == "code_required")
        check("الاستعادة: الرمز المستهلك لا يُعاد استعماله",
              _raises(lambda: svc6.recover_access(OWNER, boot["recovery_codes"][3], "كلمة-ثالثة-قوية!2026"),
                       owner_auth.OwnerAuthError) is not None)
        check("الاستعادة: رموز المجموعة القديمة كلها بطلت (رمز آخر غير مستعمل منها مرفوض)",
              _raises(lambda: svc6.recover_access(OWNER, boot["recovery_codes"][0], "كلمة-رابعة-قوية!2026"),
                       owner_auth.OwnerAuthError) is not None)
        rec2 = svc6.recover_access(OWNER, rec["recovery_codes"][5], "كلمة-خامسة-قوية!2026")
        check("الاستعادة (موجب): رموز المجموعة الجديدة تعمل في استعادة ثانية",
              rec2["status"] == "access_recovered")

        # استنزاف رموز الاستعادة بالتجربة يقفل كالدخول
        store7 = owner_auth.OwnerAuthStore(os.path.join(tmp, "owner-auth-rec-lock"))
        svc7 = owner_auth.OwnerAuthService(ta, store7, kdf=FAST_KDF)
        svc7.bootstrap_owner(PASSWORD)
        for _ in range(owner_auth.LOGIN_MAX_FAILURES):
            _raises(lambda: svc7.recover_access(OWNER, "bad" * 10, "كلمة-بديلة-قوية!2026"),
                     owner_auth.OwnerAuthError)
        check("الاستعادة: استنزاف الرموز بالتجربة يقفل الحساب (قفل تدريجي مشترك)",
              svc7.status()["locked"] is True)

        # ══ 7) حماية بيانات المصادقة ══════════════════════════════════════════
        state_file = store.state_path
        state_text = open(state_file, encoding="utf-8").read()
        events_text = open(store.events_path, encoding="utf-8").read()
        check("البيانات: كلمة المرور لا تسكن ملف الحساب نصًّا (بصمة scrypt فقط)",
              PASSWORD not in state_text and PASSWORD2 not in state_text
              and '"alg": "scrypt"' in state_text)
        check("البيانات: رمز البريد لا يسكن ملف الحساب ولا سجل الأحداث نصًّا (بصماته فقط)",
              code not in state_text and code not in events_text
              and all(c not in state_text for c in r["recovery_codes"][:2]))
        st_mask = svc.status()
        st_json = json.dumps(st_mask, ensure_ascii=False)
        allowed_keys = {"account_exists", "primary_email", "created_at", "updated_at",
                        "locked", "locked_until", "pending_code", "recovery_codes_remaining"}
        check("البيانات: الحالة المقنّنة للواجهة قائمة مفاتيح آمنة معلنة بلا أي سر أو بصمة",
              set(st_mask.keys()) <= allowed_keys
              and "hash" not in st_json and "salt" not in st_json
              and not any(c in st_json for c in r["recovery_codes"][:2])
              and st_mask["primary_email"] == OWNER)
        all_events = (
            {e["event"] for e in svc.audit_events()}
            | {e["event"] for e in svc5.audit_events()}
            | {e["event"] for e in svc6.audit_events()}
            | {e["event"] for e in svc_lock.audit_events()}
        )
        check("البيانات: سجل الأحداث يوثق كل مسار (إنشاء/إصدار رمز/دخول/فشل/قفل/تغيير/استعادة)",
              {"account_bootstrapped", "email_code_issued", "login_ok", "login_failed",
               "email_code_failed", "locked_out", "password_changed", "recovery_completed"}
              <= all_events)

        # العبث والتلف
        tampered_state = json.loads(state_text)
        tampered_state["password"]["hash"] = "00" * 32
        with open(state_file, "w", encoding="utf-8") as fh:
            json.dump(tampered_state, fh, ensure_ascii=False)
        check("العبث: تعديل بصمة كلمة المرور يُكشف بتكامل الحالة الذاتي (لا نجاح صامت)",
              _raises(lambda: svc.begin_login(OWNER, PASSWORD), (owner_auth.OwnerAuthError, owner_auth.OwnerAuthDataError)) is not None)

        # JSON تالف: صوت عالٍ لا إعادة تعيين صامتة
        store8 = owner_auth.OwnerAuthStore(os.path.join(tmp, "owner-auth-corrupt"))
        svc8 = owner_auth.OwnerAuthService(ta, store8, kdf=FAST_KDF)
        svc8.bootstrap_owner(PASSWORD)
        with open(store8.state_path, "w", encoding="utf-8") as fh:
            fh.write("{تالف تمامًا")
        e_corrupt = _raises(lambda: svc8.begin_login(OWNER, PASSWORD), owner_auth.OwnerAuthDataError)
        check("التلف: ملف حساب تالف يرفع خطأ صريحًا — لا إعادة تعيين صامتة تسمح بإنشاء حساب جديد",
              e_corrupt is not None and "لا إعادة تعيين" in str(e_corrupt))
        check("التلف: bootstrap فوق ملف تالف مرفوض أيضًا (لا تسكع بيانات غير موثوقة)",
              _raises(lambda: svc8.bootstrap_owner(PASSWORD), owner_auth.OwnerAuthDataError) is not None)

        # حساب مخزن ببريد آخر (انحراف الإعدادات)
        store9 = owner_auth.OwnerAuthStore(os.path.join(tmp, "owner-auth-mismatch"))
        svc9 = owner_auth.OwnerAuthService(ta, store9, kdf=FAST_KDF)
        svc9.bootstrap_owner(PASSWORD)
        st_txt = json.loads(open(store9.state_path, encoding="utf-8").read())
        st_txt.pop("integrity", None)
        st_txt["email"] = "someone-else@gmail.com"
        st_txt["integrity"] = owner_auth._state_integrity(st_txt)
        with open(store9.state_path, "w", encoding="utf-8") as fh:
            json.dump(st_txt, fh, ensure_ascii=False)
        check("الهوية: حساب مخزن ببريد غير الأساسي يُرفض عند التحميل (لا مصالحة صامتة)",
              _raises(lambda: svc9.begin_login(OWNER, PASSWORD), owner_auth.OwnerAuthDataError) is not None)

        # حدود الثقة: OwnerVerifier تحقق-فقط (لا قدرة توقيع)
        verifier = ta.owner_verifier()
        doc = {"probe": 1}
        check("حدود الثقة: OwnerVerifier تحقق-فقط — بلا أي قدرة توقيع",
              not hasattr(verifier, "sign")
              and verifier.verify(doc, ta.owner_sign(doc)) is True
              and verifier.verify(doc, "زائف") is False)

        # كلمات المرور: الدوال النقية
        rec_pw = owner_auth.hash_password(PASSWORD, **{**FAST_KDF, "salt": secrets.token_bytes(16)})
        rec_pw2 = owner_auth.hash_password(PASSWORD, **{**FAST_KDF, "salt": secrets.token_bytes(16)})
        check("kdf: scrypt بملح فردي — نفس كلمة المرور بصمتان مختلفتان والتحقق زمن-ثابت",
              rec_pw["hash"] != rec_pw2["hash"]
              and owner_auth.verify_password(PASSWORD, rec_pw) is True
              and owner_auth.verify_password(PASSWORD2, rec_pw) is False)
        check("kdf: السجل يحمل معاملاته فيُتحقق بها (لا انكسار عند ترقية المعاملات)",
              owner_auth.verify_password(PASSWORD, rec_pw) and all(
                  k in rec_pw for k in ("n", "r", "p", "dklen", "salt", "hash", "alg")))

    # ══ 8) حدود المستوى أ: بيانات المصادقة خارج المستودع ════════════════════
    check("الحدود: مخزن مصادقة داخل شجرة git مرفوض (بيانات المستوى أ)",
          _raises(lambda: owner_auth.OwnerAuthStore(os.path.join(REPO_ROOT, "owner-auth-test")), ValueError) is not None)
    check("الحدود: مسار نسبي مرفوض للمخزن (مسار مطلق إلزامي)",
          _raises(lambda: owner_auth.OwnerAuthStore("relative/path"), owner_auth.OwnerAuthDataError) is not None)

    passed = sum(1 for _, ok in results if ok)
    print(f"\n{passed}/{len(results)} اختبارًا ناجحًا")
    sys.exit(0 if passed == len(results) else 1)


if __name__ == "__main__":
    main()
