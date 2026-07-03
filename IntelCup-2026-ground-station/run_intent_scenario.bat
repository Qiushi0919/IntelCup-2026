@echo off
cd /d "%~dp0"
set "PYTHON=python"
if exist multimodal_recognition\.venv\Scripts\python.exe set "PYTHON=multimodal_recognition\.venv\Scripts\python.exe"
if exist ..\IntelCup-2026-multimodal-input\multimodal_recognition\.venv\Scripts\python.exe set "PYTHON=..\IntelCup-2026-multimodal-input\multimodal_recognition\.venv\Scripts\python.exe"
%PYTHON% multimodal_recognition\intent_scenario.py --camera 0 --rotate 0 --laser
pause
