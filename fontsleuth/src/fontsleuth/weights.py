"""Font weight names and parsing of style words found in font names."""

import re


class WeightNames:
    """class:WeightNames--#231

    Purpose: Converts between numeric weights (100-900) and names, and reads weight/italic words from font names.
    Parameters: none (all methods are static).
    Raises: nothing.
    Called from: FontFileReader.read (#74), PdfSource.embedded_styles (#217), StyleFinding.weight_label (#151).
    Calls: nothing.
    """

    NAMES = {
        100: "Thin", 200: "Extra Light", 300: "Light", 400: "Regular", 500: "Medium",
        600: "Semibold", 700: "Bold", 800: "Extra Bold", 900: "Black",
    }
    # Order matters: longer / more specific words must be tested first.
    _WORDS = [
        (re.compile(r"extra\s*bold|ultra\s*bold|xbold"), 800),
        (re.compile(r"semi\s*bold|demi\s*bold|demi"), 600),
        (re.compile(r"extra\s*light|ultra\s*light|xlight"), 200),
        (re.compile(r"black|heavy"), 900),
        (re.compile(r"thin|hairline"), 100),
        (re.compile(r"bold"), 700),
        (re.compile(r"medium"), 500),
        (re.compile(r"light"), 300),
        (re.compile(r"regular|normal|book|roman|plain"), 400),
    ]

    @staticmethod
    def label(value: int) -> str:
        """class:WeightNames--method:label--#232

        Purpose: Names the nearest standard weight.
        Parameters: value, a numeric weight such as 650.
        Returns: a name such as "Bold".
        Raises: nothing.
        Called from: StyleFinding.weight_label (#151).
        Calls: nothing.
        """
        nearest = min(max(round(value / 100) * 100, 100), 900)
        return WeightNames.NAMES[nearest]

    @staticmethod
    def from_text(text: str) -> int | None:
        """class:WeightNames--method:from_text--#233

        Purpose: Finds a weight word (Bold, Light, SemiBold...) inside a style or font name.
        Parameters: text, e.g. "Arial-BoldMT" or "Semibold Italic".
        Returns: the numeric weight, or None when no weight word is present.
        Raises: nothing.
        Called from: FontFileReader.read (#74), PdfSource.embedded_styles (#217).
        Calls: nothing.
        """
        lowered = text.lower()
        for pattern, value in WeightNames._WORDS:
            if pattern.search(lowered):
                return value
        return None

    @staticmethod
    def is_italic(text: str) -> bool:
        """class:WeightNames--method:is_italic--#234

        Purpose: Tells whether a style or font name says italic or oblique.
        Parameters: text, the name to inspect.
        Returns: True for italic/oblique names.
        Raises: nothing.
        Called from: FontFileReader.read (#74), PdfSource.embedded_styles (#217).
        Calls: nothing.
        """
        lowered = text.lower()
        return "italic" in lowered or "oblique" in lowered or lowered.endswith(("-it", " it"))

    @staticmethod
    def split_pdf_name(raw: str) -> tuple[str, str]:
        """class:WeightNames--method:split_pdf_name--#235

        Purpose: Splits a PDF font name such as "ABCDEF+Arial-BoldItalicMT" into a readable family and style.
        Parameters: raw, the PostScript name stored in the PDF.
        Returns: (family, style); style is "" when the name has no style part.
        Raises: nothing.
        Called from: PdfSource.embedded_styles (#217).
        Calls: nothing.
        """
        name = re.sub(r"^[A-Z]{6}\+", "", raw)
        match = re.match(r"^([^-,]*)[-,](.*)$", name)
        family, style = (match.group(1), match.group(2)) if match else (name, "")
        return WeightNames._humanize(family, True), WeightNames._humanize(style, False)

    @staticmethod
    def _humanize(text: str, is_family: bool) -> str:
        """class:WeightNames--method:_humanize--#236

        Purpose: Removes vendor suffixes (MT, PS) and spaces out CamelCase words.
        Parameters: text, the raw name part; is_family, True for the family part.
        Returns: the cleaned text.
        Raises: nothing.
        Called from: WeightNames.split_pdf_name (#235).
        Calls: re.sub.
        """
        text = re.sub(r"(PSMT|MT|PS)$", "", text) if len(text) > 4 else text
        text = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", text)
        return text.replace("_", " ").strip()
