@echo off
chcp 65001 >nul
cd /d "%~dp0"
rem Gera o BotDDT.exe (nao precisa de Python na maquina de quem recebe). Rode UMA vez aqui, no PC com Python.
python -m pip install --upgrade pyinstaller numpy opencv-python-headless
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
python -m PyInstaller --noconfirm --onedir --windowed --name BotDDT ^
  --add-data "templates;templates" --add-data "dados\tiros_semente.json;dados" ^
  --collect-all cv2 botddt.py
if errorlevel 1 goto erro
copy /y LEIA-ME_AMIGOS.txt dist\BotDDT\LEIA-ME.txt >nul
powershell -NoProfile -Command "Compress-Archive -Path 'dist\BotDDT' -DestinationPath 'BotDDT.zip' -Force"
echo.
echo Pronto: BotDDT.zip (e a pasta dist\BotDDT). Mande o zip para os amigos: descompactar e abrir BotDDT.exe.
goto fim
:erro
echo ERRO ao gerar o exe: me mande o texto acima.
:fim
pause
