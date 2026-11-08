"""Draws the "what the best match looks like" picture shown beside the original."""

from PIL import Image, ImageDraw

from fontsleuth.font_matcher import GlyphRenderer
from fontsleuth.models import FontCandidate, Rgb


class PreviewRenderer:
    """class:PreviewRenderer--#153

    Purpose: Renders the typed text in a matched font, size and colour so the user can compare it by eye.
    Parameters: none (all methods are static).
    Raises: OSError when the font file can no longer be opened.
    Called from: ResultPanel.show_finding (#187).
    Calls: GlyphRenderer.load (#88).
    """

    @staticmethod
    def render(candidate: FontCandidate, text: str, size_px: float, ink: Rgb, background: Rgb) -> Image.Image:
        """class:PreviewRenderer--method:render--#154

        Purpose: Draws text at its estimated pixel size on the background colour.
        Parameters: candidate, the font face; text, the line; size_px, em size in picture pixels;
            ink and background, the colours.
        Returns: an RGB Pillow image.
        Raises: OSError if the font file cannot be opened.
        Called from: ResultPanel.show_finding (#187).
        Calls: GlyphRenderer.load (#88), ImageDraw.text.
        """
        font = GlyphRenderer.load(candidate, max(size_px, 4.0))
        ascent, descent = font.getmetrics()
        margin = int(size_px * 0.4) + 4
        canvas = Image.new("RGB", (int(font.getlength(text)) + 2 * margin, ascent + descent + 2 * margin),
                           background.as_tuple())
        ImageDraw.Draw(canvas).text((margin, margin + ascent), text, font=font, fill=ink.as_tuple(), anchor="ls")
        return canvas
