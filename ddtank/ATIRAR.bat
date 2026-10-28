@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo ATIRADOR LIGADO: o bot navega E joga os turnos. F8 pausa, F10 sai.
python navegador.py --atirar
pause
