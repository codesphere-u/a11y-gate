"""Static HTML/CSS WCAG 2.2 accessibility, keyboard-navigation & readability scanner."""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum
from html.parser import HTMLParser
from typing import Any

from a11y_gate.metrics import contrast_ratio, flesch_kincaid_grade, parse_css_color

_STYLE_PROP_RE = re.compile(r"([a-zA-Z-]+)\s*:\s*([^;]+)")
_OUTLINE_NONE_RE = re.compile(r"(?i)outline\s*:\s*(?:none|0(?:px)?)\b")


class A11ySeverity(StrEnum):
    ERROR = "error"
    WARNING = "warning"


@dataclass(frozen=True)
class A11yFinding:
    rule_id: str
    severity: A11ySeverity
    wcag: str
    line: int
    message: str
    remediation: str
    uri: str = "index.html"


@dataclass(frozen=True)
class A11yReport:
    uri: str
    passed: bool
    error_count: int
    warning_count: int
    readability_grade: float
    word_count: int
    findings: tuple[A11yFinding, ...]


def _parse_inline_style(style: str) -> dict[str, str]:
    return {m.group(1).strip().lower(): m.group(2).strip() for m in _STYLE_PROP_RE.finditer(style)}


class _HtmlA11yParser(HTMLParser):
    def __init__(self, uri: str) -> None:
        super().__init__(convert_charrefs=True)
        self.uri = uri
        self.findings: list[A11yFinding] = []
        self.has_html_tag = False
        self.has_html_lang = False
        self.label_for_ids: set[str] = set()
        self.controls: list[tuple[int, str, dict[str, str | None]]] = []
        self.in_label_depth = 0
        self.in_non_visible_depth = 0
        self.headings: list[tuple[int, int]] = []
        self.visible_text_chunks: list[str] = []
        self.style_blocks: list[tuple[int, str]] = []
        self._capturing_style_line: int | None = None
        self._style_buf: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        t = tag.lower()
        line = self.getpos()[0]
        attr_map: dict[str, str | None] = {k.lower(): v for k, v in attrs}

        if t == "html":
            self.has_html_tag = True
            if (attr_map.get("lang") or "").strip():
                self.has_html_lang = True

        if t in ("script", "style", "noscript"):
            self.in_non_visible_depth += 1
            if t == "style":
                self._capturing_style_line = line
                self._style_buf = []

        if t == "label":
            self.in_label_depth += 1
            target = (attr_map.get("for") or "").strip()
            if target:
                self.label_for_ids.add(target)

        if t == "img" and "alt" not in attr_map:
            self.findings.append(
                A11yFinding(
                    rule_id="A11Y-002",
                    severity=A11ySeverity.ERROR,
                    wcag="1.1.1 Non-text Content (A)",
                    line=line,
                    message="<img> element is missing an alt attribute.",
                    remediation='Provide descriptive alt text or alt="" for purely decorative images.',
                    uri=self.uri,
                )
            )

        if t in ("input", "select", "textarea"):
            input_type = (attr_map.get("type") or "text").lower()
            if input_type not in ("hidden", "submit", "button", "reset", "image") and self.in_label_depth == 0:
                self.controls.append((line, t, attr_map))

        if len(t) == 2 and t[0] == "h" and t[1] in "123456":
            self.headings.append((line, int(t[1])))

        if "tabindex" in attr_map:
            raw_ti = (attr_map.get("tabindex") or "").strip()
            if raw_ti.lstrip("+-").isdigit() and int(raw_ti) > 0:
                self.findings.append(
                    A11yFinding(
                        rule_id="A11Y-005",
                        severity=A11ySeverity.ERROR,
                        wcag="2.4.3 Focus Order (A)",
                        line=line,
                        message=f"Positive tabindex='{raw_ti}' on <{t}> disrupts natural keyboard focus order.",
                        remediation='Use tabindex="0" or semantic DOM order instead of positive tabindex values.',
                        uri=self.uri,
                    )
                )

        if t in ("div", "span") and "onclick" in attr_map:
            has_role = bool((attr_map.get("role") or "").strip())
            has_tab = (attr_map.get("tabindex") or "").strip() == "0"
            if not (has_role and has_tab):
                self.findings.append(
                    A11yFinding(
                        rule_id="A11Y-006",
                        severity=A11ySeverity.ERROR,
                        wcag="2.1.1 Keyboard (A)",
                        line=line,
                        message=f"Clickable <{t} onclick> is inaccessible to keyboard and screen-reader users.",
                        remediation='Use a native <button type="button"> or add role="button" and tabindex="0".',
                        uri=self.uri,
                    )
                )

        style = attr_map.get("style") or ""
        if style:
            if _OUTLINE_NONE_RE.search(style):
                self.findings.append(
                    A11yFinding(
                        rule_id="A11Y-008",
                        severity=A11ySeverity.ERROR,
                        wcag="2.4.7 Focus Visible (AA)",
                        line=line,
                        message=f"Inline CSS on <{t}> removes focus outline without a visible focus indicator.",
                        remediation="Preserve :focus-visible outlines or provide a high-contrast custom focus ring.",
                        uri=self.uri,
                    )
                )
            props = _parse_inline_style(style)
            fg = props.get("color")
            bg = props.get("background-color") or props.get("background")
            if fg and bg and parse_css_color(fg) and parse_css_color(bg):
                ratio = contrast_ratio(fg, bg)
                if ratio < 4.5:
                    self.findings.append(
                        A11yFinding(
                            rule_id="A11Y-007",
                            severity=A11ySeverity.ERROR,
                            wcag="1.4.3 Contrast Minimum (AA)",
                            line=line,
                            message=(
                                f"Low contrast ratio {ratio}:1 on <{t}> ({fg} on {bg}); "
                                "WCAG 2.2 AA requires >= 4.5:1."
                            ),
                            remediation="Darken foreground or lighten background to achieve at least 4.5:1 contrast.",
                            uri=self.uri,
                        )
                    )

    def handle_endtag(self, tag: str) -> None:
        t = tag.lower()
        if t == "label" and self.in_label_depth > 0:
            self.in_label_depth -= 1
        if t in ("script", "style", "noscript") and self.in_non_visible_depth > 0:
            self.in_non_visible_depth -= 1
            if t == "style" and self._capturing_style_line is not None:
                self.style_blocks.append((self._capturing_style_line, "".join(self._style_buf)))
                self._capturing_style_line = None
                self._style_buf = []

    def handle_data(self, data: str) -> None:
        if self._capturing_style_line is not None:
            self._style_buf.append(data)
        elif self.in_non_visible_depth == 0:
            stripped = data.strip()
            if stripped:
                self.visible_text_chunks.append(stripped)


