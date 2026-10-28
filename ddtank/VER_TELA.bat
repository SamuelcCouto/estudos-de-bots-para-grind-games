@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo Mostra a tela que o bot reconhece (nao clica). Ctrl+C para sair.
python navegador.py --so-ver
pause
