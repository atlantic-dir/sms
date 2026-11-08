"""Widgets that show the outcome of an analysis."""

import logging

from PyQt6.QtCore import QAbstractTableModel, QModelIndex, QRectF, QSize, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QPainter, QPixmap
from PyQt6.QtWidgets import (
    QApplication, QFormLayout, QFrame, QGroupBox, QHBoxLayout, QHeaderView, QLabel, QPushButton, QSizePolicy,
    QTableView, QVBoxLayout, QWidget,
)

from fontsleuth.models import AnalysisResult, Rgb, StyleFinding
from fontsleuth.preview import PreviewRenderer
from fontsleuth.qt_images import ImageConverter
from fontsleuth.theme import Theme

RESULT_LOG = logging.getLogger("fontsleuth.results")


class ResultFormatter:
    """class:ResultFormatter--#158

    Purpose: Turns findings into the text shown in the headline and copied to the clipboard.
    Parameters: none (all methods are static).
    Raises: nothing.
    Called from: ResultPanel.show_finding (#187), ResultPanel.copy_summary (#189).
    Calls: nothing.
    """

    @staticmethod
    def size_text(finding: StyleFinding, dpi: float | None) -> str:
        """class:ResultFormatter--method:size_text--#159

        Purpose: Describes the size in points, and in pixels when it was measured from a picture.
        Parameters: finding, the style; dpi, the resolution used for the conversion.
        Returns: text such as "11.0 pt (14.7 px at 96 DPI)".
        Raises: nothing.
        Called from: ResultPanel.show_finding (#187), CandidateTableModel.data (#167), ResultFormatter.summary (#161).
        Calls: nothing.
        """
        if finding.size_pt is None:
            return "unknown"
        if finding.size_px is None:
            return f"{finding.size_pt:g} pt"
        return f"{finding.size_pt:.1f} pt ({finding.size_px:.1f} px at {dpi:g} DPI)"

    @staticmethod
    def headline(finding: StyleFinding) -> str:
        """class:ResultFormatter--method:headline--#160

        Purpose: Builds the one-line answer.
        Parameters: finding, the style.
        Returns: text such as "Calibri Bold - 11.0 pt - #1F3A5F".
        Raises: nothing.
        Called from: ResultPanel.show_finding (#187).
        Calls: Rgb.hex (#145).
        """
        size = "?" if finding.size_pt is None else f"{finding.size_pt:g} pt"
        color = finding.color.hex() if finding.color else "?"
        return f"{finding.family} {finding.style_name} – {size} – {color}"

    @staticmethod
    def summary(result: AnalysisResult, finding: StyleFinding) -> str:
        """class:ResultFormatter--method:summary--#161

        Purpose: Builds the multi-line text copied to the clipboard.
        Parameters: result, the whole analysis; finding, the selected row.
        Returns: lines of "Label: value".
        Raises: nothing.
        Called from: ResultPanel.copy_summary (#189).
        Calls: ResultFormatter.size_text (#159), StyleFinding.weight_label (#151), Rgb.hex (#145).
        """
        color = finding.color
        lines = [
            f"Font: {finding.family}",
            f"Style: {finding.style_name}",
            f"Weight: {finding.weight_label()}",
            f"Italic: {'yes' if finding.italic else 'no'}",
            f"Size: {ResultFormatter.size_text(finding, result.dpi)}",
            f"Color: {color.hex()} (RGB {color.r}, {color.g}, {color.b})" if color else "Color: unknown",
            "Source: exact, read from the PDF's text data" if result.kind == "exact"
            else f"Source: estimated from pixels (match score {finding.score}, confidence {result.confidence})",
        ]
        return "\n".join(lines)


