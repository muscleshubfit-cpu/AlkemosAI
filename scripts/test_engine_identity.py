#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""اختبارات الهوية الموحدة — العقد والمحلل والمزودات والفهرس والعزل (دفعة 17).

(أمر المالك: نظام حساب موحد بين Alkemos.com وAlkemosAI — Alkemos.com مصدر
الهوية الأساسي، ولا اعتماد على بريد أو بيانات من المستدعي لإثبات الهوية
أو الدور، والملكية لا تُستنبط من البريد أبدًا.)

كل فحص هنا إعلان صريح عن الهجوم أو المسار المشروع:
- **العقد:** معرف الحساب UUID قانوني حصرًا (البريد مرفوض) · الحساب الموثق
  لا يُنشأ ببيانات المستدعي (الإغلاق حارس) · مسارات المطالبات المبدوءة
  ببيانات المستخدم القابلة للكتابة (user_metadata) مرفوضة.
- **المحلل:** الملكية بربط معرف الحساب لا بالبريد ولا بالدور (حساب ببريد
  المالك القديم speerr@gmail.com ليس مالكًا؛ وحساب المالك المرتبط بدور
  client في المنبع هو المالك) · أدمن → حوكمة كل الحسابات بلا حذف نهائي ·
  مدرب → أدمن بنطاق مسنديه حصرًا (وبلا مسندين: عميل لنفسه) · عميل → نفسه ·
  دور مجهول → فشل مغلق · عمر رمز المحرك لا يتجاوز جلسة المنبع والجلسة
  المنتهية مرفوضة قبل السك.
- **مزود JWKS:** توقيع RS256 حقيقي بمفاتيح مولدة محليًا (توليد RSA نظيف
  رياضيًا للاختبار فقط) — عبث الحمولة يبطل التوقيع · انتهاء/مستقبل/مصدر/
  جمهور/مفتاح مجهول يرفض · تدوير المفاتيح (kid جديد) يعمل · user_metadata
  مصدر دور مرفوض من البناء · ES256 مرفوض برسالة صريحة (فجوة موثقة).
- **الخدمة:** الباب العام يقبل رمز منبع معتم فقط (لا بريد ولا دور في
  التوقيع أصلًا) · الرموز المجهولة ترفض برسالة موحدة · جلسة الخدمة نطاقها
  الحساب نفسه · تبديل المزود يحفظ هوية الحساب نفسها (معرف الحساب مفتاح
  الوحدة).
- **الفهرس (فصل الهوية عن النموذج):** بيانات الهوية في فهرس خارج المستودع
  ومفاتيح بيانات النموكز مختلفة تمامًا · التفضيلات محكومة بنطاق هوية
  موثقة · العبث يُكشف (تكامل ذاتي) · داخل شجرة git مرفوض.
- **العزل عبر الهوية:** عميلان مختلفان عبر جلسات هوية موحدة — لا يبلغ
  أحدهما ذاكرة الآخر مهما عُرف معرفه · الموافقة للعميل نفسه والانسحاب
  خارج النطاق مرفوض.
