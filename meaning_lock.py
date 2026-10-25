"""Meaning Lock: extract legally significant facts before/after an edit and flag unintended changes."""
import re

NUMW = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "ten": 10, "fifteen": 15, "thirty": 30, "sixty": 60, "ninety": 90}
MON = {m: i for i, m in enumerate(["january", "february", "march", "april", "may", "june", "july", "august", "september", "october", "november", "december"], 1)}
MULT = {"lakh": 1e5, "lakhs": 1e5, "crore": 1e7, "crores": 1e7, "thousand": 1e3}


def inr(n):
    s = str(int(n))
    if len(s) <= 3:
        return "₹" + s
    head, tail = s[:-3], s[-3:]
    head = re.sub(r"(\d)(?=(\d\d)+$)", r"\1,", head)
    return f"₹{head},{tail}"


def extract(text):
    f = {k: set() for k in ("amount", "date", "percent", "duration", "section", "reference_no", "party")}
    for m in re.finditer(r"(?:₹|Rs\.?|INR)\s*([\d,]+(?:\.\d+)?)(?:\s*(lakhs?|crores?|thousand))?|\b(\d+(?:\.\d+)?)\s*(lakhs?|crores?)\b", text, re.I):
        num = (m.group(1) or m.group(3)).replace(",", "")
        mult = MULT.get((m.group(2) or m.group(4) or "").lower(), 1)
        try:
            f["amount"].add(inr(float(num) * mult))
        except ValueError:
            pass
    for m in re.finditer(r"\b(\d{1,2})[./-](\d{1,2})[./-](\d{4})\b", text):
        f["date"].add(f"{m.group(3)}-{int(m.group(2)):02d}-{int(m.group(1)):02d}")
    for m in re.finditer(r"\b(\d{1,2})(?:st|nd|rd|th)?\s+(" + "|".join(MON) + r")\s+(\d{4})\b", text, re.I):
        f["date"].add(f"{m.group(3)}-{MON[m.group(2).lower()]:02d}-{int(m.group(1)):02d}")
    for m in re.finditer(r"(\d+(?:\.\d+)?)\s*(?:%|per\s*cent|percent)", text, re.I):
        f["percent"].add(m.group(1).rstrip("0").rstrip(".") + "%" if "." in m.group(1) else m.group(1) + "%")
    for m in re.finditer(r"\b(\d+|" + "|".join(NUMW) + r")\s*(?:\(\d+\)\s*)?(days?|weeks?|months?|years?)\b", text, re.I):
        n = m.group(1).lower()
        f["duration"].add(f"{NUMW.get(n, n)} {m.group(2).lower().rstrip('s')}s")
    for m in re.finditer(r"\bSections?\s+(\d+[A-Z]?(?:\(\w+\))*)", text):
        f["section"].add("Section " + m.group(1))
    for m in re.finditer(r"\b(?:No\.|Nos\.|Number|Ref\.?)\s*:?\s*([A-Z0-9][A-Z0-9/-]{3,})", text):
        f["reference_no"].add(m.group(1))
    return f


def compare(before, after, instruction="", must_keep=()):
    b, a = extract(before), extract(after)
    for t in must_keep:
        if t.lower() in before.lower():
            b["party"].add(t)
        if t.lower() in after.lower():
            a["party"].add(t)
    ins = instruction.lower()
    ins_digits = re.sub(r"\D", " ", ins).split()

    def intended(v):
        d = re.sub(r"\D", "", v)
        return bool(d) and (d in ins_digits or v.lower() in ins)

    rows, worst = [], "locked"
    for cat in b:
        removed, added, kept = sorted(b[cat] - a[cat]), sorted(a[cat] - b[cat]), sorted(b[cat] & a[cat])
        if not removed and not added:
            status = "locked"
        elif all(intended(v) for v in (added or removed)):
            status = "changed_by_instruction"
        else:
            status = "unintended_change"
        if status == "unintended_change":
            worst = "review_required"
        elif status == "changed_by_instruction" and worst == "locked":
            worst = "intended_changes"
        if kept or removed or added:
            rows.append({"category": cat, "status": status, "kept": kept, "removed": removed, "added": added})
    return {"overall": worst, "rows": rows}
