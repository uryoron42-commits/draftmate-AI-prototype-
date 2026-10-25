"""Upload -> Markdown (Microsoft MarkItDown) with an in-memory store. Swap STORE for a DB/Redis if you need persistence."""
import os
import tempfile
import uuid
from pathlib import Path

import config
from context import chunk, compact, est_tokens

ALLOWED = {".pdf", ".docx", ".pptx", ".xlsx", ".csv", ".html", ".htm", ".txt", ".md"}
STORE = {}


def to_markdown(filename, data):
    ext = Path(filename).suffix.lower()
    if ext not in ALLOWED:
        raise ValueError(f"Unsupported file type {ext or '(none)'}. Allowed: {', '.join(sorted(ALLOWED))}")
    if len(data) > config.MAX_UPLOAD_MB * 1024 * 1024:
        raise ValueError(f"File is larger than {config.MAX_UPLOAD_MB} MB.")
    if ext in {".txt", ".md"}:
        return data.decode("utf-8", errors="replace")
    try:
        from markitdown import MarkItDown
    except ImportError:
        raise ValueError("Install the converter first: pip install 'markitdown[all]'")
    with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as f:
        f.write(data)
        path = f.name
    try:
        return MarkItDown().convert(path).text_content or ""
    finally:
        os.unlink(path)


def save(filename, data):
    md = to_markdown(filename, data)
    if not md.strip():
        raise ValueError("No readable text found. Scanned PDFs need OCR first.")
    did = uuid.uuid4().hex[:10]
    STORE[did] = {"id": did, "name": filename, "markdown": md}
    cm = compact(md)
    return {"doc_id": did, "name": filename, "tokens_raw_markdown": est_tokens(md), "tokens_after_cleanup": est_tokens(cm),
            "clauses": len(chunk(cm)), "preview": md[:400]}


def get(did):
    return STORE.get(did)
