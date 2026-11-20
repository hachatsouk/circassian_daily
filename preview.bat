@echo off
rem Makes today's post again in the output folder so you can look at it. Nothing is sent to Instagram.
cd /d "%~dp0"
python -m cdaily prepare || goto fail
start "" "%~dp0output"
echo.
pause
exit /b 0
:fail
echo.
echo Stopped because of the error shown here. Copy the text and send it to Claude.
pause
exit /b 1
