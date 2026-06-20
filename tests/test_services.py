"""Tests for the Nest Legacy services."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import device_registry as dr

from custom_components.nest_legacy.const import DOMAIN
from custom_components.nest_legacy.services import async_setup_services

from pytest_homeassistant_custom_component.common import MockConfigEntry


@pytest.fixture(autouse=True)
async def setup_services(hass: HomeAssistant) -> None:
    """Register the Nest Legacy services for each test."""
    async_setup_services(hass)


@pytest.fixture
def mock_entry_with_coordinator(hass: HomeAssistant) -> MockConfigEntry:
    """A config entry whose runtime_data is a mocked coordinator."""
    entry = MockConfigEntry(domain=DOMAIN, unique_id="user-123")
    entry.add_to_hass(hass)
    coordinator = MagicMock()
    coordinator.get_guests.return_value = {"structure-1": [{"id": "GUEST_1"}]}
    entry.runtime_data = coordinator
    return entry


async def test_list_guests_no_config_entry(hass: HomeAssistant) -> None:
    """Calling a service with no config entries raises a translated error."""
    with pytest.raises(ServiceValidationError) as exc_info:
        await hass.services.async_call(
            DOMAIN, "list_guests", {}, blocking=True, return_response=True
        )
    assert exc_info.value.translation_key == "no_config_entry"


async def test_list_guests_success(
    hass: HomeAssistant, mock_entry_with_coordinator: MockConfigEntry
) -> None:
    """list_guests returns the coordinator's guest data."""
    response = await hass.services.async_call(
        DOMAIN, "list_guests", {}, blocking=True, return_response=True
    )
    assert response == {"guests": {"structure-1": [{"id": "GUEST_1"}]}}


async def test_set_user_schedule_device_not_found(
    hass: HomeAssistant, mock_entry_with_coordinator: MockConfigEntry
) -> None:
    """An unknown device_id raises a translated error."""
    with pytest.raises(ServiceValidationError) as exc_info:
        await hass.services.async_call(
            DOMAIN,
            "delete_user_schedule",
            {"device_id": "missing-device", "user_id": "GUEST_1234"},
            blocking=True,
        )
    assert exc_info.value.translation_key == "device_not_found"


async def test_delete_user_schedule_success(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_entry_with_coordinator: MockConfigEntry,
) -> None:
    """delete_user_schedule resolves the device and calls the coordinator."""
    coordinator = mock_entry_with_coordinator.runtime_data
    coordinator.data = {"serial-123": MagicMock()}
    coordinator.async_send_client_command = AsyncMock()

    device = device_registry.async_get_or_create(
        config_entry_id=mock_entry_with_coordinator.entry_id,
        identifiers={(DOMAIN, "serial-123")},
        name="Front Door Lock",
    )

    await hass.services.async_call(
        DOMAIN,
        "delete_user_schedule",
        {"device_id": device.id, "user_id": "GUEST_1234"},
        blocking=True,
    )

    coordinator.async_send_client_command.assert_awaited_once()
