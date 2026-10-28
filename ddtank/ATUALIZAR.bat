@echo off
chcp 65001 >nul
cd /d "%~dp0"
git pull --autostash
echo.
echo Atualizado. Feche e abra os .bat de novo.
pause
