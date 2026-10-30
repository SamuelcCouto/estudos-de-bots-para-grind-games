@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo ============================================================
echo  LIMPEZA do BotDDT (versao desenvolvedor)
echo ============================================================
echo Vai APAGAR deste PC (nada disso e codigo, tudo pode ser regerado):
echo   - sessoes\   (gravacoes do bot e da sua jogada)
echo   - envio\*.zip (pacotes para enviar)
echo   - logs\      (relatorios, csv, logs do dia)
echo   - capturas\, debug\ e todas as pastas __pycache__
echo   - a pasta botDDTGPT, se ainda existir
echo Vai MANTER: o codigo, templates\, dados\ (o que o bot aprendeu) e testes\.
echo.
choice /m "Apagar agora"
if errorlevel 2 goto fim
if exist sessoes rmdir /s /q sessoes
if exist logs rmdir /s /q logs
if exist capturas rmdir /s /q capturas
if exist debug rmdir /s /q debug
if exist botDDTGPT rmdir /s /q botDDTGPT
if exist envio del /q envio\*.zip
for /d /r %%d in (__pycache__) do if exist "%%d" rmdir /s /q "%%d"
echo.
echo Pronto. (O .git guarda o historico; para encolher o repositorio, peca a limpeza do historico.)
:fim
pause
