@echo off
setlocal
cd /d "%~dp0.."
if not exist "data\logs" mkdir "data\logs"
for /f %%I in ('powershell -NoProfile -Command "Get-Date -Format yyyyMMdd"') do set DAY=%%I
set LOG=data\logs\daily_%DAY%.log
echo ===== START %DATE% %TIME% =====>> "%LOG%"
"C:\Users\jukit\AppData\Local\Programs\Python\Python311\python.exe" scripts\run_daily.py --interval 2.0 >> "%LOG%" 2>&1
set EXITCODE=%ERRORLEVEL%
echo ===== END %DATE% %TIME% exit=%EXITCODE% =====>> "%LOG%"
exit /b %EXITCODE%
