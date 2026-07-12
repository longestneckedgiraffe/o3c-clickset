@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    echo Virtual environment not found. Follow the README installation steps first.
    exit /b 1
)
".venv\Scripts\python.exe" gui.py
