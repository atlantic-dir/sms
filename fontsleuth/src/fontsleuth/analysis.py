"""Coordinates one analysis: exact PDF text styles when available, otherwise a picture-based estimate."""

from collections.abc import Callable

import numpy as np

from fontsleuth.errors import AnalysisError, MissingTextError
from fontsleuth.font_matcher import FontMatcher, MatchScore
from fontsleuth.ink_analysis import InkAnalyzer
from fontsleuth.models import AnalysisResult, FontCandidate, StyleFinding
from fontsleuth.sources import ImageSource, PageImage, PdfSource, Rect
from fontsleuth.text_mask import MaskBuilder, TextMask

Progress = Callable[[int, int], None]
Cancelled = Callable[[], bool]


class ConfidenceRater:
    """class:ConfidenceRater--#1

    Purpose: Turns raw match scores into plain-language confidence and detects near-ties.
    Parameters: none (all methods are static).
    Raises: nothing.
    Called from: AnalysisService.analyze_pixels (#6).
    Calls: nothing.
    """

    HIGH = 0.85
    MEDIUM = 0.72
    TIE_GAP = 0.02

    @staticmethod
    def label(score: float) -> str:
        """class:ConfidenceRater--method:label--#2

        Purpose: Names how trustworthy a match score is.
        Parameters: score, the best font's score.
        Returns: "High", "Medium" or "Low".
        Raises: nothing.
        Called from: AnalysisService.analyze_pixels (#6).
        Calls: nothing.
        """
        if score >= ConfidenceRater.HIGH:
            return "High"
        return "Medium" if score >= ConfidenceRater.MEDIUM else "Low"

    @staticmethod
    def is_ambiguous(matches: list[MatchScore]) -> bool:
        """class:ConfidenceRater--method:is_ambiguous--#3

        Purpose: Detects when the runner-up is almost as good as the winner, so the winner must not be trusted alone.
        Parameters: matches, ranked best first.
        Returns: True when the top two scores differ by less than 0.02.
        Raises: nothing.
        Called from: AnalysisService.analyze_pixels (#6).
        Calls: nothing.
        """
        return len(matches) > 1 and matches[0].score - matches[1].score < ConfidenceRater.TIE_GAP


