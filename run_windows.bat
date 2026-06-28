@echo off
setlocal
cd /d %~dp0
set PYTHONPATH=%CD%\src
python -m autosub --source auto --language en --model base.en
pause
