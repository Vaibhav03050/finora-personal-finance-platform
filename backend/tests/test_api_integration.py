def test_register_and_login_flow(client):
    resp = client.post("/api/v1/auth/register", json={"email": "flow_test@example.com", "password": "password123", "name": "Flow"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert "access_token" in body["data"]
    # Regression test: TokenResponse must include email so the frontend can
    # populate Settings > Profile immediately, without waiting for a page
    # reload to trigger a separate /auth/me call.
    assert body["data"]["email"] == "flow_test@example.com"
    assert body["data"]["name"] == "Flow"

    resp2 = client.post("/api/v1/auth/login", json={"email": "flow_test@example.com", "password": "password123"})
    assert resp2.status_code == 200
    assert resp2.json()["data"]["access_token"]
    assert resp2.json()["data"]["email"] == "flow_test@example.com"


def test_login_wrong_password_rejected(client):
    client.post("/api/v1/auth/register", json={"email": "wrongpw@example.com", "password": "password123"})
    resp = client.post("/api/v1/auth/login", json={"email": "wrongpw@example.com", "password": "nope12345"})
    assert resp.status_code == 401


def test_duplicate_registration_rejected(client):
    client.post("/api/v1/auth/register", json={"email": "dupe@example.com", "password": "password123"})
    resp = client.post("/api/v1/auth/register", json={"email": "dupe@example.com", "password": "password123"})
    assert resp.status_code == 409


def test_transactions_require_authentication(client):
    resp = client.get("/api/v1/transactions")
    assert resp.status_code == 401


def test_create_and_list_transaction(client, auth_headers):
    resp = client.post("/api/v1/transactions", json={
        "date": "2026-01-05", "merchant": "Amazon", "description": "Amazon order",
        "amount_rupees": 1299, "type": "expense",
    }, headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["amount_rupees"] == 1299.0
    assert data["category"] == "Shopping"
    assert data["category_source"] == "rule"

    listing = client.get("/api/v1/transactions", headers=auth_headers)
    assert listing.status_code == 200
    assert listing.json()["meta"]["total"] >= 1


def test_categorization_uses_merchant_when_description_is_generic(client, auth_headers):
    """Regression test: merchant='Amazon', description='Shopping' should still
    categorize as Shopping via the merchant keyword, not fall through to a
    generic ML guess just because the description itself has no merchant keyword."""
    resp = client.post("/api/v1/transactions", json={
        "date": "2026-01-05", "merchant": "Amazon", "description": "Shopping",
        "amount_rupees": 1500, "type": "expense",
    }, headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["category"] == "Shopping"
    assert data["category_source"] == "rule"


def test_duplicate_transaction_not_double_counted(client, auth_headers):
    payload = {"date": "2026-02-01", "merchant": "Uber", "description": "Uber ride", "amount_rupees": 320, "type": "expense"}
    r1 = client.post("/api/v1/transactions", json=payload, headers=auth_headers)
    r2 = client.post("/api/v1/transactions", json=payload, headers=auth_headers)
    assert r1.status_code == 200 and r2.status_code == 200
    assert r2.json()["meta"].get("duplicate") is True
    assert r1.json()["data"]["id"] == r2.json()["data"]["id"]


def test_update_and_delete_transaction(client, auth_headers):
    create = client.post("/api/v1/transactions", json={
        "date": "2026-03-01", "merchant": "TestShop", "description": "test", "amount_rupees": 500, "type": "expense",
    }, headers=auth_headers)
    txn_id = create.json()["data"]["id"]

    update = client.put(f"/api/v1/transactions/{txn_id}", json={"category": "Home"}, headers=auth_headers)
    assert update.status_code == 200
    assert update.json()["data"]["category"] == "Home"
    assert update.json()["data"]["category_source"] == "manual"

    delete = client.delete(f"/api/v1/transactions/{txn_id}", headers=auth_headers)
    assert delete.status_code == 200


def test_cannot_access_another_users_transaction(client):
    client.post("/api/v1/auth/register", json={"email": "user_a@example.com", "password": "password123"})
    login_a = client.post("/api/v1/auth/login", json={"email": "user_a@example.com", "password": "password123"})
    headers_a = {"Authorization": f"Bearer {login_a.json()['data']['access_token']}"}

    txn = client.post("/api/v1/transactions", json={
        "date": "2026-01-01", "merchant": "X", "description": "x", "amount_rupees": 100, "type": "expense",
    }, headers=headers_a)
    txn_id = txn.json()["data"]["id"]

    client.post("/api/v1/auth/register", json={"email": "user_b@example.com", "password": "password123"})
    login_b = client.post("/api/v1/auth/login", json={"email": "user_b@example.com", "password": "password123"})
    headers_b = {"Authorization": f"Bearer {login_b.json()['data']['access_token']}"}

    resp = client.delete(f"/api/v1/transactions/{txn_id}", headers=headers_b)
    assert resp.status_code == 404  # not visible to other users


def test_cannot_edit_another_users_transaction(client):
    """Regression coverage for the PUT endpoint specifically, since it's now
    wired to the frontend's Edit action - the existing cross-user test only
    covered DELETE."""
    client.post("/api/v1/auth/register", json={"email": "edit_user_a@example.com", "password": "password123"})
    login_a = client.post("/api/v1/auth/login", json={"email": "edit_user_a@example.com", "password": "password123"})
    headers_a = {"Authorization": f"Bearer {login_a.json()['data']['access_token']}"}

    txn = client.post("/api/v1/transactions", json={
        "date": "2026-01-01", "merchant": "Original", "description": "x", "amount_rupees": 100, "type": "expense",
    }, headers=headers_a)
    txn_id = txn.json()["data"]["id"]

    client.post("/api/v1/auth/register", json={"email": "edit_user_b@example.com", "password": "password123"})
    login_b = client.post("/api/v1/auth/login", json={"email": "edit_user_b@example.com", "password": "password123"})
    headers_b = {"Authorization": f"Bearer {login_b.json()['data']['access_token']}"}

    resp = client.put(f"/api/v1/transactions/{txn_id}", json={"merchant": "Hacked"}, headers=headers_b)
    assert resp.status_code == 404

    # confirm it truly wasn't modified
    check = client.get("/api/v1/transactions", headers=headers_a)
    txn_after = next(t for t in check.json()["data"] if t["id"] == txn_id)
    assert txn_after["merchant"] == "Original"


def test_edit_transaction_updates_all_editable_fields(client, auth_headers):
    """Confirms the full field set the frontend edit form sends round-trips correctly."""
    txn = client.post("/api/v1/transactions", json={
        "date": "2026-01-01", "merchant": "Old Merchant", "description": "old desc",
        "amount_rupees": 100, "type": "expense", "category": "Other",
    }, headers=auth_headers)
    txn_id = txn.json()["data"]["id"]

    resp = client.put(f"/api/v1/transactions/{txn_id}", json={
        "date": "2026-02-15", "merchant": "New Merchant", "description": "new desc",
        "amount_rupees": 250.50, "type": "income", "category": "Income",
    }, headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["date"] == "2026-02-15"
    assert data["merchant"] == "New Merchant"
    assert data["description"] == "new desc"
    assert data["amount_rupees"] == 250.50
    assert data["type"] == "income"
    assert data["category"] == "Income"
    assert data["category_source"] == "manual"  # manual category override tracked correctly


def test_goal_lifecycle_and_plan(client, auth_headers):
    create = client.post("/api/v1/goals", json={
        "name": "Laptop", "category": "Laptop", "target_amount_rupees": 60000,
        "target_date": "2026-12-01", "current_saved_rupees": 10000,
    }, headers=auth_headers)
    assert create.status_code == 200
    goal_id = create.json()["data"]["id"]
    assert create.json()["data"]["achieved"] is False

    plan = client.get(f"/api/v1/goals/{goal_id}/plan", headers=auth_headers)
    assert plan.status_code == 200
    plan_data = plan.json()["data"]
    assert plan_data["status"] == "in_progress"
    assert plan_data["required_monthly_rupees"] > 0
    assert "required_monthly_minor" not in plan_data  # key naming bug regression check


def test_multiple_goals_can_be_created_and_listed(client, auth_headers):
    """Regression test: a user can create multiple independent goals."""
    for name, category, amount in [
        ("Laptop", "Laptop", 60000),
        ("Trip", "Travel", 30000),
        ("Emergency Fund", "Emergency Fund", 100000),
    ]:
        resp = client.post("/api/v1/goals", json={
            "name": name, "category": category, "target_amount_rupees": amount,
            "target_date": "2027-12-01", "current_saved_rupees": 0,
        }, headers=auth_headers)
        assert resp.status_code == 200

    listing = client.get("/api/v1/goals", headers=auth_headers)
    assert listing.status_code == 200
    names = {g["name"] for g in listing.json()["data"]}
    assert {"Laptop", "Trip", "Emergency Fund"}.issubset(names)


def test_goal_created_already_achieved_is_flagged_immediately(client, auth_headers):
    """Regression test: creating a goal where current_saved already meets/exceeds
    the target must set achieved=True right away, not just on a later update -
    otherwise it would incorrectly show up as an 'active' goal on the dashboard."""
    create = client.post("/api/v1/goals", json={
        "name": "Emergency Fund", "category": "Emergency Fund", "target_amount_rupees": 50000,
        "target_date": "2027-01-01", "current_saved_rupees": 55000,
    }, headers=auth_headers)
    assert create.status_code == 200
    assert create.json()["data"]["achieved"] is True

    goal_id = create.json()["data"]["id"]
    plan = client.get(f"/api/v1/goals/{goal_id}/plan", headers=auth_headers)
    assert plan.json()["data"]["status"] == "achieved"


def test_goal_deadline_already_passed(client, auth_headers):
    create = client.post("/api/v1/goals", json={
        "name": "Old Goal", "category": "Custom", "target_amount_rupees": 20000,
        "target_date": "2020-01-01", "current_saved_rupees": 5000,
    }, headers=auth_headers)
    goal_id = create.json()["data"]["id"]
    plan = client.get(f"/api/v1/goals/{goal_id}/plan", headers=auth_headers)
    assert plan.json()["data"]["status"] == "deadline_passed"


def test_goal_zero_target_amount_rejected(client, auth_headers):
    resp = client.post("/api/v1/goals", json={
        "name": "Bad Goal", "category": "Custom", "target_amount_rupees": 0,
        "target_date": "2027-01-01", "current_saved_rupees": 0,
    }, headers=auth_headers)
    assert resp.status_code == 422


def test_natural_language_parse_endpoint(client, auth_headers):
    resp = client.post("/api/v1/transactions/parse-natural-language", json={"text": "Spent 250 on lunch"}, headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["meta"]["parsed"] is True
    assert body["data"]["amount_rupees"] == 250.0


def test_delete_all_data_privacy_control(client, auth_headers):
    client.post("/api/v1/transactions", json={
        "date": "2026-01-01", "merchant": "X", "description": "x", "amount_rupees": 100, "type": "expense",
    }, headers=auth_headers)
    resp = client.delete("/api/v1/transactions/data/all", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["data"]["deleted"] >= 1

    listing = client.get("/api/v1/transactions", headers=auth_headers)
    assert listing.json()["meta"]["total"] == 0


def test_simulator_endpoint_returns_illustrative_disclaimer(client):
    resp = client.post("/api/v1/simulator/compound-growth", json={
        "monthly_contribution_rupees": 5000, "years": 10, "annual_return_pct": 10,
    })
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert "not guaranteed" in data["disclaimer"].lower()
    assert data["future_value_rupees"] > data["total_contribution_rupees"]


def test_assistant_works_without_ai_key_configured(client, auth_headers):
    resp = client.post("/api/v1/assistant/ask", json={"question": "What is an emergency fund?"}, headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()["data"]
    assert body["source"] == "template"
    assert len(body["answer"]) > 0


def test_audit_logs_filter_by_nonexistent_action_returns_empty(client, admin_headers):
    resp = client.get("/api/v1/admin/audit-logs?action=totally_made_up_action_xyz", headers=admin_headers)
    assert resp.status_code == 200
    assert resp.json()["data"] == []
    assert resp.json()["meta"]["total"] == 0


def test_audit_logs_filter_by_user_id_returns_only_that_users_records(client, auth_headers, admin_headers):
    me_resp = client.get("/api/v1/auth/me", headers=auth_headers)
    my_id = me_resp.json()["data"]["id"]
    resp = client.get(f"/api/v1/admin/audit-logs?user_id={my_id}", headers=admin_headers)
    assert resp.status_code == 200
    assert all(r["user_id"] == my_id for r in resp.json()["data"])


def test_audit_logs_page_size_over_max_rejected(client, admin_headers):
    resp = client.get("/api/v1/admin/audit-logs?page_size=500", headers=admin_headers)
    assert resp.status_code == 422


def test_audit_logs_invalid_page_number_rejected(client, admin_headers):
    resp = client.get("/api/v1/admin/audit-logs?page=0", headers=admin_headers)
    assert resp.status_code == 422


def test_health_endpoints(client):
    assert client.get("/healthz").status_code == 200
    assert client.get("/readyz").status_code == 200
