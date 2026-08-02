@echo off
setlocal
cd /d "%~dp0"
set "FROBEL_PYTHON=%~dp0.venv\Scripts\python.exe"

if not exist "%FROBEL_PYTHON%" (
  echo Project virtual environment not found.
  echo Create .venv and install requirements.txt first.
  pause
  exit /b 1
)

"%FROBEL_PYTHON%" -c "import pyodbc, docx" >nul 2>&1
if errorlevel 1 (
  echo Required Python packages are missing.
  echo Run: .venv\Scripts\python.exe -m pip install -r requirements.txt
  pause
  exit /b 1
)

if /I "%~1"=="--check" (
  echo Python, pyodbc and python-docx checks passed.
  exit /b 0
)

echo Starting Frobel Operations Center at http://127.0.0.1
echo Run this file as administrator if Windows denies port 80 access.
"%FROBEL_PYTHON%" app.py --host 127.0.0.1 --port 80

if errorlevel 1 (
  echo.
  echo Startup failed. Check SQL Server, port 80, permissions and Python packages.
  pause
  exit /b 1
)
endlocal