def scan_html(
    html_text: str,
    *,
    uri: str = "index.html",
    max_grade_level: float = 11.0,
) -> A11yReport:
    """Scan an HTML document for WCAG 2.2 accessibility, contrast, keyboard & readability issues."""
    parser = _HtmlA11yParser(uri)
    parser.feed(html_text)
    findings = list(parser.findings)

    if parser.has_html_tag and not parser.has_html_lang:
        findings.append(
            A11yFinding(
                rule_id="A11Y-001",
                severity=A11ySeverity.ERROR,
                wcag="3.1.1 Language of Page (A)",
                line=1,
                message="<html> element is missing a non-empty lang attribute.",
                remediation='Add a BCP-47 language code such as <html lang="en"> or <html lang="sw">.',
                uri=uri,
            )
        )

    for line, tag, attr_map in parser.controls:
        ctrl_id = (attr_map.get("id") or "").strip()
        has_aria = bool((attr_map.get("aria-label") or "").strip() or (attr_map.get("aria-labelledby") or "").strip())
        if not has_aria and (not ctrl_id or ctrl_id not in parser.label_for_ids):
            findings.append(
                A11yFinding(
                    rule_id="A11Y-003",
                    severity=A11ySeverity.ERROR,
                    wcag="1.3.1 / 3.3.2 Labels or Instructions (A)",
                    line=line,
                    message=f"Form control <{tag}> has no associated <label for> or aria-label.",
                    remediation="Associate an explicit <label for='...'> or wrap the control inside <label>.",
                    uri=uri,
                )
            )

    prev_level = 0
    for line, level in parser.headings:
        if prev_level > 0 and level > prev_level + 1:
            findings.append(
                A11yFinding(
                    rule_id="A11Y-004",
                    severity=A11ySeverity.WARNING,
                    wcag="1.3.1 Info and Relationships (A)",
                    line=line,
                    message=f"Heading level skipped from <h{prev_level}> directly to <h{level}>.",
                    remediation="Use sequential heading levels without skipping tiers.",
                    uri=uri,
                )
            )
        prev_level = level

    for style_line, css_text in parser.style_blocks:
        if _OUTLINE_NONE_RE.search(css_text):
            findings.append(
                A11yFinding(
                    rule_id="A11Y-008",
                    severity=A11ySeverity.ERROR,
                    wcag="2.4.7 Focus Visible (AA)",
                    line=style_line,
                    message="<style> contains 'outline: none' / 'outline: 0', removing keyboard focus indicators.",
                    remediation="Preserve focus outlines or provide a high-contrast :focus-visible replacement.",
                    uri=uri,
                )
            )

    visible_text = " ".join(parser.visible_text_chunks)
    grade, _ease, word_count = flesch_kincaid_grade(visible_text)
    if word_count >= 20 and grade > max_grade_level:
        findings.append(
            A11yFinding(
                rule_id="A11Y-009",
                severity=A11ySeverity.WARNING,
                wcag="3.1.5 Reading Level (AAA)",
                line=1,
                message=(
                    f"Page copy Flesch-Kincaid grade level is {grade:.1f} "
                    f"(exceeds plain-language target <= {max_grade_level:.1f})."
                ),
                remediation="Shorten sentences and simplify jargon for low-literacy and assistive-tech readers.",
                uri=uri,
            )
        )

    errors = sum(1 for f in findings if f.severity == A11ySeverity.ERROR)
    warnings = sum(1 for f in findings if f.severity == A11ySeverity.WARNING)
    return A11yReport(
        uri=uri,
        passed=(errors == 0),
        error_count=errors,
        warning_count=warnings,
        readability_grade=grade,
        word_count=word_count,
        findings=tuple(findings),
    )


def findings_to_sarif(findings: tuple[A11yFinding, ...] | list[A11yFinding]) -> dict[str, Any]:
    rules: dict[str, dict[str, Any]] = {}
    results: list[dict[str, Any]] = []
    for f in findings:
        if f.rule_id not in rules:
            rules[f.rule_id] = {
                "id": f.rule_id,
                "shortDescription": {"text": f.wcag},
                "help": {"text": f.remediation},
            }
        results.append(
            {
                "ruleId": f.rule_id,
                "level": f.severity.value,
                "message": {"text": f"{f.message} ({f.wcag})"},
                "locations": [
                    {
                        "physicalLocation": {
                            "artifactLocation": {"uri": f.uri},
                            "region": {"startLine": max(1, f.line)},
                        }
                    }
                ],
            }
        )
    return {
        "$schema": "https://json.schemastore.org/sarif-2.1.0.json",
        "version": "2.1.0",
        "runs": [
            {
                "tool": {
                    "driver": {
                        "name": "a11y-gate",
                        "version": "0.1.0",
                        "informationUri": "https://github.com/codesphere-u/a11y-gate",
                        "rules": list(rules.values()),
                    }
                },
                "results": results,
            }
        ],
    }
