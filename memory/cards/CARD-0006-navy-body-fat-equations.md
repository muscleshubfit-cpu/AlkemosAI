---
id: CARD-0006
title: معادلتا البحرية الأمريكية لدهن الجسم (Hodgdon–Beckett 1984)
classification: حسابات المنصة
entity: حساب/دهن الجسم (معادلتا البحرية)
version: v1.0
status: معتمدة
last_reviewed: 2026-11-22 (UTC)
supersedes: —
superseded_by: —
contradicts: []
source: alkemos-aws@32b6387:src/lib/content/body-fat-calculator.ts — اطلاع 2026-11-22 (UTC)
approved_via: G-K 2026-11-22 (UTC)
---

<div dir="rtl" align="right">

## الحقائق (عربية أساسًا + المصطلح الإنجليزي عند اللزوم)

- دهن الجسم يحسب بمعادلتي البحرية الأمريكية (US Navy — Hodgdon–Beckett 1984) من قياسات بالسنتيمتر.
- للرجال: 495 ÷ (1.0324 − 0.19077×log10(الخصر−الرقبة) + 0.15456×log10(الطول)) − 450.
- للنساء: 495 ÷ (1.29579 − 0.35004×log10(الخصر+الورك−الرقبة) + 0.22100×log10(الطول)) − 450.
- هامش الدقة الموثق في المصدر: انحراف 3–4 نقاط مئوية عن قياس DEXA المرجعي.

**EN:**

- Body fat uses the US Navy equations (Hodgdon-Beckett 1984) with measurements in centimeters.
- Men: 495 / (1.0324 - 0.19077*log10(waist-neck) + 0.15456*log10(height)) - 450.
- Women: 495 / (1.29579 - 0.35004*log10(waist+hip-neck) + 0.22100*log10(height)) - 450.
- Documented accuracy band: 3-4 percentage points vs DEXA.

## الأصل الكامل (provenance)

- **المنبع:** مستودع alkemos-aws العام (المصدر الأساسي — ADR-0012) على الالتزام `32b63874c2a2488b39bf449d83539fc930fe05a5` عبر raw.githubusercontent قراءة-فقط بلا مفاتيح (R-35).
- **ما استُشهد به:** المعادلتان الحرفيتان وهامش الدقة الموثق في ترويسة body-fat-calculator.ts.
- **الحقوق:** المصدر أصل مملوك لـAlkemos (مسجل في `references/data-rights.md` §2)؛ وهذه البطاقة «فارق مُتعلم مملوك» (data-rights §1) — إعادة بنائها حتمية عبر `scripts/gk_build_cards.py`.
- **تاريخ الاطلاع:** 2026-11-22 (UTC) · **الاعتماد:** G-K 2026-11-22 (UTC) (بوابة G-K — ADR-0017).

</div>
