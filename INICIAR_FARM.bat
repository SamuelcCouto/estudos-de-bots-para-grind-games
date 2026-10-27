@echo off
chcp 65001 >nul
title Social Empires - Auto Farm
cd /d "%~dp0"

rem Reabre o launcher com flags que mantem o jogo renderizando mesmo
rem minimizado/coberto por outras janelas (necessario para o bot "enxergar").
"%SystemRoot%\System32\tasklist.exe" /FI "IMAGENAME eq Launcher_Social_Empires.exe" | "%SystemRoot%\System32\find.exe" /I "Launcher_Social_Empires" >nul
if not errorlevel 1 (
    echo Fechando o launcher aberto para reabrir no modo do bot...
    "%SystemRoot%\System32\taskkill.exe" /IM Launcher_Social_Empires.exe >nul 2>&1
    "%SystemRoot%\System32\PING.EXE" -n 5 127.0.0.1 >nul
    "%SystemRoot%\System32\taskkill.exe" /F /IM Launcher_Social_Empires.exe >nul 2>&1
    "%SystemRoot%\System32\PING.EXE" -n 3 127.0.0.1 >nul
)

start "" "%~dp0..\Launcher_Social_Empires.exe" --disable-features=CalculateNativeWinOcclusion --disable-backgrounding-occluded-windows --disable-renderer-backgrounding --disable-background-timer-throttling

echo Aguardando o launcher abrir...
"%SystemRoot%\System32\PING.EXE" -n 16 127.0.0.1 >nul

python "%~dp0se_autofarm.py"
pause
