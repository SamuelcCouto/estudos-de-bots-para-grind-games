# -*- coding: utf-8 -*-
"""Mira exata no PVE (pve_rede.py + atirador): elite bloqueando, ponto livre, calibracao da carga pelo relogio."""
import os
import struct
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import numpy as np

import pve_rede
import rede_ddt as R
import rede_vivo as RV


class FalsaRede:
    def __init__(self, est):
        self.estado = est


def estado(eu=(185, 819), elites=(), boss=(769, 320)):
    est = RV.Estado()
    est.eu = 0
    est.vivos = {0: dict(id=0, x=eu[0], y=eu[1], vivo=True)}
    est.mapa, est.vento = 11688, 1.4
    est.monstros = {119: dict(id=119, nome="Juiz", x=boss[0], y=boss[1], vida=1000000, vida_max=1646880, vivo=True)}
    for i, e in enumerate(elites):
        est.monstros[200 + i] = dict(id=200 + i, nome="Boxeador", x=e[0], y=e[1], vida=300000, vida_max=304500, vivo=True)
    return est


# ---- info(): boss = o de maior vida; elites vivos no chao
mp = pve_rede.MiraPve(FalsaRede(estado(elites=[(316, 838)])))
i = mp.info()
assert i["boss"] == (769, 320) and i["elites"] == [(316, 838)] and i["eu"] == (185, 819), i
print("info: boss, elite e boneco lidos da rede OK")

# ---- elite perto: so a < 80 px em x (bloqueou a 12-21 px, passou a >= 107)
for x_el, perto in ((190, True), (205, True), (260, True), (316, False), (100, False)):
    mp = pve_rede.MiraPve(FalsaRede(estado(elites=[(x_el, 838)])))
    assert (mp.elite_perto(mp.info()) is not None) == perto, (x_el, perto)
print("elite a menos de 80 px bloqueia, a 130 px nao OK")

# ---- ponto livre: para a direita do elite, ate elite + 100
mp = pve_rede.MiraPve(FalsaRede(estado(elites=[(190, 838)])))
assert mp.ponto_livre(mp.info()) == 190 + pve_rede.ELITE_FOLGA_PX          # 190 - 150 = 40 fica na parede: so a direita
mp = pve_rede.MiraPve(FalsaRede(estado(elites=[(316, 838)])))
assert mp.ponto_livre(mp.info()) is None, "elite longe: nao anda"
print("ponto livre: anda so quando o elite bloqueia OK")

# ---- lado direito: boss a esquerda; ponto livre so em x >= 1090 (de 1062 nao ha mira)
est = estado(eu=(1162, 837), elites=[(1162, 838)])
mp = pve_rede.MiraPve(FalsaRede(est))
i = mp.info()
assert i["direcao"] == -1, i["direcao"]
assert mp.ponto_livre(i) == 1312, mp.ponto_livre(i)           # 1012 fica fora da faixa viavel
est = estado(eu=(1300, 837), elites=[(1300, 838)])
mp = pve_rede.MiraPve(FalsaRede(est))
assert mp.ponto_livre(mp.info()) == 1150, "do outro lado do elite tambem vale (1150 e 1450 a 150 px; vale o 1o)"
print("lado direito: ponto livre dentro da faixa com mira OK")

# ---- elite morto nao conta
est = estado(elites=[(190, 838)])
est.monstros[200]["vivo"] = False
mp = pve_rede.MiraPve(FalsaRede(est))
assert mp.info()["elites"] == [] and mp.ponto_livre(mp.info()) is None
print("elite morto nao bloqueia OK")

# ---- Estado: ADD_LIVING / LIVING_MOVETO / KILL_PLAYER mantem os monstros
est = RV.Estado()
est.monstros = {35: dict(id=35, nome="Boxeador", x=199, y=839, vida=304500, vida_max=304500, vivo=True)}
corpo = bytes([55]) + struct.pack(">iiii", 199, 839, 316, 838) + struct.pack(">i", 4) + b"\x00\x04walk"
est.processar("servidor", (R.GAME_CMD, 0, 35, 0, corpo))
assert (est.monstros[35]["x"], est.monstros[35]["y"]) == (316, 838), est.monstros[35]
print("LIVING_MOVETO atualiza a posicao do elite OK")


# ---- calibracao da carga pelo relogio
class A:  # so o que tempo_relogio usa
    amostras_carga = []


import atirador

a = A()
assert atirador.Atirador.tempo_relogio(a, 54.0) is None, "sem amostras: None"
a.amostras_carga = [(1.9, 55.0), (1.9, 56.0), (1.8, 53.0)]
t = atirador.Atirador.tempo_relogio(a, 54.0)
assert 1.7 < t < 2.0, t                       # ~29%/s: 54% em ~1,85 s
a.amostras_carga = [(1.0, 29.0), (1.5, 43.5), (2.0, 58.0), (2.5, 72.5)]   # reta f = 29 s
assert abs(atirador.Atirador.tempo_relogio(a, 58.0) - 2.0) < 0.05
print("tempo de carga pelo relogio (a partir da forca real dos tiros) OK")

# ---- planejar sem terreno da internet: so confere que devolve None sem quebrar quando nao ha terreno
mp = pve_rede.MiraPve(FalsaRede(estado()))
mp._ter = ((11688, 0), None)
assert mp.planejar(mp.info(), 70) is None
print("sem terreno: sem plano (usa a memoria) OK")
