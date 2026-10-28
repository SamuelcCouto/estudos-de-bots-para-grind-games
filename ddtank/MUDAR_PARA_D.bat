@echo off
chcp 65001 >nul
setlocal
rem Cria uma copia NOVA e LEVE do bot no disco D: (so a versao atual, sem o historico de gravacoes antigas)
rem e copia para la o que o bot aprendeu neste PC. Nada e apagado do C:.
set "ORIGEM=%~dp0.."
set "DESTINO=D:\estudos-de-bots-para-grind-games"
if not exist D:\ (
  echo Nao achei o disco D:.
  pause
  exit /b 1
)
for /f "delims=" %%u in ('git -C "%ORIGEM%" remote get-url origin') do set "URL=%%u"
if "%URL%"=="" set "URL=https://github.com/samuelccouto/estudos-de-bots-para-grind-games.git"
echo Origem : %ORIGEM%
echo Destino: %DESTINO%
echo.
echo 1) baixa o bot (versao atual, sem historico: poucos MB) para o D:
echo 2) copia o que o bot aprendeu: dados\aprendizado.json, dados\combos.json, dados\modelos_aprendidos e logs
echo Feche o bot antes de continuar.
pause
if exist "%DESTINO%\.git" (
  echo Ja existe %DESTINO% - so atualizando.
  git -C "%DESTINO%" pull --autostash
) else (
  git clone --depth 1 -b claude/wonderful-rubin-3oyqi3 "%URL%" "%DESTINO%"
  if errorlevel 1 (
    echo ERRO ao baixar. Confira a internet/login do GitHub e tente de novo.
    pause
    exit /b 1
  )
)
robocopy "%ORIGEM%\ddtank\dados" "%DESTINO%\ddtank\dados" aprendizado.json combos.json /NJH /NJS /NP >nul
robocopy "%ORIGEM%\ddtank\dados\modelos_aprendidos" "%DESTINO%\ddtank\dados\modelos_aprendidos" /E /NJH /NJS /NP >nul
robocopy "%ORIGEM%\ddtank\logs" "%DESTINO%\ddtank\logs" /E /NJH /NJS /NP >nul
echo.
echo PRONTO! A partir de agora use os .bat da pasta %DESTINO%\ddtank
echo (o ATIRAR.bat de la grava tudo no D:). Abra o jogo e teste um ATIRAR.bat de la.
echo Quando estiver funcionando, apague a pasta antiga do C: pelo Explorer:  %ORIGEM%
echo (isso libera o espaco: as gravacoes antigas e o historico do git ficam todos la).
start "" explorer "%DESTINO%\ddtank"
pause
