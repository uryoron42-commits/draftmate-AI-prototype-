"""Citation & authority verification.
Pipeline per citation: regex extraction -> deterministic stale-law check -> web-grounded proposition check.
Rule: nothing is 'verified' unless a real web source was returned. Uncertainty is reported, never hidden."""
import hashlib
import re
from concurrent.futures import ThreadPoolExecutor

import llm
from law_maps import NEW_ACT, STALE_MAP

ACTS = (r"(Indian Penal Code|I\.?P\.?C\.?|Code of Criminal Procedure|Criminal Procedure Code|Cr\.?\s?P\.?\s?C\.?|"
        r"Indian Evidence Act|Evidence Act|Negotiable Instruments Act|N\.?I\.? Act|Bharatiya Nyaya Sanhita|BNSS|BNS|"
        r"Bharatiya Nagarik Suraksha Sanhita|Bharatiya Sakshya Adhiniyam|BSA|Code of Civil Procedure|C\.?P\.?C\.?|"
        r"(?:[A-Z][A-Za-z&]+\s+){1,5}Act)")
STATUTE_RE = re.compile(
    r"(?:\b[Ss]ection|\b[Ss]ec\.|\b[Ss]\.)\s*(\d+[A-Z]{0,2})((?:\s*\(\w+\))*)\s*,?\s*(?:(?:of|read with|r/w)\s+)?(?:the\s+)?"
    + ACTS + r"(?![A-Za-z])(?:,?\s*((?:18|19|20)\d{2}))?")
TOK = r"(?:[A-Z][\w.&'’\-]*|of|and|the|for|ors\.?|anr\.?)"
REPORTER = (r"(?:\(\d{4}\)\s*\d+\s*(?:SCC|SCR)\s*\d+|AIR\s*\d{4}\s*(?:SC|Del|Bom|Cal|Mad|All|Pat|Ker|Kar|P&H|Guj|Raj|MP|Ori)\s*\d+"
            r"|\[\d{4}\]\s*\d+\s*SCR\s*\d+|\d{4}\s*SCC\s*OnLine\s*[A-Za-z]+\s*\d+)")
CASE_RE = re.compile(rf"([A-Z][\w.&'’\-]*\s+(?:{TOK}\s+){{0,5}}v(?:s)?\.?\s+(?:{TOK}[\s,]+){{1,8}}?)({REPORTER})")

_cache = {}


def act_key(name):
    n = re.sub(r"[.\s]", "", name).lower()
    if n in ("ipc", "indianpenalcode"):
        return "ipc"
    if n in ("crpc", "codeofcriminalprocedure", "criminalprocedurecode"):
        return "crpc"
    if n in ("indianevidenceact", "evidenceact"):
        return "iea"
    return None


def _para(text, start, end):
    s = text.rfind("\n", 0, start) + 1
    e = text.find("\n", end)
    e = len(text) if e < 0 else e
    p = text[s:e]
    if len(p) > 420:
        a = max(0, start - s - 200)
        p = p[a:a + 420]
    return p.strip()


def extract(text):
    items, covered = [], []
    for m in STATUTE_RE.finditer(text):
        sec, sub, act, yr = m.group(1), m.group(2) or "", m.group(3), m.group(4)
        raw = m.group(0).strip()
        raw = raw[:-1] if raw.endswith(".") and "." not in m.group(3)[:-1] else raw
        items.append({"type": "statute", "raw": raw, "span": m.span(), "section": sec + sub.replace(" ", ""),
                      "base": sec, "act": act, "act_key": act_key(act), "year": yr, "sentence": _para(text, *m.span())})
        covered.append(m.span())
    for m in CASE_RE.finditer(text):
        name = re.sub(r"\s+", " ", m.group(1)).strip(" ,")
        items.append({"type": "case", "raw": f"{name} {m.group(2).strip()}", "span": m.span(), "case_name": name,
                      "reporter": m.group(2).strip(), "sentence": _para(text, *m.span())})
    items.sort(key=lambda i: i["span"][0])
    for n, it in enumerate(items, 1):
        it["id"] = f"c{n}"
    return items


