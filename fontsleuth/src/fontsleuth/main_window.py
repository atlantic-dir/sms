"""The application window: wires the canvas, controls, results and background jobs together."""

import logging
from pathlib import Path

from PyQt6.QtCore import QPoint, Qt, QTimer, QUrl
from PyQt6.QtGui import QAction, QCloseEvent, QDesktopServices, QKeySequence
from PyQt6.QtWidgets import (
    QFileDialog, QLabel, QMainWindow, QMessageBox, QProgressBar, QScrollArea, QSizePolicy, QSplitter, QVBoxLayout, QWidget,
)

from fontsleuth import __version__
from fontsleuth.analysis import AnalysisService
from fontsleuth.background import BackgroundJob
from fontsleuth.canvas import PageCanvas
from fontsleuth.control_panel import ControlPanel
from fontsleuth.errors import SourceError
from fontsleuth.font_controller import FontLibraryController
from fontsleuth.logging_setup import LogSetup
from fontsleuth.models import AnalysisResult
from fontsleuth.qt_images import ImageConverter
from fontsleuth.result_panel import ResultFormatter, ResultPanel
from fontsleuth.settings_store import AppSettings
from fontsleuth.sources import IMAGE_SUFFIXES, PDF_SUFFIXES, SourceFactory

WINDOW_LOG = logging.getLogger("fontsleuth.window")
HELP_TEXT = (
    "<h3>How to use Font Sleuth</h3><ol>"
    "<li><b>Open</b> a picture or PDF (or drop it on the window).</li>"
    "<li><b>Drag a box</b> around <i>one line</i> of text.</li>"
    "<li><b>Type</b> the words you see (not needed for PDFs that contain real text).</li>"
    "<li>Press <b>Analyze</b>.</li></ol>"
    "<p>For PDFs with real text the answer is <b>exact</b>. For pictures it is an <b>estimate</b>: "
    "the app compares your text against the fonts installed on this computer, so it can only name "
    "fonts it has. Use <i>Fonts &gt; Add font folder</i> to include more. Check the "
    "<i>Compare by eye</i> pictures before relying on a result.</p>"
    "<p>Larger, sharper pictures give better answers. Pixel sizes become points using the "
    "resolution (DPI) shown; screenshots are usually 96 DPI.</p>"
)


