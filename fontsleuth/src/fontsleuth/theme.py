"""The single place that defines colours, spacing and the application style sheet."""


class Theme:
    """class:Theme--#229

    Purpose: Holds the shared colours and spacing and builds the style sheet used by every window.
    Parameters: none (class-level constants and static methods).
    Raises: nothing.
    Called from: Application.run (#10), PageCanvas.__init__ (#21), ResultPanel.__init__ (#181), ControlPanel.__init__ (#42).
    Calls: nothing.
    """

    BACKGROUND = "#F4F5F8"
    SURFACE = "#FFFFFF"
    BORDER = "#C9CED8"
    TEXT = "#1B2130"
    MUTED = "#4F586B"
    ACCENT = "#2250D6"
    ACCENT_HOVER = "#1A40AB"
    ERROR = "#B3261E"
    WARNING = "#8A5300"
    SUCCESS = "#18703A"
    SPACING = 8
    MARGIN = 12

    @staticmethod
    def stylesheet() -> str:
        """class:Theme--method:stylesheet--#230

        Purpose: Builds the Qt style sheet shared by the whole application (sizes are in points/em so it
            scales on high-DPI screens).
        Parameters: none.
        Returns: the style sheet text.
        Raises: nothing.
        Called from: Application.run (#10).
        Calls: nothing.
        """
        t = Theme
        return f"""
        QWidget {{ color: {t.TEXT}; font-size: 10pt; }}
        QMainWindow, QDialog, QScrollArea, QSplitter {{ background: {t.BACKGROUND}; }}
        QGroupBox {{ background: {t.SURFACE}; border: 1px solid {t.BORDER}; border-radius: 6px;
                     margin-top: 1.4em; padding: 0.6em; font-weight: 600; }}
        QGroupBox::title {{ subcontrol-origin: margin; left: 0.8em; padding: 0 0.3em; }}
        QLineEdit, QTableView {{ background: {t.SURFACE}; border: 1px solid {t.BORDER};
                     border-radius: 4px; padding: 0.3em; }}
        QLineEdit:focus, QTableView:focus {{ border: 2px solid {t.ACCENT}; }}
        QLineEdit[invalid="true"] {{ border: 2px solid {t.ERROR}; }}
        QPushButton {{ background: {t.SURFACE}; border: 1px solid {t.BORDER}; border-radius: 4px;
                       padding: 0.45em 1.1em; }}
        QPushButton:hover {{ border-color: {t.ACCENT}; }}
        QPushButton:focus {{ border: 2px solid {t.ACCENT}; }}
        QPushButton:disabled {{ color: #7B8394; background: #ECEEF3; }}
        QPushButton[primary="true"] {{ background: {t.ACCENT}; color: white; border-color: {t.ACCENT};
                       font-weight: 600; }}
        QPushButton[primary="true"]:hover {{ background: {t.ACCENT_HOVER}; }}
        QPushButton[primary="true"]:disabled {{ background: #9AA9D8; color: white; }}
        QLabel[role="hint"] {{ color: {t.MUTED}; }}
        QLabel[role="error"] {{ color: {t.ERROR}; font-weight: 600; }}
        QLabel[role="warning"] {{ color: {t.WARNING}; }}
        QLabel[role="success"] {{ color: {t.SUCCESS}; font-weight: 600; }}
        QLabel[role="headline"] {{ font-size: 14pt; font-weight: 700; }}
        QHeaderView::section {{ background: #E8EBF2; border: 0; padding: 0.3em 0.5em; font-weight: 600; }}
        QStatusBar {{ background: {t.SURFACE}; border-top: 1px solid {t.BORDER}; }}
        QProgressBar {{ border: 1px solid {t.BORDER}; border-radius: 4px; text-align: center; }}
        QProgressBar::chunk {{ background: {t.ACCENT}; }}
        """
