-- Example Yandex Query (YQL) for the batch / historical-analysis scenario:
-- instead of reacting to events in real time via a trigger, this scans
-- Audit Trails logs already archived in an Object Storage bucket and
-- lists who created each VM, for offline / periodic tagging.
--
-- Prerequisite: an Object Storage → Yandex Query binding over the bucket
-- that receives your Audit Trails output, with data source type "Audit Trails".
--
-- Replace `my_audit_trails_binding` below with your binding's name.

SELECT
    CAST(JSON_VALUE(data, "$.event_time") AS Timestamp) AS event_time,

    JSON_VALUE(data, "$.authentication.subject_name") AS creator_name,
    JSON_VALUE(data, "$.authentication.subject_id")   AS creator_id,
    JSON_VALUE(data, "$.authentication.subject_type")  AS creator_type,

    JSON_VALUE(data, "$.details.instance_id")   AS vm_id,
    JSON_VALUE(data, "$.details.instance_name") AS vm_name,

    JSON_VALUE(data, "$.cloud_name")  AS cloud_name,
    JSON_VALUE(data, "$.folder_name") AS folder_name
FROM
    `my_audit_trails_binding`
WHERE
    JSON_VALUE(data, "$.event_type") = 'yandex.cloud.audit.compute.CreateInstance'
    AND JSON_VALUE(data, "$.event_status") = 'DONE'
ORDER BY
    event_time DESC
LIMIT 100;
