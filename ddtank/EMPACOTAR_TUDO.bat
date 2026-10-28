@echo off
chcp 65001 >nul
cd /d "%~dp0"
rem Empacota a gravacao mais recente com TODOS os prints (so quando eu pedir: pode dar centenas de MB)
python empacotar.py --tudo
choice /m "Enviar a gravacao para o GitHub agora"
if errorlevel 2 goto fim
call "%~dp0ENVIAR_SESSAO.bat"
:fim
