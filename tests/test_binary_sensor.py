"""Additive binary sensor behavior exercised in real HA with mocked cloud."""
from datetime import timedelta

from homeassistant.util import dt as dt_util
from .test_decoder import lock_event
from .test_ha import setup, by_name


async def test_one_binary_sensor_and_unknown_initial_state(hass, entry, cloud):
    await setup(hass, entry)
    sensors = hass.states.async_all("binary_sensor")
    assert len(sensors) == 1
    state = sensors[0]
    assert state.attributes["friendly_name"].endswith("Front door lock")
    assert state.attributes["device_class"] == "door"
    # Match the inspected NeonPlan3D Contact selector's eligibility predicate.
    assert state.entity_id.startswith("binary_sensor.")
    assert state.attributes["device_class"] in ("door", "window", "opening", "garage_door", "")
    assert state.state == "unknown"
    assert state.attributes["last_observation_only"] is True
    assert "physical door" in state.attributes["caution"]
    await hass.config_entries.async_unload(entry.entry_id)


async def test_binary_tracks_existing_report_without_changing_other_entities(hass, entry, cloud):
    runtime = await setup(hass, entry)
    now = dt_util.utcnow()
    for action, expected, label, offset in ((2, "on", "Unlocked", 0), (1, "off", "Locked", 1)):
        runtime.on_event(lock_event(action=action, at=now + timedelta(seconds=offset)))
        await hass.async_block_till_done()
        assert by_name(hass, "Front door lock").state == expected
        assert by_name(hass, "Last reported lock state").state == label
        assert by_name(hass, "Last lock operation").state == label
    before = by_name(hass, "Front door lock")
    # Door-condition properties and interior-lock activity are not bolt reports.
    runtime.on_property({"siid": 3, "piid": 1021, "value": 32})
    runtime.on_event(lock_event(action=4, at=now + timedelta(seconds=2)))
    await hass.async_block_till_done()
    assert by_name(hass, "Front door lock").state == "off"
    assert by_name(hass, "Front door lock").attributes["observed_at"] == before.attributes["observed_at"]
    await runtime._connection_changed("test", False)
    assert by_name(hass, "Front door lock").state == "off"
    assert by_name(hass, "Front door lock").attributes["cloud_connection"] == "Disconnected"
    assert await hass.config_entries.async_unload(entry.entry_id)
    assert not runtime._listeners


async def test_binary_restores_same_report_without_polling_or_new_events(hass, entry, cloud):
    runtime = await setup(hass, entry)
    runtime.on_event(lock_event(at=dt_util.utcnow()))
    await hass.async_block_till_done()
    old = by_name(hass, "Front door lock")
    old_event = by_name(hass, "Lock operation").state
    await hass.config_entries.async_unload(entry.entry_id)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    restored = by_name(hass, "Front door lock")
    assert restored.entity_id == old.entity_id
    assert restored.state == "on"
    assert restored.attributes["observed_at"] == old.attributes["observed_at"]
    assert by_name(hass, "Lock operation").state in ("unknown", old_event)
    await hass.config_entries.async_unload(entry.entry_id)
