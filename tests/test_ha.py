"""Real Home Assistant setup/entity/unload tests; device transport is mocked."""
from datetime import timedelta
from unittest.mock import AsyncMock, patch

from homeassistant.util import dt as dt_util
from custom_components.lockin_v5.const import DOMAIN
from custom_components.lockin_v5.diagnostics import async_get_config_entry_diagnostics
from custom_components.lockin_v5.miot.miot_error import MIoTHttpError, MIoTErrorCode
from custom_components.lockin_v5.api import ReadOnlyClient
from .test_decoder import lock_event


async def setup(hass, entry):
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry.runtime_data


def by_name(hass, suffix):
    return next(s for s in hass.states.async_all() if s.attributes.get("friendly_name", "").endswith(suffix))


async def test_setup_entities_sleep_and_unload(hass, entry, cloud):
    runtime = await setup(hass, entry)
    http, mqtt = cloud
    mqtt.connect.assert_called_once()
    mqtt.sub_event.assert_called_once()
    assert by_name(hass, "Last lock activity").state == "unknown"
    now = dt_util.utcnow()
    runtime.on_event(lock_event(at=now))
    await hass.async_block_till_done()
    assert by_name(hass, "Last lock activity").state == "Unlocked — face recognition — outside"
    assert by_name(hass, "Last reported lock state").state == "Unlocked"
    event_state = by_name(hass, "Lock operation")
    assert event_state.attributes["event_type"] == "unlocked"
    runtime.on_event(lock_event(at=now))
    assert by_name(hass, "Lock operation").state == event_state.state
    await runtime._connection_changed("test", False)
    assert by_name(hass, "Cloud connection").state == "Disconnected"
    assert by_name(hass, "Last lock activity").state != "unavailable"
    assert not [s for s in hass.states.async_all() if s.entity_id.startswith("lock.")]
    assert not hass.services.has_service(DOMAIN, "unlock")
    assert await hass.config_entries.async_unload(entry.entry_id)
    mqtt.deinit.assert_called_once()
    http.deinit_async.assert_awaited_once()
    assert not runtime._listeners and not runtime._event_listeners


async def test_restore_and_no_replayed_unlock(hass, entry, cloud):
    runtime = await setup(hass, entry)
    payload = lock_event(at=dt_util.utcnow())
    runtime.on_event(payload)
    await hass.config_entries.async_unload(entry.entry_id)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    restored = entry.runtime_data
    assert by_name(hass, "Last reported lock state").state == "Unlocked"
    before = by_name(hass, "Lock operation")
    restored.on_event(payload)
    assert by_name(hass, "Lock operation").state == before.state
    await hass.config_entries.async_unload(entry.entry_id)


async def test_old_event_updates_history_not_fresh_event(hass, entry, cloud):
    runtime = await setup(hass, entry)
    runtime.on_event(lock_event(at=dt_util.utcnow() - timedelta(hours=1)))
    assert by_name(hass, "Last lock activity").state.startswith("Unlocked")
    assert by_name(hass, "Lock operation").state == "unknown"
    await hass.config_entries.async_unload(entry.entry_id)


async def test_wrong_device_payload_ignored(hass, entry, cloud):
    runtime = await setup(hass, entry)
    runtime.on_event({**lock_event(at=dt_util.utcnow()), "did": "other-device"})
    assert by_name(hass, "Last reported lock state").state == "unknown"
    await hass.config_entries.async_unload(entry.entry_id)


async def test_unsupported_model(hass, entry, cloud):
    entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(entry, data={**entry.data, "device": {"did": "test-device", "model": "loock.lock.fcl201"}})
    assert not await hass.config_entries.async_setup(entry.entry_id)
    cloud[1].connect.assert_not_called()


async def test_http_auth_failure(hass, entry, cloud):
    cloud[0].get_devices_with_dids_async.side_effect = MIoTHttpError("private body", MIoTErrorCode.CODE_HTTP_INVALID_ACCESS_TOKEN)
    entry.add_to_hass(hass)
    assert not await hass.config_entries.async_setup(entry.entry_id)
    cloud[1].connect.assert_not_called()
    cloud[0].deinit_async.assert_awaited_once()


async def test_refresh_persists_token_and_reconnects(hass, entry, cloud):
    runtime = await setup(hass, entry)
    auth = {"access_token": "NEW-TEST", "refresh_token": "NEW-REFRESH", "expires_ts": 4102444800}
    hass.config_entries.async_update_entry(entry, data={**entry.data, "auth": {**entry.data["auth"], "expires_ts": 0}})
    fake = AsyncMock()
    fake.refresh_access_token_async.return_value = auth
    with patch("custom_components.lockin_v5.runtime.oauth_client", return_value=fake):
        await runtime._maintenance(None)
    assert entry.data["auth"] == auth
    fake.deinit_async.assert_awaited_once()
    cloud[1].deinit.assert_called_once()
    assert cloud[1].connect.call_count == 2
    await hass.config_entries.async_unload(entry.entry_id)


async def test_diagnostics_no_secrets_or_history(hass, entry, cloud):
    runtime = await setup(hass, entry)
    runtime.on_event(lock_event(at=dt_util.utcnow()))
    result = str(await async_get_config_entry_diagnostics(hass, entry))
    assert "TEST-ONLY" not in result and "test-device" not in result
    assert "face recognition" not in result
    await hass.config_entries.async_unload(entry.entry_id)


async def test_control_paths_fail_closed():
    client = ReadOnlyClient.__new__(ReadOnlyClient)
    for method in (client.action_async, client.set_prop_async):
        try:
            await method([])
        except PermissionError:
            pass
        else:
            raise AssertionError("A write method was allowed")
