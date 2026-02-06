"""Schema validation utilities for TaskX using package-data-only registry."""

from typing import Any

try:
    import jsonschema
    from jsonschema.validators import Draft202012Validator
    JSONSCHEMA_AVAILABLE = True
except ImportError:
    JSONSCHEMA_AVAILABLE = False

from taskx.utils.schema_registry import get_registry


def validate_data(
    data: dict[str, Any] | list[dict[str, Any]],
    schema_name: str,
    strict: bool = True
) -> tuple[bool, list[str]]:
    """Validate data against a schema from package data.

    Args:
        data: Data to validate (single dict or list of dicts)
        schema_name: Name of schema to validate against
        strict: If True, raise on validation errors; if False, return error list

    Returns:
        Tuple of (is_valid, error_messages)

    Raises:
        ImportError: If jsonschema not installed
        KeyError: If schema not found in package data
        ValueError: If validation fails and strict=True
    """
    if not JSONSCHEMA_AVAILABLE:
        raise ImportError(
            "jsonschema package required for validation.\n"
            "Install with: pip install jsonschema"
        )

    # Load schema from package data (no CWD fallback)
    registry = get_registry()
    schema = registry.get_json(schema_name)

    # Validate
    validator = Draft202012Validator(schema)
    errors = list(validator.iter_errors(data))

    if errors:
        error_messages = [
            f"{'.'.join(str(p) for p in e.path)}: {e.message}"
            if e.path
            else e.message
            for e in errors
        ]

        if strict:
            raise ValueError(
                f"Schema validation failed for '{schema_name}':\n" +
                "\n".join(f"  - {msg}" for msg in error_messages)
            )

        return False, error_messages

    return True, []
