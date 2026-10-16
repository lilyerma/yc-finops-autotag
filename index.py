"""
Yandex Cloud Function: FinOps auto-tagging of newly created VMs.

Listens to a Cloud Logging trigger fed by an Audit Trails log group.
On every batch of log records, it fail-fast filters for a successful
'CreateInstance' event, extracts who created the VM, and writes that
identity into a `created_by` label on the instance — so cost/billing
data can later be attributed to a team or individual without any
upfront tagging policy in place.

Approach based on the pattern described in:
"Как автоматизировать FinOps-разметку ресурсов в Yandex Cloud с помощью логов"
https://habr.com/ru/companies/inferit/articles/1057926/
(itself adapted from Yandex Cloud's audit-trail-driven security-response example).

Required setup (see README for details):
  - Audit Trails trail capturing yandex.cloud.audit.compute.CreateInstance
  - Cloud Logging log group as the trail's destination
  - Cloud Logging trigger on that log group, pointed at this function
  - Service account with audit-trails.viewer + compute.editor,
    scoped to the narrowest folder/cloud that's actually needed

Environment variables (all optional, sane defaults shown):
  TARGET_EVENT_TYPE - audit event type to react to
                       (default: yandex.cloud.audit.compute.CreateInstance)
  TARGET_RESOURCE_TYPE - resource type to look up in resource_metadata.path
                          (default: compute.instance)
  LABEL_KEY - label key to write the sanitized actor name into
              (default: created_by)
"""
from __future__ import annotations

import logging
import os

import yandexcloud

from audit_event_parser import (
    TriggerParsingError,
    extract_actor_name,
    extract_resource_id,
    extract_trigger_messages,
    is_target_event,
)
from label_sanitizer import sanitize_label_value
from vm_labeler import tag_instance

logger = logging.getLogger()
logger.setLevel(logging.INFO)

TARGET_EVENT_TYPE = os.environ.get(
    "TARGET_EVENT_TYPE", "yandex.cloud.audit.compute.CreateInstance"
)
TARGET_RESOURCE_TYPE = os.environ.get("TARGET_RESOURCE_TYPE", "compute.instance")
LABEL_KEY = os.environ.get("LABEL_KEY", "created_by")


def handler(event: dict, context) -> dict:
    try:
        trigger_messages = extract_trigger_messages(event)
    except TriggerParsingError as err:
        logger.error(str(err))
        return {"statusCode": 400, "body": "Invalid trigger batch format"}

    from yandex.cloud.compute.v1.instance_service_pb2_grpc import InstanceServiceStub

    sdk = yandexcloud.SDK()
    instance_service = sdk.client(InstanceServiceStub)

    for msg in trigger_messages:
        log_data = msg.get("json_payload")
        if not log_data:
            continue

        if not is_target_event(log_data, TARGET_EVENT_TYPE):
            logger.info(
                "Skipping event: %s [%s]",
                log_data.get("event_type"),
                log_data.get("event_status"),
            )
            continue

        instance_id = extract_resource_id(log_data, TARGET_RESOURCE_TYPE)
        if not instance_id:
            logger.error(
                "%s ID not found in resource_metadata.path", TARGET_RESOURCE_TYPE
            )
            continue

        actor_name = extract_actor_name(log_data)
        label_value = sanitize_label_value(actor_name)

        logger.info(
            "Processing target instance %s created by %s", instance_id, actor_name
        )

        try:
            tag_instance(instance_service, instance_id, LABEL_KEY, label_value)
        except Exception as exc:  # noqa: BLE001 - keep processing remaining messages
            logger.error("Failed to tag instance %s: %s", instance_id, exc)

    return {"statusCode": 200, "body": "OK"}
