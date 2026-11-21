@echo off
rem Sends the latest project changes to GitHub and starts today's post.
cd /d "%~dp0"
if exist daily-workflow.yml move /y daily-workflow.yml .github\workflows\daily.yml >nul
git add -A
git commit -m "Reliable daily schedule: three morning run times, one post per day, post at 08:00 Amman" --trailer "Co-Authored-By: Claude Fable 5.2 <noreply@anthropic.com>" --trailer "Claude-Session: https://claude.ai/code/session_01NKVfbQ9HJaPDETnMTBYa8B"
git pull --rebase origin main || goto fail
git push origin main || goto fail
echo.
echo Starting today's post...
gh workflow run daily.yml || goto fail
echo Started. It takes about three minutes to reach Instagram.
echo.
pause
exit /b 0
:fail
echo.
echo Stopped because of the error shown here. Copy the text and send it to Claude.
pause
exit /b 1
