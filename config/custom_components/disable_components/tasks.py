"""Task tracking and management functionality."""
from __future__ import annotations

import asyncio
import logging
from typing import List

from homeassistant.core import Event, callback

_LOGGER = logging.getLogger(__name__)

# Global list to track tasks that need cancellation at shutdown
_ACTIVE_TASKS: List[asyncio.Task] = []

def track_task(task: asyncio.Task) -> None:
    """Track a task for cancellation at shutdown."""
    if task not in _ACTIVE_TASKS:
        _ACTIVE_TASKS.append(task)
        
        @callback
        def remove_task(_) -> None:
            """Remove the task from the tracking list when done."""
            if task in _ACTIVE_TASKS:
                _ACTIVE_TASKS.remove(task)
        
        task.add_done_callback(remove_task)
        _LOGGER.debug("Task %s added to tracking", task)

@callback
def cancel_tracked_tasks(event: Event = None) -> None:
    """Cancel all tracked tasks at shutdown."""
    if not _ACTIVE_TASKS:
        return
    
    _LOGGER.debug("Cancelling %d tracked tasks at shutdown", len(_ACTIVE_TASKS))
    for task in _ACTIVE_TASKS:
        if not task.done():
            task.cancel()