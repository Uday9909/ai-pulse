import os
import pytest

os.environ["DATABASE_URL"] = "sqlite:///./test.db"
os.environ["AI_MODE"] = "mock"

from fastapi.testclient import TestClient  # noqa: E402
from app.main import app  # noqa: E402
from app import seed, models  # noqa: E402
from app.auth import hash_password  # noqa: E402
from app.db import SessionLocal  # noqa: E402


@pytest.fixture()
def client():
    seed.run()
    return TestClient(app)


def login(client, email, org_name=None):
    r = client.post("/auth/login", json={"email": email, "password": "pulse123"})
    data = r.json()
    token = data["token"]
    if org_name:
        org = next(o for o in data["organizations"] if o["org_name"] == org_name)
        token = client.post("/auth/select-org", json={"org_id": org["org_id"]},
                            headers={"Authorization": f"Bearer {token}"}).json()["token"]
    return {"Authorization": f"Bearer {token}"}, data


def add_responder(org_name, dept_name, email, score=3, flags=None):
    """Insert an employee in a department with one answer."""
    db = SessionLocal()
    try:
        org = db.query(models.Organization).filter_by(name=org_name).one()
        dept = db.query(models.Department).filter_by(org_id=org.id, name=dept_name).one()
        user = models.User(email=email, name=email, password_hash=hash_password("pulse123"))
        db.add(user)
        db.flush()
        membership = models.Membership(
            user_id=user.id,
            org_id=org.id,
            department_id=dept.id,
            role="employee",
            job_role="sales",
            seniority="mid",
        )
        db.add(membership)
        db.flush()
        db.add(models.Response(
            membership_id=membership.id,
            question_id="common-open",
            answer="synthetic",
            score=score,
            reason="synthetic",
            flags=flags or [],
        ))
        db.commit()
    finally:
        db.close()


def add_response(email, org_name, score=3, flags=None, question_id="common-open"):
    """Add one answer to an existing membership."""
    db = SessionLocal()
    try:
        org = db.query(models.Organization).filter_by(name=org_name).one()
        user = db.query(models.User).filter_by(email=email).one()
        membership = db.query(models.Membership).filter_by(user_id=user.id, org_id=org.id).one()
        db.add(models.Response(
            membership_id=membership.id,
            question_id=question_id,
            answer="synthetic",
            score=score,
            reason="synthetic",
            flags=flags or [],
        ))
        db.commit()
    finally:
        db.close()
