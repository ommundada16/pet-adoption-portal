def test_create_request_marks_pet_pending(client, db, user_auth):
    db.fetchone_queue.append({"status": "Available"})
    r = client.post("/api/adoption-requests", json={"pet_id": 3}, headers=user_auth)
    assert r.status_code == 201
    assert any("SET status = 'Pending'" in s for s, _ in db.executed)


def test_create_request_guards(client, db, user_auth, shelter_auth):
    assert client.post("/api/adoption-requests", json={"pet_id": 3}, headers=shelter_auth).status_code == 403
    assert client.post("/api/adoption-requests", json={}, headers=user_auth).status_code == 400
    assert client.post("/api/adoption-requests", json={"pet_id": 3}, headers=user_auth).status_code == 404
    db.fetchone_queue.append({"status": "Adopted"})
    assert client.post("/api/adoption-requests", json={"pet_id": 3}, headers=user_auth).status_code == 409


def test_my_requests(client, db, user_auth):
    db.fetchall_queue.append([{"request_id": 1}])
    assert client.get("/api/adoption-requests/my-requests", headers=user_auth).get_json() == [{"request_id": 1}]


def test_shelter_requests(client, db, shelter_auth, user_auth):
    db.fetchall_queue.append([{"request_id": 1}])
    assert client.get("/api/adoption-requests/shelter-requests", headers=shelter_auth).status_code == 200
    assert client.get("/api/adoption-requests/shelter-requests", headers=user_auth).status_code == 403


def test_approve_marks_pet_adopted(client, db, shelter_auth):
    db.fetchone_queue.append({"pet_id": 3, "shelter_id": 1})
    r = client.put("/api/adoption-requests/9", json={"status": "Approved"}, headers=shelter_auth)
    assert r.status_code == 200 and db.executed[-1][1] == ("Adopted", 3)


def test_reject_makes_pet_available_again(client, db, shelter_auth):
    db.fetchone_queue.append({"pet_id": 3, "shelter_id": 1})
    client.put("/api/adoption-requests/9", json={"status": "Rejected"}, headers=shelter_auth)
    assert db.executed[-1][1] == ("Available", 3)


def test_update_request_guards(client, db, shelter_auth, user_auth):
    assert client.put("/api/adoption-requests/9", json={"status": "Approved"}, headers=user_auth).status_code == 403
    assert client.put("/api/adoption-requests/9", json={"status": "Hacked"}, headers=shelter_auth).status_code == 400
    assert client.put("/api/adoption-requests/9", json={"status": "Approved"}, headers=shelter_auth).status_code == 404
    db.fetchone_queue.append({"pet_id": 3, "shelter_id": 2})  # belongs to another shelter
    assert client.put("/api/adoption-requests/9", json={"status": "Approved"}, headers=shelter_auth).status_code == 403


def test_cancel_request_paths(client, db, user_auth, shelter_auth):
    assert client.delete("/api/adoption-requests/9", headers=shelter_auth).status_code == 403
    assert client.delete("/api/adoption-requests/9", headers=user_auth).status_code == 404
    db.fetchone_queue.append({"user_id": 99, "pet_id": 3, "status": "Pending"})
    assert client.delete("/api/adoption-requests/9", headers=user_auth).status_code == 403
    db.fetchone_queue.append({"user_id": 7, "pet_id": 3, "status": "Approved"})
    assert client.delete("/api/adoption-requests/9", headers=user_auth).status_code == 400
    db.fetchone_queue.append({"user_id": 7, "pet_id": 3, "status": "Pending"})
    assert client.delete("/api/adoption-requests/9", headers=user_auth).status_code == 200
    assert db.executed[-1][1] == (3,)
