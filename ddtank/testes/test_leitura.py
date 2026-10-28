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

# mira quase na horizontal (Profundezas, mostrador "1"): a leitura antiga so ia de 8 a 90 graus e devolvia lixo (90),
# o bot apertava "baixo" no limite e desistia do turno. Recortes do mostrador colados num quadro preto.
def so_mostrador(nome):
    f = np.zeros((720, 1280, 3), np.uint8)
    f[470:580, 290:420] = cv2.imread(os.path.join(AQUI, "frames", nome + ".png"))
    return f
for nome, gab in [("MOSTRADOR_1_VERMELHO", 1), ("MOSTRADOR_1_LARANJA", 1), ("MOSTRADOR_15", 15)]:
    a = L.angulo(so_mostrador(nome))
    print(f"mostrador {gab:2d} -> lido {a:.1f}")
    assert gab - 7 <= a <= gab + 1.5, (nome, a)   # o ponteiro le ~2-5 graus abaixo do numero

# boneco virado para a ESQUERDA: o ponteiro vai para o lado esquerdo do mostrador (o numero continua sendo o angulo
# a partir do chao do lado para onde ele olha). Gravacao do usuario: tocou "esquerda" na Profundezas.
for nome, gab, lado in [("MOSTRADOR_ESQ_48", 48, -1), ("MOSTRADOR_ESQ_61", 61, -1), ("MOSTRADOR_15", 15, 1), ("MOSTRADOR_1_VERMELHO", 1, 1)]:
    a, ld = L.mira(so_mostrador(nome))
    print(f"mostrador {gab:2d} -> lido {a:.1f}, virado para a {'direita' if ld > 0 else 'esquerda'}")
    assert ld == lado and gab - 7 <= a <= gab + 2, (nome, a, ld)

# vida do boss com a barra quase vazia: "1%" na barra (boss VIVO; a parte vermelha some) x boss morto (retrato cinza)
def so_vida(nome):
    f = np.zeros((720, 1280, 3), np.uint8)
    f[160:215, 650:850] = cv2.imread(os.path.join(AQUI, "frames", nome + ".png"))
    return f
v1, vm, v100, v34 = (L.vida_boss(so_vida(n)) for n in ("VIDA_1PORCENTO", "VIDA_MORTO", "VIDA_100", "VIDA_34"))
print(f"vida: barra '1%' -> {v1:.0f}, morto -> {vm:.0f}, cheia -> {v100:.0f}, '34%' -> {v34:.0f}")
assert v1 >= 1 and vm == 0 and v100 > 95 and 28 <= v34 <= 45, (v1, vm, v100, v34)
assert not L.boss_morto(so_vida("VIDA_1PORCENTO")) and L.boss_morto(so_vida("VIDA_MORTO"))

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

# minimapa: jogador = ponto azul pequeno; a AGUA da Profundezas (mancha azul-clara grande a esquerda, ~(12,34)) NAO e o
# jogador - o leitor antigo pegava "a maior mancha azul" e confundia (forca toda errada)
az, vm = L.pontos_minimapa(img("TIRO_75"))
print("minimapa (Profundezas):", az, vm)
perto = lambda p, q, tol=1.5: p is not None and abs(p[0] - q[0]) <= tol and abs(p[1] - q[1]) <= tol
assert perto(az, (27, 47)) and perto(vm, (65.4, 46.8)), (az, vm)


def so_minimapa(nome):
    """quadro preto 1280 com o recorte do minimapa (testes/frames/MINI_*.png) no lugar certo"""
    f = np.zeros((720, 1280, 3), np.uint8)
    x0, x1, y0, y1 = L.MINIMAPA
    f[y0:y1, x0:x1] = cv2.imread(os.path.join(AQUI, "frames", f"MINI_{nome}.png"))
    return f


