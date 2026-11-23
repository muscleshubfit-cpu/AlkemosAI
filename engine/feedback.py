#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""التغذية الراجعة 👍/👎 — تحقق وتطبيع نقيان (قراءة فقط من EVO).

الأصل: alkemos-aws @ 500ed1f246be9dabc9a8a9402acadad10c009fc3
       src/lib/evo-feedback.ts (EVO-1 — W5.1).

وضعية مقاومة الإساءة: كل نص حر مسقوف (السبب ≤300 والمقتطفات ≤500) فلا تصل
حمولة معادية إلى المخزن بلا حدود — وحد الدفعات لكل IP مسؤولية المسار (خارج النقل).
"""
from __future__ import annotations

from typing import Any, Dict, Optional, Tuple

FEEDBACK_REASON_MAX = 300
FEEDBACK_SNIPPET_MAX = 500


def _cap(value: Any, max_len: int) -> Optional[str]:
    if not isinstance(value, str):
        return None
    trimmed = value.strip()
    if not trimmed:
        return None
    return trimmed[:max_len]


def parse_evo_feedback_input(body: Any) -> Tuple[bool, Dict]:
    """تحقق وتطبيع حمولة التغذية الراجعة — لا يرمي استثناءً أبدًا.

    يعيد (True, value) أو (False, {"error": ...}).
    """
    if not isinstance(body, dict):
        return False, {"error": "Invalid payload"}
    feedback = body.get("feedback")
    if feedback not in ("up", "down"):
        return False, {"error": "feedback must be 'up' or 'down'"}
    value = {
        "feedback": feedback,
        "reason": _cap(body.get("reason"), FEEDBACK_REASON_MAX),
        "messageId": _cap(body.get("messageId"), 80),
        "question": _cap(body.get("question"), FEEDBACK_SNIPPET_MAX),
        "reply": _cap(body.get("reply"), FEEDBACK_SNIPPET_MAX),
    }
    return True, {"value": value}
