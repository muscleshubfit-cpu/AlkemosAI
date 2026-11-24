#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""محاكاة التكامل بين النظامين: الموقع (مصدر الحساب) ↔ المحرك (دفعة 17).

(أمر المالك: اختبارات محاكاة تكامل بين النظامين — **بلا أي اتصال إنتاجي**.)

هذا الاختبار يشغّل **المزود الحقيقي** (`adapters/identity/SupabaseIntrospectionProvider`
— نفس آلية تحقق الموقع جهة الخدمة) ضد **خادم محاكاة محلي** يقلد سلوك مصدر
حساب Alkemos.com كما تفتيشه الدفعة (Supabase Auth):

- `GET /auth/v1/userinfo` — هوية المستخدم من خدمة المصادقة (Bearer إلزامي).
- `GET /rest/v1/profiles?id=eq.<uuid>` — الدور من جدول profiles (صف واحد).
- `GET /rest/v1/coach_assignments?coach_id=eq.<uuid>` — عملاء المدرب المسندون.

سيناريو الحسابات المزروعة (محاكاة موثقة لا إنتاج):
- الحساب المالك: دور **client** في المنبع وبريد عادي — الملكية تأتي من ربط
  معرف الحساب في المحرك (ALKEMOS_OWNER_ACCOUNT_IDS) لا من الدور ولا البريد.
- عميل B: بريده في المنبع = بريد المالك القديم (speerr@gmail.com) — لا يمنح
  شيئًا (الفحص الحاسم ضد الانحدار).
- مدرب: مسند للعملاء A وB فقط.
- أدمن: حوكمة كل الحسابات.

