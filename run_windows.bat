@echo off
cd /d "%~dp0"
echo Creating virtual environment...
py -3.11 -m venv .venv
if errorlevel 1 py -m venv .venv
call .venv\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements.txt
if errorlevel 1 (
  echo Dependency installation failed. Check Python version and internet connection.
  pause
  exit /b 1
)
python app.py
pause
