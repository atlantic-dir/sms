"""Ranks installed fonts by how closely they reproduce a picture of text."""

import math
from collections.abc import Callable
from dataclasses import dataclass

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from fontsleuth.errors import AnalysisError, CancelledError
from fontsleuth.models import FontCandidate
from fontsleuth.text_mask import TextMask


@dataclass
class MatchScore:
    """class:MatchScore--#86

    Purpose: How well one font reproduced the picture, and what text size that implies.
    Parameters: candidate (the font face), score (higher is better, about 0..1), size_px (estimated em size in
        pixels of the source picture), spacing_differs (True if width and height disagree about the size,
        typically because of letter-spacing or a stretched image).
    Raises: nothing.
    Called from: FontMatcher.rank (#100), AnalysisService.analyze_pixels (#6).
    Calls: nothing.
    """

    candidate: FontCandidate
    score: float
    size_px: float
    spacing_differs: bool


class GlyphRenderer:
    """class:GlyphRenderer--#87

    Purpose: Draws text with a candidate font into a cropped 0..1 coverage array.
    Parameters: none (all methods are static).
    Raises: OSError when Pillow cannot open the font file.
    Called from: FontMatcher.rank (#100), PreviewRenderer.render (#154).
    Calls: Pillow ImageFont and ImageDraw.
    """

    @staticmethod
    def load(candidate: FontCandidate, size: float) -> ImageFont.FreeTypeFont:
        """class:GlyphRenderer--method:load--#88

        Purpose: Opens a font face at a pixel size, applying variable-font coordinates if needed.
        Parameters: candidate, the face; size, em size in pixels.
        Returns: a Pillow font.
        Raises: OSError if the file cannot be opened.
        Called from: GlyphRenderer.render (#92), PreviewRenderer.render (#154).
        Calls: ImageFont.truetype.
        """
        font = ImageFont.truetype(str(candidate.path), size=size, index=candidate.index)
        if candidate.axes is not None:
            font.set_variation_by_axes(list(candidate.axes))
        return font

    @staticmethod
    def _signature(font: ImageFont.FreeTypeFont, char: str) -> bytes:
        """class:GlyphRenderer--method:_signature--#89

        Purpose: Renders one character so that "missing glyph" boxes can be recognised by comparison.
        Parameters: font, the loaded font; char, the character.
        Returns: the raw bitmap bytes.
        Raises: nothing.
        Called from: GlyphRenderer.supports (#90).
        Calls: ImageDraw.text.
        """
        size = int(font.size * 2) + 8
        canvas = Image.new("L", (size, size), 0)
        ImageDraw.Draw(canvas).text((4, 4), char, font=font, fill=255)
        return canvas.tobytes()

    @staticmethod
    def supports(font: ImageFont.FreeTypeFont, text: str) -> bool:
        """class:GlyphRenderer--method:supports--#90

        Purpose: Checks that the font has a real glyph for every visible character in the text. Cheap size
            measurements settle almost every character; the slow bitmap comparison runs only when a character's
            measurements equal those of the font's "missing glyph" box.
        Parameters: font, the loaded font; text, the string to draw.
        Returns: True when no character falls back to the font's "missing glyph" shape.
        Raises: nothing.
        Called from: GlyphRenderer.can_draw (#91).
        Calls: GlyphRenderer._signature (#89).
        """
        missing = "\U0010FFFF"
        missing_metrics = (font.getbbox(missing), font.getlength(missing))
        missing_bitmap = None
        for char in {c for c in text if not c.isspace()}:
            if (font.getbbox(char), font.getlength(char)) != missing_metrics:
                continue
            missing_bitmap = missing_bitmap or GlyphRenderer._signature(font, missing)
            if GlyphRenderer._signature(font, char) == missing_bitmap:
                return False
        return True

    @staticmethod
    def can_draw(candidate: FontCandidate, text: str) -> bool:
        """class:GlyphRenderer--method:can_draw--#91

        Purpose: Tells whether a font has every character of the text.
        Parameters: candidate, the face; text, the line to draw.
        Returns: True when all visible characters exist in the font; False for unreadable font files.
        Raises: nothing (OSError is treated as "cannot draw", so one broken font cannot stop the search).
        Called from: FontMatcher.rank (#100).
        Calls: GlyphRenderer.load (#88), GlyphRenderer.supports (#90).
        """
        try:
            return GlyphRenderer.supports(GlyphRenderer.load(candidate, 24), text)
        except OSError:
            return False

    @staticmethod
    def render(candidate: FontCandidate, text: str, size: int, threshold: float) -> np.ndarray | None:
        """class:GlyphRenderer--method:render--#92

        Purpose: Draws the text and crops the result to its ink bounding box.
        Parameters: candidate, the face; text, one line; size, em size in px; threshold, ink cut-off for the crop.
        Returns: a float32 HxW coverage array, or None when the font draws nothing. Missing characters are
            not checked here (see GlyphRenderer.can_draw (#91)) so that the first pass stays fast.
        Raises: OSError if the font file cannot be opened.
        Called from: FontMatcher._safe_render (#104).
        Calls: GlyphRenderer.load (#88).
        """
        font = GlyphRenderer.load(candidate, size)
        ascent, descent = font.getmetrics()
        pad = size // 2 + 2
        canvas = Image.new("L", (int(font.getlength(text)) + 2 * pad, ascent + descent + 2 * pad), 0)
        ImageDraw.Draw(canvas).text((pad, pad + ascent), text, font=font, fill=255, anchor="ls")
        array = np.asarray(canvas, dtype=np.float32) / 255.0
        rows, cols = np.where((array >= threshold).any(axis=1))[0], np.where((array >= threshold).any(axis=0))[0]
        if rows.size == 0:
            return None
        return array[rows[0]: rows[-1] + 1, cols[0]: cols[-1] + 1]