كل المفاتيح والرموز هنا مولدة عشوائية/اصطناعية — لا أسرار في المستودع،
ولا أي اتصال شبكي خارج loopback الاختباري (محاكاة فقط).
"""
import base64
import hashlib
import json
import os
import secrets
import sys
import tempfile
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from engine import auth, identity, settings  # noqa: E402
from engine.identity import (  # noqa: E402
    ROLE_ADMIN,
    ROLE_CLIENT,
    ROLE_COACH,
    AccountIndex,
    IdentityResolver,
    ServiceProofError,
    ServiceProofVerifier,
    StaticProvider,
    UnifiedIdentityService,
    canonical_account_id,
    parse_service_caller_keys,
)
from adapters.identity.jwks import JwksProvider  # noqa: E402
from engine.memory import service as mem_service  # noqa: E402
from engine.memory import store as mem_store  # noqa: E402

NOW = 2_000_000_000
OWNER = "11111111-1111-1111-1111-111111111111"
ADMIN = "22222222-2222-2222-2222-222222222222"
COACH = "33333333-3333-3333-3333-333333333333"
COACH2 = "33333333-3333-3333-3333-333333333334"   # مدرب بلا مسندين
CLIENT_A = "aaaaaaaa-0000-0000-0000-000000000001"
CLIENT_B = "bbbbbbbb-0000-0000-0000-000000000002"
CLIENT_C = "cccccccc-0000-0000-0000-000000000003"
OLD_OWNER_EMAIL = "speerr@gmail.com"   # بريد المالك القديم — لم يعد هوية


def _raises(fn, exc):
    try:
        fn()
        return None
    except exc as e:
        return e
    except Exception:
        return None


# ── توليد RSA نقي للاختبار (لا مكتبات خارجية — قانون المحرك) ─────────────
def _is_probable_prime(n: int, rounds: int = 24) -> bool:
    if n < 2:
        return False
    for p in (2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37):
        if n % p == 0:
            return n == p
    d, r = n - 1, 0
    while d % 2 == 0:
        d //= 2
        r += 1
    for _ in range(rounds):
        a = 2 + secrets.randbelow(n - 3)
        x = pow(a, d, n)
        if x in (1, n - 1):
            continue
        for _ in range(r - 1):
            x = pow(x, 2, n)
            if x == n - 1:
                break
        else:
            return False
    return True


def _gen_prime(bits: int) -> int:
    while True:
        cand = secrets.randbits(bits) | (1 << (bits - 1)) | 1
        if _is_probable_prime(cand):
            return cand


def _gen_rsa_keypair(bits: int = 2048):
    """زوج RSA للاختبار فقط (ليس للاستخدام الإنتاجي).

    يضبط طول المعيار n بالضبط ``bits`` بتًا (إعادة المحاولة حتى يتحقق)
    — ضروري لسياسة الحد الأدنى 2048 بت (مراجعة دفعة 17): مفتاح "2048"
    أقصر من 2048 فعليًا يرفضه المزود، فالاختبارات تحتاج أطوالًا دقيقة
    للموجبة (2048) والسالبة (512/1024/2047).
    """
    e = 65537
    while True:
        p = _gen_prime(bits // 2)
        q = _gen_prime(bits - bits // 2)
        if p == q:
            continue
        n = p * q
        if n.bit_length() != bits:
            continue
        phi = (p - 1) * (q - 1)
        try:
            d = pow(e, -1, phi)
        except ValueError:
            continue
        return {"n": n, "e": e, "d": d, "bits": bits}


def _b64e(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


_SHA256_DIGEST_INFO_PREFIX = bytes.fromhex("3031300d060960864801650304020105000420")


def _rsa_sign_sha256(key: dict, message: bytes) -> bytes:
    k = (key["n"].bit_length() + 7) // 8
    digest_info = _SHA256_DIGEST_INFO_PREFIX + hashlib.sha256(message).digest()
    em = b"\x00\x01" + b"\xff" * (k - len(digest_info) - 3) + b"\x00" + digest_info
    m = int.from_bytes(em, "big")
    return pow(m, key["d"], key["n"]).to_bytes(k, "big")


def _jwk_of(key: dict, kid: str) -> dict:
    k = (key["n"].bit_length() + 7) // 8
    return {
        "kty": "RSA", "use": "sig", "alg": "RS256", "kid": kid,
        "n": _b64e(key["n"].to_bytes(k, "big")),
        "e": _b64e(key["e"].to_bytes(3, "big")),
    }


def _make_jwt(key: dict, kid: str, payload: dict, *, alg: str = "RS256",
              sig_key: dict = None, tamper_payload: str = None) -> str:
    """بناء JWT اختباري — التوقيع على الحمولة الأصلية ثم (اختياريًا) العبث
    بالحمولة بعد التوقيع (tamper_payload) لمحاكاة المهاجم الذي يعدل المحتوى."""
    header = {"alg": alg, "typ": "JWT", "kid": kid}
    header_b64 = _b64e(json.dumps(header, separators=(",", ":")).encode())
    payload_b64 = _b64e(json.dumps(payload, separators=(",", ":")).encode())
    signing_input = header_b64.encode() + b"." + payload_b64.encode()
    sig = _rsa_sign_sha256(sig_key or key, signing_input)
    if tamper_payload is not None:
        payload_b64 = _b64e(tamper_payload.encode())
    return f"{header_b64}.{payload_b64}.{_b64e(sig)}"


def _jwks_provider(key: dict, kid: str, **kw):
    jwks = {"keys": [_jwk_of(key, kid)]}
    fetch_state = {"doc": jwks, "calls": 0}

    def fetcher():
        fetch_state["calls"] += 1
        return fetch_state["doc"]

    provider = JwksProvider(
        issuer="https://accounts.alkemos.test",
        jwks_fetcher=fetcher,
        **kw,
    )
    return provider, fetch_state


def _make_service_proof(key: dict, kid: str, account_id: str, upstream_token: str,
                        *, now: int, ttl: int = 120, aud=None, sub=None,
                        iat=None, exp=None):
    """برهان خادم اختباري — يوقّع بمفتاح الموقع الخاص (نموذج خادم الموقع).

    (مراجعة دفعة 17 — حد الثقة بين الموقع والمحرك): هكذا يبني خادم
    الموقع الموثوق برهانه المرتبط برمز الجلسة وحسابها؛ الأشكال المعطوبة
    (aud/sub/العمر) تُمرر عبر المعاملات لفحص الرفض.
    """
    from engine.identity.server_proof import PROOF_AUDIENCE

    payload = {
        "aud": PROOF_AUDIENCE if aud is None else aud,
        "sub": account_id if sub is None else sub,
        "tok": hashlib.sha256(upstream_token.encode("utf-8")).hexdigest(),
        "iat": (now - 10) if iat is None else iat,
        "exp": (now + ttl) if exp is None else exp,
    }
    return _make_jwt(key, kid, payload)


def main():
    results = []

    def check(name, cond, detail=""):
        results.append((name, bool(cond)))
        mark = "✓" if cond else "✗"
        print(f"  {mark} {name}" + (f" — {detail}" if (detail and not cond) else ""))

    ta = auth.TokenAuthority(secrets.token_bytes(48), secrets.token_bytes(48))

    # ══ 1) عقد الحساب الموثق ════════════════════════════════════════════════
    print("══ 1) العقد: معرف الحساب والحساب الموثق ══")
    check("المعرف: UUID قانوني يقرأ كانونيًا (صغير بشرطات)",
          canonical_account_id(CLIENT_A.upper()) == CLIENT_A)
    check("المعرف: الصورة بلا شرطات تتقنن إلى الكانونية",
          canonical_account_id(CLIENT_A.replace("-", "")) == CLIENT_A)
    check("المعرف: البريد ليس معرف حساب — مرفوض (قانون الهوية الموحدة)",
          _raises(lambda: canonical_account_id(OLD_OWNER_EMAIL), identity.AccountContractError) is not None)
    check("المعرف: القيمة الفارغة/غير النصية مرفوضة",
          _raises(lambda: canonical_account_id(""), identity.AccountContractError) is not None
          and _raises(lambda: canonical_account_id(None), identity.AccountContractError) is not None)
    check("المعرف: is_canonical يميز بلا استثناء",
          identity.is_canonical_account_id(CLIENT_A) and not identity.is_canonical_account_id(OLD_OWNER_EMAIL))

    forged = _raises(
        lambda: identity.VerifiedAccount(
            CLIENT_A, ROLE_CLIENT, frozenset(), "x@y.z", CLIENT_A,
            None, NOW, "forged",
        ),
        identity.IdentityError,
    )
    check("الحساب الموثق: لا إنشاء مباشر ببيانات المستدعي (إغلاق الإنشاء)",
          forged is not None)
    check("الحساب الموثق: is_verified_account يرفض النصوص والقواميس والأدوار",
          not identity.is_verified_account("client")
          and not identity.is_verified_account({"account_id": CLIENT_A, "role": ROLE_CLIENT})
          and not identity.is_verified_account(None))
    check("العقد: مسار مطالبة يبدأ ببيانات المستخدم (user_metadata) مرفوض",
          _raises(lambda: identity.parse_claim_path("user_metadata,role"),
                   identity.AccountContractError) is not None)
    check("العقد: مسار مطالبة متحكم به (app_metadata,engine_role) مقبول",
          identity.parse_claim_path("app_metadata,engine_role") == ("app_metadata", "engine_role"))
    check("العقد: مسار فارغ = بلا مسار (None)",
          identity.parse_claim_path("") is None and identity.parse_claim_path(None) is None)

    # ══ 2) المحلل: الترجمة بأقل صلاحية والملكية بالربط ══════════════════════
    print("══ 2) المحلل: الملكية بالربط والترجمة والدور والعمر ══")
    resolver = IdentityResolver(ta, owner_account_ids=[OWNER])
    static = StaticProvider({
        "tok-owner-client-role": {"account_id": OWNER, "role": ROLE_CLIENT,
                                   "email": "not-the-owner@example.com"},
        "tok-a": {"account_id": CLIENT_A, "role": ROLE_CLIENT, "email": OLD_OWNER_EMAIL},
        "tok-b": {"account_id": CLIENT_B, "role": ROLE_CLIENT},
        "tok-admin": {"account_id": ADMIN, "role": ROLE_ADMIN},
        "tok-coach": {"account_id": COACH, "role": ROLE_COACH,
                       "scope": [CLIENT_A, CLIENT_B]},
        "tok-coach-empty": {"account_id": COACH2, "role": ROLE_COACH, "scope": []},
    })
    # (مراجعة دفعة 17) حد الثقة لبوابة الخدمة: مفاتيح خادم الموقع العامة
    # المثبتة + برهان موقع بمفتاحه الخاص — لا جلسة خدمة برمز الجلسة وحده.
    site_key = _gen_rsa_keypair()
    site_kid = "site-backend-1"
    site_verifier = ServiceProofVerifier({site_kid: (site_key["n"], site_key["e"])})
    svc = UnifiedIdentityService(static, ta, owner_account_ids=[OWNER],
                                 service_proof_verifier=site_verifier)
    svc_ungated = UnifiedIdentityService(static, ta, owner_account_ids=[OWNER])

    sess_owner = svc.authenticate("tok-owner-client-role", now=NOW)
    check("الملكية: حساب مرتبط بدور client في المنبع يترجم مالكًا (الربط لا الدور)",
          sess_owner["token_kind"] == auth.KIND_OWNER
          and sess_owner["principal"].all_clients
          and sess_owner["principal"].principal_id == OWNER)
    check("الملكية: رمز المالك موقع بمفتاح المالك المستقل (attest يثبت)",
          sess_owner["principal"].kind == auth.KIND_OWNER
          and ta.attest(sess_owner["principal"]) is True)
    check("الملكية: المالك يملك الحذف النهائي (صلاحية فريدة)",
          sess_owner["principal"].can(auth.PERM_MEMORY_HARD_DELETE)
          and sess_owner["principal"].can(auth.PERM_CONSENT_OWNER_BASIS))

    sess_a = svc.authenticate("tok-a", now=NOW)
    check("ضد الانحدار: حساب ببريد المالك القديم speerr@gmail.com ليس مالكًا "
          "— البريد لا يمنح ملكية أبدًا (أمر المالك)",
          sess_a["token_kind"] == auth.KIND_CLIENT
          and not sess_a["principal"].all_clients
          and not sess_a["principal"].can(auth.PERM_MEMORY_HARD_DELETE)
          and sess_a.get("email") == OLD_OWNER_EMAIL)
    check("العميل: نطاقه نفسه حصرًا (معرف الحساب — لا البريد)",
          sess_a["principal"].principal_id == CLIENT_A
          and sess_a["principal"].clients == frozenset({CLIENT_A})
          and sess_a["principal"].can_access_client(CLIENT_A)
          and not sess_a["principal"].can_access_client(CLIENT_B))
    check("العميل: لا كتابة ذاكرة ولا مراجعة حوكمة (أقل صلاحية)",
          not sess_a["principal"].can(auth.PERM_MEMORY_WRITE)
          and not sess_a["principal"].can(auth.PERM_MEMORY_REVIEW))

    sess_admin = svc.authenticate("tok-admin", now=NOW)
    check("الأدمن: حوكمة كل الحسابات (all_clients) بلا كتابة وبلا حذف نهائي",
          sess_admin["principal"].kind == auth.KIND_ADMIN
          and sess_admin["principal"].all_clients
          and sess_admin["principal"].can(auth.PERM_MEMORY_REVIEW)
          and not sess_admin["principal"].can(auth.PERM_MEMORY_WRITE)
          and not sess_admin["principal"].can(auth.PERM_MEMORY_HARD_DELETE))

    sess_coach = svc.authenticate("tok-coach", now=NOW)
    check("المدرب: أدمن بنطاق مسنديه حصرًا (A وB) — لا يبلغ C",
          sess_coach["principal"].kind == auth.KIND_ADMIN
          and sess_coach["principal"].clients == frozenset({CLIENT_A, CLIENT_B})
          and sess_coach["principal"].can_access_client(CLIENT_A)
          and not sess_coach["principal"].can_access_client(CLIENT_C))
    sess_coach2 = svc.authenticate("tok-coach-empty", now=NOW)
    check("المدرب بلا مسندين: عميل لنفسه فقط (أقل صلاحية — لا نطاق حوكمة)",
          sess_coach2["principal"].kind == auth.KIND_CLIENT
          and sess_coach2["principal"].clients == frozenset({COACH2}))

    check("الدور المجهول: فشل مغلق (لا افتراض دور)",
          _raises(lambda: StaticProvider({"tok-x": {"account_id": CLIENT_C, "role": "wizard"}})
                  .verify_upstream_token("tok-x", now=NOW),
                  identity.IdentityVerificationError) is not None)

    # ── العمر: سقف جلسة المنبع ────────────────────────────────────────────
    static_exp = StaticProvider({
        "tok-expired": {"account_id": CLIENT_A, "role": ROLE_CLIENT, "expires_at": NOW - 1},
        "tok-short": {"account_id": CLIENT_B, "role": ROLE_CLIENT, "expires_at": NOW + 100},
    })
    svc_exp = UnifiedIdentityService(static_exp, ta, owner_account_ids=[OWNER])
    check("الجلسة المنتهية في المنبع: مرفوضة قبل السك (لا هوية بجلسة ميتة)",
          _raises(lambda: svc_exp.authenticate("tok-expired", now=NOW),
                   identity.IdentityError) is not None)
    sess_short = svc_exp.authenticate("tok-short", now=NOW)
    check("العمر: رمز المحرك لا يتجاوز انتهاء جلسة المنبع (سقف صلب)",
          sess_short["expires_at"] <= NOW + 100
          and _raises(lambda: svc_exp.verify_engine_token(sess_short["token"], now=NOW + 101),
                      auth.AuthError) is not None)
    check("العمر: الرمز الصالح يعمل قبل انتهائه",
          svc_exp.verify_engine_token(sess_short["token"], now=NOW).principal_id == CLIENT_B)
    sess_long = svc.authenticate("tok-b", now=NOW)
    check("العمر: بلا انتهاء منبع معروف = العمر الافتراضي (12 ساعة)",
          sess_long["expires_at"] == NOW + 12 * 3600)

    # ── جلسة الخدمة: نطاق الحساب نفسه + برهان الخادم (مراجعة دفعة 17) ──
    proof_a = _make_service_proof(site_key, site_kid, CLIENT_A, "tok-a", now=NOW)
    sess_svc = svc.authenticate_service("tok-a", server_proof=proof_a, now=NOW)
    check("جلسة الخدمة: برهان خادم صحيح + رمز المنبع → نطاق الحساب نفسه مع كتابة الذاكرة",
          sess_svc["token_kind"] == auth.KIND_SERVICE
          and sess_svc["principal"].clients == frozenset({CLIENT_A})
          and sess_svc["principal"].can(auth.PERM_MEMORY_WRITE)
          and not sess_svc["principal"].can_access_client(CLIENT_B))
    check("جلسة الخدمة بلا حساب موثق: مرفوضة (رمز منبع فقط)",
          _raises(lambda: svc.authenticate_service("رمز-مجهول", now=NOW,
                                                   server_proof=proof_a),
                  identity.IdentityVerificationError) is not None)

    # ══ 2-ب) حد الثقة لبوابة الخدمة (مراجعة دفعة 17 — أمر المالك) ═══════
    # لا هوية service (كتابة الذاكرة) بمجرد امتلاك رمز جلسة العميل:
    # الاستدعاء يجب أن يثبت أنه صادر من خادم الموقع الموثوق (برهان موقع
    # RS256 بمفتاح خاص يقيم عند الموقع؛ المحرك يتحقق بالمفتاح العام
    # المثبت فقط — لا سر مشترك)، وكل ما عدا ذلك يُرفض.
    print("══ 2-ب) حد الثقة: بوابة الخدمة ببرهان الخادم ══")
    check("حد الثقة: امتلاك رمز جلسة العميل وحده لا يفتح بوابة الخدمة (بلا برهان خادم)",
          _raises(lambda: svc.authenticate_service("tok-a", now=NOW),
                  ServiceProofError) is not None)
    check("حد الثقة: برهان فارغ/معطوب الشكل مرفوض",
          _raises(lambda: svc.authenticate_service("tok-a", server_proof="..", now=NOW),
                  ServiceProofError) is not None)
    check("حد الثقة: بلا مفاتيح خادم مثبتة البوابة معطلة كليًا (فشل مغلق)",
          _raises(lambda: svc_ungated.authenticate_service("tok-a",
                                                            server_proof=proof_a, now=NOW),
                  ServiceProofError) is not None)
    rogue_key = _gen_rsa_keypair()
    rogue_proof = _make_service_proof(rogue_key, site_kid, CLIENT_A, "tok-a", now=NOW)
    check("حد الثقة: برهان موقع بمفتاح غير المثبت مرفوض (لا تحقق بمفتاح مجهول)",
          _raises(lambda: svc.authenticate_service("tok-a", server_proof=rogue_proof,
                                                   now=NOW),
                  ServiceProofError) is not None)
    check("حد الثقة: برهان لرمز جلسة آخر مرفوض (ربط البرهان بالرمز — لا إعادة استخدام)",
          _raises(lambda: svc.authenticate_service("tok-b", server_proof=proof_a,
                                                   now=NOW),
                  ServiceProofError) is not None)
    proof_for_b = _make_service_proof(site_key, site_kid, CLIENT_B, "tok-b", now=NOW)
    cross = _raises(lambda: svc.authenticate_service("tok-b", server_proof=proof_a,
                                                      now=NOW),
                    ServiceProofError)
    ok_b = svc.authenticate_service("tok-b", server_proof=proof_for_b, now=NOW)
    check("حد الثقة: برهان لحساب غير حساب الرمز مرفوض (ربط البرهان بالحساب)",
          cross is not None and ok_b["principal"].clients == frozenset({CLIENT_B}))
    expired_proof = _make_service_proof(site_key, site_kid, CLIENT_A, "tok-a",
                                        now=NOW - 10_000)
    check("حد الثقة: البرهان المنتهي مرفوض",
          _raises(lambda: svc.authenticate_service("tok-a", server_proof=expired_proof,
                                                   now=NOW),
                  ServiceProofError) is not None)
    long_proof = _make_service_proof(site_key, site_kid, CLIENT_A, "tok-a",
                                     now=NOW, ttl=3600)
    check("حد الثقة: البرهان فوق سقف العمر (300ث) مرفوض — البراهين قصيرة حصرًا",
          _raises(lambda: svc.authenticate_service("tok-a", server_proof=long_proof,
                                                   now=NOW),
                  ServiceProofError) is not None)
    future_proof = _make_service_proof(site_key, site_kid, CLIENT_A, "tok-a",
                                       now=NOW, iat=NOW + 500, exp=NOW + 600)
    check("حد الثقة: البرهان الصادر في المستقبل مرفوض",
          _raises(lambda: svc.authenticate_service("tok-a", server_proof=future_proof,
                                                   now=NOW),
                  ServiceProofError) is not None)
    bad_aud_proof = _make_service_proof(site_key, site_kid, CLIENT_A, "tok-a",
                                        now=NOW, aud="someone-else")
    check("حد الثقة: برهان بجمهور غير بوابة الخدمة مرفوض (لا يعاد لغرض آخر)",
          _raises(lambda: svc.authenticate_service("tok-a", server_proof=bad_aud_proof,
                                                   now=NOW),
                  ServiceProofError) is not None)
    # إعداد مفاتيح الخادم: الصيغة وسياسة القوة عند الإعداد
    check("إعداد مفاتيح الخادم: الصيغة kid:n_hex:e_hex تعمل (مفتاح عام 2048+)",
          list(parse_service_caller_keys(
              f"{site_kid}:{hex(site_key['n'])}:{hex(site_key['e'])}"
          ).keys()) == [site_kid])
    weak_key = _gen_rsa_keypair(1024)
    check("إعداد مفاتيح الخادم: مفتاح أضعف من 2048 بت مرفوض عند الإعداد (نفس السياسة)",
          _raises(lambda: parse_service_caller_keys(
              f"k:{hex(weak_key['n'])}:{hex(weak_key['e'])}"),
                  ServiceProofError) is not None)
    check("إعداد مفاتيح الخادم: صيغة ملتبسة مرفوضة بصوت عالٍ",
          _raises(lambda: parse_service_caller_keys("kid:not-hex"),
                  ServiceProofError) is not None)
    check("إعداد مفاتيح الخادم: kid مكرر مرفوض",
          _raises(lambda: parse_service_caller_keys(
              f"{site_kid}:{hex(site_key['n'])}:{hex(site_key['e'])},"
              f"{site_kid}:{hex(site_key['n'])}:{hex(site_key['e'])}"),
                  ServiceProofError) is not None)
    check("إعداد مفاتيح الخادم: القيمة الفارغة = لا مفاتيح (البوابة معطلة)",
          parse_service_caller_keys("") == {})

    check("التحقق من رمز المحرك: نفس سلطة TokenAuthority (بلا مسار جديد)",
          svc.verify_engine_token(sess_owner["token"], now=NOW).kind == auth.KIND_OWNER)

    # ── تبديل المزود: الهوية ثابتة عبر المزودين ─────────────────────────────
    key, kid = _gen_rsa_keypair(), "k1"
    jwks_provider, fetch_state = _jwks_provider(
        key, kid, role_claim_path="app_metadata,engine_role",
    )
    payload_admin = {
        "iss": "https://accounts.alkemos.test", "sub": ADMIN,
        "iat": NOW - 60, "exp": NOW + 3600,
        "email": OLD_OWNER_EMAIL,
        "app_metadata": {"engine_role": ROLE_ADMIN},
    }
    token_admin = _make_jwt(key, kid, payload_admin)
    account_via_jwks = jwks_provider.verify_upstream_token(token_admin, now=NOW)
    sess_admin2 = UnifiedIdentityService(
        jwks_provider, ta, owner_account_ids=[OWNER]
    ).authenticate(token_admin, now=NOW)
    check("تبديل المزود: نفس الحساب عبر مزودين مختلفين = نفس معرف الهوية",
          account_via_jwks.account_id == ADMIN
          and sess_admin2["principal"].principal_id == ADMIN
          and sess_admin2["token_kind"] == auth.KIND_ADMIN)
    check("تبديل المزود: بريد المالك القديم في مطالبات منبع آخر لا يصنع مالكًا",
          not sess_admin2["principal"].can(auth.PERM_MEMORY_HARD_DELETE))

    # ══ 3) مزود JWKS: التوقيع غير المتماثل ─════════════════════════════════
    print("══ 3) مزود JWKS: توقيع RS256 والمطالبات والحالات السلبية ══")
    check("JWKS: رأس جلب المفاتيح يُقرأ من مصدر واحد (jwks_url XOR jwks_fetcher)",
          _raises(lambda: JwksProvider(issuer="https://x.test", jwks_url="https://x.test/k",
                                        jwks_fetcher=lambda: {}),
                  identity.AccountContractError) is not None)
    check("JWKS: HTTPS إلزامي — رابط http لغير loopback مرفوض من البناء",
          _raises(lambda: JwksProvider(issuer="http://accounts.alkemos.test",
                                        jwks_url="http://x.test/k"),
                  identity.AccountContractError) is not None)
    check("JWKS: مسار دور من user_metadata مرفوض من البناء (كتابة المستخدم)",
          _raises(lambda: JwksProvider(issuer="https://x.test", jwks_url="https://x.test/k",
                                        role_claim_path="user_metadata,role"),
                  identity.AccountContractError) is not None)

    ok_account = jwks_provider.verify_upstream_token(token_admin, now=NOW)
    check("JWKS: رمز صحيح يمر (دور الأدمن من app_metadata المتحكم بها)",
          ok_account.role == ROLE_ADMIN and ok_account.account_id == ADMIN)

    tampered = _make_jwt(key, kid, payload_admin, tamper_payload=json.dumps(
        {**payload_admin, "sub": OWNER, "app_metadata": {"engine_role": ROLE_ADMIN}}
    ))
    check("JWKS: عبث الحمولة بعد التوقيع (ترقية sub للمالك) يبطل التوقيع",
          _raises(lambda: jwks_provider.verify_upstream_token(tampered, now=NOW),
                   identity.IdentityVerificationError) is not None)

    other_key = _gen_rsa_keypair()
    wrong_key_token = _make_jwt(other_key, kid, payload_admin)
    check("JWKS: توقيع بمفتاح آخر بنفس kid يرفض",
          _raises(lambda: jwks_provider.verify_upstream_token(wrong_key_token, now=NOW),
                   identity.IdentityVerificationError) is not None)

    expired_payload = {**payload_admin, "exp": NOW - 10}
    check("JWKS: رمز منتهي الصلاحية يرفض",
          _raises(lambda: jwks_provider.verify_upstream_token(
              _make_jwt(key, kid, expired_payload), now=NOW),
              identity.IdentityVerificationError) is not None)
    future_iat = {**payload_admin, "iat": NOW + 10_000}
    check("JWKS: رمز صادر في المستقبل يرفض",
          _raises(lambda: jwks_provider.verify_upstream_token(
              _make_jwt(key, kid, future_iat), now=NOW),
              identity.IdentityVerificationError) is not None)
    future_nbf = {**payload_admin, "nbf": NOW + 10_000}
    check("JWKS: nbf مستقبلية يرفض",
          _raises(lambda: jwks_provider.verify_upstream_token(
              _make_jwt(key, kid, future_nbf), now=NOW),
              identity.IdentityVerificationError) is not None)
    bad_iss = {**payload_admin, "iss": "https://evil.example"}
    check("JWKS: مصدر (iss) غير مطابق يرفض",
          _raises(lambda: jwks_provider.verify_upstream_token(
              _make_jwt(key, kid, bad_iss), now=NOW),
              identity.IdentityVerificationError) is not None)

    aud_provider, _ = _jwks_provider(key, "k-aud", audience="alkemos-engine")
    aud_ok = {**payload_admin, "aud": "alkemos-engine"}
    aud_list = {**payload_admin, "aud": ["other", "alkemos-engine"]}
    aud_bad = {**payload_admin, "aud": "someone-else"}
    check("JWKS: الجمهور (aud) المطابق يمر (نصًا أو ضمن قائمة)",
          aud_provider.verify_upstream_token(_make_jwt(key, "k-aud", aud_ok), now=NOW).account_id == ADMIN
          and aud_provider.verify_upstream_token(_make_jwt(key, "k-aud", aud_list), now=NOW).account_id == ADMIN)
    check("JWKS: الجمهور غير المطابق يرفض",
          _raises(lambda: aud_provider.verify_upstream_token(
              _make_jwt(key, "k-aud", aud_bad), now=NOW),
              identity.IdentityVerificationError) is not None)

    es256_err = _raises(lambda: jwks_provider.verify_upstream_token(
        _make_jwt(key, kid, payload_admin, alg="ES256"), now=NOW),
        identity.IdentityVerificationError)
    check("JWKS: ES256 مرفوض برسالة صريحة (فجوة موثقة — لا ادعاء دعم)",
          es256_err is not None and "ES256" in str(es256_err))
    check("JWKS: خوارزمية HS256/none مرفوضة",
          _raises(lambda: jwks_provider.verify_upstream_token(
              _make_jwt(key, kid, payload_admin, alg="HS256"), now=NOW),
              identity.IdentityVerificationError) is not None
          and _raises(lambda: jwks_provider.verify_upstream_token(
              _make_jwt(key, kid, payload_admin, alg="none"), now=NOW),
              identity.IdentityVerificationError) is not None)

    email_sub = {**payload_admin, "sub": OLD_OWNER_EMAIL}
    check("JWKS: sub بريد (ليس UUID) يرفض — البريد ليس هوية",
          _raises(lambda: jwks_provider.verify_upstream_token(
              _make_jwt(key, kid, email_sub), now=NOW),
              identity.IdentityVerificationError) is not None)

    unknown_kid = _make_jwt(key, "k-unknown", payload_admin)
    check("JWKS: مفتاح مجهول (kid غائب عن JWKS) يرفض بعد إعادة الجلب",
          _raises(lambda: jwks_provider.verify_upstream_token(unknown_kid, now=NOW),
                   identity.IdentityVerificationError) is not None)

    # تدوير المفاتيح: kid جديد يستبدل القديم
    new_key, new_kid = _gen_rsa_keypair(), "k2"
    jwks_rot, rot_state = _jwks_provider(new_key, new_kid,
                                          role_claim_path="app_metadata,engine_role")
    rotated_payload = {**payload_admin, "sub": CLIENT_A,
                        "app_metadata": {"engine_role": ROLE_CLIENT}}
    new_token = _make_jwt(new_key, new_kid, rotated_payload)
    check("JWKS: بعد تدوير المفاتيح الرمز الجديد يعمل",
          jwks_rot.verify_upstream_token(new_token, now=NOW).account_id == CLIENT_A)
    check("JWKS: بعد التدوير الرمز بالمفتاح القديم (kid غائب) يرفض",
          _raises(lambda: jwks_rot.verify_upstream_token(token_admin, now=NOW),
                   identity.IdentityVerificationError) is not None)

    # ── (مراجعة دفعة 17) سياسة أحجام مفاتيح RSA: ≥2048 قبل التوقيع ─────
    print("── JWKS: سياسة الحد الأدنى 2048 بت (قبل التحقق من التوقيع) ──")
    for weak_bits in (512, 1024, 2047):
        weak_pair = _gen_rsa_keypair(weak_bits)
        weak_provider, _ = _jwks_provider(weak_pair, "weak-k")
        weak_payload = {**payload_admin, "sub": CLIENT_A}
        weak_token = _make_jwt(weak_pair, "weak-k", weak_payload)
        err = _raises(lambda: weak_provider.verify_upstream_token(weak_token, now=NOW),
                      identity.IdentityVerificationError)
        check(f"JWKS: مفتاح {weak_bits} بت يرفض قبل التحقق من التوقيع (سياسة ≥2048)",
              err is not None and "2048" in str(err))
    strong_pair = _gen_rsa_keypair(2048)
    strong_provider, _ = _jwks_provider(strong_pair, "strong-k")
    strong_payload = {**payload_admin, "sub": CLIENT_A}
    strong_token = _make_jwt(strong_pair, "strong-k", strong_payload)
    check("JWKS: مفتاح 2048 بت (الحد الأدنى) يُقبل ويعمل",
          strong_provider.verify_upstream_token(strong_token, now=NOW).account_id == CLIENT_A)
    # مفتاح ضعيف برمز سليم التوقيع فعلًا: الرفع عند حل المفتاح قبل التوقيع
    signed_weak_token = _make_jwt(weak_pair := _gen_rsa_keypair(512), "k-signed-weak",
                                  strong_payload)
    check("JWKS: رمز موقع فعلًا بمفتاح ضعيف لا يصل التوقيع أبدًا (الرفع عند المفتاح)",
          _raises(lambda: _jwks_provider(weak_pair, "k-signed-weak")[0]
                  .verify_upstream_token(signed_weak_token, now=NOW),
                  identity.IdentityVerificationError) is not None)

    no_role_provider, _ = _jwks_provider(key, kid)
    plain_client_payload = {**payload_admin, "sub": CLIENT_A}
    del plain_client_payload["app_metadata"]
    plain = no_role_provider.verify_upstream_token(
        _make_jwt(key, kid, plain_client_payload), now=NOW)
    check("JWKS: بلا مسار دور مضبوط = عميل (افتراض أي حساب جديد — لا اختراع)",
          plain.role == ROLE_CLIENT)

    coach_payload = {
        "iss": "https://accounts.alkemos.test", "sub": COACH,
        "iat": NOW - 60, "exp": NOW + 3600,
        "app_metadata": {"engine_role": ROLE_COACH,
                          "engine_scope": [CLIENT_A]},
    }
    scope_provider, _ = _jwks_provider(
        key, kid, role_claim_path="app_metadata,engine_role",
        scope_claim_path="app_metadata,engine_scope",
    )
    coach_account = scope_provider.verify_upstream_token(
        _make_jwt(key, kid, coach_payload), now=NOW)
    check("JWKS: نطاق المدرب من مطالبة متحكم بها (app_metadata) يقرأ قانونيًا",
          coach_account.role == ROLE_COACH
          and coach_account.scope == frozenset({CLIENT_A}))

    # ══ 4) الخدمة: الباب العام ═════════════════════════════════════════════
    print("══ 4) الخدمة: الباب العام والفهرس وفصل بيانات الهوية ══")
    import inspect

    sigs = {
        name: inspect.signature(getattr(UnifiedIdentityService, name))
        for name in ("authenticate", "authenticate_service", "verify_engine_token")
    }
    param_names = {n: set(s.parameters) - {"self"} for n, s in sigs.items()}
    check("الباب العام: تواقيع الأبواب لا تقبل بريدًا ولا دورًا من المستدعي "
          "(رمز منبع معتم فقط)",
          all("email" not in ps and "role" not in ps and "account_id" not in ps
              for ps in param_names.values()))
    check("الباب العام: الرمز غير النصي/الفارغ يرفض",
          _raises(lambda: svc.authenticate(None, now=NOW), identity.IdentityVerificationError) is not None
          and _raises(lambda: svc.authenticate("", now=NOW), identity.IdentityVerificationError) is not None)
    check("الباب العام: الرمز المجهول يرفض برسالة موحدة (لا تعداد)",
          _raises(lambda: svc.authenticate("لا-شيء", now=NOW), identity.IdentityVerificationError) is not None)
    check("قناع describe آمن: بلا مفاتيح ولا رموز ولا بريد",
          set(svc.describe()) == {"provider", "owner_accounts_count", "account_index"})

    with tempfile.TemporaryDirectory() as tmpdir:
        idx_root = os.path.join(tmpdir, "identity-accounts")
        mem_root = os.path.join(tmpdir, "model-memory")
        idx = AccountIndex(idx_root)
        svc_idx = UnifiedIdentityService(static, ta, owner_account_ids=[OWNER],
                                         service_proof_verifier=site_verifier,
                                         account_index=idx)
        s = svc_idx.authenticate("tok-a", now=NOW)
        s2 = svc_idx.authenticate("tok-a", now=NOW + 5)
        entry = idx.get(CLIENT_A)
        check("الفهرس: أول ظهور ثم ظهور لاحق (جلسات العد استخدام لكل حساب)",
              entry is not None and entry["sessions_count"] == 2
              and entry["first_seen"] is not None and entry["roles_seen"] == [ROLE_CLIENT])
        check("الفهرس: بيانات الهوية في ملفات مستقلة عن مخزن بيانات النموذج",
              os.path.exists(os.path.join(idx_root, "accounts-state.json"))
              and not os.path.exists(os.path.join(mem_root, "memory.jsonl"))
              and idx_root != mem_root)

        check("الفهرس: مسار نسبي مرفوض",
              _raises(lambda: AccountIndex("relative/path"), identity.AccountIndexError) is not None)
        check("الفهرس: داخل شجرة git مرفوض (بيانات هوية = مستوى أ)",
              _raises(lambda: AccountIndex(os.path.join(
                  os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "idx-test")),
                  (identity.AccountIndexError, ValueError)) is not None)

        prefs = idx.set_preferences(s["principal"], CLIENT_A, {"locale": "ar", "units": "metric"})
        check("التفضيلات: كتابة بهوية العميل لنفسه وقراءتها",
              prefs == {"locale": "ar", "units": "metric"}
              and idx.get_preferences(CLIENT_A) == prefs)
        b_principal = svc_idx.authenticate("tok-b", now=NOW)["principal"]
        check("التفضيلات: عميل آخر لا يكتب تفضيلات غيره (نطاق الهوية)",
              _raises(lambda: idx.set_preferences(b_principal, CLIENT_A, {"locale": "en"}),
                       identity.AccountIndexError) is not None)
        check("التفضيلات: المالك يكتب ضمن صلاحيته (كل الحسابات)",
              idx.set_preferences(svc_idx.authenticate("tok-owner-client-role", now=NOW)["principal"],
                                  CLIENT_A, {"locale": "ar"}) == {"locale": "ar"})
        check("التفضيلات: قيمة نصية بدل هوية موثقة مرفوضة",
              _raises(lambda: idx.set_preferences("owner", CLIENT_A, {}),
                       identity.AccountIndexError) is not None)
        check("التفضيلات: سقف المفاتيح مفروض (رفض 100 مفتاح)",
              _raises(lambda: idx.set_preferences(b_principal, CLIENT_B,
                                                   {"k" + str(i): "v" for i in range(100)}),
                      identity.AccountIndexError) is not None)
        check("الاستخدام: ملخص الجلسات لكل حساب من بيانات الهوية",
              idx.usage(CLIENT_A)["sessions_count"] == 2
              and idx.usage(CLIENT_B)["sessions_count"] == 1)
        tamper_err = None
        state_path = os.path.join(idx_root, "accounts-state.json")
        original = open(state_path, encoding="utf-8").read()
        try:
            open(state_path, "w", encoding="utf-8").write(
                original.replace('"sessions_count": 2', '"sessions_count": 999'))
            idx.get(CLIENT_A)
        except identity.AccountIndexError:
            tamper_err = True
        finally:
            open(state_path, "w", encoding="utf-8").write(original)
        check("الفهرس: العبث بالحالة يُكشف ببصمة التكامل (صوت عالٍ)",
              tamper_err is not None)

        # ── (مراجعة دفعة 17) بيانات الفهرس ليست مصدر هوية أو صلاحيات ──────
        # SHA-256 يكشف التلف لا العبث المتعمد (من يملك حق الكتابة يعيد حساب
        # البصمة) — لذلك القاعدة: لا يُشتق من الفهرس أي قرار هوية/صلاحية.
        from engine.identity.accounts import _state_integrity

        state_doc = json.loads(original)
        state_doc["accounts"][CLIENT_A]["roles_seen"] = ["admin"]   # تزوير
        state_doc["integrity"] = _state_integrity(state_doc)        # ...بإعادة حساب البصمة
        try:
            open(state_path, "w", encoding="utf-8").write(
                json.dumps(state_doc, ensure_ascii=False, indent=2))
            s_after = svc_idx.authenticate("tok-a", now=NOW)
        finally:
            open(state_path, "w", encoding="utf-8").write(original)
        check("حدود الفهرس (موثقة): إعادة كتابة الحالة وإعادة حساب البصمة تعبر فحص التكامل — لكن الهوية لا تتأثر",
              s_after["token_kind"] == auth.KIND_CLIENT
              and s_after["principal"].clients == frozenset({CLIENT_A})
              and not s_after["principal"].can(auth.PERM_MEMORY_REVIEW))
        forged_entry = dict(idx.get(CLIENT_A) or {})
        forged_entry["roles_seen"] = ["admin", "owner"]
        inmem = mem_store.InMemoryMemoryStore()
        check("الفهرس: سجل الحساب (بعد حقن أدوار) ليس هوية — المستهلكات ترفضه",
              not identity.is_verified_account(forged_entry)
              and _raises(lambda: mem_service.MemoryService(inmem, forged_entry),
                          mem_service.MemoryServiceError) is not None)
        idx_events = idx.events()
        check("الفهرس: أحداث السجل ليست إثبات هوية أو صلاحية (بيانات تدقيق أرشيفية)",
              bool(idx_events)
              and not identity.is_verified_account(idx_events[0])
              and _raises(lambda: mem_service.MemoryService(inmem, idx_events[0]),
                          mem_service.MemoryServiceError) is not None)

        # ══ 5) العزل عبر الهوية الموحدة (ذاكرة + موافقات) ═════════════════
        print("══ 5) العزل: الذاكرة والموافقات عبر جلسات الهوية ══")
        from engine.learning.consent import ConsentLedger
        store = mem_store.JsonlMemoryStore(mem_root)
        # الكتابة عبر جلسة الخدمة (كبلة الموقع نيابة عن المستخدم — عقد الدفعة 17)
        service_session_a = svc_idx.authenticate_service(
            "tok-a", server_proof=proof_a, now=NOW)
        svc_a = mem_service.MemoryService(store, service_session_a["principal"])
        for i in range(9):   # إيقاع الاستخراج: كل 10 رسائل (نمط 0081)
            svc_a.record_exchange(CLIENT_A, [], f"رسالة {i}", "رد", [])
        extracted, stored_facts = svc_a.record_exchange(
            CLIENT_A, [], "بتمرن في الجيم 4 أيام", "تمام",
            [{"fact": "يتمرن في الجيم 4 أيام أسبوعيًا", "category": "lifestyle"}])
        check("الذاكرة: جلسة خدمة العميل A تكتب حقيقته (مفتاحها معرف حسابه)",
              stored_facts and store.load_facts(CLIENT_A)[0]["client_id"] == CLIENT_A)
        svc_a_read = mem_service.MemoryService(store, s["principal"])
        check("الذاكرة: العميل A يقرأ ذاكرته عبر هويته الموحدة",
              "يتمرن في الجيم 4 أيام" in svc_a_read.get_injectable_context(CLIENT_A))
        svc_b = mem_service.MemoryService(store, b_principal)
        check("العزل: عميل B لا يقرأ ذاكرة A عبر هويته الموحدة",
              _raises(lambda: svc_b.get_injectable_context(CLIENT_A),
                      mem_service.AccessDenied) is not None)
        svc_service_a = mem_service.MemoryService(store, service_session_a["principal"])
        check("العزل: جلسة خدمة A لا تبلغ B (نطاقها حسابها)",
              _raises(lambda: svc_service_a.get_injectable_context(CLIENT_B),
                          mem_service.AccessDenied) is not None)
        coach_principal = svc_idx.authenticate("tok-coach", now=NOW)["principal"]
        svc_coach = mem_service.MemoryService(store, coach_principal)
        check("العزل: المدرب يراجع ذاكرة مسنديه (A) ولا يبلغ C",
              svc_coach.review_facts(CLIENT_A) is not None
              and _raises(lambda: svc_coach.review_facts(CLIENT_C),
                          mem_service.AccessDenied) is not None)
        owner_principal = svc_idx.authenticate("tok-owner-client-role", now=NOW)["principal"]
        svc_owner_mem = mem_service.MemoryService(store, owner_principal)
        fact_id = store.load_facts(CLIENT_A)[0]["id"]
        check("المالك المرتبط: يحذف نهائيًا بأمر موثق (صلاحية الملكية الفريدة)",
              svc_owner_mem.hard_delete_fact(CLIENT_A, fact_id, "أمر-مالك-موثق-دفعة-17") is True
              and not store.load_facts(CLIENT_A))

        consent_root = os.path.join(tmpdir, "consent")
        ledger = ConsentLedger(consent_root)
        grant = ledger.grant_client_consent(
            "ref-1", CLIENT_A, "training", ["training_only"],
            "2026-11-24T00:00:00Z", s["principal"])
        check("الموافقات: العميل يسجل موافقته بنفسه عبر هويته الموحدة",
              grant["client_id"] == CLIENT_A
              and grant["recorded_by"].startswith("client:" + CLIENT_A))
        check("الموافقات: عميل آخر لا يسحب موافقة A (خارج نطاقه)",
              _raises(lambda: ledger.withdraw("ref-1", "2026-11-24T01:00:00Z", b_principal),
                      Exception) is not None)
        w = ledger.withdraw("ref-1", "2026-11-24T01:00:00Z", owner_principal)
        check("الموافقات: المالك المرتبط يسحب ضمن صلاحيته",
              w.get("type") in ("withdrawal", "withdraw") or w.get("status") == "withdrawn")

    # ══ 6) الإعدادات ════════════════════════════════════════════════════════
    print("══ 6) الإعدادات: هوية موحدة بلا بريد ══")
    check("الإعدادات: لم يعد هناك OWNER_EMAIL_PRIMARY (هوية البريد ألغيت)",
          not hasattr(settings, "OWNER_EMAIL_PRIMARY")
          and not hasattr(settings, "normalize_owner_email"))
    check("الإعدادات: الافتراضي مزود الاستعلام عند مصدر الحساب",
          settings.IDENTITY_PROVIDER == "supabase-introspection")
    check("الإعدادات: معرفات المالك الافتراضية فارغة (فشل مغلق حتى يضبطها المالك)",
          settings.OWNER_ACCOUNT_IDS == frozenset())

    env_backup = {k: os.environ.get(k) for k in (
        "ALKEMOS_OWNER_ACCOUNT_IDS", "ALKEMOS_IDENTITY_PROVIDER")}
    try:
        os.environ["ALKEMOS_OWNER_ACCOUNT_IDS"] = f"{OWNER}, {CLIENT_A.upper()}"
        import importlib
        settings2 = importlib.reload(settings)
        check("الإعدادات: قراءة معرفات المالك من البيئة بتقنين كانوني (تجاهل حالة)",
              settings2.OWNER_ACCOUNT_IDS == frozenset({OWNER, CLIENT_A})
              and settings2.is_owner_account_id(OWNER))
        check("الإعدادات: قيمة ملوثة (بريد) في معرفات المالك ترفض بصوت عالٍ",
              _raises(_reload_with_bad_owner, Exception) is not None
              and _BAD_OWNER_MSG is not None
              and "ALKEMOS_OWNER_ACCOUNT_IDS" in _BAD_OWNER_MSG
              and "ليس معرف حساب" in _BAD_OWNER_MSG)
    finally:
        for k, v in env_backup.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        import importlib
        importlib.reload(settings)

    # مزود الإنتاج: يرفض المزود المجهول والمحاكاة ويغلق عند نقص الإعداد
    import adapters.identity as adapters_identity
    saved_provider = settings.IDENTITY_PROVIDER
    try:
        settings.IDENTITY_PROVIDER = "static-test"
        err_static = _raises(adapters_identity.build_identity_service,
                             settings.IdentitySettingsError)
        check("جذر التركيب: مزود المحاكاة (static-test) مرفوض للإنتاج",
              err_static is not None)
        settings.IDENTITY_PROVIDER = "مزود-مجهول"
        err_unknown = _raises(adapters_identity.build_identity_service,
                              settings.IdentitySettingsError)
        check("جذر التركيب: مزود غير معروف مرفوض بصوت عالٍ",
              err_unknown is not None)
        settings.IDENTITY_PROVIDER = "supabase-introspection"
        err_missing = _raises(adapters_identity.build_identity_service,
                              settings.IdentitySettingsError)
        check("جذر التركيب: نقص ALKEMOS_IDENTITY_ISSUER يرفض البناء (فشل مغلق)",
              err_missing is not None and "ISSUER" in str(err_missing))
    finally:
        settings.IDENTITY_PROVIDER = saved_provider

    passed = sum(1 for _, ok in results if ok)
    print(f"\n{passed}/{len(results)} اختبارًا ناجحًا")
    sys.exit(0 if passed == len(results) else 1)


_BAD_OWNER_MSG = None


def _reload_with_bad_owner():
    """إعادة تحميل الإعدادات بقيمة معرف مالك ملوثة — يجب أن ترفض بصوت عالٍ.

    (الاستثناء يُلتقط كنص لأن كلاس الوحدة يُعاد إنشاؤه أثناء إعادة التحميل
    الفاشلة فلا يطابق الكلاس المرجعي القديم — الحكم بالرسالة الموثقة.)
    """
    global _BAD_OWNER_MSG
    import importlib
    os.environ["ALKEMOS_OWNER_ACCOUNT_IDS"] = "not-a-uuid@nope"
    try:
        importlib.reload(settings)
    except Exception as e:  # noqa: BLE001 — نص الرسالة هو المطلوب
        _BAD_OWNER_MSG = str(e)
        raise


if __name__ == "__main__":
    main()
