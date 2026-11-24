#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ذاكرة استهلاك براهين الخادم (jti) — منع إعادة الاستخدام داخل عمر البرهان.

(مراجعة دفعة 17 — استكمال: أمر المالك «أغلق فجوة إعادة استخدام برهان
الخادم: أضف آلية jti لمنع إعادة استخدام البرهان خلال فترة صلاحيته، مع
تخزين آمن ومحدود زمنيًا، واختبارات إعادة التشغيل والتزامن».)

المشكلة التي يعالجها هذا الملف: برهان الخادم صحيح التوقيع ومرتبط بالرمز
والحساب، لكن **إعادة استخدامه** كانت ممكنة طوال صلاحيته (≤300 ث): من
يلتقط البرهان مع رمز الجلسة (شبكة مُرصَّدة · سجل مضيف · متصفح وكل)
يستطيع مناداة بوابة الخدمة مرة ثانية بنفس البرهان — فكل فحوص التوقيع
والربط تمر لأن البرهان نفسه صحيح. العلاج المعياري: مطالبة ``jti``
(هوية البرهان الفريدة) في حمولة البرهان، و**استهلاكها أحاديًا** عند
المحرك: أول تحقق ناجح يسجل الـjti، وكل محاولة لاحقة بنفس الـjti خلال
صلاحيته تُرفض بصوت عالٍ.

خصائص التخزين (كلها مختبرة):
- **آمن ضد التزامن:** الاستهلاك «تحقق-وسجّل» ذري داخل قفل — خيوط
  العملية بقفل خيوطي، و**العمليات المتعددة بقفل flock وقراءة حالة
  طازجة من الملف داخل القفل** (لا اعتماد على نسخة الذاكرة الموروثة
  بالـfork — اختبار تزامن فعلي بعمليات fork).
- **محدود زمنيًا:** كل مدخل يحمل أجلًا (انتهاء البرهان + سماحية الساعة)
  ويسقط عند أول استهلاك لاحق بعد أجله — الذاكرة لا تنمو بلا سقف زمني،
  وبعد انتهاء البرهان أصلًا يرفضه فحص الصلاحية فلا قيمة لبقائه.
- **ينجو من إعادة التشغيل:** عند إعطاء ``root`` (مسار مطلق خارج شجرة
  git — مستوى أ) تُ persist الحالة ذريًا بعد كل استهلاك وتُحمَّل عند
  البناء؛ فإعادة تشغيل المحرك خلال نافذة صلاحية البرهان لا تفتح نافذة
  إعادة استخدام (اختبار إعادة تشغيل فعلي: كائن جديد على نفس المسار
  يرفض البرهان المستهلك). بلا ``root``: ذاكرة داخل العملية حصرًا
  (حماية داخل العملية — للعقود الاختبارية/المؤقتة).
- **محدود الحجم بسقف صوت عالٍ:** ``max_entries`` مدخلات حية؛ تجاوزه
  بعد التطهير = رفض صوت عالٍ (فشل مغلق) لا تليين ولا إسقاط مدخل حي
  فيفتح باب إعادة استخدام.
- **التلف صوت عالٍ لا إعادة تعيين صامتة:** ملف غير قابل للقراءة أو
  مخطط مجهول = خطأ عند البناء/الاستهلاك — قرار الاستعادة بيد المالك
  (نفس قانون كل مخازن المستوى أ في المستودع).

حدود معلنة بصدق (نفس فلسفة فهرس الحسابات §حدود السلامة):
- من يملك **حق الكتابة على ملف الذاكرة** يستطيع حذف مدخلات (أو الملف
  كله) فيتيح إعادة استخدام برهان التقطه — الشيفرة تكشف التلف/الفساد
  الصريح فقط، أما الحذف المقصود فمسؤولية الطبقة التشغيلية (صلاحيات
  الملف والمراقبة). تخفيف أثر عملي: البرهان مقيد برمز جلسة بعينه
  (بصمة sha256) وحساب بعينه وعمر ≤300 ث — فالحذف لا يخدم المهاجم
  إلا إذا كان يملك الرمز نفسه أيضًا، والرمز يُستهلك بانتهاء جلسة
  العميل.
- الـjti يُستهلك **فقط بعد نجاح التحقق كله** (التوقيع والربط والصلاحية
  — انظر ``server_proof.ServiceProofVerifier.verify``): البراهين
  الفاسدة/المزيفة لا تحرق هويات براهين سواها ولا تسمّم الذاكرة.

