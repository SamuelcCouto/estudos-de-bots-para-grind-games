# -*- coding: utf-8 -*-
"""Configuracao do bot de DDTank. O jogo e achado pelo nome do .exe"""
import os
import sys

# Como achar a janela do launcher. Preencha pelo menos um (ou passe --titulo / --exe).
TITULO_JANELA = ""            # trecho do titulo da janela (opcional)
EXE_JANELA = "BetelTank.exe"  # nome do .exe do jogo (confirmado pelo --listar)

# Versao empacotada (BotDDT.exe, feito com PyInstaller): os dados do usuario (logs, sessoes, dados, envio) ficam AO LADO do
# .exe; os arquivos so de leitura (templates, sementes de tiro) vem de dentro do pacote.
CONGELADO = bool(getattr(sys, "frozen", False))
PASTA = os.path.dirname(os.path.abspath(sys.executable)) if CONGELADO else os.path.dirname(os.path.abspath(__file__))
PASTA_RECURSOS = getattr(sys, "_MEIPASS", PASTA) if CONGELADO else PASTA
PASTA_CAPTURAS = os.path.join(PASTA, "capturas")
PASTA_LOGS = os.path.join(PASTA, "logs")
PASTA_TEMPLATES = os.path.join(PASTA_RECURSOS, "templates")
