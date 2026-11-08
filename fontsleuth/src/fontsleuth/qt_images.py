"""Conversion between Pillow images and Qt images."""

from PIL import Image
from PyQt6.QtGui import QImage, QPixmap


class ImageConverter:
    """class:ImageConverter--#155

    Purpose: Converts Pillow images to QImage / QPixmap safely (the result owns its pixel data).
    Parameters: none (all methods are static).
    Raises: nothing.
    Called from: MainWindow._show_page (#130), ResultPanel.show_finding (#187).
    Calls: PyQt6.QtGui.QImage.
    """

    @staticmethod
    def to_qimage(image: Image.Image) -> QImage:
        """class:ImageConverter--method:to_qimage--#156

        Purpose: Copies an RGB Pillow image into a QImage.
        Parameters: image, any Pillow image (converted to RGB).
        Returns: a QImage that owns its memory.
        Raises: nothing.
        Called from: ImageConverter.to_pixmap (#157), MainWindow._show_page (#130).
        Calls: QImage.copy.
        """
        rgb = image.convert("RGB")
        data = rgb.tobytes()
        return QImage(data, rgb.width, rgb.height, 3 * rgb.width, QImage.Format.Format_RGB888).copy()

    @staticmethod
    def to_pixmap(image: Image.Image) -> QPixmap:
        """class:ImageConverter--method:to_pixmap--#157

        Purpose: Converts a Pillow image to a QPixmap for painting.
        Parameters: image, any Pillow image.
        Returns: a QPixmap.
        Raises: nothing.
        Called from: ResultPanel.show_finding (#187).
        Calls: ImageConverter.to_qimage (#156).
        """
        return QPixmap.fromImage(ImageConverter.to_qimage(image))
