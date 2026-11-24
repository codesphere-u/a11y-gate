"""CLI for a11y-gate."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path

from a11y_gate.metrics import contrast_ratio
from a11y_gate.scanner import A11yFinding, findings_to_sarif, scan_html


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="a11y-gate",
        description="Static HTML/CSS WCAG 2.2 accessibility, contrast & readability CI gate.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_scan = sub.add_parser("scan", help="Scan an HTML file or directory")
    p_scan.add_argument("target", help="HTML file or directory containing .html files")
    p_scan.add_argument("--max-grade", type=float, default=11.0)
    p_scan.add_argument("--format", choices=["json", "sarif"], default="json")

    p_contrast = sub.add_parser("contrast", help="Compute WCAG 2.2 contrast ratio for two CSS colors")
    p_contrast.add_argument("fg")
    p_contrast.add_argument("bg")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "contrast":
        ratio = contrast_ratio(args.fg, args.bg)
        print(
            json.dumps(
                {
                    "fg": args.fg,
                    "bg": args.bg,
                    "ratio": ratio,
                    "wcag_aa_normal": ratio >= 4.5,
                    "wcag_aa_large": ratio >= 3.0,
                    "wcag_aaa_normal": ratio >= 7.0,
                },
                indent=2,
            )
        )
        return 0 if ratio >= 4.5 else 2

    if args.command == "scan":
        target = Path(args.target)
        files = [target] if target.is_file() else sorted(target.rglob("*.html"))
        all_findings: list[A11yFinding] = []
        any_failed = False
        for fp in files:
            rep = scan_html(fp.read_text(encoding="utf-8"), uri=str(fp), max_grade_level=args.max_grade)
            all_findings.extend(rep.findings)
            if not rep.passed:
                any_failed = True

        if args.format == "sarif":
            print(json.dumps(findings_to_sarif(all_findings), indent=2))
        else:
            print(
                json.dumps(
                    {
                        "files_scanned": len(files),
                        "passed": not any_failed,
                        "findings": [
                            {
                                "rule_id": f.rule_id,
                                "severity": f.severity.value,
                                "wcag": f.wcag,
                                "uri": f.uri,
                                "line": f.line,
                                "message": f.message,
                            }
                            for f in all_findings
                        ],
                    },
                    indent=2,
                )
            )
        return 0 if not any_failed else 2
    return 1


if __name__ == "__main__":
    sys.exit(main())
