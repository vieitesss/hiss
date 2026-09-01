import os


def test_healthz_returns_200(client):
    r = client.get("/healthz")
    assert r.status_code == 200
    assert r.get_json()["status"] == "ok"


def test_readyz_returns_200_when_db_up(client):
    r = client.get("/readyz")
    assert r.status_code == 200
    assert r.get_json()["status"] == "ok"


def test_version_returns_app_version(client, monkeypatch, app):
    # Reuse the existing app fixture and mutate config directly — avoids
    # creating a second Flask app/engine that would leave a lingering
    # connection and interleave TRUNCATE/commit (see Node 6 postmortem).
    monkeypatch.setenv("APP_VERSION", "9.9.9-test")
    app.config["APP_VERSION"] = "9.9.9-test"
    r = client.get("/version")
    assert r.status_code == 200
    assert r.get_json()["version"] == "9.9.9-test"

    # default is dev when unset
    monkeypatch.delenv("APP_VERSION", raising=False)
    app.config["APP_VERSION"] = "dev"
    r = client.get("/version")
    assert r.get_json()["version"] == "dev"


def test_label_filter_when_flag_on_returns_filtered(client):
    client.post("/api/v1/projects", json={"key": "FLT", "name": "Flt"})
    r = client.post("/api/v1/projects/FLT/issues", json={"title": "I1"})
    id1 = r.get_json()["id"]
    r = client.post("/api/v1/projects/FLT/issues", json={"title": "I2"})
    id2 = r.get_json()["id"]

    client.post("/api/v1/labels", json={"name": "bug"})
    client.post(f"/api/v1/issues/{id1}/labels/bug")

    r = client.get("/api/v1/projects/FLT/issues?label=bug")
    assert r.status_code == 200
    ids = [i["id"] for i in r.get_json()]
    assert id1 in ids and id2 not in ids


def test_label_filter_when_flag_off_returns_400(client, monkeypatch, app):
    monkeypatch.setenv("FEATURE_LABEL_FILTERING", "false")
    app.config["FEATURE_LABEL_FILTERING"] = False
    # need a project to test filter param presence
    client.post("/api/v1/projects", json={"key": "FF", "name": "FF"})
    r = client.get("/api/v1/projects/FF/issues?label=bug")
    assert r.status_code == 400
    assert r.is_json
    msg = r.get_json()["message"].lower()
    assert "disabled" in msg or "flag" in msg

    # without label param should still be 200
    r = client.get("/api/v1/projects/FF/issues")
    assert r.status_code == 200
    # restore for other tests (app fixture is function-scoped, so not strictly needed,
    # but keep env clean)
    monkeypatch.setenv("FEATURE_LABEL_FILTERING", "true")
    app.config["FEATURE_LABEL_FILTERING"] = True
