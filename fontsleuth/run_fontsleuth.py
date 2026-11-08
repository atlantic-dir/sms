"""Launcher used by PyInstaller and for running straight from a source checkout."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from fontsleuth.app import Application  # noqa: E402

if __name__ == "__main__":
    sys.exit(Application.run(sys.argv))