class CandidateTableModel(QAbstractTableModel):
    """class:CandidateTableModel--#162

    Purpose: Feeds the ranked list of styles into a QTableView.
    Parameters: parent, the owning QObject.
    Raises: nothing.
    Called from: ResultPanel.__init__ (#181).
    Calls: QAbstractTableModel.
    """

    HEADERS = ["Font", "Weight", "Size", "Color", "Match"]

    def __init__(self, parent=None) -> None:
        """class:CandidateTableModel--method:__init__--#163

        Purpose: Starts empty.
        Parameters: parent, the owning QObject.
        Returns: nothing.
        Raises: nothing.
        Called from: ResultPanel.__init__ (#181).
        Calls: QAbstractTableModel.
        """
        super().__init__(parent)
        self._findings: list[StyleFinding] = []
        self._dpi: float | None = None

    def set_findings(self, findings: list[StyleFinding], dpi: float | None) -> None:
        """class:CandidateTableModel--method:set_findings--#164

        Purpose: Replaces the rows.
        Parameters: findings, the styles (best first); dpi, for size text.
        Returns: nothing.
        Raises: nothing.
        Called from: ResultPanel.show_result (#185).
        Calls: nothing.
        """
        self.beginResetModel()
        self._findings, self._dpi = list(findings), dpi
        self.endResetModel()

    def rowCount(self, parent=QModelIndex()) -> int:
        """class:CandidateTableModel--method:rowCount--#165

        Purpose: Number of rows.
        Parameters: parent, ignored for a flat table.
        Returns: the row count.
        Raises: nothing.
        Called from: Qt view.
        Calls: nothing.
        """
        return 0 if parent.isValid() else len(self._findings)

    def columnCount(self, parent=QModelIndex()) -> int:
        """class:CandidateTableModel--method:columnCount--#166

        Purpose: Number of columns.
        Parameters: parent, ignored for a flat table.
        Returns: the column count.
        Raises: nothing.
        Called from: Qt view.
        Calls: nothing.
        """
        return 0 if parent.isValid() else len(self.HEADERS)

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole):
        """class:CandidateTableModel--method:data--#167

        Purpose: Supplies the text, colour swatch and tooltip for a cell.
        Parameters: index, the cell; role, the Qt data role.
        Returns: the value for the role, or None.
        Raises: nothing.
        Called from: Qt view.
        Calls: ResultFormatter.size_text (#159), StyleFinding.weight_label (#151), Rgb.hex (#145).
        """
        if not index.isValid():
            return None
        finding = self._findings[index.row()]
        if role == Qt.ItemDataRole.DisplayRole:
            return self._text(finding, index.column())
        if role == Qt.ItemDataRole.DecorationRole and index.column() == 3 and finding.color:
            return QColor(*finding.color.as_tuple())
        if role == Qt.ItemDataRole.ToolTipRole:
            return finding.note or self._text(finding, index.column())
        return None

    def _text(self, finding: StyleFinding, column: int) -> str:
        """class:CandidateTableModel--method:_text--#168

        Purpose: Formats one cell's text.
        Parameters: finding, the row's style; column, the column number.
        Returns: the display text.
        Raises: nothing.
        Called from: CandidateTableModel.data (#167).
        Calls: ResultFormatter.size_text (#159), StyleFinding.weight_label (#151), Rgb.hex (#145).
        """
        if column == 0:
            return f"{finding.family} {finding.style_name}"
        if column == 1:
            return f"{finding.weight_label()}"
        if column == 2:
            return f"{finding.size_pt:g} pt" if finding.size_pt is not None else "?"
        if column == 3:
            return finding.color.hex() if finding.color else "?"
        return "Exact" if finding.score is None else f"{finding.score:.2f}"

    def headerData(self, section: int, orientation, role: int = Qt.ItemDataRole.DisplayRole):
        """class:CandidateTableModel--method:headerData--#169

        Purpose: Supplies column titles.
        Parameters: section, the column; orientation, horizontal or vertical; role, the Qt role.
        Returns: the title for horizontal headers, otherwise None.
        Raises: nothing.
        Called from: Qt view.
        Calls: nothing.
        """
        if role == Qt.ItemDataRole.DisplayRole and orientation == Qt.Orientation.Horizontal:
            return self.HEADERS[section]
        return None

    def finding(self, row: int) -> StyleFinding | None:
        """class:CandidateTableModel--method:finding--#170

        Purpose: Returns the style in a row.
        Parameters: row, the row number.
        Returns: the StyleFinding, or None when out of range.
        Raises: nothing.
        Called from: ResultPanel.show_finding (#187).
        Calls: nothing.
        """
        return self._findings[row] if 0 <= row < len(self._findings) else None


class SwatchLabel(QFrame):
    """class:SwatchLabel--#171

    Purpose: A small square that shows a colour.
    Parameters: parent, the owning widget.
    Raises: nothing.
    Called from: ResultPanel.__init__ (#181).
    Calls: QFrame.
    """

    def __init__(self, parent=None) -> None:
        """class:SwatchLabel--method:__init__--#172

        Purpose: Sizes the swatch relative to the font so it scales with the screen.
        Parameters: parent, the owning widget.
        Returns: nothing.
        Raises: nothing.
        Called from: ResultPanel.__init__ (#181).
        Calls: QFrame.
        """
        super().__init__(parent)
        side = self.fontMetrics().height() * 2
        self.setMinimumSize(side, side)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.set_color(None)

    def set_color(self, color: Rgb | None) -> None:
        """class:SwatchLabel--method:set_color--#173

        Purpose: Paints the swatch (hatched grey when there is no colour).
        Parameters: color, the colour or None.
        Returns: nothing.
        Raises: nothing.
        Called from: ResultPanel.show_finding (#187), SwatchLabel.__init__ (#172).
        Calls: Rgb.hex (#145).
        """
        fill = color.hex() if color else "#E8EBF2"
        self.setStyleSheet(f"background: {fill}; border: 1px solid {Theme.BORDER}; border-radius: 4px;")
        self.setAccessibleName(f"Text colour {fill}" if color else "No colour")


