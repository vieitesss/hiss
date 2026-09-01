def test_create_and_list_comments(client):
    client.post("/api/v1/projects", json={"key": "CM", "name": "Com"})
    r = client.post("/api/v1/projects/CM/issues", json={"title": "T"})
    iid = r.get_json()["id"]

    r = client.post(f"/api/v1/issues/{iid}/comments", json={"body": "hello"})
    assert r.status_code == 201

    r = client.get(f"/api/v1/issues/{iid}/comments")
    assert r.status_code == 200
    assert len(r.get_json()) == 1

    # missing body → 400
    r = client.post(f"/api/v1/issues/{iid}/comments", json={})
    assert r.status_code == 400
    assert r.is_json


def test_create_and_attach_detach_label(client):
    client.post("/api/v1/projects", json={"key": "LB", "name": "Lb"})
    r = client.post("/api/v1/projects/LB/issues", json={"title": "T"})
    iid = r.get_json()["id"]

    r = client.post("/api/v1/labels", json={"name": "bug"})
    assert r.status_code == 201

    r = client.post(f"/api/v1/issues/{iid}/labels/bug")
    assert r.status_code == 200
    assert any(label["name"] == "bug" for label in r.get_json()["labels"])

    r = client.delete(f"/api/v1/issues/{iid}/labels/bug")
    assert r.status_code == 200
    assert not any(label["name"] == "bug" for label in r.get_json()["labels"])


def test_duplicate_label_returns_409(client):
    client.post("/api/v1/labels", json={"name": "feature"})
    r = client.post("/api/v1/labels", json={"name": "feature"})
    assert r.status_code == 409
    assert r.is_json
