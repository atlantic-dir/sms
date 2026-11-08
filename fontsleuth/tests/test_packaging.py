"""The single-file edition and the documentation conventions must stay in step with the source form."""

import importlib.util
import subprocess
import sys
from pathlib import Path

from PIL import Image

from helpers import SAMPLE, render_line

ROOT = Path(__file__).resolve().parent.parent


def test_single_file_edition_runs_an_analysis(tmp_path, all_fonts, weight_pairs, qtbot):
    target = tmp_path / "bundle" / "fontsleuth_single.py"
    subprocess.run([sys.executable, str(ROOT / "tools" / "make_single_file.py"), str(target)], check=True)
    spec = importlib.util.spec_from_file_location("fontsleuth_single", target)
    bundle = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = bundle  # dataclasses look their module up here
    spec.loader.exec_module(bundle)
    face = weight_pairs[0][1]
    image = render_line(face, size=30)
    crop = bundle.PageImage(image, None)
    fonts = [bundle.FontCandidate(**f.__dict__) for f in all_fonts]
    result = bundle.AnalysisService.analyze_pixels(crop, SAMPLE, 96, fonts)
    assert result.findings[0].family == face.family
    assert bundle.__version__


def test_docstring_notes_and_index_are_consistent():
    done = subprocess.run([sys.executable, str(ROOT / "tools" / "notes.py"), "--check"], capture_output=True, text=True)
    assert done.returncode == 0, done.stdout


def test_build_script_exists_and_covers_the_required_steps():
    text = (ROOT / "build_exe.bat").read_text()
    for needed in ("venv", "pip install -r requirements.txt", "pyinstaller", "--onefile", "--windowed"):
        assert needed in text
