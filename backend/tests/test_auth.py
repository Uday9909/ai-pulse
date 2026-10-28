import hashlib
import os
import pathlib
import subprocess
import sys
from datetime import datetime, timedelta, timezone

import jwt
import pytest

from app.auth import hash_password, password_needs_rehash, verify_password
from app.config import SECRET_KEY
from app.db import SessionLocal
from app import models

FUTURE = datetime.now(timezone.utc) + timedelta(hours=1)


def auth(token):
    return {"Authorization": f"Bearer {token}"}


def test_password_hash_is_salted_and_verifies():
    first = hash_password("pulse123")
    second = hash_password("pulse123")

    assert first != second
    assert first.startswith("pbkdf2_sha256$")
    assert verify_password("pulse123", first)
    assert not verify_password("wrong", first)


def test_legacy_sha256_login_is_upgraded(client):
    db = SessionLocal()
    try:
        user = db.query(models.User).filter_by(email="priya@northwind.test").one()
        user.password_hash = hashlib.sha256(b"pulse123").hexdigest()
        db.commit()
    finally:
        db.close()

    r = client.post(
        "/auth/login",
        json={"email": "priya@northwind.test", "password": "pulse123"},
    )
    assert r.status_code == 200

    db = SessionLocal()
    try:
        user = db.query(models.User).filter_by(email="priya@northwind.test").one()
        assert user.password_hash.startswith("pbkdf2_sha256$")
        assert not password_needs_rehash(user.password_hash)
    finally:
        db.close()


def test_short_secret_key_is_rejected():
    backend = pathlib.Path(__file__).resolve().parents[1]
    env = os.environ.copy()
    env["SECRET_KEY"] = "too-short"

    result = subprocess.run(
        [sys.executable, "-c", "import app.config"],
        cwd=backend,
        env=env,
        capture_output=True,
        text=True,
    )

    assert result.returncode != 0
    assert "at least 32 bytes" in result.stderr


def test_config_refuses_to_start_without_secret_key():
    backend = pathlib.Path(__file__).resolve().parents[1]
    env = os.environ.copy()
    env["SECRET_KEY"] = ""

    result = subprocess.run(
        [sys.executable, "-c", "import app.config"],
        cwd=backend,
        env=env,
        capture_output=True,
        text=True,
    )

    assert result.returncode != 0
    assert "SECRET_KEY is not set" in result.stderr


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
