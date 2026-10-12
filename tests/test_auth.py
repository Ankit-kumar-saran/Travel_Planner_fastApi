def test_register_login_me(client):
    res = client.post("/auth/register", json={"name": "Asha", "email": "a@x.com", "password": "secret1"})
    assert res.status_code == 201
    assert res.json()["role"] == "user"
    assert "password" not in res.text and "password_hash" not in res.text

    token = client.post("/auth/login", json={"email": "a@x.com", "password": "secret1"}).json()["access_token"]
    me = client.get("/users/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200 and me.json()["email"] == "a@x.com"


def test_register_validation_and_duplicate(client):
    bad = client.post("/auth/register", json={"name": "A", "email": "nope", "password": "12"})
    assert bad.status_code == 422
    body = {"name": "Asha", "email": "a@x.com", "password": "secret1"}
    assert client.post("/auth/register", json=body).status_code == 201
    assert client.post("/auth/register", json=body).status_code == 400


def test_login_wrong_password_and_unknown_email(client):
    client.post("/auth/register", json={"name": "Asha", "email": "a@x.com", "password": "secret1"})
    assert client.post("/auth/login", json={"email": "a@x.com", "password": "wrong!!"}).status_code == 401
    assert client.post("/auth/login", json={"email": "zz@x.com", "password": "secret1"}).status_code == 401


def test_protected_route_needs_valid_token(client):
    assert client.get("/users/me").status_code == 401
    assert client.get("/users/me", headers={"Authorization": "Bearer garbage"}).status_code == 401


def test_admin_routes_blocked_for_normal_user(client, user_headers):
    assert client.get("/admin/overview", headers=user_headers).status_code == 403
    assert client.post("/cities", json={"name": "Goa"}, headers=user_headers).status_code == 403


def test_forgot_and_reset_password(client, db, capsys):
    client.post("/auth/register", json={"name": "Asha", "email": "a@x.com", "password": "oldpass1"})
    # Same answer for registered and unknown emails
    r1 = client.post("/auth/forgot-password", json={"email": "a@x.com"})
    r2 = client.post("/auth/forgot-password", json={"email": "nobody@x.com"})
    assert r1.status_code == r2.status_code == 200 and r1.json() == r2.json()

    # In dev mode (no SMTP) the link is printed; grab the token from it
    out = capsys.readouterr().out
    token = out.split("token=")[1].split()[0]

    assert client.post("/auth/reset-password", json={"token": "wrong", "new_password": "newpass1"}).status_code == 400
    assert client.post("/auth/reset-password", json={"token": token, "new_password": "newpass1"}).status_code == 200
    # Token is single-use
    assert client.post("/auth/reset-password", json={"token": token, "new_password": "again12"}).status_code == 400
    assert client.post("/auth/login", json={"email": "a@x.com", "password": "newpass1"}).status_code == 200
    assert client.post("/auth/login", json={"email": "a@x.com", "password": "oldpass1"}).status_code == 401


def test_expired_reset_token_rejected(client, db, capsys):
    client.post("/auth/register", json={"name": "Asha", "email": "a@x.com", "password": "oldpass1"})
    client.post("/auth/forgot-password", json={"email": "a@x.com"})
    token = capsys.readouterr().out.split("token=")[1].split()[0]
    with db.cursor() as cur:
        cur.execute("UPDATE password_resets SET expires_at = NOW() - INTERVAL 1 MINUTE")
    db.commit()
    assert client.post("/auth/reset-password", json={"token": token, "new_password": "newpass1"}).status_code == 400
