"""Unit tests for CORE-04: Event-driven execution trace model."""

from __future__ import annotations

import json
import pytest

from sipl.interpreter import (
    DivisionByZeroError,
    TraceEventKind,
    trace_source,
)


def test_trace_determinism_and_completeness_on_while_loop() -> None:
    """Verify deterministic and complete event trace for factorial while-loop."""
    source = (
        "begin\n"
        "    S := 1;\n"
        "    while M > 0 do\n"
        "        begin\n"
        "            S := S * M;\n"
        "            M := M - 1\n"
        "        end\n"
        "end"
    )
    trace1 = trace_source(source, {"M": 3})
    trace2 = trace_source(source, {"M": 3})

    # Determinism check
    assert trace1.to_dict() == trace2.to_dict()
    assert trace1.initial_state == {"M": 3}
    assert trace1.final_state == {"M": 0, "S": 6}
    assert trace1.terminated_normally is True
    assert trace1.error is None

    # Sequential indices 0 .. len-1
    indices = [ev.index for ev in trace1.events]
    assert indices == list(range(len(trace1.events)))

    # Check condition evaluations: 3 True iterations + 1 False exit check = 4 checks
    cond_events = [
        ev for ev in trace1.events if ev.kind == TraceEventKind.CONDITION_EVALUATED
    ]
    assert len(cond_events) == 4
    assert [ev.details["result"] for ev in cond_events] == [True, True, True, False]
    assert [ev.details["iteration"] for ev in cond_events] == [0, 1, 2, 3]
    for ev in cond_events:
        assert ev.span.start_line == 3

    # Check variable changes: S:=1, then (S:=3, M:=2), (S:=6, M:=1), (S:=6, M:=0) => 7 changes
    var_events = [
        ev for ev in trace1.events if ev.kind == TraceEventKind.VARIABLE_CHANGED
    ]
    assert len(var_events) == 7
    assert var_events[0].details == {
        "variable": "S",
        "old_value": None,
        "new_value": 1,
    }
    assert var_events[0].state_delta == {"S": 1}
    assert var_events[-1].details == {
        "variable": "M",
        "old_value": 1,
        "new_value": 0,
    }
    assert var_events[-1].state_delta == {"M": 0}

    # Last event is always ProgramTerminated
    last_ev = trace1.events[-1]
    assert last_ev.kind == TraceEventKind.PROGRAM_TERMINATED
    assert last_ev.details["status"] == "completed"
    assert last_ev.state == {"M": 0, "S": 6}


def test_trace_branching_if_else_and_skip() -> None:
    """Verify trace events for if-then-else branches and skip statement."""
    source = (
        "begin\n"
        "    if X > 5 then\n"
        "        Y := 10\n"
        "    else\n"
        "        skip\n"
        "end"
    )
    # Branch 1: then_branch (X = 8)
    trace_then = trace_source(source, {"X": 8})
    kinds_then = [ev.kind for ev in trace_then.events]
    assert kinds_then == [
        TraceEventKind.BEFORE_STATEMENT,     # IfStmt
        TraceEventKind.CONDITION_EVALUATED,  # X > 5 => True
        TraceEventKind.BEFORE_STATEMENT,     # AssignStmt Y := 10
        TraceEventKind.VARIABLE_CHANGED,     # Y: None -> 10
        TraceEventKind.AFTER_STATEMENT,      # AssignStmt
        TraceEventKind.AFTER_STATEMENT,      # IfStmt
        TraceEventKind.PROGRAM_TERMINATED,   # Program
    ]
    cond_then = trace_then.events[1]
    assert cond_then.details == {"construct": "if", "result": True, "branch": "then"}

    # Branch 2: else_branch (X = 2) -> executes SkipStmt
    trace_else = trace_source(source, {"X": 2})
    kinds_else = [ev.kind for ev in trace_else.events]
    assert kinds_else == [
        TraceEventKind.BEFORE_STATEMENT,     # IfStmt
        TraceEventKind.CONDITION_EVALUATED,  # X > 5 => False
        TraceEventKind.BEFORE_STATEMENT,     # SkipStmt
        TraceEventKind.AFTER_STATEMENT,      # SkipStmt
        TraceEventKind.AFTER_STATEMENT,      # IfStmt
        TraceEventKind.PROGRAM_TERMINATED,   # Program
    ]
    cond_else = trace_else.events[1]
    assert cond_else.details == {"construct": "if", "result": False, "branch": "else"}


def test_trace_json_and_text_formatting() -> None:
    """Verify JSON serialization and human-readable text output of ExecutionTrace."""
    source = "begin A := 4; B := A / 2 end"
    trace = trace_source(source)

    json_str = trace.to_json()
    parsed = json.loads(json_str)
    assert parsed["initial_state"] == {}
    assert parsed["final_state"] == {"A": 4, "B": 2}
    assert parsed["terminated_normally"] is True
    assert parsed["event_count"] == len(trace.events)

    text_out = trace.format_text()
    assert "=== SIPL Execution Trace" in text_out
    assert "VariableChanged" in text_out
    assert "ProgramTerminated" in text_out
    assert "Status:        COMPLETED" in text_out


def test_trace_error_handling_and_capture_mode() -> None:
    """Verify trace behavior when runtime error occurs (raise vs capture_errors=True)."""
    source = "begin X := 10; Y := X / 0 end"

    with pytest.raises(DivisionByZeroError):
        trace_source(source, capture_errors=False)

    err_trace = trace_source(source, capture_errors=True)
    assert err_trace.terminated_normally is False
    assert err_trace.error is not None
    assert err_trace.error["error_kind"] == "DivisionByZeroError"
    assert err_trace.final_state == {"X": 10}
    assert err_trace.events[-1].kind == TraceEventKind.PROGRAM_TERMINATED
    assert err_trace.events[-1].details["status"] == "error"
    assert "Status:        ERROR" in err_trace.format_text()