GAB_MINI = {   # (jogador, boss) conferidos a olho
    "FANTASMA": ((32, 57.2), (90.5, 56.5)),
    "PROFUNDEZAS_AGUA": ((27, 47), (65.4, 46.8)),
    "MINHOCAO": ((37.8, 67.5), (73.1, 64.9)),
    "MOLDURA_VERMELHA": ((5.6, 66.2), (73.1, 64.9)),     # a moldura do minimapa fica vermelha: nao e o boss
    "EFEITO_AZUL": ((14, 56.7), None),                   # efeito azul enorme cobrindo o minimapa: ignorado
}
for nome, (gj, gb) in GAB_MINI.items():
    j, b = L.pontos_minimapa(so_minimapa(nome))
    print(f"minimapa {nome}: jogador {j and tuple(round(v, 1) for v in j)}, boss {b and tuple(round(v, 1) for v in b)}")
    assert perto(j, gj), (nome, j, gj)
    assert (b is None) if gb is None else perto(b, gb), (nome, b, gb)

# rastreador: um quadro sozinho pode pegar a setinha acima do boneco (ou um efeito); a posicao que mais se repete vence
j1, _ = L.pontos_minimapa(so_minimapa("PROFUNDEZAS_SETA"))
print("quadro isolado com a seta:", j1)
r = L.RastreadorMinimapa()
for nome in ["PROFUNDEZAS_AGUA"] * 6 + ["PROFUNDEZAS_SETA"] * 2:
    r.observar(*L.candidatos_minimapa(so_minimapa(nome)))
j, conf = r.jogador()
print(f"rastreado: {j}, confianca {conf:.2f}, boss {r.boss}")
assert perto(j, (27, 47)) and conf > 0.5, (j, conf)
# leituras falsas passageiras (ex.: algo azul em (71,23)) nao vencem a posicao estavel
r = L.RastreadorMinimapa()
for k in range(12):
    r.observar([(32.0, 57.0, 9)] + ([(71.0, 23.0, 20)] if k in (9, 10) else []), [(90.0, 56.0, 12)])
assert perto(r.jogador()[0], (32, 57)), r.jogador()
# se o boneco for empurrado, a posicao nova assume em poucas leituras
for k in range(6):
    r.observar([(40.0, 57.0, 9)], [(90.0, 56.0, 12)])
assert perto(r.jogador()[0], (40, 57)), r.jogador()
r.reiniciar()
assert r.jogador() == (None, 0.0) and r.boss is None
print("rastreador OK")

# Chefao Global: a barra de vida e a do servidor (nao diz se o SEU tiro pegou) -> numeros de dano em cima do boss.
# Recortes da gravacao do usuario (20261028_121648): o acerto mais fraco dos 40 tiros normais deu 908 px; fora dos
# tiros (turno do boss, efeitos) o maximo foi 702.
def colar(nome, x0, y0):
    f = np.zeros((720, 1280, 3), np.uint8)
    c = cv2.imread(os.path.join(AQUI, "frames", nome + ".png"))
    f[y0:y0 + c.shape[0], x0:x0 + c.shape[1]] = c
    return f
for nome, acerto in [("DANO_ACERTO_4828", True), ("DANO_ACERTO_1076", True), ("DANO_ACERTO_908", True),
                     ("DANO_NADA_BOSS", False), ("DANO_NADA", False)]:
    n = L.numeros_de_dano(colar(nome, 780, 310))
    print(f"numeros de dano {nome}: {n} px")
    assert (n >= L.NUMEROS_DANO_ACERTO) == acerto, (nome, n)
# POW (especial, tecla B): cheio = botao vermelho pulsando (inclusive no pulso mais fraco)
for nome, cheio in [("POW_CHEIO", True), ("POW_CHEIO_FRACO", True), ("POW_VAZIO", False), ("POW_USADO", False)]:
    assert L.pow_cheio(colar(nome, 915, 495)) == cheio, nome
assert not any(L.pow_cheio(img(f"VEZ_SIM_{i}")) for i in (21, 74, 214, 415, 602)), "instancias normais: POW vazio"
f = img("BATALHA_PERICAO")                      # 1o turno do usuario no Pericao (antes dos itens)
j, b = L.pontos_minimapa(f)
assert perto(j, (10.5, 58.4)) and perto(b, (76.3, 61.4)) and L.minha_vez(f), (j, b)
assert L.mira(f) == (4.5, 1) and 40 <= L.vida_boss(f) <= 46, (L.mira(f), L.vida_boss(f))   # vida do servidor: 43%
print("chefao global (numeros de dano, POW) OK")
print("\nleituras OK")
