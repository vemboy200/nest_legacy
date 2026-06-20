"""Tests for the Nest Legacy config flow."""

from __future__ import annotations

from unittest.mock import AsyncMock

from aiohttp import ClientError
import pytest

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.service_info.dhcp import DhcpServiceInfo

from custom_components.nest_legacy.const import (
    CONF_ACCESS_TOKEN,
    CONF_ACCOUNT_TYPE,
    CONF_COOKIES,
    CONF_ENABLE_PROTOBUF_LOCK,
    CONF_EVENT_POLL_INTERVAL,
    CONF_ISSUE_TOKEN,
    DOMAIN,
)
from custom_components.nest_legacy.pynest.exceptions import BadCredentialsException

from pytest_homeassistant_custom_component.common import MockConfigEntry


async def test_google_account_flow_success(
    hass: HomeAssistant, mock_nest_client: AsyncMock, mock_setup_entry: AsyncMock
) -> None:
    """A full Google account flow creates a config entry."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_ACCOUNT_TYPE: "google"},
    )
    assert result["step_id"] == "google_account"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_ISSUE_TOKEN: "issue-token", CONF_COOKIES: "cookies"},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_ISSUE_TOKEN] == "issue-token"
    await hass.config_entries.async_unload(result["result"].entry_id)


async def test_nest_account_flow_success(
    hass: HomeAssistant, mock_nest_client: AsyncMock, mock_setup_entry: AsyncMock
) -> None:
    """A full legacy Nest account flow creates a config entry."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_ACCOUNT_TYPE: "nest"},
    )
    assert result["step_id"] == "nest_account"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_ACCESS_TOKEN: "access-token"},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_ACCESS_TOKEN] == "access-token"
    await hass.config_entries.async_unload(result["result"].entry_id)


async def test_invalid_auth(hass: HomeAssistant, mock_nest_client: AsyncMock, mock_setup_entry: AsyncMock) -> None:
    """Invalid credentials surface as a form error."""
    mock_nest_client.async_authenticate_with_nest_token.side_effect = (
        BadCredentialsException("bad creds")
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_ACCOUNT_TYPE: "nest"}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_ACCESS_TOKEN: "bad-token"}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}


async def test_cannot_connect(
    hass: HomeAssistant, mock_nest_client: AsyncMock, mock_setup_entry: AsyncMock
) -> None:
    """Connection errors surface as a form error."""
    mock_nest_client.async_authenticate_with_nest_token.side_effect = ClientError(
        "boom"
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_ACCOUNT_TYPE: "nest"}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_ACCESS_TOKEN: "token"}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}


async def test_duplicate_entry_aborts(
    hass: HomeAssistant, mock_nest_client: AsyncMock, mock_setup_entry: AsyncMock
) -> None:
    """A second config entry for the same account aborts."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="user-123",
        data={CONF_ACCOUNT_TYPE: "nest", CONF_ACCESS_TOKEN: "access-token"},
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_ACCOUNT_TYPE: "nest"}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_ACCESS_TOKEN: "access-token"}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_dhcp_discovery_shows_user_form(
    hass: HomeAssistant, mock_nest_client: AsyncMock
) -> None:
    """DHCP discovery with no existing entry starts the normal user flow."""
    discovery_info = DhcpServiceInfo(
        ip="192.168.1.5", hostname="nest-thermostat", macaddress="18b430aabbcc"
    )
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_DHCP},
        data=discovery_info,
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"


async def test_dhcp_discovery_aborts_if_already_configured(
    hass: HomeAssistant, mock_nest_client: AsyncMock
) -> None:
    """DHCP discovery aborts when a Nest Legacy entry already exists."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="user-123",
        data={CONF_ACCOUNT_TYPE: "nest", CONF_ACCESS_TOKEN: "access-token"},
    )
    entry.add_to_hass(hass)

    discovery_info = DhcpServiceInfo(
        ip="192.168.1.5", hostname="nest-thermostat", macaddress="18b430aabbcc"
    )
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_DHCP},
        data=discovery_info,
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_reauth_flow_success(
    hass: HomeAssistant, mock_nest_client: AsyncMock, mock_setup_entry: AsyncMock
) -> None:
    """Reauth re-validates and updates an existing entry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="user-123",
        data={CONF_ACCOUNT_TYPE: "nest", CONF_ACCESS_TOKEN: "old-token"},
    )
    entry.add_to_hass(hass)

    result = await entry.start_reauth_flow(hass)
    assert result["step_id"] == "nest_account"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_ACCESS_TOKEN: "new-token"}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert entry.data[CONF_ACCESS_TOKEN] == "new-token"


async def test_reauth_wrong_account_aborts(
    hass: HomeAssistant, mock_nest_client: AsyncMock, mock_setup_entry: AsyncMock
) -> None:
    """Reauthenticating with a different account aborts."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="a-different-user",
        data={CONF_ACCOUNT_TYPE: "nest", CONF_ACCESS_TOKEN: "old-token"},
    )
    entry.add_to_hass(hass)

    result = await entry.start_reauth_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_ACCESS_TOKEN: "new-token"}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "wrong_account"


async def test_reconfigure_flow_success(
    hass: HomeAssistant, mock_nest_client: AsyncMock, mock_setup_entry: AsyncMock
) -> None:
    """Reconfigure re-validates and updates an existing entry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="user-123",
        data={CONF_ACCOUNT_TYPE: "nest", CONF_ACCESS_TOKEN: "old-token"},
    )
    entry.add_to_hass(hass)

    result = await entry.start_reconfigure_flow(hass)
    assert result["step_id"] == "nest_account"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_ACCESS_TOKEN: "new-token"}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert entry.data[CONF_ACCESS_TOKEN] == "new-token"


async def test_options_flow(hass: HomeAssistant, mock_nest_client: AsyncMock, mock_setup_entry: AsyncMock) -> None:
    """The options flow updates the config entry options."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="user-123",
        data={CONF_ACCOUNT_TYPE: "nest", CONF_ACCESS_TOKEN: "token"},
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {CONF_EVENT_POLL_INTERVAL: 10, CONF_ENABLE_PROTOBUF_LOCK: False},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options[CONF_EVENT_POLL_INTERVAL] == 10
    assert entry.options[CONF_ENABLE_PROTOBUF_LOCK] is False
