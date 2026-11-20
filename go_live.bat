@echo off
rem Double-click this after setup.bat has made a test post you are happy with.
rem It puts the project in a PUBLIC GitHub repository (Buffer needs public media links),
rem stores the keys as GitHub secrets and switches on the daily run at 08:00 Amman time.
cd /d "%~dp0"
set NEED=0
where git >nul 2>&1
if errorlevel 1 (
  echo Installing Git...
  winget install --id Git.Git -e --accept-source-agreements --accept-package-agreements
  set NEED=1
)
where gh >nul 2>&1
if errorlevel 1 (
  echo Installing the GitHub command line tool...
  winget install --id GitHub.cli -e --accept-source-agreements --accept-package-agreements
  set NEED=1
)
if "%NEED%"=="1" (
  echo.
  echo Tools were just installed. Close this window and double-click go_live.bat again.
  pause
  exit /b 0
)
gh auth status >nul 2>&1
if errorlevel 1 (
  echo Sign in to GitHub in the browser window that opens...
  gh auth login --hostname github.com --git-protocol https --web -s workflow || goto fail
  gh auth setup-git
)
gh auth status 2>&1 | findstr /C:"workflow" >nul
if errorlevel 1 (
  echo GitHub needs one more permission, to save the daily schedule. Approve it in the browser...
  gh auth refresh --hostname github.com -s workflow || goto fail
)
python -m cdaily github || goto fail
echo.
pause
exit /b 0
:fail
echo.
echo Stopped because of the error shown here. Copy the text and send it to Claude.
pause
exit /b 1
