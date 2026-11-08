import pytest

from fontsleuth.weights import WeightNames


@pytest.mark.parametrize("text,expected", [
    ("Bold", 700), ("Arial-BoldMT", 700), ("Semibold Italic", 600), ("SemiBold", 600), ("ExtraBold", 800),
    ("Extra Light", 200), ("UltraLight", 200), ("Light", 300), ("Black", 900), ("Heavy", 900), ("Medium", 500),
    ("Thin", 100), ("Regular", 400), ("Book", 400), ("Helvetica", None),
])
def test_weight_words(text, expected):
    assert WeightNames.from_text(text) == expected


@pytest.mark.parametrize("raw,family,style", [
    ("ABCDEF+Calibri-Bold", "Calibri", "Bold"),
    ("Arial-BoldItalicMT", "Arial", "Bold Italic"),
    ("TimesNewRomanPS-BoldMT", "Times New Roman", "Bold"),
    ("Helvetica", "Helvetica", ""),
    ("Times-Bold", "Times", "Bold"),
])
def test_pdf_name_split(raw, family, style):
    assert WeightNames.split_pdf_name(raw) == (family, style)


def test_labels_and_italic():
    assert WeightNames.label(700) == "Bold" and WeightNames.label(640) == "Semibold" and WeightNames.label(5000) == "Black"
    assert WeightNames.is_italic("Light Oblique") and not WeightNames.is_italic("Bold")