class Similarity:
    """class:Similarity--#93

    Purpose: Scores how alike a picture mask and a rendered text are.
    Parameters: none (all methods are static).
    Raises: nothing.
    Called from: FontMatcher.rank (#100), InkRefiner.refine (#114).
    Calls: numpy, Pillow.
    """

    ASPECT_TOLERANCE = 0.03
    DENSITY_TOLERANCE = 0.05

    @staticmethod
    def correlation(a: np.ndarray, b: np.ndarray) -> float:
        """class:Similarity--method:correlation--#94

        Purpose: Zero-mean normalised cross-correlation of two equally sized arrays.
        Parameters: a and b, arrays of the same shape.
        Returns: a value from -1 to 1 (0 when either array is flat).
        Raises: nothing.
        Called from: Similarity.best_shift (#96).
        Calls: numpy.
        """
        a0, b0 = a - a.mean(), b - b.mean()
        denominator = math.sqrt(float((a0 * a0).sum() * (b0 * b0).sum()))
        return float((a0 * b0).sum() / denominator) if denominator > 1e-9 else 0.0

    @staticmethod
    def fit(mask: np.ndarray, rendered: np.ndarray) -> np.ndarray:
        """class:Similarity--method:fit--#95

        Purpose: Resamples a rendering to exactly the size of the picture's mask (area averaging, which mimics
            anti-aliasing).
        Parameters: mask, the picture's coverage; rendered, a candidate rendering of any size.
        Returns: a float32 array with the mask's shape.
        Raises: nothing.
        Called from: Similarity.score (#98), InkRefiner.refine (#114).
        Calls: PIL.Image.resize.
        """
        height, width = mask.shape
        resized = Image.fromarray(rendered).resize((width, height), Image.Resampling.BOX)
        return np.asarray(resized, dtype=np.float32)

    @staticmethod
    def best_shift(mask: np.ndarray, fitted: np.ndarray) -> tuple[float, int, int]:
        """class:Similarity--method:best_shift--#96

        Purpose: Finds the correlation when the two images may be off by up to one pixel in each direction.
        Parameters: mask and fitted, arrays of the same shape.
        Returns: (best correlation, dy, dx) where fitted[y - dy, x - dx] lines up with mask[y, x].
        Raises: nothing.
        Called from: Similarity.score (#98), InkRefiner.refine (#114).
        Calls: Similarity.correlation (#94).
        """
        height, width = mask.shape
        best = (-1.0, 0, 0)
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                a = mask[max(dy, 0): height + min(dy, 0), max(dx, 0): width + min(dx, 0)]
                b = fitted[max(-dy, 0): height + min(-dy, 0), max(-dx, 0): width + min(-dx, 0)]
                if a.size > 1:
                    value = Similarity.correlation(a, b)
                    best = (value, dy, dx) if value > best[0] else best
        return best

    @staticmethod
    def score(mask: np.ndarray, rendered: np.ndarray) -> float:
        """class:Similarity--method:score--#98

        Purpose: Combines shape correlation with penalties for wrong proportions and wrong stroke thickness
            (the stroke term is what tells Regular from Bold).
        Parameters: mask, the picture's coverage; rendered, a candidate rendering (any size, cropped to ink).
        Returns: the score; 1.0 is a perfect match.
        Raises: nothing.
        Called from: FontMatcher.rank (#100).
        Calls: Similarity.fit (#95), Similarity.best_shift (#96).
        """
        height, width = mask.shape
        fitted = Similarity.fit(mask, rendered)
        aspect = math.log((rendered.shape[1] / rendered.shape[0]) / (width / height))
        density = math.log(max(float(mask.mean()), 1e-6) / max(float(fitted.mean()), 1e-6))
        shape_score = Similarity.best_shift(mask, fitted)[0]
        aspect_penalty = 0.6 * max(0.0, abs(aspect) - Similarity.ASPECT_TOLERANCE)
        density_penalty = 0.5 * max(0.0, abs(density) - Similarity.DENSITY_TOLERANCE)
        return shape_score - aspect_penalty - density_penalty


