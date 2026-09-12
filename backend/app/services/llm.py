"""Thin wrapper around the LLM used to score open-ended answers.

AI_MODE=mock  -> returns canned responses from data/mock_ai_responses.json
AI_MODE=live  -> calls an OpenAI-compatible chat completions endpoint
"""
import hashlib
import json
import os

import httpx

from ..config import AI_MODE, LLM_API_URL, LLM_API_KEY, LLM_MODEL

_MOCK_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "data", "mock_ai_responses.json")

PROMPT = """You are scoring how well an employee uses AI at work.
Rubric: 1 = no AI use, 2 = occasional basic use, 3 = regular use for simple tasks,
4 = regular, thoughtful use with review of outputs, 5 = advanced use that changes how the work is done.
Flag risks using only these labels: customer_data_shared, confidential_data_shared, unreviewed_output, policy_unaware.
Answer the question: {question}
Employee's answer: {answer}
Return JSON: {{"score": <1-5>, "reason": "<one sentence>", "flags": [<labels>]}}"""


def _mock(answer: str) -> str:
    with open(_MOCK_PATH) as f:
        canned = json.load(f)
    idx = int(hashlib.md5(answer.encode()).hexdigest(), 16) % len(canned)
    return canned[idx]


def score_answer(question: str, answer: str) -> str:
    """Returns the raw text the model produced."""
    if AI_MODE == "mock":
        return _mock(answer)
    r = httpx.post(
        LLM_API_URL,
        headers={"Authorization": f"Bearer {LLM_API_KEY}"},
        json={
            "model": LLM_MODEL,
            "messages": [{"role": "user", "content": PROMPT.format(question=question, answer=answer)}],
        },
        timeout=60,
    )
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"]
