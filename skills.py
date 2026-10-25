"""Skills = plain Markdown files in /skills with a small header. Drop in a new .md and it appears instantly (no restart, no code)."""
import re

import config

ALIASES = {"draft": "general-drafting", "review": "contract-review", "summarize": "summarize", "summarise": "summarize"}


def _parse(path):
    raw = path.read_text(encoding="utf-8")
    m = re.match(r"---\n(.*?)\n---\n(.*)", raw, re.S)
    if not m:
        return None
    meta = {}
    for line in m.group(1).splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            meta[k.strip()] = v.strip()
    meta.setdefault("id", path.stem)
    meta["triggers"] = [t.strip().lower() for t in meta.get("triggers", "").split(",") if t.strip()]
    for flag in ("verify", "lock", "grounded"):
        meta[flag] = meta.get(flag, "false").lower() == "true"
    meta.setdefault("output", "text")
    meta.setdefault("context", "retrieve")
    meta["body"] = m.group(2).strip()
    return meta


def load_all():
    out = {}
    for p in sorted(config.SKILLS_DIR.glob("*.md")):
        s = _parse(p)
        if s:
            out[s["id"]] = s
    return out


def public(s):
    return {k: s[k] for k in ("id", "name", "category", "description", "output", "verify", "grounded") if k in s}


def route(instructions, explicit=None):
    """Explicit id wins, then an @skill-id mention, then keyword scoring, else general drafting."""
    skills = load_all()
    if explicit:
        sid = ALIASES.get(explicit, explicit)
        if sid in skills:
            return skills[sid]
    for m in re.finditer(r"@([\w-]+)", instructions or ""):
        sid = m.group(1).lower()
        if sid in skills:
            return skills[sid]
    low = (instructions or "").lower()
    best, score = None, 0
    for s in skills.values():
        sc = sum(2 if " " in t else 1 for t in s["triggers"] if t in low)
        if sc > score:
            best, score = s, sc
    return best or skills.get("general-drafting") or next(iter(skills.values()))
