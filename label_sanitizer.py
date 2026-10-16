"""
Sanitization of arbitrary actor names (IAM logins, service account names,
federated identities) into values that satisfy Yandex Cloud's label
requirements: lowercase, limited character set, max 63 chars, must start
with a lowercase letter.

https://yandex.cloud/en/docs/resource-manager/concepts/labels
"""
from __future__ import annotations

import re

_MAX_LABEL_LENGTH = 63
_ALLOWED_CHARS_PATTERN = re.compile(r"[^a-z0-9\-_./\\@]")
_FALLBACK_PREFIX = "user."


def sanitize_label_value(raw_value: str) -> str:
    """
    Turn an arbitrary string into a valid Yandex Cloud label value.

    Steps:
      1. Lowercase everything.
      2. Strip any character outside the allowed set (a-z, 0-9, - _ . / \\ @).
      3. Truncate to the 63-character limit.
      4. Ensure the value starts with a lowercase letter; if not, prefix
         with 'user.' and re-truncate (the prefix itself can push the
         string past the limit).
    """
    value = raw_value.lower()
    value = _ALLOWED_CHARS_PATTERN.sub("", value)
    value = value[:_MAX_LABEL_LENGTH]

    if not value or not value[0].isalpha():
        value = f"{_FALLBACK_PREFIX}{value}"[:_MAX_LABEL_LENGTH]

    return value
