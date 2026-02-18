"""Google Jules runner adapter (v0 deterministic refusal stub)."""

from __future__ import annotations

from typing import Any


class GoogleJulesAdapter:
    """Adapter for the google_jules runner."""

    runner_id = "google_jules"

    def prepare(self, packet: dict[str, Any], route_plan: dict[str, Any]) -> dict[str, Any]:
        selected = _select_step(route_plan, self.runner_id)
        return {
            "runner_id": self.runner_id,
            "step": selected.get("step"),
            "model_id": selected.get("model"),
            "packet_id": packet.get("id") or packet.get("task_id"),
        }

    def run(self, runspec: dict[str, Any]) -> dict[str, Any]:
        return {
            "status": "refused",
            "reason_code": "RUNNER_NOT_IMPLEMENTED",
            "runner_id": self.runner_id,
            "step": runspec.get("step"),
            "model_id": runspec.get("model_id"),
            "outputs": [],
        }

    def normalize(self, result: dict[str, Any]) -> dict[str, Any]:
        return {
            "status": str(result.get("status", "error")),
            "reason_code": result.get("reason_code"),
            "runner_id": result.get("runner_id", self.runner_id),
            "model_id": result.get("model_id"),
            "step": result.get("step"),
            "outputs": list(result.get("outputs", [])),
        }


def _select_step(route_plan: dict[str, Any], runner_id: str) -> dict[str, Any]:
    steps = route_plan.get("steps", [])
    for item in steps:
        if isinstance(item, dict) and item.get("runner") == runner_id:
            return item
    return steps[0] if steps else {}
