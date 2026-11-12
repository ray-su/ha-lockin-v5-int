"""Smoke-test a fresh, isolated HA setup endpoint without the pytest HA harness.

Requires an explicitly supplied local scratch parent. Never point this at a live
HA configuration. The tool creates and removes its own temporary config there,
blocks non-loopback socket connections, and never contacts Xiaomi or authorizes
a real account. Optional failure probes use synthetic callbacks and mocked cloud
methods, not live authorization or device discovery.
"""
from __future__ import annotations

import argparse
import asyncio
from importlib.metadata import version
from importlib import import_module
import json
from pathlib import Path
import shutil
import tempfile
from unittest.mock import AsyncMock, patch

# Initialize compatibility aliases before importing any HTTP test clients.
from homeassistant import bootstrap, loader
from homeassistant.auth.const import GROUP_ID_ADMIN
from homeassistant.core import HomeAssistant
from aiohttp.test_utils import TestClient, TestServer
from pytest_socket import socket_allow_hosts

ROOT = Path(__file__).resolve().parents[1]


async def probe_failure(hass, client, token, config_dir, stage):
    """Exercise a browser-facing abort with explicitly synthetic cloud results."""
    headers = {"Authorization": f"Bearer {token}"}
    response = await client.post("/api/config/config_entries/flow", headers=headers,
                                 json={"handler": "lockin_v5"})
    assert response.status == 200
    flow_id = (await response.json())["flow_id"]
    path = f"/api/config/config_entries/flow/{flow_id}"
    response = await client.post(path, headers=headers, json={"region": "sg"})
    assert response.status == 200 and (await response.json())["step_id"] == "login"
    flow = hass.config_entries.flow._progress[flow_id]
    callback = await client.get(f"/api/webhook/{flow._webhook_id}",
                                params={"state": flow._state, "code": "SYNTHETIC-CODE"})
    assert callback.status == 200, f"Synthetic callback HTTP status: {callback.status}"
    assert "Authorization received" in await callback.text(), "Synthetic callback handler was not reached"
    errors = import_module("custom_components.lockin_v5.miot.miot_error")
    oauth = AsyncMock(return_value={"access_token": "SYNTHETIC-TOKEN", "refresh_token": "SYNTHETIC-REFRESH"})
    devices = AsyncMock()
    if stage == "token exchange":
        oauth.side_effect = errors.MIoTOauthError("SYNTHETIC-PRIVATE-PAYLOAD", http_status=200, cloud_code=-12345)
        expected = "OAuth response error; HTTP 200; API code -12345"
    else:
        devices.side_effect = errors.MIoTHttpError("SYNTHETIC-PRIVATE-PAYLOAD", http_status=503)
        expected = "Cloud API error; HTTP 503"
    with patch("custom_components.lockin_v5.miot.miot_cloud.MIoTOauthClient.get_access_token_async", oauth), patch(
        "custom_components.lockin_v5.api.ReadOnlyClient.get_devices_async", devices
    ):
        response = await client.post(path, headers=headers, json={})
    assert response.status == 200
    payload = await response.json()
    assert payload["type"] == "abort" and payload["reason"] == "login_failed"
    assert payload["description_placeholders"] == {"stage": stage, "detail": expected}
    assert "SYNTHETIC" not in json.dumps(payload)
    assert not flow._auth and flow._code is None
    assert flow_id not in hass.config_entries.flow._progress
    oauth.assert_awaited_once()
    if stage == "token exchange":
        devices.assert_not_awaited()
    else:
        devices.assert_awaited_once()
    translation_path = config_dir / "custom_components/lockin_v5/translations/en.json"
    translation = json.loads(await hass.async_add_executor_job(translation_path.read_text))
    message = translation["config"]["abort"]["login_failed"].format(**payload["description_placeholders"])
    assert stage in message and expected in message and "SYNTHETIC" not in message
    return {"synthetic_failure": True, "flow_http_status": response.status,
            "result": "abort", "stage": stage, "diagnostic": expected,
            "english_message_format_verified": True, "private_payload_absent": True}


async def probe(config_dir: Path, exercise_failures: bool):
    socket_allow_hosts(["127.0.0.1", "::1"], allow_unix_socket=True)
    hass = HomeAssistant(str(config_dir))
    loader.async_setup(hass)
    client = None
    try:
        result = await bootstrap.async_from_config_dict({
            "homeassistant": {"latitude": 0, "longitude": 0, "elevation": 0,
                              "unit_system": "metric", "time_zone": "UTC", "country": "CA"},
            "http": {"server_host": "127.0.0.1", "server_port": 18123},
            "config": {},
            # default_config normally supplies this HTTP callback route.
            "webhook": {},
        }, hass)
        assert result is hass, "Isolated HA bootstrap failed"
        user = await hass.auth.async_create_user("Local test", group_ids=[GROUP_ID_ADMIN], local_only=True)
        refresh = await hass.auth.async_create_refresh_token(user, client_id="http://localhost/")
        token = hass.auth.async_create_access_token(refresh)
        # TestServer binds an ephemeral loopback port, not the configured HA port.
        client = TestClient(TestServer(hass.http.app, host="127.0.0.1"))
        await client.start_server()
        response = await client.post("/api/config/config_entries/flow",
                                     headers={"Authorization": f"Bearer {token}"},
                                     json={"handler": "lockin_v5"})
        assert response.status == 200, f"Setup status: {response.status}"
        payload = await response.json()
        assert payload["type"] == "form" and payload["step_id"] == "user"
        assert payload["data_schema"][0]["name"] == "region"
        hass.config_entries.flow.async_abort(payload["flow_id"])
        failures = []
        if exercise_failures:
            for stage in ("token exchange", "device discovery"):
                failures.append(await probe_failure(hass, client, token, config_dir, stage))
        assert not hass.config_entries.async_entries("lockin_v5")
        return {"home_assistant": version("homeassistant"), "python_slugify": version("python-slugify"),
                "http_status": response.status, "form": payload["step_id"], "field": "region",
                "pytest_ha_harness_used": False, "non_loopback_connections": "blocked",
                "live_ha_or_cloud_access": False, "config_entries_created": 0,
                "synthetic_failure_probes": failures}
    finally:
        if client is not None:
            await client.close()
        await hass.async_stop(force=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scratch", type=Path, required=True)
    parser.add_argument("--exercise-failures", action="store_true")
    args = parser.parse_args()
    args.scratch.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="lockin-smoke-", dir=args.scratch) as folder:
        config_dir = Path(folder)
        shutil.copytree(ROOT / "custom_components/lockin_v5", config_dir / "custom_components/lockin_v5",
                        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        # Run bootstrap in its own fresh interpreter/process, never an existing HA.
        report = asyncio.run(probe(config_dir, args.exercise_failures))
        report["integration_version"] = json.loads((config_dir / "custom_components/lockin_v5/manifest.json").read_text())["version"]
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