هذه الوحدة نقية (stdlib حصرًا — لا شبكة) داخل ``engine/identity``؛
تستخدم أدوات سلامة الملفات المشتركة (``engine/fsafety``) فقط.
"""
from __future__ import annotations

import json
import threading
import time
from pathlib import Path
from typing import Dict, Optional

from ..fsafety import (
    FileLock,
    assert_outside_git_tree,
    atomic_write_text,
)
from .contract import IdentityError

#: مخطط ملف الذاكرة — تغييره يستلزم ترقية صريحة لا قبولًا صامتًا
CACHE_SCHEMA = "alkemos.proof-replay/1"

#: اسم ملف الحالة داخل الجذر
CACHE_FILE = "proof-replay.json"

#: ملف قفل flock (التزامن بين العمليات)
LOCK_FILE = "proof-replay.lock"

#: أقصى طول مقبول لقيمة jti (نص)
JTI_MAX_LENGTH = 128

#: السقف الافتراضي لعدد المدخلات الحية (براهين مستهلكة ضمن صلاحيتها)
#: — 100 ألف برهان حي يعني ~277 برهانًا/ثانية مستدامة طوال نافذة
#: 360 ثانية: أقصى استخدام متوقع بكثير، والتجاوز رفض صوت عالٍ.
DEFAULT_MAX_ENTRIES = 100_000


class ProofReplayError(IdentityError):
    """إعادة استخدام برهان مستهلك (jti مكرر) أو خلل في ذاكرة المنع — صوت عالٍ."""


def _unix_now() -> int:
    return int(time.time())


class ProofReplayCache:
    """ذاكرة استهلاك jti أحادية الاستخدام — آمنة للخيوط والعمليات ومحدودة زمنيًا.

    ``root=None``: ذاكرة داخل العملية (قفل خيوطي — لا استمرارية عبر
    إعادة التشغيل). ``root=<مسار مطلق خارج git>``: حالة ملفية ذرية تحت
    flock تُحمَّل عند البناء وتُقرأ طازجة داخل القفل عند كل استهلاك —
    فالاستهلاك ذري عبر العمليات وينجو من إعادة التشغيل.
    """

    def __init__(self, root=None, *, max_entries: int = DEFAULT_MAX_ENTRIES) -> None:
        try:
            cap = int(max_entries)
        except (TypeError, ValueError) as exc:
            raise ProofReplayError("سقف مدخلات ذاكرة البرهان يجب أن يكون عددًا") from exc
        if cap < 1:
            raise ProofReplayError("سقف مدخلات ذاكرة البرهان يجب أن يكون ≥ 1")
        self._max_entries = cap
        self._thread_lock = threading.Lock()
        self._root: Optional[Path] = None
        self._cache_path: Optional[Path] = None
        self._lock_path: Optional[Path] = None
        if root is not None:
            root_path = Path(root)
            if not root_path.is_absolute():
                raise ProofReplayError(
                    "مسار ذاكرة استهلاك البراهين يجب أن يكون مطلقًا"
                )
            assert_outside_git_tree(root_path)   # بيانات تشغيلية = مستوى أ
            root_path.mkdir(parents=True, exist_ok=True)
            self._root = root_path
            self._cache_path = root_path / CACHE_FILE
            self._lock_path = root_path / LOCK_FILE
        # التحميل عند البناء — التلف صوت عالٍ لا إعادة تعيين صامتة
        self._entries: Dict[str, int] = self._load_fresh()

    # -- الحالة ---------------------------------------------------------------
    def _load_fresh(self) -> Dict[str, int]:
        """قراءة الحالة من الملف (طازجة) — أو ذاكرة فارغة في وضع الذاكرة."""
        if self._root is None or not self._cache_path.exists():
            return {}
        raw = self._cache_path.read_text(encoding="utf-8")
        try:
            doc = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ProofReplayError(
                "ملف ذاكرة استهلاك البراهين تالف (JSON غير قابل للقراءة) — "
                "لا إعادة تعيين صامتة تمحو ذاكرة الاستهلاك: قرار الاستعادة "
                "بيد المالك من نسخة احتياطية"
            ) from exc
        if not isinstance(doc, dict) or doc.get("schema") != CACHE_SCHEMA:
            raise ProofReplayError(
                f"مخطط ملف ذاكرة استهلاك البراهين غير معروف: "
                f"{(doc or {}).get('schema') if isinstance(doc, dict) else None!r}"
            )
        entries = doc.get("entries")
        if not isinstance(entries, dict):
            raise ProofReplayError("مدخلات ذاكرة استهلاك البراهين يجب أن تكون قاموسًا")
        clean: Dict[str, int] = {}
        for jti, deadline in entries.items():
            if isinstance(jti, str) and isinstance(deadline, int) and not isinstance(deadline, bool):
                clean[jti] = deadline
        return clean

    def _persist(self) -> None:
        """كتابة الحالة ذريًا (مؤقت → fsync → replace) — فوريًا بعد الاستهلاك."""
        if self._root is None:
            return
        doc = {
            "schema": CACHE_SCHEMA,
            "updated_note": "مدخلات jti مستهلكة — تسقط بعد أجلها (انتهاء البرهان + سماحية الساعة)",
            "entries": self._entries,
        }
        atomic_write_text(
            self._cache_path,
            json.dumps(doc, ensure_ascii=False, sort_keys=True, indent=2),
        )

    # -- الاستهلاك ---------------------------------------------------------------
    def consume(self, jti: str, *, valid_until: int, now: Optional[int] = None) -> None:
        """استهلاك jti أحاديًا — يرفع ``ProofReplayError`` عند التكرار.

        ``valid_until``: أجل المدخل (انتهاء البرهان + سماحية الساعة)؛
        ``now``: الزمن الحالي (يُمرر من التحقق للاتساق مع فحوص الصلاحية).
        الذرية: تحقق-وسجّل داخل قفل واحد — خيوطيًا في وضع الذاكرة، وفخريًا
        (flock + قراءة طازجة من الملف داخل القفل) في وضع الملف.
        """
        if (
            not isinstance(jti, str)
            or not jti.strip()
            or len(jti) > JTI_MAX_LENGTH
        ):
            raise ProofReplayError(
                f"jti غير صالح — نص غير فارغ بطول ≤{JTI_MAX_LENGTH} حرفًا إلزامي"
            )
        deadline = int(valid_until)
        current = int(now if now is not None else _unix_now())

        if self._root is None:
            # وضع الذاكرة: قفل خيوطي يكفي (عملية واحدة)
            with self._thread_lock:
                self._consume_locked(jti, deadline, current)
            return

        # وضع الملف: flock بين العمليات + قراءة طازجة داخل القفل —
        # نسخة الذاكرة الموروثة بالfork لا تُعتمد أبدًا هنا.
        with FileLock(self._lock_path):
            self._entries = self._load_fresh()
            self._consume_locked(jti, deadline, current)
            self._persist()

    def _consume_locked(self, jti: str, deadline: int, current: int) -> None:
        # التطهير أولًا: مدخلات انتهى أجلها تسقط (ذاكرة محدودة زمنيًا)
        self._entries = {
            k: d for k, d in self._entries.items() if d > current
        }
        if jti in self._entries:
            raise ProofReplayError(
                "برهان الخادم مستهلك أصلًا (jti مكرر ضمن صلاحيته) — "
                "إعادة استخدام البرهان مرفوضة (ذاكرة الاستهلاك أحادية)"
            )
        if len(self._entries) + 1 > self._max_entries:
            raise ProofReplayError(
                f"ذاكرة استهلاك البراهين بلغت سقفها ({self._max_entries} "
                "مدخلًا حيًا بعد التطهير) — رفض صوت عالٍ لا تليين (فشل مغلق: "
                "إسقاط مدخل حي يفتح باب إعادة استخدام)"
            )
        self._entries[jti] = deadline

    # -- التشخيص ---------------------------------------------------------------
    def size(self, *, now: Optional[int] = None) -> int:
        """عدد المدخلات **الحيّة** (أجلها > الآن) — للتشخيص والاختبار فقط."""
        current = int(now if now is not None else _unix_now())
        if self._root is None:
            with self._thread_lock:
                return sum(1 for d in self._entries.values() if d > current)
        with FileLock(self._lock_path):
            self._entries = self._load_fresh()
            return sum(1 for d in self._entries.values() if d > current)

    def max_entries(self) -> int:
        return self._max_entries
