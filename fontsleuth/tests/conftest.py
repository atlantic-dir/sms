"""Shared fixtures: installed fonts and synthetic pictures of text."""

import os
from pathlib import Path

import pytest

from fontsleuth.font_library import FontScanner

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
FONT_DIRS = [Path(p) for p in (
    "/usr/share/fonts", "~/.fonts", "C:/Windows/Fonts", "/Library/Fonts", "/System/Library/Fonts",
)]


@pytest.fixture(scope="session")
def all_fonts():
    """Every readable font face on this computer (emoji and bitmap-style symbol fonts removed)."""
    report = FontScanner.scan([p.expanduser() for p in FONT_DIRS])
    faces = [f for f in report.candidates if not any(w in f.family for w in ("Emoji", "Unifont", "Symbol"))]
    if len(faces) < 10:
        pytest.skip("Too few fonts installed to run font-matching tests.")
    return faces


@pytest.fixture(scope="session")
def weight_pairs(all_fonts):
    """Up to three families that have both an upright Regular and an upright Bold face."""
    by_family: dict[str, dict[int, object]] = {}
    for face in all_fonts:
        if not face.italic and face.axes is None and face.style in {"Regular", "Bold", "Book"}:
            by_family.setdefault(face.family, {})[700 if face.style == "Bold" else 400] = face
    pairs = [(v[400], v[700]) for v in by_family.values() if 400 in v and 700 in v]
    if not pairs:
        pytest.skip("No family with both Regular and Bold installed.")
    return pairs[:3]
