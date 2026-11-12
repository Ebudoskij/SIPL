"""Automated runner for CORE-06: SIPL Conformance Suite."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from sipl.cli import run_cli
from sipl.interpreter import SIPLRuntimeError, execute_program
from sipl.parser import SIPLSyntaxError, parse_program
from sipl.semantics import build_semantic_term, evaluate_program_semantics

CONFORMANCE_DIR = Path(__file__).resolve().parent.parent / "examples" / "conformance"
CONFORMANCE_FILES = sorted(CONFORMANCE_DIR.glob("*.json"))


def _load_case(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def test_conformance_suite_has_sufficient_cases() -> None:
    """Verify conformance suite contains valid, syntax_error, and runtime_error cases."""
    assert len(CONFORMANCE_FILES) >= 15
    categories = {_load_case(p)["category"] for p in CONFORMANCE_FILES}
    assert categories == {"valid_execution", "syntax_error", "runtime_error"}


@pytest.mark.parametrize("case_path", CONFORMANCE_FILES, ids=lambda p: p.stem)
def test_conformance_case(
    case_path: Path,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Execute a portable JSON conformance test case against AST, Interpreter, Semantics, and CLI."""
    spec = _load_case(case_path)
    category = spec["category"]
    source: str = spec["source"]
    expected_exit_code: int = spec["expected_exit_code"]

    # Write temporary .sipl source file for CLI conformance check
    temp_sipl = tmp_path / f"{spec['name']}.sipl"
    temp_sipl.write_text(source, encoding="utf-8")

    if category == "valid_execution":
        initial_state: dict[str, int] = spec.get("initial_state", {})
        max_steps: int = spec.get("max_steps", 10_000)

        # 1. Parse and verify AST
        program = parse_program(source)
        if "expected_ast" in spec:
            assert program.to_dict() == spec["expected_ast"]
        if "expected_ast_root_body_type" in spec:
            assert program.body.to_dict()["type"] == spec["expected_ast_root_body_type"]

        # 2. Verify Compositional Semantic Term (SEM-01)
        if "expected_semantic_term" in spec:
            sem_term = build_semantic_term(program)
            assert sem_term.format("course") == spec["expected_semantic_term"]

        # 3. Verify Interpreter Execution (CORE-03)
        exec_res = execute_program(program, initial_state, max_steps=max_steps)
        assert exec_res.final_state == spec["expected_final_state"]

        # 4. Verify Semantic Term Evaluation Equivalence (SEM-02)
        sem_eval_res = evaluate_program_semantics(
            program, initial_state, max_steps=max_steps
        )
        assert sem_eval_res.final_state == spec["expected_final_state"]

        # 5. Verify CLI `run --json` exit code and JSON output (CORE-05)
        state_json = json.dumps(initial_state)
        exit_code = run_cli(
            [
                "run",
                str(temp_sipl),
                "--state",
                state_json,
                "--max-steps",
                str(max_steps),
                "--json",
            ]
        )
        cli_out = json.loads(capsys.readouterr().out)
        assert exit_code == expected_exit_code
        assert cli_out["status"] == "ok"
        assert cli_out["final_state"] == spec["expected_final_state"]

    elif category == "syntax_error":
        # 1. Parser must raise SIPLSyntaxError with expected kind and line
        with pytest.raises(SIPLSyntaxError) as syn_exc:
            parse_program(source)
        err = syn_exc.value
        assert err.to_dict()["error_type"] == spec["expected_error_type"]
        assert err.error_kind == spec["expected_error_kind"]
        if "expected_line" in spec:
            assert err.line == spec["expected_line"]

        # 2. CLI `check --json` must return expected_exit_code (3)
        exit_code = run_cli(["check", str(temp_sipl), "--json"])
        cli_out = json.loads(capsys.readouterr().out)
        assert exit_code == expected_exit_code
        assert cli_out["status"] == "error"
        assert cli_out["error"]["error_kind"] == spec["expected_error_kind"]

    elif category == "runtime_error":
        initial_state = spec.get("initial_state", {})
        max_steps = spec.get("max_steps", 10_000)

        program = parse_program(source)

        # 1. Interpreter must raise SIPLRuntimeError with expected kind
        with pytest.raises(SIPLRuntimeError) as rt_exc:
            execute_program(program, initial_state, max_steps=max_steps)
        rt_err = rt_exc.value
        assert rt_err.to_dict()["error_type"] == spec["expected_error_type"]
        assert rt_err.error_kind == spec["expected_error_kind"]

        # 2. CLI `run --json` must return expected_exit_code (4)
        state_json = json.dumps(initial_state)
        exit_code = run_cli(
            [
                "run",
                str(temp_sipl),
                "--state",
                state_json,
                "--max-steps",
                str(max_steps),
                "--json",
            ]
        )
        cli_out = json.loads(capsys.readouterr().out)
        assert exit_code == expected_exit_code
        assert cli_out["status"] == "error"
        assert cli_out["error"]["error_kind"] == spec["expected_error_kind"]

    else:
        pytest.fail(f"Unknown conformance category: {category!r}")
