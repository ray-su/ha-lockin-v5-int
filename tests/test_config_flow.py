"""OAuth/config-flow behavior, no real authorization or external requests."""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.components import webhook
from custom_components.lockin_v5.const import DOMAIN, MODEL


@pytest.fixture
def clients():
    oauth = MagicMock()
    oauth.gen_auth_url.return_value = "https://account.xiaomi.com/oauth2/authorize?state=TEST"
    oauth.deinit_async = AsyncMock()
    oauth.get_access_token_async = AsyncMock(return_value={"access_token": "TEST", "refresh_token": "TEST", "expires_ts": 4102444800})
    http = MagicMock()
    http.get_devices_async = AsyncMock(return_value={"devices": {"test-device": {"did": "test-device", "name": "Test Lockin", "model": MODEL, "fw_version": "1"}, "unsupported": {"did": "unsupported", "name": "Other lock", "model": "loock.lock.fcl201"}}})
    http.deinit_async = AsyncMock()
    with patch("custom_components.lockin_v5.config_flow.oauth_client", return_value=oauth), patch("custom_components.lockin_v5.config_flow.http_client", return_value=http), patch("custom_components.lockin_v5.async_setup_entry", return_value=True):
        yield oauth, http


async def login_form(hass):
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    assert result["type"] == FlowResultType.FORM and result["step_id"] == "user"
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"region": "sg"})
    flow = hass.config_entries.flow._progress[result["flow_id"]]
    assert result["step_id"] == "login"
    return result, flow


async def authorize(flow):
    req = MagicMock(query={"state": flow._state, "code": "TEST-CODE"})
    response = await flow._handle_callback(flow.hass, flow._webhook_id, req)
    assert response.status == 200
    assert flow._webhook_id is None


async def test_full_flow_filters_exact_model_and_closes_sessions(hass, clients):
    result, flow = await login_form(hass)
    await authorize(flow)
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["step_id"] == "device"
    assert list(flow._devices) == ["test-device"]
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"device": "test-device"})
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["data"]["device"]["model"] == MODEL
    assert "token" not in result["data"]["device"]
    assert clients[0].deinit_async.await_count == 2
    clients[1].deinit_async.assert_awaited_once()


async def test_bad_oauth_state_is_rejected(hass, clients):
    result, flow = await login_form(hass)
    response = await flow._handle_callback(hass, flow._webhook_id, MagicMock(query={"state": "WRONG", "code": "TEST"}))
    assert response.status == 400 and flow._code is None
    assert flow._webhook_id in hass.data[webhook.DOMAIN]
    hass.config_entries.flow.async_abort(result["flow_id"])
    assert flow._webhook_id is None and flow._expiry is None


async def test_pending_and_expired_login(hass, clients):
    result, flow = await login_form(hass)
    pending = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert pending["errors"]["base"] == "login_pending"
    flow._expire()
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["reason"] == "login_expired"


async def test_no_supported_model(hass, clients):
    clients[1].get_devices_async.return_value = {"devices": {"other": {"did": "other", "name": "Other", "model": "loock.lock.fcl201"}}}
    result, flow = await login_form(hass)
    await authorize(flow)
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["reason"] == "no_supported_device"


async def test_oauth_failure_is_sanitized(hass, clients, caplog):
    clients[0].get_access_token_async.side_effect = RuntimeError("SECRET-RAW-TOKEN")
    result, flow = await login_form(hass)
    await authorize(flow)
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["reason"] == "login_failed"
    assert "SECRET-RAW-TOKEN" not in caplog.text
    assert clients[0].deinit_async.await_count == 2


async def test_duplicate_device(hass, entry, clients):
    entry.add_to_hass(hass)
    result, flow = await login_form(hass)
    await authorize(flow)
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"device": "test-device"})
    assert result["reason"] == "already_configured"


async def test_reauth_same_lock(hass, entry, clients):
    entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_REAUTH, "entry_id": entry.entry_id}, data=entry.data)
    assert result["step_id"] == "reauth_confirm"
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    flow = hass.config_entries.flow._progress[result["flow_id"]]
    await authorize(flow)
    with patch.object(hass.config_entries, "async_reload", new=AsyncMock(return_value=True)):
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["reason"] == "reauth_successful"
    assert entry.data["auth"]["access_token"] == "TEST"


async def test_reauth_wrong_account(hass, entry, clients):
    entry.add_to_hass(hass)
    clients[1].get_devices_async.return_value = {"devices": {"other": {"did": "other", "name": "Other", "model": MODEL}}}
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_REAUTH, "entry_id": entry.entry_id}, data=entry.data)
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    flow = hass.config_entries.flow._progress[result["flow_id"]]
    await authorize(flow)
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["reason"] == "reauth_wrong_account"
    assert entry.data["auth"]["access_token"] == "TEST-ONLY"