class PixmapView(QWidget):
    """class:PixmapView--#174

    Purpose: Draws a picture scaled to fit its space while keeping the aspect ratio.
    Parameters: parent, the owning widget.
    Raises: nothing.
    Called from: ResultPanel.__init__ (#181).
    Calls: QWidget.
    """

    def __init__(self, parent=None) -> None:
        """class:PixmapView--method:__init__--#175

        Purpose: Starts empty with a flexible size policy.
        Parameters: parent, the owning widget.
        Returns: nothing.
        Raises: nothing.
        Called from: ResultPanel.__init__ (#181).
        Calls: QWidget.
        """
        super().__init__(parent)
        self._pixmap: QPixmap | None = None
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

    def set_pixmap(self, pixmap: QPixmap | None) -> None:
        """class:PixmapView--method:set_pixmap--#176

        Purpose: Replaces the picture and repaints.
        Parameters: pixmap, the new picture or None to clear.
        Returns: nothing.
        Raises: nothing.
        Called from: ResultPanel.show_finding (#187), ResultPanel.clear (#183).
        Calls: nothing.
        """
        self._pixmap = pixmap
        self.updateGeometry()
        self.update()

    def sizeHint(self) -> QSize:
        """class:PixmapView--method:sizeHint--#177

        Purpose: Suggests a height proportional to the font so previews stay readable.
        Parameters: none.
        Returns: the preferred size.
        Raises: nothing.
        Called from: Qt layout.
        Calls: nothing.
        """
        return QSize(self.fontMetrics().height() * 14, self.fontMetrics().height() * 4)

    def minimumSizeHint(self) -> QSize:
        """class:PixmapView--method:minimumSizeHint--#178

        Purpose: Allows the preview to shrink when the window is small.
        Parameters: none.
        Returns: the smallest useful size.
        Raises: nothing.
        Called from: Qt layout.
        Calls: nothing.
        """
        return QSize(self.fontMetrics().height() * 4, self.fontMetrics().height() * 2)

    def paintEvent(self, event) -> None:
        """class:PixmapView--method:paintEvent--#179

        Purpose: Draws a border and the scaled picture centred inside it.
        Parameters: event, the QPaintEvent.
        Returns: nothing.
        Raises: nothing.
        Called from: Qt event loop.
        Calls: QPainter.
        """
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        painter.setPen(QColor(Theme.BORDER))
        painter.drawRect(self.rect().adjusted(0, 0, -1, -1))
        if self._pixmap is None or self._pixmap.isNull():
            return
        box = QRectF(self.rect().adjusted(1, 1, -1, -1))
        scale = min(box.width() / self._pixmap.width(), box.height() / self._pixmap.height())
        target = QRectF(0, 0, self._pixmap.width() * scale, self._pixmap.height() * scale)
        target.moveCenter(box.center())
        painter.drawPixmap(target, self._pixmap, QRectF(self._pixmap.rect()))


