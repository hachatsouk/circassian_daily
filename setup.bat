@echo off
rem Double-click this file once. It installs what is needed, asks for the two keys and makes a test post locally.
cd /d "%~dp0"
where python >nul 2>&1
if errorlevel 1 (
  echo Python was not found. Install Python 3.11 or newer from python.org, then run this file again.
  pause
  exit /b 1
)
echo Installing Python packages...
python -m pip install -q -r requirements.txt || goto fail
echo Installing the browser used to draw the pages...
python -m playwright install chromium || goto fail
where ffmpeg >nul 2>&1
if errorlevel 1 (
  echo Installing ffmpeg...
  winget install --id Gyan.FFmpeg -e --accept-source-agreements --accept-package-agreements
  echo.
  echo ffmpeg was just installed. Close this window and double-click setup.bat again.
  pause
  exit /b 0
)
python -m cdaily setup || goto fail
echo.
pause
exit /b 0
:fail
echo.
echo Setup stopped because of the error shown here. Copy the text and send it to Claude.
pause
exit /b 1
