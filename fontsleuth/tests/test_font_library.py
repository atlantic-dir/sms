import shutil

import pytest

from fontsleuth.errors import CancelledError
from fontsleuth.font_library import FontScanner


def test_scan_reads_family_style_weight(all_fonts):
    bold = [f for f in all_fonts if f.style == "Bold" and not f.italic]
    assert bold and all(f.weight == 700 for f in bold)
    assert all(f.family and f.style for f in all_fonts)


def test_scan_skips_damaged_fonts_and_reports_them(tmp_path, all_fonts):
    shutil.copy(all_fonts[0].path, tmp_path / "good.ttf") if all_fonts[0].path.suffix == ".ttf" else None
    (tmp_path / "broken.ttf").write_bytes(b"this is not a font")
    report = FontScanner.scan([tmp_path])
    assert [name for name, _ in report.skipped] == ["broken.ttf"]


def test_cache_is_reused_and_survives_corruption(tmp_path, all_fonts):
    source = next(f.path for f in all_fonts if f.path.suffix == ".ttf")
    shutil.copy(source, tmp_path / "a.ttf")
    cache = tmp_path / "cache" / "fonts.json"
    first = FontScanner.scan([tmp_path], cache)
    assert cache.exists()
    assert [f.key() for f in FontScanner.scan([tmp_path], cache).candidates] == [f.key() for f in first.candidates]
    cache.write_text("{not json")
    assert len(FontScanner.scan([tmp_path], cache).candidates) == len(first.candidates)


def test_scan_can_be_cancelled(tmp_path, all_fonts):
    source = next(f.path for f in all_fonts if f.path.suffix == ".ttf")
    shutil.copy(source, tmp_path / "a.ttf")
    with pytest.raises(CancelledError):
        FontScanner.scan([tmp_path], cancelled=lambda: True)


def test_duplicate_files_are_listed_once(tmp_path, all_fonts):
    source = next(f.path for f in all_fonts if f.path.suffix == ".ttf")
    for name in ("one.ttf", "two.ttf"):
        shutil.copy(source, tmp_path / name)
    families = [(f.family, f.style) for f in FontScanner.scan([tmp_path]).candidates]
    assert len(families) == len(set(families))
