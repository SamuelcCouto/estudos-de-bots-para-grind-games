@echo off
chcp 65001 >nul
cd /d "%~dp0"
title PVP - jogando e gravando
echo PVP: o bot joga os turnos e grava as tentativas (ate 60 min; F10 para parar).
echo Deixe o jogo na SALA do PVP (ou em partida). Para iniciar as partidas voce mesmo: PVP.bat --sem-inicio
python pvp.py %*
echo.
echo Terminou. Clique em "Enviar gravacao" no BotDDT para me mandar (os prints de cada tiro vao junto).
pause
