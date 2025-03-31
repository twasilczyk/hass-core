"""OAuth handling functionality."""
from __future__ import annotations

import asyncio
import logging
from typing import Any

from homeassistant.core import HomeAssistant

from .const import CLOUD_DATA_KEY
from .tasks import track_task

_LOGGER = logging.getLogger(__name__)

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
                task_str = str(task)
                if ("await_tokens" in task_str and 
                    ("CloudOAuth2Implementation" in task_str or 
                     "account_link.py" in task_str or 
                     f"flow={flow_id}" in task_str)):
                    
                    _LOGGER.debug("Found and tracking OAuth token task for flow_id=%s", flow_id)
                    track_task(task)
            
            return url
        
        # Apply the patch
        CloudOAuth2Implementation.async_generate_authorize_url = patched_async_generate_authorize_url
        _LOGGER.debug("CloudOAuth2Implementation.async_generate_authorize_url successfully patched")
        
        # No need to register the shutdown handler here, it's done in __init__.py
        
    except (ImportError, AttributeError) as ex:
        _LOGGER.debug("Error patching CloudOAuth2Implementation: %s", ex)