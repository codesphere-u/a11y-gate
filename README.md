# a11y-gate

**Deterministic static HTML/CSS WCAG 2.2 accessibility, relative-luminance contrast ratio, keyboard-navigation, and Flesch-Kincaid plain-language readability CI gate with SARIF v2.1.0 output.**

Zero runtime dependencies. Pure Python 3.11+. Built to catch screen-reader, low-vision, keyboard-trap, and reading-complexity barriers in CI before web portals ship.

## Quick Start

```bash
uv sync --extra dev
a11y-gate contrast "#595959" "#ffffff"
a11y-gate scan ./dist --format sarif > a11y.sarif
```

## License

MIT License — see [LICENSE](LICENSE).
