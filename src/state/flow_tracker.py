"""TTL-based flow tracking for signal editing flows.

This module provides in-memory tracking of active editing flows between users
and signals. Each flow has a TTL (Time To Live) and only the owner can edit
a signal while the flow is active.

Key features:
- TTL-based expiration (default 72 hours)
- Automatic cleanup of expired flows
- Max flows limit with force cleanup
- Thread-safe operations
"""

import os
import time
from dataclasses import dataclass
from typing import Dict, Optional

from src.utils.logger import get_logger

logger = get_logger(__name__)

# Configuration
_flow_ttl_raw = int(os.getenv("FLOW_TTL_SECONDS", "259200"))
FLOW_TTL = _flow_ttl_raw if _flow_ttl_raw > 0 else 259200  # 72 hours default, must be positive
MAX_FLOWS = 10000
CLEANUP_INTERVAL = 100  # Cleanup every N operations

# Global state
_active_flows: Dict[int, "FlowInfo"] = {}
_operation_counter = 0


@dataclass
class FlowInfo:
    """Information about an active flow.

    Attributes:
        user_id: The user who owns this flow
        timestamp: Unix timestamp when the flow was created
    """
    user_id: int
    timestamp: float


def start_flow(signal_id: int, user_id: int) -> None:
    """Register a new flow for a signal.

    Args:
        signal_id: Signal ID to track
        user_id: User ID who owns the flow
    """
    global _operation_counter

    _active_flows[signal_id] = FlowInfo(user_id=user_id, timestamp=time.time())
    _operation_counter += 1

    logger.debug(
        "Flow started",
        signal_id=signal_id,
        user_id=user_id,
        total_flows=len(_active_flows)
    )

    # Periodic cleanup
    if _operation_counter >= CLEANUP_INTERVAL:
        _operation_counter = 0
        cleanup_expired()

    # Force cleanup if max flows exceeded
    if len(_active_flows) > MAX_FLOWS:
        _force_cleanup()


def get_flow_owner(signal_id: int) -> Optional[int]:
    """Get the owner of a flow if it exists and is not expired.

    Args:
        signal_id: Signal ID to check

    Returns:
        User ID of the flow owner, or None if flow doesn't exist or is expired
    """
    flow = _active_flows.get(signal_id)
    if flow is None:
        return None

    # Check if expired
    if time.time() - flow.timestamp > FLOW_TTL:
        logger.debug("Flow expired", signal_id=signal_id, user_id=flow.user_id)
        del _active_flows[signal_id]
        return None

    return flow.user_id


def is_allowed(signal_id: int, user_id: int) -> bool:
    """Check if a user is allowed to edit a signal.

    A user is allowed if:
    - No flow exists for the signal, OR
    - The user is the owner of the flow

    Args:
        signal_id: Signal ID to check
        user_id: User ID to verify

    Returns:
        True if the user is allowed to edit, False otherwise
    """
    owner = get_flow_owner(signal_id)

    # No owner = allowed
    if owner is None:
        return True

    # User is owner = allowed
    allowed = owner == user_id

    if not allowed:
        logger.debug(
            "Flow access denied",
            signal_id=signal_id,
            user_id=user_id,
            owner_id=owner
        )

    return allowed


def end_flow(signal_id: int) -> None:
    """Remove a flow from tracking.

    Args:
        signal_id: Signal ID to remove
    """
    if signal_id in _active_flows:
        flow = _active_flows[signal_id]
        del _active_flows[signal_id]
        logger.debug(
            "Flow ended",
            signal_id=signal_id,
            user_id=flow.user_id,
            total_flows=len(_active_flows)
        )


def cleanup_expired() -> int:
    """Remove all expired flows from tracking.

    Returns:
        Number of flows removed
    """
    now = time.time()
    expired = [
        signal_id
        for signal_id, flow in _active_flows.items()
        if now - flow.timestamp > FLOW_TTL
    ]

    for signal_id in expired:
        del _active_flows[signal_id]

    if expired:
        logger.debug(
            "Cleaned up expired flows",
            count=len(expired),
            total_flows=len(_active_flows)
        )

    return len(expired)


def _force_cleanup() -> None:
    """Force cleanup by removing oldest flows when MAX_FLOWS is exceeded.

    Removes oldest 10% of flows to bring count under limit.
    """
    if len(_active_flows) <= MAX_FLOWS:
        return

    # Sort by timestamp (oldest first)
    sorted_flows = sorted(
        _active_flows.items(),
        key=lambda x: x[1].timestamp
    )

    # Remove oldest 10%
    to_remove = max(1, len(_active_flows) // 10)

    for signal_id, _ in sorted_flows[:to_remove]:
        del _active_flows[signal_id]

    logger.warning(
        "Force cleanup triggered",
        removed=to_remove,
        total_flows=len(_active_flows),
        max_flows=MAX_FLOWS
    )
