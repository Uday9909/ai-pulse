import hashlib
import json
import os

import pytest

from tests.conftest import login
from app.db import SessionLocal
from app import models
from app.services import scoring

# The scoring contract, stated independently of the implementation under test.
ALLOWED_FLAGS = {
    "customer_data_shared",
    "confidential_data_shared",
    "unreviewed_output",
    "policy_unaware",
}
MOCK_COUNT = len(json.load(open(os.path.join(os.path.dirname(__file__), "..", "data", "mock_ai_responses.json"))))


def answer_for_index(index: int) -> str:
    """An answer whose md5 selects the given canned mock response."""
    n = 0
    while True:
        answer = f"probe-{index}-{n}"
        if int(hashlib.md5(answer.encode()).hexdigest(), 16) % MOCK_COUNT == index:
            return answer
        n += 1


@pytest.mark.parametrize("index", range(MOCK_COUNT))
def test_malformed_mock_entries_do_not_break_submit(client, index):
    # Neha has no seeded answers; submitting common-open twice now returns 409.
    headers, _ = login(client, "neha@northwind.test", "Northwind Logistics")
    answer = answer_for_index(index)

    r = client.post(
        "/diagnostic/submit",
        json={"answers": [{"question_id": "common-open", "answer": answer}]},
        headers=headers,
    )

    assert r.status_code == 200
    db = SessionLocal()
    try:
        row = db.query(models.Response).filter_by(answer=answer).one()
        assert row.score is None or (float(row.score).is_integer() and 1 <= row.score <= 5)
        assert set(row.flags or []) <= ALLOWED_FLAGS
    finally:
        db.close()


def test_unparseable_output_returns_scoring_failed(monkeypatch):
    monkeypatch.setattr(scoring.llm, "score_answer", lambda q, a: "this is not json")
    assert scoring.score_open_answer("q", "a") == {
        "score": None,
        "reason": None,
        "flags": ["scoring_failed"],
    }


def test_fenced_json_is_parsed(monkeypatch):
    monkeypatch.setattr(
        scoring.llm,
        "score_answer",
        lambda q, a: '```json\n{"score": 4, "reason": "ok", "flags": []}\n```',
    )
    assert scoring.score_open_answer("q", "a") == {"score": 4, "reason": "ok", "flags": []}


def test_out_of_range_and_non_numeric_scores_become_none(monkeypatch):
    monkeypatch.setattr(scoring.llm, "score_answer", lambda q, a: '{"score": 7, "flags": []}')
    assert scoring.score_open_answer("q", "a")["score"] is None

    monkeypatch.setattr(scoring.llm, "score_answer", lambda q, a: '{"score": "four", "flags": []}')
    assert scoring.score_open_answer("q", "a")["score"] is None


def test_unknown_flags_are_dropped(monkeypatch):
    monkeypatch.setattr(
        scoring.llm,
        "score_answer",
        lambda q, a: '{"score": 3, "flags": ["probably_lying", "unreviewed_output"]}',
    )
    assert scoring.score_open_answer("q", "a")["flags"] == ["unreviewed_output"]
