"""Testes rotas públicas meta (/, robots, security.txt)."""
import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("DIOMIKA_ENV", "production")
    monkeypatch.setenv("ALLOWED_HOSTS", "api.diomika.com,testserver")
    from main import app

    return TestClient(app, base_url="https://api.diomika.com")


def test_api_root(client):
    r = client.get("/")
    assert r.status_code == 200
    body = r.json()
    assert body["service"] == "diomika-api"
    assert body["health"] == "/health"
    assert "status" in body


def test_robots_txt(client):
    r = client.get("/robots.txt")
    assert r.status_code == 200
    assert "Disallow: /" in r.text


def test_security_txt(client):
    r = client.get("/.well-known/security.txt")
    assert r.status_code == 200
    assert "Contact:" in r.text
