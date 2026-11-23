#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""اختبارات المستوى ب — تحميل البطاقات + فهرس BM25 المشتق + المسترجع الموثق.

القوانين تحت الاختبار:
- لا تُفهرس إلا البطاقات المعتمدة (بوابة G-K عبرتها) — المسودة ليست معرفة.
- إلزام الاستشهاد: كل مقتطف يحمل مصدره وتاريخ مراجعته (R-09 ضد الهلوسة).
- الفهرس مشتق حتمي: نفس الملفات = نفس الترتيب، وإعادة البناء بأمر واحد.
- أرضية الصدق: لا نتائج ذات درجة صفر — الضجيج لا يُقدَّم كمعرفة.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from engine.knowledge import cards as kcards  # noqa: E402
from engine.knowledge import index as kindex  # noqa: E402
from engine.knowledge import retriever  # noqa: E402

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CARDS_DIR = os.path.join(REPO_ROOT, "memory", "cards")


def main():
    results = []

    def check(name, cond, detail=""):
        results.append((name, bool(cond)))
        mark = "✓" if cond else "✗"
        print(f"  {mark} {name}" + (f" — {detail}" if (detail and not cond) else ""))

    # ── تحميل البطاقات الحقيقية ─────────────────────────────────────────────
    all_cards = kcards.load_cards(CARDS_DIR, approved_only=False)
    approved = kcards.load_cards(CARDS_DIR, approved_only=True)
    check("التحميل: 15 بطاقة معتمدة من memory/cards", len(approved) == 15, f"وجد {len(approved)}")
    check("التحميل: كلها حالة «معتمدة» عبر G-K", all(c["status"] == "معتمدة" for c in approved))
    check("التحميل: كل بطاقة بمصدر وتاريخ مراجعة موثقين", all(c["source"].strip() and c["last_reviewed"].strip() for c in approved))
    check("التحميل: ترتيب حتمي بالمعرف", [c["id"] for c in approved] == sorted(c["id"] for c in approved))
    check("التحميل: أسطر حقائق قابلة للاستخراج (AR/EN)", len(kcards.fact_lines(approved[0])) >= 3)

    # ── المُرمِّز المشترك مع طبقة الذاكرة ────────────────────────────────────
    toks = kindex.tokenize("معادلة Mifflin-St Jeor للأيض الأساسي")
    check("الترميز: ثنائي اللغة بتطبيع موحد", "mifflin" in toks and "st" in toks and "للايض" in toks)
    check("الترميز: الأرقام الهندية تصير لاتينية", "10" in kindex.tokenize("١٠ كيلو"))

    # ── BM25 حتمي ────────────────────────────────────────────────────────────
    docs = [
        {"id": "A", "text": "بروتين الكازين بيطء الامتصاص"},
        {"id": "B", "text": "معادلة ميفلين سان جيور للأيض الأساسي BMR"},
        {"id": "C", "text": "توزيع الماكروز 4 4 9 للسكريات والبروتين والدهون"},
    ]
    idx = kindex.Bm25Index(docs)
    top = idx.search("معادلة ميفلين للأيض", k=3)
    check("BM25: المطابقة العربية تجد المستند الصحيح أولًا", top and top[0][0] == "B")
    check("BM25: لا نتائج بلا مصطلح مشترك (أرضية الصدق)", idx.search("zzz qqq", k=3) == [])
    again = kindex.Bm25Index(docs).search("معادلة ميفلين للأيض", k=3)
    check("BM25: حتمية الترتيب عبر البناء", [t[0] for t in top] == [t[0] for t in again])

    # ── المسترجع فوق البطاقات الحقيقية ───────────────────────────────────────
    r = retriever.KnowledgeRetriever(CARDS_DIR)
    res = r.search("معادلة Mifflin-St Jeor للأيض الأساسي ومعاملات النشاط", k=3)
    check("الاسترجاع: استعلام عربي/إنجليزي يجد CARD-0001 أولًا", bool(res) and res[0]["card_id"] == "CARD-0001", f"الأول {res[0]['card_id'] if res else 'بلا'}")
    res = r.search("Mifflin St Jeor equation BMR activity factors", k=3)
    check("الاسترجاع: استعلام إنجليزي يجد CARD-0001", bool(res) and res[0]["card_id"] == "CARD-0001")
    res = r.search("الماء 35 مل لكل كيلوجرام وزن الجسم", k=3)
    check("الاسترجاع: بطاقة الماء CARD-0007", bool(res) and res[0]["card_id"] == "CARD-0007")
    check("الاسترجاع: إلزام الاستشهاد في كل مقتطف (المصدر + تاريخ المراجعة)", all(x["source"].strip() and x["last_reviewed"].strip() and x["card_id"].strip() for x in res))
    check("الاسترجاع: مقتطف غير فارغ لكل نتيجة", all(x["snippet"].strip() for x in res))
    check("الاسترجاع: لا نتائج للضجيج (بلا مصطلح تمييزي)", r.search("طائرة فضاء زحل المريخ", k=3) == [])
    first = [x["card_id"] for x in r.search("معادلة ميفلين", k=5)]
    second = [x["card_id"] for x in r.search("معادلة ميفلين", k=5)]
    check("الاسترجاع: حتمية كاملة (تشغيلان متطابقان)", first == second)
    check("الاسترجاع: إعادة الفهرسة من الملفات بأمر واحد", r.rebuild() == 15)

    passed = sum(1 for _, ok in results if ok)
    print(f"\n{passed}/{len(results)} اختبارًا ناجحًا")
    sys.exit(0 if passed == len(results) else 1)


if __name__ == "__main__":
    main()
