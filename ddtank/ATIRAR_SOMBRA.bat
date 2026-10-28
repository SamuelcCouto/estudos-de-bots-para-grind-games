@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo SOMBRA: navega e, na batalha, so MOSTRA o tiro que faria. Grava. F8 pausa, F10 sai. USE SO UM BOT POR VEZ.
python navegador.py --sombra
call "%~dp0EMPACOTAR_E_ENVIAR.bat"
