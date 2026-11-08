import io

import pymupdf
import pytest
from PIL import Image

from fontsleuth.analysis import AnalysisService
from fontsleuth.errors import AnalysisError, MissingTextError, SourceError
from fontsleuth.sources import ImageSource, PdfSource, SourceFactory
from helpers import SAMPLE, render_line

DISPLAY = PdfSource.DISPLAY_DPI / 72.0  # display pixels per PDF point


def px(*points):
    """Converts PDF points to the displayed-page pixels the app uses for selections."""
    return tuple(int(round(p * DISPLAY)) for p in points)


@pytest.fixture
def styled_pdf(tmp_path):
    doc = pymupdf.open()
    page = doc.new_page(width=400, height=300)
    page.insert_text((50, 60), "Heading in Times Bold", fontname="tibo", fontsize=20, color=(0.8, 0.1, 0.1))
    page.insert_text((50, 100), "Body text in Helvetica", fontname="helv", fontsize=11, color=(0.1, 0.2, 0.6))
    page.insert_text((50, 140), "Hidden OCR layer text", fontname="helv", fontsize=12, render_mode=3)
    path = tmp_path / "styled.pdf"
    doc.save(path)
    return path


def test_pdf_text_is_read_exactly(styled_pdf):
    source = SourceFactory.open(styled_pdf)
    finding, = source.embedded_styles(0, px(45, 40, 250, 66))
    assert (finding.family, finding.weight, finding.size_pt) == ("Times", 700, 20.0)
    assert finding.color.hex() == "#CC1A1A"
    body, = source.embedded_styles(0, px(45, 88, 250, 106))
    assert (body.family, body.weight, body.size_pt, body.color.hex()) == ("Helvetica", 400, 11.0, "#1A3399")


def test_hidden_ocr_text_is_ignored(styled_pdf):
    assert SourceFactory.open(styled_pdf).embedded_styles(0, px(45, 125, 250, 146)) == []


def test_selection_covering_two_styles_lists_both(styled_pdf):
    findings = SourceFactory.open(styled_pdf).embedded_styles(0, px(40, 30, 300, 110))
    assert {f.family for f in findings} == {"Times", "Helvetica"}


def test_selection_touching_only_an_edge_of_a_neighbour_line_is_ignored(styled_pdf):
    findings = SourceFactory.open(styled_pdf).embedded_styles(0, px(45, 86, 250, 106))
    assert [f.family for f in findings] == ["Helvetica"]


def test_rotated_page_selection_maps_correctly(tmp_path):
    doc = pymupdf.open()
    page = doc.new_page(width=400, height=300)
    page.insert_text((50, 60), "Rotated page text", fontname="tibo", fontsize=18)
    page.set_rotation(90)
    path = tmp_path / "rot.pdf"
    doc.save(path)
    source = PdfSource(path)
    shown = source.render_page(0)
    assert shown.image.size[0] < shown.image.size[1]  # portrait after rotation
    area = pymupdf.Rect(45, 40, 200, 70) * page.rotation_matrix
    rect = tuple(int(v * DISPLAY) for v in (area.x0, area.y0, area.x1, area.y1))
    assert [f.size_pt for f in source.embedded_styles(0, rect)] == [18.0]


def test_pdf_without_text_falls_back_to_pixels(tmp_path, all_fonts, weight_pairs):
    face = weight_pairs[0][1]
    picture = render_line(face, size=40, ink=(10, 80, 20), bg=(255, 255, 255))
    buffer = io.BytesIO()
    picture.save(buffer, "PNG")
    doc = pymupdf.open()
    page = doc.new_page(width=500, height=200)
    page.insert_image(pymupdf.Rect(20, 20, 20 + picture.width * 0.5, 20 + picture.height * 0.5), stream=buffer.getvalue())
    path = tmp_path / "scan.pdf"
    doc.save(path)
    source = PdfSource(path)
    rect = px(10, 10, 20 + picture.width * 0.5 + 10, 20 + picture.height * 0.5 + 10)
    result = AnalysisService.analyze(source, 0, rect, SAMPLE, None, all_fonts)
    assert result.kind == "estimated" and result.findings[0].family == face.family
    assert result.dpi == PdfSource.ANALYSIS_DPI
    assert result.ink_color.g > result.ink_color.r
    with pytest.raises(MissingTextError):
        AnalysisService.analyze(source, 0, rect, "", None, all_fonts)


def test_real_pdf_text_needs_no_typing(styled_pdf, all_fonts):
    result = AnalysisService.analyze(PdfSource(styled_pdf), 0, px(45, 40, 250, 66), "", None, all_fonts)
    assert result.kind == "exact" and result.findings[0].score is None


def test_tiny_selection_is_rejected(styled_pdf, all_fonts):
    with pytest.raises(AnalysisError, match="too small"):
        AnalysisService.analyze(PdfSource(styled_pdf), 0, (10, 10, 12, 12), "x", None, all_fonts)


def test_protected_corrupt_missing_and_unsupported_files(tmp_path):
    doc = pymupdf.open()
    doc.new_page()
    locked = tmp_path / "locked.pdf"
    doc.save(locked, encryption=pymupdf.PDF_ENCRYPT_AES_256, user_pw="secret", owner_pw="owner")
    with pytest.raises(SourceError, match="password"):
        SourceFactory.open(locked)
    broken = tmp_path / "broken.pdf"
    broken.write_bytes(b"%PDF-1.4 nonsense")
    with pytest.raises(SourceError, match="could not be opened"):
        SourceFactory.open(broken)
    fake = tmp_path / "fake.png"
    fake.write_bytes(b"not an image")
    with pytest.raises(SourceError, match="could not be read"):
        SourceFactory.open(fake)
    with pytest.raises(SourceError, match="not found"):
        SourceFactory.open(tmp_path / "gone.png")
    with pytest.raises(SourceError, match="not a supported type"):
        SourceFactory.open(tmp_path / "notes.txt")


@pytest.mark.parametrize("suffix,kwargs", [(".png", {}), (".jpg", {"quality": 90}), (".bmp", {}), (".tiff", {}),
                                           (".webp", {}), (".gif", {})])
def test_common_picture_formats_open(tmp_path, suffix, kwargs):
    path = tmp_path / f"p{suffix}"
    Image.new("RGB", (60, 30), (200, 10, 10)).save(path, **kwargs)
    source = SourceFactory.open(path)
    assert source.render_page(0).image.size == (60, 30)


def test_dpi_hint_and_multipage(tmp_path):
    path = tmp_path / "a.tiff"
    frames = [Image.new("RGB", (40, 20), c) for c in ((255, 0, 0), (0, 255, 0))]
    frames[0].save(path, save_all=True, append_images=frames[1:], dpi=(300, 300))
    source = ImageSource(path)
    assert source.page_count == 2 and source.dpi_hint() == 300
    assert source.render_page(1).image.getpixel((0, 0)) == (0, 255, 0)
    no_dpi = tmp_path / "b.png"
    Image.new("RGB", (4, 4)).save(no_dpi)
    assert ImageSource(no_dpi).dpi_hint() is None


def test_transparent_png_keeps_light_text_visible(tmp_path):
    light = Image.new("RGBA", (40, 20), (0, 0, 0, 0))
    light.paste((255, 255, 255, 255), (5, 5, 35, 15))
    path = tmp_path / "t.png"
    light.save(path)
    page = ImageSource(path).render_page(0).image
    assert page.getpixel((0, 0)) == (0, 0, 0) and page.getpixel((20, 10)) == (255, 255, 255)
