@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo ATIRADOR LIGADO: navega E joga os turnos. Grava. F8 pausa, F10 sai. USE SO UM BOT POR VEZ.
python navegador.py --atirar
call "%~dp0EMPACOTAR_E_ENVIAR.bat"
