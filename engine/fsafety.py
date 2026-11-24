#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""أدوات سلامة الملفات المشتركة — الكتابة الذرية والقفل والاستعادة وحارس المسار.

(دفعة 16-تتمة — تحصين التخزين بأمر المالك بعد مراجعة المحرك)

القوانين المنفذة هنا:
- **كتابة ذرية دائمًا:** ملف مؤقت في الدليل نفسه → fsync → ‏os.replace → fsync
  الدليل — لا حالة وسيطة مرئية للقارئين؛ انقطاع العملية في أسوأ الأحوال يترك
  سطرًا أخيرًا غير مكتمل (لا ملفًا مبتورًا كاملًا) وهو ما تستعيده القراءة.
- **قفل حصري flock حول كل دورة قراءة-تعديل-كتابة:** لا كتابة متزامنة تُضيع
  تحديثات بعضها بعضًا (مختبر بعمليات فعلية متعددة في test_engine_security.py).
- **استعادة آمنة عند الانقطاع:** السطر الأخير المبتور (أثر انقطاع كتابة) يُسقط
  بعد حجز نسخة أصل كدليل في recovery/ — أما تلف وسط الملف فلا يُسقط صمتًا
  أبدًا: نسخة محجوزة + خطأ صريح القرار فيه بيد المالك.
- **حارس المستوى أ:** أي مسار داخل شجرة git يُرفض — بيانات تحمل هوية العملاء
  (ذاكرة/موافقات) لا تسكن مستودعًا عامًا أبدًا (الخطة §2-أ / SECURITY §3).
"""
from __future__ import annotations

import fcntl
import hashlib
import json
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple


class FileCorruptionError(RuntimeError):
    """تلف في وسط الملف لا يمكن إسقاطه بصمت — القرار بيد المالك (النسخة محجوزة)."""


def utc_now_iso() -> str:
    """طابع UTC موحد ISO-8601 بلاحقة Z (ADR-0013)."""
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def canonical_json(obj) -> str:
    """تمثيل حتمي للتوقيع والبصمات: مفاتيح مرتبة بلا فراغات زائدة."""
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def assert_outside_git_tree(path) -> None:
    """حارس المستوى أ: يرفض أي مسار داخل شجرة عمل git (مستودع عام أو خاص).

    يصعد في شجرة الأدلة باحثًا عن دليل .git؛ وجوده يعني أن المسار داخل مستودع
    فيُرفض فورًا — تُطبق على ذاكرة العملاء وسجل الموافقات معًا.
    """
    cur = Path(path).resolve()
    for parent in [cur, *cur.parents]:
        if (parent / ".git").exists():
            raise ValueError(
                "بيانات المستوى أ (تحمل هوية العملاء) خارج المستودع نهائيًا — "
                f"المسار '{path}' يقع داخل شجرة git في '{parent}'. "
                "اختر دليلًا خارج أي مستودع (الخطة §2-أ / SECURITY §3)."
            )


class FileLock:
    """قفل ملف حصري (flock) — دورات القراءة-التعديل-الكتابة كلها تحته.

    القفل بين العمليات والخيوط معًا: كل فتح للملف يمنح وصف ملف مستقلًا
    فتتنافس الأقفال حتى داخل العملية الواحدة.
    """

    def __init__(self, lock_path) -> None:
        self.lock_path = Path(lock_path)

    def __enter__(self) -> "FileLock":
        self.lock_path.parent.mkdir(parents=True, exist_ok=True)
        self._fh = open(self.lock_path, "a+b")
        try:
            fcntl.flock(self._fh.fileno(), fcntl.LOCK_EX)
        except BaseException:
            self._fh.close()
            raise
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        try:
            fcntl.flock(self._fh.fileno(), fcntl.LOCK_UN)
        finally:
            self._fh.close()


def atomic_write_bytes(path, data: bytes) -> None:
    """كتابة ذرية: مؤقت في الدليل نفسه → fsync → استبدال → fsync الدليل."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.tmp-{os.getpid()}")
    with open(tmp, "wb") as fh:
        fh.write(data)
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp, path)
    # fsync الدليل (أفضل جهد — بعض الأنظمة لا تدعمه على الأدلة)
    try:
        dfd = os.open(str(path.parent), os.O_RDONLY)
        try:
            os.fsync(dfd)
        finally:
            os.close(dfd)
    except OSError:
        pass


def atomic_write_text(path, text: str) -> None:
    atomic_write_bytes(path, text.encode("utf-8"))


