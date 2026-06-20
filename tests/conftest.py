"""Fixtures for Nest Legacy tests."""

from __future__ import annotations

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant import config_entries as _config_entries

if not hasattr(_config_entries, "OptionsFlowWithReload"):
    # Local sandbox pins an older homeassistant release that predates
    # OptionsFlowWithReload. This shim only exists so the test suite can be
    # exercised locally; CI installs a current homeassistant where the real
    # class (which also reloads the entry after save) is used.
    _config_entries.OptionsFlowWithReload = _config_entries.OptionsFlow

import custom_components.nest_legacy.config_flow  # noqa: F401
import custom_components.nest_legacy.coordinator  # noqa: F401
from custom_components.nest_legacy.const import DOMAIN
from custom_components.nest_legacy.pynest.models import NestLimits, NestSession, NestUrls

pytest_plugins = "pytest_homeassistant_custom_component"


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations: None) -> None:
    """Enable custom integrations for every test."""


@pytest.fixture(autouse=True)
def mock_http_setup() -> Generator[None]:
    """Avoid starting a real HTTP server for the http dependency in tests."""
    with patch("homeassistant.components.http.async_setup", return_value=True):
        yield


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Stub out the integration's real setup/unload so flow tests stay isolated."""
    with (
        patch(
            "custom_components.nest_legacy.async_setup_entry", return_value=True
        ) as mock_setup,
        patch("custom_components.nest_legacy.async_unload_entry", return_value=True),
    ):
        yield mock_setup


@pytest.fixture
def mock_nest_session() -> NestSession:
    """Return a fake successful authentication session."""
    return NestSession(
        access_token="fake-access-token",
        email="user@example.com",
        expires_in="3600",
        userid="user-123",
        user="user-123",
        urls=NestUrls(
            rubyapi_url="https://example.com/ruby",
            czfe_url="https://example.com/czfe",
            log_upload_url="https://example.com/log",
            transport_url="https://example.com/transport",
            weather_url="https://example.com/weather",
            support_url="https://example.com/support",
            direct_transport_url="https://example.com/direct",
        ),
        limits=NestLimits(
            thermostats_per_structure=1,
            structures=1,
            smoke_detectors_per_structure=1,
            smoke_detectors=1,
            thermostats=1,
        ),
    )


@pytest.fixture
def mock_nest_client(mock_nest_session: NestSession) -> Generator[AsyncMock]:
    """Mock the NestClient used by the config flow and coordinator."""
    with (
        patch(
            "custom_components.nest_legacy.config_flow.NestClient", autospec=True
        ) as mock_client_cls,
        patch(
            "custom_components.nest_legacy.coordinator.NestClient", autospec=True
        ) as mock_coordinator_client_cls,
    ):
        for client_cls in (mock_client_cls, mock_coordinator_client_cls):
            client = client_cls.return_value
            client.async_authenticate_with_google_credentials = AsyncMock(
                return_value=mock_nest_session
            )
            client.async_authenticate_with_nest_token = AsyncMock(
                return_value=mock_nest_session
            )
            client.async_get_first_data = AsyncMock(return_value={})
            client.is_expired = lambda: False
        yield mock_client_cls.return_value
