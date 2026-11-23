#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""تعلم التغذية E1+E2+E3 — نقل حرفي السلوك من EVO (قراءة فقط).

الأصل: alkemos-aws @ 500ed1f246be9dabc9a8a9402acadad10c009fc3
       src/lib/evo-nutrition-learning.ts (EVO-4 — W4).

القوانين المنقولة كما هي:
- أرضية الصدق: العينة الرقيقة تُحجب (sample_size ≥ 3 للتجميعات الإحصائية) —
  الضجيج لا يُقدَّم كمعرفة.
- مجهولية بالبناء: الحقول المنظمة فقط (أصناف/أرقام) تدخل التجميعات والهياكل —
  النص الحر (overview/notes/title) لا يدخل أبدًا فلا يتسرب اسم شخص.
- حاجز الهدف المجهول: مصدر بلا نص هدف حقيقي لا يدخل عائلات الهدف أبدًا.
- سلوك الاستبدال: مفاتيح مطبّعة تزيل تكرار صور الإملاء، وسقوف مقصوصة
  (EVO_SWAP_DIFF_MAX=40 لكل حدث) حتى لا يغرق حدث صاخب الدلاء.
- فشل صادق في الأرقام: القيمة الغائبة = null — لا يُخترع رقم أبدًا.

ملاحظات النقل (TS → Python) الموثقة للأمانة الحرفية:
- Math.round(x) في JS يقرب .5 نحو +∞ — js_round أدناه يطابقه (بايثون round بنكي).
- «‎??‎» الـnullish coalescing يُحاكى بدقة (السلسلة الفارغة ليست nullish).
- كائنات JSON بلا مفاتيح شرطية حين تغيب القيمة (نفس spread الشرطي في الأصل).
"""
from __future__ import annotations

import json
import math
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from engine.memory import pure

# ─────────────────────────── الثوابت (نفس قيم الأصل) ───────────────────────────

EVO_PATTERN_BUCKETS = (
    "calories_by_goal",
    "macros_by_goal",
    "meal_count",
    "food_frequency",
    "exemplar",
    "swap_volume",
    "swap_removed",
    "swap_added",
)

EVO_MIN_GOAL_SAMPLE = 3
EVO_MIN_FOOD_PLANS = 3
EVO_FOOD_TOP_INJECT = 12
EVO_SWAP_TOP_INJECT = 12
EVO_SWAP_MIN_COUNT = 3
EVO_EXEMPLAR_MEALS_MAX = 7
EVO_EXEMPLAR_ITEMS_MAX = 3
EVO_FOOD_MIN_LEN = 2
EVO_SWAP_DIFF_MAX = 40
EVO_AGG_SOURCES_MAX = 500

GOAL_AR = {
    "fat-loss": "خسارة الوزن",
    "muscle-gain": "بناء العضل",
    "maintain": "الحفاظ على الوزن",
}

# عائلات regex نفسها التي يستخدمها المولّد في EVO (computeNutritionTargets) —
# المجمّع والمولّد لا يختلفان أبدًا.
_RE_FAT_LOSS = re.compile(r"weight.?loss|lose|fat loss|تخفيس|تنحيف|خسارة وزن|دهون")
_RE_MUSCLE_GAIN = re.compile(r"muscle|gain|bulk|mass|ضخام|بناء عضل|زيادة وزن")


def js_round(x: float) -> int:
    """Math.round بروح JS: النصف نحو +∞ (بايثون round بنكي فيختلف)."""
    return math.floor(x + 0.5)


def to_number(value: Any) -> Optional[float]:
    """محاكاة Number() في JS: سلسلة رقمية تُقبل، الفارغة = 0، الفاسدة = None."""
    if value is None:
        return None
    if isinstance(value, bool):
        return 1.0 if value else 0.0
    if isinstance(value, (int, float)):
        f = float(value)
        return f if math.isfinite(f) else None
    if isinstance(value, str):
        s = value.strip()
        if s == "":
            return 0.0  # JS: Number("") === 0
        try:
            f = float(s)
            return f if math.isfinite(f) else None
        except ValueError:
            return None
    return None


def _utc_iso(now: Optional[datetime] = None) -> str:
    dt = now or datetime.now(timezone.utc)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


# ───────────────────────── تصنيف الهدف ومفاتيح الأصناف ─────────────────────────


def classify_goal(goal_text: Optional[str]) -> str:
    """تصنيف نص الهدف الحر إلى النطاق المستقر (fat-loss/muscle-gain/maintain)."""
    g = str(goal_text or "").lower()
    if _RE_FAT_LOSS.search(g):
        return "fat-loss"
    if _RE_MUSCLE_GAIN.search(g):
        return "muscle-gain"
    return "maintain"


def normalize_food_name(name: Any) -> str:
    """مفتاح صنف مستقر بنفس تطبيع الذاكرة + حذف «ال» التعريف المقدمة.

    الأسماء الأقصر من محرفين (بعد التطبيع) بلا إشارة — الشظايا لا تطابق شيئًا.
    """
    n = pure.normalize_for_memory(str(name or ""))
    if len(n) < EVO_FOOD_MIN_LEN:
        return ""
    # «الأرز» بعد التطبيع «الارز» — حذف بادئة «ال» يوحّدها مع «ارز» (حراسة: كلمة حقيقية خلفها).
    if n.startswith("ال") and len(n) >= 4 and n[2].isalpha() and n[3].isalpha():
        n = n[2:].strip()
    return n


def _nullish(value: Any, fallback: Any = None) -> Any:
    """محاكاة ‎??‎: None فقط يستدعي البديل — السلسلة الفارغة قيمة محفوظة."""
    return value if value is not None else fallback


def _item_from_loose(raw: Any) -> Optional[Dict]:
    if not isinstance(raw, dict):
        return None
    food = _nullish(_nullish(raw.get("food"), raw.get("name")), "")
    food = str(food).strip()
    if not food:
        return None
    calories = None
    cal_raw = raw.get("calories")
    if cal_raw is not None:
        n = to_number(cal_raw)
        if n is not None and n > 0:
            calories = js_round(n)
    return {"food": food, "calories": calories}


def _pick_meals(content: Any) -> List[Any]:
    if isinstance(content, dict):
        meals = content.get("meals")
        if isinstance(meals, list):
            return meals
    return []


def extract_meal_items(content: Any) -> List[Dict]:
    """الأصناف المختارة فقط (items الرئيسية — البدائل لا تلوث التكرار) من الشكلين."""
    out: List[Dict] = []
    for meal in _pick_meals(content):
        if not isinstance(meal, dict):
            continue
        items = meal.get("items")
        if not isinstance(items, list):
            continue
        for raw in items:
            item = _item_from_loose(raw)
            if item:
                out.append(item)
    return out


def _num_field(rec: Dict, key: str) -> Optional[float]:
    n = to_number(rec.get(key))
    if n is None or not math.isfinite(n) or n <= 0:
        return None
    return n


def extract_nutrition_numbers(content: Any, totals: Optional[Dict] = None) -> Dict:
    """أرقام الخطة من الشكلين: المحتوى المنظم أولًا ثم إجماليات صف meal_plans.

    الغائب = None — المجمّع لا يخترع قيمًا أبدًا.
    """
    daily_calories = None
    protein = None
    carbs = None
    fat = None
    if isinstance(content, dict):
        daily_calories = _num_field(content, "daily_calories")
        macros = content.get("macros")
        if isinstance(macros, dict):
            protein = _num_field(macros, "protein_g")
            carbs = _num_field(macros, "carbs_g")
            fat = _num_field(macros, "fat_g")
    if totals:
        if daily_calories is None:
            daily_calories = _num_field(totals, "calories")
        if protein is None:
            protein = _num_field(totals, "protein")
        if carbs is None:
            carbs = _num_field(totals, "carbs")
        if fat is None:
            fat = _num_field(totals, "fat")
    meals = _pick_meals(content)
    meal_count = len(meals) if len(meals) > 0 else None
    return {
        "dailyCalories": daily_calories,
        "protein": protein,
        "carbs": carbs,
        "fat": fat,
        "mealCount": meal_count,
    }


# ───────────────────────────── E1 — التجميع الحتمي ─────────────────────────────


def _avg(nums: List[float]) -> Optional[int]:
    if not nums:
        return None
    return js_round(sum(nums) / len(nums))


def aggregate_nutrition_patterns(sources: List[Dict]) -> List[Dict]:
    """E1 — تجميع حتمي بلا LLM (تكلفة صفر) بأرضية الصدق والمجهولية بالبناء.

    sources: قائمة بخطط NutritionPlanSource (origin/approved/goalText/content/totals).
    يعيد مسودات صفوف جاهزة للإدراج (0080 shape) — العينة الرقيقة تُحجب.
    """
    drafts: List[Dict] = []
    goals: Dict[str, Dict] = {}
    meal_counts: Dict[int, int] = {}
    foods: Dict[str, Dict] = {}

    source_list = list(sources or [])[:EVO_AGG_SOURCES_MAX]
    for index, src in enumerate(source_list):
        nums = extract_nutrition_numbers(src.get("content"), src.get("totals"))
        # حاجز الهدف المجهول: بلا نص هدف حقيقي لا يدخل المصدر عائلات الهدف أبدًا.
        goal_text = str(_nullish(src.get("goalText"), "")).strip()
        if goal_text:
            goal = classify_goal(goal_text)
            agg = goals.setdefault(
                goal, {"count": 0, "calories": [], "protein": [], "carbs": [], "fat": []}
            )
            if nums["dailyCalories"] is not None:
                agg["calories"].append(nums["dailyCalories"])
            if nums["protein"] is not None:
                agg["protein"].append(nums["protein"])
            if nums["carbs"] is not None:
                agg["carbs"].append(nums["carbs"])
            if nums["fat"] is not None:
                agg["fat"].append(nums["fat"])
            # المساهمة في دلو الهدف عند حمل أي رقم قابل للاستخدام.
            if nums["dailyCalories"] is not None or nums["protein"] is not None:
                agg["count"] += 1

        if nums["mealCount"] is not None:
            mc = nums["mealCount"]
            meal_counts[mc] = meal_counts.get(mc, 0) + 1

        seen = set()
        for item in extract_meal_items(src.get("content")):
            key = normalize_food_name(item["food"])
            if not key or key in seen:
                continue
            seen.add(key)
            entry = foods.setdefault(key, {"plans": set(), "display": {}})
            entry["plans"].add(index)
            raw = str(item["food"]).strip()
            entry["display"][raw] = entry["display"].get(raw, 0) + 1

    for goal, agg in goals.items():
        if agg["count"] >= EVO_MIN_GOAL_SAMPLE and len(agg["calories"]) >= EVO_MIN_GOAL_SAMPLE:
            drafts.append(
                {
                    "bucket": "calories_by_goal",
                    "key": goal,
                    "payload": {
                        "count": agg["count"],
                        "avg": _avg(agg["calories"]),
                        "min": min(agg["calories"]),
                        "max": max(agg["calories"]),
                    },
                    "sample_size": agg["count"],
                }
            )
        if agg["count"] >= EVO_MIN_GOAL_SAMPLE and len(agg["protein"]) >= EVO_MIN_GOAL_SAMPLE:
            drafts.append(
                {
                    "bucket": "macros_by_goal",
                    "key": goal,
                    "payload": {
                        "count": agg["count"],
                        "avg_protein": _avg(agg["protein"]),
                        "avg_carbs": _avg(agg["carbs"]),
                        "avg_fat": _avg(agg["fat"]),
                    },
                    "sample_size": agg["count"],
                }
            )

    for count, plans in meal_counts.items():
        drafts.append(
            {
                "bucket": "meal_count",
                "key": str(count),
                "payload": {"count": plans},
                "sample_size": plans,
            }
        )

    for key, entry in foods.items():
        if len(entry["plans"]) < EVO_MIN_FOOD_PLANS:
            continue
        # صورة العرض = التهجئة الخام الأكثر تكرارًا (الأولى تفوز عند التساوي).
        display = key
        best = -1
        for raw, n in entry["display"].items():
            if n > best:
                best = n
                display = raw
        drafts.append(
            {
                "bucket": "food_frequency",
                "key": key,
                "payload": {"plans": len(entry["plans"]), "display": display},
                "sample_size": len(entry["plans"]),
            }
        )

    return drafts


# ───────────────────────────── E2 — النموذج المرجعي ────────────────────────────


def build_exemplar_skeleton(content: Any) -> Optional[Dict]:
    """E2 — هيكل مرجعي من الحقول المنظمة فقط؛ النص الحر لا يدخل بالبناء.

    يعيد None لأي خطة ناقصة البنية (لا سعرات أو ماكروز كاملة أو وجبات).
    عينة واحدة لا تجميع — ضوابط دخوله المعرفة العامة في بوابة G-EX (الخطة §2-ب).
    """
    if not isinstance(content, dict):
        return None
    daily_calories = _num_field(content, "daily_calories")
    macros_rec = content.get("macros")
    meals = _pick_meals(content)
    if not daily_calories or not isinstance(macros_rec, dict) or len(meals) == 0:
        return None
    protein = _num_field(macros_rec, "protein_g")
    carbs = _num_field(macros_rec, "carbs_g")
    fat = _num_field(macros_rec, "fat_g")
    if protein is None or carbs is None or fat is None:
        return None

    skeleton_meals = []
    for meal in meals[:EVO_EXEMPLAR_MEALS_MAX]:
        if not isinstance(meal, dict):
            continue
        name = str(_nullish(meal.get("name"), "")).strip()
        if not name:
            continue
        total_cals = _num_field(meal, "total_calories")
        items = []
        raw_items = meal.get("items") if isinstance(meal.get("items"), list) else []
        for raw in raw_items[:EVO_EXEMPLAR_ITEMS_MAX]:
            item = _item_from_loose(raw)
            if not item:
                continue
            assert isinstance(raw, dict)
            entry: Dict[str, Any] = {"food": item["food"]}
            amount = raw.get("amount")
            if isinstance(amount, str) and amount.strip():
                entry["amount"] = amount.strip()
            if item["calories"] is not None:
                entry["calories"] = item["calories"]
            items.append(entry)
        if not items:
            continue
        skeleton_meals.append(
            {"name": name, "total_calories": total_cals, "items": items}
        )

    if not skeleton_meals:
        return None
    return {
        "daily_calories": daily_calories,
        "macros": {"protein_g": protein, "carbs_g": carbs, "fat_g": fat},
        "meals": skeleton_meals,
    }


def pick_exemplar_source(sources: List[Dict]) -> Optional[Dict]:
    """منتقي E2: المعتمدة أولًا (إشارة الجودة)، ثم اكتمال البنية، ثم الحداثة.

    القائمة من المتصل مرتبة من الأحدث إلى الأقدم — المؤشر الأصغر أحدث.
    """
    best_source = None
    best_score = -1
    candidates = list(sources or [])[:EVO_AGG_SOURCES_MAX]
    for index, source in enumerate(candidates):
        skeleton = build_exemplar_skeleton(source.get("content"))
        if not skeleton:
            continue
        recency = max(0, 50 - index)
        completeness = min(len(skeleton["meals"]), EVO_EXEMPLAR_MEALS_MAX)
        approval = 100 if source.get("approved") else 0
        origin = 10 if source.get("origin") == "plans" else (5 if source.get("origin") == "external_plans" else 0)
        score = approval + origin + completeness * 5 + recency
        if score > best_score:
            best_score = score
            best_source = source
    return best_source


# ───────────────────────────── E3 — تعلم الاستبدال ─────────────────────────────


def diff_food_names(old_content: Any, new_content: Any) -> Dict:
    """فرق أصناف الخطة القديمة مقابل المعدلة — هوية الصنف الحقيقية للتعلم.

    مفاتيح مطبّعة تزيل تكرار صور الإملاء؛ أول تهجئة خام تُحفظ صورةً للعرض؛
    السقف 40 صنفًا لكل جانب حتى لا يغرق حدث صاخب الدلاء.
    """

    def collect(content: Any) -> Dict[str, str]:
        result: Dict[str, str] = {}
        for item in extract_meal_items(content):
            key = normalize_food_name(item["food"])
            if key and key not in result:
                result[key] = str(item["food"]).strip()
        return result

    old_map = collect(old_content)
    new_map = collect(new_content)
    removed = [
        {"key": k, "display": d}
        for k, d in old_map.items()
        if k not in new_map
    ][:EVO_SWAP_DIFF_MAX]
    added = [
        {"key": k, "display": d}
        for k, d in new_map.items()
        if k not in old_map
    ][:EVO_SWAP_DIFF_MAX]
    return {"removed": removed, "added": added}


def merge_swap_payload(
    existing: Optional[Dict], foods: List[str], now: Optional[datetime] = None
) -> Dict:
    """دمج قراءة-تعديل-كتابة لزيادة استبدال واحدة — المتصل يختم الطابع.

    يتحمل الحمولات التالفة (base=0) — لا يرمي استثناءً أبدًا.
    """
    prev = to_number((existing or {}).get("count"))
    base = prev if (prev is not None and prev > 0) else 0
    return {"count": int(base + len(foods or [])), "last_seen": _utc_iso(now)}


# ───────────────────────────── حقن البرومت ─────────────────────────────


def _ar_num(n: float) -> str:
    i = int(n) if isinstance(n, float) and n.is_integer() else n
    return f"{i:,}"


def _dumps_compact(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":"))


def build_platform_knowledge_block(rows: List[Dict]) -> str:
    """كتلة «معرفة المنصة الغذائية» (E1+E2) — أرضية الصدق والوسم المرجعي ساريان.

    المدخل الفارغ أو الرقيق كله = سلسلة فارغة (لا قسم فارغ في البرومت أبدًا).
    """
    rows = list(rows or [])
    calories = [r for r in rows if r.get("bucket") == "calories_by_goal"]
    macros = [r for r in rows if r.get("bucket") == "macros_by_goal"]
    meal_counts = [r for r in rows if r.get("bucket") == "meal_count"]
    foods = sorted(
        [r for r in rows if r.get("bucket") == "food_frequency"],
        key=lambda r: -(to_number((r.get("payload") or {}).get("plans")) or 0),
    )[:EVO_FOOD_TOP_INJECT]
    exemplar = next((r for r in rows if r.get("bucket") == "exemplar"), None)

    lines: List[str] = []
    if calories or macros:
        lines.append(
            "أرقام مجمعة مجهولة الهوية من خطط حقيقية على منصة Alkemos "
            "(راجعها كمرجع اتجاه لا كقاعدة صارمة — أرقام العميل الرسمية أعلاه تبقى الحاكمة):"
        )
        for row in calories:
            p = row.get("payload") or {}
            mean, mn, mx = p.get("avg"), p.get("min"), p.get("max")
            if not all(isinstance(v, (int, float)) for v in (mean, mn, mx)):
                continue
            lines.append(
                f"- {GOAL_AR.get(row['key'], row['key'])}: متوسط {_ar_num(mean)} سعرة يوميًا "
                f"(نطاق شائع {_ar_num(mn)}–{_ar_num(mx)} من {row.get('sample_size', 0)} خطة)"
            )
        for row in macros:
            p = row.get("payload") or {}
            ap, ac, af = p.get("avg_protein"), p.get("avg_carbs"), p.get("avg_fat")
            if not all(isinstance(v, (int, float)) for v in (ap, ac, af)):
                continue
            lines.append(
                f"- {GOAL_AR.get(row['key'], row['key'])} (ماكروز شائعة): "
                f"بروتين {_ar_num(ap)}جم / كارب {_ar_num(ac)}جم / دهون {_ar_num(af)}جم"
            )
    if meal_counts:
        top = [f"{r['key']} وجبات" for r in sorted(
            meal_counts,
            key=lambda r: -(to_number((r.get("payload") or {}).get("count")) or 0),
        )[:3]]
        if top:
            lines.append(f"- عدد الوجبات الأكثر شيوعًا في الخطط الحقيقية: {' · '.join(top)}")
    if len(foods) >= 3:
        listing = "، ".join(
            str((r.get("payload") or {}).get("display") or r.get("key")) for r in foods
        )
        lines.append(f"- أصناف متكررة في خطط المنصة (استخدمها كأساس مألوف مع التنويع): {listing}")
    if exemplar and isinstance(exemplar.get("payload"), dict):
        skeleton = exemplar["payload"]
        if (
            isinstance(skeleton.get("daily_calories"), (int, float))
            and isinstance(skeleton.get("meals"), list)
            and len(skeleton["meals"]) > 0
        ):
            lines.append(
                "هيكل مرجعي (الشكل فقط — ممنوع نسخ أصنافه حرفيًا): "
                + _dumps_compact(
                    {"daily_calories": skeleton["daily_calories"], "meals": skeleton["meals"]}
                )
            )

    if not lines:
        return ""
    return "\n\n📊 معرفة المنصة الغذائية (مجمّعة مجهولة الهوية من خطط حقيقية):\n" + "\n".join(lines)


def build_swap_learning_block(rows: List[Dict]) -> str:
    """كتلة تعلم الاستبدال (E3): قلّل الاعتماد على المستبدَل وقدّم البدائل المختارة فعلًا.

    أرضية الاستبدال: أقل من 3 أحداث حقيقية لا تستحق سطرًا في البرومت.
    """
    rows = list(rows or [])

    def count_of(r: Dict) -> float:
        return to_number((r.get("payload") or {}).get("count")) or 0

    over_floor = lambda r: count_of(r) >= EVO_SWAP_MIN_COUNT  # noqa: E731
    removed = sorted(
        [r for r in rows if r.get("bucket") == "swap_removed" and over_floor(r)],
        key=lambda r: -count_of(r),
    )[:EVO_SWAP_TOP_INJECT]
    added = sorted(
        [r for r in rows if r.get("bucket") == "swap_added" and over_floor(r)],
        key=lambda r: -count_of(r),
    )[:EVO_SWAP_TOP_INJECT]
    volume = [r for r in rows if r.get("bucket") == "swap_volume"]

    lines: List[str] = []
    if removed:
        listing = "، ".join(
            f"{(r.get('payload') or {}).get('display') or r.get('key')} ({int(count_of(r))})"
            for r in removed
        )
        lines.append(
            f"- أصناف يستبدلها المستخدمون كثيرًا — قلّل الاعتماد عليها واقترح بدائل أذكى مباشرة: {listing}"
        )
    if added:
        listing = "، ".join(
            str((r.get("payload") or {}).get("display") or r.get("key")) for r in added
        )
        lines.append("- بدائل يختارها المستخدمون فعلًا عند الاستبدال — يُفضّل الاقتراح بها أولًا: " + listing)
    for row in volume:
        p = row.get("payload") or {}
        last_week, total = p.get("last_week"), p.get("total")
        if isinstance(last_week, (int, float)) and last_week > 0:
            suffix = f" (الإجمالي {_ar_num(total)})" if isinstance(total, (int, float)) else ""
            kind = "الوجبات" if row.get("key") == "meal" else "التمارين"
            lines.append(f"- استبدالات {kind} المسجلة أسبوعيًا على المنصة: {_ar_num(last_week)}{suffix}")

    if not lines:
        return ""
    return "\n\n🔁 تعلم من سلوك الاستبدال الحقيقي (مجهول الهوية):\n" + "\n".join(lines)
