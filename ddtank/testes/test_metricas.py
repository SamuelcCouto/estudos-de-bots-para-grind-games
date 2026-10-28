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

def luta(inst, danos, venceu=True, aviao=False, dur=30.0, cartas=20.0, menus=15.0):
    m.instancia_inicio(inst, 0)
    relogio[0] += menus
    m.batalha_inicio(inst, 0)
    if aviao:
        m.turno("aviao")
    for d in danos:
        m.turno("ataque", itens=[2, 3, 4], combo="A")
        m.resultado_tiro(d, d > 3)
    relogio[0] += dur
    m.batalha_fim(venceu)
    relogio[0] += cartas
    if venceu:
        m.instancia_fim(inst)

for _ in range(3):
    luta("RAINHA_LIRIS", [100.0], dur=30)                   # mata no 1o turno
    luta("ESCORPIAO_REI", [62.0, 38.0], dur=44, aviao=True)  # acerta mas nao mata: precisa upar
    luta("DRAGAO_GELADO", [0.0, 70.0, 30.0], dur=60)         # o 1o tiro erra: pontaria
    m.volta_fim(len(m.voltas) + 1)
luta("ESCORPIAO_REI", [40.0], venceu=False, dur=25)          # derrota (empurrado para fora)

txt = m.texto_relatorio()
print(txt)
r = m.por_instancia()
assert r["RAINHA_LIRIS"]["mata_no_1o"] == 1.0 and "OK - mata no 1o turno" in M.Metricas.diagnostico("RAINHA_LIRIS", r["RAINHA_LIRIS"])
assert "PRECISA UPAR" in M.Metricas.diagnostico("ESCORPIAO_REI", r["ESCORPIAO_REI"])
assert r["ESCORPIAO_REI"]["derrotas"] == 1 and r["ESCORPIAO_REI"]["avioes"] == 3
assert "PONTARIA" in M.Metricas.diagnostico("DRAGAO_GELADO", r["DRAGAO_GELADO"])
assert abs(r["RAINHA_LIRIS"]["luta_media"] - 30) < 0.01 and abs(r["RAINHA_LIRIS"]["instancia_media"] - 65) < 0.01
assert len(m.voltas) == 3 and "voltas/hora" in txt
linhas = list(csv.reader(open(os.path.join(pasta, "lutas.csv"), encoding="utf-8"), delimiter=";"))
assert len(linhas) == 1 + 10 and linhas[0][0] == "data", len(linhas)
assert len(list(csv.reader(open(os.path.join(pasta, "voltas.csv"), encoding="utf-8")))) == 1 + 3
assert os.path.exists(os.path.join(pasta, "relatorio.txt"))
assert any("[TEMPO] Rainha Liris: luta 30s - VITORIA em 1 turno" in l for l in logs), logs[:3]
shutil.rmtree(pasta)
print("cronometro e diagnostico OK\n")

# ------------------------------------------------------------ combos de itens
arq = os.path.join(tempfile.mkdtemp(), "combos.json")
c = C.Combos(arq=arq)
# instancia que ja morre no 1o turno com o combo padrao: nao mexe
for _ in range(3):
    c.registrar("RAINHA_LIRIS", "A", 100.0)
assert c.escolher("RAINHA_LIRIS")[0] == "A"
# instancia que nao morre: testa cada combo 2x e fica com o que mais tira vida
dano = {"A": 62.0, "B": 78.0, "C": 55.0, "D": 58.0}
testados = []
for _ in range(8):
    nome, ordem, motivo = c.escolher("ESCORPIAO_REI")
    testados.append(nome)
    c.registrar("ESCORPIAO_REI", nome, dano[nome])
print("combos testados no Escorpiao:", testados)
assert sorted(set(testados)) == ["A", "B", "C", "D"]
nome, ordem, motivo = c.escolher("ESCORPIAO_REI")
print("escolhido:", nome, motivo)
assert nome == "B"
# se um combo passa a matar no 1o turno, fica com ele
for _ in range(3):
    c.registrar("ESCORPIAO_REI", "C", 100.0)
assert c.escolher("ESCORPIAO_REI")[0] == "C"
# persistencia + ordem definida pelo usuario
assert C.Combos(arq=arq).escolher("ESCORPIAO_REI")[0] == "C"
assert C.Combos(arq=arq, fixo=[3, 4, 4]).escolher("ESCORPIAO_REI")[1] == [3, 4, 4]
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
