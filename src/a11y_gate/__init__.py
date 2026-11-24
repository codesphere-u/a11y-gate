"""a11y-gate — WCAG 2.2 accessibility, contrast & readability CI gate."""

from a11y_gate.metrics import (
    contrast_ratio,
    flesch_kincaid_grade,
    parse_css_color,
    relative_luminance,
)
from a11y_gate.scanner import A11yFinding, A11yReport, A11ySeverity, findings_to_sarif, scan_html

__version__ = "0.1.0"

__all__ = [
    "A11yFinding",
    "A11yReport",
    "A11ySeverity",
    "__version__",
    "contrast_ratio",
    "findings_to_sarif",
    "flesch_kincaid_grade",
    "parse_css_color",
    "relative_luminance",
    "scan_html",
]
