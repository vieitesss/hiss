def test_create_and_list_issues(client):
    client.post("/api/v1/projects", json={"key": "PRJ", "name": "Project"})
    r = client.post("/api/v1/projects/PRJ/issues", json={"title": "First", "description": "d"})
    assert r.status_code == 201
    iid = r.get_json()["id"]

    r = client.get("/api/v1/projects/PRJ/issues")
    assert r.status_code == 200
    ids = [i["id"] for i in r.get_json()]
    assert iid in ids


def test_filter_issues_by_status_and_priority(client):
    client.post("/api/v1/projects", json={"key": "FILT", "name": "Filt"})
    client.post("/api/v1/projects/FILT/issues", json={"title": "A", "priority": "high"})
    client.post("/api/v1/projects/FILT/issues", json={"title": "B", "priority": "low"})

    r = client.get("/api/v1/projects/FILT/issues?priority=high")
    assert r.status_code == 200
    assert len(r.get_json()) == 1

    # Create and patch one to done, then filter by status
    r = client.post("/api/v1/projects/FILT/issues", json={"title": "C"})
    cid = r.get_json()["id"]
    client.patch(f"/api/v1/issues/{cid}", json={"status": "done"})
    r = client.get("/api/v1/projects/FILT/issues?status=done")
    assert any(i["id"] == cid for i in r.get_json())


def test_update_issue_and_invalid_enum_returns_400(client):
    client.post("/api/v1/projects", json={"key": "UPD", "name": "Upd"})
    r = client.post("/api/v1/projects/UPD/issues", json={"title": "T"})
    iid = r.get_json()["id"]

    r = client.patch(f"/api/v1/issues/{iid}", json={"status": "in_progress", "priority": "low"})
    assert r.status_code == 200
    assert r.get_json()["status"] == "in_progress"

    r = client.patch(f"/api/v1/issues/{iid}", json={"status": "bad"})
    assert r.status_code == 400
    assert r.is_json


def test_unknown_project_or_issue_returns_404(client):
    r = client.get("/api/v1/projects/UNKNOWN/issues")
    assert r.status_code == 404
    assert r.is_json

    r = client.post("/api/v1/projects/UNKNOWN/issues", json={"title": "x"})
    assert r.status_code == 404

    r = client.get("/api/v1/issues/99999")
    assert r.status_code == 404
    assert r.content_type.startswith("application/json")
