"""The picture area where the user drags a box around the text."""

from pathlib import Path

from PyQt6.QtCore import QPointF, QRectF, Qt, pyqtSignal
from PyQt6.QtGui import QBrush, QColor, QImage, QPainter, QPen, QPixmap
from PyQt6.QtWidgets import QGraphicsPixmapItem, QGraphicsRectItem, QGraphicsScene, QGraphicsView

from fontsleuth.sources import Rect
from fontsleuth.theme import Theme


class PageCanvas(QGraphicsView):
    """class:PageCanvas--#20

    Purpose: Shows one page, lets the user drag a selection rectangle, and zooms / scrolls the page.
    Parameters: parent, the owning widget.
    Raises: nothing.
    Called from: MainWindow.__init__ (#119).
    Calls: QGraphicsScene, QGraphicsPixmapItem, QGraphicsRectItem.
    """

    selectionChanged = pyqtSignal(object)  # Rect | None
    fileDropped = pyqtSignal(str)
    MIN_SELECTION = 4

    def __init__(self, parent=None) -> None:
        """class:PageCanvas--method:__init__--#21

        Purpose: Creates the scene and configures drawing, cursor and drag-and-drop.
        Parameters: parent, the owning widget.
        Returns: nothing.
        Raises: nothing.
        Called from: MainWindow.__init__ (#119).
        Calls: QGraphicsView.
        """
        super().__init__(parent)
        self.setScene(QGraphicsScene(self))
        self.setRenderHints(QPainter.RenderHint.SmoothPixmapTransform)
        self.setBackgroundBrush(QBrush(QColor("#DDE1EA")))
        self.setCursor(Qt.CursorShape.CrossCursor)
        self.setAcceptDrops(True)
        self.setAccessibleName("Page view. Drag with the mouse to select a line of text.")
        self._pixmap_item: QGraphicsPixmapItem | None = None
        self._selection_item: QGraphicsRectItem | None = None
        self._anchor: QPointF | None = None
        self._fit_mode = True

    def set_page(self, image: QImage) -> None:
        """class:PageCanvas--method:set_page--#22

        Purpose: Shows a new page, clearing any previous selection, and fits it to the window.
        Parameters: image, the page picture.
        Returns: nothing.
        Raises: nothing.
        Called from: MainWindow._show_page (#130).
        Calls: PageCanvas.clear_page (#23), PageCanvas.fit_page (#34).
        """
        self.clear_page()
        self._pixmap_item = self.scene().addPixmap(QPixmap.fromImage(image))
        self.scene().setSceneRect(QRectF(self._pixmap_item.pixmap().rect()))
        self.fit_page()

    def clear_page(self) -> None:
        """class:PageCanvas--method:clear_page--#23

        Purpose: Removes the page and selection (back to the empty state).
        Parameters: none.
        Returns: nothing.
        Raises: nothing.
        Called from: PageCanvas.set_page (#22), MainWindow._close_source (#129).
        Calls: nothing.
        """
        self.scene().clear()
        self._pixmap_item = self._selection_item = self._anchor = None
        self.selectionChanged.emit(None)
        self.viewport().update()

    def has_page(self) -> bool:
        """class:PageCanvas--method:has_page--#24

        Purpose: Tells whether a page is displayed.
        Parameters: none.
        Returns: True when a page is shown.
        Raises: nothing.
        Called from: MainWindow._update_actions (#125).
        Calls: nothing.
        """
        return self._pixmap_item is not None

    def selection(self) -> Rect | None:
        """class:PageCanvas--method:selection--#25

        Purpose: Returns the selected rectangle in page pixels.
        Parameters: none.
        Returns: (left, top, right, bottom) integers, or None when nothing is selected.
        Raises: nothing.
        Called from: MainWindow._start_analysis (#132).
        Calls: nothing.
        """
        if self._selection_item is None:
            return None
        r = self._selection_item.rect()
        return (int(r.left()), int(r.top()), int(r.right()), int(r.bottom()))

    def select_all(self) -> None:
        """class:PageCanvas--method:select_all--#26

        Purpose: Selects the whole page (the keyboard alternative to dragging, and handy for cropped snippets).
        Parameters: none.
        Returns: nothing.
        Raises: nothing.
        Called from: MainWindow._build_actions (#122).
        Calls: PageCanvas._set_selection (#28).
        """
        if self._pixmap_item is not None:
            self._set_selection(self.sceneRect())

    def clear_selection(self) -> None:
        """class:PageCanvas--method:clear_selection--#27

        Purpose: Removes the selection rectangle.
        Parameters: none.
        Returns: nothing.
        Raises: nothing.
        Called from: MainWindow._build_actions (#122).
        Calls: PageCanvas._set_selection (#28).
        """
        self._set_selection(None)

    def _set_selection(self, rect: QRectF | None) -> None:
        """class:PageCanvas--method:_set_selection--#28

        Purpose: Draws (or removes) the selection rectangle and announces the change.
        Parameters: rect, the rectangle in page pixels, or None.
        Returns: nothing.
        Raises: nothing.
        Called from: PageCanvas.select_all (#26), PageCanvas.clear_selection (#27), PageCanvas.mouseMoveEvent (#30),
            PageCanvas.mouseReleaseEvent (#31).
        Calls: QGraphicsRectItem.
        """
        if self._selection_item is not None:
            self.scene().removeItem(self._selection_item)
            self._selection_item = None
        if rect is not None:
            pen = QPen(QColor(Theme.ACCENT), 2)
            pen.setCosmetic(True)
            pen.setStyle(Qt.PenStyle.DashLine)
            self._selection_item = self.scene().addRect(rect, pen, QBrush(QColor(34, 80, 214, 40)))
        self.selectionChanged.emit(self.selection())

    def mousePressEvent(self, event) -> None:
        """class:PageCanvas--method:mousePressEvent--#29

        Purpose: Starts a new selection when the left button goes down on the page.
        Parameters: event, the QMouseEvent.
        Returns: nothing.
        Raises: nothing.
        Called from: Qt event loop.
        Calls: PageCanvas._clamped (#32).
        """
        if event.button() == Qt.MouseButton.LeftButton and self._pixmap_item is not None:
            self._anchor = self._clamped(self.mapToScene(event.position().toPoint()))
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:
        """class:PageCanvas--method:mouseMoveEvent--#30

        Purpose: Stretches the selection rectangle while the button is held.
        Parameters: event, the QMouseEvent.
        Returns: nothing.
        Raises: nothing.
        Called from: Qt event loop.
        Calls: PageCanvas._clamped (#32), PageCanvas._set_selection (#28).
        """
        if self._anchor is not None:
            point = self._clamped(self.mapToScene(event.position().toPoint()))
            self._set_selection(QRectF(self._anchor, point).normalized())
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        """class:PageCanvas--method:mouseReleaseEvent--#31

        Purpose: Ends the drag; a tiny accidental drag clears the selection.
        Parameters: event, the QMouseEvent.
        Returns: nothing.
        Raises: nothing.
        Called from: Qt event loop.
        Calls: PageCanvas._set_selection (#28).
        """
        if self._anchor is not None:
            self._anchor = None
            rect = self.selection()
            if rect and (rect[2] - rect[0] < self.MIN_SELECTION or rect[3] - rect[1] < self.MIN_SELECTION):
                self._set_selection(None)
            return
        super().mouseReleaseEvent(event)

    def _clamped(self, point: QPointF) -> QPointF:
        """class:PageCanvas--method:_clamped--#32

        Purpose: Keeps a point inside the page.
        Parameters: point, in scene coordinates.
        Returns: the nearest point on the page.
        Raises: nothing.
        Called from: PageCanvas.mousePressEvent (#29), PageCanvas.mouseMoveEvent (#30).
        Calls: nothing.
        """
        bounds = self.sceneRect()
        return QPointF(min(max(point.x(), 0.0), bounds.width()), min(max(point.y(), 0.0), bounds.height()))

    def zoom(self, factor: float) -> None:
        """class:PageCanvas--method:zoom--#33

        Purpose: Zooms the view by a factor and stops automatic fitting.
        Parameters: factor, e.g. 1.25 to zoom in.
        Returns: nothing.
        Raises: nothing.
        Called from: MainWindow._build_actions (#122), PageCanvas.wheelEvent (#35).
        Calls: QGraphicsView.scale.
        """
        if self._pixmap_item is not None:
            self._fit_mode = False
            self.scale(factor, factor)

    def fit_page(self) -> None:
        """class:PageCanvas--method:fit_page--#34

        Purpose: Scales the page to fill the window.
        Parameters: none.
        Returns: nothing.
        Raises: nothing.
        Called from: PageCanvas.set_page (#22), PageCanvas.resizeEvent (#36), MainWindow._build_actions (#122).
        Calls: QGraphicsView.fitInView.
        """
        if self._pixmap_item is not None:
            self._fit_mode = True
            self.fitInView(self.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)

    def wheelEvent(self, event) -> None:
        """class:PageCanvas--method:wheelEvent--#35

        Purpose: Ctrl + mouse wheel zooms; the plain wheel scrolls.
        Parameters: event, the QWheelEvent.
        Returns: nothing.
        Raises: nothing.
        Called from: Qt event loop.
        Calls: PageCanvas.zoom (#33).
        """
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            self.zoom(1.25 if event.angleDelta().y() > 0 else 0.8)
        else:
            super().wheelEvent(event)

    def resizeEvent(self, event) -> None:
        """class:PageCanvas--method:resizeEvent--#36

        Purpose: Keeps the page fitted while the user has not zoomed manually.
        Parameters: event, the QResizeEvent.
        Returns: nothing.
        Raises: nothing.
        Called from: Qt event loop.
        Calls: PageCanvas.fit_page (#34).
        """
        super().resizeEvent(event)
        if self._fit_mode:
            self.fit_page()

    def paintEvent(self, event) -> None:
        """class:PageCanvas--method:paintEvent--#37

        Purpose: Paints the page, or a friendly "open a file" message when empty.
        Parameters: event, the QPaintEvent.
        Returns: nothing.
        Raises: nothing.
        Called from: Qt event loop.
        Calls: QPainter.
        """
        super().paintEvent(event)
        if self._pixmap_item is None:
            painter = QPainter(self.viewport())
            painter.setPen(QColor(Theme.MUTED))
            painter.drawText(self.viewport().rect().adjusted(24, 24, -24, -24), Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap,
                             "Open a picture or PDF to begin\n(File > Open, Ctrl+O), or drop a file here.")

    def dragEnterEvent(self, event) -> None:
        """class:PageCanvas--method:dragEnterEvent--#38

        Purpose: Accepts drags that carry a file.
        Parameters: event, the QDragEnterEvent.
        Returns: nothing.
        Raises: nothing.
        Called from: Qt event loop.
        Calls: nothing.
        """
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dragMoveEvent(self, event) -> None:
        """class:PageCanvas--method:dragMoveEvent--#39

        Purpose: Keeps accepting the drag while it moves over the view.
        Parameters: event, the QDragMoveEvent.
        Returns: nothing.
        Raises: nothing.
        Called from: Qt event loop.
        Calls: nothing.
        """
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event) -> None:
        """class:PageCanvas--method:dropEvent--#40

        Purpose: Announces the dropped file so the window can open it.
        Parameters: event, the QDropEvent.
        Returns: nothing.
        Raises: nothing.
        Called from: Qt event loop.
        Calls: nothing.
        """
        urls = [u.toLocalFile() for u in event.mimeData().urls() if u.isLocalFile()]
        if urls:
            self.fileDropped.emit(str(Path(urls[0])))
            event.acceptProposedAction()
