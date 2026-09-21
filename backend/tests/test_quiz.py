"""Tests for the beginner-mode financial starting-score quiz
(/api/v1/profile/quiz). Scoring must be deterministic and transparent -
every answer maps to a stated point value, never a black box."""


def test_get_quiz_questions_no_auth_required(client):
    resp = client.get("/api/v1/profile/quiz")
    assert resp.status_code == 200
    questions = resp.json()["data"]
    assert len(questions) == 6
    ids = {q["id"] for q in questions}
    assert ids == {"money_left", "emergency_fund", "debt", "regular_saving", "track_expenses", "has_goal"}


def test_submit_quiz_requires_authentication(client):
    resp = client.post("/api/v1/profile/quiz", json={"money_left": True})
    assert resp.status_code == 401


def test_quiz_best_case_answers_score_100(client, auth_headers):
    answers = {
        "money_left": True, "emergency_fund": True, "debt": False,
        "regular_saving": True, "track_expenses": True, "has_goal": True,
    }
    resp = client.post("/api/v1/profile/quiz", json=answers, headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()["data"]
    assert body["starting_score"] == 100
    assert "keep it up" in body["biggest_opportunity"].lower()


def test_quiz_worst_case_answers_score_floors_at_5(client, auth_headers):
    answers = {
        "money_left": False, "emergency_fund": False, "debt": True,
        "regular_saving": False, "track_expenses": False, "has_goal": False,
    }
    resp = client.post("/api/v1/profile/quiz", json=answers, headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()["data"]
    assert body["starting_score"] == 5
    assert "emergency fund" in body["biggest_opportunity"].lower()


def test_quiz_score_never_below_zero_or_above_100(client, auth_headers):
    resp = client.post("/api/v1/profile/quiz", json={
        "money_left": False, "emergency_fund": False, "debt": True,
        "regular_saving": False, "track_expenses": False, "has_goal": False,
    }, headers=auth_headers)
    score = resp.json()["data"]["starting_score"]
    assert 0 <= score <= 100


def test_quiz_empty_submission_uses_false_defaults(client, auth_headers):
    resp = client.post("/api/v1/profile/quiz", json={}, headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()["data"]
    # base 40, all defaults False: -5 -10 +5(no debt) -5 -5 +0 = 20
    assert body["starting_score"] == 20
    assert len(body["breakdown"]) == 6


def test_quiz_partial_submission_only_answered_keys_override_defaults(client, auth_headers):
    resp = client.post("/api/v1/profile/quiz", json={"money_left": True, "emergency_fund": True}, headers=auth_headers)
    assert resp.status_code == 200
    # 40 +15 +15 +5(debt default) -5 -5 +0 = 65
    assert resp.json()["data"]["starting_score"] == 65


def test_quiz_unknown_keys_are_ignored_not_rejected(client, auth_headers):
    resp = client.post("/api/v1/profile/quiz", json={"money_left": True, "not_a_real_question": True}, headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()["data"]
    assert len(body["breakdown"]) == 6  # only the 6 real questions scored
    assert body["starting_score"] == 40  # 40 +15(money_left) +5 -10 -5 -5 +0


def test_quiz_rejects_non_coercible_string_value(client, auth_headers):
    resp = client.post("/api/v1/profile/quiz", json={"money_left": "maybe"}, headers=auth_headers)
    assert resp.status_code == 422


def test_quiz_rejects_malformed_json_body(client, auth_headers):
    resp = client.post(
        "/api/v1/profile/quiz",
        headers={**auth_headers, "Content-Type": "application/json"},
        content=b"not valid json",
    )
    assert resp.status_code == 422


def test_quiz_rejects_missing_body(client, auth_headers):
    resp = client.post("/api/v1/profile/quiz", headers=auth_headers)
    assert resp.status_code == 422


def test_quiz_breakdown_every_answer_has_a_stated_reason(client, auth_headers):
    """Transparency requirement: every scored question shows its own point
    contribution, never an unexplained aggregate number."""
    resp = client.post("/api/v1/profile/quiz", json={"money_left": True}, headers=auth_headers)
    breakdown = resp.json()["data"]["breakdown"]
    for item in breakdown:
        assert "question" in item and "answer" in item and "points" in item
        assert isinstance(item["points"], int)


def test_quiz_biggest_opportunity_targets_first_unmet_priority(client, auth_headers):
    """Priority order: emergency fund > tracking > regular saving > goal."""
    resp = client.post("/api/v1/profile/quiz", json={
        "money_left": True, "emergency_fund": False, "debt": False,
        "regular_saving": True, "track_expenses": True, "has_goal": True,
    }, headers=auth_headers)
    assert "emergency fund" in resp.json()["data"]["biggest_opportunity"].lower()

    resp2 = client.post("/api/v1/profile/quiz", json={
        "money_left": True, "emergency_fund": True, "debt": False,
        "regular_saving": True, "track_expenses": False, "has_goal": True,
    }, headers=auth_headers)
    assert "tracking" in resp2.json()["data"]["biggest_opportunity"].lower() or "track" in resp2.json()["data"]["biggest_opportunity"].lower()
