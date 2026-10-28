# -*- coding: utf-8 -*-
"""Leituras da batalha contra quadros reais da gravacao. Rode: python testes/test_leitura.py"""
import os
import sys

import cv2
import numpy as np

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(AQUI))
import leitura as L

img = lambda nome: cv2.imread(os.path.join(AQUI, "frames", nome + ".jpg"))

# angulo: gabarito lido a olho no mostrador (numero verde/colorido)
GAB = {2: 16, 42: 16, 100: 14, 156: 33, 219: 18, 275: 34, 355: 18, 412: 21, 470: 33, 534: 16, 591: 34, 649: 23}
erros = [abs(L.angulo(img(f"ANG_{i}")) - v) for i, v in GAB.items()]
print(f"angulo: erro medio {np.mean(erros):.1f} graus, maximo {np.max(erros):.1f}")
assert np.mean(erros) < 3.2 and np.max(erros) < 6, "leitura do angulo piorou"

# sua vez (PASS)
assert all(L.minha_vez(img(f"VEZ_SIM_{i}")) for i in (21, 74, 214, 415, 602))
assert not any(L.minha_vez(img(f"VEZ_NAO_{i}")) for i in (2, 66, 92, 355, 580))
print("minha_vez OK")

# itens: #63 todos coloridos, #80 nenhum
assert L.itens_ativos(img("ITENS_63")) == [True] * 8, L.itens_ativos(img("ITENS_63"))
assert L.itens_ativos(img("ITENS_80")) == [False] * 8, L.itens_ativos(img("ITENS_80"))
assert L.itens_ativos(img("VEZ_SIM_74")) == [False] * 7 + [True], L.itens_ativos(img("VEZ_SIM_74"))   # so o 8 sobrou
print("itens OK")

# vida do boss
assert L.vida_boss(img("VEZ_SIM_74")) > 95 and 30 <= L.vida_boss(img("HP_42")) <= 52, (L.vida_boss(img("VEZ_SIM_74")), L.vida_boss(img("HP_42")))
print("vida OK", round(L.vida_boss(img("VEZ_SIM_74"))), round(L.vida_boss(img("HP_42"))))

# barra de forca: cresce enquanto segura e fica no valor final depois
f = [L.forca(img(f"TIRO_{i}")) for i in (75, 84, 85, 86)]
print("forca nos quadros do tiro:", [round(v) for v in f])
assert f[0] < 5 and f[1] > 30 and abs(f[2] - f[3]) < 3

# minimapa: jogador a esquerda do boss (Profundezas: azul ~(12,34), vermelho ~(66,46))
az, vm = L.pontos_minimapa(img("TIRO_75"))
print("minimapa:", az, vm)
assert az and vm and vm[0] - az[0] > 30
print("\nleituras OK")
