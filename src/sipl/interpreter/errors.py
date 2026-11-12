"""Runtime exceptions for the SIPL interpreter (CORE-03)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from sipl.ast import SourceSpan


@dataclass
class SIPLRuntimeError(Exception):
    """Base class for all runtime errors during SIPL program execution."""

    message: str
    span: SourceSpan | None = None
    state: dict[str, int] = field(default_factory=dict)
    error_kind: str = "RuntimeError"

    def __str__(self) -> str:
        if self.span is not None:
            return (
                f"{self.error_kind} at line {self.span.start_line}, "
                f"column {self.span.start_column}: {self.message}"
            )
        return f"{self.error_kind}: {self.message}"

    def to_dict(self) -> dict[str, Any]:
        """Serialize runtime error to a structured JSON-compatible dictionary."""
        return {
            "error_type": "SIPLRuntimeError",
            "error_kind": self.error_kind,
            "message": self.message,
            "span": self.span.to_dict() if self.span is not None else None,
            "state": dict(self.state),
        }


class UninitializedVariableError(SIPLRuntimeError):
    """Raised when evaluating a variable that has no value in the current state d."""

    variable_name: str

    def __init__(
        self,
        variable_name: str,
        span: SourceSpan | None = None,
        state: dict[str, int] | None = None,
    ) -> None:
        self.variable_name = variable_name
        super().__init__(
            message=f"Variable '{variable_name}' is not initialized in the current state",
            span=span,
            state=dict(state) if state is not None else {},
            error_kind="UninitializedVariableError",
        )


class DivisionByZeroError(SIPLRuntimeError):
    """Raised when integer division '/' attempts to divide by zero."""

    def __init__(
        self,
        span: SourceSpan | None = None,
        state: dict[str, int] | None = None,
    ) -> None:
        super().__init__(
            message="Integer division by zero",
            span=span,
            state=dict(state) if state is not None else {},
            error_kind="DivisionByZeroError",
        )


class StepLimitExceededError(SIPLRuntimeError):
    """Raised when execution exceeds the configured maximum step count (infinite loop guard)."""

    max_steps: int

    def __init__(
        self,
        max_steps: int,
        span: SourceSpan | None = None,
        state: dict[str, int] | None = None,
    ) -> None:
        self.max_steps = max_steps
        super().__init__(
            message=f"Execution exceeded maximum step limit of {max_steps} steps",
            span=span,
            state=dict(state) if state is not None else {},
            error_kind="StepLimitExceededError",
        )
