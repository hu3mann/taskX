"""JSON output utilities with schema validation."""

import hashlib
import json
from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

try:
    from taskx.schemas.message import CanonicalMessage
except ImportError:
    CanonicalMessage = None  # type: ignore[assignment, misc]
from taskx.schemas.validator import validate_data


def write_messages_with_validation(messages: list[CanonicalMessage], output_path: Path) -> tuple[int, int]:
    """Write messages to JSON file with schema validation.

    Args:
        messages: List of CanonicalMessage objects to write
        output_path: Path to output JSON file

    Behavior:
        - Validates each message via Pydantic; invalid ones are written to a
          quarantine file (messages_bad.jsonl) and skipped from main output.
        - Does not raise on validation errors; continues writing valid data.
        - Raises OSError only if the main file cannot be written.
    Returns:
        (valid_count, invalid_count)
    """
    # Validate messages, quarantining any invalid ones
    quarantine_dir = output_path.parent / "quarantine"
    quarantine_path = quarantine_dir / "messages_bad.jsonl"
    messages_data: list[dict] = []
    bad_count = 0

    for i, msg in enumerate(messages):
        try:
            # Pydantic validation happens automatically
            msg_dict = msg.model_dump(mode="json", by_alias=True)
            # JSON Schema validation (secondary)
            ok, errors = validate_data(msg_dict, "message", strict=False)
            if ok:
                messages_data.append(msg_dict)
            else:
                quarantine_dir.mkdir(parents=True, exist_ok=True)
                with open(quarantine_path, "a", encoding="utf-8") as qf:
                    qf.write(json.dumps({
                        "index": i,
                        "error": "jsonschema: " + "; ".join(errors),
                        "row": msg_dict,
                    }) + "\n")
                bad_count += 1
        except Exception as e:  # pragma: no cover - triggered only by malformed data
            # Lazily create quarantine dir and append the bad record with reason
            quarantine_dir.mkdir(parents=True, exist_ok=True)
            with open(quarantine_path, "a", encoding="utf-8") as qf:
                qf.write(json.dumps({
                    "index": i,
                    "error": f"pydantic: {e}",
                }) + "\n")
            bad_count += 1

    # Write to file with pretty formatting
    output_data = {
        "messages": messages_data,
        "total_count": len(messages_data),
        "schema_version": "1.0"
    }

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, indent=2, ensure_ascii=False)

    return len(messages_data), bad_count


def write_messages_jsonl_stream(
    messages: Iterable[CanonicalMessage],
    output_path: Path
) -> tuple[int, int]:
    """Write messages to JSONL with schema validation, streaming input.

    Args:
        messages: Iterable of CanonicalMessage objects
        output_path: Path to output JSONL file

    Returns:
        (valid_count, invalid_count)
    """
    quarantine_dir = output_path.parent / "quarantine"
    quarantine_path = quarantine_dir / "messages_bad.jsonl"
    valid_count = 0
    bad_count = 0

    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w", encoding="utf-8") as f:
        for i, msg in enumerate(messages):
            try:
                msg_dict = msg.model_dump(mode="json", by_alias=True)
                ok, errors = validate_data(msg_dict, "message", strict=False)
                if ok:
                    f.write(json.dumps(msg_dict, ensure_ascii=False) + "\n")
                    valid_count += 1
                else:
                    quarantine_dir.mkdir(parents=True, exist_ok=True)
                    with open(quarantine_path, "a", encoding="utf-8") as qf:
                        qf.write(json.dumps({
                            "index": i,
                            "error": "jsonschema: " + "; ".join(errors),
                            "row": msg_dict,
                        }) + "\n")
                    bad_count += 1
            except Exception as e:  # pragma: no cover - malformed data
                quarantine_dir.mkdir(parents=True, exist_ok=True)
                with open(quarantine_path, "a", encoding="utf-8") as qf:
                    qf.write(json.dumps({
                        "index": i,
                        "error": f"pydantic: {e}",
                    }) + "\n")
                bad_count += 1

    return valid_count, bad_count


