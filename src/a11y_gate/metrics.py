"""WCAG 2.2 relative-luminance contrast ratio & Flesch-Kincaid readability math."""

from __future__ import annotations

import re

_NAMED_COLORS: dict[str, tuple[int, int, int]] = {
    "black": (0, 0, 0),
    "white": (255, 255, 255),
    "red": (255, 0, 0),
    "green": (0, 128, 0),
    "blue": (0, 0, 255),
    "yellow": (255, 255, 0),
    "gray": (128, 128, 128),
    "grey": (128, 128, 128),
    "silver": (192, 192, 192),
    "navy": (0, 0, 128),
}

_RGB_RE = re.compile(r"^rgba?\(\s*(\d{1,3})\s*,\s*(\d{1,3})\s*,\s*(\d{1,3})")


def parse_css_color(raw: str) -> tuple[int, int, int] | None:
    """Parse #RGB, #RRGGBB, rgb(r,g,b), or basic CSS named colors into an (R, G, B) tuple."""
    s = raw.strip().lower()
    if s in _NAMED_COLORS:
        return _NAMED_COLORS[s]
    if s.startswith("#"):
        hex_part = s[1:]
        if len(hex_part) == 3 and all(c in "0123456789abcdef" for c in hex_part):
            return (int(hex_part[0] * 2, 16), int(hex_part[1] * 2, 16), int(hex_part[2] * 2, 16))
        if len(hex_part) == 6 and all(c in "0123456789abcdef" for c in hex_part):
            return (int(hex_part[0:2], 16), int(hex_part[2:4], 16), int(hex_part[4:6], 16))
    if m := _RGB_RE.match(s):
        r, g, b = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if 0 <= r <= 255 and 0 <= g <= 255 and 0 <= b <= 255:
            return (r, g, b)
    return None


def _linearize(channel_8bit: int) -> float:
    c = channel_8bit / 255.0
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def relative_luminance(rgb: tuple[int, int, int]) -> float:
    """Compute W3C WCAG 2.2 relative luminance L in [0.0, 1.0]."""
    r, g, b = rgb
    return 0.2126 * _linearize(r) + 0.7152 * _linearize(g) + 0.0722 * _linearize(b)


def contrast_ratio(fg: str, bg: str) -> float:
    """Compute exact WCAG 2.2 contrast ratio in [1.0, 21.0] for two CSS color strings."""
    rgb1 = parse_css_color(fg)
    rgb2 = parse_css_color(bg)
    if rgb1 is None or rgb2 is None:
        raise ValueError(f"Unsupported CSS color string: fg={fg!r}, bg={bg!r}")
    l1 = relative_luminance(rgb1)
    l2 = relative_luminance(rgb2)
    hi, lo = max(l1, l2), min(l1, l2)
    return round((hi + 0.05) / (lo + 0.05), 2)


def _count_syllables(word: str) -> int:
    cleaned = re.sub(r"[^a-z]", "", word.lower())
    if not cleaned:
        return 0
    if len(cleaned) <= 3:
        return 1
    cleaned = re.sub(r"(?:es|ed|e)$", "", cleaned)
    groups = re.findall(r"[aeiouy]+", cleaned)
    return max(1, len(groups))


def flesch_kincaid_grade(text: str) -> tuple[float, float, int]:
    """Return (grade_level, reading_ease, word_count) for plain-language accessibility checks."""
    words = re.findall(r"[A-Za-z]+(?:'[A-Za-z]+)?", text)
    if len(words) < 20:
        return 0.0, 100.0, len(words)
    sentences = [s for s in re.split(r"[.!?]+", text) if s.strip()]
    sent_count = max(1, len(sentences))
    syllables = sum(_count_syllables(w) for w in words)
    wps = len(words) / sent_count
    spw = syllables / len(words)
    grade = max(0.0, round(0.39 * wps + 11.8 * spw - 15.59, 2))
    ease = round(206.835 - 1.015 * wps - 84.6 * spw, 2)
    return grade, ease, len(words)
