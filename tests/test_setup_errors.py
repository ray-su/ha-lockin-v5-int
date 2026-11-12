"""Synthetic failure diagnostics: fixed labels/codes only, with external sockets blocked."""
import json
from pathlib import Path
import ssl
from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
import pytest

from custom_components.lockin_v5.api import auth_failure, http_client, oauth_client
from custom_components.lockin_v5.miot.miot_error import MIoTHttpError, MIoTOauthError
from custom_components.lockin_v5.setup_errors import safe_error_summary
from .test_config_flow import authorize, login_form
from .test_config_flow import clients as clients

SECRET = "SYNTHETIC-PRIVATE-PAYLOAD"


@pytest.mark.parametrize(("error", "expected"), [
    (TimeoutError(SECRET), "Request timed out"),
    (ssl.SSLError(SECRET), "TLS connection error"),
    (aiohttp.ClientConnectorDNSError(MagicMock(), OSError(SECRET)), "DNS lookup failed"),
    (aiohttp.ClientConnectionError(SECRET), "Connection failed"),
    (json.JSONDecodeError(SECRET, SECRET, 0), "Invalid JSON response"),
    (aiohttp.ClientError(SECRET), "HTTP client error"),
    (KeyError(SECRET), "Internal or response error (KeyError)"),
    (TypeError(SECRET), "Internal or response error (TypeError)"),
    (ValueError(SECRET), "Internal or response error (ValueError)"),
    (AttributeError(SECRET), "Internal or response error (AttributeError)"),
    (RuntimeError(SECRET), "Unexpected internal error"),
])
def test_allowlisted_exception_categories(error, expected):
    assert safe_error_summary(error) == expected
    assert SECRET not in safe_error_summary(error)


@pytest.mark.parametrize("bad", [SECRET, True, 3.5, None, [], {}, 999999999999999999])
def test_invalid_numeric_metadata_is_never_exposed(bad):
    error = MIoTOauthError(SECRET, http_status=bad, cloud_code=bad)
    assert safe_error_summary(error) == "OAuth response error"
    error.http_status = bad
    error.cloud_code = bad
    assert safe_error_summary(error) == "OAuth response error"


def test_numeric_codes_not_confused_with_internal_sdk_code():
    error = MIoTOauthError(SECRET, http_status=200, cloud_code=-12345)
    assert safe_error_summary(error) == "OAuth response error; HTTP 200; API code -12345"
    assert "-10000" not in safe_error_summary(error)


@pytest.mark.parametrize("status", [401, 403, 503])
async def test_oauth_transport_preserves_only_http_status(status):
    client = oauth_client("sg", "synthetic-uuid", "http://homeassistant.local:8123/api/webhook/test")
    try:
        response = MagicMock(status=status)
        response.text = AsyncMock(return_value=SECRET)
        with patch.object(client._session, "get", new=AsyncMock(return_value=response)):
            with pytest.raises(MIoTOauthError) as caught:
                await client.get_access_token_async("SYNTHETIC-CODE")
        assert caught.value.http_status == status
        assert auth_failure(caught.value) is (status == 401)
        assert SECRET not in str(caught.value)
        response.text.assert_not_awaited()
    finally:
        await client.deinit_async()


@pytest.mark.parametrize("body", [
    {"code": -12345, "message": SECRET, "result": {"access_token": SECRET}},
    {"code": SECRET, "message": SECRET},
    {"code": 0, "result": SECRET},
    [SECRET],
    None,
])
async def test_oauth_response_payload_is_not_leaked(body):
    client = oauth_client("sg", "synthetic-uuid", "http://homeassistant.local:8123/api/webhook/test")
    try:
        response = MagicMock(status=200)
        response.text = AsyncMock(return_value=json.dumps(body))
        with patch.object(client._session, "get", new=AsyncMock(return_value=response)):
            with pytest.raises(MIoTOauthError) as caught:
                await client.get_access_token_async("SYNTHETIC-CODE")
        assert caught.value.http_status == 200
        assert SECRET not in str(caught.value) + safe_error_summary(caught.value)
        if isinstance(body, dict) and body.get("code") == -12345:
            assert caught.value.cloud_code == -12345
    finally:
        await client.deinit_async()


@pytest.mark.parametrize("method", ["get", "post"])
@pytest.mark.parametrize("status", [200, 401, 503])
async def test_real_cloud_transport_retains_safe_error_metadata(method, status):
    client = http_client("sg", "synthetic-uuid", "SYNTHETIC-TOKEN")
    try:
        response = MagicMock(status=status)
        response.text = AsyncMock(return_value=json.dumps({"code": -23456, "message": SECRET}))
        with patch.object(client._session, method, new=AsyncMock(return_value=response)):
            with pytest.raises(MIoTHttpError) as caught:
                if method == "post":
                    await client.get_devices_async()
                else:
                    await client._MIoTHttpClient__mihome_api_get_async("/synthetic", {"synthetic": SECRET})
        assert caught.value.http_status == status
        assert caught.value.cloud_code == (-23456 if status == 200 else None)
        assert auth_failure(caught.value) is (status == 401)
        assert SECRET not in str(caught.value) + safe_error_summary(caught.value)
    finally:
        await client.deinit_async()


@pytest.mark.parametrize("stage", ["token exchange", "device discovery"])
async def test_failure_stage_in_abort_and_logs_without_secrets(hass, clients, caplog, stage):
    result, flow = await login_form(hass)
    await authorize(flow)
    if stage == "token exchange":
        clients[0].get_access_token_async.side_effect = MIoTOauthError(SECRET, http_status=200, cloud_code=-12345)
    else:
        clients[1].get_devices_async.side_effect = MIoTHttpError(SECRET, http_status=503)
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["reason"] == "login_failed"
    placeholders = result["description_placeholders"]
    assert placeholders["stage"] == stage
    assert "HTTP" in placeholders["detail"]
    assert stage in caplog.text
    assert SECRET not in json.dumps(result) + caplog.text
    strings = json.loads((Path(__file__).resolve().parents[1] / "custom_components/lockin_v5/strings.json").read_text())
    rendered = strings["config"]["abort"]["login_failed"].format(**placeholders)
    assert stage in rendered and SECRET not in rendered
    clients[0].deinit_async.assert_awaited()
    if stage == "device discovery":
        clients[1].deinit_async.assert_awaited_once()


async def test_token_client_constructor_failure_is_safe(hass, clients, caplog):
    result, flow = await login_form(hass)
    await authorize(flow)
    with patch("custom_components.lockin_v5.config_flow.oauth_client", side_effect=RuntimeError(SECRET)):
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["reason"] == "login_failed"
    assert result["description_placeholders"] == {
        "stage": "token exchange", "detail": "Unexpected internal error"}
    assert SECRET not in caplog.text


async def test_callback_host_change_does_not_replace_registered_redirect(hass, clients):
    result, flow = await login_form(hass)
    original = flow._redirect
    response = await flow._handle_callback(hass, flow._webhook_id, MagicMock(
        host="127.0.0.1:8123", query={"state": flow._state, "code": "SYNTHETIC-CODE"}))
    assert response.status == 200 and flow._redirect == original
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["step_id"] == "device"
    hass.config_entries.flow.async_abort(result["flow_id"])
