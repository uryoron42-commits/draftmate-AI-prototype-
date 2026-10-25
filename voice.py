"""Voice agent brain: Hinglish/English transcript -> structured action, with confirmation for consequential actions."""
import re

import llm

YES = re.compile(r"\b(yes|yeah|yep|confirm(?:ed)?|ok(?:ay)?|sure|go ahead|proceed|haan|han|haa|kar do|theek hai|thik hai)\b", re.I)
NO = re.compile(r"\b(no|nope|cancel|stop|don'?t|nahi|nahin|mat|ruko|rehne do|wait)\b", re.I)
NUM = r"(\d+(?:\.\d+)?)"


def confirm(transcript):
    return "no" if NO.search(transcript) else "yes" if YES.search(transcript) else "unclear"


def _act(intent, say, params=None, confirm_prompt=None):
    return {"intent": intent, "params": params or {}, "requires_confirmation": bool(confirm_prompt),
            "confirm_prompt": confirm_prompt, "say": say}


def fast_parse(t, has_draft):
    s = t.lower().strip()
    if re.search(r"red\s*team|opposing|loophole|weakness", s):
        return _act("red_team", "Running opposing counsel on your draft.")
    if re.search(r"\b(delete|remove|hata|hatao|hata do|mita)\b", s):
        c = re.search(r"clause\s*(\d+)", s)
        target = {"clause": int(c.group(1))} if c else {"target": "unverified_citation" if re.search(r"fake|unverified|citation|case", s) else "selection"}
        return _act("delete", "This will delete content.", target, "Delete this from the draft? Say confirm to proceed or cancel to stop.")
    c = re.search(r"clause\s*(\d+)", s)
    if c:
        return _act("edit_clause", f"Editing clause {c.group(1)}.", {"clause": int(c.group(1)), "instruction": t})
    m = re.search(rf"(?:interest|byaj|ब्याज)\D{{0,20}}{NUM}|{NUM}\s*(?:%|percent|prati?shat)?\D{{0,15}}(?:interest|byaj)", s)
    if m:
        val = float(m.group(1) or m.group(2))
        return _act("set_value", f"Setting interest to {val:g} percent.", {"field": "interest_percent", "value": val})
    if re.search(r"\b(bns|bnss|bsa|ipc|stale|outdated|update the law)\b|\bfix\b", s):
        return _act("fix_stale", "Replacing outdated law references.")
    if re.search(r"\b(verify|check|citations?|authorit)", s):
        return _act("verify", "Checking every citation against sources.")
    if re.search(r"\b(export|download|pdf|docx|word doc)\b", s):
        fmt = "docx" if re.search(r"docx|word", s) else "pdf"
        return _act("export", f"Exporting as {fmt}.", {"format": fmt})
    if re.search(r"\b(draft|banao|bana do|likho|prepare|generate|notice|agreement)\b", s):
        return _act("generate", "Drafting your document.", {"instructions": t},
                    "This will replace the current draft. Say confirm to proceed or cancel to stop." if has_draft else None)
    return None


def parse_command(transcript, has_draft=False, use_llm=True):
    hit = fast_parse(transcript, has_draft)
    if hit or not use_llm:
        return hit or _act("unknown", "I did not catch a command. Try: draft, fix law references, verify citations, red team, or export.")
    try:
        r = llm.generate(
            "Classify this spoken legal-drafting command (English/Hindi/Hinglish) into JSON: "
            '{"intent":"generate|edit_clause|set_value|fix_stale|verify|red_team|export|delete|dictate|unknown",'
            '"params":{},"say":"short spoken feedback"}\nTranscript: ' + transcript, json_mode=True, temperature=0)
        d = llm.parse_json(llm.text(r)) or {}
        intent = d.get("intent", "unknown")
        risky = intent in ("delete",) or (intent == "generate" and has_draft)
        return _act(intent, d.get("say", ""), d.get("params"), "Say confirm to proceed or cancel to stop." if risky else None)
    except Exception:  # noqa
        return _act("unknown", "I did not catch a command.")


def transcribe(audio, mime="audio/webm"):
    """Speech-to-text via Gemini (handles Hinglish). Use browser SpeechRecognition on the frontend for zero-latency live captions."""
    from google.genai import types
    part = types.Part.from_bytes(data=audio, mime_type=mime)
    r = llm.generate("Transcribe this speech exactly. It may mix Hindi and English; write Hindi words in Roman script. "
                     "Expect legal terms (indemnity, injunction, affidavit, cheque, BNS, IPC, Section 138). Output only the transcript.",
                     parts=[part], temperature=0)
    return llm.text(r)
