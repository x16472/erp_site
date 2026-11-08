@echo off
setlocal EnableExtensions DisableDelayedExpansion
chcp 65001 >nul
title Manual attendance simulator
set "SIM_RESULT=1"
set "SIM_PREVIEW="
if /i "%~1"=="--preview" set "SIM_PREVIEW=-Preview"
if not "%~1"=="" if /i not "%~1"=="--preview" (
    echo Usage: simulate-attendance.bat [--preview]
    goto finish
)
:createWorkspace
set "SIM_WORK=%TEMP%\erp-clock-%RANDOM%-%RANDOM%"
if exist "%SIM_WORK%" goto createWorkspace
mkdir "%SIM_WORK%"
if errorlevel 1 goto finish
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0simulate-attendance.ps1" -Phase Prepare -Workspace "%SIM_WORK%"
if errorlevel 1 goto cleanup
set /a SIM_OFFSET=0
type nul > "%SIM_WORK%\offsets.csv"
for /f "usebackq delims=" %%E in ("%SIM_WORK%\employees.txt") do call :makeOffset %%E
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0simulate-attendance.ps1" -Phase Apply -Workspace "%SIM_WORK%" %SIM_PREVIEW%
set "SIM_RESULT=%ERRORLEVEL%"
:cleanup
del /q "%SIM_WORK%\context.json" "%SIM_WORK%\employees.txt" "%SIM_WORK%\offsets.csv" >nul 2>&1
rd "%SIM_WORK%" >nul 2>&1
:finish
if not "%SIM_RESULT%"=="0" echo Simulation failed. Check the message above.
pause
exit /b %SIM_RESULT%

:makeOffset
rem 每位員工累加 1 至 600 秒，亂數在批次檔迴圈中產生。
set /a "SIM_GAP=%RANDOM% %% 600 + 1"
set /a "SIM_OFFSET+=SIM_GAP"
>> "%SIM_WORK%\offsets.csv" echo %~1,%SIM_OFFSET%
exit /b 0

pause
