"""Repository root detection and project type inference."""

import fnmatch
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from taskx.utils.repo_config import (
    MarkerDef,
    RepoConfig,
    load_repo_config,
)

ProjectType = Literal["python", "node", "go", "rust", "unknown"]


@dataclass(frozen=True)
class RepoInfo:
    """Information about detected repository."""

    root: Path
    project_type: ProjectType
    marker: str  # e.g. ".git", "pyproject.toml", "package.json"


@dataclass(frozen=True)
class RepoScope:
    """Complete repository scope including workspace and project roots."""

    workspace_root: Path
    project_root: Path
    workspace_marker: str
    project_marker: str
    project_type: ProjectType
    config_used: bool


def detect_repo_root(
    start: Path,
    repo_root_override: Path | None = None,
) -> RepoInfo:
    """
    Detect repository root and project type.

    Priority order:
      1. Explicit --repo-root if provided
      2. Nearest parent containing .git/
      3. Nearest parent containing language marker (pyproject.toml, package.json, etc.)
      4. Hard fail if none found

    Args:
        start: Starting directory for search
        repo_root_override: Explicit repo root path (skips detection)

    Returns:
        RepoInfo with root path, project type, and marker used

    Raises:
        RuntimeError: If no repo root can be detected
    """
    # Handle explicit override
    if repo_root_override is not None:
        override_path = repo_root_override.resolve()
        if not override_path.exists():
            raise RuntimeError(f"Explicit repo root does not exist: {override_path}")
        if not override_path.is_dir():
            raise RuntimeError(f"Explicit repo root is not a directory: {override_path}")

        # Infer project type from markers at override root
        project_type = _infer_project_type(override_path)

        return RepoInfo(
            root=override_path,
            project_type=project_type,
            marker="override"
        )

    # Search upward from start
    current = start.resolve()

    # Walk up to filesystem root
    while True:
        # Check for .git/ first (highest priority)
        if (current / ".git").exists():
            project_type = _infer_project_type(current)
            return RepoInfo(
                root=current,
                project_type=project_type,
                marker=".git"
            )

        # Check for language markers in priority order
        marker_checks = [
            ("pyproject.toml", "python"),
            ("package.json", "node"),
            ("go.mod", "go"),
            ("Cargo.toml", "rust"),
            ("requirements.txt", "python"),
        ]

        for marker_file, proj_type in marker_checks:
            if (current / marker_file).exists():
                return RepoInfo(
                    root=current,
                    project_type=proj_type,  # type: ignore
                    marker=marker_file
                )

        # Move up one level
        parent = current.parent
        if parent == current:
            # Reached filesystem root without finding marker
            checked_markers = [".git/"] + [m[0] for m in marker_checks]
            raise RuntimeError(
                f"No repository root found. Started at: {start}\n"
                f"Checked markers: {', '.join(checked_markers)}"
            )

        current = parent


def _infer_project_type(directory: Path) -> ProjectType:
    """
    Infer project type from markers in a directory.

    Uses the same priority order as detection.
    """
    # Priority order for type inference
    if (directory / "pyproject.toml").exists():
        return "python"
    if (directory / "package.json").exists():
        return "node"
    if (directory / "go.mod").exists():
        return "go"
    if (directory / "Cargo.toml").exists():
        return "rust"
    if (directory / "requirements.txt").exists():
        return "python"

    # No markers found
    return "unknown"


def find_taskx_repo_root(start_path: Path) -> Path | None:
    """
    Find TaskX repository root by searching for .taskxroot marker.

    Walks up directory tree from start_path looking for:
    1. .taskxroot file (highest priority)
    2. pyproject.toml where [project].name == "taskx" (fallback)

    Args:
        start_path: Starting directory for search

    Returns:
        Path to repo root, or None if not found
    """
    import tomllib

    current = start_path.resolve()

    while True:
        # Check for .taskxroot marker (primary)
        taskxroot_marker = current / ".taskxroot"
        if taskxroot_marker.exists() and taskxroot_marker.is_file():
            return current

        # Check for pyproject.toml with project.name == "taskx" (fallback)
        pyproject = current / "pyproject.toml"
        if pyproject.exists() and pyproject.is_file():
            try:
                with open(pyproject, "rb") as f:
                    data = tomllib.load(f)
                    if data.get("project", {}).get("name") == "taskx":
                        return current
            except (OSError, tomllib.TOMLDecodeError):
                pass  # Invalid TOML, keep searching

        # Move up one level
        parent = current.parent
        if parent == current:
            # Reached filesystem root without finding marker
            return None

        current = parent


