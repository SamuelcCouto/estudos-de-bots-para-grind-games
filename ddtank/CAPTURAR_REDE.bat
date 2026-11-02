@echo off
chcp 65001 >nul
rem Captura SO o trafego do jogo (porta TCP 25565) com o pktmon, que ja vem no Windows. Nao altera o jogo: so le.
rem Pede administrador sozinho (o Windows mostra a janela "Deseja permitir...?": clique em Sim).
net session >nul 2>&1
if %errorlevel% neq 0 (
    powershell -NoProfile -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
    exit /b
)
cd /d "%~dp0"
title Captura da rede do DDTank
set "PASTA=%~dp0capturas_rede"
if not exist "%PASTA%" mkdir "%PASTA%"
for /f %%i in ('powershell -NoProfile -Command "Get-Date -Format yyyyMMdd_HHmmss"') do set "DATA=%%i"
set "ETL=%PASTA%\rede_%DATA%.etl"
set "PCAP=%PASTA%\rede_%DATA%.pcapng"

pktmon stop >nul 2>&1
pktmon filter remove >nul 2>&1
pktmon filter add DDTank -t TCP -p 25565 >nul
pktmon start --capture --comp nics --pkt-size 0 --file-name "%ETL%"
if %errorlevel% neq 0 (
    echo.
    echo ERRO ao iniciar a captura. Tire um print desta janela e mande para o Claude.
    pause
    exit /b
)
echo.
echo ================================================================
echo  CAPTURANDO o trafego do jogo.
echo  Agora jogue normalmente (1 ou 2 partidas de PVP).
echo  Quando terminar, volte aqui e aperte qualquer tecla.
echo ================================================================
pause >nul
pktmon stop
pktmon etl2pcap "%ETL%" --out "%PCAP%"
pktmon filter remove >nul
echo.
echo Pronto: %PCAP%
echo Pode fechar esta janela e avisar o Claude.
pause
