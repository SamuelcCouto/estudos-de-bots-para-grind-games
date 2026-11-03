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

# 2) aprender pelo pacote do proprio tiro: ponto de saida EXATO e a correcao do ponteiro (o ponteiro ja mostra o angulo real)
eu = (966, 478)
m.aprender(eu, +1, 85, dict(x=966, y=445, forca=1080, angulo=-87))      # olhando para a direita, ponteiro 85 -> angulo -87
saida, _inc, medido = m.saida_e_inclinacao(eu, +1)
assert medido and saida == (966, 445), saida
pl = m.planejar(eu, (1400, 470), 0.0)
assert pl["medido"] and pl["correcao"] == -2 and pl["saida"] == (966, 445) and pl["origem"] == "medida"
assert pl["angulo_envio"] == -2 - pl["mira"], "angulo enviado = -(ponteiro) + correcao"
assert not m.saida_e_inclinacao((990, 478), +1)[2], "andou: a medida antiga nao vale mais"
m.aprender((1200, 500), -1, 60, dict(x=1190, y=468, forca=900, angulo=-125))   # olhando para a esquerda: -125 = 60 - 180 + 5... corr -5
assert abs(m.contexto((1200, 500), -1)[2] - (-5)) < 1e-9
assert m.aprender((1300, 500), +1, 60, dict(x=1330, y=477, forca=900, angulo=-35)) is None, "ponteiro x angulo com 25 graus: lado errado"
print("saida e correcao do ponteiro aprendidas pelo pacote do tiro (direita e esquerda) OK")
m2 = ME.MiraExata(log=lambda *_: None)
m2.limite(True, 49.4, (297, 1383))
pl = m2.planejar((297, 1383), (1182, 811), 1.7)
assert pl and pl["mira"] <= 49, pl["mira"]
assert m2.planejar((900, 1383), (1182, 811), 1.7)["mira"] > 49, "longe de onde travou, o limite nao vale"
print("limite da arma respeitado pelo plano (mira <= 49) OK")

# 2b) terreno: inclinacao (conta do jogo), ponto de saida (cliente) e o plano desviando de um morro
import numpy as np
import terreno_jogo as TJ
chao = np.zeros((1200, 2400), bool)
chao[800:, :] = True                                         # chao plano em y = 800
xs = np.arange(2400)
for x in range(300, 600):                                    # rampa de 30 graus subindo para a esquerda (x 300-600)
    chao[int(800 - (600 - x) * np.tan(np.radians(30))):, x] = True
t = TJ.Terreno(chao.copy(), mapa_id=1, info={"Weight": "10", "DragIndex": "2"})
assert t.inclinacao(1000, 800) == 0.0
inc = t.inclinacao(450, int(800 - 150 * np.tan(np.radians(30))))
assert 28 <= inc <= 32, inc                                 # mais alto a esquerda: o boneco gira no sentido horario (+)
assert TJ.saida_do_tiro((771, 436), +1, -15) == (794, 405), "pacote real: pe (771, 436), inclinacao -15 -> saida (794, 405)"
assert TJ.saida_do_tiro((1000, 800), -1, 0) == (970, 777)
chao2 = chao.copy()
chao2[560:800, 1290:1330] = True                             # muro de 240 px entre nos e o alvo
t2 = TJ.Terreno(chao2, mapa_id=2, info={"Weight": "10", "DragIndex": "2"})
m3 = ME.MiraExata(log=lambda *_: None)
pl_sem = m3.planejar((1000, 800), (1600, 800), 0.0)
pl = m3.planejar((1000, 800), (1600, 800), 0.0, terreno=t2)
assert pl and not pl.get("bloqueado") and pl["acertos"] >= 3 and pl["origem"] == "terreno", pl
r = FX.simular(pl["saida"][0], pl["saida"][1], pl["forca"], pl["angulo_envio"], 0.0, terreno=t2, alvos=[(1585, 765, 1615, 800)],
               largura=t2.largura, altura=t2.altura + 200)
assert r["motivo"] == "alvo", r["motivo"]
print(f"terreno: inclinacao {inc:+.0f} na rampa de 30, saida do tiro igual a do pacote, plano por cima do muro "
      f"(mira {pl['mira']}, {pl['acertos']}/5 variacoes acertam; sem terreno escolheria {pl_sem['mira']}) OK")
