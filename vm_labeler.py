"""
Thin wrapper around the Yandex Compute API for reading an instance's
current labels and writing back an updated 'owner' label.

Import of the generated gRPC/protobuf modules is deliberately deferred to
inside the functions that need them (lazy import) — this keeps the module
importable, and its logic testable/mockable, without pulling in the full
gRPC stack at module load time.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class TagResult:
    instance_id: str
    label_key: str
    label_value: str
    operation_id: str


def tag_instance(
    instance_service,
    instance_id: str,
    label_key: str,
    label_value: str,
) -> TagResult:
    """
    Read the instance's current labels, set/overwrite `label_key` to
    `label_value`, and push the update via the Compute API.

    `instance_service` is an already-constructed InstanceServiceStub
    (or a compatible mock/fake for testing).
    """
    from yandex.cloud.compute.v1.instance_service_pb2 import (
        GetInstanceRequest,
        UpdateInstanceRequest,
    )
    from google.protobuf.field_mask_pb2 import FieldMask

    current_instance = instance_service.Get(GetInstanceRequest(instance_id=instance_id))
    labels = dict(current_instance.labels)
    labels[label_key] = label_value

    operation = instance_service.Update(
        UpdateInstanceRequest(
            instance_id=instance_id,
            update_mask=FieldMask(paths=["labels"]),
            labels=labels,
        )
    )

    logger.info(
        "Tagged instance %s with %s=%s (operation_id=%s)",
        instance_id,
        label_key,
        label_value,
        operation.id,
    )

    return TagResult(
        instance_id=instance_id,
        label_key=label_key,
        label_value=label_value,
        operation_id=operation.id,
    )
