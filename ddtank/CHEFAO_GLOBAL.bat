@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo CHEFAO GLOBAL (Pericao): o bot entra, luta ate o servidor derrubar o chefao e espera o proximo horario.
echo Horarios: 12h-13h e 21h-22h (mude com --horarios-chefe). Grava. F8 pausa, F10 sai. USE SO UM BOT POR VEZ.
python navegador.py --atirar --rota C
call "%~dp0EMPACOTAR_E_ENVIAR.bat"
