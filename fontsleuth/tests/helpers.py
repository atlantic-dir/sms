"""Helpers that draw pictures of text for tests."""

import io

from PIL import Image, ImageDraw

from fontsleuth.font_matcher import GlyphRenderer

SAMPLE = "Quarterly Report: Invoice 2048 due"


def render_line(face, text=SAMPLE, size=28, ink=(31, 58, 95), bg=(250, 250, 240), jpeg=None, scale=None):
    """Draws one line of text with a font face onto a solid background, optionally degraded."""
    font = GlyphRenderer.load(face, size)
    ascent, descent = font.getmetrics()
    image = Image.new("RGB", (int(font.getlength(text)) + 30, ascent + descent + 24), bg)
    ImageDraw.Draw(image).text((15, 12 + ascent), text, font=font, fill=ink, anchor="ls")
    if scale:
        image = image.resize((int(image.width * scale), int(image.height * scale)), Image.Resampling.BICUBIC)
    if jpeg:
        buffer = io.BytesIO()
        image.save(buffer, "JPEG", quality=jpeg)
        image = Image.open(buffer).convert("RGB")
    return image
