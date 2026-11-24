@echo off
cd /d "%~dp0"
if not exist .venv (
  echo Criando ambiente Python na primeira execucao...
  python -m venv .venv
  .venv\Scripts\python -m pip install --upgrade pip
  .venv\Scripts\pip install -r requirements.txt
)
.venv\Scripts\python DWLAW.PY.Selenium.GLPI.AberturaChamado.py
if errorlevel 1 pause
