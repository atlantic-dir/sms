"""Finds installed fonts and describes each face (family, style, weight, italic)."""

import json
import logging
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from pathlib import Path

from fontTools.ttLib import TTCollection, TTFont

from fontsleuth.errors import CancelledError
from fontsleuth.models import FontCandidate
from fontsleuth.weights import WeightNames

FONT_LOG = logging.getLogger("fontsleuth.fonts")
logging.getLogger("fontTools").setLevel(logging.ERROR)  # old fonts trigger harmless timestamp warnings
FONT_SUFFIXES = {".ttf", ".otf", ".ttc", ".otc"}


@dataclass
class ScanReport:
    """class:ScanReport--#72

    Purpose: Outcome of a font scan: the usable faces and the files that had to be skipped.
    Parameters: candidates (usable faces), skipped (list of (file name, reason)).
    Raises: nothing.
    Called from: FontScanner.scan (#85), MainWindow._on_fonts_ready (#138).
    Calls: nothing.
    """

    candidates: list[FontCandidate] = field(default_factory=list)
    skipped: list[tuple[str, str]] = field(default_factory=list)


class FontFileReader:
    """class:FontFileReader--#73

    Purpose: Reads the faces stored in one font file (including collections and variable-font styles).
    Parameters: none (all methods are static).
    Raises: any fontTools error for a damaged file; the caller records it as "skipped".
    Called from: FontScanner.scan (#85).
    Calls: fontTools.
    """

    @staticmethod
    def read(path: Path) -> list[FontCandidate]:
        """class:FontFileReader--method:read--#74

        Purpose: Lists every face in a font file.
        Parameters: path, a .ttf/.otf/.ttc/.otc file.
        Returns: a list of FontCandidate (one per face or named variable-font style).
        Raises: fontTools errors or OSError when the file is unreadable.
        Called from: FontScanner.scan (#85).
        Calls: FontFileReader._describe (#75).
        """
        if path.suffix.lower() in {".ttc", ".otc"}:
            fonts = TTCollection(str(path), lazy=True).fonts
        else:
            fonts = [TTFont(str(path), lazy=True)]
        found: list[FontCandidate] = []
        for index, font in enumerate(fonts):
            found.extend(FontFileReader._describe(path, index, font))
        return found

    @staticmethod
    def _describe(path: Path, index: int, font: TTFont) -> list[FontCandidate]:
        """class:FontFileReader--method:_describe--#75

        Purpose: Builds candidates for one face; a variable font yields one candidate per named style.
        Parameters: path and index identify the face; font is the opened fontTools font.
        Returns: one or more FontCandidate objects.
        Raises: fontTools errors for damaged tables.
        Called from: FontFileReader.read (#74).
        Calls: WeightNames.from_text (#233), WeightNames.is_italic (#234).
        """
        names = font["name"]
        family = (names.getDebugName(16) or names.getDebugName(1) or path.stem).strip()
        style = (names.getDebugName(17) or names.getDebugName(2) or "Regular").strip()
        os2 = font["OS/2"] if "OS/2" in font else None
        # The style name ("Bold") is what people see; some fonts store a misleading OS/2 weight (e.g. 600 for Bold).
        weight = WeightNames.from_text(style) or int(getattr(os2, "usWeightClass", 0) or 0) or 400
        italic = bool((getattr(os2, "fsSelection", 0) & 1) or (font["head"].macStyle & 2)) or WeightNames.is_italic(style)
        if "fvar" not in font or not font["fvar"].instances:
            return [FontCandidate(path, index, family, style, weight, italic)]
        axes = font["fvar"].axes
        found = []
        for instance in font["fvar"].instances:
            coords = instance.coordinates
            label = (names.getDebugName(instance.subfamilyNameID) or "Regular").strip()
            values = tuple(float(coords.get(axis.axisTag, axis.defaultValue)) for axis in axes)
            inst_weight = int(coords.get("wght", weight))
            found.append(FontCandidate(path, index, family, label, inst_weight, italic or WeightNames.is_italic(label), values))
        return found


