"""Maintains the numbered docstring notes required by project-conventions.md.

Usage (run from the project folder):
    python tools/notes.py           assign numbers to "#?", resolve [[Class.method]] references, rewrite docs/note-index.md
    python tools/notes.py --check   verify everything and exit with status 1 if anything is wrong (writes nothing)
"""

import argparse
import ast
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PACKAGE = ROOT / "src" / "fontsleuth"
INDEX = ROOT / "docs" / "note-index.md"
LABELS = ("Purpose:", "Parameters:", "Returns:", "Raises:", "Called from:", "Calls:")
ID_CLASS = re.compile(r"^class:(\w+)--#(\d+|\?)$")
ID_METHOD = re.compile(r"^class:(\w+)--method:(\w+)--#(\d+|\?)$")
REF = re.compile(r"\[\[([A-Za-z_]\w*(?:\.[A-Za-z_]\w*)?)\]\]")
RESOLVED = re.compile(r"\b([A-Za-z_]\w*(?:\.[A-Za-z_]\w*)?) \(#(\d+)\)")


class Note:
    """One class or method with its docstring identifier."""

    def __init__(self, file: Path, owner: str, name: str | None, doc: str | None, is_method: bool) -> None:
        self.file, self.owner, self.name, self.doc, self.is_method = file, owner, name, doc, is_method
        first = (doc or "").strip().splitlines()[0].strip() if doc and doc.strip() else ""
        match = (ID_METHOD if is_method else ID_CLASS).match(first)
        self.identifier = first
        self.valid = bool(match)
        self.number = None if not match or match.group(match.lastindex) == "?" else int(match.group(match.lastindex))
        self.declared = (match.groups()[:-1] if match else ())

    @property
    def key(self) -> str:
        """Dotted reference name, e.g. Class or Class.method."""
        return f"{self.owner}.{self.name}" if self.is_method else self.owner


def collect() -> list[Note]:
    """Reads every module in the package and returns its class and method notes in source order."""
    notes = []
    for file in sorted(PACKAGE.glob("*.py")):
        tree = ast.parse(file.read_text(encoding="utf-8"))
        for node in tree.body:
            if isinstance(node, ast.ClassDef):
                notes.append(Note(file, node.name, None, ast.get_docstring(node, clean=False), False))
                for item in node.body:
                    if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        notes.append(Note(file, node.name, item.name, ast.get_docstring(item, clean=False), True))
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                notes.append(Note(file, "<module>", node.name, None, True))  # flagged by check_structure
    return notes


def read_index_state() -> tuple[int, set[int]]:
    """Returns (next number, retired numbers) from the existing index, or (1, empty)."""
    if not INDEX.exists():
        return 1, set()
    text = INDEX.read_text(encoding="utf-8")
    nxt = re.search(r"Next number: (\d+)", text)
    retired_line = re.search(r"Retired numbers: (.*)", text)
    retired = {int(n) for n in re.findall(r"\d+", retired_line.group(1))} if retired_line else set()
    old = {int(n) for n in re.findall(r"`class:[^`]*--#(\d+)`", text)}
    return (int(nxt.group(1)) if nxt else 1), retired | old


def check_structure(notes: list[Note]) -> list[str]:
    """Lists convention violations: missing or malformed identifiers, missing sections, duplicates."""
    problems, seen_numbers, seen_classes = [], {}, {}
    for n in notes:
        where = f"{n.file.name}: {n.key}"
        if n.owner == "<module>":
            problems.append(f"{where}: module-level function; use a class with a static method")
            continue
        if not n.doc:
            problems.append(f"{where}: missing docstring")
            continue
        if not n.valid:
            problems.append(f"{where}: first docstring line must be the identifier, found {n.identifier!r}")
            continue
        expected = (n.owner, n.name) if n.is_method else (n.owner,)
        if tuple(n.declared) != expected:
            problems.append(f"{where}: identifier names {tuple(n.declared)} but the code is {expected}")
        for label in LABELS:
            if label == "Returns:" and not n.is_method:
                continue
            if label not in n.doc:
                problems.append(f"{where}: docstring lacks '{label}'")
        if n.number is not None:
            if n.number in seen_numbers:
                problems.append(f"{where}: number #{n.number} also used by {seen_numbers[n.number]}")
            seen_numbers[n.number] = n.key
        if not n.is_method:
            if n.owner in seen_classes:
                problems.append(f"{where}: class name also defined in {seen_classes[n.owner]} (names must be unique)")
            seen_classes[n.owner] = n.file.name
    return problems


