import json

from . import llm


def score_open_answer(question_text: str, answer: str) -> dict:
    raw = llm.score_answer(question_text, answer)
    data = json.loads(raw)
    return {"score": data.get("score"), "reason": data.get("reason"), "flags": data.get("flags", [])}
