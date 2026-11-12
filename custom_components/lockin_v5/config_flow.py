"""Independent OAuth setup; only loock.lock.v2203 is selectable."""
from __future__ import annotations

import hmac
import logging
import secrets
from typing import Any

from aiohttp import web
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components import webhook
from homeassistant.core import callback

from .api import http_client, oauth_authorization, oauth_client, redirect_url
from .const import DOMAIN, MODEL, NAME, REGIONS
from .miot.common import get_system_info_str
from .setup_errors import safe_error_summary

_LOGGER = logging.getLogger(__name__)


class LockinConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    def __init__(self):
        self._uuid = secrets.token_hex(16)
        self._state = secrets.token_urlsafe(32)
        self._webhook_id: str | None = None
        self._expiry = None
        self._code: str | None = None
        self._expired = False
        self._region = "sg"
        self._redirect = ""
        self._url = ""
        self._auth: dict = {}
        self._devices: dict = {}
        self._reauth = None
        self._oauth = None

    async def async_step_user(self, user_input: dict[str, Any] | None = None):
        if user_input is not None:
            self._region = user_input["region"]
            return await self._begin_login()
        return self.async_show_form(step_id="user", data_schema=vol.Schema({vol.Required("region", default="sg"): vol.In(REGIONS)}))

    async def async_step_reauth(self, entry_data):
        self._reauth = self._get_reauth_entry()
        self._region = entry_data["region"]
        self._uuid = entry_data["uuid"]
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(self, user_input=None):
        if user_input is not None:
            return await self._begin_login()
        return self.async_show_form(step_id="reauth_confirm", data_schema=vol.Schema({}))

    async def _begin_login(self):
        self._cleanup()
        if self._oauth is not None:
            await self._oauth.deinit_async()
            self._oauth = None
        self._code = None
        self._expired = False
        self._webhook_id = str(secrets.randbits(64))
        self._redirect = redirect_url(self._webhook_id)
        system_info = await get_system_info_str(self.hass)
        client = oauth_client(self._region, self._uuid, self._redirect, system_info=system_info)
        try:
            self._state, self._url = oauth_authorization(client)
            webhook.async_register(self.hass, DOMAIN, NAME, self._webhook_id, self._handle_callback, allowed_methods=("GET",), local_only=True)
        except Exception:
            await client.deinit_async()
            raise
        self._oauth = client
        self._expiry = self.hass.loop.call_later(600, self._expire)
        return await self.async_step_login()

    async def _handle_callback(self, hass, webhook_id, request):
        state = request.query.get("state", "")
        code = request.query.get("code", "")
        if self._expired or webhook_id != self._webhook_id or self._code is not None or not hmac.compare_digest(state, self._state) or not code or len(code) > 4096:
            return web.Response(status=400, text="Invalid or expired authorization. Start again in Home Assistant.")
        self._code = code
        # One use only; no code or token in response/logs.
        self._cleanup()
        return web.Response(text="Authorization received. Return to the Lockin setup form and press Submit.", headers={"Cache-Control": "no-store", "Referrer-Policy": "no-referrer"})

    @callback
    def _expire(self):
        self._expired = True
        self._cleanup()
        self._close_oauth()

    @callback
    def _close_oauth(self):
        if self._oauth is not None:
            client, self._oauth = self._oauth, None
            self.hass.async_create_task(client.deinit_async())

    @callback
    def _cleanup(self):
        if self._webhook_id:
            webhook.async_unregister(self.hass, self._webhook_id)
            self._webhook_id = None
        if self._expiry:
            self._expiry.cancel()
            self._expiry = None

    @callback
    def async_remove(self):
        self._cleanup()
        self._close_oauth()
        self._code = None
        self._auth = {}
        super().async_remove()

    async def async_step_login(self, user_input=None):
        if self._expired:
            return self.async_abort(reason="login_expired")
        errors = {}
        if user_input is not None:
            if not self._code:
                errors["base"] = "login_pending"
            else:
                stage = "token exchange"
                client = None
                http = None
                try:
                    client, self._oauth = self._oauth, None
                    if client is None:
                        raise RuntimeError("OAuth session unavailable")
                    self._auth = await client.get_access_token_async(code=self._code)
                    self._code = None
                    stage = "device discovery"
                    http = http_client(self._region, self._uuid, self._auth["access_token"])
                    result = await http.get_devices_async()
                    self._devices = {
                        str(did): {key: info.get(key) for key in ("did", "model", "name", "fw_version")}
                        for did, info in result["devices"].items() if info.get("model") == MODEL
                    }
                except Exception as error:
                    # Never log raw exception text, URLs, headers, or cloud bodies.
                    detail = safe_error_summary(error)
                    _LOGGER.warning("Lockin setup failed during %s: %s", stage, detail)
                    return self.async_abort(reason="login_failed", description_placeholders={"stage": stage, "detail": detail})
                finally:
                    if client:
                        await client.deinit_async()
                    if http:
                        await http.deinit_async()
                if not self._devices:
                    return self.async_abort(reason="no_supported_device")
                if self._reauth:
                    did = self._reauth.data["device"]["did"]
                    if did not in self._devices:
                        return self.async_abort(reason="reauth_wrong_account")
                    return self.async_update_reload_and_abort(self._reauth, data_updates={"auth": self._auth, "redirect": self._redirect, "device": self._devices[did]})
                return await self.async_step_device()
        return self.async_show_form(step_id="login", data_schema=vol.Schema({}), errors=errors, description_placeholders={"login_url": self._url})

    async def async_step_device(self, user_input=None):
        choices = {did: f"{d['name']} ({did[-4:]})" for did, d in self._devices.items()}
        if user_input is not None:
            did = user_input["device"]
            if did not in self._devices or self._devices[did]["model"] != MODEL:
                return self.async_abort(reason="no_supported_device")
            await self.async_set_unique_id(f"{self._region}:{did}")
            self._abort_if_unique_id_configured()
            return self.async_create_entry(title=self._devices[did]["name"] or NAME, data={"region": self._region, "uuid": self._uuid, "redirect": self._redirect, "auth": self._auth, "device": self._devices[did]})
        return self.async_show_form(step_id="device", data_schema=vol.Schema({vol.Required("device"): vol.In(choices)}))
