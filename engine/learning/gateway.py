#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""بوابة اعتماد الأمثلة قبل التدريب (G-EX) — الخطة §6: الشروط الستة + توقيع المالك.

لا مثال يعبر إلا باكتمال الشروط الستة مجتمعة وتوقيع مالك — والمخرجات:
- المقبول → datasets/approved/EX-xxxx بإصدار وبصمة sha256 وأصل كامل
  + قيد تعلم جاهز للملك في learning-log (القبول ذاته يوثقه المالك).
- المرفوض → memory/archive بسببه الموثق — لا حذف أبدًا.

الشروط (مطبقة آليًا ما أمكن، والبقية إثبات موثق من المتصل):
1. أصل موثق: ملف مصدر موجود + SHA256 مطابق حرفيًا + تاريخ اطلاع صالح تقويميًا.
2. تجريد هوية مكتمل: فحص قائمة الحرمان الآلي صفر الإصابات + مراجعة بشرية موثقة
   (المراجع والتاريخ) — إزالة الاسم وحدها لا تساوي تجريدًا مكتملًا.
3. أساس استخدام مصرح: موافقة العميل الصريحة الموثقة (opt-in يحترم الانسحاب)
   أو أساس موثق يقرره المالك ويُقيد في learning-log — وسحب الموافقة يمنع
   استخدام المثال في أي دفعة تالية (check_withdrawal).
4. جودة المصدر: تغذية راجعة إيجابية أو اجتياز بوابات السلامة/التقييم
   (قاضٍ 0–10 بعتبة قابلة للضبط — الافتراضي 7، وتعديلها بقرار مالك موثق).
5. لا تعارض: لا تكرار لنفس الأصل المعتمد سابقًا + إقرار حل التعارضات مع
   بطاقات المستوى ب (بصيغة conflicts_resolved موثقة من المراجعة).
6. تصنيف استخدام واحد لا يُعدل بعد الاعتماد: تدريب فقط / تدريب+استرجاع / استرجاع فقط.

