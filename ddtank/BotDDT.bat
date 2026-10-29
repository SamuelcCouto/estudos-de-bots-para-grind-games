@echo off
chcp 65001 >nul
cd /d "%~dp0"
title BotDDT
echo Baixando novidades...
git pull --autostash >nul 2>nul
where pythonw >nul 2>nul && (start "" pythonw painel.py) || (python painel.py)
