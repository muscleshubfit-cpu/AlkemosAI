#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""اختبارات طبقة التعلم — E1/E2/E3 المنقولة من EVO + المتابعات + التغذية الراجعة.

التوقعات منقولة من src/lib/__tests__/evo-nutrition-learning.test.ts و
evo-followup.test.ts و evo-feedback.test.ts @ 500ed1f — نفس الحالات الحرجة:
- أرضية الصدق: العينة الرقيقة تُحجب (لا ضجيج كمعرفة).
- مجهولية بالبناء: النص الحر (overview/notes) لا يدخل التجميعات أبدًا.
- حاجز الهدف المجهول + حتمية الاختيار (المعتمد أولًا ثم الاكتمال ثم الحداثة).
- لا اختراع أرقام: الغائب = None.
"""
import os
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from engine import feedback as efeedback  # noqa: E402
from engine import followup as efollowup  # noqa: E402
from engine.learning import nutrition as nut  # noqa: E402


def plans_content(**overrides):
    """خطة شكل plans.content — النص الحر يحمل اسمًا يجب ألا يتسرب أبدًا."""
    base = {
        "overview": "خطة العميل أحمد لتخفيس الوزن",
        "daily_calories": 1600,
        "macros": {"protein_g": 120, "carbs_g": 150, "fat_g": 45},
        "meals": [
            {
                "name": "الإفطار",
                "total_calories": 500,
                "items": [
                    {"food": "بيض مسلوق", "amount": "3 بيضات", "calories": 234},
                    {"food": "خبز بلدي", "amount": "½ رغيف", "calories": 180},
                ],
            },
            {
                "name": "الغداء",
                "total_calories": 700,
                "items": [{"food": "صدر دجاج مشوي", "amount": "150 جم", "calories": 250}],
            },
        ],
    }
    base.update(overrides)
    return base


MEAL_PLANNER_DATA = {
    "meals": [
        {
            "name": "الوجبة الأولى",
            "items": [
                {"name": "شوفان", "source": "local", "grams": 70, "per100g": {"calories": 380, "protein": 13, "carbs": 60, "fat": 7}},
                {"name": "حليب", "source": "local", "grams": 250, "per100g": {"calories": 60, "protein": 3.2, "carbs": 5, "fat": 3}},
            ],
        },
        {
            "name": "الوجبة الثانية",
            "items": [
                {"name": "شوفان", "source": "local", "grams": 50, "per100g": {"calories": 380, "protein": 13, "carbs": 60, "fat": 7}},
            ],
        },
    ],
}


def main():
    results = []

    def check(name, cond, detail=""):
        results.append((name, bool(cond)))
        mark = "✓" if cond else "✗"
        print(f"  {mark} {name}" + (f" — {detail}" if (detail and not cond) else ""))

    # ── تكافؤ JS في التقريب والتحويل (أساس أمانة النقل) ─────────────────────
    check("js_round: النصف نحو +∞ (ليس بانكي)", nut.js_round(0.5) == 1 and nut.js_round(2.5) == 3 and nut.js_round(-2.5) == -2)
    check("to_number: سلسلة رقمية تُقبل والفارغة صفر والفاسدة None", nut.to_number("1600") == 1600.0 and nut.to_number("") == 0.0 and nut.to_number("abc") is None and nut.to_number(None) is None)

    # ── classify_goal ────────────────────────────────────────────────────────
    check("الهدف: خسارة عربي/إنجليزي", nut.classify_goal("تخفيس الوزن") == "fat-loss" and nut.classify_goal("weight loss") == "fat-loss" and nut.classify_goal("خسارة وزن ودهون") == "fat-loss")
    check("الهدف: بناء عربي/إنجليزي", nut.classify_goal("بناء عضل") == "muscle-gain" and nut.classify_goal("muscle gain") == "muscle-gain" and nut.classify_goal("ضخام") == "muscle-gain")
    check("الهدف: الافتراضي maintain للفارغ/المجهول", nut.classify_goal("") == "maintain" and nut.classify_goal(None) == "maintain" and nut.classify_goal("لياقة عامة") == "maintain")

    # ── normalize_food_name ──────────────────────────────────────────────────
    check("الأصناف: توحيد الألف/التاء المربوطة/«ال» التعريف", nut.normalize_food_name("الأرز") == nut.normalize_food_name("ارز") and nut.normalize_food_name("بطاطس") == nut.normalize_food_name("البطاطس"))
    check("الأصناف: الشظايا والفراغ تسقط", nut.normalize_food_name("") == "" and nut.normalize_food_name("ا") == "" and nut.normalize_food_name("   ") == "")

    # ── extract_meal_items (الشكلان الحقيقيان) ──────────────────────────────
    items = nut.extract_meal_items(plans_content())
    check("الأصناف: شكل plans (food/amount/calories)", len(items) == 3 and items[0] == {"food": "بيض مسلوق", "calories": 234})
    items = nut.extract_meal_items(MEAL_PLANNER_DATA)
    check("الأصناف: شكل meal_plans (name/grams/per100g)", [i["food"] for i in items] == ["شوفان", "حليب", "شوفان"] and all(i["calories"] is None for i in items))
    check("الأصناف: دفاع ضد المدخلات التالفة", nut.extract_meal_items(None) == [] and nut.extract_meal_items("نص") == [] and nut.extract_meal_items({"meals": [None, {"items": "ليست قائمة"}, 42]}) == [])

    # ── extract_nutrition_numbers ────────────────────────────────────────────
    nums = nut.extract_nutrition_numbers(plans_content())
    check("الأرقام: من المحتوى المنظم", nums["dailyCalories"] == 1600 and nums["protein"] == 120 and nums["carbs"] == 150 and nums["fat"] == 45 and nums["mealCount"] == 2)
    nums = nut.extract_nutrition_numbers({"meals": [{"name": "وجبة", "items": [{"name": "شوفان"}]}]}, {"calories": 1800, "protein": 90})
    check("الأرقام: إجماليات الصف تسد الفجوات (meal_plans)", nums["dailyCalories"] == 1800 and nums["protein"] == 90 and nums["carbs"] is None)
    nums = nut.extract_nutrition_numbers({"meals": []})
    check("الأرقام: الغائب = None (لا اختراع)", all(v is None for v in nums.values()))

    # ── E1: aggregate_nutrition_patterns ─────────────────────────────────────
    src = lambda cal, goal="تخفيس الوزن", approved=True, content=None: {  # noqa: E731
        "origin": "plans", "approved": approved, "goalText": goal,
        "content": content or plans_content(daily_calories=cal),
    }
    drafts = nut.aggregate_nutrition_patterns([src(1600), src(1500), src(1700)])
    cal_bucket = next((d for d in drafts if d["bucket"] == "calories_by_goal" and d["key"] == "fat-loss"), None)
    check("E1: دلو السعرات عند بلوغ الأرضية (3 خطط)", cal_bucket is not None and cal_bucket["sample_size"] == 3 and cal_bucket["payload"]["avg"] == 1600 and cal_bucket["payload"]["min"] == 1500 and cal_bucket["payload"]["max"] == 1700)
    drafts = nut.aggregate_nutrition_patterns([src(1600), src(1500)])
    check("E1: دون الأرضية (خطتان) يُحجب — لا ضجيج كمعرفة", not any(d["bucket"] == "calories_by_goal" for d in drafts))
    drafts = nut.aggregate_nutrition_patterns([src(None, content=MEAL_PLANNER_DATA), src(None, content=MEAL_PLANNER_DATA), src(None, content=MEAL_PLANNER_DATA)])
    check("E1: حاجز الهدف المجهول — بلا هدف لا تدخل عائلات الهدف", not any(d["bucket"].endswith("_by_goal") for d in drafts))
    three = [src(1600, goal="تخسيس"), src(1500, goal="تخسيس"), src(1700, goal="تخسيس")]
    drafts = nut.aggregate_nutrition_patterns(three)
    food = next((d for d in drafts if d["bucket"] == "food_frequency" and d["key"] == "بيض مسلوق"), None)
    check("E1: تكرار الأصناف يعد الخطة مرة واحدة (بيض مسلوق في 3 خطط)", food is not None and food["sample_size"] == 3)
    check("E1: مجهولية بالبناء — اسم العميل في النص الحر لا يتسرب", all("أحمد" not in __import__("json").dumps(d, ensure_ascii=False) for d in drafts))
    check("E1: مدخل فارغ بلا استثناء", nut.aggregate_nutrition_patterns([]) == [])

    # ── E2: build_exemplar_skeleton + pick_exemplar_source ───────────────────
    skeleton = nut.build_exemplar_skeleton(plans_content())
    check("E2: هيكل مرجعي مكتمل من الحقول المنظمة", skeleton is not None and skeleton["daily_calories"] == 1600 and len(skeleton["meals"]) == 2 and skeleton["meals"][0]["items"][0] == {"food": "بيض مسلوق", "amount": "3 بيضات", "calories": 234})
    check("E2: النص الحر (overview) غائب عن الهيكل", "أحمد" not in __import__("json").dumps(skeleton, ensure_ascii=False) and "overview" not in skeleton)
    check("E2: خطة ناقصة الماكروز = None", nut.build_exemplar_skeleton({"daily_calories": 1600, "meals": [{"name": "وجبة", "items": [{"food": "شوفان"}]}]}) is None)
    chosen = nut.pick_exemplar_source([
        {"origin": "meal_plans", "approved": False, "goalText": None, "content": plans_content(daily_calories=2000)},
        {"origin": "plans", "approved": True, "goalText": "تخسيس", "content": plans_content()},
    ])
    check("E2: المنتقي يفضل المعتمدة (إشارة الجودة)", chosen is not None and chosen["approved"] is True)
    check("E2: لا شيء مؤهل = None", nut.pick_exemplar_source([{"origin": "plans", "approved": True, "goalText": None, "content": {"meals": []}}]) is None)

    # ── E3: diff_food_names + merge_swap_payload ─────────────────────────────
    old = plans_content()
    new = plans_content(
        meals=[
            {"name": "الإفطار", "total_calories": 480, "items": [{"food": "بيض مسلوق", "amount": "3", "calories": 234}, {"food": "توست أسمر", "calories": 200}]},
            {"name": "الغداء", "total_calories": 700, "items": [{"food": "صدر دجاج مشوي", "amount": "150 جم", "calories": 250}]},
        ]
    )
    diff = nut.diff_food_names(old, new)
    removed_keys = [d["key"] for d in diff["removed"]]
    added_keys = [d["key"] for d in diff["added"]]
    check("E3: كشف المغادِر والوافد عبر التحرير", removed_keys == ["خبز بلدي"] and added_keys == ["توست اسمر"])
    check("E3: نفس المحتوى = فرق فارغ (توحيد الإملاء)", nut.diff_food_names(old, old) == {"removed": [], "added": []})
    check("E3: التهجئة الخام تُحفظ صورةً للعرض", diff["added"][0]["display"] == "توست أسمر" and nut.normalize_food_name("الأرز") == nut.normalize_food_name("ارز"))
    check("E3: دفاع ضد المدخلات التالفة", nut.diff_food_names(None, None) == {"removed": [], "added": []})
    check("E3: النص الحر لا يدخل الفرق", "أحمد" not in __import__("json").dumps(nut.diff_food_names(old, new), ensure_ascii=False))
    merged = nut.merge_swap_payload(None, ["أرز", "دجاج"], datetime(2026, 11, 24, tzinfo=timezone.utc))
    check("E3: الدمج من الصفر يعدّ الأصناف ويختم UTC", merged == {"count": 2, "last_seen": "2026-11-24T00:00:00.000Z"})
    merged = nut.merge_swap_payload({"count": 5, "last_seen": "x"}, ["أرز"], datetime(2026, 11, 24, tzinfo=timezone.utc))
    check("E3: الدمج من حالة قائمة", merged["count"] == 6)
    merged = nut.merge_swap_payload({"count": "تالف"}, ["أرز"], datetime(2026, 11, 24, tzinfo=timezone.utc))
    check("E3: الحمولة التالفة = أساس صفري (لا استثناء)", merged["count"] == 1)

    # ── كتل الحقن ────────────────────────────────────────────────────────────
    rows = [
        {"bucket": "calories_by_goal", "key": "fat-loss", "payload": {"count": 5, "avg": 1600, "min": 1400, "max": 1900}, "sample_size": 5},
        {"bucket": "macros_by_goal", "key": "fat-loss", "payload": {"count": 5, "avg_protein": 130, "avg_carbs": 150, "avg_fat": 45}, "sample_size": 5},
        {"bucket": "meal_count", "key": "3", "payload": {"count": 7}, "sample_size": 7},
        {"bucket": "food_frequency", "key": "بيض مسلوق", "payload": {"plans": 4, "display": "بيض مسلوق"}, "sample_size": 4},
        {"bucket": "food_frequency", "key": "شوفان", "payload": {"plans": 3, "display": "شوفان"}, "sample_size": 3},
        {"bucket": "food_frequency", "key": "دجاج", "payload": {"plans": 3, "display": "دجاج مشوي"}, "sample_size": 3},
    ]
    block = nut.build_platform_knowledge_block(rows)
    check("الحقن: كتلة المعرفة الغذائية بأرقام مجمعة موسومة", "معرفة المنصة الغذائية" in block and "متوسط 1,600 سعرة" in block and "بروتين 130جم" in block and "3 وجبات" in block)
    rows_ex = rows + [{"bucket": "exemplar", "key": "exemplar", "payload": {"daily_calories": 1600, "meals": [{"name": "الإفطار", "items": [{"food": "بيض"}]}]}, "sample_size": 1}]
    block = nut.build_platform_knowledge_block(rows_ex)
    check("الحقن: الهيكل المرجعي يُعرض كشكل فقط (قانون عدم النسخ)", "هيكل مرجعي (الشكل فقط — ممنوع نسخ أصنافه حرفيًا)" in block and '"daily_calories":1600' in block)
    check("الحقن: إشارة الأصناف دون 3 أغذية تُحجب", "أصناف متكررة" not in nut.build_platform_knowledge_block(rows[:2]))
    check("الحقن: لا صفوف = سلسلة فارغة (لا قسم فارغ)", nut.build_platform_knowledge_block([]) == "")
    swap_rows = [
        {"bucket": "swap_removed", "key": "بروكلي", "payload": {"count": 6, "display": "بروكلي"}, "sample_size": 6},
        {"bucket": "swap_added", "key": "فاصوليا", "payload": {"count": 4, "display": "فاصوليا خضراء"}, "sample_size": 4},
        {"bucket": "swap_removed", "key": "مزاج", "payload": {"count": 1, "display": "مزاج"}, "sample_size": 1},
        {"bucket": "swap_volume", "key": "meal", "payload": {"last_week": 18, "total": 120}, "sample_size": 120},
    ]
    block = nut.build_swap_learning_block(swap_rows)
    check("الحقن: قوائم قلّل/قدّم مع حجب ما دون أرضية الاستبدال (3)", "بروكلي (6)" in block and "فاصوليا خضراء" in block and "مزاج" not in block and "استبدالات الوجبات" in block)
    check("الحقن: لا إشارة استبدال = سلسلة فارغة", nut.build_swap_learning_block([]) == "")

    # ── المتابعات (is_followup_due + build_followup_pref_write) ─────────────
    now = datetime(2026, 11, 24, 12, 0, tzinfo=timezone.utc)
    check("المتابعات: غير المشترك لا يستحق أبدًا (D4)", efollowup.is_followup_due({"opted_in": False, "last_sent_at": None}, now) is False)
    check("المتابعات: المشترك الجديد مستحق فورًا", efollowup.is_followup_due({"opted_in": True, "last_sent_at": None}, now) is True)
    six_days_ago = (now - timedelta(days=6)).isoformat()
    eight_days_ago = (now - timedelta(days=8)).isoformat()
    check("المتابعات: إيقاع 7 أيام من آخر إرسال ناجح", efollowup.is_followup_due({"opted_in": True, "last_sent_at": six_days_ago}, now) is False and efollowup.is_followup_due({"opted_in": True, "last_sent_at": eight_days_ago}, now) is True)
    check("المتابعات: الطابع التالف = لم يُرسل قط", efollowup.is_followup_due({"opted_in": True, "last_sent_at": "تالف"}, now) is True)

    w = efollowup.build_followup_pref_write("c1", None, {"optedIn": True, "language": "ar"}, now)
    check("مفتاح الاشتراك: لا صف + تفعيل = INSERT باللغة", w == {"mode": "insert", "values": {"client_id": "c1", "opted_in": True, "language": "ar"}})
    check("مفتاح الاشتراك: لا صف + إلغاء = لا كتابة", efollowup.build_followup_pref_write("c1", None, {"optedIn": False, "language": "ar"}, now) is None)
    w = efollowup.build_followup_pref_write("c1", {"opted_in": False, "language": "en"}, {"optedIn": True, "language": "ar"}, now)
    check("مفتاح الاشتراك: صف مغلق + تفعيل = UPDATE باللغة", w["mode"] == "update" and w["values"]["opted_in"] is True and w["values"]["language"] == "ar")
    w = efollowup.build_followup_pref_write("c1", {"opted_in": True, "language": "en"}, {"optedIn": False, "language": "en"}, now)
    check("مفتاح الاشتراك: الإلغاء يبقي اللغة (إعادة اشتراك بنقرة)", w["mode"] == "update" and w["values"]["opted_in"] is False and "language" not in w["values"])
    check("مفتاح الاشتراك: لا تغيير = لا كتابة (لا churn)", efollowup.build_followup_pref_write("c1", {"opted_in": True, "language": "ar"}, {"optedIn": True, "language": "ar"}, now) is None)
    w = efollowup.build_followup_pref_write("c1", {"opted_in": True, "language": "ar"}, {"optedIn": True, "language": "en"}, now)
    check("مفتاح الاشتراك: تغيير اللغة مع البقاء مشتركًا = UPDATE", w is not None and w["values"]["language"] == "en")
    w = efollowup.build_followup_pref_write("c1", None, {"optedIn": True, "language": "fr"}, now)
    check("مفتاح الاشتراك: نطاق 0079 — أي لغة ليست en هي ar", w["values"]["language"] == "ar")

    # ── التغذية الراجعة ──────────────────────────────────────────────────────
    ok, v = efeedback.parse_evo_feedback_input({"feedback": "up"})
    check("التغذية الراجعة: قبول تصويت إيجابي بلا سياق", ok and v["value"]["feedback"] == "up" and v["value"]["reason"] is None)
    ok, v = efeedback.parse_evo_feedback_input({"feedback": "down", "reason": " الرد عام ", "question": "سؤال", "reply": "رد", "messageId": "m1"})
    check("التغذية الراجعة: سلبية بسبب وسياق مقصوصين", ok and v["value"]["reason"] == "الرد عام" and v["value"]["messageId"] == "m1")
    ok, v = efeedback.parse_evo_feedback_input({"feedback": "sideways"})
    check("التغذية الراجعة: القيم غير الصالحة ترفض بلا استثناء", not ok and "error" in v)
    ok, _ = efeedback.parse_evo_feedback_input("نص")
    check("التغذية الراجعة: الشكل غير الكائن يرفض", not ok)
    ok, v = efeedback.parse_evo_feedback_input({"feedback": "up", "reason": "ر" * 500, "question": "س" * 900})
    check("التغذية الراجعة: سقوف صارمة (300/500)", ok and len(v["value"]["reason"]) == 300 and len(v["value"]["question"]) == 500)
    ok, v = efeedback.parse_evo_feedback_input({"feedback": "down", "reason": "   ", "messageId": None})
    check("التغذية الراجعة: الفراغ يصير None", ok and v["value"]["reason"] is None and v["value"]["messageId"] is None)

    passed = sum(1 for _, ok in results if ok)
    print(f"\n{passed}/{len(results)} اختبارًا ناجحًا")
    sys.exit(0 if passed == len(results) else 1)


if __name__ == "__main__":
    main()
