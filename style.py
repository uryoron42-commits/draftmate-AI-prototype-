"""Style Passport: learn a drafter's style from reference documents. Deterministic fingerprint (free) + optional LLM summary."""
import re
import uuid

import llm

PASSPORTS = {}
FORMAL = ["hereby", "whereas", "aforesaid", "herein", "hereinafter", "notwithstanding", "thereof", "shall", "without prejudice", "failing which"]


def fingerprint(md):
    paras = [p.strip() for p in re.split(r"\n\s*\n", md) if p.strip()]
    sents = [s for s in re.split(r"(?<=[.;])\s+(?=[A-Z])", re.sub(r"\s+", " ", md)) if len(s) > 20]
    heads = [l.strip() for l in md.split("\n") if l.strip() and (l.strip().isupper() or l.lstrip().startswith("#")) and len(l) < 120]
    low = md.lower()
    return {
        "headings_in_caps": bool(heads) and sum(h.replace("#", "").strip().isupper() for h in heads) / len(heads) > 0.5,
        "that_paragraphs_ratio": round(sum(p.startswith("That ") for p in paras) / max(1, len(paras)), 2),
        "numbered_paragraphs": len(re.findall(r"(?m)^\s*\d+[.)]\s", md)) > 2,
        "lettered_subclauses": len(re.findall(r"(?m)^\s*\(?[a-z]\)\s", md)) > 2,
        "avg_sentence_words": round(sum(len(s.split()) for s in sents) / max(1, len(sents))),
        "formal_terms": {w: low.count(w) for w in FORMAL if low.count(w)},
        "defined_terms": sorted(set(re.findall(r"[“\"‘]([A-Z][\w ]{2,30})[”\"’]", md)))[:12],
        "date_format": "dd.mm.yyyy" if re.search(r"\b\d{2}\.\d{2}\.\d{4}\b", md) else ("dd/mm/yyyy" if re.search(r"\b\d{2}/\d{2}/\d{4}\b", md) else "written"),
        "currency_style": "₹" if "₹" in md else ("Rs." if "Rs" in md else "unspecified"),
    }


def extract(md, name="reference", use_llm=True):
    fp = fingerprint(md)
    passport = {"id": uuid.uuid4().hex[:10], "name": name, "fingerprint": fp, "tone": "", "structure": "", "terminology": [], "clause_patterns": []}
    if use_llm:
        sample = md[:2500] + "\n...\n" + md[len(md) // 2:len(md) // 2 + 1500] + "\n...\n" + md[-1200:]
        try:
            r = llm.generate(
                "Study this legal document sample and describe the DRAFTER'S STYLE only (not the facts). Return JSON: "
                '{"tone":"short phrase","structure":"how it is organised","terminology":["preferred terms"],'
                '"clause_patterns":["up to 5 reusable sentence patterns with facts replaced by <placeholders>"]}\n\n<sample>\n' + sample + "\n</sample>",
                json_mode=True, temperature=0.1)
            data = llm.parse_json(llm.text(r)) or {}
            for k in ("tone", "structure", "terminology", "clause_patterns"):
                if k in data:
                    passport[k] = data[k]
        except Exception:  # noqa  - fingerprint alone is still useful
            pass
    PASSPORTS[passport["id"]] = passport
    return passport


def to_prompt(p):
    if not p:
        return ""
    fp = p["fingerprint"]
    bits = [f"Tone: {p.get('tone') or 'formal'}", f"Structure: {p.get('structure') or 'follow the reference'}",
            f"Headings in capitals: {fp['headings_in_caps']}", f"'That ...' numbered paragraphs: {fp['that_paragraphs_ratio'] > 0.3}",
            f"Date format: {fp['date_format']}", f"Currency style: {fp['currency_style']}"]
    if p.get("terminology"):
        bits.append("Preferred terms: " + ", ".join(map(str, p["terminology"][:10])))
    if fp["defined_terms"]:
        bits.append("Defined terms used: " + ", ".join(fp["defined_terms"]))
    if p.get("clause_patterns"):
        bits.append("Clause patterns to imitate:\n- " + "\n- ".join(map(str, p["clause_patterns"][:5])))
    return "STYLE PASSPORT (imitate this drafting style; never copy facts from the reference):\n" + "\n".join(bits)
