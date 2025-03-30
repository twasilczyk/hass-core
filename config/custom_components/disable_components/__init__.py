"""Component to disable/exclude specified components after they load."""
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

# Example configuration:
# ```
# default_config:
#
# disable_components:
#   - cloud
#   - energy
# ```
CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.All(cv.ensure_list, [cv.string])
    },
    extra=vol.ALLOW_EXTRA,
)

async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    components_to_disable = config.get(DOMAIN, [])
    if not components_to_disable:
        _LOGGER.warning("No components specified to disable, %s will do nothing", DOMAIN)
        return True
    _LOGGER.info("Components to disable: %s", ", ".join(components_to_disable))

    await ensure_dependencies(hass, components_to_disable)

    async def on_startup(event: Event) -> None:
        await disable_components(hass, components_to_disable)
    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STARTED, on_startup)

    return True
