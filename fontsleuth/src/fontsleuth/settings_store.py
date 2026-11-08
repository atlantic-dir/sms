"""Saved user preferences (QSettings)."""

from pathlib import Path

from PyQt6.QtCore import QByteArray, QSettings


class AppSettings:
    """class:AppSettings--#191

    Purpose: Reads and writes the preferences that should survive a restart.
    Parameters: store, an optional QSettings (tests pass a temporary one).
    Raises: nothing.
    Called from: MainWindow.__init__ (#119), FontLibraryController.__init__ (#64).
    Calls: PyQt6.QtCore.QSettings.
    """

    def __init__(self, store: QSettings | None = None) -> None:
        """class:AppSettings--method:__init__--#192

        Purpose: Opens the settings store.
        Parameters: store, a QSettings or None for the default per-user store.
        Returns: nothing.
        Raises: nothing.
        Called from: MainWindow.__init__ (#119).
        Calls: QSettings.
        """
        self._store = store or QSettings("FontSleuth", "FontSleuth")

    def last_folder(self) -> str:
        """class:AppSettings--method:last_folder--#193

        Purpose: Returns the folder last used to open a file.
        Parameters: none.
        Returns: a folder path, or "" if none is stored.
        Raises: nothing.
        Called from: MainWindow._choose_file (#126).
        Calls: nothing.
        """
        return str(self._store.value("last_folder", "", type=str))

    def set_last_folder(self, folder: Path) -> None:
        """class:AppSettings--method:set_last_folder--#194

        Purpose: Remembers the folder of the file just opened.
        Parameters: folder, the folder path.
        Returns: nothing.
        Raises: nothing.
        Called from: MainWindow._open_path (#127).
        Calls: nothing.
        """
        self._store.setValue("last_folder", str(folder))

    def font_folders(self) -> list[str]:
        """class:AppSettings--method:font_folders--#195

        Purpose: Returns the extra font folders the user added.
        Parameters: none.
        Returns: a list of folder paths.
        Raises: nothing.
        Called from: FontLibraryController.rescan (#69).
        Calls: nothing.
        """
        value = self._store.value("font_folders", [], type=list)
        return [str(v) for v in value]

    def set_font_folders(self, folders: list[str]) -> None:
        """class:AppSettings--method:set_font_folders--#196

        Purpose: Stores the extra font folders.
        Parameters: folders, folder paths.
        Returns: nothing.
        Raises: nothing.
        Called from: FontLibraryController.add_folder (#68).
        Calls: nothing.
        """
        self._store.setValue("font_folders", folders)

    def dpi(self) -> int:
        """class:AppSettings--method:dpi--#197

        Purpose: Returns the last picture resolution the user chose.
        Parameters: none.
        Returns: dots per inch (default 96).
        Raises: nothing.
        Called from: MainWindow.__init__ (#119).
        Calls: nothing.
        """
        return int(self._store.value("dpi", 96, type=int))

    def set_dpi(self, dpi: int) -> None:
        """class:AppSettings--method:set_dpi--#198

        Purpose: Remembers the picture resolution.
        Parameters: dpi, dots per inch.
        Returns: nothing.
        Raises: nothing.
        Called from: MainWindow.closeEvent (#143).
        Calls: nothing.
        """
        self._store.setValue("dpi", dpi)

    def geometry(self) -> QByteArray:
        """class:AppSettings--method:geometry--#199

        Purpose: Returns the saved window geometry.
        Parameters: none.
        Returns: opaque bytes for QWidget.restoreGeometry (empty when none saved).
        Raises: nothing.
        Called from: MainWindow.__init__ (#119).
        Calls: nothing.
        """
        value = self._store.value("geometry")
        return value if isinstance(value, QByteArray) else QByteArray()

    def set_geometry(self, value: QByteArray) -> None:
        """class:AppSettings--method:set_geometry--#200

        Purpose: Saves the window geometry.
        Parameters: value, from QWidget.saveGeometry.
        Returns: nothing.
        Raises: nothing.
        Called from: MainWindow.closeEvent (#143).
        Calls: nothing.
        """
        self._store.setValue("geometry", value)
