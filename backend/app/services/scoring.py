import json

from . import llm

ALLOWED_FLAGS = set(llm.ALLOWED_FLAGS)

SCORING_FAILED = {"score": None, "reason": None, "flags": ["scoring_failed"]}


def _strip_code_fence(raw: str) -> str:
    """Models sometimes wrap JSON in ```json ... ```."""
    text = raw.strip()
    if not text.startswith("```"):
        return text
    lines = text.splitlines()[1:]
    if lines and lines[-1].strip().startswith("```"):
        lines = lines[:-1]
    return "\n".join(lines).strip()


def _coerce_score(value) -> int | None:
    """An int in 1..5, or None. Accepts "4" and 4.0; rejects "four" and 7."""
    if isinstance(value, bool):
        return None
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    elif isinstance(value, str) and value.strip().isdigit():
        value = int(value.strip())
    if not isinstance(value, int) or not 1 <= value <= 5:
        return None
    return value


def score_open_answer(question_text: str, answer: str) -> dict:
    raw = llm.score_answer(question_text, answer)
    try:
        data = json.loads(_strip_code_fence(raw))
    except (json.JSONDecodeError, TypeError):
        return dict(SCORING_FAILED)
    if not isinstance(data, dict):
        return dict(SCORING_FAILED)

    reason = data.get("reason")
    raw_flags = data.get("flags")
    if isinstance(raw_flags, str):
        raw_flags = [raw_flags]
    return {
        "score": _coerce_score(data.get("score")),
        "reason": reason if isinstance(reason, str) else None,
        "flags": [f for f in raw_flags if f in ALLOWED_FLAGS] if isinstance(raw_flags, list) else [],
    }
