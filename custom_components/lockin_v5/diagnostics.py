"""Intentionally limited diagnostics: no credentials, IDs, payloads or household history."""
from .const import MODEL, VERSION


async def async_get_config_entry_diagnostics(hass, entry):
    runtime = entry.runtime_data
    return {
        "integration_version": VERSION,
        "model": MODEL,
        "connection": runtime.connection,
        "known_field_names": sorted(runtime.state.fields),
        "dedup_entries": len(runtime.state.seen),
        "cloud_dependent": True,
        "device_control_supported": False,
    }
