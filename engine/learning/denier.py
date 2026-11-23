#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""فاحص قائمة الحرمان الآلي — الشرط الثاني من شروط بوابة G-EX.

الفحص الآلي «حزام وأحزمة» فقط ولا يعوّض المراجعة البشرية أبدًا: أي شك = رفض
مؤرشف (الخطة §6 شرط 2). القائمة البادئة موثقة أدناه وقابلة للتوسيع — كل إضافة
تُوثق بقياس في سجل التعلم.

النطاقات المفحوصة (بداية):
- البريد الإلكتروني وأرقام الهواتف (تسعة أرقام فأكثر بأي فواصل) والرقم القومي (14 رقمًا).
- مفردات سريرية/دوائية/نفسية بادئة عربية وإنجليزية (تشخيص/دواء/اكتئاب...) —
  الكلمة العامة تُرفض والإيجابية الزائفة مقبولة هنا عمدًا: بوابة أمثلة التدريب
  أشد تحفظًا من فحص المخرجات لأن الضرر (تسرب هوية) لا يُعالج بعد الوقوع.
"""
from __future__ import annotations

import re
from typing import Dict, List

EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
# رقم هاتف: يبدأ برقم (وربما +) ويمتد بفواصل — ثم نعدّ الأرقام الفعلية.
_PHONE_CANDIDATE_RE = re.compile(r"\+?\d[\d\s\-()]{7,}\d")
NATIONAL_ID_RE = re.compile(r"\b\d{14}\b")

DENIAL_KEYWORDS = (
    # عربية — سريرية/دوائية/نفسية (بداية قابلة للتوسيع)
    "تشخيص", "مشخص", "مصاب", "يعاني من", "يعاني", "مرض", "أمراض", "دواء", "أدوية",
    "علاج", "جرعة", "جرعات", "حبوب", "اقراص", "انسولين", "اكتئاب", "قلق", "نفسي",
    "نفسية", "طبيب", "أطباء", "تحليل", "أشعة", "عملية جراحية",
    # إنجليزية
    "diagnosis", "diagnosed", "disease", "disorder", "medication", "medications",
    "medicine", "drug", "drugs", "dose", "dosage", "insulin", "depression",
    "anxiety", "therapist", "psychiatr", "surgery", "clinic",
)

_KIND_AR = {
    "email": "بريد إلكتروني",
    "phone": "رقم هاتف",
    "national_id": "رقم قومي (14 رقمًا)",
    "keyword": "مفردة من قائمة الحرمان",
}


def _count_digits(s: str) -> int:
    return sum(ch.isdigit() for ch in s)


def scan_text(text: str) -> Dict:
    """فحص نص ضد قائمة الحرمان — يعيد {passed, hits} ولا يرمي استثناءً أبدًا.

    passed=True فقط عند صفر إصابات: أي إصابة = فشل الشرط الآلي (والمراجعة
    البشرية شرط مستقل إلزامي فوق هذا الفحص في بوابة G-EX).
    """
    hits: List[Dict] = []
    s = str(text or "")
    lowered = s.lower()

    for m in EMAIL_RE.finditer(s):
        hits.append({"kind": "email", "match": m.group(0)})
    for m in _PHONE_CANDIDATE_RE.finditer(s):
        if _count_digits(m.group(0)) >= 9:
            hits.append({"kind": "phone", "match": m.group(0).strip()})
    for m in NATIONAL_ID_RE.finditer(s):
        hits.append({"kind": "national_id", "match": m.group(0)})
    for kw in DENIAL_KEYWORDS:
        start = 0
        while True:
            idx = lowered.find(kw, start)
            if idx < 0:
                break
            hits.append({"kind": "keyword", "match": s[idx : idx + len(kw)]})
            start = idx + len(kw)

    described = [
        {"kind": h["kind"], "kind_ar": _KIND_AR.get(h["kind"], h["kind"]), "match": h["match"]}
        for h in hits
    ]
    return {"passed": len(described) == 0, "hits": described}
