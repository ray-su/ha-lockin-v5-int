"""Exercise the actual vendored MQTT parser and HTTP adapter, sockets disabled."""
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.util import dt as dt_util
from custom_components.lockin_v5.miot.miot_mips import MipsCloudClient
from custom_components.lockin_v5.api import http_client, oauth_client
from .test_decoder import lock_event
from .test_ha import setup, by_name


async def test_actual_mqtt_decode_to_real_ha_state(hass, entry, cloud):
    runtime = await setup(hass, entry)
    mqtt = MipsCloudClient(uuid="test", cloud_server="sg", app_id="123", token="TEST-ONLY", loop=hass.loop)
    mqtt._internal_loop = MagicMock()
    mqtt._internal_loop.call_soon_threadsafe.side_effect = lambda fn, *args: fn(*args)
    with patch.object(mqtt, "_mips_sub_internal"):
        mqtt.sub_event("test-device", runtime.on_event)
        mqtt.sub_prop("test-device", runtime.on_property)
        mqtt.sub_device_state("test-device", runtime._device_changed)
    mqtt._on_mips_message("device/test-device/up/event_occured/2/1020", json.dumps({"params": {**lock_event(at=dt_util.utcnow()), "did": "test-device"}}).encode())
    mqtt._on_mips_message("device/test-device/up/properties_changed/4/1003", json.dumps({"params": {"did": "test-device", "siid": 4, "piid": 1003, "value": 67}}).encode())
    mqtt._on_mips_message("device/test-device/state/offline", json.dumps({"device_id": "test-device", "event": "offline"}).encode())
    await hass.async_block_till_done()
    assert by_name(hass, "Last lock activity").state == "Unlocked — face recognition — outside"
    assert by_name(hass, "Battery A").state == "67"
    assert by_name(hass, "Device connectivity report").state.startswith("Offline")
    assert by_name(hass, "Last reported lock state").state == "Unlocked"
    await hass.config_entries.async_unload(entry.entry_id)


@pytest.mark.parametrize("payload", [b"[]", b"null", b"garbage", b"{}", b"\xff"])
async def test_corrupt_mqtt_message_does_not_break_following_event(hass, payload):
    received = MagicMock()
    mqtt = MipsCloudClient(uuid="test", cloud_server="sg", app_id="123", token="TEST-ONLY", loop=hass.loop)
    mqtt._internal_loop = MagicMock()
    mqtt._internal_loop.call_soon_threadsafe.side_effect = lambda fn, *args: fn(*args)
    with patch.object(mqtt, "_mips_sub_internal"):
        mqtt.sub_event("test-device", received)
    mqtt._on_mips_message("device/test-device/up/event_occured/2/1020", payload)
    valid = {"params": lock_event(at=dt_util.utcnow())}
    mqtt._on_mips_message("device/test-device/up/event_occured/2/1020", json.dumps(valid).encode())
    await hass.async_block_till_done()
    received.assert_called_once()


async def test_real_oauth_url_and_mocked_token_exchange():
    client = oauth_client("sg", "test-uuid", "http://homeassistant.local:8123/api/webhook/test")
    try:
        url = client.gen_auth_url(state="TEST-STATE")
        assert "state=TEST-STATE" in url and "response_type=code" in url
        response = MagicMock(status=200)
        response.text = AsyncMock(return_value=json.dumps({"code": 0, "result": {"access_token": "TEST-ONLY", "refresh_token": "TEST-REFRESH", "expires_in": 3600}}))
        with patch.object(client._session, "get", new=AsyncMock(return_value=response)) as get:
            result = await client.get_access_token_async("TEST-CODE")
            assert result["access_token"] == "TEST-ONLY"
            assert get.call_args.kwargs["url"].startswith("https://sg.ha.api.io.mi.com/")
    finally:
        await client.deinit_async()


async def test_real_http_get_properties_request_is_read_only():
    client = http_client("sg", "test-uuid", "TEST-ONLY")
    try:
        response = MagicMock(status=200)
        response.text = AsyncMock(return_value=json.dumps({"code": 0, "result": [{"did": "test", "siid": 4, "piid": 1003, "value": 67}]}))
        with patch.object(client._session, "post", new=AsyncMock(return_value=response)) as post:
            result = await client.get_props_async([{"did": "test", "siid": 4, "piid": 1003}])
            assert result[0]["value"] == 67
            assert post.call_args.kwargs["url"].endswith("/prop/get")
            assert post.call_args.kwargs["json"]["datasource"] == 1
    finally:
        await client.deinit_async()
