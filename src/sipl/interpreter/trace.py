"""Event-driven execution trace model for SIPL (CORE-04)."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from sipl.ast import SourceSpan


class TraceEventKind(str, Enum):
    """Types of events emitted during SIPL program execution."""

    BEFORE_STATEMENT = "BeforeStatement"
    AFTER_STATEMENT = "AfterStatement"
    VARIABLE_CHANGED = "VariableChanged"
    CONDITION_EVALUATED = "ConditionEvaluated"
    PROGRAM_TERMINATED = "ProgramTerminated"


@dataclass(frozen=True)
class TraceEvent:
    """Single deterministic execution trace event linked to a SourceSpan and state."""

    index: int
    step: int
    kind: TraceEventKind
    statement_type: str
    span: SourceSpan
    state: dict[str, int]
    state_delta: dict[str, int] = field(default_factory=dict)
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Serialize trace event to a JSON-compatible dictionary."""
        return {
            "index": self.index,
            "step": self.step,
            "kind": self.kind.value,
            "statement_type": self.statement_type,
            "span": self.span.to_dict(),
            "state": dict(self.state),
            "state_delta": dict(self.state_delta),
            "details": dict(self.details),
        }

    def format_line(self) -> str:
        """Format a single trace event as a concise human-readable line."""
        loc = f"[{self.span}]"
        state_str = (
            "{" + ", ".join(f"{k}={v}" for k, v in self.state.items()) + "}"
            if self.state
            else "{}"
        )
        if self.kind == TraceEventKind.VARIABLE_CHANGED:
            var = self.details.get("variable")
            old_v = self.details.get("old_value")
            new_v = self.details.get("new_value")
            old_repr = "⊥" if old_v is None else str(old_v)
            return (
                f"#{self.index:03d} (step {self.step}) {self.kind.value} {loc}: "
                f"{var}: {old_repr} -> {new_v} | state={state_str}"
            )
        if self.kind == TraceEventKind.CONDITION_EVALUATED:
            construct = self.details.get("construct", "cond")
            result = self.details.get("result")
            return (
                f"#{self.index:03d} (step {self.step}) {self.kind.value} {loc}: "
                f"{construct} condition => {result} | state={state_str}"
            )
        if self.kind == TraceEventKind.PROGRAM_TERMINATED:
            status = self.details.get("status", "completed")
            return (
                f"#{self.index:03d} (step {self.step}) {self.kind.value} {loc}: "
                f"status={status} | final_state={state_str}"
            )
        return (
            f"#{self.index:03d} (step {self.step}) {self.kind.value} "
            f"({self.statement_type}) {loc} | state={state_str}"
        )


@dataclass(frozen=True)
class ExecutionTrace:
    """Complete structured trace of a SIPL program execution."""

    initial_state: dict[str, int]
    final_state: dict[str, int]
    steps_executed: int
    events: tuple[TraceEvent, ...]
    terminated_normally: bool = True
    error: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        """Serialize the entire execution trace into a JSON-compatible dictionary."""
        return {
            "initial_state": dict(self.initial_state),
            "final_state": dict(self.final_state),
            "steps_executed": self.steps_executed,
            "terminated_normally": self.terminated_normally,
            "error": dict(self.error) if self.error is not None else None,
            "event_count": len(self.events),
            "events": [ev.to_dict() for ev in self.events],
        }

    def to_json(self, indent: int = 2) -> str:
        """Serialize the execution trace to a formatted JSON string."""
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=indent)

    def format_text(self) -> str:
        """Format the execution trace as human-readable text output."""
        lines = [
            f"=== SIPL Execution Trace ({len(self.events)} events, {self.steps_executed} steps) ===",
            f"Initial state: {self.initial_state}",
        ]
        for ev in self.events:
            lines.append("  " + ev.format_line())
        lines.append(f"Final state:   {self.final_state}")
        lines.append(f"Status:        {'COMPLETED' if self.terminated_normally else 'ERROR'}")
        return "\n".join(lines)


class TraceCollector:
    """Internal helper that records TraceEvents during interpreter execution."""

    def __init__(self) -> None:
        self._events: list[TraceEvent] = []

    @property
    def events(self) -> tuple[TraceEvent, ...]:
        return tuple(self._events)

    def emit(
        self,
        *,
        step: int,
        kind: TraceEventKind,
        statement_type: str,
        span: SourceSpan,
        state: dict[str, int],
        state_delta: dict[str, int] | None = None,
        details: dict[str, Any] | None = None,
    ) -> TraceEvent:
        """Create and append a new TraceEvent with a sequential index."""
        event = TraceEvent(
            index=len(self._events),
            step=step,
            kind=kind,
            statement_type=statement_type,
            span=span,
            state=state,
            state_delta=dict(state_delta) if state_delta else {},
            details=dict(details) if details else {},
        )
        self._events.append(event)
        return event
