# -*- coding: utf-8 -*-
"""Configuracao do bot de DDTank. Preencha depois de rodar:  python bot_ddtank.py --listar"""
import os

# Como achar a janela do launcher. Preencha pelo menos um (ou passe --titulo / --exe).
TITULO_JANELA = ""   # trecho do titulo da janela, ex.: "DDTank"
EXE_JANELA = ""      # nome do .exe do launcher, ex.: "Launcher.exe"

PASTA = os.path.dirname(os.path.abspath(__file__))
PASTA_CAPTURAS = os.path.join(PASTA, "capturas")
PASTA_LOGS = os.path.join(PASTA, "logs")
PASTA_TEMPLATES = os.path.join(PASTA, "templates")