def _redact_long_strings(data: Any, max_len: int = 256) -> Any:
    """Redact long strings in data structure for quarantine.

    Args:
        data: Data to redact (dict, list, or primitive)
        max_len: Maximum string length before redaction

    Returns:
        Redacted copy of data
    """
    if isinstance(data, dict):
        return {k: _redact_long_strings(v, max_len) for k, v in data.items()}
    elif isinstance(data, list):
        return [_redact_long_strings(item, max_len) for item in data]
    elif isinstance(data, str) and len(data) > max_len:
        # Redact long strings with hash and length
        return {
            "_omitted": True,
            "_sha256": hashlib.sha256(data.encode("utf-8")).hexdigest(),
            "_len": len(data),
        }
    else:
        return data


def quarantine_invalid_json(
    *,
    data: dict,
    schema_name: str,
    error: Exception,
    quarantine_dir: Path,
    run_id: str | None,
    intended_path: Path,
    allow_raw: bool,
) -> Path:
    """Write invalid JSON to quarantine with metadata.

    Args:
        data: Invalid data payload
        schema_name: Schema that validation failed against
        error: The validation exception
        quarantine_dir: Directory to write quarantine file
        run_id: Optional run ID for filename
        intended_path: Path where valid artifact would have been written
        allow_raw: If False, redact long strings to prevent data leaks

    Returns:
        Path to quarantine file
    """
    quarantine_dir.mkdir(parents=True, exist_ok=True)

    # Generate deterministic filename
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    run_part = run_id if run_id else "no_run"
    filename = f"{schema_name}__{run_part}__{timestamp}.json"
    quarantine_path = quarantine_dir / filename

    # Redact data if needed
    quarantine_data = data if allow_raw else _redact_long_strings(data)

    # Build quarantine record
    quarantine_record = {
        "schema_name": schema_name,
        "created_at": datetime.now(UTC).isoformat(),
        "run_id": run_id,
        "intended_path": str(intended_path),
        "error": str(error),
        "data": quarantine_data,
    }

    # Write quarantine file
    with open(quarantine_path, "w", encoding="utf-8") as f:
        json.dump(quarantine_record, f, indent=2, ensure_ascii=False)

    return quarantine_path


def write_json_strict(
    *,
    data: dict,
    output_path: Path,
    schema_name: str,
    run_id: str | None = None,
    quarantine_dir: Path | None = None,
    allow_raw_in_quarantine: bool = False,
) -> None:
    """Write JSON with strict schema validation and quarantine on failure.

    Args:
        data: Dictionary to write as JSON
        output_path: Path to output file
        schema_name: Name of schema to validate against
        run_id: Optional run ID for quarantine filename
        quarantine_dir: Directory for quarantine files (default: output_path.parent / "quarantine")
        allow_raw_in_quarantine: If True, allow raw data in quarantine; if False, redact long strings

    Raises:
        RuntimeError: If validation fails (after quarantining)
    """
    # Validate against schema
    try:
        ok, errors = validate_data(data, schema_name, strict=True)
        if not ok:
            raise ValueError(f"Validation failed: {errors}")
    except Exception as e:
        # Quarantine invalid data
        qdir = quarantine_dir if quarantine_dir else (output_path.parent / "quarantine")
        quarantine_path = quarantine_invalid_json(
            data=data,
            schema_name=schema_name,
            error=e,
            quarantine_dir=qdir,
            run_id=run_id,
            intended_path=output_path,
            allow_raw=allow_raw_in_quarantine,
        )

        raise RuntimeError(
            f"Schema validation failed for {schema_name} at {output_path}. "
            f"Invalid data quarantined to {quarantine_path}"
        ) from e

    # Write valid data
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def write_json_with_validation(data: dict, output_path: Path, schema_name: str) -> None:
    """Write JSON to file with schema validation.

    Legacy wrapper around write_json_strict for backward compatibility.

    Args:
        data: Dictionary to write as JSON
        output_path: Path to output file
        schema_name: Name of schema to validate against

    Raises:
        ValueError: If validation fails
    """
    try:
        write_json_strict(
            data=data,
            output_path=output_path,
            schema_name=schema_name,
            run_id=None,
            quarantine_dir=None,
            allow_raw_in_quarantine=False,
        )
    except RuntimeError as e:
        # Convert to ValueError for backward compatibility
        raise ValueError(str(e)) from e
