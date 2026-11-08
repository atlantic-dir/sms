"""Turns an ink-coverage map into a tight mask of one line of text."""

from dataclasses import dataclass

import numpy as np

from fontsleuth.errors import AnalysisError


@dataclass
class TextMask:
    """class:TextMask--#223

    Purpose: Ink coverage cropped to the text's bounding box.
    Parameters: coverage (HxW float array, 0..1); top and left, where the crop starts in the original picture.
    Raises: nothing.
    Called from: MaskBuilder.build (#227), FontMatcher.rank (#100), InkRefiner.refine (#114).
    Calls: nothing.
    """

    coverage: np.ndarray
    top: int = 0
    left: int = 0

    @property
    def width(self) -> int:
        """class:TextMask--method:width--#224

        Purpose: Width of the mask in pixels.
        Parameters: none.
        Returns: the width.
        Raises: nothing.
        Called from: FontMatcher.rank (#100).
        Calls: nothing.
        """
        return int(self.coverage.shape[1])

    @property
    def height(self) -> int:
        """class:TextMask--method:height--#225

        Purpose: Height of the mask in pixels.
        Parameters: none.
        Returns: the height.
        Raises: nothing.
        Called from: FontMatcher.rank (#100).
        Calls: nothing.
        """
        return int(self.coverage.shape[0])

    @property
    def solid_fraction(self) -> float:
        """class:TextMask--method:solid_fraction--#238

        Purpose: Share of ink pixels that are fully inked. Thick strokes have solid interiors (high value);
            thin strokes are all anti-aliased edge (low value), which makes the colour estimate unreliable.
        Parameters: none.
        Returns: a number from 0 to 1.
        Raises: nothing.
        Called from: AnalysisService._warnings (#8).
        Calls: numpy.
        """
        inked = int((self.coverage >= 0.35).sum())
        return float((self.coverage >= 0.95).sum()) / inked if inked else 0.0


class MaskBuilder:
    """class:MaskBuilder--#226

    Purpose: Crops a coverage map to the text and checks that it holds a single line.
    Parameters: none (all methods are static).
    Raises: AnalysisError when the text is missing, too small, or spans several lines.
    Called from: AnalysisService.analyze_pixels (#6).
    Calls: numpy.
    """

    THRESHOLD = 0.35
    MIN_HEIGHT = 6

    @staticmethod
    def build(coverage: np.ndarray) -> TextMask:
        """class:MaskBuilder--method:build--#227

        Purpose: Crops the coverage map to the ink bounding box and validates it.
        Parameters: coverage, an HxW float array from InkAnalyzer.analyze (#108).
        Returns: a TextMask.
        Raises: AnalysisError if no ink, text shorter than 6 px, or more than one line.
        Called from: AnalysisService.analyze_pixels (#6).
        Calls: MaskBuilder.count_lines (#228).
        """
        ink = coverage >= MaskBuilder.THRESHOLD
        rows, cols = np.where(ink.any(axis=1))[0], np.where(ink.any(axis=0))[0]
        if rows.size == 0:
            raise AnalysisError("No text was found in the selection. Drag the box around the text and try again.")
        cropped = coverage[rows[0]: rows[-1] + 1, cols[0]: cols[-1] + 1]
        if cropped.shape[0] < MaskBuilder.MIN_HEIGHT:
            raise AnalysisError(
                "The text is too small in this picture to identify reliably (under 6 pixels tall). "
                "Use a larger or sharper copy of the image."
            )
        if MaskBuilder.count_lines(cropped) > 1:
            raise AnalysisError(
                "The selection seems to contain more than one line of text. "
                "Drag a box around a single line, then type just that line."
            )
        return TextMask(cropped, int(rows[0]), int(cols[0]))

    @staticmethod
    def count_lines(cropped: np.ndarray) -> int:
        """class:MaskBuilder--method:count_lines--#228

        Purpose: Counts text lines by finding wide empty horizontal gaps; tiny bands (i-dots) are ignored.
        Parameters: cropped, the cropped coverage map.
        Returns: the number of lines (at least 1).
        Raises: nothing.
        Called from: MaskBuilder.build (#227).
        Calls: numpy.
        """
        has_ink = (cropped >= MaskBuilder.THRESHOLD).any(axis=1)
        total = len(has_ink)
        min_gap = max(2, int(total * 0.06))
        bands, start, gap = [], None, 0
        for y, filled in enumerate(has_ink):
            if filled:
                start = y if start is None else start
                gap = 0
            elif start is not None:
                gap += 1
                if gap >= min_gap:
                    bands.append(y - gap + 1 - start)
                    start, gap = None, 0
        if start is not None:
            bands.append(total - gap - start)
        tallest = max(bands) if bands else 0
        return max(1, sum(1 for band in bands if band >= 0.3 * tallest))
