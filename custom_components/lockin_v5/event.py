"""Named event types for fresh operations, never emitted on state restoration."""
from homeassistant.components.event import EventEntity
from homeassistant.core import callback

from .const import EVENT_TYPES
from .sensor import device_info


async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities([LockinEvent(entry.runtime_data, category) for category in EVENT_TYPES])


class LockinEvent(EventEntity):
    _attr_should_poll = False
    _attr_has_entity_name = True

    def __init__(self, runtime, category):
        self.runtime = runtime
        self.category = category
        self._attr_unique_id = f"{runtime.entry.data['region']}:{runtime.did}:event:{category}"
        self._attr_name = {"lock": "Lock operation", "warning": "Warning reported", "visitor": "Visitor activity", "doorbell": "Doorbell"}[category]
        self._attr_translation_key = category
        self._attr_event_types = EVENT_TYPES[category]
        self._attr_device_info = device_info(runtime)

    @callback
    def _handle_event(self, event):
        if event.category != self.category:
            return
        self._trigger_event(event.event_type, {**event.attributes, "summary": event.summary, "occurred_at": event.occurred_at.isoformat(), "time_source": event.time_source})
        self.async_write_ha_state()

    async def async_added_to_hass(self):
        await super().async_added_to_hass()
        self.async_on_remove(self.runtime.subscribe(self._handle_event, events=True))
