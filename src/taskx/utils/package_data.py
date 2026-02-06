"""Package data loading utilities for schemas and resources.

Provides portable schema loading that works in both:
- Development mode (editable install)
- Installed mode (regular pip install)

NOTE: This module is deprecated in favor of schema_registry.py
but maintained for backward compatibility.
"""

from pathlib import Path
from typing import Any

# Import from schema_registry (package-only, no CWD fallbacks)
from taskx.utils.schema_registry import (
    get_schema_json as _registry_get_json,
)
from taskx.utils.schema_registry import (
    get_schema_text as _registry_get_text,
)


def get_schema_text(schema_name: str) -> str:
    """Load schema JSON text by name.

    Uses package data only (no CWD fallbacks).

    Args:
        schema_name: Schema name without extension (e.g., "allowlist_diff")

    Returns:
        Schema JSON as text string

    Raises:
        KeyError: If schema cannot be found in package data
    """
    return _registry_get_text(schema_name)


def get_schema_dict(schema_name: str) -> dict[str, Any]:
    """Load schema as parsed dictionary.

    Uses package data only (no CWD fallbacks).

    Args:
        schema_name: Schema name without extension (e.g., "allowlist_diff")

    Returns:
        Parsed schema dictionary

    Raises:
        KeyError: If schema cannot be found
        ValueError: If schema is malformed
    """
    return _registry_get_json(schema_name)


def get_schema_path(schema_name: str) -> Path | None:
    """Get filesystem path to schema (best effort).

    DEPRECATED: This function is deprecated as schemas should be loaded
    via package data, not filesystem paths. It may return None even when
    the schema is available via the registry.

    Args:
        schema_name: Schema name without extension

    Returns:
        None (schemas are accessed via package data, not filesystem)
    """
    # In package-only mode, we don't provide filesystem paths
    # Schemas are accessed via importlib.resources
    return None

