def test_create_and_list_projects(client):
    r = client.post("/api/v1/projects", json={"key": "ALFA", "name": "Alfa"})
    assert r.status_code == 201
    assert r.get_json()["key"] == "ALFA"

    r = client.get("/api/v1/projects")
    assert r.status_code == 200
    keys = [p["key"] for p in r.get_json()]
    assert "ALFA" in keys


def test_duplicate_project_key_returns_409(client):
    client.post("/api/v1/projects", json={"key": "DUP", "name": "One"})
    r = client.post("/api/v1/projects", json={"key": "DUP", "name": "Two"})
    assert r.status_code == 409
    assert r.is_json
    assert "error" in r.get_json()


def test_create_project_missing_field_returns_400(client):
    r = client.post("/api/v1/projects", json={"key": "ONLYKEY"})
    assert r.status_code == 400
    assert r.is_json
    assert r.content_type.startswith("application/json")
