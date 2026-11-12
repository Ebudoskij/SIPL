"""SIPL Interpreter and execution trace package (CORE-03, CORE-04)."""

from sipl.interpreter.errors import (
    DivisionByZeroError,
    SIPLRuntimeError,
    StepLimitExceededError,
    UninitializedVariableError,
)
from sipl.interpreter.evaluator import (
    DEFAULT_MAX_STEPS,
    ExecutionResult,
    Interpreter,
    execute_program,
    run_source,
    trace_program,
    trace_source,
)
from sipl.interpreter.state import ExecutionState
from sipl.interpreter.trace import (
    ExecutionTrace,
    TraceCollector,
    TraceEvent,
    TraceEventKind,
)

__all__ = [
    "DEFAULT_MAX_STEPS",
    "DivisionByZeroError",
    "ExecutionResult",
    "ExecutionState",
    "ExecutionTrace",
    "Interpreter",
    "SIPLRuntimeError",
    "StepLimitExceededError",
    "TraceCollector",
    "TraceEvent",
    "TraceEventKind",
    "UninitializedVariableError",
    "execute_program",
    "run_source",
    "trace_program",
    "trace_source",
]
