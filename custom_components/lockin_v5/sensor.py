"""Human-readable observations, kept separate from transport availability."""
from __future__ import annotations

from homeassistant.components.sensor import SensorEntity, SensorDeviceClass, SensorStateClass
from homeassistant.const import EntityCategory, PERCENTAGE
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.util import dt as dt_util

from .const import DOMAIN, MODEL, NAME

# key, visible name, icon, device class, diagnostic, enabled by default
DESCRIPTIONS = [
    ("lock_activity", "Last lock activity", "mdi:history", None, False, True),
    ("last_operation", "Last lock operation", "mdi:lock-clock", None, False, True),
    ("reported_lock_state", "Last reported lock state", "mdi:lock-question", None, False, True),
    ("last_method", "Last access method", "mdi:face-recognition", None, False, True),
    ("last_side", "Last operation side", "mdi:door", None, False, True),
    ("last_operation_time", "Last lock operation time", "mdi:clock", SensorDeviceClass.TIMESTAMP, False, True),
    ("last_unlock_time", "Last unlocked", "mdi:lock-open", SensorDeviceClass.TIMESTAMP, False, True),
    ("last_warning", "Last warning", "mdi:alert-outline", None, False, True),
    ("door_report", "Last door-condition report", "mdi:door", None, False, True),
    ("battery_a", "Battery A", "mdi:battery", SensorDeviceClass.BATTERY, False, True),
    ("battery_b", "Battery B", "mdi:battery", SensorDeviceClass.BATTERY, False, True),
    ("battery_presence", "Batteries and USB", "mdi:battery-sync", None, False, True),
    ("last_visitor", "Last visitor activity", "mdi:account-eye", None, False, True),
    ("last_doorbell_time", "Last doorbell press", "mdi:doorbell", SensorDeviceClass.TIMESTAMP, False, True),
    ("connection", "Cloud connection", "mdi:cloud-check", None, True, True),
    ("device_report", "Device connectivity report", "mdi:wifi", None, True, True),
    ("video_status", "Last video-module status", "mdi:video", None, True, True),
    ("last_received", "Last data received", "mdi:clock-check", SensorDeviceClass.TIMESTAMP, True, True),
    ("battery_updated", "Battery report time", "mdi:clock", SensorDeviceClass.TIMESTAMP, True, True),
    ("last_diagnostic", "Firmware diagnostic", "mdi:code-braces", None, True, False),
]


def device_info(runtime):
    info = runtime.entry.data["device"]
    return DeviceInfo(identifiers={(DOMAIN, f"{runtime.entry.data['region']}:{runtime.did}")}, manufacturer="Lockin", model=NAME, model_id=MODEL, name=info.get("name") or NAME, sw_version=info.get("fw_version"))


async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities([LockinSensor(entry.runtime_data, description) for description in DESCRIPTIONS])


class LockinSensor(SensorEntity):
    _attr_should_poll = False
    _attr_has_entity_name = True

    def __init__(self, runtime, description):
        self.runtime = runtime
        self.key, name, icon, device_class, diagnostic, enabled = description
        self._attr_unique_id = f"{runtime.entry.data['region']}:{runtime.did}:{self.key}"
        self._attr_name = name
        self._attr_icon = icon
        self._attr_device_info = device_info(runtime)
        self._attr_device_class = device_class
        self._attr_entity_registry_enabled_default = enabled
        if diagnostic:
            self._attr_entity_category = EntityCategory.DIAGNOSTIC
        if device_class == SensorDeviceClass.BATTERY:
            self._attr_native_unit_of_measurement = PERCENTAGE
            self._attr_state_class = SensorStateClass.MEASUREMENT

    @property
    def native_value(self):
        if self.key == "connection":
            return self.runtime.connection
        if self.key == "device_report":
            return self.runtime.device_report
        value = self.runtime.state.fields.get(self.key, {}).get("value")
        if value is not None and self.device_class == SensorDeviceClass.TIMESTAMP:
            return dt_util.parse_datetime(value)
        return value

    @property
    def extra_state_attributes(self):
        if self.key in ("connection", "device_report"):
            return {"does_not_confirm_lock_or_door_position": True}
        field = self.runtime.state.fields.get(self.key, {})
        attrs = {k: v for k, v in field.items() if k != "value"}
        attrs.update({"last_observation_only": True, "cloud_connection": self.runtime.connection})
        if self.key == "door_report":
            attrs["caution"] = "This property has remained Locked across an observed unlock; not a reliable live lock or door-contact state."
        if self.key in ("battery_a", "battery_b"):
            attrs["battery_identity"] = "Service 4" if self.key == "battery_a" else "Service 10"
            attrs["caution"] = "Mapping to large/small physical battery is not verified."
        return attrs

    async def async_added_to_hass(self):
        await super().async_added_to_hass()
        self.async_on_remove(self.runtime.subscribe(self.async_write_ha_state))
