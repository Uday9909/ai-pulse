from tests.conftest import login, add_responder, add_response

SMALL_GROUP_MIN_RESPONDENTS = 5


def dashboard_for(client, email, org_name):
    headers, data = login(client, email, org_name)
    org_id = next(o["org_id"] for o in data["organizations"] if o["org_name"] == org_name)
    return client.get(f"/dashboard?org_id={org_id}", headers=headers).json()


def test_small_department_is_hidden(client):
    data = dashboard_for(client, "asha@northwind.test", "Northwind Logistics")
    names = {d["department"] for d in data["departments"]}

    # Every seeded department is under five respondents.
    assert names == {"Other teams"}
    other = data["departments"][0]
    # Sales 3 + Support 3 + Engineering 2 + HR 2 (includes Ravi).
    assert other["employees"] == 10
    assert other["responded"] == 2


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
