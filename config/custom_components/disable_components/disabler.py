"""Component disabling functionality."""
from __future__ import annotations

import logging
from typing import Any, List

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import CLOUD_DATA_KEY
from .oauth import setup_cloud_mocks

_LOGGER = logging.getLogger(__name__)


async def ensure_dependencies(hass: HomeAssistant, components_to_disable: list[str]) -> None:
    """Ensure all components to disable are loaded first."""
    for component in components_to_disable:
        if component not in hass.config.components:
            _LOGGER.debug("Waiting for %s to be loaded before disabling it", component)
            # This will ensure the component gets loaded
            try:
                await hass.config.async_domain_component_dependencies(component)
            except Exception as ex:
                _LOGGER.warning(
                    "Error loading dependencies for %s, may fail to disable: %s",
                    component, str(ex)
                )


async def disable_components(hass: HomeAssistant, components_to_disable: list[str]) -> None:
    """Disable specified components."""
    for component in components_to_disable:
        if component in hass.config.components:
            await unload_component(hass, component)
        else:
            _LOGGER.warning(
                "Component %s was not loaded, cannot disable", component
            )


async def unload_component(hass: HomeAssistant, component_domain: str) -> None:
    """Unload a specific component."""
    _LOGGER.info("Disabling %s integration", component_domain)

    # Special case handling for specific components
    if component_domain == CLOUD_DATA_KEY:
        await setup_cloud_mocks(hass)

    # Special handling for components that register in the frontend
    try:
        # For components that register UI panels
        if hasattr(hass.data, "get") and "frontend_panels" in hass.data:
            panels = hass.data["frontend_panels"]
            if component_domain in panels:
                _LOGGER.debug("Removing %s from frontend panels", component_domain)
                if hasattr(panels, "pop"):
                    panels.pop(component_domain, None)
    except Exception as ex:
        _LOGGER.warning("Error removing frontend panel for %s: %s", component_domain, ex)

    # Check if component data exists
    if component_domain not in hass.data:
        _LOGGER.warning(
            "%s component not found in hass.data, might not be loaded",
            component_domain
        )
        # Continue anyway to try other methods

    # Try to stop component services if possible
    if component_domain in hass.data:
        component_data = hass.data[component_domain]
        if hasattr(component_data, "async_stop") and callable(component_data.async_stop):
            _LOGGER.debug("Stopping %s services", component_domain)
            await component_data.async_stop()

        # If it's not cloud, remove component data
        # We keep a mock cloud data to prevent errors
        if component_domain != CLOUD_DATA_KEY:
            try:
                hass.data.pop(component_domain, None)
                _LOGGER.debug("Removed %s data from hass.data", component_domain)
            except Exception as ex:
                _LOGGER.debug("Could not remove %s data: %s", component_domain, ex)

    # Unload any component config entries
    config_entries = [
        entry
        for entry in hass.config_entries.async_entries(component_domain)
        if entry.state == ConfigEntry.STATE_LOADED
    ]

    if config_entries:
        _LOGGER.debug("Unloading %d %s config entries",
                     len(config_entries), component_domain)
        for entry in config_entries:
            await hass.config_entries.async_unload(entry.entry_id)

    # Remove component from loaded components list
    if component_domain in hass.config.components:
        hass.config.components.remove(component_domain)
        _LOGGER.info("%s component successfully disabled", component_domain)
    else:
        _LOGGER.debug("%s component not found in loaded components", component_domain)
