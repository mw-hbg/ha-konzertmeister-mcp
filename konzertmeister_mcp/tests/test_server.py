"""The MCP server: tools, filters and what reaches Konzertmeister – with a fake API."""

import asyncio
import json

import httpx
import pytest

import km_api
import mcp_server
import privacy
import settings as km_settings

APPOINTMENTS = [
    {
        "id": 1, "name": "Probe Jugendkapelle", "start": "2026-12-01T18:00:00+01:00", "typId": 1, "active": True,
        "group": {"id": 5, "name": "Jugendkapelle"}, "privateLinkURL": "https://secret.example/1",
        "checkinQrCodeImageUrl": "https://qr.example", "org": {"id": 9, "name": "Stadtkapelle", "paymentPlan": {"balance": 5}},
        "location": {"name": "Probelokal", "formattedAddress": "Hauptstr. 1"}, "published": False,
        "publicSharingUrl": "https://public.example/1", "tags": [{"tag": "Weihnachten"}],
    },
    {"id": 2, "name": "Vorstandssitzung", "group": {"id": 6, "name": "Vorstand"}},
    {"id": 3, "name": "Jahreskonzert", "active": False, "cancelDescription": "Halle zu", "published": True,
     "publicSharingUrl": "https://public.example/3"},
]
REPLIES = [
    {"kmUserFirstName": "Anna", "kmUserLastName": "A", "kmUserEmail": "anna@example.com", "reply": "POSITIVE", "replyComment": "gern"},
    {"kmUserFirstName": "Ben", "kmUserLastName": "B", "kmUserEmail": "ben@example.com", "reply": "UNANSWERED"},
]
MEMBERS = [
    {"kmUserId": 1, "firstname": "Anna", "lastname": "A", "mail": "anna@example.com", "mobilePhone": "0170",
     "address": {"city": "Herrenberg", "streetline1": "Weg 1"},
     "properties": [{"memberPropertyName": "Instrument", "valueString": "Flöte", "memberPropertyActive": True}]},
]


class FakeKm:
    def __init__(self, status: int = 200):
        self.calls = []
        self.status = status

    def __call__(self, request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content) if request.content else None
        self.calls.append((request.method, request.url.path, request.headers.get(km_api.KEY_HEADER), body))
        if self.status != 200:
            return httpx.Response(self.status, json={"message": "nope"})
        path = request.url.path
        if path == km_api.PATH_APPOINTMENTS:
            return httpx.Response(200, json=APPOINTMENTS)
        if path.startswith("/api/v4/att/"):
            return httpx.Response(200, json=REPLIES)
        if path.startswith("/api/v2/attreal/"):
            return httpx.Response(200, json=[{"kmUserFirstName": "Anna", "attending": True, "kmUserEmail": "anna@example.com"},
                                             {"kmUserFirstName": "Ben", "attending": False}])
        if path == km_api.PATH_MEMBERS:
            return httpx.Response(200, json=MEMBERS)
        if path == km_api.PATH_CREATE:
            return httpx.Response(200, json={"id": 44, "name": body.get("name") or "Probe", "start": body["startZoned"]})
        return httpx.Response(200)


def make(tmp_path, fake=None, **overrides):
    fake = fake or FakeKm()
    data = {"tools": sorted(km_settings.ALL_TOOLS), **overrides}
    state = mcp_server.State(
        km_settings.normalize(data),
        km_api.Konzertmeister("SECRET-KEY-123456", base_url="https://km.test", transport=httpx.MockTransport(fake)),
        tmp_path,
    )
    return mcp_server.build_server(state), fake, state


def call(server, name, args=None):
    async def run():
        result = await server.call_tool(name, args or {})
        content = result[0] if isinstance(result, tuple) else result
        return json.loads(content[0].text)

    return asyncio.run(run())


def fails(server, name, args=None) -> str:
    with pytest.raises(Exception) as info:
        call(server, name, args)
    return str(info.value)


def tool_names(server):
    return {t.name for t in asyncio.run(server.list_tools())}


