@echo off
chcp 65001 >nul
rem Testa a leitura AO VIVO da rede do jogo (so le; nao altera nada). Nao precisa instalar nada: usa so o Python.
rem Pede administrador sozinho (o Windows mostra "Deseja permitir...?": clique em Sim).
net session >nul 2>&1
if %errorlevel% neq 0 (
    powershell -NoProfile -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
    exit /b
)
cd /d "%~dp0"
title Teste da leitura da rede do DDTank
echo Deixe o jogo aberto e entre numa partida (PVP ou instancia).
echo Esta janela vai mostrar de quem e a vez, as posicoes, o vento e o resultado de cada tiro.
echo Para terminar: feche esta janela (ou Ctrl+C).
echo.
python rede_vivo.py
echo.
echo Terminou. Tire um print desta janela e mande para o Claude.
pause
