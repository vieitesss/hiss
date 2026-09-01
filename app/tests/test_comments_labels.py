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


def test_update_and_delete_comment(client):
    client.post("/api/v1/projects", json={"key": "CM2", "name": "Com"})
    r = client.post("/api/v1/projects/CM2/issues", json={"title": "T"})
    iid = r.get_json()["id"]
    r = client.post(f"/api/v1/issues/{iid}/comments", json={"body": "hello"})
    cid = r.get_json()["id"]

    r = client.patch(f"/api/v1/comments/{cid}", json={"body": "updated"})
    assert r.status_code == 200
    assert r.get_json()["body"] == "updated"

    r = client.patch(f"/api/v1/comments/{cid}", json={"body": "   "})
    assert r.status_code == 400

    r = client.delete(f"/api/v1/comments/{cid}")
    assert r.status_code == 204
    r = client.get(f"/api/v1/issues/{iid}/comments")
    assert r.get_json() == []

    r = client.delete("/api/v1/comments/99999")
    assert r.status_code == 404


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


def test_delete_label_detaches_from_issues(client):
    client.post("/api/v1/projects", json={"key": "LB2", "name": "Lb"})
    r = client.post("/api/v1/projects/LB2/issues", json={"title": "T"})
    iid = r.get_json()["id"]
    client.post("/api/v1/labels", json={"name": "bug"})
    client.post(f"/api/v1/issues/{iid}/labels/bug")

    r = client.delete("/api/v1/labels/bug")
    assert r.status_code == 204

    r = client.get("/api/v1/labels")
    assert all(lb["name"] != "bug" for lb in r.get_json())
    r = client.get(f"/api/v1/issues/{iid}")
    assert r.get_json()["labels"] == []

    r = client.delete("/api/v1/labels/missing")
    assert r.status_code == 404