def test_only_released_tools_exist(tmp_path):
    server, _, _ = make(tmp_path, tools=sorted(km_settings.DEFAULT_TOOLS))
    assert tool_names(server) == set(km_settings.DEFAULT_TOOLS)
    server, _, _ = make(tmp_path, tools=[])
    assert tool_names(server) == set()


def test_annotations_tell_reading_from_writing(tmp_path):
    server, _, _ = make(tmp_path)
    tools = {t.name: t for t in asyncio.run(server.list_tools())}
    assert tools["list_appointments"].annotations.readOnlyHint is True
    assert tools["create_appointment"].annotations.readOnlyHint is False
    assert tools["update_member"].annotations.destructiveHint is True


def test_appointments_are_reduced_and_sent_with_the_key(tmp_path):
    server, fake, _ = make(tmp_path)
    result = call(server, "list_appointments")
    method, path, key, body = fake.calls[0]
    assert (method, path, key) == ("POST", km_api.PATH_APPOINTMENTS, "SECRET-KEY-123456")
    assert body["dateMode"] == "UPCOMING" and body["activationStatusList"] == ["ACTIVE"]
    assert body["typeIds"] == list(km_settings.FALLBACK_TYPE_IDS)
    first = result["appointments"][0]
    assert first["group"] == "Jugendkapelle" and first["location"]["name"] == "Probelokal" and first["tags"] == ["Weihnachten"]
    text = json.dumps(result)
    for hidden in ("secret.example", "qr.example", "paymentPlan", "public.example/1"):
        assert hidden not in text  # internal links, QR codes, unpublished link
    third = result["appointments"][2]
    assert third["cancelled"] and third["cancel_reason"] == "Halle zu" and third["public_link"].endswith("/3")


def test_date_filters_and_types(tmp_path):
    server, fake, _ = make(tmp_path, types=[{"name": "Probe", "id": 1}, {"name": "Konzert", "id": 2}])
    call(server, "list_appointments", {"start_date": "2026-12-01", "end_date": "2026-12-31", "include_cancelled": True, "sort_by": "deadline"})
    body = fake.calls[0][3]
    assert body["dateMode"] == "FROM_DATE" and body["filterStart"].startswith("2026-12-01T00:00:00")
    assert body["filterEnd"].startswith("2026-12-31T23:59:59") and body["typeIds"] == [1, 2]
    assert body["activationStatusList"] == ["ACTIVE", "CANCELLED"] and body["sortMode"] == "DEADLINE"
    assert "not a date" in fails(server, "list_appointments", {"start_date": "morgen"})


def test_group_filter_hides_other_groups_and_their_replies(tmp_path):
    server, fake, _ = make(tmp_path, groups=[5])
    result = call(server, "list_appointments")
    assert [a["id"] for a in result["appointments"]] == [1, 3]  # 3: no group, kept by default
    assert "1 appointment" in result["note"]
    assert call(server, "get_appointment_replies", {"appointment_id": 1})["summary"]["yes"] == 1
    assert "not shared" in fails(server, "get_appointment_replies", {"appointment_id": 2})
    assert "list_appointments first" in fails(server, "get_appointment_attendance", {"appointment_id": 99})
    assert not any("/att/m2m/2" in c[1] for c in fake.calls)

    server, _, _ = make(tmp_path, groups=[5], include_without_group=False)
    assert [a["id"] for a in call(server, "list_appointments")["appointments"]] == [1]


def test_contact_details_only_when_released(tmp_path):
    server, _, _ = make(tmp_path)
    replies = call(server, "get_appointment_replies", {"appointment_id": 1})
    assert "anna@example.com" not in json.dumps(replies)
    assert replies["replies"][0] == {"name": "Anna A", "reply": "yes", "comment": "gern"}
    members = call(server, "list_members")
    assert members["members"] == [{"name": "Anna A"}] and members["released_details"] == ["names only"]
    attendance = call(server, "get_appointment_attendance", {"appointment_id": 1})
    assert attendance["attended"] == 1 and {"name": "Ben", "attended": False} in attendance["people"]

    server, _, _ = make(tmp_path, share={"email": True, "phone": True, "address": True, "properties": True})
    member = call(server, "list_members")["members"][0]
    assert member["email"] == "anna@example.com" and member["mobile_phone"] == "0170"
    assert member["address"]["city"] == "Herrenberg" and member["fields"] == {"Instrument": "Flöte"}
    assert call(server, "get_appointment_replies", {"appointment_id": 1})["replies"][0]["email"] == "anna@example.com"


