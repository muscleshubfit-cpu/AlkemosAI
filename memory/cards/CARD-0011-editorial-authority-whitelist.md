---
id: CARD-0011
title: دستور التحرير: الجهات العلمية الـ14 البيضاء ونطاق FAQ وقانون المرساة
classification: دستور التحرير
entity: تحرير/الجهات العلمية البيضاء وقواعد المحتوى
version: v1.0
status: معتمدة
last_reviewed: 2026-11-22 (UTC)
supersedes: —
superseded_by: —
contradicts: []
source: alkemos-aws@32b6387:src/lib/blog-editorial-law.ts — اطلاع 2026-11-22 (UTC)
approved_via: G-K 2026-11-22 (UTC)
---

<div dir="rtl" align="right">

## الحقائق (عربية أساسًا + المصطلح الإنجليزي عند اللزوم)

- الدستور يسرد 14 جهة علمية بيضاء للتذييل الخارجي: who.int · ncbi.nlm.nih.gov · pubmed.ncbi.nlm.nih.gov · ods.od.nih.gov · nccih.nih.gov · cdc.gov · mayoclinic.org · acsm.org · issn-online.org · nsca.com · health.gov · nasm.org · acefitness.org · eatright.org.
- نطاق الأسئلة الشائعة (FAQ) في مقالات المدونة: 4 إلى 7 أسئلة.
- قانون نص المرساة (anchor grammar law): كل نص مرساة عبارة طبيعية قصيرة تُقرأ نحويًا داخل جملتها — وهو قانون ملزم ببوابة تحقق حتمية.

**EN:**

- EDITORIAL_AUTHORITY_DOMAINS whitelists 14 authority domains: who.int, ncbi.nlm.nih.gov, pubmed.ncbi.nlm.nih.gov, ods.od.nih.gov, nccih.nih.gov, cdc.gov, mayoclinic.org, acsm.org, issn-online.org, nsca.com, health.gov, nasm.org, acefitness.org, eatright.org.
- EDITORIAL_FAQ_COUNT_RANGE = min 4, max 7.
- Anchor grammar law: every anchor text MUST be a short natural phrase that reads grammatically inside its sentence - enforced by a deterministic gate.

## الأصل الكامل (provenance)

- **المنبع:** مستودع alkemos-aws العام (المصدر الأساسي — ADR-0012) على الالتزام `32b63874c2a2488b39bf449d83539fc930fe05a5` عبر raw.githubusercontent قراءة-فقط بلا مفاتيح (R-35).
- **ما استُشهد به:** EDITORIAL_AUTHORITY_DOMAINS وEDITORIAL_FAQ_COUNT_RANGE وقانون نص المرساة في blog-editorial-law.ts.
- **الحقوق:** المصدر أصل مملوك لـAlkemos (مسجل في `references/data-rights.md` §2)؛ وهذه البطاقة «فارق مُتعلم مملوك» (data-rights §1) — إعادة بنائها حتمية عبر `scripts/gk_build_cards.py`.
- **تاريخ الاطلاع:** 2026-11-22 (UTC) · **الاعتماد:** G-K 2026-11-22 (UTC) (بوابة G-K — ADR-0017).

</div>
