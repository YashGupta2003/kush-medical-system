"""
Integration tests hitting real HTTP endpoints via FastAPI's TestClient -
these confirm login works end-to-end and that Owner-vs-Staff access
control is actually enforced at the API layer, not just in theory.
"""


def test_login_with_correct_credentials_returns_token(client, owner_user):
    response = client.post("/auth/login", json={"username": "owner1", "password": "ownerpass123"})
    assert response.status_code == 200
    body = response.json()
    assert body["role"] == "owner"
    assert "access_token" in body and len(body["access_token"]) > 10


def test_login_with_wrong_password_is_rejected(client, owner_user):
    response = client.post("/auth/login", json={"username": "owner1", "password": "wrongpassword"})
    assert response.status_code == 401


def test_login_with_unknown_username_is_rejected(client):
    response = client.post("/auth/login", json={"username": "nobody", "password": "whatever"})
    assert response.status_code == 401


def test_protected_endpoint_rejects_requests_with_no_token(client):
    response = client.get("/bills")
    assert response.status_code == 401


def test_protected_endpoint_rejects_garbage_token(client):
    response = client.get("/bills", headers={"Authorization": "Bearer not-a-real-token"})
    assert response.status_code == 401


def test_protected_endpoint_works_with_a_valid_token(client, owner_headers):
    response = client.get("/bills", headers=owner_headers)
    assert response.status_code == 200


def test_owner_only_endpoint_blocks_staff_with_403(client, staff_headers):
    response = client.get("/analytics/overview", headers=staff_headers)
    assert response.status_code == 403


def test_owner_only_endpoint_allows_owner(client, owner_headers):
    response = client.get("/analytics/overview", headers=owner_headers)
    assert response.status_code == 200


def test_gst_report_is_owner_only(client, staff_headers, owner_headers):
    staff_response = client.get("/gst/report", headers=staff_headers)
    owner_response = client.get("/gst/report", headers=owner_headers)
    assert staff_response.status_code == 403
    assert owner_response.status_code == 200


def test_deactivated_account_cannot_log_in(client, db_session, owner_user):
    from app.services.auth_service import authenticate_user
    owner_user.is_active = False
    db_session.commit()

    response = client.post("/auth/login", json={"username": "owner1", "password": "ownerpass123"})
    assert response.status_code == 401


def test_staff_cannot_create_new_users(client, staff_headers):
    response = client.post(
        "/auth/users",
        json={"username": "newstaff", "password": "password123", "role": "staff"},
        headers=staff_headers,
    )
    assert response.status_code == 403


def test_owner_can_create_a_new_staff_account(client, owner_headers):
    response = client.post(
        "/auth/users",
        json={"username": "newstaff", "password": "password123", "role": "staff", "full_name": "New Staff"},
        headers=owner_headers,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["username"] == "newstaff"
    assert body["role"] == "staff"


def test_cannot_create_duplicate_username(client, owner_headers, owner_user):
    response = client.post(
        "/auth/users",
        json={"username": "owner1", "password": "password123", "role": "staff"},
        headers=owner_headers,
    )
    assert response.status_code == 400