def test_create_appointment_needs_template_and_creator(tmp_path):
    server, _, _ = make(tmp_path)
    assert "Unknown template" in fails(server, "create_appointment", {"template": "Probe", "start": "2030-01-01T18:00"})
    server, _, _ = make(tmp_path, templates=[{"name": "Probe", "id": "T-1"}])
    assert "creator e-mail" in fails(server, "create_appointment", {"template": "Probe", "start": "2030-01-01T18:00"})
    server, fake, state = make(tmp_path, templates=[{"name": "Probe", "id": "T-1"}], creator_mail="leiter@example.com")
    assert "past" in fails(server, "create_appointment", {"template": "probe", "start": "2020-01-01T18:00"})
    created = call(server, "create_appointment", {"template": "probe", "start": "2030-01-08T18:30", "name": "Extraprobe"})
    body = fake.calls[-1][3]
    assert body == {"appointmentTemplateExtId": "T-1", "creatorMail": "leiter@example.com",
                    "startZoned": "2030-01-08T18:30:00+01:00", "name": "Extraprobe"}
    assert created["created"]["id"] == 44 and state.known[44] is True


def test_members_are_added_and_changed(tmp_path):
    server, fake, _ = make(tmp_path)
    assert "valid e-mail" in fails(server, "add_member", {"email": "kein-mail"})
    call(server, "add_member", {"email": "neu@example.com", "first_name": "Neu",
                                "properties": [{"property_id": "P1", "value": True}, {"property_id": "P2", "value": "2026-05-01"},
                                               {"property_id": "P3", "value": 3}, {"property_id": "P4", "value": "Trompete"}]})
    assert fake.calls[-1][1] == km_api.PATH_ADD_MEMBER
    assert fake.calls[-1][3] == {"mail": "neu@example.com", "firstname": "Neu", "properties": [
        {"propertyExtId": "P1", "valueBoolean": True}, {"propertyExtId": "P2", "valueDate": "2026-05-01"},
        {"propertyExtId": "P3", "valueNumber": 3}, {"propertyExtId": "P4", "valueString": "Trompete"}]}
    assert "Nothing to change" in fails(server, "update_member", {"email": "neu@example.com"})
    assert call(server, "update_member", {"email": "neu@example.com", "mobile_phone": "0171"})["updated"] == ["mobilePhone"]
    assert fake.calls[-1][1] == km_api.PATH_UPDATE_MEMBER


def test_rejected_key_is_reported_without_the_key(tmp_path):
    server, _, state = make(tmp_path, fake=FakeKm(status=401))
    text = fails(server, "list_appointments")
    assert "rejected the API key" in text and "SECRET-KEY" not in text
    assert (tmp_path / "key_invalid").exists()
    server, _, _ = make(tmp_path)
    call(server, "list_appointments")
    assert not (tmp_path / "key_invalid").exists()  # works again → marker gone


def test_answers_are_cached_briefly(tmp_path):
    server, fake, _ = make(tmp_path)
    call(server, "list_members")
    call(server, "list_members")
    assert len(fake.calls) == 1


def test_templates_and_types_lists(tmp_path):
    server, _, _ = make(tmp_path, templates=[{"name": "Probe", "id": "SECRET-T"}])
    assert call(server, "list_appointment_templates") == {"templates": [{"name": "Probe"}]}
    assert "not named" in call(server, "list_appointment_types")["note"]


def test_privacy_helpers():
    assert privacy.reply_view({"reply": "MAYBE"}, {})["reply"] == "maybe"
    assert privacy.reply_view({}, {})["name"] == "?"
    assert privacy.group_allowed({"group": {"id": "x"}}, {"groups": [1]}) is False