class FontMatcher:
    """class:FontMatcher--#99

    Purpose: Tries every candidate font on the typed text and returns the best matches with size estimates.
        Pass 1 compares each font's smooth rendering with the picture; pass 2 re-checks the best few fonts at
        the estimated pixel size, because small text is usually drawn with hinting that a scaled-down large
        rendering does not reproduce.
    Parameters: none (all methods are static).
    Raises: AnalysisError for empty text or no usable font; CancelledError when cancelled.
    Called from: AnalysisService.analyze_pixels (#6).
    Calls: GlyphRenderer.render (#92), Similarity.score (#98).
    """

    MAX_REFERENCE_SIZE = 200
    SPACING_TOLERANCE = 0.08
    REFINE_COUNT = 12
    THRESHOLD = 0.35

    @staticmethod
    def rank(
        mask: TextMask,
        text: str,
        candidates: list[FontCandidate],
        top_n: int = 8,
        progress: Callable[[int, int], None] | None = None,
        cancelled: Callable[[], bool] | None = None,
    ) -> list[MatchScore]:
        """class:FontMatcher--method:rank--#100

        Purpose: Scores all fonts against the picture and returns the best ones.
        Parameters: mask, the cropped text coverage; text, what the picture says; candidates, fonts to try;
            top_n, how many results to keep; progress, called with (done, total); cancelled, returns True to stop.
        Returns: MatchScore list, best first.
        Raises: AnalysisError if the text is empty or no font can draw it; CancelledError if cancelled.
        Called from: AnalysisService.analyze_pixels (#6).
        Calls: FontMatcher._first_pass (#102), FontMatcher._shortlist (#101), FontMatcher._second_pass (#103).
        """
        text = text.strip()
        if not text:
            raise AnalysisError("Type the text shown in the selection so it can be matched against fonts.")
        total = len(candidates) + FontMatcher.REFINE_COUNT
        results = FontMatcher._first_pass(mask, text, candidates, total, progress, cancelled)
        results.sort(key=lambda r: r.score, reverse=True)
        shortlist = FontMatcher._shortlist(results, text, cancelled)
        head = FontMatcher._second_pass(mask, text, shortlist, len(candidates), total, progress, cancelled)
        head.sort(key=lambda r: r.score, reverse=True)
        return head[:top_n]

    @staticmethod
    def _shortlist(results: list[MatchScore], text: str, cancelled) -> list[MatchScore]:
        """class:FontMatcher--method:_shortlist--#101

        Purpose: Walks down the ranked results and keeps the first few fonts that really contain every character.
        Parameters: results, first-pass scores sorted best first; text, the typed line; cancelled, the callback.
        Returns: up to REFINE_COUNT matches.
        Raises: AnalysisError if no font has all the characters; CancelledError if cancelled.
        Called from: FontMatcher.rank (#100).
        Calls: GlyphRenderer.can_draw (#91).
        """
        shortlist: list[MatchScore] = []
        for match in results:
            if cancelled and cancelled():
                raise CancelledError("Analysis cancelled.")
            if GlyphRenderer.can_draw(match.candidate, text):
                shortlist.append(match)
                if len(shortlist) == FontMatcher.REFINE_COUNT:
                    break
        if not shortlist:
            raise AnalysisError(
                "None of the installed fonts has every character you typed. "
                "Check the text for typos, or add a font folder that covers these characters."
            )
        return shortlist

    @staticmethod
    def _first_pass(mask, text, candidates, total, progress, cancelled) -> list[MatchScore]:
        """class:FontMatcher--method:_first_pass--#102

        Purpose: Scores every candidate using one smooth, oversized rendering each.
        Parameters: mask, text and candidates as in FontMatcher.rank (#100); total, the progress denominator;
            progress and cancelled, the callbacks.
        Returns: an unsorted list of MatchScore.
        Raises: CancelledError if cancelled.
        Called from: FontMatcher.rank (#100).
        Calls: FontMatcher._safe_render (#104), FontMatcher._size_estimate (#105), Similarity.score (#98).
        """
        reference = int(min(max(mask.height * 2, 48), FontMatcher.MAX_REFERENCE_SIZE))
        results: list[MatchScore] = []
        for done, candidate in enumerate(candidates, start=1):
            if cancelled and cancelled():
                raise CancelledError("Analysis cancelled.")
            rendered = FontMatcher._safe_render(candidate, text, reference)
            if rendered is not None:
                size, differs = FontMatcher._size_estimate(mask, rendered, reference)
                results.append(MatchScore(candidate, Similarity.score(mask.coverage, rendered), size, differs))
            if progress:
                progress(done, total)
        return results

    @staticmethod
    def _second_pass(mask, text, shortlist, done, total, progress, cancelled) -> list[MatchScore]:
        """class:FontMatcher--method:_second_pass--#103

        Purpose: Re-scores the shortlist with a rendering at the estimated pixel size and keeps the better score.
        Parameters: mask and text as before; shortlist, the best first-pass results; done and total, progress
            counters; progress and cancelled, the callbacks.
        Returns: the shortlist, with improved scores where the native-size rendering fits better.
        Raises: CancelledError if cancelled.
        Called from: FontMatcher.rank (#100).
        Calls: FontMatcher._safe_render (#104), FontMatcher._size_estimate (#105), Similarity.score (#98).
        """
        improved: list[MatchScore] = []
        for offset, match in enumerate(shortlist, start=1):
            if cancelled and cancelled():
                raise CancelledError("Analysis cancelled.")
            native_size = max(int(round(match.size_px)), 4)
            native = FontMatcher._safe_render(match.candidate, text, native_size)
            if native is not None:
                score = Similarity.score(mask.coverage, native)
                if score > match.score:
                    size, differs = FontMatcher._size_estimate(mask, native, native_size)
                    match = MatchScore(match.candidate, score, size, differs)
            improved.append(match)
            if progress:
                progress(done + offset, total)
        return improved

    @staticmethod
    def _safe_render(candidate: FontCandidate, text: str, size: int) -> np.ndarray | None:
        """class:FontMatcher--method:_safe_render--#104

        Purpose: Renders with one font but treats an unreadable font file as "skip this font".
        Parameters: candidate, the face; text, the line; size, em size in pixels.
        Returns: the rendering, or None when the font cannot be used.
        Raises: nothing (OSError from a damaged or removed font file is the only case swallowed, by design,
            so one bad font cannot abort the whole search).
        Called from: FontMatcher._first_pass (#102), FontMatcher._second_pass (#103).
        Calls: GlyphRenderer.render (#92).
        """
        try:
            return GlyphRenderer.render(candidate, text, size, FontMatcher.THRESHOLD)
        except OSError:
            return None

    @staticmethod
    def _size_estimate(mask: TextMask, rendered: np.ndarray, reference: int) -> tuple[float, bool]:
        """class:FontMatcher--method:_size_estimate--#105

        Purpose: Converts the picture's ink size into an em size. Width is preferred (more pixels, less noise);
            height is used when the two disagree.
        Parameters: mask, the picture; rendered, the reference rendering; reference, its em size.
        Returns: (size in pixels, True if width and height disagree by more than 8%).
        Raises: nothing.
        Called from: FontMatcher._first_pass (#102), FontMatcher._second_pass (#103).
        Calls: nothing.
        """
        by_width = reference * mask.width / rendered.shape[1]
        by_height = reference * mask.height / rendered.shape[0]
        differs = abs(math.log(by_width / by_height)) > FontMatcher.SPACING_TOLERANCE
        return (by_height if differs else by_width), differs
