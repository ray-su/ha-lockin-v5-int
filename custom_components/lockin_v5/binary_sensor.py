"""Read-only binary projection of the existing last reported lock state."""
from homeassistant.components.binary_sensor import BinarySensorDeviceClass, BinarySensorEntity

from .sensor import device_info


async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities([LockinLockReport(entry.runtime_data)])


class LockinLockReport(BinarySensorEntity):
    """On means unlocked; never infer physical door position."""

    _attr_should_poll = False
    _attr_has_entity_name = True
    _attr_name = "Front door lock"
    # Visualization proxy: NeonPlan3D's Contact picker accepts door, not lock.
    # Preserve identity and state mapping; this is NOT a physical door contact.
    _attr_device_class = BinarySensorDeviceClass.DOOR

    def __init__(self, runtime):
        self.runtime = runtime
        self._attr_unique_id = f"{runtime.entry.data['region']}:{runtime.did}:lock_report_binary"
        self._attr_device_info = device_info(runtime)

    @property
    def is_on(self):
        value = self.runtime.state.fields.get("reported_lock_state", {}).get("value")
        return {"Locked": False, "Unlocked": True}.get(value)

    @property
    def extra_state_attributes(self):
        field = self.runtime.state.fields.get("reported_lock_state", {})
        return {
            **{key: value for key, value in field.items() if key != "value"},
            "last_observation_only": True,
            "cloud_connection": self.runtime.connection,
            "caution": "Last reported locked/unlocked state, not physical door open/closed. Retained reports may be stale.",
        }

    async def async_added_to_hass(self):
        await super().async_added_to_hass()
        self.async_on_remove(self.runtime.subscribe(self.async_write_ha_state))