def require_taskx_repo_root(start_path: Path) -> Path:
    """
    Find TaskX repository root or raise error with helpful message.

    Args:
        start_path: Starting directory for search

    Returns:
        Path to repo root

    Raises:
        RuntimeError: If no TaskX repo detected
    """
    repo_root = find_taskx_repo_root(start_path)

    if repo_root is None:
        raise RuntimeError(
            "TaskX repo not detected. This command requires running in a TaskX repository.\n"
            "To fix:\n"
            "  1. Create a .taskxroot marker: touch .taskxroot\n"
            "  2. Or ensure pyproject.toml has [project].name = 'taskx'\n"
            "  3. Or use --no-repo-guard to bypass (use with caution)"
        )

    return repo_root


def detect_repo_scope(
    start: Path,
    repo_root_override: Path | None = None,
    project_root_override: Path | None = None,
) -> RepoScope:
    """
    Detect workspace and project roots for mono-repo support.

    Workspace root is typically the top-level .git directory.
    Project root is the nearest subproject marker within workspace.

    Args:
        start: Starting directory for search
        repo_root_override: Explicit workspace root path
        project_root_override: Explicit project root path

    Returns:
        RepoScope with workspace and project roots

    Raises:
        RuntimeError: If roots cannot be detected or are ambiguous
    """
    # Step 1: Determine workspace root
    if repo_root_override is not None:
        workspace_root = repo_root_override.resolve()
        if not workspace_root.exists():
            raise RuntimeError(f"Explicit workspace root does not exist: {workspace_root}")
        if not workspace_root.is_dir():
            raise RuntimeError(f"Explicit workspace root is not a directory: {workspace_root}")
        workspace_marker = "override"
    else:
        # Detect workspace using default markers or config
        workspace_root, workspace_marker = _detect_workspace_root(start)

    # Step 2: Load config from workspace root (if present)
    config = load_repo_config(workspace_root)

    # Step 3: Determine project root
    if project_root_override is not None:
        project_root = project_root_override.resolve()
        if not project_root.exists():
            raise RuntimeError(f"Explicit project root does not exist: {project_root}")
        if not project_root.is_dir():
            raise RuntimeError(f"Explicit project root is not a directory: {project_root}")

        # Verify project root is within workspace root
        try:
            project_root.relative_to(workspace_root)
        except ValueError:
            raise RuntimeError(
                f"Project root {project_root} is not within workspace root {workspace_root}"
            )

        project_marker = "override"
        project_type = _infer_project_type_from_config(project_root, config)
    else:
        # Detect project root within workspace
        project_root, project_marker, project_type = _detect_project_root(
            start, workspace_root, config
        )

    return RepoScope(
        workspace_root=workspace_root,
        project_root=project_root,
        workspace_marker=workspace_marker,
        project_marker=project_marker,
        project_type=project_type,
        config_used=(config is not None),
    )


def _detect_workspace_root(start: Path) -> tuple[Path, str]:
    """Detect workspace root using default markers (.git)."""
    current = start.resolve()

    while True:
        # Check for .git/ (primary workspace marker)
        if (current / ".git").exists():
            return current, ".git"

        # Move up one level
        parent = current.parent
        if parent == current:
            # Reached filesystem root without finding workspace marker
            raise RuntimeError(
                f"No workspace root found. Started at: {start}\n"
                f"Checked markers: .git/"
            )

        current = parent


