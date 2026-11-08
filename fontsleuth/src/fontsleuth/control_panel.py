"""The numbered steps on the right-hand side: open, select, type, analyse."""

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QGroupBox, QHBoxLayout, QLabel, QLineEdit, QProgressBar, QPushButton, QSpinBox, QVBoxLayout, QWidget,
)

from fontsleuth.sources import Rect


class ControlPanel(QWidget):
    """class:ControlPanel--#41

    Purpose: Holds the controls for the three steps and the Analyze / Cancel buttons with a progress bar.
    Parameters: parent, the owning widget.
    Raises: nothing.
    Called from: MainWindow.__init__ (#119).
    Calls: Qt widgets.
    """

    openRequested = pyqtSignal()
    analyzeRequested = pyqtSignal()
    cancelRequested = pyqtSignal()
    selectAllRequested = pyqtSignal()
    clearRequested = pyqtSignal()
    pageChanged = pyqtSignal(int)  # zero-based

    def __init__(self, parent=None) -> None:
        """class:ControlPanel--method:__init__--#42

        Purpose: Builds the three step boxes and the action row.
        Parameters: parent, the owning widget.
        Returns: nothing.
        Raises: nothing.
        Called from: MainWindow.__init__ (#119).
        Calls: ControlPanel._file_box (#43), ControlPanel._select_box (#44), ControlPanel._text_box (#45), ControlPanel._action_row (#46).
        """
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._file_box())
        layout.addWidget(self._select_box())
        layout.addWidget(self._text_box())
        layout.addLayout(self._action_row())

    def _file_box(self) -> QGroupBox:
        """class:ControlPanel--method:_file_box--#43

        Purpose: Builds step 1: the open button, file name and page navigation.
        Parameters: none.
        Returns: the group box.
        Raises: nothing.
        Called from: ControlPanel.__init__ (#42).
        Calls: nothing.
        """
        box = QGroupBox("1. Open a picture or PDF")
        layout = QVBoxLayout(box)
        self._open = QPushButton("Open file…")
        self._open.setToolTip("Open a PNG, JPG, BMP, GIF, TIFF, WebP or PDF file (Ctrl+O)")
        self._open.clicked.connect(self.openRequested)
        self._file_label = QLabel("No file open")
        self._file_label.setProperty("role", "hint")
        self._file_label.setWordWrap(True)
        pages = QHBoxLayout()
        self._prev = QPushButton("◀")
        self._prev.setToolTip("Previous page (Page Up)")
        self._next = QPushButton("▶")
        self._next.setToolTip("Next page (Page Down)")
        self._page = QSpinBox()
        self._page.setPrefix("Page ")
        self._page.setMinimum(1)
        self._page.setAccessibleName("Page number")
        self._of = QLabel("")
        self._prev.clicked.connect(lambda: self._page.stepBy(-1))
        self._next.clicked.connect(lambda: self._page.stepBy(1))
        self._page.valueChanged.connect(lambda value: self.pageChanged.emit(value - 1))
        for widget in (self._prev, self._page, self._of, self._next):
            pages.addWidget(widget)
        pages.addStretch(1)
        self._page_row = [self._prev, self._page, self._of, self._next]
        layout.addWidget(self._open)
        layout.addWidget(self._file_label)
        layout.addLayout(pages)
        return box

    def _select_box(self) -> QGroupBox:
        """class:ControlPanel--method:_select_box--#44

        Purpose: Builds step 2: instructions and the selection read-out.
        Parameters: none.
        Returns: the group box.
        Raises: nothing.
        Called from: ControlPanel.__init__ (#42).
        Calls: nothing.
        """
        box = QGroupBox("2. Select one line of text")
        layout = QVBoxLayout(box)
        hint = QLabel("Drag a box around a single line of text in the picture. "
                      "Zoom with Ctrl + mouse wheel.")
        hint.setWordWrap(True)
        hint.setProperty("role", "hint")
        self._selection_label = QLabel("Nothing selected")
        self._selection_label.setWordWrap(True)
        buttons = QHBoxLayout()
        self._select_all = QPushButton("Select whole picture")
        self._select_all.setToolTip("Use the entire page, for a picture that is already cropped to the text (Ctrl+A)")
        self._clear = QPushButton("Clear")
        self._clear.setToolTip("Remove the selection (Ctrl+Shift+A)")
        self._select_all.clicked.connect(self.selectAllRequested)
        self._clear.clicked.connect(self.clearRequested)
        buttons.addWidget(self._select_all)
        buttons.addWidget(self._clear)
        buttons.addStretch(1)
        layout.addWidget(hint)
        layout.addWidget(self._selection_label)
        layout.addLayout(buttons)
        return box

    def _text_box(self) -> QGroupBox:
        """class:ControlPanel--method:_text_box--#45

        Purpose: Builds step 3: the text the picture shows and the resolution.
        Parameters: none.
        Returns: the group box.
        Raises: nothing.
        Called from: ControlPanel.__init__ (#42).
        Calls: nothing.
        """
        box = QGroupBox("3. Type what the selected text says")
        layout = QVBoxLayout(box)
        self._text = QLineEdit()
        self._text.setPlaceholderText("Type the words exactly as shown")
        self._text.setAccessibleName("Text shown in the selection")
        self._text.setToolTip("Needed to compare fonts in pictures. PDFs with real text do not need it.")
        self._text.returnPressed.connect(self.analyzeRequested)
        self._text.textChanged.connect(lambda _text: self.show_text_error(""))
        self._text_error = QLabel()
        self._text_error.setProperty("role", "error")
        self._text_error.setWordWrap(True)
        self._text_error.hide()
        dpi_row = QHBoxLayout()
        dpi_label = QLabel("Picture resolution:")
        self._dpi = QSpinBox()
        self._dpi.setRange(36, 1200)
        self._dpi.setSuffix(" DPI")
        self._dpi.setAccessibleName("Picture resolution in dots per inch")
        dpi_row.addWidget(dpi_label)
        dpi_row.addWidget(self._dpi)
        dpi_row.addStretch(1)
        self._dpi_hint = QLabel()
        self._dpi_hint.setProperty("role", "hint")
        self._dpi_hint.setWordWrap(True)
        for widget in (self._text, self._text_error):
            layout.addWidget(widget)
        layout.addLayout(dpi_row)
        layout.addWidget(self._dpi_hint)
        return box

    def _action_row(self) -> QVBoxLayout:
        """class:ControlPanel--method:_action_row--#46

        Purpose: Builds the Analyze / Cancel buttons and the progress bar.
        Parameters: none.
        Returns: the layout.
        Raises: nothing.
        Called from: ControlPanel.__init__ (#42).
        Calls: nothing.
        """
        layout = QVBoxLayout()
        row = QHBoxLayout()
        self._analyze = QPushButton("Analyze")
        self._analyze.setProperty("primary", True)
        self._analyze.setToolTip("Find the font, weight, size and colour (Ctrl+Enter)")
        self._analyze.clicked.connect(self.analyzeRequested)
        self._cancel = QPushButton("Cancel")
        self._cancel.setToolTip("Stop the analysis (Esc)")
        self._cancel.clicked.connect(self.cancelRequested)
        self._cancel.hide()
        row.addWidget(self._analyze, 1)
        row.addWidget(self._cancel)
        self._progress = QProgressBar()
        self._progress.hide()
        layout.addLayout(row)
        layout.addWidget(self._progress)
        return layout

    def set_file(self, name: str, page_count: int) -> None:
        """class:ControlPanel--method:set_file--#47

        Purpose: Shows the open file's name and sets up page navigation.
        Parameters: name, the file name ("" for none); page_count, the number of pages.
        Returns: nothing.
        Raises: nothing.
        Called from: MainWindow._open_path (#127), MainWindow._close_source (#129).
        Calls: nothing.
        """
        self._file_label.setText(name or "No file open")
        self._page.blockSignals(True)
        self._page.setMaximum(max(page_count, 1))
        self._page.setValue(1)
        self._page.blockSignals(False)
        self._of.setText(f"of {page_count}" if page_count else "")
        for widget in self._page_row:
            widget.setVisible(page_count > 1)

    def current_page(self) -> int:
        """class:ControlPanel--method:current_page--#48

        Purpose: Returns the page chosen in the page box.
        Parameters: none.
        Returns: a zero-based page index.
        Raises: nothing.
        Called from: MainWindow._start_analysis (#132).
        Calls: nothing.
        """
        return self._page.value() - 1

    def step_page(self, delta: int) -> None:
        """class:ControlPanel--method:step_page--#49

        Purpose: Moves to the previous or next page.
        Parameters: delta, -1 or +1.
        Returns: nothing.
        Raises: nothing.
        Called from: MainWindow._build_actions (#122).
        Calls: nothing.
        """
        self._page.stepBy(delta)

    def set_selection(self, rect: Rect | None) -> None:
        """class:ControlPanel--method:set_selection--#50

        Purpose: Shows the size of the selected box.
        Parameters: rect, (left, top, right, bottom) or None.
        Returns: nothing.
        Raises: nothing.
        Called from: MainWindow._on_selection_changed (#131).
        Calls: nothing.
        """
        self._selection_label.setProperty("role", "")
        if rect is None:
            self._selection_label.setText("Nothing selected yet")
        else:
            self._selection_label.setText(f"Selected: {rect[2] - rect[0]} × {rect[3] - rect[1]} pixels")

    def text(self) -> str:
        """class:ControlPanel--method:text--#51

        Purpose: Returns the text typed by the user.
        Parameters: none.
        Returns: the text.
        Raises: nothing.
        Called from: MainWindow._start_analysis (#132).
        Calls: nothing.
        """
        return self._text.text()

    def focus_text(self) -> None:
        """class:ControlPanel--method:focus_text--#52

        Purpose: Puts the cursor in the text box.
        Parameters: none.
        Returns: nothing.
        Raises: nothing.
        Called from: MainWindow._on_job_failed (#135).
        Calls: nothing.
        """
        self._text.setFocus()

    def show_text_error(self, message: str) -> None:
        """class:ControlPanel--method:show_text_error--#53

        Purpose: Shows (or clears) a validation message next to the text box, keeping what was typed.
        Parameters: message, the explanation, or "" to clear.
        Returns: nothing.
        Raises: nothing.
        Called from: MainWindow._on_job_failed (#135), ControlPanel._text_box (#45).
        Calls: nothing.
        """
        self._text_error.setText(message)
        self._text_error.setVisible(bool(message))
        self._text.setProperty("invalid", bool(message))
        self._text.style().unpolish(self._text)
        self._text.style().polish(self._text)

    def dpi(self) -> int:
        """class:ControlPanel--method:dpi--#54

        Purpose: Returns the resolution chosen for point-size conversion.
        Parameters: none.
        Returns: dots per inch.
        Raises: nothing.
        Called from: MainWindow._start_analysis (#132), MainWindow.closeEvent (#143).
        Calls: nothing.
        """
        return self._dpi.value()

    def set_dpi(self, value: int, editable: bool, note: str) -> None:
        """class:ControlPanel--method:set_dpi--#55

        Purpose: Sets the resolution box and explains where the number came from.
        Parameters: value, dots per inch; editable, False for PDFs (resolution is known); note, the explanation.
        Returns: nothing.
        Raises: nothing.
        Called from: MainWindow._open_path (#127).
        Calls: nothing.
        """
        self._dpi.setValue(value)
        self._dpi.setEnabled(editable)
        self._dpi_hint.setText(note)

    def set_busy(self, busy: bool, can_start: bool) -> None:
        """class:ControlPanel--method:set_busy--#56

        Purpose: Switches between the idle and working states (prevents duplicate runs).
        Parameters: busy, True while analysing; can_start, whether Analyze may be pressed when idle.
        Returns: nothing.
        Raises: nothing.
        Called from: MainWindow._update_actions (#125).
        Calls: nothing.
        """
        self._analyze.setEnabled(can_start and not busy)
        self._cancel.setVisible(busy)
        self._progress.setVisible(busy)
        for widget in (self._open, self._select_all, self._clear, self._text, *self._page_row):
            widget.setEnabled(not busy)

    def set_progress(self, done: int, total: int) -> None:
        """class:ControlPanel--method:set_progress--#57

        Purpose: Updates the progress bar.
        Parameters: done and total, work counts.
        Returns: nothing.
        Raises: nothing.
        Called from: MainWindow._start_analysis (#132).
        Calls: nothing.
        """
        self._progress.setRange(0, max(total, 1))
        self._progress.setValue(done)
