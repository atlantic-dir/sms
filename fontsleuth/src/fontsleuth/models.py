"""Plain data objects passed between the logic layer and the GUI."""

from dataclasses import dataclass, field
from pathlib import Path

from PIL import Image

from fontsleuth.weights import WeightNames


@dataclass(frozen=True)
class Rgb:
    """class:Rgb--#144

    Purpose: An sRGB colour with 0-255 channels.
    Parameters: r, g, b, integer channels.
    Raises: nothing.
    Called from: InkAnalyzer.analyze (#108), PdfSource.embedded_styles (#217), ResultPanel.show_result (#185).
    Calls: nothing.
    """

    r: int
    g: int
    b: int

    def hex(self) -> str:
        """class:Rgb--method:hex--#145

        Purpose: Formats the colour as an upper-case web hex code.
        Parameters: none.
        Returns: text such as "#1F3A5F".
        Raises: nothing.
        Called from: ResultPanel.show_finding (#187), ResultFormatter.summary (#161).
        Calls: nothing.
        """
        return f"#{self.r:02X}{self.g:02X}{self.b:02X}"

    def as_tuple(self) -> tuple[int, int, int]:
        """class:Rgb--method:as_tuple--#146

        Purpose: Returns the channels as a plain tuple, handy for Pillow.
        Parameters: none.
        Returns: (r, g, b).
        Raises: nothing.
        Called from: PreviewRenderer.render (#154).
        Calls: nothing.
        """
        return (self.r, self.g, self.b)

    @staticmethod
    def from_int(value: int) -> "Rgb":
        """class:Rgb--method:from_int--#147

        Purpose: Builds a colour from a packed 0xRRGGBB integer, as PDFs store it.
        Parameters: value, the packed integer.
        Returns: the matching Rgb.
        Raises: nothing.
        Called from: PdfSource.embedded_styles (#217).
        Calls: nothing.
        """
        return Rgb((value >> 16) & 255, (value >> 8) & 255, value & 255)


@dataclass(frozen=True)
class FontCandidate:
    """class:FontCandidate--#148

    Purpose: One concrete font face (file, face index and optional variable-font position).
    Parameters: path, index, family, style, weight, italic, axes (variable-font coordinates or None).
    Raises: nothing.
    Called from: FontFileReader.read (#74), FontMatcher.rank (#100), GlyphRenderer.render (#92).
    Calls: nothing.
    """

    path: Path
    index: int
    family: str
    style: str
    weight: int
    italic: bool
    axes: tuple[float, ...] | None = None

    def key(self) -> tuple:
        """class:FontCandidate--method:key--#149

        Purpose: Gives a value that is equal for faces that would render identically.
        Parameters: none.
        Returns: a hashable tuple used to remove duplicate font files.
        Raises: nothing.
        Called from: FontScanner.scan (#85).
        Calls: nothing.
        """
        return (self.family.lower(), self.style.lower(), self.weight, self.italic, self.axes)


@dataclass
class StyleFinding:
    """class:StyleFinding--#150

    Purpose: One answer to "what is this text's style?" - exact (from a PDF) or a ranked estimate.
    Parameters: family, style_name, weight, italic, size_pt, size_px, color, score (None when exact),
        sample_text, note, candidate (the matched font face, when estimated).
    Raises: nothing.
    Called from: AnalysisService.analyze (#5), PdfSource.embedded_styles (#217).
    Calls: nothing.
    """

    family: str
    style_name: str
    weight: int
    italic: bool
    size_pt: float | None
    size_px: float | None
    color: "Rgb | None"
    score: float | None = None
    sample_text: str = ""
    note: str = ""
    candidate: FontCandidate | None = None

    def weight_label(self) -> str:
        """class:StyleFinding--method:weight_label--#151

        Purpose: Describes the weight for people, e.g. "Bold (700)".
        Parameters: none.
        Returns: the weight name followed by its numeric value.
        Raises: nothing.
        Called from: CandidateTableModel.data (#167), ResultFormatter.summary (#161).
        Calls: WeightNames.label (#232).
        """
        return f"{WeightNames.label(self.weight)} ({self.weight})"


@dataclass
class AnalysisResult:
    """class:AnalysisResult--#152

    Purpose: Everything the GUI needs to show after one analysis.
    Parameters: kind ("exact" or "estimated"), findings (best first), ink_color, background_color,
        confidence (text label or ""), ambiguous (top matches too close to call), warnings (plain sentences),
        text (the text that was matched), dpi (resolution used for point sizes), crop (the analysed picture).
    Raises: nothing.
    Called from: AnalysisService.analyze (#5), ResultPanel.show_result (#185).
    Calls: nothing.
    """

    kind: str
    findings: list[StyleFinding]
    ink_color: "Rgb | None" = None
    background_color: "Rgb | None" = None
    confidence: str = ""
    ambiguous: bool = False
    warnings: list[str] = field(default_factory=list)
    text: str = ""
    dpi: float | None = None
    crop: Image.Image | None = None
