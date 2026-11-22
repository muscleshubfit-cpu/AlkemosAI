---
id: CARD-0013
title: دروع سلامة EVO: قانون YMYL وإبعاد إشارات الأزمات عن النموذج
classification: EVO/السلامة
entity: EVO/دروع السلامة (YMYL)
version: v1.0
status: معتمدة
last_reviewed: 2026-11-22 (UTC)
supersedes: —
superseded_by: —
contradicts: []
source: alkemos-aws@32b6387:src/lib/evo-safety.ts — اطلاع 2026-11-22 (UTC)
approved_via: G-K 2026-11-22 (UTC)
---

<div dir="rtl" align="right">

## الحقائق (عربية أساسًا + المصطلح الإنجليزي عند اللزوم)

- قانون YMYL: منصة Alkemos منصة صحة/لياقة — رسائل إيذاء الذات وإشارات اضطرابات الأكل لا تصل إلى نموذج اللغة أبدًا؛ تحصل على رد ثابت دافئ يحيل إلى مساعدة مهنية.
- الدرع أخلاقي ودرع ضد الهلوسة معًا: النموذج لا «يدرّب» أزمة أبدًا.
- الدقة العالية قبل الاستدعاء: كل نمط يجب أن يذكر الذات («نفسي»/myself/my life) أو سلوك اضطراب أكل ملموس؛ ومبالغات الجيم («التمرين ده قتلني») لا تُفعّل الدروع عمدًا.
- الصيام (والصيام المتقطع) موضوع لياقة مشروع — غير مدرج في قائمة اضطرابات الأكل عمدًا.
- المطابقة العربية تسبقها تسوية إملائية: إزالة التشكيل والتطويل وتوحيد الألف والياء والتاء المربوطة.

**EN:**

- YMYL law: Alkemos is a health/fitness platform - self-harm and eating-disorder signals must NEVER reach an LLM; they get a static, warm, professional-help redirect.
- This is both an ethics requirement and a hallucination firewall: the model must never coach a crisis.
- High precision over recall: every pattern names the SELF or a concrete ED behavior; gym hyperbole must not fire.
- Fasting is a LEGITIMATE fitness topic - deliberately absent from the ED list.
- Arabic normalization precedes matching: diacritics/tatweel stripped, alef/yaa/taa-marbouta unified.

## الأصل الكامل (provenance)

- **المنبع:** مستودع alkemos-aws العام (المصدر الأساسي — ADR-0012) على الالتزام `32b63874c2a2488b39bf449d83539fc930fe05a5` عبر raw.githubusercontent قراءة-فقط بلا مفاتيح (R-35).
- **ما استُشهد به:** قوانين التصميم الموثقة في ترويسة evo-safety.ts وعائلات الأنماط.
- **الحقوق:** المصدر أصل مملوك لـAlkemos (مسجل في `references/data-rights.md` §2)؛ وهذه البطاقة «فارق مُتعلم مملوك» (data-rights §1) — إعادة بنائها حتمية عبر `scripts/gk_build_cards.py`.
- **تاريخ الاطلاع:** 2026-11-22 (UTC) · **الاعتماد:** G-K 2026-11-22 (UTC) (بوابة G-K — ADR-0017).

</div>
