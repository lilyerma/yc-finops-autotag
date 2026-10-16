# YC FinOps Auto-Tagging

A serverless Yandex Cloud Function that automatically tags newly created
VMs with a `created_by` label, by reacting to Audit Trails events in
real time. Built for **FinOps resource attribution**: knowing who
created a resource (and therefore which team/cost center to bill) even
when no tagging policy was enforced at creation time.

🇷🇺 Русская версия: [README.ru.md](README.ru.md)

## Why this exists

One of the most common FinOps problems is unattributed spend: a VM
exists, it costs money, and nobody can say which team owns it. On a
mature platform this is solved by enforcing tags via policy at resource
creation. This project takes a different angle — using the cloud's own
audit log as the source of truth, so ownership tagging can be added
*after the fact*, without changing how teams provision resources.

Approach based on the pattern described in Onelab/Inferit's article
[«Как автоматизировать FinOps-разметку ресурсов в Yandex Cloud с помощью логов»](https://habr.com/ru/companies/inferit/articles/1057926/)
(Habr, itself adapted from Yandex Cloud's audit-trail-driven
security-response reference example). This repo is an independent,
tested implementation of the real-time trigger scenario described there,
plus an example query for the batch/historical scenario.

## Two tagging strategies

| | Real-time trigger (this repo's function) | Batch / historical analysis |
|---|---|---|
| **Latency** | Seconds | Hours to days (run on a schedule) |
| **Infra required** | Audit Trail → log group → Cloud Function trigger | Audit Trail → Object Storage bucket → Yandex Query |
| **Cost profile** | Pay for function invocations + log group storage | Pay for YQL data scanned per run |
| **Best for** | Ongoing tagging of everything going forward | One-off catch-up on an existing untagged fleet |

Both approaches read from the same underlying Audit Trails event
(`yandex.cloud.audit.compute.CreateInstance`); see
[`batch_scenario/historical_vm_creators.sql`](batch_scenario/historical_vm_creators.sql)
for an example Yandex Query used in the second approach.

## Architecture (real-time trigger, this repo)

```
 VM created  ──▶  Audit Trail  ──▶  Cloud Logging log group  ──▶  Cloud Logging trigger
                                                                          │
                                                                          ▼
                                                              Cloud Function (this repo)
                                                                          │
                                                        fail-fast filter: CreateInstance + DONE?
                                                                          │
                                                                          ▼
                                                         Compute API: Get → merge labels → Update
                                                                          │
                                                                          ▼
                                                        VM now has label created_by=<sanitized actor>
```

## Project structure

```
yc-finops-autotag/
├── index.py                     # Cloud Function entry point (handler)
├── audit_event_parser.py         # Parses the trigger's LoggingMessageBatch envelope
├── label_sanitizer.py             # Turns arbitrary actor names into valid label values
├── vm_labeler.py                   # Compute API Get/Update calls (lazy gRPC import)
├── batch_scenario/
│   └── historical_vm_creators.sql   # YQL example for the batch/historical alternative
├── tests/
│   ├── test_audit_event_parser.py
│   └── test_label_sanitizer.py
├── requirements.txt
├── requirements-dev.txt
└── .gitignore
```

As with the [yc-vm-scheduler](../yc-vm-scheduler) project, logic is split
into small, independently testable pieces, keeping cloud-SDK calls
isolated from the pure parsing/validation logic:

- **`audit_event_parser.py`** — no cloud SDK dependency. Unwraps the
  trigger's message envelope, applies the fail-fast filter (does this
  log record match the target `event_type`/`event_status`?), and pulls
  the instance ID and actor identity out of the audit record. Fully
  unit-tested.
- **`label_sanitizer.py`** — no cloud SDK dependency. Implements Yandex
  Cloud's label value rules (lowercase, restricted character set, 63-char
  limit, must start with a letter) as a single pure function. Fully
  unit-tested, including edge cases like all-numeric or all-invalid input.
- **`vm_labeler.py`** — the only module that talks to the Compute API:
  reads current labels, merges in the new one, and pushes the update.
  gRPC/protobuf imports are lazy so the module stays lightweight and
  mockable.
- **`index.py`** — orchestration: iterates the batch, applies the
  filter, and calls the other two modules. Target event type, resource
  type, and label key are all configurable via environment variables
  instead of hardcoded, so the same function can be repointed at other
  resource types (disks, databases, etc.) without a code change.

## Configuration

| Environment variable    | Default                                       | Description                                             |
|--------------------------|------------------------------------------------|-----------------------------------------------------------|
| `TARGET_EVENT_TYPE`       | `yandex.cloud.audit.compute.CreateInstance`   | Audit event type to react to.                            |
| `TARGET_RESOURCE_TYPE`    | `compute.instance`                            | Resource type to look up in `resource_metadata.path`.    |
| `LABEL_KEY`               | `created_by`                                  | Label key written with the sanitized actor name.          |

## Required cloud setup

1. **Audit Trail**, filtered to `yandex.cloud.audit.compute.CreateInstance`,
   sending output to a Cloud Logging log group. Scope it to the narrowest
   organization/cloud/folder that actually needs it, both for cost and
   for blast-radius reasons (see IAM note below).
2. **Cloud Logging trigger** on that log group, pointed at this function.
3. **Service account** for the function with:
   - `compute.editor` — to read and update instance labels
     (least-privilege: scope this to the specific folder(s) that need
     auto-tagging, not the whole cloud)
   - `functions.functionInvoker` — to allow the trigger to invoke the function

## Deployment (Yandex Cloud CLI)

```bash
zip -r function.zip index.py audit_event_parser.py label_sanitizer.py vm_labeler.py requirements.txt

yc serverless function create --name=finops-autotag

yc serverless function version create \
  --function-name=finops-autotag \
  --runtime python312 \
  --entrypoint index.handler \
  --memory 128m \
  --execution-timeout 30s \
  --source-path function.zip \
  --service-account-id <YOUR_SERVICE_ACCOUNT_ID>
```

Then create a Cloud Logging trigger against your log group, pointed at
this function version — see the
[official trigger guide](https://yandex.cloud/en/docs/functions/concepts/trigger/cloud-logging-trigger)
for the exact console/CLI steps.

## Local testing

```bash
pip install -r requirements-dev.txt
pytest tests/ -v
```

`audit_event_parser.py` and `label_sanitizer.py` are fully covered
without needing any cloud credentials or network access.
`vm_labeler.py` is intentionally thin so it can be exercised with a
mocked `InstanceServiceStub` if desired.

## Possible extensions

- Generalize `index.py` into a dispatcher keyed by `event_type`, so one
  function tags VMs, disks, and managed databases alike (config-driven
  `event_type → resource_type → API method` mapping, as discussed in the
  source article)
- Enrich the `created_by` value with a team/cost-center lookup instead of
  the raw IAM identity
- Batch job implementing the historical/YQL scenario end-to-end
  (schedule → query → tag), using `batch_scenario/historical_vm_creators.sql`
  as the starting query
- Dead-letter handling for tag operations that fail repeatedly

## License

MIT
