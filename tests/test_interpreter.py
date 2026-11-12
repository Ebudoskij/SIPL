"""Unit tests for CORE-03: SIPL Interpreter, State Model, and Runtime Error Handling."""

from __future__ import annotations

from pathlib import Path

import pytest

from sipl.interpreter import (
    DivisionByZeroError,
    ExecutionState,
    Interpreter,
    StepLimitExceededError,
    UninitializedVariableError,
    execute_program,
    run_source,
)
from sipl.parser import parse_file

VALID_DIR = Path(__file__).resolve().parent.parent / "examples" / "valid"


def test_execution_state_operations_and_validation() -> None:
    """Verify ExecutionState get, set, snapshot, copy, notation, and type validation."""
    empty_state = ExecutionState()
    assert len(empty_state) == 0
    assert empty_state.format_notation() == "∅"
    assert repr(empty_state) == "ExecutionState({})"

    state = ExecutionState({"N": 2, "M": 5})
    assert len(state) == 2
    assert "M" in state
    assert "X" not in state
    assert list(sorted(state)) == ["M", "N"]
    assert state.get("M") == 5
    assert state.format_notation() == "{M ↦ 5, N ↦ 2}"
    assert state == ExecutionState({"M": 5, "N": 2})
    assert state == {"M": 5, "N": 2}
    assert (state == 42) is False

    cloned = state.copy()
    cloned.set("M", 99)
    assert state.get("M") == 5
    assert cloned.get("M") == 99

    with pytest.raises(ValueError, match="Invalid variable name"):
        ExecutionState({"": 1})

    with pytest.raises(TypeError, match="must be integers"):
        ExecutionState({"X": True})  # type: ignore[dict-item]

    with pytest.raises(TypeError, match="requires an int"):
        state.set("X", False)  # type: ignore[arg-type]


def test_minimal_skip_and_nested_blocks() -> None:
    """Verify skip statement and nested begin..end blocks preserve state."""
    res = run_source("begin skip end", {"A": 42})
    assert res.final_state == {"A": 42}
    assert res.steps_executed == 1
    assert res.to_dict() == {"final_state": {"A": 42}, "steps_executed": 1}

    res_block = run_source(
        "begin begin A := 10; begin B := A + 5 end end end"
    )
    assert res_block.final_state == {"A": 10, "B": 15}


def test_arithmetic_and_integer_division_semantics() -> None:
    """Verify +, -, *, / and negative integer literals."""
    source = (
        "begin\n"
        "    A := 17;\n"
        "    B := 5;\n"
        "    Q := A / B;\n"
        "    R := A - Q * B;\n"
        "    NEG := -17 / B\n"
        "end"
    )
    res = run_source(source)
    assert res.final_state == {
        "A": 17,
        "B": 5,
        "Q": 3,
        "R": 2,
        "NEG": -3,
    }


def test_if_then_else_and_logical_operators() -> None:
    """Verify if-then-else with =, >, ¬, !, ∨, ||."""
    source = (
        "begin\n"
        "    if (X = 0) ∨ (X > 10) then\n"
        "        R1 := 1\n"
        "    else\n"
        "        R1 := 0;\n"
        "    if !(X = 5) &&_dummy = 0 || ¬(X > 3) then\n"
        "        skip\n"
        "    else\n"
        "        skip\n"
        "end"
    )
    # Test canonical and extension logical operators cleanly
    prog_src = (
        "begin\n"
        "    if (X = 0) ∨ (X > 10) then R1 := 1 else R1 := 0;\n"
        "    if !(X = 5) || ¬(X > 3) then R2 := 1 else R2 := 0\n"
        "end"
    )
    res1 = run_source(prog_src, {"X": 5})
    assert res1.final_state == {"X": 5, "R1": 0, "R2": 0}

    res2 = run_source(prog_src, {"X": 12})
    assert res2.final_state == {"X": 12, "R1": 1, "R2": 1}


