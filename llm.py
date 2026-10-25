"""Thin Gemini wrapper: retries, model fallback, Google-Search grounding, streaming, safe JSON parsing."""
import json
import re
import time

import config


class LLMError(Exception):
    pass


_client = None


def client():
    global _client
    if _client is None:
        if not config.GEMINI_API_KEY:
            raise LLMError("GEMINI_API_KEY is missing from the .env file.")
        from google import genai
        _client = genai.Client(api_key=config.GEMINI_API_KEY)
    return _client


def _models():
    return [config.MODEL] + [m for m in config.FALLBACK_MODELS if m != config.MODEL]


def _config(system=None, json_mode=False, temperature=0.3, grounded=False):
    from google.genai import types
    cfg = {"temperature": temperature}
    if system:
        cfg["system_instruction"] = system
    if json_mode and not grounded:  # JSON mime type and search tool cannot be combined
        cfg["response_mime_type"] = "application/json"
    if grounded:
        cfg["tools"] = [types.Tool(google_search=types.GoogleSearch())]
    return types.GenerateContentConfig(**cfg)


def generate(prompt, system=None, json_mode=False, temperature=0.3, grounded=False, parts=None):
    """Returns the raw response. Tries the main model, then fallbacks, 2 attempts each."""
    contents = (parts + [prompt]) if parts else prompt
    cfg = _config(system, json_mode, temperature, grounded)
    last = None
    for model in _models():
        for attempt in range(2):
            try:
                return client().models.generate_content(model=model, contents=contents, config=cfg)
            except LLMError:
                raise
            except Exception as e:  # noqa
                last = e
                time.sleep(0.7 * (attempt + 1))
    raise LLMError(f"All models failed: {last}")

def stream(prompt, system=None, temperature=0.3):
    """Fallback to standard generation to prevent any async generator StopIteration errors."""
    resp = generate(prompt, system=system, temperature=temperature)
    text_content = text(resp)
    if text_content:
        yield text_content
        
def text(resp):
    return (getattr(resp, "text", None) or "").strip()


def sources(resp):
    """Web sources Gemini actually used (grounding metadata). Empty list = nothing was found."""
    out, seen = [], set()
    try:
        meta = resp.candidates[0].grounding_metadata
        for ch in (meta.grounding_chunks or []):
            if ch.web and ch.web.uri and ch.web.uri not in seen:
                seen.add(ch.web.uri)
                out.append({"title": ch.web.title or "", "uri": ch.web.uri})
    except Exception:  # noqa
        pass
    return out


def parse_json(s):
    s = re.sub(r"^```(?:json)?\s*|\s*```$", "", (s or "").strip())
    try:
        return json.loads(s)
    except Exception:  # noqa
        m = re.search(r"(\{.*\}|\[.*\])", s, re.S)
        if m:
            try:
                return json.loads(m.group(1))
            except Exception:  # noqa
                return None
    return None
