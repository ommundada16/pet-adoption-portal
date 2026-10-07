import io

import app as app_module


def test_list_pets_no_filter(client, db):
    db.fetchall_queue.append([{"pet_id": 1, "name": "Bruno"}])
    r = client.get("/api/pets")
    assert r.status_code == 200 and r.get_json()[0]["name"] == "Bruno"
    assert "p.species" not in db.executed[0][0]


def test_list_pets_filters_are_parameterised(client, db):
    client.get("/api/pets?species=Dog&adopted=no")
    sql, params = db.executed[0]
    assert "p.species = %s" in sql and params == ("Dog",) and "!= 'Adopted'" in sql
    client.get("/api/pets?adopted=yes")
    assert "= 'Adopted'" in db.executed[1][0]


def test_species_filter_is_not_vulnerable_to_sql_injection(client, db):
    client.get("/api/pets?species=Dog'%20OR%20'1'='1")
    sql, params = db.executed[0]
    assert "OR" not in sql and "OR '1'='1" in params[0]


def test_get_pet_found_and_missing(client, db):
    db.fetchone_queue.append({"pet_id": 1, "name": "Bruno"})
    assert client.get("/api/pets/1").status_code == 200
    assert client.get("/api/pets/999").status_code == 404


def test_add_pet_requires_shelter_role(client, db, user_auth):
    r = client.post("/api/pets", json={"name": "A", "species": "Dog"}, headers=user_auth)
    assert r.status_code == 403


def test_add_pet_uses_shelter_id_from_token(client, db, shelter_auth):
    r = client.post("/api/pets", json={"name": "Rex", "species": "Dog", "shelter_id": 999}, headers=shelter_auth)
    assert r.status_code == 201 and r.get_json()["pet_id"] == 42
    assert db.executed[0][1][0] == 1  # token's shelter, not the spoofed body value


def test_add_pet_missing_fields_400(client, db, shelter_auth):
    assert client.post("/api/pets", json={"name": "Rex"}, headers=shelter_auth).status_code == 400


def test_my_pets(client, db, shelter_auth, user_auth):
    db.fetchall_queue.append([{"pet_id": 1}])
    assert client.get("/api/pets/my-pets", headers=shelter_auth).get_json() == [{"pet_id": 1}]
    assert client.get("/api/pets/my-pets", headers=user_auth).status_code == 403


def test_update_pet_paths(client, db, shelter_auth, user_auth):
    assert client.put("/api/pets/1", json={"status": "Adopted"}, headers=user_auth).status_code == 403
    assert client.put("/api/pets/1", json={"status": "Adopted"}, headers=shelter_auth).status_code == 404
    db.fetchone_queue.append({"shelter_id": 2})
    assert client.put("/api/pets/1", json={"name": "x"}, headers=shelter_auth).status_code == 403
    db.fetchone_queue.append({"shelter_id": 1})
    assert client.put("/api/pets/1", json={"bogus": 1}, headers=shelter_auth).status_code == 400
    db.fetchone_queue.append({"shelter_id": 1})
    ok = client.put("/api/pets/1", json={"name": "New", "status": "Adopted", "evil": "x"}, headers=shelter_auth)
    assert ok.status_code == 200
    sql, params = db.executed[-1]
    assert "evil" not in sql and params == ("New", "Adopted", 1)  # unknown fields are ignored


def test_delete_pet_paths(client, db, shelter_auth, user_auth):
    assert client.delete("/api/pets/1", headers=user_auth).status_code == 403
    assert client.delete("/api/pets/1", headers=shelter_auth).status_code == 404
    db.fetchone_queue.append({"shelter_id": 2, "image_filename": None})
    assert client.delete("/api/pets/1", headers=shelter_auth).status_code == 403
    db.fetchone_queue.append({"shelter_id": 1, "image_filename": None})
    assert client.delete("/api/pets/1", headers=shelter_auth).status_code == 200
    assert any("DELETE FROM adoption_requests" in s for s, _ in db.executed)


def test_delete_pet_removes_image_file(client, db, shelter_auth, tmp_path, monkeypatch):
    monkeypatch.setitem(app_module.app.config, "UPLOAD_FOLDER", str(tmp_path))
    (tmp_path / "pet_1_a.png").write_bytes(b"x")
    db.fetchone_queue.append({"shelter_id": 1, "image_filename": "pet_1_a.png"})
    assert client.delete("/api/pets/1", headers=shelter_auth).status_code == 200
    assert not (tmp_path / "pet_1_a.png").exists()


def test_upload_image_paths(client, db, shelter_auth, user_auth, tmp_path, monkeypatch):
    monkeypatch.setitem(app_module.app.config, "UPLOAD_FOLDER", str(tmp_path))
    url = "/api/pets/1/upload-image"
    multipart = "multipart/form-data"
    assert client.post(url, headers=user_auth).status_code == 403
    assert client.post(url, headers=shelter_auth).status_code == 404
    db.fetchone_queue.append({"shelter_id": 2})
    assert client.post(url, headers=shelter_auth).status_code == 403
    db.fetchone_queue.append({"shelter_id": 1})
    assert client.post(url, headers=shelter_auth).status_code == 400
    db.fetchone_queue.append({"shelter_id": 1})
    bad = client.post(url, headers=shelter_auth, data={"image": (io.BytesIO(b"x"), "evil.exe")}, content_type=multipart)
    assert bad.status_code == 400
    db.fetchone_queue.append({"shelter_id": 1})
    ok = client.post(url, headers=shelter_auth, data={"image": (io.BytesIO(b"\x89PNG"), "cat.png")}, content_type=multipart)
    assert ok.status_code == 200 and (tmp_path / ok.get_json()["filename"]).exists()
    assert client.get("/uploads/" + ok.get_json()["filename"]).status_code == 200
