#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""فهرس BM25 مشتق فوق بطاقات المستوى ب — عربي/إنجليزي بتطبيع موحد.

القانون (الخطة §2-ب): الفهرس مشتق دائمًا من الملفات — هذا التنفيذ يعاد بناؤه
في الذاكرة من memory/cards/ عند كل إنشاء (تكلفة صفروبلا مخطط)، وطبقة التضمين
المتجه متعدد اللغات تُبنى فوق الملفات نفسها بعد قرار D-5 (اختيار النموذج) —
لا شيء هنا يعتمد على هوية أي نموذج أو مزود.

المُرمِّز يعيد استخدام normalize_for_memory (توحيد الإملاء العربي + الأرقام) —
نفس عائلة التطبيع التي تستخدمها ذاكرة العملاء ومجمّع التعلم، فتلتقي الطبقات
على مفاتيح واحدة.
"""
from __future__ import annotations

import math
from collections import Counter
from typing import Dict, List, Sequence, Tuple

from engine.memory import pure

K1 = 1.5
B = 0.75

# كلمات وقف بادئة (عربية + إنجليزية) — وظيفية عالية التكرار لا تحمل معنى تمييزيًا.
# البداية موثقة وقابلة للتوسيع بقياس دقة الاسترجاع (بطارية المرحلة 7 تقيس النهائية).
STOPWORDS = frozenset({
    # عربية
    "في", "من", "على", "الى", "إلى", "عن", "مع", "هذا", "هذه", "ذلك", "تلك",
    "التي", "الذي", "الذين", "ما", "لا", "لم", "لن", "قد", "كان", "كانت",
    "تكون", "هو", "هي", "هم", "انا", "انت", "نحن", "كل", "بعض", "بين", "عند",
    "حتى", "او", "أو", "ثم", "ايضا", "أيضا", "لكن", "بل", "غير", "سوف",
    "عندما", "حيث", "كما", "نعم", "عنده", "منها", "فيه", "بها", "له", "به",
    # إنجليزية
    "the", "a", "an", "and", "or", "of", "to", "in", "for", "on", "with",
    "by", "at", "from", "is", "are", "was", "were", "be", "been", "it", "its",
    "this", "that", "these", "those", "as", "not", "no",
})


def tokenize(text: str) -> List[str]:
    """ترميز ثنائي اللغة: تطبيع الذاكرة نفسه + حجب كلمات الوقف ثم التقسيم."""
    return [t for t in pure.normalize_for_memory(text).split() if t not in STOPWORDS]


class Bm25Index:
    """فهرس BM25 حتمي — نفس المستندات = نفس النتائج (ترتيب الأحفاد بالمعرف)."""

    def __init__(self, docs: Sequence[Dict]) -> None:
        """docs: قوائم {id, text} — كل مستند معرف بنصه الكامل."""
        self.doc_ids: List[str] = []
        self.term_freqs: List[Counter] = []
        self.doc_lens: List[int] = []
        self.df: Counter = Counter()
        for doc in docs:
            tokens = tokenize(doc["text"])
            tf = Counter(tokens)
            self.doc_ids.append(doc["id"])
            self.term_freqs.append(tf)
            self.doc_lens.append(len(tokens))
            for term in tf:
                self.df[term] += 1
        self.n = len(self.doc_ids)
        self.avgdl = (sum(self.doc_lens) / self.n) if self.n else 0.0

    def _idf(self, term: str) -> float:
        df = self.df.get(term, 0)
        if df == 0:
            return 0.0
        return math.log(1.0 + (self.n - df + 0.5) / (df + 0.5))

    def score(self, query: str, doc_index: int) -> float:
        tf = self.term_freqs[doc_index]
        dl = self.doc_lens[doc_index] or 1
        total = 0.0
        for term in tokenize(query):
            f = tf.get(term, 0)
            if f == 0:
                continue
            idf = self._idf(term)
            total += idf * (f * (K1 + 1.0)) / (f + K1 * (1.0 - B + B * dl / (self.avgdl or 1.0)))
        return total

    def search(self, query: str, k: int = 5) -> List[Tuple[str, float]]:
        """ترتيب تنازلي بالدرجة ثم تصاعديًا بالمعرف عند التساوي — حتمي دائمًا.

        المستندات ذات الدرجة صفر (لا مصطلح مشترك) لا تُعاد أبدًا —
        «لا نقدّم الضجيج كمعرفة» (أرضية الصدق).
        """
        scored: List[Tuple[str, float]] = []
        for i in range(self.n):
            s = self.score(query, i)
            if s > 0:
                scored.append((self.doc_ids[i], s))
        scored.sort(key=lambda t: (-t[1], t[0]))
        return scored[:k]
