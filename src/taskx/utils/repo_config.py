"""Repository configuration loader for mono-repo and workspace support.

Supports .chatx/repo.toml or .chatx/repo.json configuration files
for customizing marker priorities and project selection rules.
"""

import json

# Use tomllib for 3.11+
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

ProjectType = Literal["python", "node", "go", "rust", "unknown"]


@dataclass(frozen=True)
class MarkerDef:
    """Definition of a repository marker (file or directory)."""

    name: str
    kind: Literal["file", "dir"]
    project_type: ProjectType
    priority: int = 100  # Lower number = higher priority


@dataclass(frozen=True)
class ProjectSelector:
    """Rules for selecting a project in multi-project repos."""

    prefer_paths: list[str] = field(default_factory=list)
    default_project_root: str | None = None
    ignore_paths: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class RepoConfig:
    """Repository configuration for workspace and project detection."""

    workspace_markers: list[MarkerDef] = field(default_factory=list)
    project_markers: list[MarkerDef] = field(default_factory=list)
    project_selector: ProjectSelector = field(default_factory=ProjectSelector)

    @classmethod
    def from_dict(cls, data: dict) -> "RepoConfig":
        """Parse and validate config dict into RepoConfig."""
        workspace_markers = []
        if "markers" in data and "workspace" in data["markers"]:
            for m in data["markers"]["workspace"]:
                workspace_markers.append(
                    MarkerDef(
                        name=m["name"],
                        kind=m["kind"],
                        project_type=m.get("project_type", "unknown"),
                        priority=m.get("priority", 100),
                    )
                )

        project_markers = []
        if "markers" in data and "project" in data["markers"]:
            for m in data["markers"]["project"]:
                project_markers.append(
                    MarkerDef(
                        name=m["name"],
                        kind=m["kind"],
                        project_type=m.get("project_type", "unknown"),
                        priority=m.get("priority", 100),
                    )
                )

        selector_data = data.get("project_selector", {})
        project_selector = ProjectSelector(
            prefer_paths=selector_data.get("prefer_paths", []),
            default_project_root=selector_data.get("default_project_root"),
            ignore_paths=selector_data.get("ignore_paths", []),
        )

        return cls(
            workspace_markers=workspace_markers,
            project_markers=project_markers,
            project_selector=project_selector,
        )


def load_repo_config(workspace_root: Path) -> RepoConfig | None:
    """Load repository configuration from .chatx/repo.toml or .chatx/repo.json.

    Priority order:
    1. .chatx/repo.toml (preferred)
    2. .chatx/repo.json (fallback)

    Args:
        workspace_root: Repository workspace root directory

    Returns:
        RepoConfig if config file found and valid, None otherwise

    Raises:
        RuntimeError: If config file is malformed or invalid
    """
    chatx_dir = workspace_root / ".chatx"

    # Try TOML first
    toml_path = chatx_dir / "repo.toml"
    if toml_path.exists():
        try:
            with open(toml_path, "rb") as f:
                data = tomllib.load(f)
            return RepoConfig.from_dict(data)
        except tomllib.TOMLDecodeError as e:
            raise RuntimeError(
                f"Malformed TOML config at {toml_path}: {e}"
            ) from e
        except (KeyError, TypeError, ValueError) as e:
            raise RuntimeError(
                f"Invalid config structure in {toml_path}: {e}"
            ) from e

    # Try JSON fallback
    json_path = chatx_dir / "repo.json"
    if json_path.exists():
        try:
            with open(json_path, encoding="utf-8") as f:
                data = json.load(f)
            return RepoConfig.from_dict(data)
        except json.JSONDecodeError as e:
            raise RuntimeError(
                f"Malformed JSON config at {json_path}: {e}"
            ) from e
        except (KeyError, TypeError, ValueError) as e:
            raise RuntimeError(
                f"Invalid config structure in {json_path}: {e}"
            ) from e

    return None