class FontCache:
    """class:FontCache--#76

    Purpose: Remembers scan results on disk so the next start-up does not re-read every font file.
    Parameters: file, the JSON cache path (may not exist yet).
    Raises: nothing (a damaged cache is ignored and rebuilt).
    Called from: FontScanner.scan (#85).
    Calls: json.
    """

    VERSION = 1

    def __init__(self, file: Path | None) -> None:
        """class:FontCache--method:__init__--#77

        Purpose: Loads the cache file if there is one.
        Parameters: file, the cache path or None to disable caching.
        Returns: nothing.
        Raises: nothing; unreadable caches are logged and ignored.
        Called from: FontScanner.scan (#85).
        Calls: FontCache._load (#78).
        """
        self._file = file
        self._entries: dict[str, dict] = self._load()
        self._fresh: dict[str, dict] = {}

    def _load(self) -> dict[str, dict]:
        """class:FontCache--method:_load--#78

        Purpose: Reads the JSON cache.
        Parameters: none.
        Returns: the stored entries, or an empty dict when missing or damaged.
        Raises: nothing.
        Called from: FontCache.__init__ (#77).
        Calls: json.load.
        """
        if self._file is None or not self._file.exists():
            return {}
        try:
            data = json.loads(self._file.read_text(encoding="utf-8"))
            return data["entries"] if data.get("version") == self.VERSION else {}
        except (OSError, ValueError, KeyError):
            FONT_LOG.warning("Font cache %s is unreadable and will be rebuilt", self._file)
            return {}

    @staticmethod
    def signature(path: Path) -> str:
        """class:FontCache--method:signature--#79

        Purpose: Builds a key that changes when a font file changes.
        Parameters: path, the font file.
        Returns: text made of path, size and modified time.
        Raises: OSError if the file cannot be inspected.
        Called from: FontScanner.scan (#85).
        Calls: Path.stat.
        """
        info = path.stat()
        return f"{path}|{info.st_size}|{int(info.st_mtime)}"

    def get(self, signature: str) -> list[FontCandidate] | None:
        """class:FontCache--method:get--#80

        Purpose: Returns cached faces for an unchanged file and keeps the entry for saving.
        Parameters: signature, from FontCache.signature (#79).
        Returns: the faces, or None when the file is not cached.
        Raises: nothing.
        Called from: FontScanner.scan (#85).
        Calls: nothing.
        """
        entry = self._entries.get(signature)
        if entry is None:
            return None
        self._fresh[signature] = entry
        return [
            FontCandidate(Path(d["path"]), d["index"], d["family"], d["style"], d["weight"], d["italic"],
                          tuple(d["axes"]) if d["axes"] is not None else None)
            for d in entry["faces"]
        ]

    def put(self, signature: str, faces: list[FontCandidate]) -> None:
        """class:FontCache--method:put--#81

        Purpose: Stores freshly read faces.
        Parameters: signature, the file key; faces, what was read.
        Returns: nothing.
        Raises: nothing.
        Called from: FontScanner.scan (#85).
        Calls: nothing.
        """
        self._fresh[signature] = {"faces": [
            {"path": str(f.path), "index": f.index, "family": f.family, "style": f.style,
             "weight": f.weight, "italic": f.italic, "axes": list(f.axes) if f.axes is not None else None}
            for f in faces
        ]}

    def save(self) -> None:
        """class:FontCache--method:save--#82

        Purpose: Writes the cache atomically (temp file, then rename) so a crash cannot corrupt it.
        Parameters: none.
        Returns: nothing.
        Raises: nothing; failures are logged because the cache is only an optimisation.
        Called from: FontScanner.scan (#85).
        Calls: json.dumps, Path.replace.
        """
        if self._file is None:
            return
        try:
            self._file.parent.mkdir(parents=True, exist_ok=True)
            temp = self._file.with_suffix(".tmp")
            temp.write_text(json.dumps({"version": self.VERSION, "entries": self._fresh}), encoding="utf-8")
            temp.replace(self._file)
        except OSError:
            FONT_LOG.warning("Could not save font cache %s", self._file, exc_info=True)


class FontScanner:
    """class:FontScanner--#83

    Purpose: Walks font folders and returns every usable face, without duplicates.
    Parameters: none (all methods are static).
    Raises: CancelledError when cancelled.
    Called from: FontLibraryController.rescan (#69).
    Calls: FontFileReader.read (#74), FontCache (#76).
    """

    @staticmethod
    def find_files(folders: Iterable[Path]) -> list[Path]:
        """class:FontScanner--method:find_files--#84

        Purpose: Lists font files below the given folders.
        Parameters: folders, directories to search recursively; missing ones are ignored.
        Returns: sorted unique file paths.
        Raises: nothing.
        Called from: FontScanner.scan (#85).
        Calls: Path.rglob.
        """
        files: set[Path] = set()
        for folder in folders:
            if folder.is_dir():
                files.update(p for p in folder.rglob("*") if p.suffix.lower() in FONT_SUFFIXES and p.is_file())
        return sorted(files)

    @staticmethod
    def scan(
        folders: Iterable[Path],
        cache_file: Path | None = None,
        progress: Callable[[int, int], None] | None = None,
        cancelled: Callable[[], bool] | None = None,
    ) -> ScanReport:
        """class:FontScanner--method:scan--#85

        Purpose: Reads all font files, using the cache for unchanged files.
        Parameters: folders, where to look; cache_file, optional JSON cache path;
            progress, called with (done, total); cancelled, returns True to stop.
        Returns: a ScanReport.
        Raises: CancelledError if cancelled() becomes True.
        Called from: FontLibraryController.rescan (#69).
        Calls: FontScanner.find_files (#84), FontCache.get (#80), FontCache.put (#81), FontFileReader.read (#74).
        """
        files = FontScanner.find_files(folders)
        cache, report, seen = FontCache(cache_file), ScanReport(), set()
        for done, path in enumerate(files, start=1):
            if cancelled and cancelled():
                raise CancelledError("Font scan cancelled.")
            try:
                signature = FontCache.signature(path)
                faces = cache.get(signature)
                if faces is None:
                    faces = FontFileReader.read(path)
                    cache.put(signature, faces)
            except Exception as error:  # noqa: BLE001 - any damaged font must not stop the scan
                FONT_LOG.warning("Skipping font %s: %s", path, error)
                report.skipped.append((path.name, str(error) or type(error).__name__))
                faces = []
            for face in faces:
                if face.key() not in seen:
                    seen.add(face.key())
                    report.candidates.append(face)
            if progress:
                progress(done, len(files))
        cache.save()
        return report
