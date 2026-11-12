"""Smoke-test a fresh, isolated HA setup endpoint without the pytest HA harness.

Requires an explicitly supplied local scratch parent. Never point this at a live
HA configuration. The tool creates and removes its own temporary config there,
blocks non-loopback socket connections, and never begins OAuth or device setup.
"""
from __future__ import annotations

import argparse
import asyncio
from importlib.metadata import version
import json
from pathlib import Path
import shutil
import tempfile

# Initialize compatibility aliases before importing any HTTP test clients.
from homeassistant import bootstrap, loader
from homeassistant.auth.const import GROUP_ID_ADMIN
from homeassistant.core import HomeAssistant
from aiohttp.test_utils import TestClient, TestServer
from pytest_socket import socket_allow_hosts

ROOT = Path(__file__).resolve().parents[1]


async def probe(config_dir: Path):
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
        assert not hass.config_entries.async_entries("lockin_v5")
        return {"home_assistant": version("homeassistant"), "python_slugify": version("python-slugify"),
                "http_status": response.status, "form": payload["step_id"], "field": "region",
                "pytest_ha_harness_used": False, "non_loopback_connections": "blocked",
                "live_ha_or_cloud_access": False, "config_entries_created": 0}
    finally:
        if client is not None:
            await client.close()
        await hass.async_stop(force=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scratch", type=Path, required=True)
    args = parser.parse_args()
    args.scratch.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="lockin-smoke-", dir=args.scratch) as folder:
        config_dir = Path(folder)
        shutil.copytree(ROOT / "custom_components/lockin_v5", config_dir / "custom_components/lockin_v5",
                        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        # Run bootstrap in its own fresh interpreter/process, never an existing HA.
        report = asyncio.run(probe(config_dir))
        report["integration_version"] = json.loads((config_dir / "custom_components/lockin_v5/manifest.json").read_text())["version"]
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
