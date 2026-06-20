"""Tests for the Nest Legacy integration setup/unload."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, patch

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed

from custom_components.nest_legacy.const import CONF_ACCESS_TOKEN, CONF_ACCOUNT_TYPE, DOMAIN

from pytest_homeassistant_custom_component.common import MockConfigEntry


def _make_entry() -> MockConfigEntry:
    return MockConfigEntry(
        domain=DOMAIN,
        unique_id="user-123",
        data={CONF_ACCOUNT_TYPE: "nest", CONF_ACCESS_TOKEN: "token"},
    )


def _mock_coordinator() -> AsyncMock:
    coordinator = AsyncMock()
    coordinator.async_initialize = AsyncMock()
    coordinator.first_protobuf_update_received = asyncio.Event()
    coordinator.first_protobuf_update_received.set()
    return coordinator


async def test_setup_entry_success(hass: HomeAssistant) -> None:
    """A healthy entry loads and forwards to platforms."""
    entry = _make_entry()
    entry.add_to_hass(hass)
    coordinator = _mock_coordinator()

    with (
        patch(
            "custom_components.nest_legacy.NestCoordinator", return_value=coordinator
        ),
        patch.object(
            hass.config_entries, "async_forward_entry_setups", return_value=True
        ),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    coordinator.async_initialize.assert_awaited_once()
    coordinator.async_start_subscriber.assert_called_once()


async def test_setup_entry_auth_failed(hass: HomeAssistant) -> None:
    """Auth failures during init trigger the reauth flow instead of a retry."""
    entry = _make_entry()
    entry.add_to_hass(hass)
    coordinator = _mock_coordinator()
    coordinator.async_initialize.side_effect = ConfigEntryAuthFailed("bad creds")

    with patch(
        "custom_components.nest_legacy.NestCoordinator", return_value=coordinator
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_ERROR


async def test_setup_entry_timeout_not_ready(hass: HomeAssistant) -> None:
    """A timeout waiting for the first update marks the entry as not-ready."""
    entry = _make_entry()
    entry.add_to_hass(hass)
    coordinator = _mock_coordinator()
    coordinator.first_protobuf_update_received = asyncio.Event()  # never set

    with (
        patch(
            "custom_components.nest_legacy.NestCoordinator", return_value=coordinator
        ),
        patch("custom_components.nest_legacy.asyncio.wait_for", side_effect=TimeoutError),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_RETRY


async def test_unload_entry(hass: HomeAssistant) -> None:
    """Unloading an entry stops the subscriber and unloads platforms."""
    entry = _make_entry()
    entry.add_to_hass(hass)
    coordinator = _mock_coordinator()

    with (
        patch(
            "custom_components.nest_legacy.NestCoordinator", return_value=coordinator
        ),
        patch.object(
            hass.config_entries, "async_forward_entry_setups", return_value=True
        ),
        patch.object(
            hass.config_entries, "async_unload_platforms", return_value=True
        ),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        assert entry.state is ConfigEntryState.LOADED

        await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.NOT_LOADED
    coordinator.async_stop_subscriber.assert_called_once()
