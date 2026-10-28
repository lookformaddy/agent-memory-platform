"""Redaction of secret- and PII-like patterns from stored text.

Runs at write time (the service redacts before storing), so raw secrets never
persist in episodic records or facts. Patterns are generic and synthetic-data
safe: they match shapes, not any real credential.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

# (label, compiled pattern, replacement)
_PATTERNS: list[tuple[str, re.Pattern[str], str]] = [
    ("bearer_token", re.compile(r"Bearer\s+[A-Za-z0-9._\-~+/=]+"), "Bearer [REDACTED]"),
    ("labelled_secret", re.compile(r"(?i)(api[_-]?key|access[_-]?token|password|secret)\s*[:=]\s*\S+"),
     r"\1=[REDACTED]"),
    ("sk_token", re.compile(r"sk-[A-Za-z0-9]{16,}"), "[REDACTED]"),
    ("aws_key", re.compile(r"AKIA[0-9A-Z]{16}"), "[REDACTED]"),
    ("ssn", re.compile(r"\b\d{3}-\d{2}-\d{4}\b"), "[REDACTED-SSN]"),
    ("card", re.compile(r"\b\d{4}[- ]\d{4}[- ]\d{4}[- ]\d{4}\b"), "[REDACTED-CARD]"),
    ("email", re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"), "[REDACTED-EMAIL]"),
    ("phone", re.compile(r"\b\+?1?[- ]?\(?\d{3}\)?[- ]\d{3}[- ]\d{4}\b"), "[REDACTED-PHONE]"),
]


@dataclass
class RedactionResult:
    text: str
    redacted_kinds: list[str]


def redact(text: str) -> RedactionResult:
    """Return the text with secret/PII-like patterns replaced, plus kinds found."""
    kinds: list[str] = []
    out = text
    for label, pattern, replacement in _PATTERNS:
        out, n = pattern.subn(replacement, out)
        if n:
            kinds.append(label)
    return RedactionResult(text=out, redacted_kinds=kinds)


def contains_secret_like(text: str) -> bool:
    return any(p.search(text) for _, p, _ in _PATTERNS)
