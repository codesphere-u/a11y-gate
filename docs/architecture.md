# Architecture — `a11y-gate`

- `a11y_gate.metrics`: W3C WCAG 2.2 sRGB linearization, relative luminance, contrast ratio (`1.0:1` to `21.0:1`), and Flesch-Kincaid reading grade/ease formulas.
- `a11y_gate.scanner`: Stdlib `HTMLParser` static auditor covering rules `A11Y-001`..`A11Y-009` plus SARIF v2.1.0 serialization.
- `a11y_gate.cli`: CI exit-code CLI (`scan`, `contrast`).
