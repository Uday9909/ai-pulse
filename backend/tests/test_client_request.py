from tests.conftest import login, add_responder, add_response
from app.db import SessionLocal
from app import models
from app.auth import hash_password

SMALL_GROUP_MIN_RESPONDENTS = 5


def make_org_with_responders(org_name, dept_counts):
    """Create an org, an admin, and N responders per department."""
    slug = org_name.lower().replace(" ", "")
    admin_email = f"admin@{slug}.test"
    db = SessionLocal()
    try:
        org = models.Organization(name=org_name)
        db.add(org)
        db.flush()
        admin = models.User(email=admin_email, name="Admin", password_hash=hash_password("pulse123"))
        db.add(admin)
        db.flush()
        db.add(models.Membership(
            user_id=admin.id, org_id=org.id, department_id=None,
            role="admin", job_role="manager", seniority="lead",
        ))
        for dept_name, count in dept_counts.items():
            dept = models.Department(org_id=org.id, name=dept_name)
            db.add(dept)
            db.flush()
            for i in range(count):
                email = f"{dept_name.lower()}{i}@{slug}.test"
                user = models.User(email=email, name=email, password_hash=hash_password("pulse123"))
                db.add(user)
                db.flush()
                membership = models.Membership(
                    user_id=user.id, org_id=org.id, department_id=dept.id,
                    role="employee", job_role="sales", seniority="mid",
                )
                db.add(membership)
                db.flush()
                db.add(models.Response(
                    membership_id=membership.id, question_id="common-open",
                    answer="synthetic", score=3, reason="synthetic", flags=[],
                ))
        db.commit()
    finally:
        db.close()
    return admin_email


def dashboard_for(client, email, org_name):
    headers, data = login(client, email, org_name)
    org_id = next(o["org_id"] for o in data["organizations"] if o["org_name"] == org_name)
    return client.get(f"/dashboard?org_id={org_id}", headers=headers).json()


def test_seeded_dashboard_hides_all_small_groups(client):
    data = dashboard_for(client, "asha@northwind.test", "Northwind Logistics")

    # Every seeded department is under five respondents, and the aggregate
    # would only hold two responders, so nothing is shown at all.
    assert data["departments"] == []


def test_single_small_department_is_hidden(client):
    admin_email = make_org_with_responders("OneDeptCo", {"Only": 4})
    data = dashboard_for(client, admin_email, "OneDeptCo")

    # Four responders in one department: too small to show, and an "Other
    # teams" row would still identify the only department.
    assert data["departments"] == []


def test_single_visible_department_is_shown_directly(client):
    admin_email = make_org_with_responders("OneDeptCo", {"Only": 5})
    data = dashboard_for(client, admin_email, "OneDeptCo")

    # Five responders clear the threshold, so the department is named.
    assert [d["department"] for d in data["departments"]] == ["Only"]


def test_other_teams_shown_when_anonymous_and_five_responded(client):
    admin_email = make_org_with_responders("TwoDeptCo", {"Alpha": 3, "Beta": 2})
    data = dashboard_for(client, admin_email, "TwoDeptCo")

    assert [d["department"] for d in data["departments"]] == ["Other teams"]
    assert data["departments"][0]["responded"] == 5
    assert data["departments"][0]["employees"] == 5


def test_small_department_flags_are_not_in_top_risks(client):
    data = dashboard_for(client, "asha@northwind.test", "Northwind Logistics")

    # Priya is the only source of customer_data_shared, and Support is too small.
    assert data["top_risks"] == []


def test_large_department_flags_still_appear(client):
    # Vikram already responded in Sales, so four more make five.
    for i in range(SMALL_GROUP_MIN_RESPONDENTS - 1):
        add_responder(
            "Northwind Logistics",
            "Sales",
            f"extra{i}@northwind.test",
            score=3,
            flags=["customer_data_shared"],
        )

    data = dashboard_for(client, "asha@northwind.test", "Northwind Logistics")
    names = {d["department"] for d in data["departments"]}
    risks = dict(data["top_risks"])

    assert "Sales" in names
    assert risks["customer_data_shared"] == 4


def test_resubmitting_answered_question_is_rejected(client):
    headers, _ = login(client, "priya@northwind.test", "Northwind Logistics")

    r = client.post(
        "/diagnostic/submit",
        json={"answers": [{"question_id": "common-freq", "answer": "Daily"}]},
        headers=headers,
    )

    assert r.status_code == 409


def test_duplicate_question_in_one_payload_is_rejected(client):
    headers, _ = login(client, "neha@northwind.test", "Northwind Logistics")
    answer = {"question_id": "common-freq", "answer": "Daily"}

    r = client.post(
        "/diagnostic/submit",
        json={"answers": [answer, answer]},
        headers=headers,
    )

    assert r.status_code == 409


def test_dashboard_does_not_double_count_legacy_duplicates(client):
    # Make Sales visible, then insert a second answer for a question Vikram
    # already answered (simulates rows written before the 409 existed).
    for i in range(4):
        add_responder("Northwind Logistics", "Sales", f"sales{i}@northwind.test", score=3)
    add_response("vikram@northwind.test", "Northwind Logistics", score=1, question_id="common-freq")

    data = dashboard_for(client, "asha@northwind.test", "Northwind Logistics")
    sales = next(d for d in data["departments"] if d["department"] == "Sales")

    # Latest common-freq (1) replaces 4; common-open is 4; four extras are 3.
    # 17 / 6 unique answers. Counting the stale row would give 21 / 7 = 3.0.
    assert sales["average_score"] == 2.83


def test_employee_can_delete_own_answers(client):
    headers, _ = login(client, "priya@northwind.test", "Northwind Logistics")

    r = client.delete("/reports/me", headers=headers)
    assert r.status_code == 200
    assert r.json()["deleted"] == 2

    report = client.get("/reports/me", headers=headers).json()
    assert report["answered"] == 0
    assert report["average_score"] is None


def test_delete_is_reflected_on_the_dashboard(client):
    # Make Sales visible: Vikram plus five synthetic responders.
    for i in range(5):
        add_responder("Northwind Logistics", "Sales", f"sales{i}@northwind.test", score=3)

    before = dashboard_for(client, "asha@northwind.test", "Northwind Logistics")
    sales = next(d for d in before["departments"] if d["department"] == "Sales")
    # Vikram scored 4 + 4; five synthetic responders scored 3 each.
    assert sales["responded"] == 6
    assert sales["average_score"] == 3.29

    headers, _ = login(client, "vikram@northwind.test", "Northwind Logistics")
    client.delete("/reports/me", headers=headers)

    after = dashboard_for(client, "asha@northwind.test", "Northwind Logistics")
    sales = next(d for d in after["departments"] if d["department"] == "Sales")
    assert sales["responded"] == 5
    assert sales["average_score"] == 3.0


def test_delete_is_per_organization(client):
    add_response("ravi@consult.test", "Northwind Logistics", score=4)
    add_response("ravi@consult.test", "Bluepeak Retail", score=5)

    northwind_headers, _ = login(client, "ravi@consult.test", "Northwind Logistics")
    assert client.delete("/reports/me", headers=northwind_headers).status_code == 200
    assert client.get("/reports/me", headers=northwind_headers).json()["answered"] == 0

    bluepeak_headers, _ = login(client, "ravi@consult.test", "Bluepeak Retail")
    bluepeak = client.get("/reports/me", headers=bluepeak_headers).json()
    assert bluepeak["answered"] == 1
    assert bluepeak["average_score"] == 5.0