def test_textbook_algorithms_execution() -> None:
    """Verify execution of canonical textbook SIPL programs on concrete states."""
    # 1. Factorial: 5! = 120
    fact_prog = parse_file(VALID_DIR / "03_factorial.sipl")
    fact_res = execute_program(fact_prog, {"M": 5})
    assert fact_res.final_state == {"M": 0, "S": 120}

    # 2. Euclid's GCD: gcd(48, 18) = 6
    gcd_prog = parse_file(VALID_DIR / "04_gcd_euclid_canonical.sipl")
    gcd_res = execute_program(gcd_prog, {"M": 48, "N": 18})
    assert gcd_res.final_state == {"M": 6, "N": 6}

    # 3. Division with remainder: 17 = 3 * 5 + 2
    div_prog = parse_file(VALID_DIR / "05_division_with_remainder.sipl")
    div_res = execute_program(div_prog, {"M": 17, "N": 5})
    assert div_res.final_state == {"M": 17, "N": 5, "Q": 3, "R": 2}

    # 4. Primality check: 13 is prime (R=1), 15 is composite (R=0)
    prime_prog = parse_file(VALID_DIR / "06_primality_check_extensions.sipl")
    res_13 = execute_program(prime_prog, {"M": 13})
    assert res_13.final_state["R"] == 1
    res_15 = execute_program(prime_prog, {"M": 15})
    assert res_15.final_state["R"] == 0

    # 5. Sum of progression 1..10 = 55
    sum_prog = parse_file(VALID_DIR / "08_sum_progression_bang.sipl")
    sum_res = execute_program(sum_prog, {"N": 10})
    assert sum_res.final_state == {"I": 11, "N": 10, "S": 55}

    # 6. Fibonacci: N=7 -> F0=13, F1=21
    fib_prog = parse_file(VALID_DIR / "12_fibonacci.sipl")
    fib_res = execute_program(fib_prog, {"N": 7})
    assert fib_res.final_state["F0"] == 13
    assert fib_res.final_state["F1"] == 21


def test_uninitialized_variable_error() -> None:
    """Verify reading an uninitialized variable raises UninitializedVariableError with span."""
    source = (
        "begin\n"
        "    X := 10;\n"
        "    Y := X + UNKNOWN_VAR\n"
        "end"
    )
    with pytest.raises(UninitializedVariableError) as exc_info:
        run_source(source)

    err = exc_info.value
    assert err.variable_name == "UNKNOWN_VAR"
    assert err.span is not None
    assert err.span.start_line == 3
    assert err.span.start_column == 14
    assert err.state == {"X": 10}
    assert "UNKNOWN_VAR" in str(err)
    err_dict = err.to_dict()
    assert err_dict["error_kind"] == "UninitializedVariableError"
    assert err_dict["state"] == {"X": 10}


def test_division_by_zero_error() -> None:
    """Verify dividing by zero raises DivisionByZeroError with source span and state."""
    source = (
        "begin\n"
        "    A := 10;\n"
        "    B := 0;\n"
        "    C := A / B\n"
        "end"
    )
    with pytest.raises(DivisionByZeroError) as exc_info:
        run_source(source)

    err = exc_info.value
    assert err.span is not None
    assert err.span.start_line == 4
    assert err.state == {"A": 10, "B": 0}
    assert "DivisionByZeroError at line 4" in str(err)


def test_step_limit_exceeded_infinite_loop_guard() -> None:
    """Verify infinite loops are safely terminated by StepLimitExceededError."""
    source = (
        "begin\n"
        "    X := 0;\n"
        "    while 1 = 1 do\n"
        "        X := X + 1\n"
        "end"
    )
    with pytest.raises(StepLimitExceededError) as exc_info:
        run_source(source, max_steps=25)

    err = exc_info.value
    assert err.max_steps == 25
    assert err.span is not None
    assert err.state["X"] > 0
    assert "maximum step limit of 25" in str(err)

    with pytest.raises(ValueError, match="max_steps must be >= 1"):
        Interpreter(max_steps=0)
