#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""خدمة ذاكرة العملاء (R1) — الغلاف الحاكم فوق المخزن والوحدات النقية.

عقد الواجهة (الخطة §3): MemoryProvider.getInjectableContext(client_id) = كتل
برومت جاهزة ناتجة عن دوال نقية — نفس توقيع formatEvoMemoryForPrompt.
هذه الخدمة لا تعرف هوية أي نموذج أو مزود (قانون الاستقلالية §1).

(دفعة 16-تتمة — عزل بيانات العملاء بأمر المالك):
- **لا دور نصيًّا من المستدعي أبدًا:** الصلاحية تأتي من `Principal` موثقة أنشأتها
  طبقة المصادقة (engine.auth) بعد فحص توقيع الرمز — قيمة `role` يمررها المستدعي
  لا تُقبل ولا تمنح شيئًا (كانت الثغرة الأولى في مراجعة المحرك).
- **عزل العملاء بنيويًا:** كل عملية تحمل client_id تفحص نطاق الهوية أولًا —
  خدمة مرتبطة بعميل لا تبلغ ذاكرة عميل آخر مهما عُرف معرفه، والعميل لا يبلغ
  غير ذاكرته، والأدمن لا يتجاوز نطاقه الصريح.
- **أقل صلاحية لكل نوع:** service = قراءة+كتابة لنطاقه · admin = مراجعة+إلغاء
  تنشيط لنطاقه · owner = الكل + الحذف النهائي بأمر موثق حصرًا.

دورة الاستخراج: عداد لكل عميل على الخادم فقط (الخادم يزيده ثم يقرر) —
المتصفح لا يرى العداد أبدًا (نمط evo_memory_state المضاد للعبث).
"""
from __future__ import annotations

from typing import Dict, List, Optional, Tuple

from .. import auth
from . import pure
from .store import MemoryStore, utc_now_iso


class MemoryServiceError(RuntimeError):
    pass


class AccessDenied(MemoryServiceError):
    """تجاوز نطاق أو صلاحية — يوثق من حاول وماذا حاول (لا يمر الصمت)."""


class MemoryService:
    """المستوى أ كاملًا: استخراج، تخزين، حقن، حوكمة — فوق أي MemoryStore.

    البناء يطلب هوية موثقة حصرًا: `MemoryService(store, principal)` حيث
    `principal` من `TokenAuthority.verify(token)` — لا يوجد مسار آخر للامتياز.
    """

    def __init__(self, store: MemoryStore, principal: auth.Principal) -> None:
        if isinstance(principal, str) or not isinstance(principal, auth.Principal):
            raise MemoryServiceError(
                "الأدوار لا تُمرر نصًا من المستدعي — الهوية تُوثق عبر طبقة المصادقة "
                "(engine.auth.TokenAuthority.verify) ثم تُمرر Principal موثقة. "
                "أي قيمة أخرى مرفوضة."
            )
        if principal.expires_at and principal.expires_at <= _unix_now():
            raise MemoryServiceError("انتهت صلاحية هوية الوصول — جدّد الرمز قبل الاستخدام")
        self.store = store
        self.principal = principal

    # -- حرس الصلاحية والنطاق --------------------------------------------------
    def _require(self, permission: str) -> None:
        if not self.principal.can(permission):
            raise AccessDenied(
                f"الهوية {self.principal.describe()} لا تملك الصلاحية '{permission}' "
                "— مبدأ أقل صلاحية."
            )

    def _check_client(self, client_id: str) -> None:
        if not self.principal.can_access_client(client_id):
            raise AccessDenied(
                f"الهوية {self.principal.describe()} لا يغطي نطاقها العميل '{client_id}' "
                "— معرفة client_id لا تمنح وصولًا (عزل بيانات العملاء)."
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
        self._require(auth.PERM_MEMORY_WRITE)
        self._check_client(client_id)
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
        self._require(auth.PERM_MEMORY_READ)
        self._check_client(client_id)
        rows = self.store.load_facts(client_id, active_only=True)
        facts = pure.sanitize_stored_facts(rows)
        return pure.format_evo_memory_for_prompt(facts)

    # -- الحوكمة ---------------------------------------------------------------
    def review_facts(self, client_id: str) -> List[Dict]:
        """قراءة المراجعة (نمط 0081) — الأدمن في نطاقه أو المالك."""
        self._require(auth.PERM_MEMORY_REVIEW)
        self._check_client(client_id)
        return self.store.load_facts(client_id, active_only=False)

    def deactivate_fact(self, client_id: str, fact_id: str, now: Optional[str] = None) -> bool:
        """إلغاء التنشيط بدل الحذف (D2) — الأدمن في نطاقه أو المالك."""
        self._require(auth.PERM_MEMORY_DEACTIVATE)
        self._check_client(client_id)
        return self.store.set_fact_active(client_id, fact_id, False, now or utc_now_iso())

    def reactivate_fact(self, client_id: str, fact_id: str, now: Optional[str] = None) -> bool:
        self._require(auth.PERM_MEMORY_DEACTIVATE)
        self._check_client(client_id)
        return self.store.set_fact_active(client_id, fact_id, True, now or utc_now_iso())

    def hard_delete_fact(
        self, client_id: str, fact_id: str, owner_order_ref: str
    ) -> bool:
        """الحذف النهائي — المالك حصرًا وبأمر مالك موثق غير فارغ (D2)."""
        self._require(auth.PERM_MEMORY_HARD_DELETE)
        self._check_client(client_id)
        if not (owner_order_ref and owner_order_ref.strip()):
            raise MemoryServiceError(
                "الحذف النهائي يتطلب مرجع أمر مالك موثقًا (D2) — لا حذف بلا أمر."
            )
        return self.store.delete_fact(client_id, fact_id)


def _unix_now() -> int:
    import time
    return int(time.time())
