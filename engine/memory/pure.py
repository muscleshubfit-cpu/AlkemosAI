#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""الوحدات النقية لذاكرة العملاء — نقل حرفي السلوك من EVO (قراءة فقط).

الأصل: alkemos-aws @ 500ed1f246be9dabc9a8a9402acadad10c009fc3
       src/lib/evo-memory.ts (EVO-2 — W3) — المالك واحد للمالكين، والخريطة
       المرافقة §4 أجازت النقل مع استبدال نقطة الوصول للتخزين فقط.

القوانين المنقولة كما هي:
- قائمة الحرمان (PII denial-list) جزء من عقد برومت الاستخراج نفسه — لا سياسة خارجية.
- لا يصل أي نص حر غير مسقوف إلى المخزن: حقائق ≤300 حرف، ≤5 حقائق لكل استخراج.
- إزالة التكرار بالتطبيع (توحيد الإملاء العربي + الأرقام العربية-الهندية → لاتينية).
- كل دوال التحقق لا ترمي استثناءً أبدًا: مدخلات فاسدة = صفر حقائق.
- الحقن: أعلى 15 حقيقة نشطة، والمدخل الفارغ = سلسلة فارغة (لا قسم فارغ أبدًا).

أسماء الدوال محفوظة بأسمائها الأصلية (snake_case) لتتبع الأصل حرفيًا.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

EVO_MEMORY_FACT_MAX = 300
EVO_MEMORY_FACTS_PER_EXTRACTION = 5
EVO_MEMORY_TOP_INJECT = 15
EVO_MEMORY_EXTRACT_EVERY = 10
EVO_MEMORY_TRANSCRIPT_MESSAGE_MAX = 500
EVO_MEMORY_TRANSCRIPT_MESSAGES = 12

CATEGORIES = ("goal", "preference", "lifestyle", "constraint", "other")

# نطاقات الحركات/التطويل والأرقام العربية-الهندية الممتدة — نفس نطاقات الأصل.
_DIACRITICS = re.compile(r"[\u064B-\u0652\u0670\u0640]")
_ARABIC_INDIC = {chr(0x0660 + i): str(i) for i in range(10)}   # ٠-٩
_ARABIC_EXT = {chr(0x06F0 + i): str(i) for i in range(10)}     # ۰-۹
_ALEF_FORMS = str.maketrans({"أ": "ا", "إ": "ا", "آ": "ا", "ٱ": "ا",
                             "ى": "ي", "ة": "ه", "ؤ": "و", "ئ": "ي"})
_WS = re.compile(r"\s+")


def normalize_for_memory(text: str) -> str:
    """توحيد الإملاء العربي + حالة اللاتيني لمطابقة تكرار مستقرة (نفس سلوك الأصل).

    يحذف الحركات والتطويل، يحوّل الأرقام العربية-الهندية (الممتدة أيضًا) إلى
    لاتينية، يوحّد صور الألف/الياء/التاء المربوطة/الهمزات، ثم يستبدل كل ما ليس
    حرفًا أو رقمًا بمسافة واحدة ويقص الأطراف.
    """
    s = str(text).lower()
    s = _DIACRITICS.sub("", s)
    s = s.translate(str.maketrans(_ARABIC_INDIC))
    s = s.translate(str.maketrans(_ARABIC_EXT))
    s = s.translate(_ALEF_FORMS)
    # [^\p{L}\p{N}]+ → " " : كل ما ليس حرفًا/رقمًا يصير فاصلًا واحدًا.
    out = "".join(ch if ch.isalnum() else " " for ch in s)
    return _WS.sub(" ", out).strip()


def is_duplicate_memory_fact(candidate: str, existing: List[str]) -> bool:
    """تكرار بسيط: تساوي بعد التطبيع، أو احتواء حين تكون الأقصر عبارة حقيقية (≥8 محارف).

    المرشح الذي يطبَّع إلى فراغ يُعد مكررًا (يُحذف ولا يُخزن) — نفس الأصل.
    """
    c = normalize_for_memory(candidate)
    if not c:
        return True
    for e in existing:
        n = normalize_for_memory(e)
        if not n:
            continue
        if c == n:
            return True
        if len(c) >= 8 and len(n) >= 8 and (n in c or c in n):
            return True
    return False


def _parse_category(value: Any) -> str:
    if isinstance(value, str):
        hit = value.strip().lower()
        if hit in CATEGORIES:
            return hit
    return "other"


def sanitize_stored_facts(rows: List[Dict[str, Any]]) -> List[Dict[str, str]]:
    """تعقيم صفوف مقروءة من المخزن قبل الحقن — لا يرمي استثناءً أبدًا؛ الصف الفاسد يُسقط.

    يسقف كل حقيقة عند 300 محرف ويقص القائمة عند 15 (سقف الحقن).
    """
    out: List[Dict[str, str]] = []
    for row in rows or []:
        if not isinstance(row, dict):
            continue
        raw = row.get("fact")
        if not isinstance(raw, str):
            continue
        fact = _WS.sub(" ", raw).strip()[:EVO_MEMORY_FACT_MAX]
        if len(fact) < 3:
            continue
        out.append({"fact": fact, "category": _parse_category(row.get("category"))})
        if len(out) >= EVO_MEMORY_TOP_INJECT:
            break
    return out


