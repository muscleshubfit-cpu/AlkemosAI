#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""خدمة ذاكرة العملاء (R1) — الغلاف الحاكم فوق المخزن والوحدات النقية.

عقد الواجهة (الخطة §3): MemoryProvider.getInjectableContext(client_id) = كتل
برومت جاهزة ناتجة عن دوال نقية — نفس توقيع formatEvoMemoryForPrompt.
هذه الخدمة لا تعرف هوية أي نموذج أو مزود (قانون الاستقلالية §1).

الأدوار (نمط 0078 RLS منقولاً إلى عقد الخدمة):
- service: الكتابة والاستخراج ورفع العداد (وحده من يكتب).
- admin: قراءة للمراجعة + إلغاء تنشيط.
- owner: الحذف النهائي — ولا يتم إلا بأمر مالك موثق (قرار D2 الموروث:
  «إلغاء التنشيط بدل الحذف؛ الحذف النهائي بأمر مالك موثق فقط»).

دورة الاستخراج: عداد لكل عميل على الخادم فقط (الخادم يزيده ثم يقرر) —
المتصفح لا يرى العداد أبدًا (نمط evo_memory_state المضاد للعبث).
"""
from __future__ import annotations

from typing import Dict, List, Optional, Tuple

from . import pure
from .store import MemoryStore, utc_now_iso

ROLE_SERVICE = "service"
ROLE_ADMIN = "admin"
ROLE_OWNER = "owner"
_ROLES = (ROLE_SERVICE, ROLE_ADMIN, ROLE_OWNER)


class MemoryServiceError(RuntimeError):
    pass


class MemoryService:
    """المستوى أ كاملًا: استخراج، تخزين، حقن، حوكمة — فوق أي MemoryStore."""

    def __init__(self, store: MemoryStore, role: str = ROLE_SERVICE) -> None:
        if role not in _ROLES:
            raise MemoryServiceError(f"دور غير معروف: {role}")
        self.store = store
        self.role = role

    # -- حرس الأدوار ---------------------------------------------------------
    def _require(self, *allowed: str) -> None:
        if self.role not in allowed:
            raise MemoryServiceError(
                f"الدور '{self.role}' لا يملك هذه العملية — المسموح: {' أو '.join(allowed)}"
            )

    # -- دورة الاستخراج ------------------------------------------------------
    def record_exchange(
        self,
        client_id: str,
        history: List[Dict[str, str]],
        message: str,
        reply: str,
        parsed_extraction: object,
        now: Optional[str] = None,
    ) -> Tuple[bool, List[Dict]]:
        """تسجيل رسالة: زيادة العداد، وإن بلغ الإيقاع (كل 10) فاستخراج وتخزين.

        parsed_extraction = مخرجات نموذج الاستخراج بعد التحليل (أي شكل —
        validate_memory_facts لا ترمي استثناءً أبدًا). الاستخراج يمر على برومت
        عقد قائمة الحرمان (pure.build_evo_memory_prompt) من جهة المتصل بالنموذج؛
        هنا نتحقق فقط أن النص المقطوع جاهز وأن نتائج التحقق نظيفة.
        يعيد (هل حصل استخراج، الحقائق المخزونة).
        """
        self._require(ROLE_SERVICE)
        now = now or utc_now_iso()
        count = self.store.get_extract_count(client_id) + 1
        self.store.set_extract_count(client_id, count)
        if not pure.should_extract_memory(count):
            return False, []
        # بلغ الإيقاع: جهّز النص المقصوص ثم حقّن مخرجات النموذج في المدقق النقي.
        transcript = pure.cap_transcript_for_extraction(history, message, reply)
        prompt = pure.build_evo_memory_prompt(transcript)
        if prompt is None:
            # لا رسالة مستخدم في المقطع — عدّادها يُرجأ إلى الدورة القادمة.
            self.store.set_extract_count(client_id, count - 1)
            return False, []
        existing = [f["fact"] for f in self.store.load_facts(client_id, active_only=True)]
        drafts = pure.validate_memory_facts(parsed_extraction, existing)
        stored: List[Dict] = []
        for d in drafts:
            stored.append(
                self.store.append_fact(
                    {
                        "client_id": client_id,
                        "fact": d["fact"],
                        "category": d["category"],
                        "is_active": True,
                        "created_at": now,
                        "updated_at": now,
                        "source": "chat_extraction",
                    }
                )
            )
        # العداد يُصفَّر بعد كل استخراج ناجح (نمط أصل العد لكل 10 رسائل).
        self.store.set_extract_count(client_id, 0)
        return True, stored

    # -- الحقن (عقد الواجهة §3) ----------------------------------------------
    def get_injectable_context(self, client_id: str) -> str:
        """كتلة برومت جاهزة من الحقائق النشطة — مدخل أي محرك لاحق (بلا اسم نموذج)."""
        self._require(ROLE_SERVICE, ROLE_ADMIN, ROLE_OWNER)
        rows = self.store.load_facts(client_id, active_only=True)
        facts = pure.sanitize_stored_facts(rows)
        return pure.format_evo_memory_for_prompt(facts)

    # -- الحوكمة ---------------------------------------------------------------
    def review_facts(self, client_id: str) -> List[Dict]:
        """قراءة الأدمن للمراجعة فقط (نمط 0081 — قراءة لا كتابة)."""
        self._require(ROLE_ADMIN, ROLE_OWNER, ROLE_SERVICE)
        return self.store.load_facts(client_id, active_only=False)

    def deactivate_fact(self, client_id: str, fact_id: str, now: Optional[str] = None) -> bool:
        """إلغاء التنشيط بدل الحذف (D2) — الأدمن أو الخدمة."""
        self._require(ROLE_SERVICE, ROLE_ADMIN, ROLE_OWNER)
        return self.store.set_fact_active(client_id, fact_id, False, now or utc_now_iso())

    def reactivate_fact(self, client_id: str, fact_id: str, now: Optional[str] = None) -> bool:
        self._require(ROLE_SERVICE, ROLE_ADMIN, ROLE_OWNER)
        return self.store.set_fact_active(client_id, fact_id, True, now or utc_now_iso())

    def hard_delete_fact(
        self, client_id: str, fact_id: str, owner_order_ref: str
    ) -> bool:
        """الحذف النهائي — owner حصرًا وبأمر مالك موثق غير فارغ (D2)."""
        self._require(ROLE_OWNER)
        if not (owner_order_ref and owner_order_ref.strip()):
            raise MemoryServiceError(
                "الحذف النهائي يتطلب مرجع أمر مالك موثقًا (D2) — لا حذف بلا أمر."
            )
        return self.store.delete_fact(client_id, fact_id)
