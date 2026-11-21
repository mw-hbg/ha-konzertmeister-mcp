"""Associations: files, key handling, servers, nginx and the report channel."""

import json
import os
import shutil
import subprocess
import time

import httpx
import pytest

import clubs as C
import common
import remote
import settings as km_settings

GOOD = {"ok": True, "name": "Stadtkapelle Herrenberg", "groups": [{"id": 5, "name": "Jugendkapelle"}], "types": [1, 2], "count": 3}


@pytest.fixture
def services(monkeypatch):
    monkeypatch.setattr(C, "probe_api", lambda key, types, **kw: dict(GOOD))
    svc = C.Services()
    yield svc
    svc.shutdown()


def test_fresh_install_has_one_empty_club(services):
    assert list(services.clubs) == ["1"]
    club = services.club("1")
    assert not club.has_key() and club.shown_state() == "no_key" and club.key_status() == "no_key"
    assert club.settings() == km_settings.default_settings()
    assert len(club.secret) >= 32 and club.webhook_id.startswith("konzertmeister_mcp_")
    assert services.named is False and club.shown_name() == ""


def test_key_is_checked_stored_privately_and_never_in_the_environment(services, monkeypatch):
    club = services.club("1")
    monkeypatch.setattr(club, "start_mcp", lambda: None)
    with pytest.raises(C.ClubError) as err:
        club.set_key("short")
    assert err.value.key == "err_key_format"
    monkeypatch.setattr(C, "probe_api", lambda key, types, **kw: {"ok": False, "kind": "auth", "detail": "HTTP 401"})
    with pytest.raises(C.ClubError) as err:
        club.set_key("a" * 40)
    assert err.value.key == "err_key_rejected" and not club.has_key()
    monkeypatch.setattr(C, "probe_api", lambda key, types, **kw: dict(GOOD))
    club.set_key("  abcdefghijklmnopqrstuvwxyz0123456789 \n")
    assert club.read_key() == "abcdefghijklmnopqrstuvwxyz0123456789"
    assert club.key_file.stat().st_mode & 0o777 == 0o600 and club.private.stat().st_mode & 0o777 == 0o700
    assert club.km_name() == "Stadtkapelle Herrenberg" and club.info()["groups"][0]["name"] == "Jugendkapelle"
    monkeypatch.setenv("SUPERVISOR_TOKEN", "supervisor-secret")
    monkeypatch.setenv("SOME_PASSWORD", "x")
    env = club.environment()
    assert "SUPERVISOR_TOKEN" not in env and "SOME_PASSWORD" not in env
    assert "abcdefghijklmnopqrstuvwxyz" not in json.dumps(env)
    assert json.loads(env["KM_SETTINGS"]) == km_settings.default_settings()
    club.delete_key()
    assert not club.has_key()


def test_symlinked_key_file_is_not_followed(services, monkeypatch, tmp_path):
    club = services.club("1")
    monkeypatch.setattr(club, "start_mcp", lambda: None)
    club.private.mkdir(parents=True, exist_ok=True)
    target = tmp_path / "elsewhere"
    target.write_text("untouched")
    os.symlink(target, club.key_file)
    assert not club.has_key()  # never read through a link
    club.set_key("b" * 40)
    assert target.read_text() == "untouched" and not club.key_file.is_symlink()


def test_info_is_merged(services):
    club = services.club("1")
    club.save_info(GOOD)
    club.save_info({"name": "", "groups": [{"id": 7, "name": "Vororchester"}], "types": [3]})
    info = club.info()
    assert info["name"] == "Stadtkapelle Herrenberg" and info["types"] == [1, 2, 3]
    assert [g["id"] for g in info["groups"]] == [5, 7]


def test_summarize_finds_name_groups_and_types():
    found = C.summarize(
        [
            {"org": {"id": 1, "name": "Stadtkapelle"}, "group": {"id": 5, "name": "Jugend"}, "typId": 2},
            {"org": {"id": 6, "name": "Jugend", "parentId": 1, "parentName": "Stadtkapelle"}, "typId": 1},
        ]
    )
    assert found == {"name": "Stadtkapelle", "groups": [{"id": 5, "name": "Jugend"}], "types": [1, 2], "count": 2}


def test_probe_api_classifies_answers():
    def run(status, body=None):
        transport = httpx.MockTransport(lambda r: httpx.Response(status, json=body if body is not None else []))
        return C.probe_api("k" * 20, [1], base_url="https://km.test", transport=transport)

    assert run(401) == {"ok": False, "kind": "auth", "detail": "HTTP 401"}
    assert run(500)["kind"] == "other"
    assert run(200, [{"typId": 4}])["types"] == [4]

    def broken(_request):
        raise httpx.ConnectError("down")

    assert C.probe_api("k" * 20, [1], base_url="https://km.test", transport=httpx.MockTransport(broken))["kind"] == "network"


def test_settings_are_stored_normalized(services, monkeypatch):
    club = services.club("1")
    monkeypatch.setattr(club, "restart_mcp", lambda: None)
    club.save_settings({"tools": ["list_members", "nope"], "groups": ["5", "x"], "creator_mail": "falsch",
                        "share": {"email": True, "phone": "yes"}})
    s = club.settings()
    assert s["tools"] == ["list_members"] and s["groups"] == [5] and s["creator_mail"] == ""
    assert s["share"] == {"email": True, "phone": False, "address": False, "properties": False}
    assert club.settings_file.stat().st_mode & 0o777 == 0o600


