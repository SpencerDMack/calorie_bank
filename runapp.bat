@echo off
setlocal

set "ROOT=%~dp0"
cd /d "%ROOT%"

if not exist ".venv\Scripts\python.exe" (
  echo Creating virtual environment in "%ROOT%.venv"...
  py -3 -m venv .venv 2>nul || python -m venv .venv
  if not exist ".venv\Scripts\python.exe" (
    echo Failed to create .venv. Make sure Python 3 is installed and on PATH.
    pause
    exit /b 1
  )

  if not exist "requirements.txt" (
    echo requirements.txt not found in "%ROOT%".
    pause
    exit /b 1
  )

  echo Installing dependencies from requirements.txt...
  ".venv\Scripts\python.exe" -m pip install --upgrade pip
  ".venv\Scripts\python.exe" -m pip install -r requirements.txt
)

".venv\Scripts\python.exe" -m streamlit run app.py
pause
endlocal
