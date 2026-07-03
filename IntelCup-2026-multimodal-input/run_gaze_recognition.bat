@echo off
cd /d "%~dp0"
set "PYTHON=python"
if exist multimodal_recognition\.venv\Scripts\python.exe set "PYTHON=multimodal_recognition\.venv\Scripts\python.exe"
%PYTHON% multimodal_recognition\gaze_three_point.py --rotate 0 --min-confidence 0.62 --head-priority 0.72 --laser --laser-base-offset 0.02 --laser-vertical-scale 8.0
pause
