"""Builds releases/fontsleuth-<version>.zip containing the single-file edition and the source form.

Usage: python tools/make_release.py   (runs the notes check and the test suite first; refuses to zip if they fail)
"""

import re
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VERSION = re.search(r'__version__ = "([^"]+)"', (ROOT / "src" / "fontsleuth" / "__init__.py").read_text()).group(1)
SOURCE_ITEMS = ["src", "tests", "tools", "docs", "requirements.txt", "requirements-dev.txt", "build_exe.bat",
                "run_fontsleuth.py", "pytest.ini", "README.md", ".gitignore"]
SKIP_PARTS = {"__pycache__", ".pytest_cache", ".venv-build", "build", "dist"}


def run(*args: str) -> None:
    """Runs a command in the project folder and stops the release if it fails."""
    subprocess.run([sys.executable, *args], cwd=ROOT, check=True)


def files_in(item: str):
    """Yields every file under an item, skipping caches."""
    path = ROOT / item
    for file in ([path] if path.is_file() else sorted(path.rglob("*"))):
        if file.is_file() and not SKIP_PARTS & set(file.relative_to(ROOT).parts) and file.suffix != ".pyc":
            yield file


def main() -> int:
    """Verifies the project, builds the single file, and writes the zip."""
    run("tools/notes.py", "--check")
    run("-m", "pytest", "-q")
    single = ROOT / "dist" / "fontsleuth.py"
    run("tools/make_single_file.py", str(single))
    top = f"fontsleuth-{VERSION}"
    out = ROOT / "releases" / f"{top}.zip"
    out.parent.mkdir(exist_ok=True)
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as bundle:
        bundle.write(single, f"{top}/1-single-file/fontsleuth.py")
        bundle.write(ROOT / "requirements.txt", f"{top}/1-single-file/requirements.txt")
        bundle.writestr(f"{top}/README.txt", (
            f"Font Sleuth {VERSION}\n\n"
            "1-single-file/   fontsleuth.py - one runnable program. Python 3.12+:\n"
            "                   pip install -r requirements.txt\n                   python fontsleuth.py\n"
            "2-source/        the full source, tests and build_exe.bat. On Windows, double-click build_exe.bat\n"
            "                 to create dist\\FontSleuth.exe (needs Python 3.12+ and internet access).\n"
            "                 2-source/README.md explains how the app works and its limits.\n"))
        for item in SOURCE_ITEMS:
            for file in files_in(item):
                bundle.write(file, f"{top}/2-source/{file.relative_to(ROOT).as_posix()}")
    print(f"Wrote {out} ({out.stat().st_size // 1024} KiB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
