"""Opens pictures and PDFs and hands out page images plus, for PDFs, the exact text styles."""

import logging
import math
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pymupdf
from PIL import Image, ImageOps, UnidentifiedImageError

from fontsleuth.errors import SourceError
from fontsleuth.models import Rgb, StyleFinding
from fontsleuth.weights import WeightNames

SOURCE_LOG = logging.getLogger("fontsleuth.sources")
IMAGE_SUFFIXES = (".png", ".jpg", ".jpeg", ".bmp", ".gif", ".tif", ".tiff", ".webp")
PDF_SUFFIXES = (".pdf",)
Rect = tuple[int, int, int, int]  # left, top, right, bottom in displayed-page pixels


@dataclass
class PageImage:
    """class:PageImage--#201

    Purpose: A page ready to display or analyse, with the resolution it was produced at.
    Parameters: image (RGB Pillow image); dpi (pixels per inch, or None when the file does not say).
    Raises: nothing.
    Called from: ImageSource.render_page (#204), PdfSource.render_page (#214), MainWindow._show_page (#130).
    Calls: nothing.
    """

    image: Image.Image
    dpi: float | None


class ImageSource:
    """class:ImageSource--#202

    Purpose: A picture file (PNG, JPEG, BMP, GIF, TIFF, WebP); multi-frame files appear as several pages.
    Parameters: path, the file to open.
    Raises: SourceError when the file is missing, damaged or not a picture.
    Called from: SourceFactory.open (#222).
    Calls: PIL.Image.
    """

    is_pdf = False

    def __init__(self, path: Path) -> None:
        """class:ImageSource--method:__init__--#203

        Purpose: Opens and verifies the picture.
        Parameters: path, the file to open.
        Returns: nothing.
        Raises: SourceError with a plain-language reason.
        Called from: SourceFactory.open (#222).
        Calls: PIL.Image.open.
        """
        self.path = path
        try:
            self._image = Image.open(path)
            self._image.load()
        except FileNotFoundError as error:
            raise SourceError(f"The file {path.name} was not found. Check that it was not moved or deleted.") from error
        except PermissionError as error:
            raise SourceError(f"Windows would not let the app read {path.name}. Close other programs using it.") from error
        except (UnidentifiedImageError, Image.DecompressionBombError, OSError, SyntaxError) as error:
            SOURCE_LOG.warning("Cannot open %s: %s", path, error)
            raise SourceError(f"{path.name} could not be read as a picture. It may be damaged or an unsupported type.") from error
        self.page_count = max(1, getattr(self._image, "n_frames", 1))

    def render_page(self, index: int) -> PageImage:
        """class:ImageSource--method:render_page--#204

        Purpose: Returns one frame as an RGB image (transparent areas are filled with a contrasting colour).
        Parameters: index, the zero-based frame number.
        Returns: a PageImage; dpi is the file's stored resolution, or None.
        Raises: SourceError if the frame cannot be decoded.
        Called from: MainWindow._show_page (#130), ImageSource.analysis_crop (#207).
        Calls: ImageSource._flatten (#206), ImageSource.dpi_hint (#205).
        """
        try:
            self._image.seek(index)
            frame = ImageOps.exif_transpose(self._image)
            return PageImage(self._flatten(frame), self.dpi_hint())
        except (EOFError, OSError) as error:
            raise SourceError(f"Page {index + 1} of {self.path.name} could not be decoded.") from error

    def dpi_hint(self) -> float | None:
        """class:ImageSource--method:dpi_hint--#205

        Purpose: Reads the resolution stored in the file, ignoring meaningless values.
        Parameters: none.
        Returns: dots per inch, or None when absent or implausible (under 36).
        Raises: nothing.
        Called from: ImageSource.render_page (#204).
        Calls: nothing.
        """
        dpi = self._image.info.get("dpi")
        value = float(dpi[0]) if isinstance(dpi, tuple) and dpi else None
        return value if value and value >= 36 else None

    @staticmethod
    def _flatten(frame: Image.Image) -> Image.Image:
        """class:ImageSource--method:_flatten--#206

        Purpose: Converts to RGB; transparent pixels become white, or black when the opaque pixels are light
            (so white text on a transparent background stays visible).
        Parameters: frame, any Pillow image.
        Returns: an RGB image.
        Raises: nothing.
        Called from: ImageSource.render_page (#204).
        Calls: numpy, PIL.Image.alpha_composite.
        """
        if frame.mode in ("RGBA", "LA", "PA") or (frame.mode == "P" and "transparency" in frame.info):
            rgba = frame.convert("RGBA")
            data = np.asarray(rgba)
            opaque = data[..., 3] > 200
            light_text = bool(opaque.any()) and float(data[..., :3][opaque].mean()) > 140
            base = Image.new("RGBA", rgba.size, (0, 0, 0, 255) if light_text else (255, 255, 255, 255))
            return Image.alpha_composite(base, rgba).convert("RGB")
        return frame.convert("RGB")

    def analysis_crop(self, index: int, rect: Rect) -> PageImage:
        """class:ImageSource--method:analysis_crop--#207

        Purpose: Cuts the selected area out of the picture at its original resolution.
        Parameters: index, the page; rect, (left, top, right, bottom) in pixels.
        Returns: the cropped PageImage.
        Raises: SourceError if the page cannot be decoded.
        Called from: AnalysisService.analyze (#5).
        Calls: ImageSource.render_page (#204).
        """
        page = self.render_page(index)
        return PageImage(page.image.crop(rect), page.dpi)

    def embedded_styles(self, index: int, rect: Rect) -> list[StyleFinding]:
        """class:ImageSource--method:embedded_styles--#208

        Purpose: Pictures carry no text data, so this always reports nothing.
        Parameters: index and rect, ignored.
        Returns: an empty list.
        Raises: nothing.
        Called from: AnalysisService.analyze (#5).
        Calls: nothing.
        """
        return []

    def close(self) -> None:
        """class:ImageSource--method:close--#209

        Purpose: Releases the file handle.
        Parameters: none.
        Returns: nothing.
        Raises: nothing.
        Called from: MainWindow._close_source (#129).
        Calls: PIL.Image.close.
        """
        self._image.close()


