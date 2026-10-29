@echo off
chcp 65001 >nul
cd /d "%~dp0"
where pythonw >nul 2>nul && (start "" pythonw painel.py) || (python painel.py)
