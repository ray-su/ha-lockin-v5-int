"""Cloud subscriptions, persistence, token lifecycle and safe event publication."""
from __future__ import annotations

import asyncio
from datetime import timedelta
import logging
import time

from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.core import callback
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryError
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from .api import auth_failure, http_client, oauth_client
from .const import DOMAIN, MODEL, READ_PROPERTIES
from .decoder import Decoder, LockState
from .miot.const import OAUTH2_CLIENT_ID
from .miot.miot_mips import MipsCloudClient, MIoTDeviceState

_LOGGER = logging.getLogger(__name__)


class LockinRuntime:
    def __init__(self, hass, entry, specification):
        self.hass, self.entry = hass, entry
        self.store = Store(hass, 1, f"{DOMAIN}.{entry.entry_id}")
        self.state = LockState(Decoder(specification))
        self.did = entry.data["device"]["did"]
        self.http = None
        self.mqtt = None
        self.connection = "Connecting"
        self.device_report = "Not reported"
        self.restored = True
        self._listeners: set = set()
        self._event_listeners: set = set()
        self._remove_timer = None
        self._remove_stop = None
        self._stopped = False
        self._refresh_lock = asyncio.Lock()
        self._retry_auth_at = 0.0
        self._reauth_pending = False
        self._storage_loaded = False

    async def prepare(self):
        if self.entry.data["device"].get("model") != MODEL:
            raise ConfigEntryError("Only loock.lock.v2203 is supported")
        saved = await self.store.async_load()
        self.state = LockState(self.state.decoder, saved if isinstance(saved, dict) else None)
        self._storage_loaded = True
        await self.refresh_auth()
        self.http = http_client(self.entry.data["region"], self.entry.data["uuid"], self.entry.data["auth"]["access_token"])
        try:
            devices = await self.http.get_devices_with_dids_async([self.did])
        except Exception as error:
            if auth_failure(error):
                raise ConfigEntryAuthFailed("Cloud authorization must be renewed") from None
            raise
        if not devices or self.did not in devices:
            raise ConfigEntryError("Selected lock is not accessible to this account")
        if devices[self.did].get("model") != MODEL:
            raise ConfigEntryError("Cloud model does not match loock.lock.v2203")
        self.device_report = "Online" if devices[self.did].get("online") else "Offline (sleep or disconnection)"
        # Cloud-cached read only. It does not establish current physical lock position.
        try:
            properties = await self.http.get_props_async([{"did": self.did, "siid": s, "piid": p} for s, p in READ_PROPERTIES])
            for item in properties:
                self.on_property(item, "cloud_cache")
        except Exception as error:
            if auth_failure(error):
                raise ConfigEntryAuthFailed("Cloud authorization must be renewed") from None
            _LOGGER.warning("Initial cached-property read failed (%s); waiting for push updates", type(error).__name__)

    async def start(self):
        self._open_mqtt()
        self._remove_timer = async_track_time_interval(self.hass, self._maintenance, timedelta(minutes=1))
        self._remove_stop = self.hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, self._on_stop)

    def _open_mqtt(self):
        self.mqtt = MipsCloudClient(uuid=self.entry.data["uuid"], cloud_server=self.entry.data["region"], app_id=OAUTH2_CLIENT_ID, token=self.entry.data["auth"]["access_token"], loop=self.hass.loop)
        self.mqtt.sub_mips_state(self.entry.entry_id, self._connection_changed)
        self.mqtt.connect()
        self.mqtt.sub_prop(self.did, self.on_property)
        self.mqtt.sub_event(self.did, self.on_event)
        self.mqtt.sub_device_state(self.did, self._device_changed)

    async def refresh_auth(self):
        async with self._refresh_lock:
            if float(self.entry.data["auth"].get("expires_ts", 0)) > time.time() + 300:
                return False
            client = oauth_client(self.entry.data["region"], self.entry.data["uuid"], self.entry.data["redirect"])
            try:
                auth = await client.refresh_access_token_async(self.entry.data["auth"]["refresh_token"])
                self.hass.config_entries.async_update_entry(self.entry, data={**self.entry.data, "auth": auth})
                if self.http:
                    self.http.update_http_header(access_token=auth["access_token"])
                return True
            except Exception as error:
                if auth_failure(error):
                    raise ConfigEntryAuthFailed("Cloud authorization must be renewed") from None
                raise
            finally:
                await client.deinit_async()

    async def _maintenance(self, _now):
        if self._stopped or self._reauth_pending or time.monotonic() < self._retry_auth_at:
            return
        try:
            refreshed = await self.refresh_auth()
            if refreshed and not self._stopped:
                # Create a fresh subscription client rather than leave an old MQTT login active.
                old, self.mqtt = self.mqtt, None
                if old:
                    await self.hass.async_add_executor_job(old.deinit)
                if not self._stopped:
                    self._open_mqtt()
        except ConfigEntryAuthFailed:
            self._reauth_pending = True
            old, self.mqtt = self.mqtt, None
            if old:
                await self.hass.async_add_executor_job(old.deinit)
            self.connection = "Authentication required"
            self._notify()
            self.entry.async_start_reauth(self.hass)
        except Exception as error:
            self._retry_auth_at = time.monotonic() + 300
            _LOGGER.warning("Cloud authorization refresh will retry (%s)", type(error).__name__)

    async def _connection_changed(self, _client_id, connected):
        if not self._stopped:
            self.connection = "Connected" if connected else "Disconnected"
            self._notify()

    @callback
    def _device_changed(self, did, state, _context):
        if self._stopped or did != self.did:
            return
        self.device_report = "Online" if state == MIoTDeviceState.ONLINE else "Offline (sleep or disconnection)"
        self._notify()

    def _matches(self, payload):
        return isinstance(payload, dict) and str(payload.get("did", self.did)) == self.did

    @callback
    def on_property(self, payload, context=None):
        if self._stopped or not self._matches(payload):
            return
        if self.state.apply_property(payload, dt_util.utcnow()):
            # Initial cloud snapshots can be stale; provenance is explicit.
            if context == "cloud_cache":
                decoded = self.state.decoder.property(payload, dt_util.utcnow())
                if decoded:
                    self.state.fields[decoded[0]]["delivery"] = "cloud_cache; device observation time unknown"
            else:
                self.restored = False
            self._save_and_notify()

    @callback
    def on_event(self, payload, _context=None):
        if self._stopped or not self._matches(payload):
            return
        now = dt_util.utcnow()
        event = self.state.apply_event(payload, now)
        if event is None:
            return
        self.restored = False
        self._save_and_notify()
        # Backfilled/old events may improve history but must never trigger a fresh unlock.
        fresh = timedelta(seconds=0) <= now - event.occurred_at <= timedelta(minutes=2)
        if event.category != "diagnostic" and fresh:
            for listener in tuple(self._event_listeners):
                listener(event)

    @callback
    def subscribe(self, listener, *, events=False):
        collection = self._event_listeners if events else self._listeners
        collection.add(listener)
        return lambda: collection.discard(listener)

    @callback
    def _notify(self):
        for listener in tuple(self._listeners):
            listener()

    @callback
    def _save_and_notify(self):
        self.store.async_delay_save(self.state.snapshot, 1)
        self._notify()

    async def _on_stop(self, _event):
        await self.stop()

    async def stop(self):
        if self._stopped:
            return
        self._stopped = True
        if self._remove_timer:
            self._remove_timer()
        if self._remove_stop:
            self._remove_stop()
        old, self.mqtt = self.mqtt, None
        if old:
            await self.hass.async_add_executor_job(old.deinit)
        if self.http:
            await self.http.deinit_async()
            self.http = None
        if self._storage_loaded:
            await self.store.async_save(self.state.snapshot())
        self._listeners.clear()
        self._event_listeners.clear()