def atomic_append_line(path, line: str) -> None:
    """إلحاق سطر واحد ذرًّا: open(O_APPEND) + كتابة السطر كاملاً بنداء واحد + fsync.

    الإلحاق داخل القفل + كتابة السطر (مع \\n) بنداء write واحد يضمن عدم تشابك
    الأسطر بين الكتاب المتزامنين.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = (line + "\n").encode("utf-8")
    with open(path, "ab") as fh:
        fh.write(payload)
        fh.flush()
        os.fsync(fh.fileno())


def read_jsonl_with_recovery(
    path,
    quarantine_dir,
    *,
    label: str = "ملف JSONL",
) -> Tuple[List[Dict], Optional[Dict]]:
    """قراءة JSONL مع استعادة آمنة — يعيد (الصفوف، تقرير الاستعادة أو None).

    حالتا التلف:
    - **سطر أخير مبتور** (أثر انقطاع كتابة): تُحجز نسخة الأصل في quarantine_dir
      ثم يُعاد كتابة الملف دونه (ذرّيًا) وتُعاد صفوفه — الاسترداد صامت للقارئ
      لكنه موثق بالنسخة المحجوزة وسجل الاستعادة.
    - **تلف في وسط الملف**: تُحجز نسخة الأصل ثم يُرفع FileCorruptionError —
      لا إسقاط صامت لبيانات أبدًا؛ الحسم بيد المالك من النسخة المحجوزة.
    """
    path = Path(path)
    quarantine = Path(quarantine_dir)
    if not path.exists():
        return [], None

    raw = path.read_bytes()
    # ملف فارغ أو لا ينتهي بسطر جديد: أسطره كما هي (قد يكون السطر الأخير مبتورًا)
    lines = raw.split(b"\n")
    # split يترك عنصرًا أخيرًا فارغًا عندما ينتهي الملف بـ \\n — طبيعي.
    rows: List[Dict] = []
    bad_index: Optional[int] = None
    bad_reason: str = ""
    for i, raw_line in enumerate(lines):
        if not raw_line.strip():
            continue
        try:
            text = raw_line.decode("utf-8")
            rows.append(json.loads(text))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            bad_index = i
            bad_reason = f"{type(exc).__name__}: {exc}"
            break

    if bad_index is None:
        return rows, None

    trailing_only = all(not seg.strip() for seg in lines[bad_index + 1 :])
    if not trailing_only:
        # تلف في الوسط — لا استعادة صامتة: احجز النسخة وارفع الخطأ.
        backup = _quarantine_copy(path, quarantine)
        raise FileCorruptionError(
            f"{label}: تلف في وسط الملف عند السطر {bad_index + 1} ({bad_reason}) — "
            f"حُجزت نسخة الأصل في {backup} ولا يُسقط أي سجل صمتًا؛ "
            "المراجعة والحسم بيد المالك."
        )

    # سطر أخير مبتور (انقطاع كتابة): احجز النسخة ثم أعد الكتابة دونه.
    backup = _quarantine_copy(path, quarantine)
    kept = raw[: raw.rfind(b"\n", 0, len(raw))] if b"\n" in raw else b""
    # احتفظ بالنص حتى آخر سطر مكتمل فقط
    complete = b"\n".join(lines[:bad_index])
    if complete and not complete.endswith(b"\n"):
        complete += b"\n"
    atomic_write_bytes(path, complete if complete else b"")
    recovery = {
        "kind": "trailing_partial_dropped",
        "dropped_line": lines[bad_index].decode("utf-8", errors="replace")[:200],
        "reason": bad_reason,
        "quarantine_backup": str(backup),
    }
    return rows, recovery


def quarantine_copy(path: Path, quarantine_dir: Path) -> Path:
    """حجز نسخة أصل من ملف تالف/مبتور — دليل الاستعادة يوثق كل حجز."""
    quarantine_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S-%f")[:-3] + "Z"
    backup = quarantine_dir / f"{path.name}.corrupt-{stamp}"
    shutil.copy2(path, backup)
    return backup


# اسم داخلي قديم (خاصة الوحدة)
_quarantine_copy = quarantine_copy


def append_recovery_note(store_root, note: Dict) -> None:
    """سجل استعادة للتدقيق: كل حدث استعادة/حجز يوثق بطابعه UTC داخل القفل."""
    note = {"recorded_at": utc_now_iso(), **note}
    lock = FileLock(Path(store_root) / "recovery.lock")
    with lock:
        atomic_append_line(Path(store_root) / "recovery.log", canonical_json(note))
