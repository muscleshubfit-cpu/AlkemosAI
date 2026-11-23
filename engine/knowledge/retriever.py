#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""مسترجع المعرفة (عقد الواجهة §3): KnowledgeRetriever.search(query).

كل مقتطف يحمل مصدره وتاريخ مراجعته — إلزام الاستشهاد ضد الهلوسة (R-09 /
الخطة §3). المسترجع لا يعرف المحرك الذي سيستهلكه (قانون الاستقلالية §1).
"""
from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional

from .cards import fact_lines, load_cards
from .index import Bm25Index, tokenize


class KnowledgeRetriever:
    """استرجاع هجين المرحلة الأولى: BM25 فوق البطاقات المعتمدة.

    الطبقة الثانية (تضمين متجه مملوك متعدد اللغات) تُضاف فوق الملفات نفسها بعد
    قرار D-5 — الواجهة هنا لن تتغير (نفس التوقيع، نفس المخرجات الموثقة).
    """

    def __init__(self, cards_dir: str | Path) -> None:
        self.cards_dir = Path(cards_dir)
        self.cards: List[Dict] = load_cards(self.cards_dir, approved_only=True)
        self.by_id: Dict[str, Dict] = {c["id"]: c for c in self.cards}
        self.index = Bm25Index([{"id": c["id"], "text": c["text"]} for c in self.cards])

    def rebuild(self) -> int:
        """إعادة الفهرسة من الملفات بأمر واحد — إعادة البناء الحتمي (ADR-0009)."""
        self.cards = load_cards(self.cards_dir, approved_only=True)
        self.by_id = {c["id"]: c for c in self.cards}
        self.index = Bm25Index([{"id": c["id"], "text": c["text"]} for c in self.cards])
        return len(self.cards)

    def _snippet(self, card: Dict, query: str, max_lines: int = 2) -> str:
        """أفضل أسطر الحقائق مطابقةً للاستعلام (مقتطف موثق من جسم البطاقة)."""
        q_terms = set(tokenize(query))
        scored = []
        for line in fact_lines(card):
            terms = set(tokenize(line))
            overlap = len(q_terms & terms)
            scored.append((-overlap, line))
        scored.sort(key=lambda t: (t[0], t[1]))
        keep = [line for neg, line in scored[:max_lines] if neg < 0]
        if not keep:
            # لا سطر حقائق يطابق — خذ أول أسطر البطاقة (المقتطف يظل موثق المصدر).
            all_lines = fact_lines(card)
            keep = all_lines[:max_lines]
        return " · ".join(keep)

    def search(self, query: str, k: int = 5) -> List[Dict]:
        """مقتطفات معرفة من المستوى ب — كل مقتطف بمصدره وتاريخ مراجعته (إلزامي).

        يعيد فقط نتائج ذات درجة موجبة؛ الترتيب حتمي (درجة تنازليًا ثم معرفًا).
        """
        results: List[Dict] = []
        for card_id, score in self.index.search(query, k=k):
            card = self.by_id[card_id]
            results.append(
                {
                    "card_id": card_id,
                    "title": card["title"],
                    "classification": card["classification"],
                    "snippet": self._snippet(card, query),
                    "source": card["source"],
                    "last_reviewed": card["last_reviewed"],
                    "version": card["version"],
                    "score": round(score, 4),
                }
            )
        return results
