#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""مسح أسرار إلزامي قبل كل push (SECURITY §4) — فوق الملفات المراحل في git."""
import re
import subprocess
import sys

PATTERNS = {
    "GitHub token": re.compile(r"gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}"),
    "Supabase secret": re.compile(r"sb_secret_[A-Za-z0-9_\-]{20,}"),
    "Cloudflare token": re.compile(r"cfut_[A-Za-z0-9_\-]{20,}|cfk_[A-Za-z0-9_\-]{20,}"),
    "AWS access key": re.compile(r"AKIA[0-9A-Z]{16}"),
    "AWS secret key": re.compile(r"(?i)aws(.{0,20})?['\"][0-9a-zA-Z/+]{40}['\"]"),
    "Private key block": re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    "JWT": re.compile(r"eyJ[A-Za-z0-9_\-]{20,}\.[A-Za-z0-9_\-]{20,}\.[A-Za-z0-9_\-]{20,}"),
    "Generic password assignment": re.compile(r"(?i)(password|passwd|secret|api_key|apikey)\s*[=:]\s*['\"][^'\"]{8,}['\"]"),
}


def main():
    files = subprocess.run(
        ["git", "diff", "--cached", "--name-only"], capture_output=True, text=True, check=True
    ).stdout.split()
    hits = []
    for path in files:
        try:
            with open(path, encoding="utf-8") as fh:
                for lineno, line in enumerate(fh, 1):
                    for label, rx in PATTERNS.items():
                        if rx.search(line):
                            hits.append(f"{path}:{lineno} [{label}]")
        except (OSError, UnicodeDecodeError):
            continue
    if hits:
        print("مسح الأسرار: فشل — إصابات:")
        for h in hits:
            print("  " + h)
        sys.exit(1)
    print(f"مسح الأسرار: نظيف — {len(files)} ملفًا مرحّلًا، صفر إصابات.")


if __name__ == "__main__":
    main()
