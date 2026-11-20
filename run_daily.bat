@echo off
rem Run from Windows Task Scheduler if you post from this PC instead of GitHub Actions.
cd /d "%~dp0"
python -m cdaily prepare || exit /b 1
git add output && git commit -m "Media" && git push
python -m cdaily publish || exit /b 1
git add data/state.json output && git commit -m "Posted" && git push
