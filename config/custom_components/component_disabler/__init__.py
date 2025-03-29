"""Component to disable specified components after they load."""
from __future__ import annotations

import logging
import voluptuous as vol
from typing import Any, Awaitable, Callable, Final, List, Set

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EVENT_HOMEASSISTANT_STARTED
from homeassistant.core import Event, HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType

_LOGGER = logging.getLogger(__name__)

DOMAIN: Final = "component_disabler"
DEFAULT_COMPONENTS_TO_DISABLE = ["cloud"]

# Mock implementations for components with special requirements
CLOUD_DATA_KEY = "cloud"
OAUTH_IMPL_KEY = "oauth2_implementations"
ACCOUNT_LINK_KEY = "account_link_impl_funcs"

# Configuration schema
CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Optional("components", default=DEFAULT_COMPONENTS_TO_DISABLE): 
                    vol.All(cv.ensure_list, [cv.string])
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the component disabler."""
    conf = config.get(DOMAIN, {})
    components_to_disable = conf.get("components", DEFAULT_COMPONENTS_TO_DISABLE)
    
    if not components_to_disable:
        _LOGGER.warning("No components specified to disable, component will do nothing")
        return True
    
    _LOGGER.info("Component Disabler will disable: %s", ", ".join(components_to_disable))

    # Ensure all components to disable are loaded first
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

    async def _disable_components_on_startup(event: Event) -> None:
        """Disable components after Home Assistant has started."""
        for component in components_to_disable:
            if component in hass.config.components:
                await _unload_component(hass, component)
            else:
                _LOGGER.warning(
                    "Component %s was not loaded, cannot disable", component
                )

    # Register a listener that will disable components after startup
    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STARTED, _disable_components_on_startup)

    return True


async def _provide_empty_oauth_implementation(
    hass: HomeAssistant, domain: str
) -> list:
    """Provide an empty implementation for OAuth2 to prevent errors."""
    _LOGGER.debug("Providing empty OAuth implementation for %s", domain)
    return []


async def _handle_cloud_component(hass: HomeAssistant) -> None:
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
    async def _mock_account_link(hass: HomeAssistant, domain: str) -> list:
        _LOGGER.debug("Providing mock account link for %s", domain)
        return []
    
    # Register the mock implementation function
    for domain in hass.config.components:
        if domain not in account_link_funcs:
            account_link_funcs[domain] = _mock_account_link


async def _unload_component(hass: HomeAssistant, component_domain: str) -> None:
    """Unload a specific component."""
    _LOGGER.info("Disabling %s integration", component_domain)

    # Special case handling for specific components
    if component_domain == CLOUD_DATA_KEY:
        await _handle_cloud_component(hass)
    
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