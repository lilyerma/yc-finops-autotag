"""
Parsing of Yandex Cloud Logging trigger events carrying Audit Trails
records (LoggingMessageBatch), and extraction of the fields needed for
FinOps auto-tagging.

Kept free of any cloud SDK import so it can be unit-tested in isolation.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class TriggerParsingError(ValueError):
    """Raised when the incoming event doesn't match the expected trigger shape."""


def extract_trigger_messages(event: dict) -> List[dict]:
    """
    Pull the list of individual log records out of a Cloud Logging trigger
    event. Triggers wrap the raw log-group payload in their own envelope,
    so the real records live at event['messages'][0]['details']['messages'].
    """
    try:
        return event["messages"][0]["details"]["messages"]
    except (KeyError, IndexError, TypeError) as exc:
        raise TriggerParsingError(f"Unexpected trigger batch structure: {exc}") from exc


def is_target_event(
    log_data: dict,
    target_event_type: str,
    target_status: str = "DONE",
) -> bool:
    """
    Fail-fast filter: is this audit log record the specific event we care
    about (matching event_type) and did it complete successfully
    (event_status == target_status)?
    """
    return (
        log_data.get("event_type") == target_event_type
        and log_data.get("event_status") == target_status
    )


def extract_resource_id(log_data: dict, resource_type: str) -> Optional[str]:
    """
    Walk resource_metadata.path looking for an entry of the given
    resource_type (e.g. 'compute.instance') and return its resource_id.
    """
    resource_path = log_data.get("resource_metadata", {}).get("path", [])
    for resource in resource_path:
        if resource.get("resource_type") == resource_type:
            return resource.get("resource_id")
    return None


def extract_actor_name(log_data: dict, default: str = "unknown") -> str:
    """
    Identify who triggered the event: prefer the human-readable
    subject_name, fall back to subject_id, then to a default placeholder.
    """
    authentication: Dict[str, Any] = log_data.get("authentication", {})
    return authentication.get("subject_name") or authentication.get("subject_id") or default
