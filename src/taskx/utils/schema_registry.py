"""Schema registry for TaskX with package-data-only loading.

Provides guaranteed schema access when TaskX is installed via pip,
with no dependency on current working directory or repository structure.
"""

import json
from dataclasses import dataclass
from typing import Any

# Use importlib.resources for Python 3.11+
try:
    from importlib.resources import files
except ImportError:
    raise RuntimeError(
        "TaskX requires Python 3.11+ for importlib.resources. "
        "Please upgrade Python."
    )


@dataclass(frozen=True)
class SchemaRegistry:
    """Registry of available schemas from package data.

    Schemas are loaded exclusively from the installed taskx_schemas package,
    ensuring consistent behavior regardless of working directory.

    Attributes:
        available: Sorted tuple of canonical schema names (without .schema.json suffix)
    """

    available: tuple[str, ...] = ()

    def __init__(self) -> None:
        """Initialize registry and discover available schemas."""
        # Discover schemas from package data
        available_schemas = self._discover_schemas()
        object.__setattr__(self, "available", tuple(sorted(available_schemas)))

    def _discover_schemas(self) -> list[str]:
        """Discover available schemas from package data.

        Returns:
            List of canonical schema names (without .schema.json suffix)
        """
        try:
            # Access taskx_schemas package (now a proper package with __init__.py)
            from importlib.resources import files as resource_files
            schema_files = resource_files("taskx_schemas")

            # Collect all .schema.json files
            available = []
            for item in schema_files.iterdir():
                if item.name.endswith(".schema.json"):
                    # Strip .schema.json suffix to get canonical name
                    canonical_name = item.name.replace(".schema.json", "")
                    available.append(canonical_name)

            return available

        except (ModuleNotFoundError, FileNotFoundError, AttributeError, TypeError):
            # Package data not available (shouldn't happen in normal install)
            # Return empty list - will cause helpful errors when trying to load schemas
            return []

    def _normalize_name(self, name: str) -> str:
        """Normalize schema name to canonical form.

        Args:
            name: Schema name (with or without .schema.json suffix)

        Returns:
            Canonical name without suffix
        """
        if name.endswith(".schema.json"):
            return name.replace(".schema.json", "")
        return name

    def _get_filename(self, canonical_name: str) -> str:
        """Get full filename for a canonical schema name.

        Args:
            canonical_name: Schema name without suffix

        Returns:
            Full filename with .schema.json suffix
        """
        return f"{canonical_name}.schema.json"

    def get_text(self, name: str) -> str:
        """Load schema as text from package data.

        Args:
            name: Schema name (with or without .schema.json suffix)

        Returns:
            Schema JSON as text string

        Raises:
            KeyError: If schema not found (includes available schemas in message)
        """
        canonical_name = self._normalize_name(name)

        # Check if schema is available
        if canonical_name not in self.available:
            available_list = ", ".join(self.available[:10])
            if len(self.available) > 10:
                available_list += f", ... ({len(self.available)} total)"

            raise KeyError(
                f"Schema '{canonical_name}' not found in TaskX package data.\n"
                f"Available schemas: {available_list}\n"
                f"If you recently migrated TaskX, ensure schemas were copied to taskx_schemas/.\n"
                f"Run 'taskx-migrate --apply' to sync schemas."
            )

        # Load from package data
        try:
            schema_files = files("taskx_schemas")
            filename = self._get_filename(canonical_name)
            schema_file = schema_files / filename

            # Read the schema file
            if hasattr(schema_file, "read_text"):
                return schema_file.read_text(encoding="utf-8")
            else:
                # Fallback for older importlib.resources API
                return schema_file.read_bytes().decode("utf-8")

        except Exception as e:
            raise RuntimeError(
                f"Failed to load schema '{canonical_name}' from package data: {e}\n"
                f"The schema exists in the registry but couldn't be read.\n"
                f"This may indicate a broken installation. Try reinstalling TaskX."
            ) from e

    def get_json(self, name: str) -> dict[str, Any]:
        """Load schema as parsed JSON dictionary.

        Args:
            name: Schema name (with or without .schema.json suffix)

        Returns:
            Parsed schema dictionary

        Raises:
            KeyError: If schema not found
            ValueError: If schema JSON is malformed
        """
        canonical_name = self._normalize_name(name)
        text = self.get_text(canonical_name)

        try:
            # Explicit cast to satisfy mypy
            res: dict[str, Any] = json.loads(text)
            return res
        except json.JSONDecodeError as e:
            raise ValueError(
                f"Schema '{canonical_name}' contains invalid JSON: {e}\n"
                f"This may indicate a corrupted installation. Try reinstalling TaskX."
            ) from e


# Global registry instance (singleton pattern)
_registry: SchemaRegistry | None = None


def get_registry() -> SchemaRegistry:
    """Get global schema registry instance (singleton).

    Returns:
        Global SchemaRegistry instance
    """
    global _registry
    if _registry is None:
        _registry = SchemaRegistry()
    return _registry


def get_schema_text(schema_name: str) -> str:
    """Load schema JSON text by name (convenience function).

    Args:
        schema_name: Schema name without extension (e.g., "allowlist_diff")

    Returns:
        Schema JSON as text string

    Raises:
        KeyError: If schema not found
    """
    return get_registry().get_text(schema_name)


def get_schema_json(schema_name: str) -> dict[str, Any]:
    """Load schema as parsed dictionary (convenience function).

    Args:
        schema_name: Schema name without extension (e.g., "allowlist_diff")

    Returns:
        Parsed schema dictionary

    Raises:
        KeyError: If schema not found
        ValueError: If schema is malformed
    """
    return get_registry().get_json(schema_name)
