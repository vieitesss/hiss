"""Comments: add/list — happy paths, json, errors."""

import json

import httpx
from typer.testing import CliRunner

from hiss.main import app
import hiss.client

runner = CliRunner()


def _mock(monkeypatch, handler):
    transport = httpx.MockTransport(handler)

    def fake(ctx=None, base_url=None):
        if base_url is None:
            base_url = hiss.client.get_base_url_for_ctx(ctx)
        return httpx.Client(transport=transport, base_url=base_url, timeout=10.0)

    monkeypatch.setattr(hiss.client, "get_client", fake)


def test_comments_list_table(monkeypatch):
    def handler(request: httpx.Request):
        assert request.method == "GET"
        assert request.url.path == "/api/v1/issues/42/comments"
        return httpx.Response(200, json=[{"id": 1, "issue_id": 42, "body": "hi", "created_at": "2024-01-01T00:00:00"}], request=request)

    _mock(monkeypatch, handler)
    result = runner.invoke(app, ["comments", "list", "42"])
    assert result.exit_code == 0
    assert "hi" in result.output


def test_comments_list_json(monkeypatch):
    def handler(request: httpx.Request):
        return httpx.Response(200, json=[{"id": 1, "issue_id": 42, "body": "hi", "created_at": "2024-01-01T00:00:00"}], request=request)

    _mock(monkeypatch, handler)
    result = runner.invoke(app, ["comments", "list", "42", "--json"])
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert data[0]["body"] == "hi"


def test_comments_list_404(monkeypatch):
    def handler(request: httpx.Request):
        return httpx.Response(404, json={"error": "not_found", "message": "issue 42 not found"}, request=request)

    _mock(monkeypatch, handler)
    result = runner.invoke(app, ["comments", "list", "42"])
    assert result.exit_code == 1
    assert "issue 42 not found" in result.output


def test_comments_add_happy(monkeypatch):
    def handler(request: httpx.Request):
        assert request.method == "POST"
        assert request.url.path == "/api/v1/issues/42/comments"
        body = json.loads(request.content.decode())
        assert body == {"body": "reproduced on staging"}
        return httpx.Response(201, json={"id": 1, "issue_id": 42, "body": "reproduced on staging", "created_at": "2024-01-01T00:00:00"}, request=request)

    _mock(monkeypatch, handler)
    result = runner.invoke(app, ["comments", "add", "42", "reproduced on staging"])
    assert result.exit_code == 0
    assert "reproduced on staging" in result.output


def test_comments_add_json(monkeypatch):
    def handler(request: httpx.Request):
        return httpx.Response(201, json={"id": 1, "issue_id": 42, "body": "hi", "created_at": "2024-01-01T00:00:00"}, request=request)

    _mock(monkeypatch, handler)
    result = runner.invoke(app, ["comments", "add", "42", "hi", "--json"])
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert data["body"] == "hi"


def test_comments_add_400(monkeypatch):
    def handler(request: httpx.Request):
        return httpx.Response(400, json={"error": "bad_request", "message": "body is required"}, request=request)

    _mock(monkeypatch, handler)
    result = runner.invoke(app, ["comments", "add", "42", "x"])
    assert result.exit_code == 1
    assert "body is required" in result.output


def test_comments_add_404(monkeypatch):
    def handler(request: httpx.Request):
        return httpx.Response(404, json={"error": "not_found", "message": "issue 42 not found"}, request=request)

    _mock(monkeypatch, handler)
    result = runner.invoke(app, ["comments", "add", "42", "hi"])
    assert result.exit_code == 1
    assert "issue 42 not found" in result.output
