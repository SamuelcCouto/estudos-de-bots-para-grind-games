@echo off
chcp 65001 >nul
cd /d "%~dp0"
python empacotar.py
choice /m "Enviar a gravacao para o GitHub agora"
if errorlevel 2 goto fim
call "%~dp0ENVIAR_SESSAO.bat"
:fim
