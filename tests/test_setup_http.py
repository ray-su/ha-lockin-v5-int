"""Exercise the browser-facing setup endpoint without cloud or live HA access."""
from unittest.mock import patch

from homeassistant.setup import async_setup_component
from homeassistant.components.config.config_entries import ConfigManagerFlowIndexView
from pytest_socket import socket_allow_hosts

from custom_components.lockin_v5.const import DOMAIN


async def test_initial_form_serialization(hass):
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})
    try:
        payload = ConfigManagerFlowIndexView(hass.config_entries.flow)._prepare_result_json(result)
        assert payload["type"] == "form"
        assert payload["step_id"] == "user"
        assert payload["data_schema"][0]["name"] == "region"
        assert payload["data_schema"][0]["default"] == "sg"
    finally:
        hass.config_entries.flow.async_abort(result["flow_id"])


async def test_initial_setup_http_returns_region_form(hass, hass_client):
    # hass_client enables sockets for its test server; restrict connections again.
    socket_allow_hosts(["127.0.0.1", "::1"], allow_unix_socket=True)
    assert await async_setup_component(hass, "config", {})
    client = await hass_client()
    with patch("custom_components.lockin_v5.config_flow.oauth_client") as oauth, patch(
        "custom_components.lockin_v5.config_flow.http_client"
    ) as cloud:
        response = await client.post("/api/config/config_entries/flow", json={"handler": DOMAIN})
        assert response.status == 200, await response.text()
        payload = await response.json()
        try:
            assert payload["type"] == "form"
            assert payload["step_id"] == "user"
            assert payload["data_schema"][0]["name"] == "region"
            assert payload["data_schema"][0]["default"] == "sg"
            oauth.assert_not_called()
            cloud.assert_not_called()
        finally:
            hass.config_entries.flow.async_abort(payload["flow_id"])
