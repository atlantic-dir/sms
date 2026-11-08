import pytest
from PyQt6.QtCore import QSettings, Qt
from PyQt6.QtWidgets import QMessageBox

from fontsleuth.main_window import MainWindow
from fontsleuth.settings_store import AppSettings
from fontsleuth.theme import Theme
from helpers import SAMPLE, render_line


@pytest.fixture
def window(qtbot, tmp_path, all_fonts):
    settings = AppSettings(QSettings(str(tmp_path / "test.ini"), QSettings.Format.IniFormat))
    win = MainWindow(settings, scan_fonts=False)
    win.setStyleSheet(Theme.stylesheet())
    win.fonts.candidates = all_fonts
    win._update_actions()
    qtbot.addWidget(win)
    win.show()
    return win


@pytest.fixture
def picture(tmp_path, weight_pairs):
    face = weight_pairs[0][1]
    path = tmp_path / "line.png"
    render_line(face, size=30, ink=(31, 58, 95)).save(path, dpi=(96, 96))
    return path, face


def run_analysis(qtbot, window):
    window._start_analysis()
    qtbot.waitUntil(lambda: window._job is None, timeout=60000)


def test_full_workflow(qtbot, window, picture):
    path, face = picture
    assert not window.controls._analyze.isEnabled()
    window._open_path(str(path))
    assert window.controls._analyze.isEnabled()
    window.canvas.select_all()
    assert window.controls._selection_label.text().startswith("Selected:")
    window.controls._text.setText(SAMPLE)
    run_analysis(qtbot, window)
    headline = window.results._headline.text()
    assert face.family in headline and "#1F3A5F" in headline
    assert window.results._table.model().rowCount() > 1
    assert window.act_copy.isEnabled()
    assert "Done:" in window.statusBar().currentMessage()
    window.results.copy_summary()
    from PyQt6.QtWidgets import QApplication
    assert "Weight: Bold (700)" in QApplication.clipboard().text()
    assert "copied" in window.statusBar().currentMessage()


def test_missing_text_error_is_shown_next_to_the_field_and_text_is_kept(qtbot, window, picture):
    window._open_path(str(picture[0]))
    window.canvas.select_all()
    run_analysis(qtbot, window)
    assert window.controls._text_error.isVisible() and "Type the text" in window.controls._text_error.text()
    window.controls._text.setText("kept")
    assert not window.controls._text_error.isVisible()
    assert window.controls.text() == "kept"


def test_no_selection_gives_guidance_not_a_crash(qtbot, window, picture):
    window._open_path(str(picture[0]))
    window.controls._text.setText(SAMPLE)
    window._start_analysis()
    assert window._job is None and "Drag a box" in window.results._message.text()


def test_unreadable_file_shows_plain_message(qtbot, window, tmp_path, monkeypatch):
    shown = []
    monkeypatch.setattr(QMessageBox, "warning", lambda *args: shown.append(args[2]))
    bad = tmp_path / "bad.png"
    bad.write_bytes(b"nope")
    window._open_path(str(bad))
    assert shown and "could not be read" in shown[0]
    assert window.source is None


def test_failed_open_keeps_the_current_file(qtbot, window, picture, tmp_path, monkeypatch):
    monkeypatch.setattr(QMessageBox, "warning", lambda *a: None)
    window._open_path(str(picture[0]))
    (tmp_path / "bad.png").write_bytes(b"nope")
    window._open_path(str(tmp_path / "bad.png"))
    assert window.source is not None and window.canvas.has_page()


def test_busy_state_blocks_duplicates_and_cancel_works(qtbot, window, picture):
    window._open_path(str(picture[0]))
    window.canvas.select_all()
    window.controls._text.setText(SAMPLE)
    window._start_analysis()
    first = window._job
    window._start_analysis()
    assert window._job is first
    assert window.controls._cancel.isVisible() and not window.controls._analyze.isEnabled()
    assert not window.act_open.isEnabled()
    window._cancel_analysis()
    qtbot.waitUntil(lambda: window._job is None, timeout=60000)
    assert window.controls._analyze.isEnabled() and not window.controls._cancel.isVisible()


def test_close_while_busy_shuts_down_cleanly(qtbot, window, picture):
    window._open_path(str(picture[0]))
    window.canvas.select_all()
    window.controls._text.setText(SAMPLE)
    window._start_analysis()
    window.close()
    assert window._job is None or not window._job.is_running()


def test_window_stays_usable_when_small_and_large(qtbot, window, picture):
    window._open_path(str(picture[0]))
    for width, height in ((640, 480), (1900, 1000)):
        window.resize(width, height)
        qtbot.wait(50)
        assert window.controls._analyze.isVisible() and window.canvas.isVisible()


def test_keyboard_shortcuts_are_registered_and_shown(window):
    assert window.act_open.shortcut().toString() == "Ctrl+O"
    assert "Ctrl+Return" in window.act_analyze.toolTip()
    assert "Ctrl+O" in window.controls._open.toolTip()


def test_pdf_page_navigation(qtbot, window, tmp_path):
    import pymupdf
    doc = pymupdf.open()
    for n in range(3):
        doc.new_page(width=300, height=200).insert_text((20, 50), f"Page {n + 1}", fontname="helv", fontsize=16)
    path = tmp_path / "three.pdf"
    doc.save(path)
    window._open_path(str(path))
    assert window.controls._page.maximum() == 3
    window.controls.step_page(1)
    window.canvas.select_all()
    window.controls._text.setText("")
    run_analysis(qtbot, window)
    assert "Helvetica" in window.results._headline.text() and "16 pt" in window.results._headline.text()
    assert "Exact" in window.results._confidence.text()