def check_references(notes: list[Note]) -> list[str]:
    """Verifies that every 'Name (#N)' reference points at the right number and no [[...]] is left unresolved."""
    numbers = {n.key: n.number for n in notes if n.number is not None}
    problems = []
    for file in sorted(PACKAGE.glob("*.py")):
        text = file.read_text(encoding="utf-8")
        for ref in REF.findall(text):
            problems.append(f"{file.name}: unresolved reference [[{ref}]]")
        for name, number in RESOLVED.findall(text):
            if name in numbers and numbers[name] != int(number):
                problems.append(f"{file.name}: '{name} (#{number})' is stale; it is now #{numbers[name]}")
    return problems


def assign_and_resolve(notes: list[Note]) -> list[str]:
    """Writes numbers for '#?' identifiers and resolves [[refs]] in every module. Returns problems found."""
    nxt, retired = read_index_state()
    nxt = max(nxt, max([n.number for n in notes if n.number] + [0]) + 1, max(retired | {0}) + 1)
    for n in notes:
        if n.valid and n.number is None:
            n.number, nxt = nxt, nxt + 1
            text = n.file.read_text(encoding="utf-8")
            old = n.identifier
            new = old[:-1] + str(n.number)
            n.file.write_text(text.replace(old, new, 1), encoding="utf-8")
            n.identifier = new
    numbers = {n.key: n.number for n in notes if n.number is not None}
    problems = []
    for file in sorted(PACKAGE.glob("*.py")):
        text = file.read_text(encoding="utf-8")

        def substitute(match: re.Match) -> str:
            name = match.group(1)
            if name not in numbers:
                problems.append(f"{file.name}: [[{name}]] does not match any class or method")
                return match.group(0)
            return f"{name} (#{numbers[name]})"

        updated = REF.sub(substitute, text)
        if updated != text:
            file.write_text(updated, encoding="utf-8")
    write_index(notes, nxt)
    return problems


def purpose_of(doc: str) -> str:
    """Returns the first sentence of the Purpose section, on one line."""
    lines, grabbing = [], False
    for line in doc.splitlines():
        stripped = line.strip()
        if stripped.startswith("Purpose:"):
            grabbing, stripped = True, stripped[len("Purpose:"):].strip()
        elif stripped.startswith(LABELS):
            grabbing = False
        if grabbing and stripped:
            lines.append(stripped)
    text = " ".join(lines)
    return (re.split(r"(?<=\.)\s", text)[0] if text else "").replace("|", "/")


def write_index(notes: list[Note], nxt: int) -> None:
    """Regenerates docs/note-index.md from the code."""
    _, previous = read_index_state()
    live = {n.number for n in notes if n.number is not None}
    retired = sorted(previous - live)
    rows = [
        f"| `{n.identifier}` | `{n.file.name}` | {purpose_of(ast_doc(n))} |"
        for n in sorted((n for n in notes if n.number is not None), key=lambda n: n.number)
    ]
    INDEX.parent.mkdir(exist_ok=True)
    INDEX.write_text(
        "# Note index\n\nEvery class and method in `src/fontsleuth`, by note number. "
        "Generated by `python tools/notes.py`; do not edit by hand.\n\n"
        f"Next number: {nxt}\n\nRetired numbers: {', '.join(map(str, retired)) or 'none'}\n\n"
        "| Identifier | File | Purpose |\n|---|---|---|\n" + "\n".join(rows) + "\n",
        encoding="utf-8",
    )


def ast_doc(note: Note) -> str:
    """Re-reads the (possibly just rewritten) docstring of a note."""
    tree = ast.parse(note.file.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == note.owner:
            if not note.is_method:
                return ast.get_docstring(node, clean=False) or ""
            for item in node.body:
                if isinstance(item, ast.FunctionDef) and item.name == note.name:
                    return ast.get_docstring(item, clean=False) or ""
    return ""


def check_index(notes: list[Note]) -> list[str]:
    """Verifies docs/note-index.md lists exactly the identifiers found in the code."""
    if not INDEX.exists():
        return ["docs/note-index.md is missing; run python tools/notes.py"]
    listed = set(re.findall(r"`(class:[^`]*--#\d+)`", INDEX.read_text(encoding="utf-8")))
    actual = {n.identifier for n in notes if n.number is not None}
    return [f"index lacks {i}" for i in sorted(actual - listed)] + [f"index has stale entry {i}" for i in sorted(listed - actual)]


def main() -> int:
    """Command-line entry point."""
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument("--check", action="store_true", help="verify only; write nothing")
    args = parser.parse_args()
    notes = collect()
    problems = check_structure(notes)
    if not args.check:
        problems += assign_and_resolve(notes)
        notes = collect()
    problems += check_references(notes) + check_index(notes)
    for problem in problems:
        print("PROBLEM:", problem)
    print(f"{len(notes)} notes checked, {len(problems)} problems")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
