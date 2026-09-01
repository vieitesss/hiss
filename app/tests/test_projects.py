def test_create_and_list_projects(client):
    r = client.post("/api/v1/projects", json={"key": "ALFA", "name": "Alfa"})
    assert r.status_code == 201
    assert r.get_json()["key"] == "ALFA"
    assert r.get_json()["open_issues"] == 0

    # Add issues in various states to verify open_issues count
    client.post("/api/v1/projects/ALFA/issues", json={"title": "Open Issue 1"})
    r_prog = client.post("/api/v1/projects/ALFA/issues", json={"title": "In Progress Issue 2"})
    prog_id = r_prog.get_json()["id"]
    client.patch(f"/api/v1/issues/{prog_id}", json={"status": "in_progress"})
    r_done = client.post("/api/v1/projects/ALFA/issues", json={"title": "Done Issue 3"})
    done_id = r_done.get_json()["id"]
    client.patch(f"/api/v1/issues/{done_id}", json={"status": "done"})

    r = client.get("/api/v1/projects")
    assert r.status_code == 200
    projects = r.get_json()
    alfa = next(p for p in projects if p["key"] == "ALFA")
    assert alfa["open_issues"] == 2  # 1 open + 1 in_progress, excluding done


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
