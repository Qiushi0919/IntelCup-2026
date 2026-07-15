@echo off
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" -c "import onnxruntime, PIL, rapidocr, psutil, openvino" >nul 2>nul
    if errorlevel 1 (
        echo Installing inspection dependencies...
        ".venv\Scripts\python.exe" -m pip install -r ground_station\requirements.txt
        if errorlevel 1 (
            pause
            exit /b 1
        )
    )
    ".venv\Scripts\python.exe" ground_station\main.py
    goto :eof
)
if exist "%USERPROFILE%\.conda\envs\gluon\python.exe" (
    "%USERPROFILE%\.conda\envs\gluon\python.exe" ground_station\main.py
    goto :eof
)
python ground_station\main.py
