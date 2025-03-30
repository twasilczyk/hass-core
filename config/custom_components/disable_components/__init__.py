"""Component to disable specified components after they load."""
from __future__ import annotations

import logging
import voluptuous as vol
from typing import Final

from homeassistant.const import EVENT_HOMEASSISTANT_STARTED
from homeassistant.core import Event, HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN
from .disabler import disable_components, ensure_dependencies

_LOGGER = logging.getLogger(__name__)

# Configuration schema - direct list of components to disable
CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.All(cv.ensure_list, [cv.string])
    },
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the disable_components integration."""
    components_to_disable = config.get(DOMAIN, [])

    if not components_to_disable:
        _LOGGER.warning("No components specified to disable, component will do nothing")
        return True

    _LOGGER.info("Disable Components will disable: %s", ", ".join(components_to_disable))
    
    # Ensure all components to disable are loaded first
    await ensure_dependencies(hass, components_to_disable)
    
    # Register a listener that will disable components after startup
    async def disable_components_on_startup(event: Event) -> None:
        """Disable components after Home Assistant has started."""
        await disable_components(hass, components_to_disable)
    
    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STARTED, disable_components_on_startup)

    return True