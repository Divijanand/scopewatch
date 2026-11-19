"""The hosted demo's password protection."""
import asyncio
import base64

import pytest
from fastapi import FastAPI

from api import auth


def basic(user, password):
    return "Basic " + base64.b64encode(f"{user}:{password}".encode()).decode()


def call(app, path, header=None):
    """Run one GET through the ASGI app and return (status, headers)."""
    sent = []

    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(msg):
        sent.append(msg)

    headers = [(b"authorization", header.encode())] if header else []
    scope = {"type": "http", "method": "GET", "path": path, "raw_path": path.encode(), "query_string": b"",
             "headers": headers, "http_version": "1.1", "scheme": "http", "server": ("test", 80),
             "client": ("test", 1), "root_path": ""}
    asyncio.run(app(scope, receive, send))
    start = next(m for m in sent if m["type"] == "http.response.start")
    return start["status"], {k.decode().lower(): v.decode() for k, v in start["headers"]}


@pytest.fixture
def app(monkeypatch):
    monkeypatch.setenv("SCOPEWATCH_PASSWORD", "s3cret")
    monkeypatch.setenv("SCOPEWATCH_USER", "judge")
    a = FastAPI()

    @a.get("/health")
    def health():
        return {"ok": True}

    @a.get("/api/data")
    def data():
        return {"rows": 1}

    assert auth.install(a)
    return a


def test_data_needs_the_password(app):
    status, headers = call(app, "/api/data")
    assert status == 401 and "Basic" in headers["www-authenticate"]


def test_wrong_password_or_user_is_refused(app):
    assert call(app, "/api/data", basic("judge", "nope"))[0] == 401
    assert call(app, "/api/data", basic("someone", "s3cret"))[0] == 401
    assert call(app, "/api/data", "Basic not-base64!!")[0] == 401


def test_right_password_gets_in_and_pages_are_not_indexed(app):
    status, headers = call(app, "/api/data", basic("judge", "s3cret"))
    assert status == 200 and "noindex" in headers["x-robots-tag"]


def test_health_check_is_open(app):
    assert call(app, "/health")[0] == 200


def test_deployed_image_refuses_to_start_without_a_password(monkeypatch):
    monkeypatch.delenv("SCOPEWATCH_PASSWORD", raising=False)
    monkeypatch.setenv("SCOPEWATCH_REQUIRE_AUTH", "1")
    with pytest.raises(RuntimeError):
        auth.install(FastAPI())


def test_local_runs_without_a_login(monkeypatch):
    monkeypatch.delenv("SCOPEWATCH_PASSWORD", raising=False)
    monkeypatch.delenv("SCOPEWATCH_REQUIRE_AUTH", raising=False)
    assert auth.install(FastAPI()) is False
