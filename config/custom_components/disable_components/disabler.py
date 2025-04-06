"""Component disabling functionality."""
from __future__ import annotations

import asyncio
import logging

from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)
CLOUD_DATA_KEY = "cloud"


async def wait_for_component(hass: HomeAssistant, component: str, timeout: int = 30) -> None:
    if component in hass.config.components:
        return True

    _LOGGER.debug("Waiting for %s to load", component)
    for i in range(timeout):
        if component in hass.config.components:
            _LOGGER.debug("Component %s is now loaded", component)
            return True
        await asyncio.sleep(1)

    _LOGGER.warning("Component %s did not load after %d seconds", component, timeout)
    return False


async def disable_components(hass: HomeAssistant, components_to_disable: list[str]) -> None:
    _LOGGER.debug("Home Assistant started, disabling selected integrations...")
    for component in components_to_disable:
        hass.async_create_background_task(
            disable_component(hass, component), name="Disabling " + component
        )


async def disable_component(hass: HomeAssistant, component_domain: str) -> None:
    try:
        if not await wait_for_component(hass, component_domain, timeout=30):
            return
        _LOGGER.info("Disabling %s", component_domain)

        # Disable frontend panels
        hass.data["frontend_panels"].pop(component_domain, None)

        # Clean up component data, except for cloud (necessary for OAuth)
        if component_domain != CLOUD_DATA_KEY:
            hass.data.pop(component_domain, None)

        # Remove component from loaded components list
        hass.config.components.remove(component_domain)
    except asyncio.exceptions.CancelledError:
        pass
    except:
        _LOGGER.error("Failed to disable %s", component_domain, exc_info=True)