def test_pairs_are_parsed():
    pairs = km_settings.parse_pairs("Probe = A-1\n\nKonzert=B2\nkaputt\nprobe = C3\nX = bad id!", False, 10)
    assert pairs == [{"name": "Probe", "id": "A-1"}, {"name": "Konzert", "id": "B2"}]
    assert km_settings.parse_pairs("Probe = 1\nKonzert = zwei", True, 10) == [{"name": "Probe", "id": 1}]
    assert km_settings.type_ids({"types": []}) == list(km_settings.FALLBACK_TYPE_IDS)


def test_up_to_ten_clubs_with_own_slots(services):
    added = [services.add_club() for _ in range(9)]
    assert len(services.clubs) == 10 and services.named
    assert len({c.port for c in services.clubs.values()}) == 10
    assert len({c.user for c in services.clubs.values()}) == 10
    with pytest.raises(C.ClubError):
        services.add_club()
    services.remove_club(added[0])
    assert not added[0].base.exists()
    again = services.add_club()
    assert again.slot == added[0].slot and again.id != added[0].id  # slot reused, id never
    services.rename_club(again, "  Jugend   Kapelle ")
    assert again.display_name() == "Jugend Kapelle"
    reloaded = C.Services()
    assert set(reloaded.clubs) == set(services.clubs)


def test_nginx_configuration(services):
    second = services.add_club()
    services.write_nginx_conf()
    conf = C.NGINX_CONF.read_text()
    for club in services.clubs.values():
        assert f"location = /{club.secret}/mcp " in conf and f"@unavailable_{club.id}" in conf
    assert f"/{services.report_secret}/ha" in conf and "allow 172.30.32.0/23" in conf
    assert "access_log off" in conf
    assert f"127.0.0.1:{second.port}/mcp" in second.proxy_conf.read_text()
    if shutil.which("nginx"):
        result = subprocess.run(["nginx", "-t", "-c", str(C.NGINX_CONF)], capture_output=True, text=True)
        assert result.returncode == 0 or "permission" in result.stderr.lower(), result.stderr


def test_direct_mode_has_no_report_channel(monkeypatch):
    (common.DATA / "options.json").write_text(json.dumps({"remote_access": "direct"}))
    svc = C.Services()
    svc.write_nginx_conf()
    assert "/ha {" not in C.NGINX_CONF.read_text()


def test_report_switches_servers_and_answers_states(services, monkeypatch):
    services.add_club()
    started, stopped = [], []
    for club in services.clubs.values():
        monkeypatch.setattr(club, "start_mcp", lambda c=club: started.append(c.id))
        monkeypatch.setattr(club, "stop_mcp", lambda c=club: stopped.append(c.id))
    access = remote.RemoteAccess(services)
    answer = access.receive_report(
        {"external_url": "https://home.example.com/lovelace", "language": "de", "integration_version": "x",
         "vereine": {}, "clubs": {"2": {"mcp_enabled": False}, "99": {"mcp_enabled": False}}}
    )
    assert stopped == ["2"] and services.club("2").switched_off
    assert answer["clubs"]["2"]["status"] == "off" and answer["clubs"]["1"]["status"] == "no_key"
    assert access.base_url() == "https://home.example.com" and access.state == "restart_needed"
    access.receive_report({"clubs": {"2": {"mcp_enabled": True}}})
    assert started == ["2"] and not services.club("2").switched_off
    config = access.discovery_config()
    assert [c["id"] for c in config["clubs"]] == ["1", "2"] and config["report_url"].endswith("/ha")
    assert config["clubs"][0]["target_url"].endswith(f"/{services.club('1').secret}/mcp")


def test_stand_in_answers_explain_the_reason():
    init = remote.not_ready_answer({"jsonrpc": "2.0", "id": 3, "method": "initialize", "params": {"protocolVersion": "2025-03-26"}}, "no_key")
    assert init["result"]["protocolVersion"] == "2025-03-26" and "no API key" in init["result"]["instructions"]
    call = remote.not_ready_answer({"jsonrpc": "2.0", "id": 4, "method": "tools/call"}, "failed")
    assert call["result"]["isError"] and "rejected" in call["result"]["content"][0]["text"]
    assert remote.not_ready_answer({"jsonrpc": "2.0", "method": "notifications/initialized"}, "off") is None


def test_real_server_starts_with_its_settings(services, monkeypatch):
    """Starts mcp_server.py for real (as the test user) and lists its tools."""
    club = services.club("1")
    monkeypatch.setattr(club, "start_mcp", lambda: None)
    club.set_key("c" * 40)
    monkeypatch.undo()
    monkeypatch.setattr(C, "probe_api", lambda key, types, **kw: dict(GOOD))
    club.save_settings({"tools": ["list_appointments", "list_members"]})
    try:
        for _ in range(80):
            if club.mcp_state() == "ready":
                break
            time.sleep(0.25)
        assert club.shown_state() == "ready" and club.key_status() == "ok"
        data = remote.mcp_request(
            f"http://127.0.0.1:{club.port}/mcp", {"jsonrpc": "2.0", "id": 1, "method": "tools/list"},
            host_header=f"127.0.0.1:{club.port}",
        )
        assert {t["name"] for t in data["result"]["tools"]} == {"list_appointments", "list_members"}
        club.key_invalid_file.touch()
        assert club.key_status() == "failed"
    finally:
        club.stop_mcp()