t3 = TJ.Terreno(np.ones((100, 100), bool), mapa_id=3)
masc = np.zeros((11, 21), bool)
masc[2:9, 3:18] = True                                       # cratera de 15 x 7 px centrada
t3.cavar_mascara(50, 50, masc)
assert t3.vazio(50, 50) and t3.vazio(43, 47) and not t3.vazio(41, 50) and not t3.vazio(50, 55)
t3.cavar_mascara(2, 2, masc)                                  # na borda do mapa: corta sem erro
assert t3.vazio(0, 0)
print("buraco com a imagem da cratera (centrada na explosao, cortada na borda) OK")
m4 = ME.MiraExata(log=lambda *_: None)
assert m4.limite(False, 76, (645, 786), -1, 63) == 13, "ponteiro min 76 olhando para a esquerda num morro de 63 -> arma min 13"
assert m4.faixa((100, 100), +1, 0)[0] == 20 and m4.faixa((100, 100), +1, -20)[0] == 33, "arma min 13 + inclinacao 20 (direita)"
print("faixa da arma pela inclinacao (min 13 -> ponteiro 76 num morro de 63) OK")

# 3) resultado do servidor
tiro = dict(atirador=0, vento=0.5, bombas=[dict(acoes=[dict(tempo=2400, tipo="CHANGE_SPEED", p=(1, 2, 0, 0)), dict(tempo=2600, tipo="BOMB", p=(1120, 470, 1, 0)),
                                                     dict(tempo=2600, tipo="KILL_PLAYER", p=(1, 32650, 1, 37495))])],
            alvos=[dict(vivo=1, dano=972, vida=1000, furia=0)])
r = ME.resultado_do_tiro(tiro, 1)
assert r["acertou"] and r["dano"] == 32650 and r["dano_pet"] == 972 and r["explodiu"] == (1120, 470) and r["teleguiado"]
assert not ME.resultado_do_tiro(tiro, 5)["acertou"]
so_pet = dict(atirador=0, vento=0.5, bombas=[dict(acoes=[dict(tempo=2600, tipo="BOMB", p=(1263, 807, 1, 0))])], alvos=[dict(vivo=1, dano=4335, vida=1, furia=0)])
assert not ME.resultado_do_tiro(so_pet, 1)["acertou"], "dano so do pet nao e acerto do tiro"
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
        self.d = dict(eu=None, vez=0, vez_t=time.time(), turno=3, vento=0.5, chave_ok={"servidor": True, "cliente": True}, mapa=None,
                      buracos=[], direcao={},
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
at.taxa_rede = w.taxa                                   # a carga pelo tempo usa a taxa calibrada (no jogo real, pela rede)
at.pasta_barra = None
while w.t < 16.0 and not w.tiros:
    at.passo()
    w.avancar(0.1)
esperado = ME.MiraExata(log=lambda *_: None).planejar((499, 489), (1126, 483), 0.5)
assert any("[rede]" in l and "mira" in l for l in logs), logs
assert w.tiros and abs(w.angulo - esperado["mira"]) <= 2.5, (w.angulo, esperado["mira"], logs)
assert abs(w.tiros[0] - esperado["forca_pct"]) <= 8, (w.tiros, esperado["forca_pct"])
assert any("rede+fisica exata" in l for l in logs)
parada = [(i * 0.05, 88) for i in range(30)]
viva = [(0.0, 88), (0.05, 3), (0.15, 6), (0.3, 11), (0.5, 18), (0.7, 25), (0.9, 32)]
assert not P.AtiradorPvp._barra_viva(parada), "barra parada no tiro anterior nao manda soltar"
assert P.AtiradorPvp._barra_viva(viva) and not P.AtiradorPvp._barra_viva(viva[:3])
assert not P.AtiradorPvp._barra_viva([(0.0, 5), (0.1, 90), (0.2, 90), (0.3, 91), (0.4, 91)]), "pulo impossivel (5 -> 90 em 0,1 s)"
print("barra 'viva' (vista baixa e subindo) x parada no tiro anterior OK")
print(f"bot do PVP com a rede: mira {esperado['mira']} / forca {esperado['forca_pct']:.0f}% do plano exato aplicados OK")
print("\nmira_exata OK")
