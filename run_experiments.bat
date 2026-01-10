@echo off
REM Wrapper script for experiment_runner.py that handles PYTHONPATH automatically

REM Get the directory where this script is located
set SCRIPT_DIR=%~dp0
set SCRIPT_DIR=%SCRIPT_DIR:~0,-1%

REM Set PYTHONPATH to project root
set PYTHONPATH=%SCRIPT_DIR%

REM Use virtual environment Python if available, otherwise system Python
if exist "%SCRIPT_DIR%\.venv\Scripts\python.exe" (
    set PYTHON=%SCRIPT_DIR%\.venv\Scripts\python.exe
) else (
    set PYTHON=python
)

REM Run the experiment runner with all arguments passed through
"%PYTHON%" "%SCRIPT_DIR%\tests\scripts\experiment_runner.py" %*