class ResultPanel(QWidget):
    """class:ResultPanel--#180

    Purpose: Shows the headline answer, details, ranked alternatives, warnings and a visual comparison.
    Parameters: parent, the owning widget.
    Raises: nothing.
    Called from: MainWindow.__init__ (#119).
    Calls: CandidateTableModel (#162), PixmapView (#174), SwatchLabel (#171), PreviewRenderer.render (#154).
    """

    statusMessage = pyqtSignal(str)

    def __init__(self, parent=None) -> None:
        """class:ResultPanel--method:__init__--#181

        Purpose: Builds the layout: placeholder, headline, details, table, preview and copy button.
        Parameters: parent, the owning widget.
        Returns: nothing.
        Raises: nothing.
        Called from: MainWindow.__init__ (#119).
        Calls: ResultPanel._build_content (#182).
        """
        super().__init__(parent)
        self._result: AnalysisResult | None = None
        self._placeholder = QLabel("Results will appear here after you press Analyze.")
        self._placeholder.setProperty("role", "hint")
        self._placeholder.setWordWrap(True)
        self._message = QLabel()
        self._message.setWordWrap(True)
        self._message.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self._content = self._build_content()
        self._content.hide()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        for widget in (self._placeholder, self._message, self._content):
            layout.addWidget(widget)
        self._message.hide()

    def _build_content(self) -> QWidget:
        """class:ResultPanel--method:_build_content--#182

        Purpose: Creates the widgets that are visible once a result exists.
        Parameters: none.
        Returns: the container widget.
        Raises: nothing.
        Called from: ResultPanel.__init__ (#181).
        Calls: CandidateTableModel (#162), SwatchLabel (#171), PixmapView (#174).
        """
        box = QWidget()
        layout = QVBoxLayout(box)
        layout.setContentsMargins(0, 0, 0, 0)
        head = QHBoxLayout()
        self._swatch = SwatchLabel()
        self._headline = QLabel()
        self._headline.setProperty("role", "headline")
        self._headline.setWordWrap(True)
        self._headline.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        head.addWidget(self._swatch)
        head.addWidget(self._headline, 1)
        self._confidence = QLabel()
        self._confidence.setWordWrap(True)
        self._warnings = QLabel()
        self._warnings.setWordWrap(True)
        self._warnings.setProperty("role", "warning")
        self._details = QFormLayout()
        self._detail_labels = {name: QLabel() for name in ("Font", "Style", "Weight", "Italic", "Size", "Color", "Source")}
        for name, label in self._detail_labels.items():
            label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            label.setWordWrap(True)
            self._details.addRow(name + ":", label)
        self._model = CandidateTableModel(self)
        self._table = QTableView()
        self._table.setModel(self._model)
        self._table.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QTableView.SelectionMode.SingleSelection)
        header = self._table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self._table.verticalHeader().hide()
        self._table.setAccessibleName("Alternative matches, best first")
        self._table.setMinimumHeight(self._table.fontMetrics().height() * 7)
        self._table.setEditTriggers(QTableView.EditTrigger.NoEditTriggers)
        self._table.selectionModel().currentRowChanged.connect(lambda current, _prev: self.show_finding(current.row()))
        self._compare = QGroupBox("Compare by eye")
        compare_layout = QVBoxLayout(self._compare)
        self._original_view, self._match_view = PixmapView(), PixmapView()
        for caption, view in (("Your picture", self._original_view), ("Selected row, redrawn", self._match_view)):
            label = QLabel(caption)
            label.setProperty("role", "hint")
            compare_layout.addWidget(label)
            compare_layout.addWidget(view)
        self._copy = QPushButton("Copy result")
        self._copy.setToolTip("Copy the selected row as text (Ctrl+Shift+C)")
        self._copy.clicked.connect(self.copy_summary)
        layout.addLayout(head)
        layout.addWidget(self._confidence)
        layout.addWidget(self._warnings)
        layout.addLayout(self._details)
        layout.addWidget(QLabel("All matches (click a row to inspect it):"))
        layout.addWidget(self._table)
        layout.addWidget(self._compare)
        layout.addWidget(self._copy, 0, Qt.AlignmentFlag.AlignLeft)
        return box

    def clear(self) -> None:
        """class:ResultPanel--method:clear--#183

        Purpose: Returns to the empty state.
        Parameters: none.
        Returns: nothing.
        Raises: nothing.
        Called from: MainWindow._show_page (#130), MainWindow._close_source (#129).
        Calls: PixmapView.set_pixmap (#176).
        """
        self._result = None
        self._content.hide()
        self._message.hide()
        self._placeholder.show()
        self._original_view.set_pixmap(None)
        self._match_view.set_pixmap(None)

    def show_error(self, message: str) -> None:
        """class:ResultPanel--method:show_error--#184

        Purpose: Shows what went wrong and what to do, in place of results.
        Parameters: message, a plain-language explanation.
        Returns: nothing.
        Raises: nothing.
        Called from: MainWindow._on_job_failed (#135).
        Calls: nothing.
        """
        self.clear()
        self._placeholder.hide()
        self._message.setProperty("role", "error")
        self._message.style().unpolish(self._message)
        self._message.style().polish(self._message)
        self._message.setText(message)
        self._message.show()

    def show_result(self, result: AnalysisResult) -> None:
        """class:ResultPanel--method:show_result--#185

        Purpose: Displays a finished analysis and selects the best row.
        Parameters: result, the analysis.
        Returns: nothing.
        Raises: nothing.
        Called from: MainWindow._on_job_succeeded (#134).
        Calls: CandidateTableModel.set_findings (#164), ResultPanel.show_finding (#187).
        """
        self._result = result
        self._placeholder.hide()
        self._message.hide()
        self._model.set_findings(result.findings, result.dpi)
        self._confidence.setText(self._confidence_text(result))
        self._confidence.setProperty("role", {"Exact": "success", "High": "success", "Medium": "warning"}.get(result.confidence, "error"))
        self._confidence.style().unpolish(self._confidence)
        self._confidence.style().polish(self._confidence)
        self._warnings.setText("\n".join("• " + w for w in result.warnings))
        self._warnings.setVisible(bool(result.warnings))
        self._compare.setVisible(result.kind == "estimated")
        self._table.setColumnHidden(3, result.kind == "estimated")  # colour is the same on every estimated row
        self._content.show()
        self._table.selectRow(0)
        self.show_finding(0)

    @staticmethod
    def _confidence_text(result: AnalysisResult) -> str:
        """class:ResultPanel--method:_confidence_text--#186

        Purpose: Words the confidence line.
        Parameters: result, the analysis.
        Returns: a sentence about how trustworthy the result is.
        Raises: nothing.
        Called from: ResultPanel.show_result (#185).
        Calls: nothing.
        """
        if result.kind == "exact":
            return "Exact: read directly from the PDF's text data, not guessed."
        closest = "closest installed font" if result.confidence != "High" else "best installed font"
        return f"Estimated from pixels – confidence: {result.confidence}. Shown: the {closest}; colour is also estimated."

    def show_finding(self, row: int) -> None:
        """class:ResultPanel--method:show_finding--#187

        Purpose: Fills the headline, details and comparison for one row.
        Parameters: row, the row number.
        Returns: nothing.
        Raises: nothing.
        Called from: ResultPanel.show_result (#185), the table's selection signal.
        Calls: ResultFormatter.headline (#160), ResultFormatter.size_text (#159), PreviewRenderer.render (#154).
        """
        finding = self._model.finding(row)
        if finding is None or self._result is None:
            return
        self._headline.setText(ResultFormatter.headline(finding))
        self._swatch.set_color(finding.color)
        color = finding.color
        values = {
            "Font": finding.family, "Style": finding.style_name, "Weight": finding.weight_label(),
            "Italic": "Yes" if finding.italic else "No",
            "Size": ResultFormatter.size_text(finding, self._result.dpi),
            "Color": f"{color.hex()}  (RGB {color.r}, {color.g}, {color.b})" if color else "unknown",
            "Source": finding.note or ("Exact" if self._result.kind == "exact" else "Estimated from pixels"),
        }
        for name, value in values.items():
            self._detail_labels[name].setText(value)
        if self._result.kind == "estimated":
            self._show_comparison(finding)

    def _show_comparison(self, finding: StyleFinding) -> None:
        """class:ResultPanel--method:_show_comparison--#188

        Purpose: Shows the original crop and the selected font redrawn at the estimated size and colour.
        Parameters: finding, the selected estimated style.
        Returns: nothing.
        Raises: nothing (a font file that vanished is reported in the status bar instead).
        Called from: ResultPanel.show_finding (#187).
        Calls: PreviewRenderer.render (#154), ImageConverter.to_pixmap (#157).
        """
        result = self._result
        self._original_view.set_pixmap(ImageConverter.to_pixmap(result.crop) if result.crop else None)
        try:
            image = PreviewRenderer.render(finding.candidate, result.text, finding.size_px, result.ink_color, result.background_color)
            self._match_view.set_pixmap(ImageConverter.to_pixmap(image))
        except OSError:
            RESULT_LOG.warning("Preview font unavailable: %s", finding.candidate.path, exc_info=True)
            self._match_view.set_pixmap(None)
            self.statusMessage.emit("That font file could not be opened to draw the preview.")

    def copy_summary(self) -> None:
        """class:ResultPanel--method:copy_summary--#189

        Purpose: Copies the selected row as text to the clipboard.
        Parameters: none.
        Returns: nothing.
        Raises: nothing.
        Called from: the Copy button, MainWindow._build_actions (#122).
        Calls: ResultFormatter.summary (#161).
        """
        row = self._table.currentIndex().row()
        finding = self._model.finding(max(row, 0))
        if finding is None or self._result is None:
            self.statusMessage.emit("Nothing to copy yet. Analyze some text first.")
            return
        QApplication.clipboard().setText(ResultFormatter.summary(self._result, finding))
        self.statusMessage.emit("Result copied to the clipboard.")

    def has_result(self) -> bool:
        """class:ResultPanel--method:has_result--#190

        Purpose: Tells whether a result is displayed.
        Parameters: none.
        Returns: True when results are showing.
        Raises: nothing.
        Called from: MainWindow._update_actions (#125).
        Calls: nothing.
        """
        return self._result is not None
