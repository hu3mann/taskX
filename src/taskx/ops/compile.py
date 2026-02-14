import hashlib
import yaml
from pathlib import Path
from typing import Any, Dict

def load_profile(profile_path: Path) -> Dict[str, Any]:
    if not profile_path.exists():
        return {}
    with open(profile_path, "r") as f:
        return yaml.safe_load(f) or {}

def compile_prompt(
    profile: Dict[str, Any],
    templates_dir: Path,
    platform_override: str | None = None,
    model_override: str | None = None
) -> str:
    platform = platform_override or profile.get("platform", {}).get("target", "chatgpt")
    model = model_override or profile.get("platform", {}).get("model", "UNKNOWN")
    
    project_name = profile.get("project", {}).get("name", "UNKNOWN")
    repo_root = profile.get("project", {}).get("repo_root", "UNKNOWN")
    timezone = profile.get("project", {}).get("timezone", "UTC")
    pin_type = profile.get("taskx", {}).get("pin_type", "UNKNOWN")
    pin_value = profile.get("taskx", {}).get("pin_value", "UNKNOWN")
    cli_version = profile.get("taskx", {}).get("cli_min_version", "UNKNOWN")

    header = f"""# OPERATOR SYSTEM PROMPT
# Project: {project_name}
# Platform: {platform}
# Model: {model}
# Repo Root: {repo_root}
# Timezone: {timezone}
# TaskX Pin: {pin_type}={pin_value}
# CLI Min Version: {cli_version}

"""

    base_supervisor = (templates_dir / "base_supervisor.md").read_text() if (templates_dir / "base_supervisor.md").exists() else "# Base Supervisor\n"
    lab_boundary = (templates_dir / "lab_boundary.md").read_text() if (templates_dir / "lab_boundary.md").exists() else "# Lab Boundary\n"
    
    overlay_path = templates_dir / "overlays" / f"{platform}.md"
    overlay = overlay_path.read_text() if overlay_path.exists() else f"# Overlay: {platform}\n"

    handoff = """
## Handoff contract
- Follow all instructions provided in this prompt.
- Use TaskX CLI for all task management.
- Ensure all outputs conform to the project spec.
"""

    return header + base_supervisor + "\n" + lab_boundary + "\n" + overlay + "\n" + handoff

def calculate_hash(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()
