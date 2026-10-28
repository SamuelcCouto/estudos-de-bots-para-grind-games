@echo off
chcp 65001 >nul
title Social Empires - Auto Farm (so o bot)
cd /d "%~dp0"
rem Use quando o launcher ja foi aberto pelo INICIAR_FARM.bat.
python "%~dp0se_autofarm.py"
pause
