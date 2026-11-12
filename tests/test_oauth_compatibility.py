"""Upstream OAuth conventions and retained-client cleanup; no cloud requests."""
import hashlib
import json
from unittest.mock import AsyncMock, MagicMock, patch
from urllib.parse import parse_qs, urlsplit

import pytest

from custom_components.lockin_v5.api import oauth_authorization, oauth_client
from .test_config_flow import clients as clients, login_form, authorize


async def test_transport_identity_and_default_state_are_release_independent():
    uuid = "0123456789abcdef0123456789abcdef"
    redirect = "http://homeassistant.local:8123/api/webhook/123456789"
    system = "hass/2026.11.1 (TestOS/1; test; Test)"
    client = oauth_client("sg", uuid, redirect, system_info=system)
    try:
        state, url = oauth_authorization(client)
        query = parse_qs(urlsplit(url).query)
        assert state == hashlib.sha1(f"d=ha.{uuid}".encode()).hexdigest()
        assert query["state"] == [state]
        assert query["redirect_uri"] == [redirect]
        response = MagicMock(status=200)
        response.text = AsyncMock(return_value=json.dumps({"code": 0, "result": {
            "access_token": "SYNTHETIC", "refresh_token": "SYNTHETIC", "expires_in": 3600}}))
        with patch.object(client._session, "get", new=AsyncMock(return_value=response)) as get:
            await client.get_access_token_async("SYNTHETIC")
        request = get.call_args.kwargs
        assert request["headers"]["User-Agent"] == f"ha_xiaomi_home/v0.5.0 {system} client/ha.{uuid}"
        assert json.loads(request["params"]["data"])["redirect_uri"] == redirect
    finally:
        await client.deinit_async()


@pytest.mark.parametrize("finish", ["abort", "expire", "callback_then_abort"])
async def test_retained_oauth_session_closes_on_abandonment(hass, clients, finish):
    result, flow = await login_form(hass)
    assert flow._webhook_id.isdecimal()
    assert flow._state == clients[0].state
    assert flow._oauth is clients[0]
    clients[0].gen_auth_url.assert_called_once_with()
    clients[0].deinit_async.assert_not_awaited()
    if finish == "callback_then_abort":
        hook = flow._webhook_id
        await authorize(flow)
        clients[0].deinit_async.assert_not_awaited()
        replay = await flow._handle_callback(hass, hook, MagicMock(query={"state": flow._state, "code": "OTHER"}))
        assert replay.status == 400 and flow._code == "TEST-CODE"
    if finish == "expire":
        flow._expire()
    hass.config_entries.flow.async_abort(result["flow_id"])
    await hass.async_block_till_done()
    clients[0].deinit_async.assert_awaited_once()
    assert flow._oauth is None
