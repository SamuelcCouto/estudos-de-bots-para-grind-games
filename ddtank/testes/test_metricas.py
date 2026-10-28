# -*- coding: utf-8 -*-
"""Cronometro/relatorio, escolha de combos de itens e gravacao leve. Rode: python testes/test_metricas.py"""
import csv
import os
import shutil
import sys
import tempfile

import numpy as np

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(AQUI))
import combos as C
import metricas as M
import registro as R

# ------------------------------------------------------------ cronometro e diagnostico
pasta = tempfile.mkdtemp()
relogio = [0.0]
logs = []
m = M.Metricas("Rota Sul", pasta=pasta, agora=lambda: relogio[0], log=logs.append)

def luta(inst, danos, venceu=True, aviao=False, dur=30.0, cartas=20.0, menus=15.0, combo="2,3,4"):
    m.instancia_inicio(inst, 0)
    relogio[0] += menus
    m.batalha_inicio(inst, 0)
    if aviao:
        m.turno("aviao")
    for d in danos:
        m.turno("ataque", itens=[2, 3, 4], combo=combo)
        m.resultado_tiro(d, d > 3)
    relogio[0] += dur
    m.batalha_fim(venceu)
    relogio[0] += cartas
    if venceu:
        m.instancia_fim(inst)

for _ in range(5):
    luta("RAINHA_LIRIS", [100.0], dur=30)                   # mata no 1o turno
    luta("ESCORPIAO_REI", [62.0, 38.0], dur=44, aviao=True)  # teste de fogo acerta e nao mata: precisa upar
    luta("DRAGAO_GELADO", [0.0, 70.0, 30.0], dur=60)         # o 1o tiro erra: pontaria
    m.volta_fim(len(m.voltas) + 1)
luta("ESCORPIAO_REI", [40.0], venceu=False, dur=25)          # derrota (empurrado para fora)

txt = m.texto_relatorio()
print(txt)
r = m.por_instancia()
d = {i: M.Metricas.diagnostico(i, r[i]) for i in r}
assert r["RAINHA_LIRIS"]["mata_no_1o"] == 1.0 and d["RAINHA_LIRIS"].startswith("OK - mata no 1o turno")
assert "pode ter sido critico" in d["RAINHA_LIRIS"], "com poucas lutas, avisa que pode ter sido critico"
assert d["ESCORPIAO_REI"].startswith("PRECISA UPAR - TESTE DE FOGO"), d["ESCORPIAO_REI"]
assert r["ESCORPIAO_REI"]["derrotas"] == 1 and r["ESCORPIAO_REI"]["avioes"] == 5
assert d["DRAGAO_GELADO"].startswith("PONTARIA"), d["DRAGAO_GELADO"]
assert abs(r["RAINHA_LIRIS"]["luta_media"] - 30) < 0.01 and abs(r["RAINHA_LIRIS"]["instancia_media"] - 65) < 0.01
assert len(m.voltas) == 5 and "voltas/hora" in txt
linhas = list(csv.reader(open(os.path.join(pasta, "lutas.csv"), encoding="utf-8"), delimiter=";"))
assert len(linhas) == 1 + 16 and linhas[0][0] == "data", len(linhas)
assert len(list(csv.reader(open(os.path.join(pasta, "voltas.csv"), encoding="utf-8")))) == 1 + 5
assert os.path.exists(os.path.join(pasta, "relatorio.txt"))
assert any("[TEMPO] Rainha Liris: luta 30s - VITORIA em 1 turno" in l for l in logs), logs[:3]
shutil.rmtree(pasta)
print("cronometro e diagnostico OK\n")

# ------------------------------------------------------------ combos de itens: a luta mais curta, sem se enganar com critico
rng = np.random.default_rng(7)
# mundo: (chance de matar no 1o ataque, tempo se mata, tempo se nao mata) de cada combo, por instancia
MUNDO = {
    "FANTASMA": {"2,3,4": (1.0, 26, 45), "2,4": (1.0, 21, 40), "4": (0.1, 18, 40),   # "4" so mata quando crita
                 "3,4": (0.9, 25, 45), "1,4": (0.95, 29, 48), "3,3,4": (1.0, 30, 50)},
    "ESCORPIAO_REI": {c: (0.03, 30, 44) for c in C.COMBOS},                             # nem o fogo mata
}
arq = os.path.join(tempfile.mkdtemp(), "combos.json")
c = C.Combos(arq=arq)
usados = {"FANTASMA": [], "ESCORPIAO_REI": []}
for _ in range(80):
    for inst, tab in MUNDO.items():
        nome, ordem, motivo = c.escolher(inst)
        usados[inst].append(nome)
        p, t_mata, t_nao = tab[nome]
        mata = rng.random() < p
        c.registrar_luta(inst, nome, (t_mata if mata else t_nao) + rng.normal(0, 2), mata, 100.0 if mata else 60.0)
fim = usados["FANTASMA"][-20:]
print("Fantasma - combos nas 20 ultimas lutas:", {k: fim.count(k) for k in set(fim)}, "| motivo:", c.escolher("FANTASMA")[2])
assert fim.count("2,4") >= 15, "deveria ficar com 2,4 (mata no 1o turno com uma animacao so)"
assert usados["FANTASMA"].count("4") <= 8, "o combo que so mata com critico nao pode ser escolhido de vez"
print("Escorpiao:", c.escolher("ESCORPIAO_REI")[2])
assert c.precisa_upar("ESCORPIAO_REI") and set(usados["ESCORPIAO_REI"][5:]) == {"2,3,4"}, set(usados["ESCORPIAO_REI"][5:])
print("\n".join(c.texto()))
# persistencia + ordem definida pelo usuario
assert C.Combos(arq=arq).escolher("FANTASMA")[0] == c.escolher("FANTASMA")[0]
assert C.Combos(arq=arq, fixo=[3, 4, 4]).escolher("FANTASMA")[1] == [3, 4, 4]
print("escolha de combos OK\n")

# ------------------------------------------------------------ gravacao leve
base = tempfile.mkdtemp()
reg = R.Registro("teste", base=base, leve=True)
img = np.zeros((688, 1280, 3), np.uint8)
assert reg.frame(img, "leitura") is None and reg.frame(img, "clique_antes") is None, "leve: sem prints de rotina"
assert reg.frame(img, "turno_inicio") is not None
assert reg.frame(img, "turno_inicio") is None, "leve: no maximo 1 print de turno a cada alguns minutos"
assert reg.frame(img, "sem_cartas") is not None, "leve: problemas sempre tem print"
reg.evento("leitura", [reg.frame(img, "leitura")], vida=50)
reg.fechar()
assert len(os.listdir(os.path.join(reg.pasta, "frames"))) == 2
shutil.rmtree(base)
print("gravacao leve OK")
print("\nmetricas OK")
