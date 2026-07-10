@echo off
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" ground_station\main.py
    goto :eof
)
if exist "%USERPROFILE%\.conda\envs\gluon\python.exe" (
    "%USERPROFILE%\.conda\envs\gluon\python.exe" ground_station\main.py
    goto :eof
)
python ground_station\main.py
