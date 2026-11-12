"""Integration tests for CORE-05: SIPL Command-Line Interface (CLI)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from sipl.cli import (
    EXIT_CLI_USAGE_ERROR,
    EXIT_OK,
    EXIT_RUNTIME_ERROR,
    EXIT_SYNTAX_ERROR,
    parse_state_args,
    run_cli,
)

EXAMPLES_DIR = Path(__file__).resolve().parent.parent / "examples"
VALID_DIR = EXAMPLES_DIR / "valid"
INVALID_DIR = EXAMPLES_DIR / "invalid"


def test_parse_state_args_formats_and_errors() -> None:
    """Verify --state parser supports KEY=VAL, comma-separated, and JSON objects."""
    assert parse_state_args(None) == {}
    assert parse_state_args([]) == {}
    assert parse_state_args(["M=5", "N=-2"]) == {"M": 5, "N": -2}
    assert parse_state_args(["M=10,N=20"]) == {"M": 10, "N": 20}
    assert parse_state_args(['{"M": 48, "N": 18}']) == {"M": 48, "N": 18}

    with pytest.raises(ValueError, match="Invalid JSON"):
        parse_state_args(["{bad_json}"])

    with pytest.raises(ValueError, match="must be an object"):
        parse_state_args(["[1, 2]"])

    with pytest.raises(ValueError, match="expected integer value"):
        parse_state_args(['{"M": true}'])

    with pytest.raises(ValueError, match="expected format VAR=INT"):
        parse_state_args(["M_WITHOUT_EQUALS"])

    with pytest.raises(ValueError, match="Empty variable name"):
        parse_state_args(["=5"])

    with pytest.raises(ValueError, match="Invalid integer value"):
        parse_state_args(["M=abc"])


def test_cli_check_valid_and_invalid_programs(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Verify `sipl check` in text and --json modes with stable exit codes."""
    valid_path = str(VALID_DIR / "03_factorial.sipl")
    invalid_path = str(INVALID_DIR / "03_if_without_else.sipl")

    # 1. Valid text mode
    code = run_cli(["check", valid_path])
    out = capsys.readouterr()
    assert code == EXIT_OK
    assert "is syntactically valid" in out.out

    # 2. Valid JSON mode
    code_json = run_cli(["check", valid_path, "--json"])
    out_json = capsys.readouterr()
    assert code_json == EXIT_OK
    payload = json.loads(out_json.out)
    assert payload["status"] == "ok"
    assert payload["valid"] is True

    # 3. Invalid text mode
    code_err = run_cli(["check", invalid_path])
    out_err = capsys.readouterr()
    assert code_err == EXIT_SYNTAX_ERROR
    assert "SyntaxError" in out_err.err

    # 4. Invalid JSON mode
    code_err_json = run_cli(["check", invalid_path, "--json"])
    out_err_json = capsys.readouterr()
    assert code_err_json == EXIT_SYNTAX_ERROR
    err_payload = json.loads(out_err_json.out)
    assert err_payload["status"] == "error"
    assert err_payload["valid"] is False
    assert err_payload["error"]["error_type"] == "SIPLSyntaxError"


def test_cli_parse_text_and_json(capsys: pytest.CaptureFixture[str]) -> None:
    """Verify `sipl parse` outputs readable AST text and structured JSON."""
    file_path = str(VALID_DIR / "10_combined_logical_and_arith.sipl")

    code = run_cli(["parse", file_path])
    out = capsys.readouterr()
    assert code == EXIT_OK
    assert "Program" in out.out
    assert "IfStmt" in out.out
    assert "OrCond" in out.out
    assert "NotCond" in out.out
    assert "BinaryArithExpr" in out.out
    assert "SkipStmt" in out.out

    # Also test WhileStmt and BlockStmt formatting
    fact_path = str(VALID_DIR / "03_factorial.sipl")
    code_fact = run_cli(["parse", fact_path])
    out_fact = capsys.readouterr()
    assert code_fact == EXIT_OK
    assert "WhileStmt" in out_fact.out
    assert "BlockStmt" in out_fact.out

    # JSON mode
    code_json = run_cli(["parse", fact_path, "--json"])
    out_json = capsys.readouterr()
    assert code_json == EXIT_OK
    payload = json.loads(out_json.out)
    assert payload["status"] == "ok"
    assert payload["ast"]["type"] == "Program"


