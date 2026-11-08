"""Separates ink from background in a picture of text and estimates the text colour."""

from dataclasses import dataclass

import numpy as np

from fontsleuth.errors import AnalysisError
from fontsleuth.models import Rgb


@dataclass
class InkModel:
    """class:InkModel--#106

    Purpose: Result of separating text from background: colours plus a 0-1 "how much ink" map.
    Parameters: ink (text colour), background (background colour), coverage (HxW float array, 1 = full ink),
        background_uniform (False when the background varies enough to make colours less reliable).
    Raises: nothing.
    Called from: InkAnalyzer.analyze (#108), AnalysisService.analyze_pixels (#6).
    Calls: nothing.
    """

    ink: Rgb
    background: Rgb
    coverage: np.ndarray
    background_uniform: bool


class InkAnalyzer:
    """class:InkAnalyzer--#107

    Purpose: Finds the background colour, the text colour and a per-pixel ink coverage map.
    Parameters: none (all methods are static).
    Raises: AnalysisError when the picture has no visible text.
    Called from: AnalysisService.analyze_pixels (#6).
    Calls: numpy.
    """

    MIN_CONTRAST = 40.0  # RGB distance below which we say "no readable text"

    @staticmethod
    def analyze(rgb: np.ndarray) -> InkModel:
        """class:InkAnalyzer--method:analyze--#108

        Purpose: Estimates background, ink colour and ink coverage for a cropped picture of one line of text.
        Parameters: rgb, an HxWx3 uint8 array.
        Returns: an InkModel.
        Raises: AnalysisError if there is no contrast between text and background.
        Called from: AnalysisService.analyze_pixels (#6).
        Calls: InkAnalyzer._background (#109), InkAnalyzer._ink_color (#110), InkAnalyzer._coverage (#111).
        """
        flat = rgb.reshape(-1, 3).astype(np.float32)
        background, uniform = InkAnalyzer._background(flat)
        distance = np.linalg.norm(flat - background, axis=1)
        ink = InkAnalyzer._ink_color(flat, distance)
        span = float(np.linalg.norm(ink - background))
        if span < InkAnalyzer.MIN_CONTRAST:
            raise AnalysisError(
                "No text stands out from the background in this selection. "
                "Drag the box tighter around the text, or choose text with stronger contrast."
            )
        coverage = InkAnalyzer._coverage(flat, background, ink).reshape(rgb.shape[:2])
        return InkModel(InkAnalyzer.to_rgb(ink), InkAnalyzer.to_rgb(background), coverage, uniform)

    @staticmethod
    def _background(flat: np.ndarray) -> tuple[np.ndarray, bool]:
        """class:InkAnalyzer--method:_background--#109

        Purpose: Finds the most common colour (the background) and whether it is a solid colour.
        Parameters: flat, an Nx3 float array of pixels.
        Returns: (background colour as float[3], True if the background is nearly uniform).
        Raises: nothing.
        Called from: InkAnalyzer.analyze (#108).
        Calls: numpy.unique.
        """
        keys = (flat // 8).astype(np.int32)
        packed = keys[:, 0] * 1024 + keys[:, 1] * 32 + keys[:, 2]
        values, counts = np.unique(packed, return_counts=True)
        mode_pixels = flat[packed == values[np.argmax(counts)]]
        centre = np.median(mode_pixels, axis=0)
        near = flat[np.linalg.norm(flat - centre, axis=1) < 24.0]
        background = np.median(near, axis=0)
        return background, bool(near.std(axis=0).max() < 6.0)

    @staticmethod
    def _ink_color(flat: np.ndarray, distance: np.ndarray) -> np.ndarray:
        """class:InkAnalyzer--method:_ink_color--#110

        Purpose: Estimates the text colour from the pixels farthest from the background (the stroke cores).
        Parameters: flat, Nx3 pixels; distance, each pixel's distance from the background.
        Returns: the ink colour as float[3].
        Raises: nothing.
        Called from: InkAnalyzer.analyze (#108).
        Calls: numpy.percentile, numpy.median.
        """
        reference = np.percentile(distance, 99.5)
        core = flat[distance >= 0.85 * reference]
        return np.median(core, axis=0)

    @staticmethod
    def _coverage(flat: np.ndarray, background: np.ndarray, ink: np.ndarray) -> np.ndarray:
        """class:InkAnalyzer--method:_coverage--#111

        Purpose: Measures how much of each pixel is ink by projecting it onto the background-to-ink line.
        Parameters: flat, Nx3 pixels; background and ink, float[3] colours.
        Returns: a length-N array clipped to 0..1.
        Raises: nothing.
        Called from: InkAnalyzer.analyze (#108).
        Calls: numpy.
        """
        axis = ink - background
        length = float(np.linalg.norm(axis))
        return np.clip(((flat - background) @ axis) / (length * length), 0.0, 1.0)

    @staticmethod
    def to_rgb(color: np.ndarray) -> Rgb:
        """class:InkAnalyzer--method:to_rgb--#112

        Purpose: Rounds a float colour to an Rgb object.
        Parameters: color, float[3].
        Returns: the matching Rgb.
        Raises: nothing.
        Called from: InkAnalyzer.analyze (#108).
        Calls: nothing.
        """
        r, g, b = (int(round(float(v))) for v in np.clip(color, 0, 255))
        return Rgb(r, g, b)
