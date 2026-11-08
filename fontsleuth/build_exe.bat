@echo off
rem Builds FontSleuth.exe: creates a private virtual environment, installs the requirements and PyInstaller,
rem then packages the app into one Windows .exe (dist\FontSleuth.exe). Needs Python 3.12 or newer on PATH.
setlocal
cd /d "%~dp0"

where py >nul 2>nul && (set "PYTHON=py -3") || (set "PYTHON=python")
%PYTHON% -c "import sys; sys.exit(0 if sys.version_info >= (3, 12) else 1)" || (
    echo Python 3.12 or newer is required. Install it from https://www.python.org/downloads/ and run this file again.
    goto :failed
)

echo [1/3] Creating virtual environment .venv-build ...
%PYTHON% -m venv .venv-build || goto :failed
call ".venv-build\Scripts\activate.bat" || goto :failed

echo [2/3] Installing requirements and PyInstaller ...
python -m pip install --upgrade pip || goto :failed
python -m pip install -r requirements.txt pyinstaller || goto :failed

echo [3/3] Building the .exe ...
pyinstaller --noconfirm --clean --onefile --windowed --name FontSleuth --paths src run_fontsleuth.py || goto :failed

echo.
echo Done. Your program is: %~dp0dist\FontSleuth.exe
endlocal
exit /b 0

:failed
echo.
echo The build did not finish. Read the messages above, fix the problem, and run build_exe.bat again.
endlocal
exit /b 1