def stale_check(it):
    if it["type"] != "statute" or not it.get("act_key"):
        return None
    new = STALE_MAP.get(it["act_key"], {}).get(it["base"])
    if not new:
        return None
    return {"replacement": f"Section {new} of the {NEW_ACT[it['act_key']]}",
            "note": f"{it['act']} was replaced on 1 July 2024. Closest corresponding provision: {NEW_ACT[it['act_key']]}, Section {new}. "
                    "Check the mapping, because sub-clauses and wording can differ."}


def fix_stale(text):
    changes = []

    def sub(m):
        key = act_key(m.group(3))
        new = STALE_MAP.get(key, {}).get(m.group(1)) if key else None
        if not new:
            return m.group(0)
        rep = f"Section {new} of the {NEW_ACT[key]}"
        tail = "." if m.group(0).rstrip().endswith(".") and "." not in m.group(3)[:-1] else ""
        changes.append({"from": m.group(0).strip().rstrip(".") if tail else m.group(0).strip(), "to": rep})
        return rep + tail
    return STATUTE_RE.sub(sub, text), changes


def _web_check(it):
    prompt = f"""You are verifying an Indian legal citation using web search. Prefer indiankanoon.org, indiacode.nic.in, sci.gov.in,
court websites and official reporters. Do not guess.
CITATION: {it['raw']}
CLAIM IN THE DRAFT: {it['sentence']}
Answer ONLY with JSON:
{{"exists":"yes|no|unsure","supports_claim":"yes|partial|no|unsure","what_it_actually_holds":"one sentence","correct_citation":"string or null","confidence":0.0}}"""
    r = llm.generate(prompt, grounded=True, temperature=0)
    data = llm.parse_json(llm.text(r)) or {}
    return data, llm.sources(r)


def _classify(it, use_web):
    base = {"id": it["id"], "type": it["type"], "raw": it["raw"], "sentence": it["sentence"], "sources": [],
            "replacement": None, "note": "", "confidence": 0.0, "possible_fabrication": False}
    stale = stale_check(it)
    if stale:
        return {**base, "status": "outdated", "replacement": stale["replacement"], "note": stale["note"], "confidence": 0.95}
    if not use_web:
        return {**base, "status": "unchecked", "note": "Web verification was not run."}
    key = hashlib.md5((it["raw"] + it["sentence"]).encode()).hexdigest()
    if key in _cache:
        return {**base, **_cache[key]}
    try:
        data, srcs = _web_check(it)
    except Exception as e:  # noqa
        return {**base, "status": "unverified", "note": f"Verification service error: {e}"}
    exists, sup = data.get("exists", "unsure"), data.get("supports_claim", "unsure")
    conf = float(data.get("confidence") or 0)
    holds = data.get("what_it_actually_holds") or ""
    if exists == "no":
        out = {"status": "unverified", "possible_fabrication": True, "note": "No matching authority found. Possible fabricated citation. " + holds}
    elif exists == "yes" and srcs and sup == "yes":
        out = {"status": "verified", "note": holds}
    elif exists == "yes" and srcs:
        out = {"status": "partial", "note": f"Authority exists but may not support the claim. It actually holds: {holds}"}
    else:
        out = {"status": "unverified", "note": "Could not confirm from accessible sources. " + holds}
    out.update({"sources": srcs, "confidence": conf, "replacement": data.get("correct_citation")})
    _cache[key] = out
    return {**base, **out}


def verify_text(text, use_web=True, workers=4):
    items = extract(text)
    with ThreadPoolExecutor(max_workers=workers) as ex:
        results = list(ex.map(lambda i: _classify(i, use_web), items))
    counts = {k: sum(1 for r in results if r["status"] == k) for k in ("verified", "partial", "outdated", "unverified", "unchecked")}
    total = len(results)
    score = round(100 * (counts["verified"] + 0.5 * counts["partial"]) / total) if total else None
    return {"citations": results, "counts": counts, "total": total, "trust_score": score}
