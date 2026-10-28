from tests.conftest import login, add_responder


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
    # Every seeded department is below the small-group threshold and the
    # aggregate would carry only two responders, so nothing is shown.
    assert r.json()["departments"] == []


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
    # Four synthetic responders make Sales visible (Vikram + 4 = 5 responded).
    for i in range(4):
        add_responder("Northwind Logistics", "Sales", f"sales{i}@northwind.test", score=3)

    headers, _ = login(client, "asha@northwind.test", "Northwind Logistics")
    sales = departments_by_name(client, headers)["Sales"]

    # Vikram scored 4 + 4; the four added responders scored 3 each.
    # 20 points over 6 scored answers, not over 7 department members.
    assert sales["responded"] == 5
    assert sales["average_score"] == 3.33


def test_department_with_only_unscored_responses_is_not_assessed(client):
    # Five completed diagnostics whose scores all failed to parse.
    for i in range(5):
        add_responder("Northwind Logistics", "Engineering", f"eng{i}@northwind.test", score=None)

    headers, _ = login(client, "asha@northwind.test", "Northwind Logistics")
    engineering = departments_by_name(client, headers)["Engineering"]

    assert engineering["responded"] == 5
    assert engineering["average_score"] is None
    assert engineering["level"] == "Not assessed"


def test_report_and_dashboard_use_the_same_maturity_scale(client):
    headers, _ = login(client, "imran@northwind.test", "Northwind Logistics")
    answers = [
        {"question_id": "common-freq", "answer": "A few times a month"},  # 2
        {"question_id": "common-policy", "answer": "I think so, but I haven't read it"},  # 2
        {"question_id": "common-data", "answer": "Rarely"},  # 2
        {"question_id": "common-review", "answer": "Use it as is"},  # 1
        {"question_id": "mgr-adoption", "answer": "A few people, informally"},  # 2
    ]
    assert client.post("/diagnostic/submit", json={"answers": answers}, headers=headers).status_code == 200

    # Four synthetic responders bring HR to five responded and keep the
    # department average at 1.8: (9 + 4 * 1.8) / 9 scored answers.
    for i in range(4):
        add_responder("Northwind Logistics", "HR", f"hr{i}@northwind.test", score=1.8)

    report = client.get("/reports/me", headers=headers).json()
    assert report["average_score"] == 1.8
    assert report["level"] == "Beginner"

    admin_headers, _ = login(client, "asha@northwind.test", "Northwind Logistics")
    hr = departments_by_name(client, admin_headers)["HR"]
    assert hr["average_score"] == 1.8
    assert hr["level"] == report["level"]


def test_report_includes_stored_reason_per_answer(client):
    headers, _ = login(client, "priya@northwind.test", "Northwind Logistics")
    report = client.get("/reports/me", headers=headers).json()

    by_question = {a["question_id"]: a for a in report["answers"]}
    assert by_question["common-freq"]["score"] == 2
    assert by_question["common-open"]["score"] == 3
    assert by_question["common-open"]["reason"] == "Useful summary but shared customer data."


def test_submit_rejects_more_than_twenty_answers(client):
    headers, _ = login(client, "neha@northwind.test", "Northwind Logistics")
    answers = [{"question_id": "common-freq", "answer": "Daily"} for _ in range(21)]

    r = client.post("/diagnostic/submit", json={"answers": answers}, headers=headers)

    assert r.status_code == 422


def test_submit_rejects_an_oversized_answer(client):
    headers, _ = login(client, "neha@northwind.test", "Northwind Logistics")
    answers = [{"question_id": "common-open", "answer": "x" * 5001}]

    r = client.post("/diagnostic/submit", json={"answers": answers}, headers=headers)

    assert r.status_code == 422


def test_cannot_submit_a_question_for_another_role(client):
    headers, _ = login(client, "priya@northwind.test", "Northwind Logistics")

    r = client.post(
        "/diagnostic/submit",
        json={"answers": [{"question_id": "mgr-open", "answer": "Anything"}]},
        headers=headers,
    )

    assert r.status_code == 400


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
