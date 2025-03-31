"""Component disabling functionality."""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Callable, List

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers import config_entry_oauth2_flow

from .const import ACCOUNT_LINK_KEY, CLOUD_DATA_KEY

_LOGGER = logging.getLogger(__name__)
_ACTIVE_TASKS: List[asyncio.Task] = []


async def wait_for_component(hass: HomeAssistant, component: str, timeout: int = 30) -> None:
    if component in hass.config.components:
        return

    _LOGGER.debug("Waiting for %s to load", component)
    for i in range(timeout):
        if component in hass.config.components:
            _LOGGER.debug("Component %s is now loaded", component)
            return
        await asyncio.sleep(1)

    _LOGGER.warning("Component %s did not load after waiting %d seconds", component, timeout)


async def disable_components(hass: HomeAssistant, components_to_disable: list[str]) -> None:
    """Disable specified components."""
    _LOGGER.debug("Home Assistant started, disabling selected integrations...")
    for component in components_to_disable:
        hass.async_create_task(disable_component(hass, component))
    
    # Register a shutdown handler to cancel any tracked tasks
    @callback
    def cancel_tracked_tasks(event: Event) -> None:
        """Cancel all tracked tasks at shutdown."""
        if not _ACTIVE_TASKS:
            return
        
        _LOGGER.debug("Cancelling %d tracked tasks at shutdown", len(_ACTIVE_TASKS))
        for task in _ACTIVE_TASKS:
            if not task.done():
                task.cancel()
    
    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, cancel_tracked_tasks)


async def disable_component(hass: HomeAssistant, component_domain: str) -> None:
    """Disable a specific component."""
    _LOGGER.info("Disabling %s integration", component_domain)

    await wait_for_component(hass, component_domain, timeout=30)

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

    # Cloud component requires special handling to retain its shutdown handlers
    if component_domain == CLOUD_DATA_KEY and component_domain in hass.data:
        disable_cloud_component(hass)
    else:
        # Standard component disabling
        if component_domain in hass.data:
            component_data = hass.data[component_domain]
            if hasattr(component_data, "async_stop") and callable(component_data.async_stop):
                _LOGGER.debug("Stopping %s services", component_domain)
                await component_data.async_stop()

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


def patch_cloud_oauth_implementation(hass: HomeAssistant) -> None:
    """Patch the cloud's OAuth2 implementation to properly handle task cancellation."""
    try:
        from homeassistant.components.cloud import account_link
        import hass_nabucasa
        
        _LOGGER.debug("Patching CloudOAuth2Implementation to properly handle shutdown")
        
        # Get the original implementation
        if not hasattr(account_link, "CloudOAuth2Implementation"):
            _LOGGER.debug("CloudOAuth2Implementation not found, skipping patch")
            return
        
        CloudOAuth2Implementation = account_link.CloudOAuth2Implementation
        
        # Store the original method
        original_async_generate_authorize_url = CloudOAuth2Implementation.async_generate_authorize_url
        
        # Create a simpler patched version that wraps the original method
        async def patched_async_generate_authorize_url(self, flow_id: str) -> str:
            """Generate a url for the user to authorize with task tracking for shutdown."""
            # Call the original method
            url = await original_async_generate_authorize_url(self, flow_id)
            
            # Find and track the task that was created by the original method
            for task in asyncio.all_tasks():
                # Look for tasks that match the await_tokens pattern
                if (f"flow={flow_id}" in str(task) or 
                    "await_tokens" in str(task) or 
                    "CloudOAuth2Implementation" in str(task)):
                    
                    _LOGGER.debug("Found and tracking OAuth token task for flow_id=%s", flow_id)
                    
                    if task not in _ACTIVE_TASKS:
                        _ACTIVE_TASKS.append(task)
                        
                        # Clean up the task from tracking when it completes
                        @callback
                        def remove_task(_) -> None:
                            """Remove the task from the tracking list when done."""
                            if task in _ACTIVE_TASKS:
                                _ACTIVE_TASKS.remove(task)
                        
                        task.add_done_callback(remove_task)
            
            return url
        
        # Apply the patch
        CloudOAuth2Implementation.async_generate_authorize_url = patched_async_generate_authorize_url
        _LOGGER.debug("CloudOAuth2Implementation.async_generate_authorize_url successfully patched")
        
    except (ImportError, AttributeError) as ex:
        _LOGGER.debug("Error patching CloudOAuth2Implementation: %s", ex)
