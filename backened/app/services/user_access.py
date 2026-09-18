"""
user_access.py

The vocabulary behind a user's role and access tags, and the one place
that reads/writes User.access — so "stored as JSON text, NULL means
no tags, invalid JSON means no tags" is handled once rather than at
every call site.
"""

import json

ROLE_ADMIN = "admin"
ROLE_MEMBER = "member"
ROLE_SPECIALIST = "specialist"
ROLES = (ROLE_ADMIN, ROLE_MEMBER, ROLE_SPECIALIST)

ACCESS_DATA_EXPORT = "data_export"
ACCESS_DATA_IMPORT = "data_import"
ACCESS_TAGS = (ACCESS_DATA_EXPORT, ACCESS_DATA_IMPORT)

ACCESS_LABELS = {
    ACCESS_DATA_EXPORT: "Data Export",
    ACCESS_DATA_IMPORT: "Data Import",
}


def parse_access(raw) -> list[str]:
    """The stored access tags, filtered to the known vocabulary."""

    if not raw:
        return []

    try:
        values = json.loads(raw)
    except (TypeError, ValueError):
        return []

    if not isinstance(values, list):
        return []

    return [
        value
        for value in values
        if value in ACCESS_TAGS
    ]


def encode_access(tags) -> str:
    """Normalise and store a list of access tags."""

    clean = []

    for tag in tags or []:
        if tag in ACCESS_TAGS and tag not in clean:
            clean.append(tag)

    return json.dumps(clean)


def display_tags(role: str, access) -> list[str]:
    """
    The chips a user's row shows: "Admin" first when they have it,
    then their access tags in a stable order.
    """

    tags = []

    if role == ROLE_ADMIN:
        tags.append("Admin")
    elif role == ROLE_SPECIALIST:
        tags.append("Specialist")

    parsed = access if isinstance(access, list) else parse_access(access)

    for tag in ACCESS_TAGS:
        if tag in parsed:
            tags.append(ACCESS_LABELS[tag])

    return tags
