@echo off
setlocal
cd /d "%~dp0"
set "PYTHON=%~dp0.venv\Scripts\python.exe"

if not exist "%PYTHON%" (
  echo Project virtual environment not found.
  echo Create .venv and install requirements.txt first.
  pause
  exit /b 1
)

"%PYTHON%" -c "import pyodbc, docx, openpyxl, pypdf, xlrd" >nul 2>&1
if errorlevel 1 (
  echo Required Python packages are missing.
  echo Run: .venv\Scripts\python.exe -m pip install -r requirements.txt
  pause
  exit /b 1
)

if /I "%~1"=="--check" (
  echo Python backend dependency checks passed.
  exit /b 0
)

echo Starting Operations Center on port 80 for local network access.
echo Run this file as administrator if Windows denies port 80 access.
"%PYTHON%" -m backend.app --host 0.0.0.0 --port 80

if errorlevel 1 (
  echo.
  echo Startup failed. Check SQL Server, port 80, permissions and Python packages.
  pause
  exit /b 1
)
endlocal