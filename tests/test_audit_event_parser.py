"""Unit tests for audit_event_parser.py — pure logic, no cloud deps."""
import pytest

from audit_event_parser import (
    TriggerParsingError,
    extract_actor_name,
    extract_resource_id,
    extract_trigger_messages,
    is_target_event,
)


def test_extract_trigger_messages_happy_path():
    event = {"messages": [{"details": {"messages": [{"json_payload": {}}]}}]}
    assert extract_trigger_messages(event) == [{"json_payload": {}}]


def test_extract_trigger_messages_missing_key_raises():
    with pytest.raises(TriggerParsingError):
        extract_trigger_messages({})


def test_extract_trigger_messages_empty_list_raises():
    with pytest.raises(TriggerParsingError):
        extract_trigger_messages({"messages": []})


def test_is_target_event_matches():
    log_data = {
        "event_type": "yandex.cloud.audit.compute.CreateInstance",
        "event_status": "DONE",
    }
    assert is_target_event(log_data, "yandex.cloud.audit.compute.CreateInstance") is True


def test_is_target_event_wrong_type():
    log_data = {"event_type": "yandex.cloud.audit.compute.DeleteInstance", "event_status": "DONE"}
    assert is_target_event(log_data, "yandex.cloud.audit.compute.CreateInstance") is False


def test_is_target_event_wrong_status():
    log_data = {
        "event_type": "yandex.cloud.audit.compute.CreateInstance",
        "event_status": "IN_PROGRESS",
    }
    assert is_target_event(log_data, "yandex.cloud.audit.compute.CreateInstance") is False


def test_extract_resource_id_finds_matching_type():
    log_data = {
        "resource_metadata": {
            "path": [
                {"resource_type": "resource-manager.folder", "resource_id": "folder123"},
                {"resource_type": "compute.instance", "resource_id": "vm456"},
            ]
        }
    }
    assert extract_resource_id(log_data, "compute.instance") == "vm456"


def test_extract_resource_id_not_found_returns_none():
    log_data = {"resource_metadata": {"path": []}}
    assert extract_resource_id(log_data, "compute.instance") is None


def test_extract_actor_name_prefers_subject_name():
    log_data = {"authentication": {"subject_name": "alice", "subject_id": "id-1"}}
    assert extract_actor_name(log_data) == "alice"


def test_extract_actor_name_falls_back_to_subject_id():
    log_data = {"authentication": {"subject_id": "id-1"}}
    assert extract_actor_name(log_data) == "id-1"


def test_extract_actor_name_falls_back_to_default():
    assert extract_actor_name({}) == "unknown"
