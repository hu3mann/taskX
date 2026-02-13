"""TaskX assisted routing subsystem."""

from taskx.router.availability import ensure_default_availability, load_availability
from taskx.router.handoff import render_handoff_markdown
from taskx.router.planner import build_route_plan, explain_step, extract_router_hints, parse_steps
from taskx.router.reporting import (
    render_route_plan_markdown,
    route_plan_from_dict,
    route_plan_to_dict,
    write_route_artifacts,
)

__all__ = [
    "build_route_plan",
    "ensure_default_availability",
    "explain_step",
    "extract_router_hints",
    "load_availability",
    "parse_steps",
    "render_handoff_markdown",
    "render_route_plan_markdown",
    "route_plan_from_dict",
    "route_plan_to_dict",
    "write_route_artifacts",
]
