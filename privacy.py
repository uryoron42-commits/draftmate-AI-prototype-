"""PII redaction before text leaves the server, and restoration afterwards."""
import re

PATTERNS = [
    ("GSTIN", r"\b\d{2}[A-Z]{5}\d{4}[A-Z]\d[Z][A-Z\d]\b"),
    ("PAN", r"\b[A-Z]{5}\d{4}[A-Z]\b"),
    ("EMAIL", r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b"),
    ("AADHAAR", r"\b\d{4}\s?\d{4}\s?\d{4}\b"),
    ("PHONE", r"(?:\+91[\s-]?)?\b[6-9]\d{9}\b"),
]


def redact(text, terms=()):
    mapping, counters = {}, {}

    def put(kind, val):
        for tok, orig in mapping.items():
            if orig == val:
                return tok
        counters[kind] = counters.get(kind, 0) + 1
        tok = f"[{kind}_{counters[kind]}]"
        mapping[tok] = val
        return tok

    for t in sorted({t.strip() for t in terms if t and t.strip()}, key=len, reverse=True):
        text = re.sub(re.escape(t), lambda m: put("PARTY", m.group(0)), text, flags=re.I)
    for kind, pat in PATTERNS:
        text = re.sub(pat, lambda m, k=kind: put(k, m.group(0)), text)
    return text, mapping


def restore(text, mapping):
    for tok, orig in mapping.items():
        text = text.replace(tok, orig)
    return text
