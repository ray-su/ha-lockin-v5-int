"""Failure/recovery paths using real HA storage and entry state."""
from unittest.mock import AsyncMock, patch

from homeassistant.config_entries import ConfigEntryState
from homeassistant.util import dt as dt_util
from custom_components.lockin_v5 import async_unload_entry, async_remove_entry
from custom_components.lockin_v5.miot.miot_error import MIoTOauthError, MIoTErrorCode
from .test_ha import setup, by_name
from .test_decoder import lock_event


async def test_initial_cloud_cache_is_marked_and_survives_sleep(hass, entry, cloud):
    cloud[0].get_props_async.return_value = [{"did": "test-device", "siid": 4, "piid": 1003, "value": 67}, {"did": "test-device", "siid": 4, "piid": 1034, "value": 3}]
    runtime = await setup(hass, entry)
    assert by_name(hass, "Battery A").state == "67"
    assert "cloud_cache" in by_name(hass, "Battery A").attributes["delivery"]
    assert by_name(hass, "Batteries and USB").state == "Both batteries installed"
    await runtime._connection_changed("test", False)
    assert by_name(hass, "Battery A").state == "67"
    await hass.config_entries.async_unload(entry.entry_id)


async def test_property_read_failure_does_not_block_event_subscription(hass, entry, cloud, caplog):
    cloud[0].get_props_async.side_effect = TimeoutError("PRIVATE-EXCEPTION-BODY")
    runtime = await setup(hass, entry)
    assert "PRIVATE-EXCEPTION-BODY" not in caplog.text
    runtime.on_event(lock_event(at=dt_util.utcnow()))
    assert by_name(hass, "Last reported lock state").state == "Unlocked"
    await hass.config_entries.async_unload(entry.entry_id)


async def test_setup_transport_failure_retries_without_leaking_exception(hass, entry, cloud, caplog):
    cloud[0].get_devices_with_dids_async.side_effect = TimeoutError("PRIVATE-EXCEPTION-BODY")
    entry.add_to_hass(hass)
    assert not await hass.config_entries.async_setup(entry.entry_id)
    assert entry.state == ConfigEntryState.SETUP_RETRY
    assert "PRIVATE-EXCEPTION-BODY" not in caplog.text
    cloud[0].deinit_async.assert_awaited_once()


async def test_revoked_token_requests_reauth_and_stops_mqtt(hass, entry, cloud):
    runtime = await setup(hass, entry)
    hass.config_entries.async_update_entry(entry, data={**entry.data, "auth": {**entry.data["auth"], "expires_ts": 0}})
    fake = AsyncMock()
    fake.refresh_access_token_async.side_effect = MIoTOauthError("PRIVATE", MIoTErrorCode.CODE_OAUTH_UNAUTHORIZED)
    with patch("custom_components.lockin_v5.runtime.oauth_client", return_value=fake), patch.object(type(entry), "async_start_reauth") as reauth:
        await runtime._maintenance(None)
        await runtime._maintenance(None)
    reauth.assert_called_once()
    assert by_name(hass, "Cloud connection").state == "Authentication required"
    cloud[1].deinit.assert_called_once()
    await hass.config_entries.async_unload(entry.entry_id)


async def test_transient_token_failure_backs_off_without_reauth(hass, entry, cloud):
    runtime = await setup(hass, entry)
    hass.config_entries.async_update_entry(entry, data={**entry.data, "auth": {**entry.data["auth"], "expires_ts": 0}})
    fake = AsyncMock()
    fake.refresh_access_token_async.side_effect = TimeoutError("PRIVATE")
    with patch("custom_components.lockin_v5.runtime.oauth_client", return_value=fake), patch.object(type(entry), "async_start_reauth") as reauth:
        await runtime._maintenance(None)
        await runtime._maintenance(None)
    fake.refresh_access_token_async.assert_awaited_once()
    reauth.assert_not_called()
    await hass.config_entries.async_unload(entry.entry_id)


async def test_failed_platform_unload_leaves_runtime_intact(hass, entry, cloud):
    await setup(hass, entry)
    with patch.object(hass.config_entries, "async_unload_platforms", new=AsyncMock(return_value=False)):
        assert not await async_unload_entry(hass, entry)
    cloud[1].deinit.assert_not_called()
    await hass.config_entries.async_unload(entry.entry_id)


async def test_removed_entry_deletes_only_own_observation_store(hass, entry, cloud, hass_storage):
    runtime = await setup(hass, entry)
    runtime.on_event(lock_event(at=dt_util.utcnow()))
    await hass.config_entries.async_unload(entry.entry_id)
    assert runtime.store.key in hass_storage
    hass_storage["unrelated.integration"] = {"version": 1, "data": {"preserve": True}}
    await async_remove_entry(hass, entry)
    # Inspect the persisted backing store, not a previously loaded Store's cache.
    assert runtime.store.key not in hass_storage
    assert hass_storage["unrelated.integration"]["data"] == {"preserve": True}


async def test_stopped_runtime_ignores_late_callbacks(hass, entry, cloud):
    runtime = await setup(hass, entry)
    await hass.config_entries.async_unload(entry.entry_id)
    runtime.on_event(lock_event(at=dt_util.utcnow()))
    runtime.on_property({"siid": 4, "piid": 1003, "value": 12})
    await runtime.stop()
    assert not runtime.state.fields
    cloud[1].deinit.assert_called_once()
