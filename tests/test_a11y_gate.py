"""Tests for WCAG 2.2 contrast ratio, Flesch-Kincaid readability, HTML scanner, SARIF & CLI."""

from __future__ import annotations

from pathlib import Path

from a11y_gate import contrast_ratio, findings_to_sarif, flesch_kincaid_grade, scan_html
from a11y_gate.cli import main as cli_main


def test_wcag_contrast_math_matches_w3c_reference_values() -> None:
    assert contrast_ratio("#000000", "#ffffff") == 21.0
    assert contrast_ratio("#777777", "#ffffff") < 4.5
    assert contrast_ratio("#595959", "#ffffff") >= 7.0
    assert contrast_ratio("rgb(0, 0, 0)", "white") == 21.0


def test_scanner_passes_accessible_page_and_catches_wcag_violations() -> None:
    good_html = """<!doctype html>
    <html lang="en"><body>
      <h1>Clinic Appointments</h1>
      <h2>Book a Visit</h2>
      <img src="clinic.png" alt="Front entrance of health center">
      <label for="phone">Phone number</label>
      <input id="phone" type="tel">
      <button type="button" style="color: #111111; background-color: #ffffff">Submit</button>
    </body></html>"""
    ok = scan_html(good_html)
    assert ok.passed is True
    assert ok.findings == ()

    bad_html = """<!doctype html>
    <html><head><style>button:focus { outline: none; }</style></head><body>
      <h1>Title</h1>
      <h3>Skipped h2</h3>
      <img src="banner.png">
      <input type="text">
      <div onclick="go()">Fake button</div>
      <a href="/x" tabindex="5">Bad order</a>
      <p style="color: #aaaaaa; background-color: #ffffff">Low contrast text.</p>
    </body></html>"""
    bad = scan_html(bad_html)
    assert bad.passed is False
    rules = {f.rule_id for f in bad.findings}
    expected = {
        "A11Y-001", "A11Y-002", "A11Y-003", "A11Y-004",
        "A11Y-005", "A11Y-006", "A11Y-007", "A11Y-008",
    }
    assert expected.issubset(rules)
    sarif = findings_to_sarif(bad.findings)
    assert sarif["version"] == "2.1.0"
    assert len(sarif["runs"][0]["results"]) >= 8


def test_readability_and_cli(tmp_path: Path) -> None:
    dense = (
        "Notwithstanding the aforementioned multidimensional administrative contingencies, "
        "interdepartmental infrastructural harmonization necessitates comprehensive longitudinal "
        "recalibration of institutional accountability paradigms across decentralized municipalities. "
    ) * 2
    grade, _ease, words = flesch_kincaid_grade(dense)
    assert words >= 20 and grade > 12.0

    assert cli_main(["contrast", "#000", "#fff"]) == 0
    assert cli_main(["contrast", "#aaa", "#fff"]) == 2

    page = tmp_path / "index.html"
    page.write_text("<html lang='en'><body><h1>Hello</h1></body></html>", encoding="utf-8")
    assert cli_main(["scan", str(page), "--format", "sarif"]) == 0
