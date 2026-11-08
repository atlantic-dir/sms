"""Sets up the log file. Text typed by the user and file contents are never written to it."""

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

from PyQt6.QtCore import QStandardPaths


class LogSetup:
    """class:LogSetup--#115

    Purpose: Creates the rotating log file used to record technical details of errors.
    Parameters: none (all methods are static).
    Raises: nothing.
    Called from: Application.run (#10), MainWindow._open_log_folder (#142).
    Calls: logging.
    """

    @staticmethod
    def folder() -> Path:
        """class:LogSetup--method:folder--#116

        Purpose: Gives the folder that holds the log file.
        Parameters: none.
        Returns: a path inside the user's application-data folder.
        Raises: nothing.
        Called from: LogSetup.configure (#117), MainWindow._open_log_folder (#142).
        Calls: QStandardPaths.writableLocation.
        """
        return Path(QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppDataLocation)) / "logs"

    @staticmethod
    def configure() -> None:
        """class:LogSetup--method:configure--#117

        Purpose: Starts logging to a size-limited file (and to the console when there is one); if the folder is not
            writable, logging goes to the console only.
        Parameters: none.
        Returns: nothing.
        Raises: nothing.
        Called from: Application.run (#10).
        Calls: LogSetup.folder (#116), RotatingFileHandler.
        """
        # A windowed Windows .exe has no console, so sys.stderr is None there.
        handlers: list[logging.Handler] = [logging.StreamHandler()] if sys.stderr is not None else []
        try:
            folder = LogSetup.folder()
            folder.mkdir(parents=True, exist_ok=True)
            handlers.append(RotatingFileHandler(folder / "fontsleuth.log", maxBytes=500_000, backupCount=2, encoding="utf-8"))
        except OSError:
            logging.getLogger("fontsleuth").warning("Log folder is not writable; logging to the console only.")
        logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s", handlers=handlers)
