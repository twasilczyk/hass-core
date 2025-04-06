"""Monkey patch for SmartThings to allow it to work without cloud component."""
from __future__ import annotations

import logging
import traceback
from typing import Any, Final

from homeassistant.config_entries import ConfigFlowResult
from homeassistant.core import Event, HomeAssistant
from homeassistant.const import EVENT_COMPONENT_LOADED
from homeassistant.helpers import importlib as hass_importlib
from homeassistant.helpers.config_entry_oauth2_flow import async_get_implementations

_LOGGER = logging.getLogger(__name__)
DOMAIN: Final = "smartthings"
original_async_step_user = None


async def setup_smartthings_hook(hass: HomeAssistant) -> None:
    hass.async_create_background_task(
        setup_task(hass), name="SmartThings hook setup"
    )


async def setup_task(hass: HomeAssistant) -> None:
    """Patch SmartThings config flow to bypass cloud check.

    This allows SmartThings integration to work without requiring the cloud component.
    Instead of checking if 'cloud' is in components, it temporarily adds cloud to the
    components list just for this check.
    """

    try:
        smartthings_module = await hass_importlib.async_import_module(
            hass, "homeassistant.components.smartthings.config_flow"
        )

        global original_async_step_user
        original_async_step_user = smartthings_module.SmartThingsConfigFlow.async_step_user
        smartthings_module.SmartThingsConfigFlow.async_step_user = patched_async_step_user
    except:
        _LOGGER.error("Failed to setup SmartThings hook", exc_info=True)


# Create a patched method that tricks the cloud check
async def patched_async_step_user(
    self, user_input: dict[str, Any] | None = None
) -> ConfigFlowResult:
    if not "cloud" in self.hass.config.components:
        _LOGGER.info("Adding cloud to components list to bypass SmartThings check")
        self.hass.config.components.add("cloud")

    try:
        return await original_async_step_user(self, user_input)
    finally:
        self.hass.config.components.remove("cloud")
        _LOGGER.info("Removed cloud from components list")
