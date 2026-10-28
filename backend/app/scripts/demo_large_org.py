"""Add five responders to Northwind Sales so the dashboard shows a department.

All seeded departments are below the client's five-responder privacy threshold,
so the seeded dashboard is intentionally empty. Run from backend:

    python -m app.scripts.demo_large_org

The command is idempotent. It does not touch app/seed.py.
"""
from ..db import SessionLocal
from .. import models
from ..auth import hash_password

DEMO_EMAILS = [f"demo-sales-{i}@northwind.test" for i in range(1, 6)]


def run() -> int:
    db = SessionLocal()
    try:
        org = db.query(models.Organization).filter_by(name="Northwind Logistics").one()
        dept = db.query(models.Department).filter_by(org_id=org.id, name="Sales").one()
        added = 0
        for index, email in enumerate(DEMO_EMAILS, start=1):
            if db.query(models.User).filter_by(email=email).first():
                continue
            user = models.User(
                email=email,
                name=f"Demo Sales {index}",
                password_hash=hash_password("pulse123"),
            )
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
                question_id="common-freq",
                answer="A few times a week",
                score=3,
                reason=None,
                flags=[],
            ))
            added += 1
        db.commit()
        print(f"Added {added} responders to Northwind Sales.")
        print(f"Login as any of: {', '.join(DEMO_EMAILS)} (password pulse123)")
        return added
    finally:
        db.close()


if __name__ == "__main__":
    run()
