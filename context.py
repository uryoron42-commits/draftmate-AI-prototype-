"""Token & context management (no external deps): compact -> chunk by clause -> retrieve by relevance -> pack into a budget."""
import math
import re
from collections import Counter

STOP = set("the and for that this with shall will from have has are was were been not any all may such upon under into per its their which than then also"
           " hereby herein thereof whereas between each other more most only both being those these".split())


def est_tokens(s):
    return max(1, len(s) // 4) if s else 0


def compact(md):
    """Remove noise that costs tokens but carries no legal meaning."""
    md = md.replace("\u00a0", " ").replace("\r", "")
    lines = [re.sub(r"[ \t]+$", "", l) for l in md.split("\n")]
    lines = [l for l in lines if not re.fullmatch(r"\s*(page\s*)?\d+\s*(of\s*\d+)?\s*", l, re.I)]
    freq = Counter(l.strip() for l in lines if 3 < len(l.strip()) < 80)
    lines = [l for l in lines if not (freq[l.strip()] >= 4 and len(l.strip()) < 80 and not re.match(r"\s*(#|\d)", l))]
    return re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()


HEAD = re.compile(r"^\s*(#{1,4}\s+|(?:ARTICLE|CLAUSE|SECTION|SCHEDULE|ANNEXURE)\b|\d+(?:\.\d+)*[.)]\s+[A-Z]|[A-Z][A-Z0-9 ,&'/-]{6,}$)")


def chunk(md, max_chars=2800, min_chars=250):
    parts, cur = [], []
    for line in md.split("\n"):
        if HEAD.match(line) and cur and sum(len(x) for x in cur) > min_chars:
            parts.append("\n".join(cur)); cur = []
        cur.append(line)
    if cur:
        parts.append("\n".join(cur))
    out = []
    for p in parts:  # split oversized chunks on paragraph borders
        while len(p) > max_chars:
            cut = p.rfind("\n\n", 0, max_chars)
            cut = cut if cut > 400 else max_chars
            out.append(p[:cut]); p = p[cut:].lstrip()
        if p.strip():
            out.append(p)
    return [{"id": i, "heading": c.strip().split("\n")[0][:80], "text": c, "tokens": est_tokens(c)} for i, c in enumerate(out)]


def _terms(s):
    return [w for w in re.findall(r"[a-z0-9]{3,}", s.lower()) if w not in STOP]


def retrieve(chunks, query, budget, full=False):
    """Pick the most relevant clauses that fit in `budget` tokens, in original order. Chunk 0 (parties/preamble) is always kept."""
    if not chunks:
        return []
    total = sum(c["tokens"] for c in chunks)
    if total <= budget:
        return chunks
    q = set(_terms(query))
    docs = [Counter(_terms(c["text"])) for c in chunks]
    df = Counter(t for d in docs for t in d)
    n = len(chunks)
    scores = [sum(d[t] * math.log(1 + n / df[t]) for t in q if t in d) / (1 + 0.15 * math.log(1 + c["tokens"])) for d, c in zip(docs, chunks)]
    order = sorted(range(n), key=lambda i: -scores[i]) if (q and any(scores)) and not full else list(range(n))
    picked, used = {0}, chunks[0]["tokens"]
    for i in order:
        if i in picked:
            continue
        if used + chunks[i]["tokens"] <= budget:
            picked.add(i); used += chunks[i]["tokens"]
    return [chunks[i] for i in sorted(picked)]


def build_context(docs, query, budget, full=False):
    """docs: list of (name, markdown). Returns (context_text, stats)."""
    blocks, orig, sent, ct, cu = [], 0, 0, 0, 0
    per = max(500, budget // max(1, len(docs)))
    for name, md in docs:
        orig += est_tokens(md)
        ch = chunk(compact(md))
        sel = retrieve(ch, query, per, full)
        ct += len(ch); cu += len(sel)
        body = "\n\n[...]\n\n".join(c["text"] for c in sel) if len(sel) < len(ch) else "\n\n".join(c["text"] for c in sel)
        sent += est_tokens(body)
        blocks.append(f'<document name="{name}">\n{body}\n</document>')
    saved = round(100 * (1 - sent / orig)) if orig else 0
    return "\n\n".join(blocks), {"original_tokens": orig, "sent_tokens": sent, "saved_percent": max(0, saved),
                                 "clauses_total": ct, "clauses_used": cu}