class AnalysisService:
    """class:AnalysisService--#4

    Purpose: Runs a full analysis of a selected area and returns an AnalysisResult.
    Parameters: none (all methods are static).
    Raises: AnalysisError, SourceError, CancelledError.
    Called from: MainWindow._start_analysis (#132).
    Calls: PdfSource.embedded_styles (#217), AnalysisService.analyze_pixels (#6).
    """

    MIN_SELECTION = 4
    MAX_PIXELS = 12_000_000
    THIN_STROKES = 0.5  # below this share of fully-inked pixels the colour estimate is unreliable

    @staticmethod
    def analyze(
        source: "ImageSource | PdfSource",
        page_index: int,
        rect: Rect,
        text: str,
        dpi: float | None,
        candidates: list[FontCandidate],
        progress: Progress | None = None,
        cancelled: Cancelled | None = None,
    ) -> AnalysisResult:
        """class:AnalysisService--method:analyze--#5

        Purpose: Prefers exact PDF text data; falls back to picture analysis when the area has no real text.
        Parameters: source, the open file; page_index, the page; rect, the selection in displayed pixels;
            text, what the picture says (may be empty for PDFs with real text); dpi, the picture resolution used
            for point sizes (None to use the file's own); candidates, fonts to try; progress and cancelled,
            callbacks.
        Returns: an AnalysisResult.
        Raises: AnalysisError for unusable selections or missing text; SourceError; CancelledError.
        Called from: MainWindow._start_analysis (#132).
        Calls: PdfSource.embedded_styles (#217), PdfSource.analysis_crop (#216), AnalysisService.analyze_pixels (#6).
        """
        if rect[2] - rect[0] < AnalysisService.MIN_SELECTION or rect[3] - rect[1] < AnalysisService.MIN_SELECTION:
            raise AnalysisError("The selection is too small. Drag a box that fully surrounds the line of text.")
        exact = source.embedded_styles(page_index, rect)
        if exact:
            warnings = ["Several different text styles are inside the box; all are listed."] if len(exact) > 1 else []
            return AnalysisResult("exact", exact, exact[0].color, None, "Exact", False, warnings, "", None)
        if (rect[2] - rect[0]) * (rect[3] - rect[1]) > AnalysisService.MAX_PIXELS and not source.is_pdf:
            raise AnalysisError("The selection is very large. Drag a box around just one line of text.")
        crop = source.analysis_crop(page_index, rect)
        effective = dpi or crop.dpi or 96.0
        return AnalysisService.analyze_pixels(crop, text, effective, candidates, progress, cancelled)

    @staticmethod
    def analyze_pixels(
        crop: PageImage,
        text: str,
        dpi: float,
        candidates: list[FontCandidate],
        progress: Progress | None = None,
        cancelled: Cancelled | None = None,
    ) -> AnalysisResult:
        """class:AnalysisService--method:analyze_pixels--#6

        Purpose: Estimates font, weight, size and colour of one line of text from its pixels.
        Parameters: crop, the cropped picture; text, the line it shows; dpi, pixels per inch for point sizes;
            candidates, fonts to try; progress and cancelled, callbacks.
        Returns: an AnalysisResult of kind "estimated" with ranked findings.
        Raises: MissingTextError, AnalysisError (no text found, several lines, no matching font); CancelledError.
        Called from: AnalysisService.analyze (#5).
        Calls: InkAnalyzer.analyze (#108), MaskBuilder.build (#227), FontMatcher.rank (#100), InkRefiner.refine (#114),
            AnalysisService._warnings (#8), AnalysisService._finding (#7).
        """
        text = text.strip()
        if not text:
            raise MissingTextError("Type the text shown in the box. It is needed to match fonts in a picture.")
        if not candidates:
            raise AnalysisError("No fonts are available yet. Wait for the font scan to finish or add a font folder.")
        rgb = np.asarray(crop.image.convert("RGB"))
        model = InkAnalyzer.analyze(rgb)
        mask = MaskBuilder.build(model.coverage)
        matches = FontMatcher.rank(mask, text, candidates, progress=progress, cancelled=cancelled)
        ink = model.ink
        ambiguous = ConfidenceRater.is_ambiguous(matches)
        findings = [AnalysisService._finding(m, text, ink, dpi) for m in matches]
        warnings = AnalysisService._warnings(model.background_uniform, mask, matches[0], ambiguous)
        return AnalysisResult(
            "estimated", findings, ink, model.background, ConfidenceRater.label(matches[0].score),
            ambiguous, warnings, text, dpi, crop.image,
        )

    @staticmethod
    def _finding(match: MatchScore, text: str, ink, dpi: float) -> StyleFinding:
        """class:AnalysisService--method:_finding--#7

        Purpose: Converts a font match into a StyleFinding with the size expressed in points.
        Parameters: match, the font match; text, the typed line; ink, the text colour; dpi, pixels per inch.
        Returns: the finding.
        Raises: nothing.
        Called from: AnalysisService.analyze_pixels (#6).
        Calls: nothing.
        """
        face = match.candidate
        note = "Letter spacing or image stretching differs from this font's normal look." if match.spacing_differs else ""
        return StyleFinding(
            family=face.family, style_name=face.style, weight=face.weight, italic=face.italic,
            size_pt=round(match.size_px * 72.0 / dpi, 1), size_px=round(match.size_px, 1), color=ink,
            score=round(match.score, 3), sample_text=text, note=note, candidate=face,
        )

    @staticmethod
    def _warnings(uniform: bool, mask: TextMask, best: MatchScore, ambiguous: bool) -> list[str]:
        """class:AnalysisService--method:_warnings--#8

        Purpose: Lists plain-language cautions that apply to this result.
        Parameters: uniform, whether the background is a solid colour; mask, the text mask (height and stroke solidity);
            best, the top match; ambiguous, whether the top two matches are nearly tied.
        Returns: a list of sentences (possibly empty).
        Raises: nothing.
        Called from: AnalysisService.analyze_pixels (#6).
        Calls: nothing.
        """
        notes = []
        if best.score < 0.6:
            notes.append("No installed font matches closely. The real font may not be installed on this computer "
                         "- use 'Add font folder' to include more fonts.")
        if ambiguous:
            notes.append("The top matches are almost equally good. Compare the preview with your picture "
                         "before relying on the first row.")
        if mask.height < 14:
            notes.append("The text is small in this picture, so the weight is less certain. "
                         "A larger copy of the image gives better results.")
        if mask.solid_fraction < AnalysisService.THIN_STROKES:
            notes.append("The strokes are thin in this picture, so the real text colour may be somewhat "
                         "darker or stronger than the colour shown.")
        if not uniform:
            notes.append("The background is not a single solid colour, so the colour estimate may be off.")
        return notes
