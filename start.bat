@echo off
title erp_site
setlocal
cd /d "%~dp0"
if not defined ERP_PYTHON set "ERP_PYTHON=%~dp0.venv\Scripts\python.exe"
if not defined WEB_HOST set "WEB_HOST=0.0.0.0"
if not defined WEB_PORT set "WEB_PORT=80"
if not exist "bin\erp-site.exe" (
  echo Go executable not found. Build it first:
  echo go build -o bin/erp-site.exe ./backend/cmd/erp
  exit /b 1
)
"%~dp0bin\erp-site.exe" --root "%~dp0." --python "%ERP_PYTHON%" %*
exit /b %ERRORLEVEL%
