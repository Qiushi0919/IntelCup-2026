@echo off
setlocal
cd /d "%~dp0"
set PYTHONUTF8=1
set PIP_DEFAULT_TIMEOUT=120

if not exist ".venv\Scripts\python.exe" (
  echo Creating the isolated demo environment...
  py -3.12 -m venv .venv
  if errorlevel 1 goto :failed
)

echo Checking face, OCR and camera dependencies...
".venv\Scripts\python.exe" -m pip install --disable-pip-version-check --quiet -r requirements.txt
if errorlevel 1 goto :failed

echo Starting USB camera inspection demo...
pushd ..
"inspection_demo\.venv\Scripts\python.exe" -m inspection_demo.app --source 0
set DEMO_EXIT=%ERRORLEVEL%
popd
if not "%DEMO_EXIT%"=="0" goto :failed
exit /b 0

:failed
echo.
echo Demo failed. See the message above.
pause
exit /b 1
