@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo TESTE DA FORCA: entre numa batalha e espere a sua vez (botao PASS).
python bot_ddtank.py --teste-forca
pause
