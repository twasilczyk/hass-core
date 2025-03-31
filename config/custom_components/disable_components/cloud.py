"""Cloud component handling functionality."""
from __future__ import annotations

import asyncio
import logging
from typing import Any

from homeassistant.core import HomeAssistant

from .const import CLOUD_DATA_KEY
from .oauth import patch_cloud_oauth_implementation

_LOGGER = logging.getLogger(__name__)

def disable_cloud_component(hass: HomeAssistant) -> None:
    """Disable cloud component functionality while preserving shutdown handlers.
    
    This is a special case handler that keeps the cloud component's shutdown handlers
    intact while disabling its actual functionality.
    """
    _LOGGER.debug("Special handling for cloud component to preserve shutdown handlers")
    
    if CLOUD_DATA_KEY not in hass.data:
        _LOGGER.debug("Cloud component data not found in hass.data")
        return
    
    cloud_data = hass.data[CLOUD_DATA_KEY]
    
    # Patch the CloudOAuth2Implementation to properly handle task cancellation
    patch_cloud_oauth_implementation(hass)
    
    # Disconnect from the cloud but keep the component in place
    # so its shutdown handlers can still run
    try:
        # Check if remote is connected before attempting to disconnect
        if (hasattr(cloud_data, "remote") and 
            hasattr(cloud_data.remote, "disconnect") and
            hasattr(cloud_data.remote, "is_connected") and
            cloud_data.remote.is_connected):
            _LOGGER.debug("Disconnecting cloud remote connection")
            try:
                # Run this in a separate try block to catch specific remote errors
                hass.async_create_task(cloud_data.remote.disconnect())
            except Exception as remote_ex:
                _LOGGER.debug("Error disconnecting remote: %s", remote_ex)
        else:
            _LOGGER.debug("Cloud remote not connected, skipping disconnect")
        
        # Check if IoT is connected before attempting to disconnect
        if (hasattr(cloud_data, "iot") and 
            hasattr(cloud_data.iot, "disconnect") and
            hasattr(cloud_data.iot, "connected") and
            cloud_data.iot.connected):
            _LOGGER.debug("Disconnecting cloud IoT connection")
            try:
                # Run this in a separate try block to catch specific IoT errors
                hass.async_create_task(cloud_data.iot.disconnect())
            except Exception as iot_ex:
                _LOGGER.debug("Error disconnecting IoT: %s", iot_ex)
        else:
            _LOGGER.debug("Cloud IoT not connected, skipping disconnect")
        
        # If there are client preferences, disable remote access
        if hasattr(cloud_data, "client") and hasattr(cloud_data.client, "prefs"):
            _LOGGER.debug("Disabling remote access in cloud preferences")
            try:
                hass.async_create_task(
                    cloud_data.client.prefs.async_update(remote_enabled=False)
                )
            except Exception as prefs_ex:
                _LOGGER.debug("Error updating cloud preferences: %s", prefs_ex)
            
        # Disable any listeners or recurring tasks
        # but DON'T remove the component data or shutdown handlers
        _LOGGER.debug("Cloud component disabled but shutdown handlers preserved")
    except Exception as ex:
        _LOGGER.warning("Error while disabling cloud component: %s", ex)