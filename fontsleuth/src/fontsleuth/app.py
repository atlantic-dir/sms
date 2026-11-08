"""Program start-up."""

import logging
from pathlib import Path

from PyQt6.QtWidgets import QApplication

from fontsleuth.logging_setup import LogSetup
from fontsleuth.main_window import MainWindow
from fontsleuth.theme import Theme


class Application:
    """class:Application--#9

    Purpose: Creates the Qt application and main window and runs the event loop.
    Parameters: none (all methods are static).
    Raises: nothing.
    Called from: `fontsleuth.__main__` and the single-file build.
    Calls: LogSetup.configure (#117), MainWindow (#118), Theme.stylesheet (#230).
    """

    @staticmethod
    def run(argv: list[str]) -> int:
        """class:Application--method:run--#10

        Purpose: Starts the program; an optional first argument is a file to open.
        Parameters: argv, the command-line arguments.
        Returns: the process exit code.
        Raises: nothing.
        Called from: `fontsleuth.__main__`.
        Calls: LogSetup.configure (#117), Theme.stylesheet (#230), MainWindow.__init__ (#119), MainWindow._open_path (#127).
        """
        app = QApplication(argv)
        app.setApplicationName("FontSleuth")
        app.setOrganizationName("FontSleuth")
        app.setStyle("Fusion")
        LogSetup.configure()
        app.setStyleSheet(Theme.stylesheet())
        window = MainWindow()
        window.show()
        if len(argv) > 1 and Path(argv[1]).exists():
            window._open_path(argv[1])
        logging.getLogger("fontsleuth").info("Started")
        return app.exec()

