"""TaskX adapters for integrating with external systems.

Adapters provide thin shims that map external project structures
to TaskX expectations without modifying TaskX core logic.

Discovery uses the ``taskx.adapters`` entry-point group so that
third-party packages can register adapters automatically.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from taskx_adapters.base import AdapterInfo, BaseAdapter
from taskx_adapters.dopemux import (
    DopemuxAdapter,
    compute_dopemux_paths,
    detect_dopemux_root,
    select_run_folder,
)
from taskx_adapters.types import DopemuxDetection, DopemuxPaths

if TYPE_CHECKING:
    from collections.abc import Iterator

__all__ = [
    "AdapterInfo",
    "BaseAdapter",
    "DopemuxAdapter",
    "DopemuxDetection",
    "DopemuxPaths",
    "compute_dopemux_paths",
    "detect_dopemux_root",
    "discover_adapters",
    "get_adapter",
    "select_run_folder",
]


def discover_adapters() -> Iterator[BaseAdapter]:
    """Yield all adapters registered under the ``taskx.adapters`` entry-point group.

    Uses ``importlib.metadata.entry_points(group=...)`` (Python 3.10+).
    Since this project requires Python >=3.11, the ``group`` parameter is always available.
    """
    from importlib.metadata import entry_points

    eps = entry_points(group="taskx.adapters")

    for ep in eps:
        adapter_cls = ep.load()
        if isinstance(adapter_cls, type) and issubclass(adapter_cls, BaseAdapter):
            yield adapter_cls()
        elif callable(adapter_cls):
            instance = adapter_cls()
            if isinstance(instance, BaseAdapter):
                yield instance


def get_adapter(name: str) -> BaseAdapter | None:
    """Return the first adapter whose ``name`` matches, or ``None``."""
    for adapter in discover_adapters():
        if adapter.name == name:
            return adapter
    return None
