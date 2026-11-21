@echo off
rem Sends the latest project changes to GitHub. Does NOT post anything.
cd /d "%~dp0"
git add -A
git commit -m "Reel goes to the Reels tab only, not the grid" --trailer "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>" --trailer "Claude-Session: https://claude.ai/code/session_01NKVfbQ9HJaPDETnMTBYa8B"
git pull --rebase origin main || goto fail
git push origin main || goto fail
echo.
echo Done. Changes are on GitHub; tomorrow's post will use them.
pause
exit /b 0
:fail
echo.
echo Stopped because of the error shown here. Copy the text and send it to Claude.
pause
exit /b 1
