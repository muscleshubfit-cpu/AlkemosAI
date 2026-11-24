#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""سجل مزود المحاكاة داخل engine/identity — **بلا أي شبكة** (قانون المحرك).

- `static-test` — مزود محاكاة للاختبار والمحاكاة فقط (جدول رموز محلي).

مزودات الإنتاج (الاستعلام عند مصدر الحساب · JWKS بتوقيع غير متماثل) تعيش
خارج engine/ في `adapters/identity/` لأنها تلمس الشبكة — والمحرك قانونه
صفر استيراد شبكي (فحص الاستقلالية في scripts/test_engine_security.py §6).
"""
from .static import StaticProvider

__all__ = ["StaticProvider"]
