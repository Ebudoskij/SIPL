"""Unit and golden tests for SEM-01: Automatic construction of SIPL semantic terms."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from sipl.cli import EXIT_OK, run_cli
from sipl.parser import parse_file
from sipl.semantics import (
    SemanticDerivationStep,
    build_semantic_term,
    source_to_semantic_term,
)

VALID_DIR = Path(__file__).resolve().parent.parent / "examples" / "valid"


def test_golden_example_1_1_factorial() -> None:
    """Verify exact semantic term for Practicum Example 1.1 (Factorial)."""
    prog = parse_file(VALID_DIR / "03_factorial.sipl")
    term = build_semantic_term(prog)

    expected_course = (
        "AS^S(1\u0304) · WH(S^2(gr, 'M⇒, 0\u0304), "
        "AS^S(S^2(mult, 'S⇒, 'M⇒)) · AS^M(S^2(sub, 'M⇒, 1\u0304)))"
    )
    assert str(term) == expected_course
    assert term.format("course") == expected_course

    expected_ascii = (
        "AS^S(const(1)) . WH(S^2(gr, 'M=>, const(0)), "
        "AS^S(S^2(mult, 'S=>, 'M=>)) . AS^M(S^2(sub, 'M=>, const(1))))"
    )
    assert term.format("ascii") == expected_ascii

    expected_latex = (
        r"AS^{S}(\overline{1}) \cdot WH(S^{2}(gr, \text{'M}\Rightarrow, \overline{0}), "
        r"AS^{S}(S^{2}(mult, \text{'S}\Rightarrow, \text{'M}\Rightarrow)) \cdot "
        r"AS^{M}(S^{2}(sub, \text{'M}\Rightarrow, \overline{1})))"
    )
    assert term.format("latex") == expected_latex


def test_golden_example_1_2_euclid_gcd() -> None:
    """Verify exact semantic term for Practicum Example 1.2 (Euclid's GCD)."""
    prog = parse_file(VALID_DIR / "04_gcd_euclid_canonical.sipl")
    term = build_semantic_term(prog)

    expected_course = (
        "WH(S^1(neg, S^2(eq, 'M⇒, 'N⇒)), "
        "IF(S^2(gr, 'M⇒, 'N⇒), "
        "AS^M(S^2(sub, 'M⇒, 'N⇒)), "
        "AS^N(S^2(sub, 'N⇒, 'M⇒))))"
    )
    assert term.format("course") == expected_course


def test_golden_example_1_3_primality_check() -> None:
    """Verify exact semantic term for Practicum Example 1.3 (Primality check with || and /)."""
    prog = parse_file(VALID_DIR / "06_primality_check_extensions.sipl")
    term = build_semantic_term(prog)

    expected_course = (
        "AS^I(2\u0304) · AS^R(1\u0304) · "
        "WH(S^2(or, S^2(gr, 'M⇒, S^2(mult, 'I⇒, 'I⇒)), S^2(eq, 'M⇒, S^2(mult, 'I⇒, 'I⇒))), "
        "IF(S^2(eq, S^2(mult, S^2(div, 'M⇒, 'I⇒), 'I⇒), 'M⇒), "
        "AS^R(0\u0304) · AS^I('M⇒), "
        "AS^I(S^2(add, 'I⇒, 1\u0304))))"
    )
    assert term.format("course") == expected_course


def test_golden_division_with_remainder_and_skip() -> None:
    """Verify semantic terms for division with remainder and skip statement."""
    skip_term = source_to_semantic_term("begin skip end")
    assert skip_term.format("course") == "id"
    assert skip_term.format("ascii") == "id"
    assert skip_term.format("latex") == "id"
    assert skip_term.to_dict() == {"term_type": "IdentityTerm", "notation": "id"}

    div_prog = parse_file(VALID_DIR / "05_division_with_remainder.sipl")
    div_term = build_semantic_term(div_prog)
    expected_div = (
        "AS^Q(0\u0304) · AS^R('M⇒) · "
        "WH(S^2(or, S^2(gr, 'R⇒, 'N⇒), S^2(eq, 'R⇒, 'N⇒)), "
        "AS^R(S^2(sub, 'R⇒, 'N⇒)) · AS^Q(S^2(add, 'Q⇒, 1\u0304)))"
    )
    assert div_term.format("course") == expected_div


def test_derivation_log_and_serialization() -> None:
    """Verify Table 1.1 rule derivation steps and dictionary serialization."""
    steps: list[SemanticDerivationStep] = []
    term = source_to_semantic_term(
        "begin if !(X = -1) then X := X + 1 else skip end",
        derivation_log=steps,
    )
    rule_codes = [s.rule_code for s in steps]
    assert "NA1" in rule_codes
    assert "NA2" in rule_codes
    assert "NA3" in rule_codes
    assert "NB1" in rule_codes
    assert "NB4" in rule_codes
    assert "NS1" in rule_codes
    assert "NS6" in rule_codes
    assert "NS3" in rule_codes
    assert rule_codes[-1] == "NP1"

    term_dict = term.to_dict()
    assert term_dict["term_type"] == "ConditionalTerm"
    assert term_dict["else_term"]["term_type"] == "IdentityTerm"


def test_cli_sem_subcommand(capsys: pytest.CaptureFixture[str]) -> None:
    """Verify `sipl sem` CLI subcommand in text, --derivation, and --json modes."""
    fact_path = str(VALID_DIR / "03_factorial.sipl")

    code = run_cli(["sem", fact_path, "--style", "ascii", "--derivation"])
    out = capsys.readouterr()
    assert code == EXIT_OK
    assert "=== Semantic Term Derivation (Table 1.1) ===" in out.out
    assert "AS^S(const(1))" in out.out

    code_json = run_cli(["sem", fact_path, "--derivation", "--json"])
    out_json = capsys.readouterr()
    assert code_json == EXIT_OK
    payload = json.loads(out_json.out)
    assert payload["status"] == "ok"
    assert payload["term"]["term_type"] == "SequenceTerm"
    assert len(payload["derivation"]) > 5
