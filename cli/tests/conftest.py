"""Shared fixtures for CLI tests — MockTransport seam, no DB."""

import httpx
import pytest
from typer.testing import CliRunner

from hiss.main import app as hiss_app
import hiss.client


@pytest.fixture
def runner():
    return CliRunner()


@pytest.fixture
def mock_client(monkeypatch):
    """Factory to patch hiss.client.get_client to use MockTransport.

    Usage:
        def test_foo(runner, mock_client):
            def handler(request):
                return httpx.Response(200, json=[])
            mock_client(handler)
            result = runner.invoke(hiss_app, [...])
    Also captures last request for assertions via mock_client.last_request.
    """

    captured = {}

    def _factory(handler, expected_base_url=None):
        transport = httpx.MockTransport(handler)

        def fake_get_client(ctx=None, base_url=None):
            if base_url is None:
                base_url = hiss.client.get_base_url_for_ctx(ctx)
            if expected_base_url is not None:
                assert base_url == expected_base_url, f"base_url {base_url} != expected {expected_base_url}"
            captured["base_url"] = base_url
            # need to expose last request url for assertions; handler can capture itself
            return httpx.Client(transport=transport, base_url=base_url, timeout=10.0)

        monkeypatch.setattr(hiss.client, "get_client", fake_get_client)
        return captured

    _factory.captured = captured
    return _factory
