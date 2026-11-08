"""Runs long tasks on a worker thread so the window stays responsive."""

import logging
import threading
from collections.abc import Callable

from PyQt6.QtCore import QObject, Qt, QThread, pyqtSignal

from fontsleuth.errors import CancelledError, FontSleuthError

BACKGROUND_LOG = logging.getLogger("fontsleuth.background")
Task = Callable[[Callable[[int, int], None], Callable[[], bool]], object]


class _Runner(QObject):
    """class:_Runner--#11

    Purpose: Lives on the worker thread and executes one task, reporting the outcome by signals.
    Parameters: task, a callable taking (progress callback, cancelled callback) and returning a result.
    Raises: nothing (every outcome is a signal).
    Called from: BackgroundJob.start (#16).
    Calls: the task.
    """

    progress = pyqtSignal(int, int)
    succeeded = pyqtSignal(object)
    failed = pyqtSignal(str, str)
    cancelled = pyqtSignal()
    finished = pyqtSignal()

    def __init__(self, task: Task, stop: threading.Event) -> None:
        """class:_Runner--method:__init__--#12

        Purpose: Stores the task and the shared cancel flag.
        Parameters: task, the work to do; stop, an Event set when the user cancels.
        Returns: nothing.
        Raises: nothing.
        Called from: BackgroundJob.start (#16).
        Calls: QObject.
        """
        super().__init__()
        self._task, self._stop = task, stop

    def run(self) -> None:
        """class:_Runner--method:run--#13

        Purpose: Runs the task and emits exactly one of succeeded / failed / cancelled, then finished. The broad
            "except Exception" is deliberate: an exception escaping a worker thread would silently kill the job,
            so unexpected errors are logged with details and shown to the user as a generic message.
        Parameters: none.
        Returns: nothing.
        Raises: nothing.
        Called from: QThread.started signal (see BackgroundJob.start (#16)).
        Calls: the task.
        """
        try:
            result = self._task(self.progress.emit, self._stop.is_set)
            self.succeeded.emit(result)
        except CancelledError:
            self.cancelled.emit()
        except FontSleuthError as error:
            self.failed.emit(str(error), type(error).__name__)
        except Exception:  # noqa: BLE001
            BACKGROUND_LOG.exception("Unexpected error in background task")
            self.failed.emit("Something unexpected went wrong. Try again; if it keeps happening, "
                             "send the log file (Help > Open log folder) to support.", "Unexpected")
        finally:
            self.finished.emit()


class BackgroundJob(QObject):
    """class:BackgroundJob--#14

    Purpose: Runs one task on its own QThread and relays progress and the result to the GUI thread.
    Parameters: task, a callable taking (progress callback, cancelled callback) and returning a result.
    Raises: nothing.
    Called from: MainWindow._start_analysis (#132), FontLibraryController.rescan (#69).
    Calls: _Runner (#11).
    """

    progress = pyqtSignal(int, int)
    succeeded = pyqtSignal(object)
    failed = pyqtSignal(str, str)
    cancelled = pyqtSignal()
    finished = pyqtSignal()

    def __init__(self, task: Task, parent: QObject | None = None) -> None:
        """class:BackgroundJob--method:__init__--#15

        Purpose: Prepares the job; nothing runs until start() is called.
        Parameters: task, the work to do; parent, the owning QObject.
        Returns: nothing.
        Raises: nothing.
        Called from: MainWindow._start_analysis (#132), FontLibraryController.rescan (#69).
        Calls: QObject.
        """
        super().__init__(parent)
        self._task = task
        self._stop = threading.Event()
        self._thread: QThread | None = None

    def start(self) -> None:
        """class:BackgroundJob--method:start--#16

        Purpose: Starts the worker thread. Calling it twice has no effect, which prevents duplicate runs.
        Parameters: none.
        Returns: nothing.
        Raises: nothing.
        Called from: MainWindow._start_analysis (#132), FontLibraryController.rescan (#69).
        Calls: _Runner.run (#13).
        """
        if self._thread is not None:
            return
        self._thread = QThread(self)
        self._runner = _Runner(self._task, self._stop)
        self._runner.moveToThread(self._thread)
        self._thread.started.connect(self._runner.run)
        for name in ("progress", "succeeded", "failed", "cancelled"):
            getattr(self._runner, name).connect(getattr(self, name))
        # Direct connection: the QThread object lives on the GUI thread, so a queued quit() could never run while
        # the GUI thread is blocked in wait() during shutdown. QThread.quit() is thread-safe.
        self._runner.finished.connect(self._thread.quit, Qt.ConnectionType.DirectConnection)
        self._thread.finished.connect(self.finished)
        self._thread.start()

    def cancel(self) -> None:
        """class:BackgroundJob--method:cancel--#17

        Purpose: Asks the task to stop at its next checkpoint.
        Parameters: none.
        Returns: nothing.
        Raises: nothing.
        Called from: MainWindow._cancel_analysis (#133), MainWindow.closeEvent (#143).
        Calls: threading.Event.set.
        """
        self._stop.set()

    def is_running(self) -> bool:
        """class:BackgroundJob--method:is_running--#18

        Purpose: Tells whether the worker thread is still active.
        Parameters: none.
        Returns: True while running.
        Raises: nothing.
        Called from: MainWindow.closeEvent (#143), FontLibraryController.rescan (#69).
        Calls: nothing.
        """
        return self._thread is not None and self._thread.isRunning()

    def wait(self, milliseconds: int = 5000) -> bool:
        """class:BackgroundJob--method:wait--#19

        Purpose: Blocks until the worker thread ends (used only while closing the window).
        Parameters: milliseconds, longest time to wait.
        Returns: True if the thread ended.
        Raises: nothing.
        Called from: MainWindow.closeEvent (#143).
        Calls: QThread.wait.
        """
        return self._thread is None or self._thread.wait(milliseconds)
