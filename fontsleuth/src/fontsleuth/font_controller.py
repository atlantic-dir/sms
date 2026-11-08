"""Keeps the list of installed fonts up to date in the background."""

import os
from pathlib import Path

from PyQt6.QtCore import QObject, QStandardPaths, pyqtSignal

from fontsleuth.background import BackgroundJob
from fontsleuth.font_library import FontScanner, ScanReport
from fontsleuth.models import FontCandidate
from fontsleuth.settings_store import AppSettings


class FontLibraryController(QObject):
    """class:FontLibraryController--#63

    Purpose: Scans system and user-added font folders on a worker thread and exposes the faces found.
    Parameters: settings, the saved preferences; parent, the owning QObject.
    Raises: nothing.
    Called from: MainWindow.__init__ (#119).
    Calls: BackgroundJob (#14), FontScanner.scan (#85).
    """

    progress = pyqtSignal(int, int)
    ready = pyqtSignal(int, int)  # faces found, files skipped
    failed = pyqtSignal(str)

    def __init__(self, settings: AppSettings, parent: QObject | None = None) -> None:
        """class:FontLibraryController--method:__init__--#64

        Purpose: Prepares an empty library.
        Parameters: settings, the saved preferences; parent, the owning QObject.
        Returns: nothing.
        Raises: nothing.
        Called from: MainWindow.__init__ (#119).
        Calls: QObject.
        """
        super().__init__(parent)
        self._settings = settings
        self._job: BackgroundJob | None = None
        self.candidates: list[FontCandidate] = []
        self.skipped: list[tuple[str, str]] = []

    @staticmethod
    def system_folders() -> list[Path]:
        """class:FontLibraryController--method:system_folders--#65

        Purpose: Lists the folders where the operating system keeps fonts (including per-user fonts on Windows).
        Parameters: none.
        Returns: existing folder paths.
        Raises: nothing.
        Called from: FontLibraryController.rescan (#69).
        Calls: QStandardPaths.standardLocations.
        """
        found = [Path(p) for p in QStandardPaths.standardLocations(QStandardPaths.StandardLocation.FontsLocation)]
        local = os.environ.get("LOCALAPPDATA")
        if local:
            found.append(Path(local) / "Microsoft" / "Windows" / "Fonts")
        return [p for p in found if p.is_dir()]

    @staticmethod
    def cache_file() -> Path:
        """class:FontLibraryController--method:cache_file--#66

        Purpose: Gives the location of the font-scan cache.
        Parameters: none.
        Returns: a path inside the user's application-data folder.
        Raises: nothing.
        Called from: FontLibraryController.rescan (#69).
        Calls: QStandardPaths.writableLocation.
        """
        base = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppDataLocation)
        return Path(base) / "font-cache.json"

    def is_busy(self) -> bool:
        """class:FontLibraryController--method:is_busy--#67

        Purpose: Tells whether a scan is running.
        Parameters: none.
        Returns: True during a scan.
        Raises: nothing.
        Called from: MainWindow._update_actions (#125).
        Calls: BackgroundJob.is_running (#18).
        """
        return self._job is not None and self._job.is_running()

    def add_folder(self, folder: Path) -> None:
        """class:FontLibraryController--method:add_folder--#68

        Purpose: Remembers an extra font folder and rescans.
        Parameters: folder, the folder to add.
        Returns: nothing.
        Raises: nothing.
        Called from: MainWindow._add_font_folder (#139).
        Calls: AppSettings.set_font_folders (#196), FontLibraryController.rescan (#69).
        """
        folders = self._settings.font_folders()
        if str(folder) not in folders:
            self._settings.set_font_folders(folders + [str(folder)])
        self.rescan()

    def rescan(self) -> None:
        """class:FontLibraryController--method:rescan--#69

        Purpose: Starts a background scan (ignored if one is already running).
        Parameters: none.
        Returns: nothing.
        Raises: nothing.
        Called from: MainWindow.__init__ (#119), FontLibraryController.add_folder (#68), MainWindow._build_actions (#122).
        Calls: BackgroundJob.start (#16), FontScanner.scan (#85).
        """
        if self.is_busy():
            return
        folders = self.system_folders() + [Path(p) for p in self._settings.font_folders()]
        cache = self.cache_file()
        self._job = BackgroundJob(lambda progress, cancelled: FontScanner.scan(folders, cache, progress, cancelled), self)
        self._job.progress.connect(self.progress)
        self._job.succeeded.connect(self._on_scanned)
        self._job.failed.connect(lambda message, _kind: self.failed.emit(message))
        self._job.start()

    def stop(self) -> None:
        """class:FontLibraryController--method:stop--#70

        Purpose: Cancels a running scan and waits briefly for it to end (used when closing the window).
        Parameters: none.
        Returns: nothing.
        Raises: nothing.
        Called from: MainWindow.closeEvent (#143).
        Calls: BackgroundJob.cancel (#17), BackgroundJob.wait (#19).
        """
        if self._job is not None:
            self._job.cancel()
            self._job.wait()

    def _on_scanned(self, report: ScanReport) -> None:
        """class:FontLibraryController--method:_on_scanned--#71

        Purpose: Stores the scan results and announces them.
        Parameters: report, the finished ScanReport.
        Returns: nothing.
        Raises: nothing.
        Called from: BackgroundJob.succeeded signal.
        Calls: nothing.
        """
        self.candidates, self.skipped = report.candidates, report.skipped
        self.ready.emit(len(self.candidates), len(self.skipped))