class MainWindow(QMainWindow):
    """class:MainWindow--#118

    Purpose: The main window; opens files, starts analyses and shows results.
    Parameters: settings, preferences store (default: the real one); scan_fonts, False in tests to skip scanning.
    Raises: nothing.
    Called from: Application.run (#10).
    Calls: PageCanvas (#20), ControlPanel (#41), ResultPanel (#180), FontLibraryController (#63), BackgroundJob (#14).
    """

    def __init__(self, settings: AppSettings | None = None, scan_fonts: bool = True) -> None:
        """class:MainWindow--method:__init__--#119

        Purpose: Builds the window, menus and status bar, restores the saved geometry and starts the font scan.
        Parameters: settings, preferences store; scan_fonts, whether to scan fonts now.
        Returns: nothing.
        Raises: nothing.
        Called from: Application.run (#10).
        Calls: MainWindow._build_layout (#120), MainWindow._build_actions (#122), MainWindow._build_status_bar (#123),
            FontLibraryController.rescan (#69).
        """
        super().__init__()
        self.setWindowTitle("Font Sleuth")
        self.settings = settings or AppSettings()
        self.source = None
        self._job: BackgroundJob | None = None
        self.fonts = FontLibraryController(self.settings, self)
        self._build_layout()
        self._build_actions()
        self._build_status_bar()
        self.controls.set_dpi(self.settings.dpi(), True, "")
        self.controls.set_file("", 0)
        self.fonts.progress.connect(self._on_fonts_progress)
        self.fonts.ready.connect(self._on_fonts_ready)
        self.fonts.failed.connect(lambda message: self._notify(message, error=True))
        if not self.restoreGeometry(self.settings.geometry()):
            self.resize(1200, 760)
        self._update_actions()
        if scan_fonts:
            self._status_label.setText("Reading installed fonts…")
            self.fonts.rescan()

    def _build_layout(self) -> None:
        """class:MainWindow--method:_build_layout--#120

        Purpose: Creates the canvas on the left and the controls and results (in a scroll area) on the right.
        Parameters: none.
        Returns: nothing.
        Raises: nothing.
        Called from: MainWindow.__init__ (#119).
        Calls: PageCanvas (#20), ControlPanel (#41), ResultPanel (#180).
        """
        self.canvas = PageCanvas()
        self.controls = ControlPanel()
        self.results = ResultPanel()
        side = QWidget()
        side_layout = QVBoxLayout(side)
        side_layout.addWidget(self.controls)
        side_layout.addWidget(self.results)
        side_layout.addStretch(1)
        scroll = self._scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(side)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(self.canvas)
        splitter.addWidget(scroll)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)
        splitter.setChildrenCollapsible(False)
        splitter.setSizes([60, 40])  # relative shares; Qt scales them to the real window width
        em = self.fontMetrics().height()
        self.canvas.setMinimumWidth(em * 18)
        scroll.setMinimumWidth(em * 24)
        scroll.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Expanding)
        self.setCentralWidget(splitter)
        self.canvas.selectionChanged.connect(self._on_selection_changed)
        self.canvas.fileDropped.connect(self._open_path)
        self.controls.openRequested.connect(self._choose_file)
        self.controls.analyzeRequested.connect(self._start_analysis)
        self.controls.cancelRequested.connect(self._cancel_analysis)
        self.controls.selectAllRequested.connect(self.canvas.select_all)
        self.controls.clearRequested.connect(self.canvas.clear_selection)
        self.controls.pageChanged.connect(self._show_page)
        self.results.statusMessage.connect(self._notify)

    def _action(self, text: str, slot, shortcuts: list[str]) -> QAction:
        """class:MainWindow--method:_action--#121

        Purpose: Creates a menu action whose label and tooltip show its shortcut.
        Parameters: text, the label; slot, what to call; shortcuts, key sequences (first is displayed).
        Returns: the action (also registered on the window so shortcuts work everywhere).
        Raises: nothing.
        Called from: MainWindow._build_actions (#122).
        Calls: QAction.
        """
        action = QAction(text, self)
        action.setShortcuts([QKeySequence(s) for s in shortcuts])
        action.setToolTip(f"{text.replace('&', '').rstrip('…')} ({shortcuts[0]})")
        action.triggered.connect(slot)
        self.addAction(action)
        return action

    def _build_actions(self) -> None:
        """class:MainWindow--method:_build_actions--#122

        Purpose: Creates all actions and the menu bar. Long only because it is a flat list of menu entries.
        Parameters: none.
        Returns: nothing.
        Raises: nothing.
        Called from: MainWindow.__init__ (#119).
        Calls: MainWindow._action (#121).
        """
        a = self._action
        self.act_open = a("&Open…", self._choose_file, ["Ctrl+O"])
        self.act_quit = a("&Quit", self.close, ["Ctrl+Q"])
        self.act_select_all = a("Select &whole picture", self.canvas.select_all, ["Ctrl+A"])
        self.act_clear = a("&Clear selection", self.canvas.clear_selection, ["Ctrl+Shift+A"])
        self.act_copy = a("Co&py result", self.results.copy_summary, ["Ctrl+Shift+C"])
        self.act_analyze = a("&Analyze selection", self._start_analysis, ["Ctrl+Return", "Ctrl+Enter"])
        self.act_cancel = a("Cancel analysis", self._cancel_analysis, ["Esc"])
        self.act_zoom_in = a("Zoom &in", lambda: self.canvas.zoom(1.25), ["Ctrl+=", "Ctrl++"])
        self.act_zoom_out = a("Zoom &out", lambda: self.canvas.zoom(0.8), ["Ctrl+-"])
        self.act_fit = a("&Fit to window", self.canvas.fit_page, ["Ctrl+0"])
        self.act_prev = a("&Previous page", lambda: self.controls.step_page(-1), ["PgUp"])
        self.act_next = a("&Next page", lambda: self.controls.step_page(1), ["PgDown"])
        self.act_add_fonts = a("&Add font folder…", self._add_font_folder, ["Ctrl+Shift+F"])
        self.act_rescan = a("&Rescan fonts", self.fonts.rescan, ["F5"])
        self.act_help = a("&How to use", self._show_help, ["F1"])
        self.act_log = a("Open &log folder", self._open_log_folder, ["Ctrl+Shift+L"])
        self.act_about = a("&About", self._show_about, ["Ctrl+Shift+F1"])
        bar = self.menuBar()
        for title, items in (
            ("&File", [self.act_open, None, self.act_quit]),
            ("&Edit", [self.act_select_all, self.act_clear, None, self.act_copy]),
            ("&Analyze", [self.act_analyze, self.act_cancel]),
            ("&View", [self.act_zoom_in, self.act_zoom_out, self.act_fit, None, self.act_prev, self.act_next]),
            ("F&onts", [self.act_add_fonts, self.act_rescan]),
            ("&Help", [self.act_help, self.act_log, self.act_about]),
        ):
            menu = bar.addMenu(title)
            for item in items:
                menu.addSeparator() if item is None else menu.addAction(item)

    def _build_status_bar(self) -> None:
        """class:MainWindow--method:_build_status_bar--#123

        Purpose: Adds a permanent font-count label and a progress bar for the font scan.
        Parameters: none.
        Returns: nothing.
        Raises: nothing.
        Called from: MainWindow.__init__ (#119).
        Calls: QStatusBar.
        """
        self._status_label = QLabel("")
        self._scan_progress = QProgressBar()
        self._scan_progress.setMaximumWidth(self.fontMetrics().height() * 12)
        self._scan_progress.hide()
        self.statusBar().addPermanentWidget(self._scan_progress)
        self.statusBar().addPermanentWidget(self._status_label)

    def _notify(self, message: str, error: bool = False) -> None:
        """class:MainWindow--method:_notify--#124

        Purpose: Shows a message in the status bar.
        Parameters: message, the text; error, True to log it as a warning too.
        Returns: nothing.
        Raises: nothing.
        Called from: many slots in this class.
        Calls: QStatusBar.showMessage.
        """
        if error:
            WINDOW_LOG.warning("Shown to user: %s", message)
        self.statusBar().showMessage(message, 15000)

    def _update_actions(self) -> None:
        """class:MainWindow--method:_update_actions--#125

        Purpose: Enables or disables actions and controls to match the current state (no file, busy, fonts loading).
        Parameters: none.
        Returns: nothing.
        Raises: nothing.
        Called from: most slots in this class.
        Calls: ControlPanel.set_busy (#56).
        """
        busy = self._job is not None
        has_page = self.canvas.has_page()
        fonts_ready = bool(self.fonts.candidates)
        self.controls.set_busy(busy, has_page and fonts_ready)
        for action in (self.act_open, self.act_select_all, self.act_clear, self.act_add_fonts, self.act_rescan,
                       self.act_prev, self.act_next):
            action.setEnabled(not busy)
        self.act_analyze.setEnabled(has_page and fonts_ready and not busy)
        self.act_cancel.setEnabled(busy)
        self.act_copy.setEnabled(self.results.has_result())
        for action in (self.act_zoom_in, self.act_zoom_out, self.act_fit):
            action.setEnabled(has_page)

    def _choose_file(self) -> None:
        """class:MainWindow--method:_choose_file--#126

        Purpose: Lets the user pick a file.
        Parameters: none.
        Returns: nothing.
        Raises: nothing.
        Called from: the Open action and button.
        Calls: MainWindow._open_path (#127).
        """
        patterns = " ".join("*" + s for s in IMAGE_SUFFIXES + PDF_SUFFIXES)
        chosen, _ = QFileDialog.getOpenFileName(
            self, "Open a picture or PDF", self.settings.last_folder(),
            f"Pictures and PDFs ({patterns});;All files (*)",
        )
        if chosen:
            self._open_path(chosen)

    def _open_path(self, path_text: str) -> None:
        """class:MainWindow--method:_open_path--#127

        Purpose: Opens a file, replacing the current one; the old file stays open if the new one fails.
        Parameters: path_text, the file path.
        Returns: nothing.
        Raises: nothing (SourceError is shown in a message box).
        Called from: MainWindow._choose_file (#126), the canvas drop signal.
        Calls: SourceFactory.open (#222), MainWindow._close_source (#129), MainWindow._show_page (#130).
        """
        if self._job is not None:
            self._notify("Wait for the analysis to finish (or cancel it) before opening another file.")
            return
        path = Path(path_text)
        try:
            source = SourceFactory.open(path)
        except SourceError as error:
            QMessageBox.warning(self, "Could not open the file", str(error))
            return
        self._close_source()
        self.source = source
        self.settings.set_last_folder(path.parent)
        self.controls.set_file(path.name, source.page_count)
        self._show_page(0)
        self._set_resolution(source)
        self._notify(f"Opened {path.name}.")

    def _set_resolution(self, source) -> None:
        """class:MainWindow--method:_set_resolution--#128

        Purpose: Fills the resolution box from the file (PDF: fixed; picture: stored value or the saved default).
        Parameters: source, the open file.
        Returns: nothing.
        Raises: nothing.
        Called from: MainWindow._open_path (#127).
        Calls: ControlPanel.set_dpi (#55).
        """
        if source.is_pdf:
            self.controls.set_dpi(int(source.ANALYSIS_DPI), False, "PDF pages have a known resolution, so no setting is needed.")
            return
        hint = source.dpi_hint()
        if hint:
            self.controls.set_dpi(round(hint), True, "Taken from the picture file. Change it if you know better.")
        else:
            self.controls.set_dpi(self.settings.dpi(), True,
                                  "The file does not say. 96 suits most screenshots on Windows; use 72 for older Macs. "
                                  "It only affects the point size, not the font.")

    def _close_source(self) -> None:
        """class:MainWindow--method:_close_source--#129

        Purpose: Closes the open file and returns the window to its empty state.
        Parameters: none.
        Returns: nothing.
        Raises: nothing.
        Called from: MainWindow._open_path (#127), MainWindow.closeEvent (#143).
        Calls: ImageSource.close (#209), PdfSource.close (#220), PageCanvas.clear_page (#23), ResultPanel.clear (#183).
        """
        if self.source is not None:
            self.source.close()
            self.source = None
        self.canvas.clear_page()
        self.results.clear()

    def _show_page(self, index: int) -> None:
        """class:MainWindow--method:_show_page--#130

        Purpose: Displays one page and clears the previous result.
        Parameters: index, the zero-based page number.
        Returns: nothing.
        Raises: nothing (SourceError is shown in a message box).
        Called from: MainWindow._open_path (#127), the page box signal.
        Calls: ImageSource.render_page (#204), PdfSource.render_page (#214), ImageConverter.to_qimage (#156).
        """
        if self.source is None:
            return
        try:
            page = self.source.render_page(index)
        except SourceError as error:
            QMessageBox.warning(self, "Could not show the page", str(error))
            return
        self.canvas.set_page(ImageConverter.to_qimage(page.image))
        self.results.clear()
        self._update_actions()

    def _on_selection_changed(self, rect) -> None:
        """class:MainWindow--method:_on_selection_changed--#131

        Purpose: Updates the selection read-out and the buttons.
        Parameters: rect, the selection or None.
        Returns: nothing.
        Raises: nothing.
        Called from: the canvas selectionChanged signal.
        Calls: ControlPanel.set_selection (#50).
        """
        self.controls.set_selection(rect)
        self._update_actions()

    def _start_analysis(self) -> None:
        """class:MainWindow--method:_start_analysis--#132

        Purpose: Validates the inputs and runs the analysis on a worker thread; ignores repeat clicks while busy.
        Parameters: none.
        Returns: nothing.
        Raises: nothing.
        Called from: the Analyze action, button and Enter key in the text box.
        Calls: AnalysisService.analyze (#5), BackgroundJob.start (#16).
        """
        if self._job is not None:
            return
        if self.source is None or not self.canvas.has_page():
            self._notify("Open a picture or PDF first (Ctrl+O).")
            return
        if not self.fonts.candidates:
            self._notify("Fonts are still being read. Try again in a moment.")
            return
        rect = self.canvas.selection()
        if rect is None:
            self._notify("Drag a box around one line of text first, or use 'Select whole picture'.", error=False)
            self.results.show_error("No text is selected yet. Drag a box around one line of text in the picture, "
                                    "then press Analyze.")
            return
        source, page, text, dpi = self.source, self.controls.current_page(), self.controls.text(), float(self.controls.dpi())
        candidates = list(self.fonts.candidates)
        self.controls.show_text_error("")
        self._job = BackgroundJob(
            lambda progress, cancelled: AnalysisService.analyze(
                source, page, rect, text, None if source.is_pdf else dpi, candidates, progress, cancelled),
            self,
        )
        self._job.progress.connect(self.controls.set_progress)
        self._job.succeeded.connect(self._on_job_succeeded)
        self._job.failed.connect(self._on_job_failed)
        self._job.cancelled.connect(lambda: self._notify("Analysis cancelled."))
        self._job.finished.connect(self._on_job_finished)
        self.controls.set_progress(0, 1)
        self._notify("Analyzing…")
        self._update_actions()
        self._job.start()

    def _cancel_analysis(self) -> None:
        """class:MainWindow--method:_cancel_analysis--#133

        Purpose: Asks the running analysis to stop.
        Parameters: none.
        Returns: nothing.
        Raises: nothing.
        Called from: the Cancel action and button.
        Calls: BackgroundJob.cancel (#17).
        """
        if self._job is not None:
            self._job.cancel()
            self._notify("Cancelling…")

    def _on_job_succeeded(self, result: AnalysisResult) -> None:
        """class:MainWindow--method:_on_job_succeeded--#134

        Purpose: Shows the result and a success message.
        Parameters: result, the finished analysis.
        Returns: nothing.
        Raises: nothing.
        Called from: BackgroundJob.succeeded signal.
        Calls: ResultPanel.show_result (#185), ResultFormatter.headline (#160).
        """
        self.results.show_result(result)
        QTimer.singleShot(0, self._scroll_to_results)
        self._notify("Done: " + ResultFormatter.headline(result.findings[0]))

    def _scroll_to_results(self) -> None:
        """class:MainWindow--method:_scroll_to_results--#237

        Purpose: Scrolls the side panel so the new result is at the top of the view (it sits below the controls).
        Parameters: none.
        Returns: nothing.
        Raises: nothing.
        Called from: MainWindow._on_job_succeeded (#134) (via a zero-delay timer, after the layout is updated).
        Calls: QScrollBar.setValue.
        """
        top = self.results.mapTo(self._scroll.widget(), QPoint(0, 0)).y()
        self._scroll.verticalScrollBar().setValue(max(top - 8, 0))

    def _on_job_failed(self, message: str, kind: str) -> None:
        """class:MainWindow--method:_on_job_failed--#135

        Purpose: Shows an error where the user will see it; missing text is flagged beside the text box.
        Parameters: message, the plain-language explanation; kind, the error class name.
        Returns: nothing.
        Raises: nothing.
        Called from: BackgroundJob.failed signal.
        Calls: ResultPanel.show_error (#184), ControlPanel.show_text_error (#53).
        """
        if kind == "MissingTextError":
            self.controls.show_text_error(message)
            self.controls.focus_text()
        self.results.show_error(message)
        self._notify("The analysis could not be completed.", error=True)

    def _on_job_finished(self) -> None:
        """class:MainWindow--method:_on_job_finished--#136

        Purpose: Frees the finished job and re-enables the controls.
        Parameters: none.
        Returns: nothing.
        Raises: nothing.
        Called from: BackgroundJob.finished signal.
        Calls: MainWindow._update_actions (#125).
        """
        if self._job is not None:
            self._job.deleteLater()
        self._job = None
        self._update_actions()

    def _on_fonts_progress(self, done: int, total: int) -> None:
        """class:MainWindow--method:_on_fonts_progress--#137

        Purpose: Shows the font-scan progress in the status bar.
        Parameters: done and total, file counts.
        Returns: nothing.
        Raises: nothing.
        Called from: FontLibraryController.progress signal.
        Calls: nothing.
        """
        self._scan_progress.show()
        self._scan_progress.setRange(0, max(total, 1))
        self._scan_progress.setValue(done)

    def _on_fonts_ready(self, count: int, skipped: int) -> None:
        """class:MainWindow--method:_on_fonts_ready--#138

        Purpose: Reports how many fonts are available and enables analysis.
        Parameters: count, usable font faces; skipped, unreadable files.
        Returns: nothing.
        Raises: nothing.
        Called from: FontLibraryController.ready signal.
        Calls: MainWindow._update_actions (#125).
        """
        self._scan_progress.hide()
        extra = f" ({skipped} unreadable files skipped; see the log)" if skipped else ""
        self._status_label.setText(f"{count} fonts available{extra}")
        if count == 0:
            self._notify("No fonts were found. Use Fonts > Add font folder to point the app at your fonts.", error=True)
        self._update_actions()

    def _add_font_folder(self) -> None:
        """class:MainWindow--method:_add_font_folder--#139

        Purpose: Lets the user include another folder of fonts in the search.
        Parameters: none.
        Returns: nothing.
        Raises: nothing.
        Called from: the Add font folder action.
        Calls: FontLibraryController.add_folder (#68).
        """
        folder = QFileDialog.getExistingDirectory(self, "Choose a folder that contains font files (.ttf, .otf)")
        if folder:
            self._status_label.setText("Reading fonts…")
            self.fonts.add_folder(Path(folder))

    def _show_help(self) -> None:
        """class:MainWindow--method:_show_help--#140

        Purpose: Shows short instructions.
        Parameters: none.
        Returns: nothing.
        Raises: nothing.
        Called from: the How to use action.
        Calls: QMessageBox.
        """
        QMessageBox.information(self, "How to use Font Sleuth", HELP_TEXT)

    def _show_about(self) -> None:
        """class:MainWindow--method:_show_about--#141

        Purpose: Shows the version.
        Parameters: none.
        Returns: nothing.
        Raises: nothing.
        Called from: the About action.
        Calls: QMessageBox.
        """
        QMessageBox.about(self, "About Font Sleuth", f"Font Sleuth {__version__}\nFinds the font, weight, size and colour of text.")

    def _open_log_folder(self) -> None:
        """class:MainWindow--method:_open_log_folder--#142

        Purpose: Opens the folder that holds the log file, for support.
        Parameters: none.
        Returns: nothing.
        Raises: nothing.
        Called from: the Open log folder action.
        Calls: LogSetup.folder (#116), QDesktopServices.openUrl.
        """
        folder = LogSetup.folder()
        folder.mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(folder)))

    def closeEvent(self, event: QCloseEvent) -> None:
        """class:MainWindow--method:closeEvent--#143

        Purpose: Cancels background work, waits for it to stop, saves preferences and closes the file.
        Parameters: event, the close event.
        Returns: nothing.
        Raises: nothing.
        Called from: Qt event loop.
        Calls: BackgroundJob.cancel (#17), FontLibraryController.stop (#70), AppSettings.set_geometry (#200).
        """
        if self._job is not None:
            self._job.cancel()
            self._job.wait()
        self.fonts.stop()
        self.settings.set_geometry(self.saveGeometry())
        self.settings.set_dpi(self.controls.dpi())
        self._close_source()
        super().closeEvent(event)
