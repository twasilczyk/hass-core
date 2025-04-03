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


async def patch_smartthings_config_flow(hass: HomeAssistant) -> bool:
    """Patch SmartThings config flow to bypass cloud check.
    
    This allows SmartThings integration to work without requiring the cloud component.
    Instead of checking if 'cloud' is in components, it temporarily adds cloud to the
    components list just for this check.
    """
    try:
        # Import SmartThings config flow
        _LOGGER.debug("Attempting to import SmartThings config flow module")
        # Use async helper to avoid blocking the event loop
        smartthings_module = await hass_importlib.async_import_module(
            hass, "homeassistant.components.smartthings.config_flow"
        )
        _LOGGER.debug("Successfully imported SmartThings config flow module")

        # Store original method for reference
        original_async_step_user = smartthings_module.SmartThingsConfigFlow.async_step_user
        _LOGGER.debug("Stored reference to original async_step_user method")

        # Create a patched method that tricks the cloud check
        async def patched_async_step_user(
            self, user_input: dict[str, Any] | None = None
        ) -> ConfigFlowResult:
            """Bypass cloud check to allow SmartThings without cloud component."""
            _LOGGER.debug("Patched async_step_user called with user_input: %s", user_input)
            
            # Check if cloud is already in components
            cloud_already_present = "cloud" in self.hass.config.components
            _LOGGER.debug("Cloud component already present: %s", cloud_already_present)
            
            # Temporarily add cloud to the components list for this check
            original_components = set(self.hass.config.components)
            _LOGGER.debug("Original components count: %s", len(original_components))
            
            if not cloud_already_present:
                self.hass.config.components.add("cloud")
                _LOGGER.debug("Added cloud to components list")
            
            try:
                # Call the original method with cloud "enabled"
                _LOGGER.debug("Calling original async_step_user method")
                result = await original_async_step_user(self, user_input)
                _LOGGER.debug("Original method returned result: %s", result)
                return result
            except Exception as e:
                _LOGGER.error("Error in original method: %s", e)
                _LOGGER.error("Traceback: %s", traceback.format_exc())
                raise
            finally:
                # Restore original components list
                if not cloud_already_present:
                    self.hass.config.components.clear()
                    self.hass.config.components.update(original_components)
                    _LOGGER.debug("Restored original components list")

        # Apply the patch
        _LOGGER.debug("Applying patch to SmartThingsConfigFlow.async_step_user")
        smartthings_module.SmartThingsConfigFlow.async_step_user = patched_async_step_user
        _LOGGER.info("Successfully patched SmartThings config flow")
        return True
    except (ImportError, AttributeError) as err:
        _LOGGER.error("Failed to patch SmartThings config flow: %s", err)
        _LOGGER.error("Traceback: %s", traceback.format_exc())
        return False


async def handle_smartthings_for_cloud_disabled(hass: HomeAssistant) -> None:
    """Handle setup for SmartThings when cloud is disabled."""
    _LOGGER.warning("Cloud component will be disabled - applying SmartThings patch immediately")
    await async_setup(hass)
    
    # Also listen for when SmartThings is loaded in case immediate patching wasn't enough
    async def handle_component_loaded(event: Event) -> None:
        """Handle component loaded events to apply SmartThings patch at the right time."""
        component = event.data.get("component")
        
        # Apply patch again when SmartThings is loaded if needed
        if component == "smartthings":
            _LOGGER.warning("SmartThings loaded with cloud disabled, applying patch again")
            await async_setup(hass)
    
    # Listen for component loaded events
    hass.bus.async_listen(EVENT_COMPONENT_LOADED, handle_component_loaded)


async def async_setup(hass: HomeAssistant) -> bool:
    """Set up SmartThings patch component."""
    _LOGGER.info("Setting up SmartThings patch component")
    success = await patch_smartthings_config_flow(hass)
    _LOGGER.info("SmartThings patch setup result: %s", success)
    return success