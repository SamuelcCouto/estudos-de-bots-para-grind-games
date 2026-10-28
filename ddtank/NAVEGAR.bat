@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo NAVEGADOR: F8 = pausar, F10 = sair. O bot percorre a rota de instancias.
python navegador.py
pause
