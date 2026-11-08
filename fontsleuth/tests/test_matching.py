import numpy as np
import pytest

from fontsleuth.errors import AnalysisError, CancelledError, MissingTextError
from fontsleuth.analysis import AnalysisService
from fontsleuth.font_matcher import FontMatcher
from fontsleuth.ink_analysis import InkAnalyzer
from fontsleuth.sources import PageImage
from fontsleuth.text_mask import MaskBuilder
from helpers import SAMPLE, render_line

from PIL import Image


def analyze(image, fonts, text=SAMPLE, dpi=96):
    return AnalysisService.analyze_pixels(PageImage(image, None), text, dpi, fonts)


def test_regular_and_bold_are_told_apart(all_fonts, weight_pairs):
    for regular, bold in weight_pairs:
        for face in (regular, bold):
            top = analyze(render_line(face, size=30), all_fonts).findings[0]
            assert (top.family, top.weight) == (face.family, face.weight), f"{face.family} {face.style}"


def test_size_color_and_points_are_recovered(all_fonts, weight_pairs):
    face = weight_pairs[0][0]
    result = analyze(render_line(face, size=24, ink=(180, 30, 40), bg=(255, 255, 255)), all_fonts, dpi=96)
    top = result.findings[0]
    assert top.size_px == pytest.approx(24, rel=0.03)
    assert top.size_pt == pytest.approx(18, rel=0.03)  # 24 px at 96 dpi
    assert max(abs(a - b) for a, b in zip(result.ink_color.as_tuple(), (180, 30, 40))) <= 4


def test_dpi_only_changes_points_not_font(all_fonts, weight_pairs):
    image = render_line(weight_pairs[0][0], size=24)
    a, b = analyze(image, all_fonts, dpi=72).findings[0], analyze(image, all_fonts, dpi=144).findings[0]
    assert a.family == b.family and a.size_px == b.size_px
    assert a.size_pt == pytest.approx(2 * b.size_pt, rel=0.01)


def test_light_text_on_dark_background(all_fonts, weight_pairs):
    face = weight_pairs[0][1]
    result = analyze(render_line(face, size=30, ink=(240, 240, 120), bg=(20, 30, 60)), all_fonts)
    assert result.findings[0].family == face.family
    assert result.ink_color.r > 200 and result.ink_color.b < 160


def test_survives_jpeg_and_rescaling(all_fonts, weight_pairs):
    face = weight_pairs[0][1]
    result = analyze(render_line(face, size=34, jpeg=75, scale=0.7), all_fonts)
    assert result.findings[0].family == face.family


def test_results_are_ranked_and_scores_sorted(all_fonts, weight_pairs):
    findings = analyze(render_line(weight_pairs[0][0]), all_fonts).findings
    scores = [f.score for f in findings]
    assert scores == sorted(scores, reverse=True) and len(findings) > 1


def test_near_ties_are_flagged_instead_of_hidden(all_fonts, weight_pairs):
    clone = [all_fonts[0], all_fonts[0].__class__(**{**all_fonts[0].__dict__, "style": "Copy"})]  # identical rendering
    result = analyze(render_line(all_fonts[0]), clone)
    assert result.ambiguous


def test_missing_text_is_a_distinct_error(all_fonts, weight_pairs):
    with pytest.raises(MissingTextError):
        analyze(render_line(weight_pairs[0][0]), all_fonts, text="   ")


def test_characters_no_font_has_give_a_clear_error(all_fonts, weight_pairs):
    face = weight_pairs[0][0]
    with pytest.raises(AnalysisError, match="every character"):
        analyze(render_line(face), all_fonts, text="\U0010FFFF\U0010FFFE ok")


def test_blank_picture_is_rejected():
    flat = np.full((40, 200, 3), 255, dtype=np.uint8)
    with pytest.raises(AnalysisError, match="No text"):
        InkAnalyzer.analyze(flat)


def test_two_lines_are_rejected(all_fonts, weight_pairs):
    one = render_line(weight_pairs[0][0], size=28)
    stacked = Image.new("RGB", (one.width, one.height * 2 + 10), (250, 250, 240))
    stacked.paste(one, (0, 0))
    stacked.paste(one, (0, one.height + 10))
    with pytest.raises(AnalysisError, match="more than one line"):
        analyze(stacked, all_fonts)


def test_tiny_text_is_rejected(all_fonts, weight_pairs):
    tiny = Image.new("RGB", (80, 20), (255, 255, 255))
    tiny.paste((0, 0, 0), (10, 8, 70, 12))
    with pytest.raises(AnalysisError, match="too small"):
        MaskBuilder.build(InkAnalyzer.analyze(np.asarray(tiny)).coverage)


def test_cancellation_stops_the_search(all_fonts, weight_pairs):
    mask = MaskBuilder.build(InkAnalyzer.analyze(np.asarray(render_line(weight_pairs[0][0]))).coverage)
    with pytest.raises(CancelledError):
        FontMatcher.rank(mask, SAMPLE, all_fonts, cancelled=lambda: True)


def test_no_fonts_gives_actionable_message(weight_pairs):
    with pytest.raises(AnalysisError, match="No fonts"):
        analyze(render_line(weight_pairs[0][0]), [])


def test_background_that_is_not_solid_is_reported(all_fonts, weight_pairs):
    image = render_line(weight_pairs[0][1], size=30, bg=(255, 255, 255))
    gradient = np.asarray(image).astype(float)
    gradient *= np.linspace(0.45, 1.0, gradient.shape[1])[None, :, None]
    result = analyze(Image.fromarray(gradient.astype(np.uint8)), all_fonts)
    assert any("not a single solid colour" in w for w in result.warnings)


def test_enormous_selection_gets_a_clear_message(all_fonts, tmp_path):
    from fontsleuth.sources import ImageSource
    path = tmp_path / "huge.png"
    Image.new("RGB", (4200, 3000), (255, 255, 255)).save(path)
    with pytest.raises(AnalysisError, match="very large"):
        AnalysisService.analyze(ImageSource(path), 0, (0, 0, 4200, 3000), "x", 96, all_fonts)


def test_thin_small_text_warns_that_colour_is_uncertain(all_fonts, weight_pairs):
    result = analyze(render_line(weight_pairs[0][0], size=12, ink=(180, 30, 40), bg=(255, 255, 255)), all_fonts)
    assert any("strokes are thin" in w for w in result.warnings)


def test_large_bold_text_does_not_get_the_thin_stroke_warning(all_fonts, weight_pairs):
    result = analyze(render_line(weight_pairs[0][1], size=48, ink=(180, 30, 40), bg=(255, 255, 255)), all_fonts)
    assert not any("strokes are thin" in w for w in result.warnings)