class PdfSource:
    """class:PdfSource--#210

    Purpose: A PDF file. Pages are shown at 144 dpi; pixel analysis re-renders the selection at 300 dpi;
        text that is stored as real text is read exactly from the file.
    Parameters: path, the file to open.
    Raises: SourceError for missing, damaged or password-protected files.
    Called from: SourceFactory.open (#222).
    Calls: pymupdf.
    """

    is_pdf = True
    DISPLAY_DPI = 144.0
    ANALYSIS_DPI = 300.0
    MAX_DISPLAY_PIXELS = 25_000_000

    def __init__(self, path: Path) -> None:
        """class:PdfSource--method:__init__--#211

        Purpose: Opens the PDF and rejects protected or empty files.
        Parameters: path, the file to open.
        Returns: nothing.
        Raises: SourceError with a plain-language reason.
        Called from: SourceFactory.open (#222).
        Calls: pymupdf.open.
        """
        self.path = path
        try:
            self._doc = pymupdf.open(path)
        except (pymupdf.FileNotFoundError, FileNotFoundError) as error:
            raise SourceError(f"The file {path.name} was not found. Check that it was not moved or deleted.") from error
        except Exception as error:  # noqa: BLE001 - PyMuPDF raises several unrelated types for damaged files
            SOURCE_LOG.warning("Cannot open PDF %s: %s", path, error)
            raise SourceError(f"{path.name} could not be opened. It may be damaged or not a real PDF.") from error
        if self._doc.needs_pass:
            self._doc.close()
            raise SourceError(f"{path.name} is password-protected. Save an unprotected copy and open that instead.")
        if self._doc.page_count == 0:
            self._doc.close()
            raise SourceError(f"{path.name} has no pages.")
        self.page_count = self._doc.page_count

    def _display_dpi(self, page: "pymupdf.Page") -> float:
        """class:PdfSource--method:_display_dpi--#212

        Purpose: Chooses the display resolution, lowered for huge pages to protect memory.
        Parameters: page, the PDF page.
        Returns: dots per inch.
        Raises: nothing.
        Called from: PdfSource.render_page (#214), PdfSource._to_points (#215).
        Calls: nothing.
        """
        area_in2 = (page.rect.width / 72.0) * (page.rect.height / 72.0)
        return min(self.DISPLAY_DPI, math.sqrt(self.MAX_DISPLAY_PIXELS / max(area_in2, 1e-6)))

    @staticmethod
    def _pixmap_to_image(pixmap: "pymupdf.Pixmap") -> Image.Image:
        """class:PdfSource--method:_pixmap_to_image--#213

        Purpose: Converts a PyMuPDF pixmap to a Pillow RGB image.
        Parameters: pixmap, a rendered pixmap without alpha.
        Returns: the image.
        Raises: nothing.
        Called from: PdfSource.render_page (#214), PdfSource.analysis_crop (#216).
        Calls: PIL.Image.frombytes.
        """
        return Image.frombytes("RGB", (pixmap.width, pixmap.height), pixmap.samples)

    def render_page(self, index: int) -> PageImage:
        """class:PdfSource--method:render_page--#214

        Purpose: Renders a page for display.
        Parameters: index, the zero-based page number.
        Returns: a PageImage with the dpi it was rendered at.
        Raises: SourceError if the page cannot be rendered.
        Called from: MainWindow._show_page (#130).
        Calls: PdfSource._display_dpi (#212), PdfSource._pixmap_to_image (#213).
        """
        try:
            page = self._doc[index]
            dpi = self._display_dpi(page)
            zoom = dpi / 72.0
            pixmap = page.get_pixmap(matrix=pymupdf.Matrix(zoom, zoom), alpha=False)
            return PageImage(self._pixmap_to_image(pixmap), dpi)
        except Exception as error:  # noqa: BLE001 - PyMuPDF has no common base class for render failures
            SOURCE_LOG.warning("Cannot render page %s of %s: %s", index, self.path, error)
            raise SourceError(f"Page {index + 1} of {self.path.name} could not be drawn.") from error

    def _to_points(self, index: int, rect: Rect) -> "pymupdf.Rect":
        """class:PdfSource--method:_to_points--#215

        Purpose: Converts a rectangle in displayed pixels to PDF points on the rotated page.
        Parameters: index, the page; rect, (left, top, right, bottom) in display pixels.
        Returns: a PyMuPDF Rect in points.
        Raises: nothing.
        Called from: PdfSource.analysis_crop (#216), PdfSource.embedded_styles (#217).
        Calls: PdfSource._display_dpi (#212).
        """
        scale = 72.0 / self._display_dpi(self._doc[index])
        return pymupdf.Rect(*(v * scale for v in rect))

    def analysis_crop(self, index: int, rect: Rect) -> PageImage:
        """class:PdfSource--method:analysis_crop--#216

        Purpose: Re-renders just the selected area at 300 dpi for sharper pixel analysis.
        Parameters: index, the page; rect, the selection in display pixels.
        Returns: a PageImage at 300 dpi.
        Raises: SourceError if rendering fails.
        Called from: AnalysisService.analyze (#5).
        Calls: PdfSource._to_points (#215), PdfSource._pixmap_to_image (#213).
        """
        try:
            zoom = self.ANALYSIS_DPI / 72.0
            pixmap = self._doc[index].get_pixmap(
                matrix=pymupdf.Matrix(zoom, zoom), clip=self._to_points(index, rect), alpha=False
            )
            return PageImage(self._pixmap_to_image(pixmap), self.ANALYSIS_DPI)
        except Exception as error:  # noqa: BLE001 - see render_page
            SOURCE_LOG.warning("Cannot render region of page %s: %s", index, error)
            raise SourceError("The selected area could not be drawn from the PDF.") from error

    def embedded_styles(self, index: int, rect: Rect) -> list[StyleFinding]:
        """class:PdfSource--method:embedded_styles--#217

        Purpose: Reads the exact font, size and colour of real (selectable) text inside the selection.
            Invisible text (the hidden layer of scanned, OCR'd PDFs) is ignored because it does not describe
            what is visible.
        Parameters: index, the page; rect, the selection in display pixels.
        Returns: one StyleFinding per distinct style, in reading order; empty if the area has no real text.
        Raises: SourceError if the page text cannot be read.
        Called from: AnalysisService.analyze (#5).
        Calls: PdfSource._to_points (#215), PdfSource._spans_in (#218), PdfSource._finding_from_span (#219).
        """
        try:
            page = self._doc[index]
            area = self._to_points(index, rect) * page.derotation_matrix
            area.normalize()
            findings: dict[tuple, StyleFinding] = {}
            for span in self._spans_in(page, area):
                key = (span["font"], round(span["size"], 2), span["color"], span["flags"])
                if key in findings:
                    findings[key].sample_text = (findings[key].sample_text + " " + span["text"].strip())[:60]
                else:
                    findings[key] = self._finding_from_span(span)
            return list(findings.values())
        except Exception as error:  # noqa: BLE001 - see render_page
            SOURCE_LOG.warning("Cannot read text of page %s: %s", index, error)
            raise SourceError("The text inside this PDF page could not be read.") from error

    @staticmethod
    def _spans_in(page: "pymupdf.Page", area: "pymupdf.Rect") -> list[dict]:
        """class:PdfSource--method:_spans_in--#218

        Purpose: Collects visible text spans that substantially overlap the selected area.
        Parameters: page, the PDF page; area, the selection in the page's unrotated coordinates.
        Returns: PyMuPDF span dictionaries.
        Raises: nothing.
        Called from: PdfSource.embedded_styles (#217).
        Calls: pymupdf.Page.get_text.
        """
        spans = []
        for block in page.get_text("dict")["blocks"]:
            for line in block.get("lines", []):
                for span in line["spans"]:
                    box = pymupdf.Rect(span["bbox"])
                    overlap = (box & area).get_area() if box.intersects(area) else 0.0
                    smaller = min(box.get_area(), area.get_area())
                    visible = span.get("alpha", 255) > 0 and "glyphless" not in span["font"].lower()
                    if visible and span["text"].strip() and smaller > 0 and overlap / smaller >= 0.4:
                        spans.append(span)
        return spans

    @staticmethod
    def _finding_from_span(span: dict) -> StyleFinding:
        """class:PdfSource--method:_finding_from_span--#219

        Purpose: Turns a PyMuPDF span into a StyleFinding (font name, weight, italic, point size, colour).
        Parameters: span, a span dictionary.
        Returns: the finding.
        Raises: nothing.
        Called from: PdfSource.embedded_styles (#217).
        Calls: WeightNames.split_pdf_name (#235), WeightNames.from_text (#233), WeightNames.is_italic (#234), Rgb.from_int (#147).
        """
        family, style = WeightNames.split_pdf_name(span["font"])
        flags = span["flags"]
        weight = WeightNames.from_text(span["font"]) or (700 if flags & 16 else 400)
        italic = bool(flags & 2) or WeightNames.is_italic(span["font"])
        name = style or (WeightNames.NAMES[weight] + (" Italic" if italic else ""))
        return StyleFinding(
            family=family, style_name=name, weight=weight, italic=italic,
            size_pt=round(float(span["size"]), 2), size_px=None, color=Rgb.from_int(span["color"]),
            sample_text=span["text"].strip()[:60], note="Read exactly from the PDF's text data.",
        )

    def close(self) -> None:
        """class:PdfSource--method:close--#220

        Purpose: Releases the PDF file.
        Parameters: none.
        Returns: nothing.
        Raises: nothing.
        Called from: MainWindow._close_source (#129).
        Calls: pymupdf.Document.close.
        """
        self._doc.close()


class SourceFactory:
    """class:SourceFactory--#221

    Purpose: Chooses the right source class for a file.
    Parameters: none (all methods are static).
    Raises: SourceError for unsupported file types.
    Called from: MainWindow._open_path (#127).
    Calls: ImageSource (#202), PdfSource (#210).
    """

    @staticmethod
    def open(path: Path) -> "ImageSource | PdfSource":
        """class:SourceFactory--method:open--#222

        Purpose: Opens an image or PDF by its file extension.
        Parameters: path, the file.
        Returns: an ImageSource or PdfSource.
        Raises: SourceError if the type is not supported or the file cannot be read.
        Called from: MainWindow._open_path (#127).
        Calls: PdfSource.__init__ (#211), ImageSource.__init__ (#203).
        """
        suffix = path.suffix.lower()
        if suffix in PDF_SUFFIXES:
            return PdfSource(path)
        if suffix in IMAGE_SUFFIXES:
            return ImageSource(path)
        raise SourceError(
            f"{path.name} is not a supported type. Open a PNG, JPG, BMP, GIF, TIFF, WebP or PDF file."
        )
