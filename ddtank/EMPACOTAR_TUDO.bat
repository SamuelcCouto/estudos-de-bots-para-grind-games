@echo off
chcp 65001 >nul
cd /d "%~dp0"
rem Empacota a gravacao mais recente com TODOS os prints (so quando eu pedir: pode dar centenas de MB)
python empacotar.py --tudo
echo.
echo Pronto. Volte ao BotDDT e clique em "Enviar gravacao para o GitHub".
pause
