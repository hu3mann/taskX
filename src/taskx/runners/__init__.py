"""Runner adapters for TaskX orchestrator."""

from taskx.runners.base import RunnerAdapter
from taskx.runners.claude_code import ClaudeCodeAdapter
from taskx.runners.codex_cli import CodexCliAdapter
from taskx.runners.copilot_cli import CopilotCliAdapter
from taskx.runners.google_jules import GoogleJulesAdapter

RUNNER_ADAPTERS: dict[str, type[RunnerAdapter]] = {
    "claude_code": ClaudeCodeAdapter,
    "codex_desktop": CodexCliAdapter,
    "copilot_cli": CopilotCliAdapter,
    "google_jules": GoogleJulesAdapter,
}

__all__ = [
    "RunnerAdapter",
    "ClaudeCodeAdapter",
    "CodexCliAdapter",
    "CopilotCliAdapter",
    "GoogleJulesAdapter",
    "RUNNER_ADAPTERS",
]
