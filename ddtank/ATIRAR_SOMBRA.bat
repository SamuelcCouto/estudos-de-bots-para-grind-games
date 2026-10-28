@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo SOMBRA: navega e, na batalha, so MOSTRA o tiro que faria. Voce atira. F8 pausa, F10 sai.
python navegador.py --sombra
pause
