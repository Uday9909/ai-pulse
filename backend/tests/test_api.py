from tests.conftest import login


def test_login_lists_organizations(client):
    _, data = login(client, "ravi@consult.test")
    names = {o["org_name"] for o in data["organizations"]}
    assert names == {"Northwind Logistics", "Bluepeak Retail"}


def test_employee_sees_questions(client):
    headers, _ = login(client, "priya@northwind.test", "Northwind Logistics")
    r = client.get("/diagnostic/questions", headers=headers)
    assert r.status_code == 200
    assert any(q["id"] == "sup-drafts" for q in r.json())


def test_admin_dashboard(client):
    headers, data = login(client, "asha@northwind.test", "Northwind Logistics")
    org_id = data["organizations"][0]["org_id"]
    r = client.get(f"/dashboard?org_id={org_id}", headers=headers)
    assert r.status_code == 200
    assert len(r.json()["departments"]) == 4


def test_admin_can_see_own_org(client):
    headers, data = login(client, "asha@northwind.test", "Northwind Logistics")
    org_id = data["organizations"][0]["org_id"]
    r = client.get(f"/dashboard?org_id={org_id}", headers=headers)
    assert r.status_code == 200
    assert "departments" in r.json()


def test_admin_cannot_see_other_org(client):
    # Asha is only a member of Northwind (org 1). Bluepeak is org 2.
    headers, _ = login(client, "asha@northwind.test", "Northwind Logistics")
    r = client.get("/dashboard?org_id=2", headers=headers)
    assert r.status_code == 403


def departments_by_name(client, headers):
    response = client.get("/dashboard?org_id=1", headers=headers).json()
    return {d["department"]: d for d in response["departments"]}


def test_department_average_divides_by_scored_responses(client):
    headers, _ = login(client, "asha@northwind.test", "Northwind Logistics")
    departments = departments_by_name(client, headers)

    # Priya answered two questions (2 and 3) out of three Support members.
    assert departments["Support"]["responded"] == 1
    assert departments["Support"]["average_score"] == 2.5

    # Vikram answered two questions (4 and 4) out of three Sales members.
    assert departments["Sales"]["average_score"] == 4.0


def test_department_without_responses_is_not_scored(client):
    headers, _ = login(client, "asha@northwind.test", "Northwind Logistics")
    engineering = departments_by_name(client, headers)["Engineering"]

    assert engineering["responded"] == 0
    assert engineering["average_score"] is None
    assert engineering["level"] == "Not assessed"


def test_select_org_rejects_non_member(client):
    headers, _ = login(client, "priya@northwind.test")
    r = client.post("/auth/select-org", json={"org_id": 2}, headers=headers)
    assert r.status_code == 403


def test_select_org_allows_multi_org_member(client):
    headers, data = login(client, "ravi@consult.test")
    bluepeak = next(o for o in data["organizations"] if o["org_name"] == "Bluepeak Retail")
    r = client.post("/auth/select-org", json={"org_id": bluepeak["org_id"]}, headers=headers)
    assert r.status_code == 200
    assert r.json()["org_id"] == bluepeak["org_id"]


def test_multi_org_admin_token_is_scoped_to_selected_org(client):
    # Ravi is an employee at Northwind and an admin at Bluepeak.
    headers, _ = login(client, "ravi@consult.test", "Bluepeak Retail")
    r = client.get("/dashboard?org_id=1", headers=headers)
    assert r.status_code == 403
