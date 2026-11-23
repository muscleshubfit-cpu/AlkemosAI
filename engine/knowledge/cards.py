#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""تحميل بطاقات المعرفة المعتمدة من memory/cards/ (المستوى ب).

الصيغة قائمة على الواجهة الأمامية YAML مبسطة + جسم Markdown (بطاقات G-K
المعتمدة عبر البوابة — memory/README قاعدة 6). لا تُفهرس إلا البطاقات
التي حالتها «معتمدة» — المسودات والمشطوبة ليست معرفة.
"""
from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional

APPROVED_STATUS = "معتمدة"


def _parse_frontmatter(text: str) -> Dict[str, str]:
    """تحليل واجهة YAML المبسطة (مفتاح: قيمة — سطر لكل مفتاح)."""
    meta: Dict[str, str] = {}
    for line in text.splitlines():
        if not line.strip() or line.strip().startswith("#"):
            continue
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        key = key.strip()
        if key and not key.startswith("-"):
            meta[key] = value.strip()
    return meta


def load_cards(cards_dir: str | Path, approved_only: bool = True) -> List[Dict]:
    """تحميل كل البطاقات مرتبة بمعرفها — كل بطاقة تحمل نصها الكامل (للفهرسة والاستشهاد).

    الحقل status يجب أن يكون «معتمدة» (بوابة G-K عبرتها) لتدخل الفهرس —
    النتيجة حتمية: نفس الملفات = نفس القائمة بنفس الترتيب.
    """
    directory = Path(cards_dir)
    cards: List[Dict] = []
    for path in sorted(directory.glob("CARD-*.md")):
        raw = path.read_text(encoding="utf-8")
        meta: Dict[str, str] = {}
        body = raw
        if raw.startswith("---"):
            parts = raw.split("\n---", 2)
            if len(parts) >= 2:
                meta = _parse_frontmatter(parts[0][3:])
                body = parts[1].lstrip("-").lstrip("\n") if len(parts) == 2 else parts[2]
        card = {
            "id": meta.get("id", path.stem),
            "title": meta.get("title", path.stem),
            "classification": meta.get("classification", ""),
            "version": meta.get("version", ""),
            "status": meta.get("status", ""),
            "last_reviewed": meta.get("last_reviewed", ""),
            "source": meta.get("source", ""),
            "approved_via": meta.get("approved_via", ""),
            "contradicts": meta.get("contradicts", "[]"),
            "text": body,
            "path": str(path),
        }
        if approved_only and card["status"] != APPROVED_STATUS:
            continue
        cards.append(card)
    return cards


def fact_lines(card: Dict) -> List[str]:
    """أسطر الحقائق (النقطية) من جسم البطاقة — AR ثم EN — لبناء المقتطفات."""
    lines: List[str] = []
    for line in card["text"].splitlines():
        s = line.strip()
        if s.startswith("- ") and len(s) > 4:
            lines.append(s[2:].strip())
    return lines
