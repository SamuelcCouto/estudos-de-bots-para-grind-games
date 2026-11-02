# -*- coding: utf-8 -*-
"""Mira exata (mira_exata.py) e a ligacao com o bot do PVP (estado da rede -> plano -> mostrador/forca).
Rode: python testes/test_mira_exata.py"""
import os
import sys
import tempfile
import time

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(AQUI))
import fisica_exata as FX
import mira_exata as ME

# 1) o plano cai no alvo (posicoes/ventos/lados variados), com a saida e a inclinacao que o planejador supoe
m = ME.MiraExata(log=lambda *_: None)
casos = [((499, 489), (1126, 483), 0.5), ((1126, 483), (499, 489), -1.3), ((300, 800), (1500, 600), 2.1),
         ((1700, 630), (777, 1008), -2.0), ((200, 400), (520, 420), 0.0), ((1550, 708), (1300, 760), 1.7)]
for eu, alvo, vento in casos:
    pl = m.planejar(eu, alvo, vento)
    assert pl and ME.MIRA_MIN <= pl["mira"] <= ME.MIRA_MAX and 4 <= pl["forca_pct"] <= 100, (eu, alvo, pl)
    x = FX.x_na_altura(pl["saida"][0], pl["saida"][1], pl["forca"], pl["angulo_envio"], alvo[1] + ME.ALVO_DY, vento)
    assert abs(x - alvo[0]) <= 15, (eu, alvo, vento, x)
    assert (pl["direcao"] > 0) == (alvo[0] > eu[0])
print("plano cai a <= 15 px do alvo em 6 situacoes (lados, alturas e ventos diferentes) OK")

# 2) aprender pelo pacote do proprio tiro: ponto de saida e inclinacao EXATOS
eu = (966, 478)
m.aprender(eu, +1, 85, dict(x=966, y=445, forca=1080, angulo=-98))      # olhando para a direita, mostrador 85 -> angulo -98
saida, inc, medido = m.saida_e_inclinacao(eu, +1)
assert medido and saida == (966, 445) and abs(inc - (-13)) < 1e-9, (saida, inc)
pl = m.planejar(eu, (1400, 470), 0.0)
assert pl["medido"] and pl["inclinacao"] == -13 and pl["saida"] == (966, 445)
assert not m.saida_e_inclinacao((990, 478), +1)[2], "andou: a medida antiga nao vale mais"
m.aprender((1200, 500), -1, 60, dict(x=1190, y=468, forca=900, angulo=-125))   # olhando para a esquerda: -125 = inc + 60 - 180
assert abs(m.saida_e_inclinacao((1200, 500), -1)[1] - (-5)) < 1e-9
print("inclinacao e saida aprendidas pelo pacote do tiro (direita e esquerda) OK")

# 3) resultado do servidor
tiro = dict(atirador=0, vento=0.5, bombas=[dict(acoes=[dict(tempo=2400, tipo="CHANGE_SPEED", p=(1, 2, 0, 0)), dict(tempo=2600, tipo="BOMB", p=(1120, 470, 1, 0))])],
            alvos=[dict(vivo=1, dano=972, vida=1000, furia=0)])
r = ME.resultado_do_tiro(tiro, 1)
assert r["acertou"] and r["dano"] == 972 and r["explodiu"] == (1120, 470) and r["teleguiado"]
assert not ME.resultado_do_tiro(tiro, 5)["acertou"]
print("resultado do tiro (explosao, dano no alvo, teleguiado) OK")

# 4) ligado ao bot do PVP: a vez lida da rede vira o plano; o mostrador vai para a mira do plano e a forca sai a do plano
import memoria as M
import pvp as P

src = open(os.path.join(AQUI, "test_atirador.py"), encoding="utf-8").read()
ns = {"__file__": os.path.join(AQUI, "test_atirador.py")}
exec(compile(src.split("# ------------------------------------------------------------ 1) turno completo")[0], "test_atirador.py", "exec"), ns)
MundoComThread, Leitor = ns["MundoComThread"], ns["Leitor"]


class LeitorT(Leitor):
    vida = staticmethod(lambda f: 100.0)
    itens = staticmethod(lambda f: [False] * 8)
    vento = staticmethod(lambda f: (0.5, 1.4))


class EstadoFalso:
    def __init__(self):
        self.d = dict(eu=None, vez=0, vez_t=time.time(), turno=3, vento=0.5, chave_ok={"servidor": True, "cliente": True},
                      vivos={0: dict(id=0, x=499, y=489, vivo=True), 1: dict(id=1, x=1126, y=483, vivo=True)}, tiros=[], meus_tiros=[])

    def copia(self):
        return dict(self.d)


class RedeFalsa:
    estado = EstadoFalso()


w = MundoComThread()
tmp = tempfile.mkdtemp()
logs = []
mem = P.MemoriaPvp(arq_aprendizado=None)
at = P.AtiradorPvp(w, mem, lambda: "PVP", leitor=LeitorT(), dormir=w.dormir, agora=lambda: w.t, log=logs.append,
                   arq_tentativas=os.path.join(tmp, "t.jsonl"), pasta_vento=os.path.join(tmp, "v"), rede=RedeFalsa())
while w.t < 16.0 and not w.tiros:
    at.passo()
    w.avancar(0.1)
esperado = ME.MiraExata(log=lambda *_: None).planejar((499, 489), (1126, 483), 0.5)
assert any("[rede]" in l and "mira" in l for l in logs), logs
assert w.tiros and abs(w.angulo - esperado["mira"]) <= 2.5, (w.angulo, esperado["mira"], logs)
assert abs(w.tiros[0] - esperado["forca_pct"]) <= 8, (w.tiros, esperado["forca_pct"])
assert any("rede+fisica exata" in l for l in logs)
print(f"bot do PVP com a rede: mira {esperado['mira']} / forca {esperado['forca_pct']:.0f}% do plano exato aplicados OK")
print("\nmira_exata OK")
