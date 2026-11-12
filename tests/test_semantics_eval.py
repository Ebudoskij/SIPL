"""Unit tests for SEM-02: Step-by-step semantic term evaluation and interpreter equivalence."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from sipl.cli import EXIT_OK, EXIT_RUNTIME_ERROR, run_cli
from sipl.interpreter import (
    DivisionByZeroError,
    StepLimitExceededError,
    UninitializedVariableError,
    execute_program,
)
from sipl.parser import parse_file
from sipl.semantics import (
    SemanticTermEvaluator,
    evaluate_program_semantics,
    evaluate_source_semantics,
)

VALID_DIR = Path(__file__).resolve().parent.parent / "examples" / "valid"


def test_semantic_eval_factorial_rules_and_explanation() -> None:
    """Verify Practicum Example 2.1 (Factorial on {M: 3}) rule transitions."""
    prog = parse_file(VALID_DIR / "03_factorial.sipl")
    res = evaluate_program_semantics(prog, {"M": 3})

    assert res.initial_state == {"M": 3}
    assert res.final_state == {"M": 0, "S": 6}

    rules = [step.rule for step in res.steps]
    assert "AF_CONST" in rules
    assert "AF_DNM" in rules
    assert "AF_S" in rules
    assert "AF_AS" in rules
    assert "AF_SEQ" in rules
    assert "AF_WH_T" in rules
    assert "AF_WH_F" in rules

    # Check human-readable explanation formatting and dict serialization
    explanation_text = res.format_explanation()
    assert "=== SIPL Compositional Semantic Term Evaluation (SEM-02) ===" in explanation_text
    assert "[AF_AS]" in explanation_text
    assert "[AF_WH_T]" in explanation_text
    assert "[AF_WH_F]" in explanation_text
    assert "Final State:   d_final = {M ↦ 0, S ↦ 6}" in explanation_text

    res_dict = res.to_dict()
    assert res_dict["final_state"] == {"M": 0, "S": 6}
    assert res_dict["step_count"] == len(res.steps)


def test_semantic_eval_if_branches_and_id() -> None:
    """Verify AF_IF_T, AF_IF_F, and AF_ID rule applications."""
    source = (
        "begin\n"
        "    if X > 0 then\n"
        "        Y := X / 2\n"
        "    else\n"
        "        skip\n"
        "end"
    )
    res_true = evaluate_source_semantics(source, {"X": 8})
    assert res_true.final_state == {"X": 8, "Y": 4}
    assert any(s.rule == "AF_IF_T" for s in res_true.steps)

    res_false = evaluate_source_semantics(source, {"X": -2})
    assert res_false.final_state == {"X": -2}
    assert any(s.rule == "AF_IF_F" for s in res_false.steps)
    assert any(s.rule == "AF_ID" for s in res_false.steps)


@pytest.mark.parametrize(
    ("filename", "initial_state"),
    [
        ("01_minimal_skip.sipl", {"A": 7}),
        ("02_arithmetic_and_negatives.sipl", {}),
        ("03_factorial.sipl", {"M": 5}),
        ("04_gcd_euclid_canonical.sipl", {"M": 28, "N": 12}),
        ("05_division_with_remainder.sipl", {"M": 19, "N": 5}),
        ("06_primality_check_extensions.sipl", {"M": 9}),
        ("06_primality_check_extensions.sipl", {"M": 7}),
        ("07_nested_if_max3.sipl", {"M": 10, "N": 25, "K": 18}),
        ("08_sum_progression_bang.sipl", {"N": 6}),
        ("09_nested_blocks_and_div.sipl", {}),
        ("10_combined_logical_and_arith.sipl", {"X": 4, "Y": 11, "Z": 5}),
        ("11_precedence_while_if_seq.sipl", {"M": 3}),
        ("12_fibonacci.sipl", {"N": 6}),
    ],
)
def test_equivalence_between_interpreter_and_semantic_evaluator(
    filename: str,
    initial_state: dict[str, int],
) -> None:
    """Verify CORE-03 interpreter and SEM-02 semantic evaluator produce identical states."""
    prog = parse_file(VALID_DIR / filename)
    interp_res = execute_program(prog, initial_state)
    sem_res = evaluate_program_semantics(prog, initial_state)
    assert sem_res.final_state == interp_res.final_state


def test_semantic_eval_runtime_errors_and_limits() -> None:
    """Verify UninitializedVariableError, DivisionByZeroError, and StepLimitExceededError."""
    with pytest.raises(UninitializedVariableError):
        evaluate_source_semantics("begin X := Y + 1 end", {})

    with pytest.raises(DivisionByZeroError):
        evaluate_source_semantics("begin X := 10 / 0 end", {})

    with pytest.raises(StepLimitExceededError):
        evaluate_source_semantics("begin while 1 = 1 do skip end", {}, max_steps=15)

    with pytest.raises(ValueError, match="max_steps must be >= 1"):
        SemanticTermEvaluator(max_steps=0)


def test_cli_sem_eval_subcommand(capsys: pytest.CaptureFixture[str]) -> None:
    """Verify `sipl sem-eval` CLI subcommand in text, --json, and error modes."""
    gcd_path = str(VALID_DIR / "04_gcd_euclid_canonical.sipl")

    # Text mode
    code = run_cli(["sem-eval", gcd_path, "-s", "M=28", "N=12"])
    out = capsys.readouterr()
    assert code == EXIT_OK
    assert "=== SIPL Compositional Semantic Term Evaluation (SEM-02) ===" in out.out
    assert "Final State:   d_final = {M ↦ 4, N ↦ 4}" in out.out

    # JSON mode
    code_json = run_cli(["sem-eval", gcd_path, "-s", "M=28", "N=12", "--json"])
    out_json = capsys.readouterr()
    assert code_json == EXIT_OK
    payload = json.loads(out_json.out)
    assert payload["status"] == "ok"
    assert payload["evaluation"]["final_state"] == {"M": 4, "N": 4}

    # Runtime error (missing M, N)
    code_err = run_cli(["sem-eval", gcd_path, "--json"])
    out_err = capsys.readouterr()
    assert code_err == EXIT_RUNTIME_ERROR
    err_payload = json.loads(out_err.out)
    assert err_payload["error"]["error_kind"] == "UninitializedVariableError"
