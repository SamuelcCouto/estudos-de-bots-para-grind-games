@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo SIMULACAO: mostra o que o bot clicaria, sem clicar.
python navegador.py --simular
pause
