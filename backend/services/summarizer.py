"""Structured notes generation from video transcripts.

Local mode  (no GROQ_API_KEY): Ollama runs models locally
Cloud mode  (GROQ_API_KEY set): Groq API (Llama 3, free)
"""
import json
import logging
import re
from typing import Optional

import httpx

from config import settings
from models.schemas import Notes, NoteSection, KeyTimestamp

logger = logging.getLogger(__name__)

NOTES_SYSTEM_PROMPT = """\
You are an expert note-taker. Analyse the video transcript and return ONLY a \
valid JSON object — no markdown fences, no explanation, no text before or after the JSON.

The JSON must match this exact structure:
{
  "summary": "<2-4 sentence overview of the entire video>",
  "sections": [
    {
      "heading": "<section title>",
      "content": "<detailed notes, use - for bullet points>",
      "start_time": <start seconds as a number>,
      "end_time": <end seconds as a number>
    }
  ],
  "key_timestamps": [
    {
      "time": <seconds as a number>,
      "label": "<3-5 word label>",
      "description": "<one sentence>"
    }
  ],
  "action_items": ["<specific actionable task>"]
}

Rules:
- 4 to 8 sections that follow the content flow
- 5 to 10 key timestamps for the most important moments
- action_items must be specific and concrete
- all time values are plain numbers (seconds), never strings
- return ONLY the JSON object, nothing else\
"""


def check_ollama() -> dict:
    """Check if local Ollama is reachable. Returns {"ok": bool, "models": [...]}"""
    try:
        import ollama
        client = ollama.Client(host=settings.ollama_base_url)
        models = [m["model"] for m in (client.list().get("models") or [])]
        return {"ok": True, "models": models}
    except Exception as exc:
        return {"ok": False, "models": [], "error": str(exc)}


def generate_notes(
    full_text: str,
    title: str,
    session_id: str,
    model: Optional[str] = None,
) -> Notes:
    """Generate structured notes. Uses Groq in cloud mode, Ollama locally."""
    user_content = f"Video Title: {title}\n\nTranscript:\n{full_text[:12000]}"

    if settings.use_groq:
        raw = _call_groq(user_content, model)
    else:
        raw = _call_ollama(user_content, model)

    return _parse_notes(raw, session_id, title)


# ── Groq ──────────────────────────────────────────────────────────────────────

def _call_groq(user_content: str, model: Optional[str]) -> str:
    from groq import Groq

    client = Groq(api_key=settings.groq_api_key)
    response = client.chat.completions.create(
        model=model or settings.groq_model,
        messages=[
            {"role": "system", "content": NOTES_SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
        ],
        response_format={"type": "json_object"},
        temperature=0.3,
        max_tokens=4096,
    )
    return response.choices[0].message.content


# ── Ollama ────────────────────────────────────────────────────────────────────

def _call_ollama(user_content: str, model: Optional[str]) -> str:
    import ollama

    _model = model or settings.ollama_model
    status = check_ollama()
    if not status["ok"]:
        raise RuntimeError(
            f"Ollama is not reachable at {settings.ollama_base_url}. "
            "Start it with: ollama serve"
        )
    if _model not in status["models"]:
        logger.info("Pulling Ollama model: %s", _model)
        ollama.Client(host=settings.ollama_base_url).pull(_model)

    client = ollama.Client(host=settings.ollama_base_url)
    response = client.chat(
        model=_model,
        messages=[
            {"role": "system", "content": NOTES_SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
        ],
        format="json",
        options={"temperature": 0.3, "num_predict": 4096},
    )
    return response["message"]["content"]


# ── Shared parser ─────────────────────────────────────────────────────────────

def _parse_notes(raw: str, session_id: str, title: str) -> Notes:
    text = re.sub(r"```(?:json)?\s*", "", raw).strip().rstrip("`").strip()

    data: dict = {}
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            try:
                data = json.loads(match.group())
            except json.JSONDecodeError:
                pass

    if not data:
        logger.warning("Could not parse LLM JSON for session %s. Raw: %s…", session_id, raw[:200])
        return Notes(
            session_id=session_id, title=title,
            summary=raw[:500], sections=[], key_timestamps=[], action_items=[],
        )

    sections = [
        NoteSection(
            heading=s.get("heading", ""),
            content=s.get("content", ""),
            start_time=_f(s.get("start_time")),
            end_time=_f(s.get("end_time")),
        )
        for s in data.get("sections", []) if s.get("heading")
    ]

    key_timestamps = [
        KeyTimestamp(
            time=_f(k.get("time", 0)) or 0.0,
            label=k.get("label", ""),
            description=k.get("description", ""),
        )
        for k in data.get("key_timestamps", []) if k.get("label")
    ]

    return Notes(
        session_id=session_id,
        title=title,
        summary=data.get("summary", ""),
        sections=sections,
        key_timestamps=key_timestamps,
        action_items=[str(a) for a in data.get("action_items", [])],
    )


def _f(val) -> Optional[float]:
    try:
        return float(val) if val is not None else None
    except (TypeError, ValueError):
        return None
