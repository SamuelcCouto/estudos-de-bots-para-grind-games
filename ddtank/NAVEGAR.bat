@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo NAVEGADOR (so navega; a batalha e sua). Grava o que faz. F8 pausa, F10 sai. USE SO UM BOT POR VEZ.
python navegador.py
call "%~dp0EMPACOTAR_E_ENVIAR.bat"