def validate_memory_facts(parsed: Any, existing: Optional[List[str]] = None) -> List[Dict[str, str]]:
    """تحويل مخرجات الاستخراج (أي شكل) إلى مسودات حقائق نظيفة — لا يرمي استثناءً أبدًا.

    يقبل [{fact, category}, ...] و["fact", ...]؛ يسقف الدفعة عند 5 وكل حقيقة عند
    300 محرف، ويطبّع الأسطر الجديدة (حماية كتلة الحقن سطرًا لكل حقيقة)، ويزيل
    التكرار داخل الدفعة وضد الحقائق النشطة القائمة للمتصل.
    """
    if not isinstance(parsed, list):
        return []
    out: List[Dict[str, str]] = []
    seen: List[str] = list(existing or [])
    for item in parsed:
        if len(out) >= EVO_MEMORY_FACTS_PER_EXTRACTION:
            break
        raw_fact = None
        if isinstance(item, str):
            raw_fact = item
        elif isinstance(item, dict) and isinstance(item.get("fact"), str):
            raw_fact = item["fact"]
        if raw_fact is None:
            continue
        fact = _WS.sub(" ", raw_fact).strip()[:EVO_MEMORY_FACT_MAX]
        if len(fact) < 3:
            continue
        if is_duplicate_memory_fact(fact, seen):
            continue
        category = _parse_category(item.get("category")) if isinstance(item, dict) else "other"
        out.append({"fact": fact, "category": category})
        seen.append(fact)
    return out


def build_evo_memory_prompt(transcript: List[Dict[str, str]]) -> Optional[str]:
    """بناء برومت الاستخراج من نص المحادثة — None حين لا توجد رسالة مستخدم.

    قائمة الحرمان جزء من العقد نفسه: حقائق حياتية/لياقية دائمة فقط — أبدًا
    تفاصيل سريرية/نفسية أو أدوية أو اتصال أو مالية أو أسماء أشخاص آخرين.
    النص الإنجليزي منقول حرفيًا من الأصل (اختبارات EVO تتحقق منه).
    """
    user_turns = [m for m in (transcript or []) if isinstance(m, dict) and m.get("role") == "user"]
    if not user_turns:
        return None
    lines = []
    for m in transcript[-EVO_MEMORY_TRANSCRIPT_MESSAGES:]:
        role = "User" if m.get("role") == "user" else "Assistant"
        content = _WS.sub(" ", str(m.get("content", ""))).strip()[:EVO_MEMORY_TRANSCRIPT_MESSAGE_MAX]
        lines.append(f"{role}: {content}")
    return (
        "Below is a conversation between a user and EVO, the digital fitness coach of the Alkemos platform.\n"
        "\n"
        + "\n".join(lines)
        + "\n"
        "\n"
        "Extract 3-5 DURABLE facts about THIS user that a real personal coach would want to remember "
        "across future conversations (their goal, preferences, lifestyle, constraints — e.g. "
        "\"trains at home with dumbbells only\", \"prefers evening workouts\", \"wants to lose 10kg for a "
        "wedding in June\", \"dislikes broccoli\", \"knee pain when running\").\n"
        "\n"
        "STRICT RULES:\n"
        "- Third-person neutral statements about the USER only (never about the assistant).\n"
        "- Durable facts ONLY — never one-off questions or small talk.\n"
        "- NEVER store: medical diagnoses, medications, mental-health details, precise clinical "
        "information, phone numbers, emails, addresses, financial details, or the names of other people.\n"
        "- Write each fact in the SAME language the user wrote in.\n"
        "- Reply with a JSON array ONLY — no prose, no markdown fences:\n"
        "  [{\"fact\": \"...\", \"category\": \"goal|preference|lifestyle|constraint|other\"}]\n"
        "- If nothing durable can be extracted, reply with: []"
    )


def cap_transcript_for_extraction(
    history: List[Dict[str, str]], message: str, reply: str
) -> List[Dict[str, str]]:
    """سقف وتشكيل المحادثة لنداء الاستخراج: آخر 10 رسائل + الرسالة الحالية + ردها."""
    return [
        *list(history or [])[-(EVO_MEMORY_TRANSCRIPT_MESSAGES - 2):],
        {"role": "user", "content": message},
        {"role": "assistant", "content": reply},
    ]


def format_evo_memory_for_prompt(facts: List[Dict[str, str]]) -> str:
    """كتلة «ذاكرة Evo الدائمة» في برومت النظام — المدخل الفارغ = سلسلة فارغة."""
    if not facts:
        return ""
    lines = [f"- [{f['category']}] {f['fact']}" for f in facts[:EVO_MEMORY_TOP_INJECT]]
    return (
        "\n\nذاكرة Evo الدائمة عن المستخدم (مستخلصة من محادثات سابقة — استخدمها طبيعيًا "
        "كمدرب حقيقي يتذكر عملاءه، ولا تعرضها كقائمة):\n" + "\n".join(lines)
    )


def should_extract_memory(count_after_increment: int) -> bool:
    """حد الإيقاع: الاستخراج يشتعِل حين يبلغ العداد (بعد الزيادة) كل رسالة رقم 10."""
    return count_after_increment >= EVO_MEMORY_EXTRACT_EVERY
