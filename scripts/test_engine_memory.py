#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""اختبارات المستوى أ — الوحدات النقية + المخزن + الخدمة (M4-ذاكرة-1).

التوقعات منقولة من اختبارات EVO الأصلية (src/lib/__tests__/evo-memory.test.ts
@ 500ed1f) — نفس الحالات الحرجة حرفيًا، وزيادات المخزن والخدمة والحارس خاصتنا:
روح فحوص الطفرة: كل قانون موثق في الوحدة له اختبار يثبت كسره عند الإخلال.
"""
import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from engine.memory import pure, service, store  # noqa: E402

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def main():
    results = []

    def check(name, cond, detail=""):
        results.append((name, bool(cond)))
        mark = "✓" if cond else "✗"
        print(f"  {mark} {name}" + (f" — {detail}" if (detail and not cond) else ""))

    # ── normalize_for_memory (منقول من اختبار EVO) ──────────────────────────
    check(
        "التطبيع يوحّد صور الإملاء العربي",
        pure.normalize_for_memory("هدفي انزّل ١٠ كيلو") == pure.normalize_for_memory("هدفى انزل 10 كيلو"),
    )
    check(
        "التطبيع يطوي الفراغات ويصغّر اللاتيني",
        pure.normalize_for_memory("  GOAL:   Lose WEIGHT ") == "goal lose weight",
    )

    # ── is_duplicate_memory_fact ─────────────────────────────────────────────
    check("التكرار: تساوٍ بعد التطبيع (أرقام هندية)", pure.is_duplicate_memory_fact("هدفه انزال 10 كيلو", ["هدفه انزال ١٠ كيلو"]))
    check("التكرار: احتواء عبارة حقيقية (≥8)", pure.is_duplicate_memory_fact("العميل بيحب تمارين الكارديو جدا", ["بيحب تمارين الكارديو"]))
    check("التكرار: الشظايا القصيرة لا تطابق كل شيء", not pure.is_duplicate_memory_fact("يتمرن في الجيم يوميا", ["تمرين"]))
    check("التكرار: المرشح الفارغ تطبيعًا يُحذف لا يُخزن", pure.is_duplicate_memory_fact("!!", []))
    check("التكرار: حقائق مختلفة فعلًا تعبر", not pure.is_duplicate_memory_fact("يتمرن في الصباح", ["يفضل الكارديو مساءً"]))

    # ── validate_memory_facts ────────────────────────────────────────────────
    facts = pure.validate_memory_facts([
        {"fact": "يتمرن 4 أيام أسبوعيًا", "category": "lifestyle"},
        {"fact": "يريد خسارة 10 كجم", "category": "goal"},
    ])
    check("التحقق: شكل {fact, category} والفئات الصحيحة", len(facts) == 2 and facts[0] == {"fact": "يتمرن 4 أيام أسبوعيًا", "category": "lifestyle"} and facts[1]["category"] == "goal")
    facts = pure.validate_memory_facts(["بيكره البروكلي", {"fact": "نام متأخر", "category": "غريبة"}])
    check("التحقق: الفئة المجهولة والسلاسل المجردة → other", facts[0]["category"] == "other" and facts[1]["category"] == "other")
    long_fact = "س " * 400
    facts = pure.validate_memory_facts([{"fact": f"قبل\nبعد {long_fact}", "category": "other"}])
    check("التحقق: سقف 300 محرف وتسطيح الأسطر الجديدة", len(facts[0]["fact"]) <= pure.EVO_MEMORY_FACT_MAX and "\n" not in facts[0]["fact"])
    many = [{"fact": f"حقيقة رقم {i} فعالة", "category": "other"} for i in range(9)]
    check("التحقق: سقف الدفعة 5", len(pure.validate_memory_facts(many)) == pure.EVO_MEMORY_FACTS_PER_EXTRACTION)
    check("التحقق: المدخلات الفاسدة = صفر حقائق لا استثناء", pure.validate_memory_facts([{"fact": "ab", "category": "other"}, None, 42]) == [] and pure.validate_memory_facts(None) == [] and pure.validate_memory_facts("[]") == [] and pure.validate_memory_facts({"fact": "x"}) == [])
    facts = pure.validate_memory_facts(
        [
            {"fact": "هدفه انزال 10 كيلو", "category": "goal"},
            {"fact": "هدفه انزال 10 كيلو!", "category": "goal"},
            {"fact": "يتغذى على 4 وجبات", "category": "lifestyle"},
        ],
        ["هو هدفه انزال 10 كيلو بس"],
    )
    check("التحقق: إزالة التكرار داخل الدفعة وضد القائمة", len(facts) == 1 and facts[0]["fact"] == "يتغذى على 4 وجبات")

    # ── sanitize_stored_facts ────────────────────────────────────────────────
    rows = [{"fact": f"حقيقة مخزنة رقم {i}", "category": "goal"} for i in range(20)]
    facts = pure.sanitize_stored_facts(rows)
    check("التعقيم: سقف الحقن 15", len(facts) == pure.EVO_MEMORY_TOP_INJECT and facts[0]["category"] == "goal")
    facts = pure.sanitize_stored_facts([{"fact": 42, "category": "goal"}, {"fact": "يحب الصباح", "category": "?????"}])
    check("التعقيم: إسقاط غير النصي وفئة مجهولة → other", len(facts) == 1 and facts[0]["category"] == "other")

    # ── format_evo_memory_for_prompt ────────────────────────────────────────
    check("الحقن: المدخل الفارغ = سلسلة فارغة (لا قسم فارغ)", pure.format_evo_memory_for_prompt([]) == "")
    facts = [{"fact": f"حقيقة {i}", "category": "preference"} for i in range(18)]
    block = pure.format_evo_memory_for_prompt(facts)
    check("الحقن: كتلة «ذاكرة Evo الدائمة» بسقف 15", "ذاكرة Evo الدائمة" in block and "[preference] حقيقة 0" in block and "حقيقة 15" not in block)

    # ── cap_transcript + build_evo_memory_prompt ────────────────────────────
    history = [{"role": "user" if i % 2 == 0 else "assistant", "content": f"رسالة رقم {i} " * 60} for i in range(15)]
    transcript = pure.cap_transcript_for_extraction(history, "سؤال حالي", "رد حالي")
    check("المقطوع: آخر الرسائل + التبادل الحالي ≤ 12", len(transcript) <= pure.EVO_MEMORY_TRANSCRIPT_MESSAGES and transcript[-2]["content"] == "سؤال حالي" and transcript[-1]["content"] == "رد حالي")
    check("البرومت: None بلا رسالة مستخدم", pure.build_evo_memory_prompt([{"role": "assistant", "content": "تمام"}]) is None)
    prompt = pure.build_evo_memory_prompt([{"role": "user", "content": "بتمرن في الجيم"}, {"role": "assistant", "content": "تمام"}])
    check("البرومت: نص المستخدم + عقد قائمة الحرمان + JSON فقط", prompt is not None and "User: بتمرن في الجيم" in prompt and "NEVER store" in prompt and "mental-health" in prompt and "JSON array ONLY" in prompt and "goal|preference|lifestyle|constraint|other" in prompt)
    long_msg = "كلمة " * 300
    prompt = pure.build_evo_memory_prompt([{"role": "user", "content": long_msg}, {"role": "assistant", "content": long_msg}])
    user_line = next(l for l in prompt.split("\n") if l.startswith("User:"))
    check("البرومت: سقف 500 محرف لكل سطر", len(user_line) <= len("User: ") + pure.EVO_MEMORY_TRANSCRIPT_MESSAGE_MAX)

    # ── should_extract_memory ────────────────────────────────────────────────
    check("الإيقاع: يشتعِل عند 10 ويبقى فوقها", not pure.should_extract_memory(pure.EVO_MEMORY_EXTRACT_EVERY - 1) and pure.should_extract_memory(pure.EVO_MEMORY_EXTRACT_EVERY) and pure.should_extract_memory(pure.EVO_MEMORY_EXTRACT_EVERY + 3))

    # ── المخزن: JSONL + الحارس ─────────────────────────────────────────────
    with tempfile.TemporaryDirectory() as tmp:
        st = store.JsonlMemoryStore(tmp)
        now = "2026-11-24T00:00:00.000Z"
        for fact in ["يتمرن في الجيم 4 أيام", "يفضل التمرين مساءً", "يريد خسارة 10 كجم"]:
            st.append_fact({"client_id": "c1", "fact": fact, "category": "lifestyle", "is_active": True, "created_at": now, "updated_at": now, "source": "chat_extraction"})
        check("المخزن: 3 حقائق نشطة", len(st.load_facts("c1")) == 3)
        recs = st.all_records()
        check("المخزن: معرفات تسلسلية", recs[0]["id"] == "MF-000001")
        st.set_fact_active("c1", recs[0]["id"], False, now)
        check("المخزن: الإلغاء بدل الحذف (is_active)", len(st.load_facts("c1")) == 2 and len(st.load_facts("c1", active_only=False)) == 3)
        st2 = store.JsonlMemoryStore(tmp)
        check("المخزن: الثبات عبر الجلسات (ملفات مفتوحة)", len(st2.load_facts("c1", active_only=False)) == 3)
        st.delete_fact("c1", recs[0]["id"])
        check("المخزن: الحذف الفعلي يزيل السجل", len(st2.all_records()) == 2 or len(st.all_records()) == 2)
        st.set_extract_count("c1", 7)
        check("المخزن: عداد الاستخراج لكل عميل", st.get_extract_count("c1") == 7 and st.get_extract_count("c2") == 0)

    check("الحارس: يرفض مخزنًا داخل شجرة git (المستودع العام)", _raises(lambda: store.JsonlMemoryStore(REPO_ROOT), ValueError))
    check("الحارس: يرفض المسار النسبي", _raises(lambda: store.JsonlMemoryStore("data/memory"), ValueError))

    # ── الخدمة: الدورة + الأدوار + الحوكمة ─────────────────────────────────
    mem = store.InMemoryMemoryStore()
    svc = service.MemoryService(mem, role="service")
    ok_extract = False
    for i in range(9):
        extracted, stored = svc.record_exchange("c1", [], f"رسالة {i}", "رد", [])
        ok_extract = ok_extract or extracted
    check("الخدمة: 9 رسائل بلا استخراج (الإيقاع 10)", not ok_extract and mem.get_extract_count("c1") == 9)
    parsed = [
        {"fact": "يتمرن في الجيم 4 أيام أسبوعيًا", "category": "lifestyle"},
        {"fact": "هدفه خسارة 10 كيلو", "category": "goal"},
        {"fact": "يتمرن في الجيم 4 أيام أسبوعيًا!", "category": "lifestyle"},
    ]
    extracted, stored = svc.record_exchange("c1", [], "بتمرن في الجيم 4 أيام", "تمام", parsed)
    check("الخدمة: العاشرة تشعل الاستخراج وتخزن بعد إزالة التكرار", extracted and len(stored) == 2 and mem.get_extract_count("c1") == 0)
    ctx = svc.get_injectable_context("c1")
    check("الخدمة: كتلة الحقن جاهزة (عقد الواجهة)", "ذاكرة Evo الدائمة" in ctx and "[lifestyle] يتمرن في الجيم 4 أيام أسبوعيًا" in ctx)
    extracted, stored = svc.record_exchange("c1", [], "سؤال", "رد", [{"fact": "يتمرن في الجيم 4 أيام أسبوعيًا", "category": "lifestyle"}])
    check("الخدمة: التكرار ضد الحقائق النشطة القائمة يُمنع", len(stored) == 0)

    admin = service.MemoryService(mem, role="admin")
    check("الخدمة: الأدمن لا يكتب (حقن الكتابة للخدمة)", _raises(lambda: admin.record_exchange("c1", [], "س", "ر", []), service.MemoryServiceError))
    facts_all = admin.review_facts("c1")
    check("الخدمة: قراءة الأدمن للمراجعة", len(facts_all) == 2)
    admin.deactivate_fact("c1", facts_all[0]["id"])
    check("الخدمة: إلغاء التنشيط يخرج الحقيقة من الحقن", facts_all[0]["fact"] not in svc.get_injectable_context("c1"))

    owner = service.MemoryService(mem, role="owner")
    check("الخدمة: الحذف النهائي بلا أمر مالك موثق مرفوض (D2)", _raises(lambda: owner.hard_delete_fact("c1", facts_all[0]["id"], "  "), service.MemoryServiceError))
    deleted = owner.hard_delete_fact("c1", facts_all[0]["id"], "أمر مالك 2026-11-24-حذف")
    check("الخدمة: الحذف النهائي بأمر موثق ينفذ", deleted and len(mem.all_records()) == 1)
    check("الخدمة: دور مجهول مرفوض من البناء", _raises(lambda: service.MemoryService(mem, role="ghost"), service.MemoryServiceError))

    passed = sum(1 for _, ok in results if ok)
    print(f"\n{passed}/{len(results)} اختبارًا ناجحًا")
    sys.exit(0 if passed == len(results) else 1)


def _raises(fn, exc):
    try:
        fn()
        return False
    except exc:
        return True
    except Exception:
        return False


if __name__ == "__main__":
    main()
