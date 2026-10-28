"""Agent OS: a git-native harness for long-running agents.

Public surface:
    from replaykit import Kernel, Memory, agent, tool

Those names resolve lazily, and that is load-bearing rather than an
optimisation. ``replaykit.memstore`` is a subpackage, so Python executes this
module before it, and an eager re-export here pulled the entire legacy
harness -- seventeen modules, GitPython and dotenv -- into every process that
imported the memory layer. The layer built to replace the kernel could not be
loaded without the kernel, a brain "consuming only the memstore API" could not
actually do so, and any import-time error in the legacy stack would have
surfaced as a memstore failure. ``tests/test_package_isolation.py`` holds the
line.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:  # pragma: no cover - for type checkers and editors only
    from replaykit.agent import AgentSpec, agent
    from replaykit.kernel import Kernel, RunResult
    from replaykit.llm import BudgetExceeded, InfraFailure, PricingError
    from replaykit.memory import Checkpoint, Memory
    from replaykit.tools import Tool, tool

_LAZY = {
    "AgentSpec": "replaykit.agent",
    "agent": "replaykit.agent",
    "Kernel": "replaykit.kernel",
    "RunResult": "replaykit.kernel",
    "BudgetExceeded": "replaykit.llm",
    "InfraFailure": "replaykit.llm",
    "PricingError": "replaykit.llm",
    "Checkpoint": "replaykit.memory",
    "Memory": "replaykit.memory",
    "Tool": "replaykit.tools",
    "tool": "replaykit.tools",
}

__all__ = [
    "AgentSpec",
    "BudgetExceeded",
    "Checkpoint",
    "InfraFailure",
    "Kernel",
    "Memory",
    "PricingError",
    "RunResult",
    "Tool",
    "agent",
    "tool",
]

__version__ = "0.2.0"


def __getattr__(name: str) -> Any:
    module = _LAZY.get(name)
    if module is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    import importlib

    return getattr(importlib.import_module(module), name)


def __dir__() -> list[str]:
    return sorted(__all__)
