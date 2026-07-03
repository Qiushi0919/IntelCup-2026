@echo off
cd /d "%~dp0"
if not exist multimodal_recognition\.venv\Scripts\python.exe (
    python -m venv multimodal_recognition\.venv
)
multimodal_recognition\.venv\Scripts\python.exe -m pip install --upgrade pip
multimodal_recognition\.venv\Scripts\python.exe -m pip install -r multimodal_recognition\requirements.txt
pause
