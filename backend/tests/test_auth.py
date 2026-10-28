import pathlib
import subprocess
from datetime import datetime, timedelta, timezone

import jwt
import pytest

from app.config import SECRET_KEY

FUTURE = datetime.now(timezone.utc) + timedelta(hours=1)


def auth(token):
    return {"Authorization": f"Bearer {token}"}


def test_token_without_exp_is_rejected(client):
    token = jwt.encode({"sub": "1", "org": 1}, SECRET_KEY, algorithm="HS256")

    r = client.get("/dashboard?org_id=1", headers=auth(token))

    assert r.status_code == 401


def test_token_without_sub_is_rejected(client):
    token = jwt.encode({"org": 1, "exp": FUTURE}, SECRET_KEY, algorithm="HS256")

    r = client.get("/dashboard?org_id=1", headers=auth(token))

    assert r.status_code == 401


def test_old_committed_secret_is_not_trusted(client):
    """The key committed in 930dd6e must no longer sign valid tokens."""
    root = pathlib.Path(__file__).resolve().parents[2]
    try:
        env = subprocess.run(
            ["git", "show", "930dd6e:backend/.env"],
            cwd=root,
            capture_output=True,
            text=True,
            check=True,
        ).stdout
    except (OSError, subprocess.CalledProcessError):
        pytest.skip("git history is unavailable")
    old_secret = next(
        line.split("=", 1)[1].strip()
        for line in env.splitlines()
        if line.startswith("SECRET_KEY=")
    )
    if old_secret == SECRET_KEY:
        pytest.skip("current test key equals the old key")

    token = jwt.encode({"sub": "1", "org": 1, "exp": FUTURE}, old_secret, algorithm="HS256")

    r = client.get("/dashboard?org_id=1", headers=auth(token))

    assert r.status_code == 401
