"""The app page and the channels nginx forwards to it."""

import json
import re

import pytest
from starlette.testclient import TestClient

import clubs as C
import remote
import web

GOOD = {"ok": True, "name": "Stadtkapelle", "groups": [{"id": 5, "name": "Jugendkapelle"}, {"id": 6, "name": "Vorstand"}], "types": [1], "count": 2}


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(C, "probe_api", lambda key, types, **kw: dict(GOOD))
    monkeypatch.setattr(C.Club, "start_mcp", lambda self: None)
    services = C.Services()
    access = remote.RemoteAccess(services)
    web.setup(services, access)
    web.FLASH.clear()
    with TestClient(web.app, base_url="http://ingress") as c:
        c.services = services
        yield c
    services.shutdown()


def csrf() -> str:
    return web.CSRF_TOKEN


def test_page_in_both_languages(client):
    en = client.get("/", headers={"Accept-Language": "en"}).text
    de = client.get("/", headers={"Accept-Language": "de-DE,de;q=0.9"}).text
    assert 'lang="en"' in en and "Save key" in en and 'type="password"' in en
    assert 'lang="de"' in de and "Schlüssel speichern" in de
    response = client.get("/")
    assert response.headers["cache-control"] == "no-store" and "frame-ancestors" in response.headers["content-security-policy"]


def test_only_ingress_may_use_the_page(client, monkeypatch):
    monkeypatch.setattr(web, "ALLOW_ANY_UI_CLIENT", False)
    assert client.get("/").status_code == 403
    assert client.post("/vereine/add".replace("vereine", "clubs"), data={"csrf": csrf()}).status_code == 403


def test_forms_need_the_csrf_token(client):
    client.post("/clubs/add", data={"csrf": "wrong"})
    assert len(client.services.clubs) == 1
    client.post("/clubs/add", data={"csrf": csrf()})
    assert len(client.services.clubs) == 2


def test_key_then_settings(client):
    client.post("/clubs/key", data={"csrf": csrf(), "club": "1", "key": "k" * 40})
    club = client.services.club("1")
    assert club.has_key()
    page = client.get("/", headers={"Accept-Language": "en"}).text
    assert "Stadtkapelle" in page and "Jugendkapelle" in page and "k" * 40 not in page
    form = {
        "csrf": csrf(), "club": "1", "tool": ["list_appointments", "create_appointment"], "group": ["5"], "nogroup": "1",
        "share": ["email"], "creator_mail": "leiter@example.com", "templates": "Probe = T1", "types": "Probe = 1",
    }
    client.post("/clubs/settings", data=form)
    s = club.settings()
    assert s["tools"] == ["create_appointment", "list_appointments"] and s["groups"] == [5]
    assert s["share"]["email"] and not s["share"]["phone"] and s["templates"] == [{"name": "Probe", "id": "T1"}]
    page = client.get("/", headers={"Accept-Language": "en"}).text
    assert "may write" in page and "E-mail addresses" in page

    page = client.post("/clubs/settings", data={**form, "creator_mail": "no-mail"}, headers={"Accept-Language": "en"}).text
    assert club.settings()["creator_mail"] == "leiter@example.com"  # invalid → nothing saved
    assert "not a valid address" in page


def test_rejected_key_is_shown(client, monkeypatch):
    monkeypatch.setattr(C, "probe_api", lambda key, types, **kw: {"ok": False, "kind": "auth", "detail": "HTTP 401"})
    page = client.post("/clubs/key", data={"csrf": csrf(), "club": "1", "key": "z" * 40}, headers={"Accept-Language": "en"}).text
    assert "rejected this key" in page
    assert not client.services.club("1").has_key()


def test_names_and_remove_only_with_several_clubs(client):
    page = client.get("/", headers={"Accept-Language": "en"}).text
    assert "✏️" not in page and "Remove association" not in page
    client.post("/clubs/add", data={"csrf": csrf()})
    page = client.get("/", headers={"Accept-Language": "en"}).text
    assert "✏️" in page and "Remove association" in page
    client.post("/clubs/rename", data={"csrf": csrf(), "club": "2", "name": "Jugend"})
    assert client.services.club("2").display_name() == "Jugend"
    client.post("/clubs/remove", data={"csrf": csrf(), "club": "2"})
    assert list(client.services.clubs) == ["1"]
    client.post("/clubs/remove", data={"csrf": csrf(), "club": "1"})
    assert list(client.services.clubs) == ["1"]  # the last one stays


def test_load_warning_from_four_clubs(client):
    for _ in range(3):
        client.post("/clubs/add", data={"csrf": csrf()})
    assert "From four associations on" in client.get("/", headers={"Accept-Language": "en"}).text


def test_rotate_changes_secret_and_webhook(client):
    club = client.services.club("1")
    old = (club.secret, club.webhook_id)
    client.post("/clubs/rotate", data={"csrf": csrf(), "club": "1"})
    assert club.secret != old[0] and club.webhook_id != old[1]


def test_report_and_stand_in_need_the_nginx_key(client):
    key = client.services.report_secret
    assert client.post("/report", content=b"{}").status_code == 403
    answer = client.post("/report", content=json.dumps({"clubs": {"1": {"mcp_enabled": True}}}), headers={"X-Report-Key": key}).json()
    assert answer["clubs"]["1"]["status"] == "no_key"
    assert client.post("/report", content=b"x" * 5000, headers={"X-Report-Key": key}).status_code == 413
    message = {"jsonrpc": "2.0", "id": 1, "method": "tools/list"}
    assert client.post("/mcp-unavailable/1", json=message).status_code == 403
    tools = client.post("/mcp-unavailable/1", json=message, headers={"X-Report-Key": key}).json()
    assert tools["result"]["tools"][0]["name"] == "konzertmeister_connection_status"
    assert "no API key" in tools["result"]["tools"][0]["description"]


def test_connector_url_is_masked_until_shown(client):
    page = client.get("/").text
    club = client.services.club("1")
    assert re.search(r'data-value="[^"]*' + re.escape(club.webhook_id), page)
    assert f">{club.webhook_id}<" not in page