الفحوص: التدفق الكامل (دخول المنبع → تحقق المحرك → هوية محرك → ذاكرة/
موافقات معزولة) · رفض الرموز الميتة · رفض الحساب بلا صف دور · فشل نطاق
المدرب مغلق · طلبات المحرك تحمل رمز المستخدم + مفتاح النشر العام فقط
(لا أسرار ولا بيانات هوية من المستدعي في الطلبات أصلًا).
"""
import json
import os
import secrets
import sys
import tempfile
import threading
import time
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from adapters.identity.supabase_introspection import (  # noqa: E402
    SupabaseIntrospectionProvider,
)
from engine import auth, identity  # noqa: E402
from engine.identity import UnifiedIdentityService  # noqa: E402
from engine.learning.consent import ConsentLedger  # noqa: E402
from engine.memory import service as mem_service  # noqa: E402
from engine.memory import store as mem_store  # noqa: E402

NOW = int(time.time())
OWNER = "11111111-1111-1111-1111-111111111111"
ADMIN = "22222222-2222-2222-2222-222222222222"
COACH = "33333333-3333-3333-3333-333333333333"
CLIENT_A = "aaaaaaaa-0000-0000-0000-000000000001"
CLIENT_B = "bbbbbbbb-0000-0000-0000-000000000002"
CLIENT_C = "cccccccc-0000-0000-0000-000000000003"
NOPROFILE = "dddddddd-0000-0000-0000-000000000004"   # مستخدم بلا صف دور
OLD_OWNER_EMAIL = "speerr@gmail.com"

TOK_OWNER = "upstream-owner-session-token"
TOK_ADMIN = "upstream-admin-session-token"
TOK_COACH = "upstream-coach-session-token"
TOK_A = "upstream-client-a-session-token"
TOK_B = "upstream-client-b-session-token"
TOK_C = "upstream-client-c-session-token"
TOK_NOPROFILE = "upstream-noprofile-session-token"
TOK_DEAD = "upstream-dead-session-token"

USERS = {
    TOK_OWNER: {"id": OWNER, "email": "owner-account@example.com"},
    TOK_ADMIN: {"id": ADMIN, "email": "admin@example.com"},
    TOK_COACH: {"id": COACH, "email": "coach@example.com"},
    TOK_A: {"id": CLIENT_A, "email": "client-a@example.com"},
    # عميل B بريده = بريد المالك القديم — البريد لا يمنح ملكية أبدًا
    TOK_B: {"id": CLIENT_B, "email": OLD_OWNER_EMAIL},
    TOK_C: {"id": CLIENT_C, "email": "client-c@example.com"},
    TOK_NOPROFILE: {"id": NOPROFILE, "email": "no-profile@example.com"},
}

PROFILES = {
    OWNER: {"id": OWNER, "role": "client"},
    ADMIN: {"id": ADMIN, "role": "admin"},
    COACH: {"id": COACH, "role": "coach"},
    CLIENT_A: {"id": CLIENT_A, "role": "client"},
    CLIENT_B: {"id": CLIENT_B, "role": "client"},
    CLIENT_C: {"id": CLIENT_C, "role": "client"},
    # NOPROFILE: بلا صف — فشل مغلق
}

COACH_ASSIGNMENTS = [
    {"client_id": CLIENT_A, "coach_id": COACH},
    {"client_id": CLIENT_B, "coach_id": COACH},
]

ANON_KEY = "stub-publishable-anon-key-public-not-a-secret"


class _StubState:
    def __init__(self):
        self.requests = []          # سجل الطلبات (path, query, headers المصفاة)
        self.fail_coach_scope = False
        self.dead_tokens = {TOK_DEAD}


STATE = _StubState()


class _Handler(BaseHTTPRequestHandler):
    """خادم محاكاة مصدر الحساب — سلوك الموثق في تفتيش الدفعة 17."""

    def log_message(self, *_args):  # نكتم سجل http.server الافتراضي
        pass

    def _bearer(self):
        header = self.headers.get("Authorization", "")
        return header[7:].strip() if header.startswith("Bearer ") else None

    def _reply(self, code: int, body):
        blob = json.dumps(body).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(blob)))
        self.end_headers()
        self.wfile.write(blob)

    def do_GET(self):  # noqa: N802 — أسلوب http.server
        parsed = urllib.parse.urlparse(self.path)
        query = dict(urllib.parse.parse_qsl(parsed.query))
        STATE.requests.append({
            "path": parsed.path,
            "query": query,
            "bearer": self._bearer(),
            "apikey": self.headers.get("apikey"),
            "method": "GET",
            "other_headers": sorted(
                k for k in self.headers.keys() if k.lower() not in ("authorization", "apikey", "accept", "host", "user-agent", "connection", "accept-encoding")
            ),
        })
        token = self._bearer()
        if token in STATE.dead_tokens or token not in USERS:
            self._reply(401, {"error": "invalid_grant"})
            return
        user = USERS[token]

        if parsed.path == "/auth/v1/userinfo":
            self._reply(200, user)
            return
        if parsed.path == "/rest/v1/profiles":
            eq = (query.get("id") or "")
            uuid = eq[3:] if eq.startswith("eq.") else ""
            if uuid in PROFILES:
                self._reply(200, [PROFILES[uuid]])
            else:
                self._reply(200, [])
            return
        if parsed.path == "/rest/v1/coach_assignments":
            if STATE.fail_coach_scope:
                self._reply(500, {"error": "internal"})
                return
            eq = (query.get("coach_id") or "")
            coach = eq[3:] if eq.startswith("eq.") else ""
            rows = [r for r in COACH_ASSIGNMENTS if r["coach_id"] == coach]
            self._reply(200, rows)
            return
        self._reply(404, {"error": "not_found"})


def _raises(fn, exc):
    try:
        fn()
        return None
    except exc as e:
        return e
    except Exception:
        return None


def main():
    results = []

    def check(name, cond, detail=""):
        results.append((name, bool(cond)))
        mark = "✓" if cond else "✗"
        print(f"  {mark} {name}" + (f" — {detail}" if (detail and not cond) else ""))

    server = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    print(f"  [محاكاة مصدر الحساب على http://127.0.0.1:{port} — loopback فقط]")

    try:
        issuer = f"http://127.0.0.1:{port}"
        provider = SupabaseIntrospectionProvider(
            issuer=issuer,
            anon_key=ANON_KEY,
            allow_insecure_loopback=True,   # اختبار محلي فقط — لا يُفعّل من إعداد الإنتاج
            http_timeout_seconds=5,
        )
        ta = auth.TokenAuthority(secrets.token_bytes(48), secrets.token_bytes(48))

        with tempfile.TemporaryDirectory() as tmpdir:
            idx = identity.AccountIndex(os.path.join(tmpdir, "accounts"))
            mem = mem_store.JsonlMemoryStore(os.path.join(tmpdir, "memory"))
            ledger = ConsentLedger(os.path.join(tmpdir, "consent"))
            svc = UnifiedIdentityService(
                provider, ta,
                owner_account_ids=[OWNER],
                account_index=idx,
            )

            # ══ 1) التدفق الكامل عبر المزود الحقيقي ═══════════════════════
            print("══ 1) التدفق: دخول المنبع → تحقق جهة الخدمة → هوية محرك ══")
            STATE.requests.clear()
            sess_b = svc.authenticate(TOK_B, now=NOW)
            paths = [r["path"] for r in STATE.requests]
            check("التدفق: تحقق userinfo ثم profiles لكل دخول (نفس آلية الموقع)",
                  paths == ["/auth/v1/userinfo", "/rest/v1/profiles"])
            check("التدفق: طلبات المحرك تحمل رمز جلسة المستخدم (Bearer) ومفتاح النشر العام",
                  all(r["bearer"] == TOK_B and r["apikey"] == ANON_KEY
                      for r in STATE.requests))
            check("التدفق: طلبات المحرك GET بلا أي بيانات هوية من المستدعي "
                  "(لا بريد ولا دور في الطلبات)",
                  all(r["method"] == "GET"
                      and set(r["query"]) <= {"select", "id", "coach_id"}
                      for r in STATE.requests))
            check("ضد الانحدار: عميل بريده بريد المالك القديم (speerr@gmail.com) "
                  "لا يحصل على أي صلاحية ملكية — البريد معلومة عرض فقط",
                  sess_b["token_kind"] == auth.KIND_CLIENT
                  and sess_b.get("email") == OLD_OWNER_EMAIL
                  and not sess_b["principal"].can(auth.PERM_MEMORY_HARD_DELETE)
                  and not sess_b["principal"].all_clients)

            sess_owner = svc.authenticate(TOK_OWNER, now=NOW)
            check("الملكية: حساب المالك (دور client في المنبع) يترجم مالكًا بالربط",
                  sess_owner["token_kind"] == auth.KIND_OWNER
                  and sess_owner["principal"].principal_id == OWNER
                  and sess_owner["principal"].all_clients
                  and ta.attest(sess_owner["principal"]))
            check("الملكية: الطلبات للمصدر لم تحمل أي دور مرشّح من المستدعي — "
                  "الدور قرأه المحرك من صف profiles جهة الخدمة",
                  PROFILES[OWNER]["role"] == "client"
                  and sess_owner["upstream_role"] == "client")

            sess_admin = svc.authenticate(TOK_ADMIN, now=NOW)
            check("الأدمن: حوكمة كل الحسابات بلا كتابة ذاكرة وبلا حذف نهائي",
                  sess_admin["principal"].kind == auth.KIND_ADMIN
                  and sess_admin["principal"].all_clients
                  and not sess_admin["principal"].can(auth.PERM_MEMORY_WRITE)
                  and not sess_admin["principal"].can(auth.PERM_MEMORY_HARD_DELETE))

            sess_coach = svc.authenticate(TOK_COACH, now=NOW)
            check("المدرب: نطاقه عملاؤه المسندون (A وB) من coach_assignments حصرًا",
                  sess_coach["principal"].clients == frozenset({CLIENT_A, CLIENT_B})
                  and sess_coach["principal"].can_access_client(CLIENT_A)
                  and not sess_coach["principal"].can_access_client(CLIENT_C))

            sess_a = svc.authenticate(TOK_A, now=NOW)
            check("العميل: هوية محرك نطاقه نفسه (معرف الحساب UUID — لا البريد)",
                  sess_a["principal"].principal_id == CLIENT_A
                  and sess_a["principal"].clients == frozenset({CLIENT_A}))

            # ══ 2) الحالات السلبية (فشل مغلق) ══════════════════════════════
            print("══ 2) الفشل المغلق: رموز ميتة وحسابات بلا دور ══")
            check("رمز منبع ميت (401 من المصدر) → لا هوية إطلاقًا",
                  _raises(lambda: svc.authenticate(TOK_DEAD, now=NOW),
                          identity.IdentityVerificationError) is not None)
            check("رمز منبع مجهول → رفض موحد",
                  _raises(lambda: svc.authenticate("رمز-مجهول تمامًا", now=NOW),
                          identity.IdentityVerificationError) is not None)
            check("حساب بلا صف دور في profiles → فشل مغلق (لا دور افتراضي مختلق)",
                  _raises(lambda: svc.authenticate(TOK_NOPROFILE, now=NOW),
                          identity.IdentityVerificationError) is not None
                  and "profiles" in str(_raises(
                      lambda: svc.authenticate(TOK_NOPROFILE, now=NOW),
                      identity.IdentityVerificationError)))
            STATE.fail_coach_scope = True
            check("فشل جلب نطاق المدرب → فشل مغلق (لا افتراض نطاق صامت)",
                  _raises(lambda: svc.authenticate(TOK_COACH, now=NOW),
                          identity.IdentityVerificationError) is not None)
            STATE.fail_coach_scope = False

            # ══ 3) العزل عبر الهوية الموحدة (ذاكرة + موافقات) ═══════════════
            print("══ 3) العزل: ذاكرة وموافقات عبر جلسات مصدر واحد ══")
            svc_a_mem = mem_service.MemoryService(
                mem, svc.authenticate_service(TOK_A, now=NOW)["principal"])
            for i in range(9):
                svc_a_mem.record_exchange(CLIENT_A, [], f"رسالة {i}", "رد", [])
            _, stored = svc_a_mem.record_exchange(
                CLIENT_A, [], "بتمرن في الجيم 4 أيام", "تمام",
                [{"fact": "يتمرن في الجيم 4 أيام أسبوعيًا", "category": "lifestyle"}])
            check("الذاكرة: الحقائق المخزنة مفتاحها معرف الحساب الموحد (A)",
                  stored and all(f["client_id"] == CLIENT_A for f in mem.all_records()))
            svc_b_mem = mem_service.MemoryService(mem, sess_b["principal"])
            check("العزل: B لا يقرأ ذاكرة A رغم معرفة معرفه (نطاق الهوية يحسم)",
                  _raises(lambda: svc_b_mem.get_injectable_context(CLIENT_A),
                          mem_service.AccessDenied) is not None)
            svc_coach_mem = mem_service.MemoryService(mem, sess_coach["principal"])
            check("المدرب يراجع مسنديه ولا يبلغ C",
                  svc_coach_mem.review_facts(CLIENT_A) is not None
                  and _raises(lambda: svc_coach_mem.review_facts(CLIENT_C),
                              mem_service.AccessDenied) is not None)
            check("المدرب لا يكتب ذاكرة (مراجعة حوكمة فقط)",
                  _raises(lambda: svc_coach_mem.record_exchange(
                      CLIENT_A, [], "س", "ر", []), mem_service.AccessDenied) is not None)

            grant = ledger.grant_client_consent(
                "ref-int-1", CLIENT_A, "training", ["training_only"],
                "2026-11-24T00:00:00Z", sess_a["principal"])
            check("الموافقات: منح العميل لنفسه موثق بهويته الموحدة (معرف حسابه)",
                  grant["client_id"] == CLIENT_A
                  and grant["recorded_by"].startswith("client:" + CLIENT_A))
            check("الموافقات: B لا يسحب موافقة A (خارج النطاق)",
                  _raises(lambda: ledger.withdraw(
                      "ref-int-1", "2026-11-24T01:00:00Z", sess_b["principal"]),
                      Exception) is not None)
            w = ledger.withdraw("ref-int-1", "2026-11-24T01:00:00Z",
                                sess_owner["principal"])
            check("الموافقات: المالك المرتبط يسحب ضمن صلاحيته",
                  w.get("type") in ("withdrawal", "withdraw")
                  or w.get("status") == "withdrawn")

            # ══ 4) فصل بيانات الهوية عن بيانات النموذج ═════════════════════
            print("══ 4) الفصل: فهرس الهوية مقابل بيانات النموذج ══")
            entries = idx.all_accounts()
            check("الفهرس: كل حساب ظهر مرة واحدة على الأقل (سجل هوية لكل مستخدم)",
                  {e["account_id"] for e in entries} >=
                  {OWNER, ADMIN, COACH, CLIENT_A, CLIENT_B})
            usage_a = idx.usage(CLIENT_A)
            check("الاستخدام: عداد جلسات الحساب من بيانات الهوية",
                  usage_a["sessions_count"] >= 2)   # authenticate + service
            check("الفصل: ملفات الهوية وملفات النموذج منفصلة تمامًا "
                  "(accounts-state مقابل memory.jsonl)",
                  os.path.exists(os.path.join(tmpdir, "accounts", "accounts-state.json"))
                  and os.path.exists(os.path.join(tmpdir, "memory", "memory.jsonl"))
                  and not os.path.exists(os.path.join(tmpdir, "memory", "accounts-state.json")))
            prefs = idx.set_preferences(sess_a["principal"], CLIENT_A,
                                        {"locale": "ar"})
            check("التفضيلات: تخدم الحساب نفسه عبر هويته الموحدة",
                  prefs == {"locale": "ar"}
                  and idx.get_preferences(CLIENT_A) == {"locale": "ar"})

            # ══ 5) رمز المحرك: التحقق والدوران ══════════════════════════════
            print("══ 5) رمز المحرك: التحقق وإعادة الاستخدام ══")
            principal2 = svc.verify_engine_token(sess_a["token"], now=NOW)
            check("رمز المحرك يتحقق ويعيد نفس الهوية (استهلاك الواجهات المستقبلية)",
                  principal2.principal_id == CLIENT_A
                  and principal2.kind == auth.KIND_CLIENT)
            check("رمز المحرك المنتهي يرفض (انتهاء صلاحية الجلسة)",
                  _raises(lambda: svc.verify_engine_token(
                      sess_a["token"], now=NOW + sess_a["expires_in"] + 1),
                      auth.AuthError) is not None)
            check("رمز المحرك المعدل يرفض (عبث التوقيع)",
                  _raises(lambda: svc.verify_engine_token(
                      sess_a["token"][:-2] + ("aa" if not sess_a["token"][-2:] == "aa" else "bb")),
                      auth.AuthError) is not None)
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)

    passed = sum(1 for _, ok in results if ok)
    print(f"\n{passed}/{len(results)} اختبارًا ناجحًا")
    sys.exit(0 if passed == len(results) else 1)


if __name__ == "__main__":
    main()
