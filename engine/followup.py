#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""المتابعات — الجزء النقي المدرج في خريطة النقل §4 (قراءة فقط من EVO).

الأصل: alkemos-aws @ 500ed1f246be9dabc9a8a9402acadad10c009fc3
       src/lib/evo-followup.ts — المنقول: isFollowupDue + buildFollowupPrefWrite
       (منشئ البريد الكامل ليس ضمن قائمة النقل — يبقى في EVO).

الحالة في EVO (تدقيق 2026-11-23 §4): بنية غير مفعّلة — مسار الإرسال مقفول
بعلم بيئة افتراضي (404) وبلا أي مجدول. النقل هنا «جاهز حالما تُفتح المتابعات»
بقرار تفعيل مستقل (EVO-3/D4) — لا يفعّل شيئًا بنفسه.

قوانين D4 المنقولة:
- الاشتراك إلزامي: لا إرسال لمشترك غير مفعّل إطلاقًا.
- إيقاع 7 أيام كحد أدنى من آخر إرسال ناجح (null = لم يُرسل قط = مستحق فورًا).
- الطابع التالف يعامل كأنه لم يُرسل قط (فشل متعمد نحو الاستحقاق — الشفافية أولًا).
- الإلغاء تحديث لا حذف (D2) — ولغة العميل تُحفظ لإعادة الاشتراك بنقرة واحدة.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Dict, Optional

EVO_FOLLOWUP_INTERVAL_DAYS = 7
_INTERVAL = timedelta(days=EVO_FOLLOWUP_INTERVAL_DAYS)


def _parse_iso(value: str) -> Optional[datetime]:
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except (ValueError, TypeError):
        return None


def is_followup_due(pref: Dict, now: Optional[datetime] = None) -> bool:
    """بوابة D4: الاشتراك إلزامي + إيقاع 7 أيام من آخر إرسال ناجح."""
    if not pref or not pref.get("opted_in"):
        return False
    last_sent = pref.get("last_sent_at")
    if not last_sent:
        return True
    last = _parse_iso(last_sent)
    if last is None:
        return True  # طابع تالف = لم يُرسل قط
    now_dt = now or datetime.now(timezone.utc)
    if now_dt.tzinfo is None:
        now_dt = now_dt.replace(tzinfo=timezone.utc)
    return now_dt - last >= _INTERVAL


def build_followup_pref_write(
    client_id: str,
    existing: Optional[Dict],
    action: Dict,
    now: Optional[datetime] = None,
) -> Optional[Dict]:
    """تخطيط كتابة مفتاح الاشتراك حتميًا (نقي) — يعيد None حين لا كتابة تلزم.

    - لا صف + تفعيل → INSERT (مع اللغة الملتقطة)
    - لا صف + إلغاء → None (الحالة الافتراضية إلغاء أصلًا)
    - صف + تغيير حقيقي → UPDATE (الإلغاء يبقي اللغة — إعادة الاشتراك بنقرة)
    - صف + لا تغيير → None (لا كتابة ولا churn على updated_at)
    اللغة تُسحب إلى نطاق 0079: أي شيء ليس "en" هو "ar".
    """
    language = "en" if action.get("language") == "en" else "ar"
    opted_in = bool(action.get("optedIn"))
    now_dt = now or datetime.now(timezone.utc)
    if now_dt.tzinfo is None:
        now_dt = now_dt.replace(tzinfo=timezone.utc)
    stamp = now_dt.isoformat(timespec="milliseconds").replace("+00:00", "Z")

    if existing is None:
        if not opted_in:
            return None
        return {
            "mode": "insert",
            "values": {"client_id": client_id, "opted_in": True, "language": language},
        }

    existing_language = existing.get("language") if existing.get("language") is not None else "ar"
    language_changed = opted_in and existing.get("opted_in") and existing_language != language
    if bool(existing.get("opted_in")) == opted_in and not language_changed:
        return None
    if opted_in:
        return {
            "mode": "update",
            "values": {"opted_in": True, "language": language, "updated_at": stamp},
        }
    return {"mode": "update", "values": {"opted_in": False, "updated_at": stamp}}
