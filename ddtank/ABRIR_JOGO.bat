@echo off
chcp 65001 >nul
rem Abre o jogo com o "registro de rede" ligado (o bot le dele as posicoes, o vento e o resultado de cada tiro: mira EXATA).
rem Sem administrador e sem instalar nada. Depois: faca login, entre na sala do PVP e rode o PVP.bat.
rem ATENCAO: o registro guarda os dados de rede do launcher; fica so em capturas_rede\ (nao mande para ninguem).
cd /d "%~dp0"
python rede_vivo.py --so-abrir
pause
