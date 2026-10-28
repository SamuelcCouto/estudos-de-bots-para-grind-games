@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo Jogue normalmente. F9 = marcador, F10 = terminar.
python gravador.py
python empacotar.py
pause
