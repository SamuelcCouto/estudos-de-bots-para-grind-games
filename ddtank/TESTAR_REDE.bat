@echo off
chcp 65001 >nul
rem Testa a leitura AO VIVO da rede do jogo (so le; nao altera nada). Sem administrador e sem instalar nada.
rem Abre o jogo com o "registro de rede" do Chromium ligado (o BetelTank e um Chromium por dentro) e le esse registro ao vivo.
rem ATENCAO: o registro guarda os dados de rede do launcher; nao mande o arquivo de capturas_rede\ para ninguem.
cd /d "%~dp0"
title Teste da leitura da rede do DDTank
echo 1) Se o jogo estiver aberto, FECHE o jogo (esta janela vai pedir).
echo 2) O jogo vai abrir sozinho. Entre e va para uma partida (PVP ou instancia).
echo 3) Esta janela vai mostrar de quem e a vez, as posicoes, o vento e o resultado de cada tiro.
echo Para terminar: feche esta janela (ou Ctrl+C). O jogo continua aberto.
echo.
python rede_vivo.py --abrir-jogo
echo.
echo Terminou. Tire um print desta janela e mande para o Claude.
pause
