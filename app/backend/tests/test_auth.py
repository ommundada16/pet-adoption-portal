from mysql.connector import IntegrityError
from werkzeug.security import generate_password_hash

from .conftest import make_token


def test_register_user_success(client, db):
    r = client.post("/api/users/register", json={"name": "A", "email": "a@x.com", "password": "pw", "phone": "9876543210"})
    assert r.status_code == 201 and r.get_json()["user_id"] == 42 and db.committed


def test_register_password_is_hashed(client, db):
    client.post("/api/users/register", json={"name": "A", "email": "a@x.com", "password": "secret"})
    stored = db.executed[0][1][2]
    assert stored != "secret" and stored.startswith(("scrypt", "pbkdf2"))


def test_register_missing_fields_400(client, db):
    r = client.post("/api/users/register", json={"name": "A"})
    assert r.status_code == 400 and "email" in r.get_json()["error"]


def test_register_non_json_body_400(client, db):
    assert client.post("/api/users/register", data="nope").status_code == 400


def test_register_bad_phone_400(client, db):
    r = client.post("/api/users/register", json={"name": "A", "email": "a@x.com", "password": "p", "phone": "123"})
    assert r.status_code == 400


def test_register_duplicate_email_409(client, db):
    db.raise_on_execute = IntegrityError("dup")
    r = client.post("/api/users/register", json={"name": "A", "email": "a@x.com", "password": "p"})
    assert r.status_code == 409


def test_register_shelter_success_and_duplicate(client, db):
    ok = client.post("/api/shelters/register", json={"name": "S", "email": "s@x.com", "password": "p", "address": "Pune"})
    assert ok.status_code == 201 and ok.get_json()["shelter_id"] == 42
    db.raise_on_execute = IntegrityError("dup")
    dup = client.post("/api/shelters/register", json={"name": "S", "email": "s@x.com", "password": "p"})
    assert dup.status_code == 409


def test_register_shelter_validation(client, db):
    assert client.post("/api/shelters/register", json={"name": "S"}).status_code == 400
    bad = client.post("/api/shelters/register", json={"name": "S", "email": "e", "password": "p", "phone": "12"})
    assert bad.status_code == 400


def test_login_user_success_returns_token(client, db):
    db.fetchone_queue.append({"user_id": 3, "name": "Asha", "password": generate_password_hash("pw")})
    r = client.post("/api/users/login", json={"email": "a@x.com", "password": "pw"})
    assert r.status_code == 200 and r.get_json()["token"] and r.get_json()["name"] == "Asha"


def test_login_user_wrong_password_401(client, db):
    db.fetchone_queue.append({"user_id": 3, "name": "Asha", "password": generate_password_hash("pw")})
    assert client.post("/api/users/login", json={"email": "a@x.com", "password": "bad"}).status_code == 401


def test_login_unknown_user_401(client, db):
    assert client.post("/api/users/login", json={"email": "z@x.com", "password": "pw"}).status_code == 401


def test_login_missing_fields_400(client, db):
    assert client.post("/api/users/login", json={"email": "a@x.com"}).status_code == 400
    assert client.post("/api/shelters/login", json={}).status_code == 400


def test_login_shelter_success_and_failure(client, db):
    db.fetchone_queue.append({"shelter_id": 1, "name": "S", "password": generate_password_hash("pw")})
    assert client.post("/api/shelters/login", json={"email": "s@x.com", "password": "pw"}).status_code == 200
    assert client.post("/api/shelters/login", json={"email": "s@x.com", "password": "pw"}).status_code == 401


def test_protected_route_requires_token(client):
    assert client.get("/api/pets/my-pets").status_code == 401


def test_protected_route_rejects_garbage_and_expired_token(client):
    assert client.get("/api/pets/my-pets", headers={"Authorization": "Bearer garbage"}).status_code == 401
    expired = make_token("shelter", 1, hours=-1)
    assert client.get("/api/pets/my-pets", headers={"Authorization": f"Bearer {expired}"}).status_code == 401