def test_cli_run_success_and_runtime_errors(
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    """Verify `sipl run` with initial state, JSON mode, and runtime error exit codes."""
    gcd_path = str(VALID_DIR / "04_gcd_euclid_canonical.sipl")

    # Text mode
    code = run_cli(["run", gcd_path, "--state", "M=48", "N=18"])
    out = capsys.readouterr()
    assert code == EXIT_OK
    assert "Final state:    {'M': 6, 'N': 6}" in out.out

    # JSON mode
    code_json = run_cli(["run", gcd_path, "--state", '{"M": 48, "N": 18}', "--json"])
    out_json = capsys.readouterr()
    assert code_json == EXIT_OK
    payload = json.loads(out_json.out)
    assert payload["status"] == "ok"
    assert payload["final_state"] == {"M": 6, "N": 6}

    # Runtime error: Uninitialized variable (M not provided)
    code_rt_err = run_cli(["run", gcd_path])
    out_rt_err = capsys.readouterr()
    assert code_rt_err == EXIT_RUNTIME_ERROR
    assert "UninitializedVariableError" in out_rt_err.err

    # Runtime error in JSON mode
    code_rt_json = run_cli(["run", gcd_path, "--json"])
    out_rt_json = capsys.readouterr()
    assert code_rt_json == EXIT_RUNTIME_ERROR
    err_payload = json.loads(out_rt_json.out)
    assert err_payload["status"] == "error"
    assert err_payload["error"]["error_kind"] == "UninitializedVariableError"

    # Infinite loop step limit error
    inf_file = tmp_path / "inf.sipl"
    inf_file.write_text("begin while 1 = 1 do skip end", encoding="utf-8")
    code_inf = run_cli(["run", str(inf_file), "--max-steps", "10", "--json"])
    out_inf = capsys.readouterr()
    assert code_inf == EXIT_RUNTIME_ERROR
    inf_payload = json.loads(out_inf.out)
    assert inf_payload["error"]["error_kind"] == "StepLimitExceededError"


def test_cli_trace_success_and_error(
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    """Verify `sipl trace` in text and JSON modes for both normal and error runs."""
    fact_path = str(VALID_DIR / "03_factorial.sipl")

    # Text mode
    code = run_cli(["trace", fact_path, "--state", "M=3"])
    out = capsys.readouterr()
    assert code == EXIT_OK
    assert "=== SIPL Execution Trace" in out.out
    assert "Final state:   {'M': 0, 'S': 6}" in out.out

    # JSON mode
    code_json = run_cli(["trace", fact_path, "--state", "M=3", "--json"])
    out_json = capsys.readouterr()
    assert code_json == EXIT_OK
    payload = json.loads(out_json.out)
    assert payload["status"] == "ok"
    assert payload["trace"]["final_state"] == {"M": 0, "S": 6}
    assert payload["trace"]["terminated_normally"] is True

    # Trace on division by zero error
    div0_file = tmp_path / "div0.sipl"
    div0_file.write_text("begin X := 5; Y := X / 0 end", encoding="utf-8")

    code_err = run_cli(["trace", str(div0_file), "--json"])
    out_err = capsys.readouterr()
    assert code_err == EXIT_RUNTIME_ERROR
    err_payload = json.loads(out_err.out)
    assert err_payload["status"] == "error"
    assert err_payload["trace"]["terminated_normally"] is False
    assert err_payload["error"]["error_kind"] == "DivisionByZeroError"

    code_err_txt = run_cli(["trace", str(div0_file)])
    out_err_txt = capsys.readouterr()
    assert code_err_txt == EXIT_RUNTIME_ERROR
    assert "DivisionByZeroError" in out_err_txt.err


def test_cli_usage_errors(capsys: pytest.CaptureFixture[str]) -> None:
    """Verify missing files and invalid CLI flags return EXIT_CLI_USAGE_ERROR (2)."""
    fact_path = str(VALID_DIR / "03_factorial.sipl")

    # Missing file
    assert run_cli(["check", "non_existent_file.sipl"]) == EXIT_CLI_USAGE_ERROR
    capsys.readouterr()

    assert run_cli(["check", "non_existent_file.sipl", "--json"]) == EXIT_CLI_USAGE_ERROR
    out_nf = json.loads(capsys.readouterr().out)
    assert out_nf["error"]["error_type"] == "FileNotFoundError"

    # Invalid --max-steps
    assert run_cli(["run", fact_path, "--max-steps", "0"]) == EXIT_CLI_USAGE_ERROR
    capsys.readouterr()
    assert run_cli(["run", fact_path, "--max-steps", "0", "--json"]) == EXIT_CLI_USAGE_ERROR
    capsys.readouterr()

    # Invalid --state
    assert run_cli(["run", fact_path, "--state", "BAD"]) == EXIT_CLI_USAGE_ERROR
    capsys.readouterr()
    assert run_cli(["run", fact_path, "--state", "BAD", "--json"]) == EXIT_CLI_USAGE_ERROR
    capsys.readouterr()
