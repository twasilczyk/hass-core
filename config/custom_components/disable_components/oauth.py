"""OAuth implementation providers for disabled components."""
from __future__ import annotations

import logging
from typing import Callable, Awaitable

from homeassistant.core import HomeAssistant

from .const import CLOUD_DATA_KEY, ACCOUNT_LINK_KEY

_LOGGER = logging.getLogger(__name__)


# TODO: unnecessary at all?
async def provide_empty_oauth_implementation(
    hass: HomeAssistant, domain: str
) -> list:
    """Provide an empty implementation for OAuth2 to prevent errors."""
    _LOGGER.debug("Providing empty OAuth implementation for %s", domain)
    return []


# TODO: unnecessary?
async def setup_cloud_mocks(hass: HomeAssistant) -> None:
    """Set up mocks for cloud component to prevent errors in other components."""
    _LOGGER.info("Setting up cloud component mocks")

    # Create a minimal mock for the cloud data
    if CLOUD_DATA_KEY not in hass.data:
        hass.data[CLOUD_DATA_KEY] = {}

    # Handle account linking functionality
    if ACCOUNT_LINK_KEY not in hass.data:
        hass.data[ACCOUNT_LINK_KEY] = {}

    account_link_funcs = hass.data[ACCOUNT_LINK_KEY]

    # Add empty implementations for OAuth to prevent errors
    async def mock_account_link(hass: HomeAssistant, domain: str) -> list:
        _LOGGER.debug("Providing mock account link for %s", domain)
        return []

    # Register the mock implementation function
    for domain in hass.config.components:
        if domain not in account_link_funcs:
            account_link_funcs[domain] = mock_account_link
