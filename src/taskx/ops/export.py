import hashlib
from pathlib import Path

import yaml  # type: ignore[import-untyped]


def load_profile(profile_path: Path) -> dict:
    if not profile_path.exists():
        return {}
    with open(profile_path) as f:
        return yaml.safe_load(f) or {}

def export_prompt(
    profile: dict,
    templates_dir: Path,
    platform_override: str | None = None,
    model_override: str | None = None,
    taskx_version: str = "UNKNOWN",
    git_hash: str = "UNKNOWN"
) -> str:
    platform = platform_override or profile.get("platform", {}).get("target", "chatgpt")
    model = model_override or profile.get("platform", {}).get("model", "UNKNOWN")

    project_name = profile.get("project", {}).get("name", "UNKNOWN")
    repo_root = profile.get("project", {}).get("repo_root", "UNKNOWN")
    timezone = profile.get("project", {}).get("timezone", "UTC")
    pin_type = profile.get("taskx", {}).get("pin_type", "UNKNOWN")
    pin_value = profile.get("taskx", {}).get("pin_value", "UNKNOWN")
    cli_version = profile.get("taskx", {}).get("cli_min_version", taskx_version)

    header = [
        "# OPERATOR SYSTEM PROMPT",
        f"# TaskX Version: {taskx_version}",
        f"# Git Commit: {git_hash}",
        f"# Project: {project_name}",
        f"# Platform: {platform}",
        f"# Model: {model}",
        f"# Repo Root: {repo_root}",
        f"# Timezone: {timezone}",
        f"# TaskX Pin: {pin_type}={pin_value}",
        f"# CLI Min Version: {cli_version}",
        ""
    ]

    parts = []

    # Discovery logic: sorted lexicographically
    # We follow a specific order for canonical templates if they exist, then others.

    canonical_order = ["base_supervisor.md", "lab_boundary.md"]
    seen = set()

    for t_name in canonical_order:
        p = templates_dir / t_name
        if p.exists():
            parts.append(p.read_text().strip())
            seen.add(t_name)

    # Overlays are special
    overlay_path = templates_dir / "overlays" / f"{platform}.md"
    if overlay_path.exists():
        parts.append(overlay_path.read_text().strip())

    # Other files in templates_dir
    if templates_dir.exists():
        other_files = sorted(
            [f for f in templates_dir.iterdir() if f.is_file() and f.name not in seen and f.suffix == ".md"],
            key=lambda x: x.name
        )
        for f in other_files:
            parts.append(f.read_text().strip())

    handoff = """## Handoff contract
- Follow all instructions provided in this prompt.
- Use TaskX CLI for all task management.
- Ensure all outputs conform to the project spec."""
    parts.append(handoff)

    prompt = "\n\n".join(header + parts)
    # ENSURE NO "Change" TOKENS INJECTED
    prompt = "\n".join([line for line in prompt.splitlines() if line.strip() != "Change"])
    return prompt

def write_if_changed(path: Path, content: str) -> bool:
    """Returns True if file was written, False if identical."""
    if path.exists():
        old_content = path.read_text()
        if old_content == content:
            return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)
    return True

def calculate_hash(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()
