@echo off
cd /d "%~dp0"
set "PYTHON=python"
if exist multimodal_recognition\.venv\Scripts\python.exe set "PYTHON=multimodal_recognition\.venv\Scripts\python.exe"
%PYTHON% multimodal_recognition\gesture_three.py --rotate 0 --min-confidence 0.65
pause
