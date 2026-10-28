@echo off
chcp 65001 >nul
cd /d "%~dp0"
git add envio
git commit -m "sessao gravada"
git pull --rebase --autostash
git push
echo.
echo Se nao apareceu nenhum erro (error/fatal) acima, o envio deu certo.
pause
