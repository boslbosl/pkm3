"""Detection-first redaction (ARCHITECTURE §10).

MVP detects high-signal secrets and returns findings. It does not mutate raw
evidence; export policy decides whether to warn/mask/block.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from .models import CanonicalSession


@dataclass
class Finding:
    kind: str
    confidence: str  # low | medium | high
    excerpt: str
    message_seq: int


# (kind, confidence, compiled pattern)
_PATTERNS: list[tuple[str, str, re.Pattern[str]]] = [
    ("aws_access_key", "high", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("private_key", "high", re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |DSA |)PRIVATE KEY-----")),
    ("openai_key", "high", re.compile(r"\bsk-[A-Za-z0-9]{20,}\b")),
    ("github_token", "high", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}\b")),
    ("slack_token", "high", re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b")),
    (
        "db_url_with_creds",
        "high",
        re.compile(r"\b(?:postgres(?:ql)?|mysql|mongodb)(?:\+\w+)?://[^\s:@/]+:[^\s:@/]+@\S+"),
    ),
    (
        "credential_assignment",
        "medium",
        re.compile(
            r"(?i)\b(?:api[_-]?key|secret|token|password|passwd|access[_-]?key)\b\s*[=:]\s*['\"]?[A-Za-z0-9_\-]{12,}"
        ),
    ),
]


def _mask(text: str, start: int, end: int, pad: int = 12) -> str:
    lo = max(0, start - pad)
    hi = min(len(text), end + pad)
    snippet = text[lo:hi].replace("\n", " ")
    return snippet.strip()


def scan_text(text: str, message_seq: int) -> list[Finding]:
    findings: list[Finding] = []
    for kind, confidence, pat in _PATTERNS:
        for m in pat.finditer(text):
            findings.append(
                Finding(
                    kind=kind,
                    confidence=confidence,
                    excerpt=_mask(text, m.start(), m.end()),
                    message_seq=message_seq,
                )
            )
    return findings


def scan_session(session: CanonicalSession) -> list[Finding]:
    findings: list[Finding] = []
    for seq, msg in enumerate(session.messages):
        if msg.content:
            findings.extend(scan_text(msg.content, seq))
    return findings
