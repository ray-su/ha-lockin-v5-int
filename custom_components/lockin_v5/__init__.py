"""Dedicated, read-only Lockin V5 Max INT integration."""
from __future__ import annotations

import asyncio
import json
from pathlib import Path

from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryError, ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.storage import Store

from .const import DOMAIN, PLATFORMS
from .runtime import LockinRuntime

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


def _read_specification():
    return json.loads(Path(__file__).with_name("miot-v2203.json").read_text())


async def async_setup_entry(hass, entry):
    specification = await hass.async_add_executor_job(_read_specification)
    runtime = LockinRuntime(hass, entry, specification)
    entry.runtime_data = runtime
    forwarded = False
    try:
        await runtime.prepare()
        forwarded = True
        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
        await runtime.start()
    except BaseException as error:
        if forwarded:
            await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
        await runtime.stop()
        if isinstance(error, (ConfigEntryAuthFailed, ConfigEntryError, asyncio.CancelledError)):
            raise
        if not isinstance(error, Exception):
            raise
        # Do not expose upstream exception bodies, which can contain tokens.
        raise ConfigEntryNotReady(f"Cloud setup failed ({type(error).__name__})") from None
    return True


async def async_unload_entry(hass, entry):
    if not await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        return False
    await entry.runtime_data.stop()
    return True


async def async_remove_entry(hass, entry):
    await Store(hass, 1, f"{DOMAIN}.{entry.entry_id}").async_remove()