هذه البوابة كود حاكم فقط — لا تفتح أي تدفق بيانات من تلقاء نفسها: مصادر
المستوى ج لا تُقرأ هنا، والمرشح يصل من المتصل مكتمل الإثباتات.
"""
from __future__ import annotations

import hashlib
import json
import re
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

from . import denier

USAGE_TRAINING_ONLY = "training_only"
USAGE_TRAINING_RETRIEVAL = "training_retrieval"
USAGE_RETRIEVAL_ONLY = "retrieval_only"
USAGE_CLASSES = (USAGE_TRAINING_ONLY, USAGE_TRAINING_RETRIEVAL, USAGE_RETRIEVAL_ONLY)

BASIS_CLIENT_CONSENT = "client_consent"
BASIS_OWNER_DECIDED = "owner_basis"
BASIS_KINDS = (BASIS_CLIENT_CONSENT, BASIS_OWNER_DECIDED)

QUALITY_POSITIVE_FEEDBACK = "positive_feedback"
QUALITY_SAFETY_PASS = "safety_pass"
QUALITY_JUDGE_SCORE = "judge_score"
QUALITY_KINDS = (QUALITY_POSITIVE_FEEDBACK, QUALITY_SAFETY_PASS, QUALITY_JUDGE_SCORE)

GATE_JUDGE_MIN_DEFAULT = 7  # قاضٍ 0–10 — قابل للضبط بقرار مالك موثق فقط

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


class GatewayError(RuntimeError):
    """رفض البوابة — الرسالة تحمل الشروط غير المكتملة (توثق في الأرشيف)."""


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _valid_calendar_date(value: str) -> bool:
    """تاريخ صالح تقويميًا (YYYY-MM-DD) — نفس روح فحوص G-K في LEARN-002/003."""
    if not isinstance(value, str) or not _DATE_RE.match(value.strip()):
        return False
    try:
        date.fromisoformat(value.strip())
        return True
    except ValueError:
        return False


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class ExampleGateway:
    """بوابة G-EX فوق أدلة معتمدة/أرشيف — كل مسار يُدار خارج شجرة git أو داخل
    المستودع حسب قرار المالك عند التفعيل الحقيقي؛ الاختبارات تستخدم أدلة مؤقتة.
    """

    def __init__(
        self,
        approved_dir: str | Path,
        archive_dir: str | Path,
        judge_min: int = GATE_JUDGE_MIN_DEFAULT,
    ) -> None:
        self.approved_dir = Path(approved_dir)
        self.archive_dir = Path(archive_dir)
        self.approved_dir.mkdir(parents=True, exist_ok=True)
        self.archive_dir.mkdir(parents=True, exist_ok=True)
        self.judge_min = judge_min

    # ── الشروط الستة ─────────────────────────────────────────────────────────
    def check_origin(self, cand: Dict) -> List[str]:
        errors: List[str] = []
        origin = cand.get("origin") or {}
        path_raw = origin.get("path")
        if not path_raw:
            return ["شرط 1 (أصل موثق): مسار الملف المصدر مفقود"]
        path = Path(path_raw)
        if not path.is_file():
            return [f"شرط 1 (أصل موثق): الملف المصدر غير موجود: {path_raw}"]
        actual = _sha256_file(path)
        if actual != origin.get("sha256"):
            errors.append("شرط 1 (أصل موثق): بصمة SHA256 لا تطابق الملف المصدر")
        if not _valid_calendar_date(origin.get("inspected_at", "")):
            errors.append("شرط 1 (أصل موثق): تاريخ الاطلاع غير صالح تقويميًا (YYYY-MM-DD)")
        return errors

    def check_deid(self, cand: Dict) -> List[str]:
        errors: List[str] = []
        scan = denier.scan_text(cand.get("content", ""))
        if not scan["passed"]:
            found = "؛ ".join(f"{h['kind_ar']}: {h['match']}" for h in scan["hits"][:5])
            errors.append(f"شرط 2 (تجريد الهوية): فحص قائمة الحرمان الآلي وجد {len(scan['hits'])} إصابة — {found}")
        deid = cand.get("deid") or {}
        if not deid.get("human_review_passed"):
            errors.append("شرط 2 (تجريد الهوية): المراجعة البشرية غير موثقة الاعتماد")
        elif not (deid.get("reviewer") or "").strip():
            errors.append("شرط 2 (تجريد الهوية): المراجعة البشرية بلا مراجع موثق")
        elif not _valid_calendar_date(deid.get("reviewed_at", "")):
            errors.append("شرط 2 (تجريد الهوية): تاريخ المراجعة غير صالح تقويميًا")
        return errors

    def check_basis(self, cand: Dict) -> List[str]:
        errors: List[str] = []
        basis = cand.get("basis") or {}
        kind = basis.get("kind")
        if kind not in BASIS_KINDS:
            return [f"شرط 3 (الأساس المصرح): النوع يجب أن يكون {BASIS_KINDS}"]
        if not (basis.get("reference") or "").strip():
            errors.append("شرط 3 (الأساس المصرح): مرجع الموافقة/الأساس مفقود")
        if basis.get("withdrawn"):
            errors.append("شرط 3 (الأساس المصرح): الأساس مسحوب — المثال ممنوع من أي دفعة تالية")
        return errors

    def check_quality(self, cand: Dict) -> List[str]:
        q = cand.get("quality") or {}
        kind = q.get("kind")
        if kind not in QUALITY_KINDS:
            return [f"شرط 4 (جودة المصدر): يجب أن يكون {QUALITY_KINDS}"]
        if kind == QUALITY_POSITIVE_FEEDBACK and not q.get("positive"):
            return ["شرط 4 (جودة المصدر): التغذية الراجعة ليست إيجابية"]
        if kind == QUALITY_SAFETY_PASS and not q.get("passed"):
            return ["شرط 4 (جودة المصدر): بوابات السلامة لم تُجتز"]
        if kind == QUALITY_JUDGE_SCORE:
            score = q.get("score")
            if not isinstance(score, (int, float)) or not (0 <= score <= 10):
                return ["شرط 4 (جودة المصدر): درجة القاضي خارج النطاق 0–10"]
            if score < self.judge_min:
                return [f"شرط 4 (جودة المصدر): درجة القاضي {score} دون العتبة {self.judge_min}"]
        return []

    def check_conflict(self, cand: Dict) -> List[str]:
        errors: List[str] = []
        origin = cand.get("origin") or {}
        for existing in self._load_approved():
            ex_origin = existing.get("origin") or {}
            if ex_origin.get("path") == origin.get("path") and ex_origin.get("sha256") == origin.get("sha256"):
                errors.append(
                    f"شرط 5 (لا تعارض): الأصل نفسه معتمد سابقًا في {existing['example_id']}"
                )
                break
        if cand.get("conflicts_resolved") is not True:
            errors.append("شرط 5 (لا تعارض): إقرار حل التعارضات مع بطاقات المستوى ب غير موثق")
        return errors

    def check_usage(self, cand: Dict) -> List[str]:
        if cand.get("usage") not in USAGE_CLASSES:
            return [f"شرط 6 (تصنيف الاستخدام): يجب أن يكون {USAGE_CLASSES}"]
        return []

    def run_checks(self, cand: Dict) -> Dict:
        """كل الشروط الستة — يعيد {passed, errors} (passed فقط عند صفر أخطاء)."""
        errors: List[str] = []
        errors += self.check_origin(cand)
        errors += self.check_deid(cand)
        errors += self.check_basis(cand)
        errors += self.check_quality(cand)
        errors += self.check_conflict(cand)
        errors += self.check_usage(cand)
        return {"passed": len(errors) == 0, "errors": errors}

    # ── الدورة: تقديم / اعتماد / رفض ────────────────────────────────────────
    def submit(self, cand: Dict) -> Dict:
        """تقديم مرشح — الفحوص الآلية فقط، بلا أي كتابة (لا اعتماد تلقائي أبدًا)."""
        return self.run_checks(cand)

    def approve(self, cand: Dict, owner_signature: Dict) -> Dict:
        """اعتماد مثال — يتطلب الشروط الستة + توقيع المالك الموثق.

        يكتب EX-xxxx في دليل المعتمد بإصدار وبصمة وأصل كامل، ويعيد قيد التعلم
        الجاهز (توقيع الاعتماد النهائي وإدراج القيد في learning-log على المالك).
        تصنيف الاستخدام يُختم مرة واحدة في الملف المعتمد ولا يُعدل بعدها.
        """
        report = self.run_checks(cand)
        if not report["passed"]:
            raise GatewayError("بوابة G-EX رفضت الاعتماد — " + " | ".join(report["errors"]))
        if not owner_signature or (owner_signature.get("signer") or "").strip() != "owner":
            raise GatewayError("الاعتماد يتطلب توقيع المالك (signer=owner) — لا اعتماد بلا توقيع")
        if not (owner_signature.get("decision_ref") or "").strip():
            raise GatewayError("التوقيع بلا مرجع قرار موثق")
        if not _valid_calendar_date(owner_signature.get("signed_at", "")):
            raise GatewayError("تاريخ التوقيع غير صالح تقويميًا (YYYY-MM-DD)")

        seq = len(self._load_approved()) + 1
        example_id = f"EX-{seq:04d}"
        record = {
            "example_id": example_id,
            "version": "v1.0",
            "content": cand["content"],
            "content_sha256": _sha256_text(cand["content"]),
            "origin": cand["origin"],
            "basis": cand["basis"],
            "quality": cand["quality"],
            "usage": cand["usage"],
            "deid": cand.get("deid"),
            "conflicts_resolved": cand.get("conflicts_resolved"),
            "owner_signature": {
                "signer": "owner",
                "signed_at": owner_signature["signed_at"],
                "decision_ref": owner_signature["decision_ref"],
            },
            "created_at": utc_now_iso(),
        }
        out_path = self.approved_dir / f"{example_id}.json"
        out_path.write_text(
            json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        return {"example_id": example_id, "record": record, "log_entry": self._log_entry(record)}

    def reject(self, cand: Dict, reason: str) -> Dict:
        """رفض مؤرشف بسبب موثق — لا حذف أبدًا (المرفوض يبقى أثرًا قابلاً للمراجعة)."""
        if not (reason or "").strip():
            raise GatewayError("الرفض يتطلب سببًا موثقًا")
        report = self.run_checks(cand)
        seq = len(list(self.archive_dir.glob("REJ-*.json"))) + 1
        record = {
            "rejection_id": f"REJ-{seq:04d}",
            "reason": reason.strip(),
            "checks_report": report,
            "candidate_summary": {
                "origin": cand.get("origin"),
                "usage": cand.get("usage"),
                "basis_kind": (cand.get("basis") or {}).get("kind"),
            },
            "created_at": utc_now_iso(),
        }
        out_path = self.archive_dir / f"REJ-{seq:04d}.json"
        out_path.write_text(
            json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        return record

    # ── الانسحاب (شرط 3: السحب يمنع أي دفعة تالية) ──────────────────────────
    def check_withdrawal(self, basis_reference: str) -> List[str]:
        """أمثلة معتمدة بُنيت على أساس مُسحب — تُستبعد من أي دفعة تدريب تالية."""
        affected = []
        for existing in self._load_approved():
            basis = existing.get("basis") or {}
            if basis.get("reference") == basis_reference:
                affected.append(existing["example_id"])
        return affected

    # ── أدوات داخلية ─────────────────────────────────────────────────────────
    def _load_approved(self) -> List[Dict]:
        records = []
        for path in sorted(self.approved_dir.glob("EX-*.json")):
            try:
                records.append(json.loads(path.read_text(encoding="utf-8")))
            except json.JSONDecodeError:
                continue
        return records

    @staticmethod
    def _log_entry(record: Dict) -> str:
        """قيد تعلم بصيغة learning-log الإلزامية — يدرجه المالك عند الاعتماد."""
        return (
            "---\n"
            f"entry: LEARN-<تسلسلي>\n"
            f"date: <YYYY-MM-DD> (UTC)\n"
            "kind: أوزان\n"
            "gate: G-EX (<تاريخ UTC>)\n"
            "---\n"
            f"- **المدخل:** مثال تدريب {record['example_id']} ({record['version']}) — "
            f"الأصل {record['origin'].get('path')} @ {record['origin'].get('sha256', '')[:12]}\n"
            f"- **القياس قبل/بعد:** بصمة المحتوى {record['content_sha256'][:12]}… · "
            f"الأساس {record['basis'].get('kind')} ({record['basis'].get('reference')})\n"
            "- **القرار:** قبول (توقيع المالك موثق في الملف)\n"
            f"- **ما أُضيف:** datasets/approved/{record['example_id']}.json — "
            f"تصنيف الاستخدام {record['usage']}\n"
            "- **ما رُفض ولماذا:** —\n"
        )
