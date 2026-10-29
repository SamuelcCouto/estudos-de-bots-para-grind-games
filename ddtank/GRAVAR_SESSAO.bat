@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo Jogue normalmente. F9 = marcador, F10 = terminar.
python gravador.py
if errorlevel 1 goto fim
python empacotar.py
echo.
echo Pronto. Volte ao BotDDT e clique em "Enviar gravacao para o GitHub".
:fim
pause
