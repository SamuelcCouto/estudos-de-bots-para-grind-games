@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo Jogue normalmente. F9 = marcador, F10 = terminar.
python gravador.py
if errorlevel 1 goto fim
python empacotar.py
choice /m "Enviar para o GitHub agora"
if errorlevel 2 goto fim
call "%~dp0ENVIAR_SESSAO.bat"
:fim
pause
