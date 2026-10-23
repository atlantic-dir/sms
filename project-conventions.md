# Project Conventions

## Technology
- Build desktop apps with PyQt6 in Python 3.12 or later.
- Follow PEP 8. Use type hints on all public functions and methods.

## Class and method documentation
Every class and every method needs a docstring. Put the note identifier on the first line of the docstring, then explain the following:
- **Purpose:** what the class or method does.
- **Parameters and returns:** what goes in and what comes out.
- **Raises:** which errors it can raise.
- **Called from:** which classes or methods call it.
- **Calls:** which classes or methods it calls.

Identifier format:
- Method: `class:<ClassName>--method:<methodName>--#<number>`
- Class: `class:<ClassName>--#<number>`

Example:
```python
def usdate(self, value: str) -> date:
    """class:getdate--method:usdate--#230

    Purpose: Converts a US-format date string to a date object.
    Parameters: value, a date string such as "10/21/2026".
    Returns: the parsed date.
    Raises: ValueError if the string does not match the format.
    Called from: GetDate.render_preview (#231).
    Calls: datetime.strptime.
    """
```

Numbering rules:
- Numbers are unique across the whole project, assigned in increasing order, and never reused. If a method is deleted, its number is retired.
- Renaming a method keeps its number and updates the name in the identifier.
- Keep a `docs/note-index.md` file that lists every identifier, its file, and a one-line purpose. Update it whenever a note is added, renamed, or removed.

## Keeping classes and methods small
- Split a class when it has more than one responsibility.
- Split a method when it does more than one step that could be named separately.
- Keep GUI code, business logic, and data access in separate modules.

## Delivery
For every app, deliver two forms in one zip file:
1. **Single file:** a complete, runnable PyQt6 program in one `.py` file, if the app can reasonably fit in one file.
2. **Source form with Windows build:** the full source code organized in folders, plus a `build_exe.bat` file. Running the batch file must create a virtual environment, install the requirements and PyInstaller, and produce a Windows `.exe` file.

Name the zip file after the app and its version, for example `reconciler-1.0.zip`.

# User Interface Rules

## Layout and display
- Build every window with Qt layouts. Never place widgets at fixed pixel coordinates or set fixed window or widget sizes.
- Windows must resize cleanly. Check that all controls stay visible and usable at small and large window sizes.
- The app must look correct on high-DPI screens. Use device-independent sizes and scalable fonts.

## Consistency
- Use the same fonts, colors, spacing, and button and label conventions in every window and dialog.
- Define shared styling once, in one module, and reuse it. Do not repeat style code in each window.

## Usability
- Add keyboard shortcuts for frequent actions, and show each shortcut in the menu or tooltip.
- Any action that takes time must show a loading indicator while it runs, and a clear success or error message when it finishes.
- Error messages must state what went wrong and what the user can do next, in plain language.

## Code simplicity
- Keep each class and method small, with one job, so it is easy to change. A longer method is acceptable only when the task truly requires it; state the reason in its docstring.

## Extra features and options
- If a helpful option is related to a requested feature but was not asked for, suggest it and wait for approval before adding it.
- If an option is closely tied to a requested feature and the user is very likely to need it (for example, a cancel button on a long-running import), add it directly, and say in your summary that you did so.
- Never add unrelated features without asking.
