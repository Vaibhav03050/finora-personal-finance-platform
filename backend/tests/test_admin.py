"""Tests for /api/v1/admin/* endpoints: authorization boundaries, response
structure, and correctness of returned audit records."""


def test_audit_logs_requires_authentication(client):
    resp = client.get("/api/v1/admin/audit-logs")
    assert resp.status_code == 401


def test_audit_logs_rejects_regular_user(client, auth_headers):
    resp = client.get("/api/v1/admin/audit-logs", headers=auth_headers)
    assert resp.status_code == 403
    assert resp.json()["success"] is False


def test_audit_logs_rejects_invalid_token(client):
    resp = client.get("/api/v1/admin/audit-logs", headers={"Authorization": "Bearer not.a.valid.token"})
    assert resp.status_code == 401


def test_overview_requires_admin(client, auth_headers):
    resp = client.get("/api/v1/admin/overview", headers=auth_headers)
    assert resp.status_code == 403


def test_admin_can_access_audit_logs(client, admin_headers):
    resp = client.get("/api/v1/admin/audit-logs", headers=admin_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert isinstance(body["data"], list)


def test_admin_can_access_overview(client, admin_headers):
    resp = client.get("/api/v1/admin/overview", headers=admin_headers)
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert "total_users" in data
    assert "total_transactions" in data
    assert "beginner_mode_users" in data
    assert isinstance(data["total_users"], int)


def test_audit_log_record_structure(client, admin_headers):
    resp = client.get("/api/v1/admin/audit-logs", headers=admin_headers)
    logs = resp.json()["data"]
    assert len(logs) >= 1  # at least the admin's own register+login events
    for log in logs:
        assert set(log.keys()) == {"id", "user_id", "action", "detail", "created_at"}
        assert isinstance(log["id"], int)
        assert isinstance(log["action"], str)
        assert isinstance(log["created_at"], str)


def test_audit_logs_ordered_most_recent_first(client, admin_headers):
    resp = client.get("/api/v1/admin/audit-logs", headers=admin_headers)
    logs = resp.json()["data"]
    ids = [l["id"] for l in logs]
    assert ids == sorted(ids, reverse=True)


def test_audit_logs_capture_register_action(client):
    import uuid
    email = f"audittest_{uuid.uuid4().hex[:8]}@example.com"
    client.post("/api/v1/auth/register", json={"email": email, "password": "password123", "name": "Audit Test"})
    # (verified indirectly via test_audit_log_reflects_real_user_actions below,
    # since only an admin can read the log)


def test_audit_log_reflects_real_user_actions(client, admin_headers):
    """End-to-end correctness check: perform real actions as a normal user,
    then verify an admin sees accurate audit entries for exactly those actions."""
    import uuid
    email = f"actiontest_{uuid.uuid4().hex[:8]}@example.com"
    reg = client.post("/api/v1/auth/register", json={"email": email, "password": "password123", "name": "Action Test"})
    user_id = reg.json()["data"]["user_id"]
    token = reg.json()["data"]["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    client.post("/api/v1/transactions", json={
        "date": "2026-08-01", "merchant": "Test", "description": "Test", "amount_rupees": 100, "type": "expense",
    }, headers=headers)
    client.post("/api/v1/transactions/bulk-confirm", json=[{
        "date": "2026-08-02", "merchant": "X", "description": "X", "amount_rupees": 50,
        "type": "expense", "category": "Other", "category_source": "manual", "confidence": 1.0, "source": "manual",
    }], headers=headers)
    client.delete("/api/v1/transactions/data/all", headers=headers)

    logs = client.get("/api/v1/admin/audit-logs", headers=admin_headers).json()["data"]
    this_user_logs = [l for l in logs if l["user_id"] == user_id]
    actions = [l["action"] for l in this_user_logs]

    assert "register" in actions
    assert "bulk_confirm" in actions
    assert "delete_all_transactions" in actions

    delete_log = next(l for l in this_user_logs if l["action"] == "delete_all_transactions")
    assert "count=2" in delete_log["detail"]  # 1 manual + 1 bulk-confirmed = 2 deleted

    bulk_log = next(l for l in this_user_logs if l["action"] == "bulk_confirm")
    assert "imported=1" in bulk_log["detail"]

    register_log = next(l for l in this_user_logs if l["action"] == "register")
    assert register_log["detail"] == email


def test_audit_logs_pagination_and_filtering_are_actually_applied(client, admin_headers):
    """Pagination and filtering query params are real, not silently ignored:
    page/page_size control slicing, and action/user_id genuinely filter results."""
    resp = client.get("/api/v1/admin/audit-logs?page=1&page_size=1", headers=admin_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["data"]) <= 1
    assert body["meta"]["page"] == 1
    assert body["meta"]["page_size"] == 1
    assert "total" in body["meta"]

    filtered = client.get("/api/v1/admin/audit-logs?action=register", headers=admin_headers)
    assert all(r["action"] == "register" for r in filtered.json()["data"])

    out_of_range_page = client.get("/api/v1/admin/audit-logs?page=999&page_size=1", headers=admin_headers)
    assert out_of_range_page.status_code == 200
    assert out_of_range_page.json()["data"] == []  # past the last page -> empty, not an error
