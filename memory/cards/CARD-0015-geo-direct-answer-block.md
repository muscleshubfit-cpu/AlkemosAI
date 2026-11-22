---
id: CARD-0015
title: نمط GEO لكتلة الجواب المباشر (40–60 كلمة بعد الواجهة + سطر المصادر)
classification: SEO/GEO/AEO
entity: SEO/كتلة الجواب المباشر GEO
version: v1.0
status: معتمدة
last_reviewed: 2026-11-22 (UTC)
supersedes: —
superseded_by: —
contradicts: []
source: alkemos-aws@32b6387:src/lib/evo-geo-answer.ts — اطلاع 2026-11-22 (UTC)
approved_via: G-K 2026-11-22 (UTC)
---

<div dir="rtl" align="right">

## الحقائق (عربية أساسًا + المصطلح الإنجليزي عند اللزوم)

- نمط الإجابة المباشرة لمحركات الذكاء التوليدي (GEO): كتلة جواب من 40 إلى 60 كلمة كأول قسم محتوى بعد الواجهة (hero) في الصفحة، مع سطر مصادر يوثق مصدر الأرقام — توليفة Yotpo/Princeton الموثقة.
- مثال إنتاجي: كتلة «هل EVO مجاني؟» ثنائية اللغة — 10 رسائل يوميًا مجانًا بلا تسجيل، والتوليد 4/8/8 شهريًا (بريميوم/برو/تدريب)، وحصة تبديلات موحدة 8 أو 16 شهريًا.
- كل رقم في الكتلة موثق من مصدر التسعير/الحصص الوحيد (memberships.ts) — أعيد التحقق 2026-11-20.
- الترتيب يرث موقع السؤال من الأسئلة الشائعة القائمة بلغتيه، مثبتًا بعرافة (canary) تمنع انحداره.

**EN:**

- The GEO direct-answer pattern: a 40-60 word answer block as the FIRST content section after the hero, plus the sources line (the Yotpo/Princeton synthesis).
- Production example: the bilingual "Is EVO free?" block - 10 messages a day free with no signup; generations 4/8/8 monthly (Premium/Pro/Coaching); ONE unified swap quota 8 or 16 a month.
- Every number is verified against src/lib/memberships.ts (the single pricing/quota source - re-verified 2026-11-20).
- The existing FAQ already leads with this question in both languages, order pinned by a canary so it can never regress.

## الأصل الكامل (provenance)

- **المنبع:** مستودع alkemos-aws العام (المصدر الأساسي — ADR-0012) على الالتزام `32b63874c2a2488b39bf449d83539fc930fe05a5` عبر raw.githubusercontent قراءة-فقط بلا مفاتيح (R-35).
- **ما استُشهد به:** كتلة EVO_GEO_BLOCK وقوانين ترويستها في evo-geo-answer.ts.
- **الحقوق:** المصدر أصل مملوك لـAlkemos (مسجل في `references/data-rights.md` §2)؛ وهذه البطاقة «فارق مُتعلم مملوك» (data-rights §1) — إعادة بنائها حتمية عبر `scripts/gk_build_cards.py`.
- **تاريخ الاطلاع:** 2026-11-22 (UTC) · **الاعتماد:** G-K 2026-11-22 (UTC) (بوابة G-K — ADR-0017).

</div>
