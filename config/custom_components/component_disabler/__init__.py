"""Component to disable specified components after they load."""
from __future__ import annotations

import logging
import voluptuous as vol
from typing import Final

from homeassistant.const import EVENT_HOMEASSISTANT_STARTED
from homeassistant.core import Event, HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN, DEFAULT_COMPONENTS_TO_DISABLE
from .disabler import unload_component

_LOGGER = logging.getLogger(__name__)

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

    async def disable_components_on_startup(event: Event) -> None:
        """Disable components after Home Assistant has started."""
        for component in components_to_disable:
            if component in hass.config.components:
                await unload_component(hass, component)
            else:
                _LOGGER.warning(
                    "Component %s was not loaded, cannot disable", component
                )

    # Register a listener that will disable components after startup
    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STARTED, disable_components_on_startup)

    return True