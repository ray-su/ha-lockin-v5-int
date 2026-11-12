"""HA fixtures use the real HA runtime with all cloud/device networking mocked."""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.lockin_v5.const import DOMAIN, MODEL


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    yield


@pytest.fixture
def entry():
    return MockConfigEntry(domain=DOMAIN, title="Test Lockin", unique_id="sg:test-device", data={"region": "sg", "uuid": "test-uuid", "redirect": "http://homeassistant.local:8123/api/webhook/test", "auth": {"access_token": "TEST-ONLY", "refresh_token": "TEST-ONLY", "expires_ts": 4102444800}, "device": {"did": "test-device", "model": MODEL, "name": "Test Lockin", "fw_version": "test"}})


@pytest.fixture
def cloud():
    http = MagicMock()
    http.get_devices_with_dids_async = AsyncMock(return_value={"test-device": {"did": "test-device", "model": MODEL, "online": False}})
    http.get_props_async = AsyncMock(return_value=[])
    http.deinit_async = AsyncMock()
    mqtt = MagicMock()
    with patch("custom_components.lockin_v5.runtime.http_client", return_value=http), patch("custom_components.lockin_v5.runtime.MipsCloudClient", return_value=mqtt):
        yield http, mqtt