def _detect_project_root(
    start: Path,
    workspace_root: Path,
    config: RepoConfig | None,
) -> tuple[Path, str, ProjectType]:
    """
    Detect project root within workspace using markers.

    Returns:
        Tuple of (project_root, marker, project_type)
    """
    # Get project markers from config or use defaults
    if config and config.project_markers:
        markers = sorted(config.project_markers, key=lambda m: (m.priority, m.name))
    else:
        # Default project markers in priority order
        markers = [
            MarkerDef("pyproject.toml", "file", "python", 10),
            MarkerDef("package.json", "file", "node", 20),
            MarkerDef("go.mod", "file", "go", 30),
            MarkerDef("Cargo.toml", "file", "rust", 40),
            MarkerDef("requirements.txt", "file", "python", 50),
        ]

    # Search upward from start to workspace_root
    current = start.resolve()

    while True:
        # Check if we're outside workspace
        try:
            current.relative_to(workspace_root)
        except ValueError:
            break  # Outside workspace, stop searching

        # Check for project markers in priority order
        for marker_def in markers:
            marker_path = current / marker_def.name
            if marker_def.kind == "file" and marker_path.is_file() or marker_def.kind == "dir" and marker_path.is_dir():
                return current, marker_def.name, marker_def.project_type

        # Stop at workspace root
        if current == workspace_root:
            break

        # Move up one level
        parent = current.parent
        if parent == current:
            break

        current = parent

    # No project marker found, check config for defaults
    if config and config.project_selector.default_project_root:
        default_path = workspace_root / config.project_selector.default_project_root
        if default_path.exists() and default_path.is_dir():
            project_type = _infer_project_type_from_config(default_path, config)
            return default_path, "default_from_config", project_type

    # Fallback: workspace root is project root
    return workspace_root, "workspace_fallback", "unknown"


def _infer_project_type_from_config(
    directory: Path,
    config: RepoConfig | None,
) -> ProjectType:
    """Infer project type from directory markers using config or defaults."""
    if config and config.project_markers:
        markers = sorted(config.project_markers, key=lambda m: (m.priority, m.name))
        for marker_def in markers:
            marker_path = directory / marker_def.name
            if marker_def.kind == "file" and marker_path.is_file() or marker_def.kind == "dir" and marker_path.is_dir():
                return marker_def.project_type

    # Fallback to default inference
    return _infer_project_type(directory)


def scan_projects(
    workspace_root: Path,
    config: RepoConfig | None = None,
) -> list[RepoInfo]:
    """
    Scan workspace for all project roots.

    A project is a directory containing any configured project marker.

    Args:
        workspace_root: Workspace root to scan
        config: Optional repo config for marker definitions

    Returns:
        List of RepoInfo sorted by repo-relative path (deterministic)
    """
    # Get project markers from config or use defaults
    if config and config.project_markers:
        markers = config.project_markers
    else:
        markers = [
            MarkerDef("pyproject.toml", "file", "python", 10),
            MarkerDef("package.json", "file", "node", 20),
            MarkerDef("go.mod", "file", "go", 30),
            MarkerDef("Cargo.toml", "file", "rust", 40),
            MarkerDef("requirements.txt", "file", "python", 50),
        ]

    # Get ignore patterns
    ignore_patterns = []
    if config and config.project_selector.ignore_paths:
        ignore_patterns = config.project_selector.ignore_paths

    projects: dict[Path, RepoInfo] = {}

    # Walk workspace deterministically (sorted)
    for dirpath in sorted(workspace_root.rglob("*")):
        if not dirpath.is_dir():
            continue

        # Check if path matches any ignore pattern
        rel_path = dirpath.relative_to(workspace_root).as_posix()
        if any(fnmatch.fnmatch(rel_path, pattern) for pattern in ignore_patterns):
            continue

        # Check for project markers
        for marker_def in markers:
            marker_path = dirpath / marker_def.name
            if marker_def.kind == "file" and marker_path.is_file() or marker_def.kind == "dir" and marker_path.is_dir():
                if dirpath not in projects:
                    projects[dirpath] = RepoInfo(
                        root=dirpath,
                        project_type=marker_def.project_type,
                        marker=marker_def.name,
                    )
                break

    # Return sorted by relative path (deterministic)
    return sorted(
        projects.values(),
        key=lambda p: p.root.relative_to(workspace_root).as_posix()
    )
