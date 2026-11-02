# -*- coding: utf-8 -*-
"""Fisica exata do tiro (fisica_exata.py) contra as tabelas oficiais de distancia x forca do Betel (as "EstAng" ao lado do jogo).
Rode: python testes/test_fisica_exata.py"""
import os
import sys

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(AQUI))
import fisica_exata as FX

# tabelas do site (distancia na regua 1..20 -> forca %), copiadas da tela do jogo (01/11)
TABELAS = {
    20: [10, 19, 25, 30, 36, 40, 44, 48, 51, 54, 57, 60, 63, 66, 69, 72, 74, 76, 78, 80],
    30: [14, 20, 24, 28, 32, 35, 38, 41, 44, 47, 50, 52, 55, 57, 60, 62, 65, 67, 69, 72],
    50: [14, 20, 24, 28, 32, 35, 39, 42, 44, 48, 50, 53, 55, 58, 60, 62, 65, 68, 70, 72],
    65: [13, 20, 26, 31, 37, 41, 44, 48, 53, 56, 58, 61, 64, 67, 70, 73, 76, 79, 82, 85],
}

# 1) a regua: as tabelas (arredondadas pelos jogadores) dao ~100 px de mapa por unidade. O tiro sai do CANO, ~35 px acima do chao
#    do alvo (com essa altura as 4 tabelas ficam coerentes: media 96 px/unid, desvio 4; sem ela, 20 graus dava 55-96)
ALTURA_CANO = 35
for ang, forcas in TABELAS.items():
    for d, pct in enumerate(forcas, start=1):
        if d < 4:
            continue                                   # distancias curtas: o arredondamento da tabela domina
        px = FX.x_na_altura(0, 0, FX.forca_unidades(pct), FX.angulo_envio(ang, +1), ALTURA_CANO)
        tol = 0.14 if d < 6 else 0.09                  # medido: d>=6 fica entre 91 e 101 px/unid nas 4 tabelas (50 graus: 96-101)
        assert abs(px / d - FX.PX_POR_UNIDADE) <= FX.PX_POR_UNIDADE * tol, (ang, d, pct, round(px / d, 1))
print("tabelas EstAng (20/30/50/65 graus) batem com a fisica exata: ~100 px do mapa por unidade da regua OK")

# 2) o solver devolve a forca da tabela (50 graus, distancias 5-20) com erro de no maximo 2 pontos
for d in range(5, 21):
    f = FX.forca_para_alvo(0, 0, d * 100.0, ALTURA_CANO, FX.angulo_envio(50, +1))
    assert f is not None and abs(f / 20 - TABELAS[50][d - 1]) <= 2, (d, f / 20, TABELAS[50][d - 1])
print("solver: forca para a distancia (50 graus) = tabela +-2 pontos OK")

# 3) vento a favor leva mais longe; virado para a esquerda e simetrico
a = FX.alcance_plano(50, 50, vento=0)
assert FX.alcance_plano(50, 50, vento=+2.0) > a > FX.alcance_plano(50, 50, vento=-2.0)
xe = FX.x_na_altura(0, 0, FX.forca_unidades(50), FX.angulo_envio(50, -1), 0)
assert abs(xe + a) < 2, (xe, a)
print("vento (a favor/contra) e simetria esquerda/direita OK")

# 4) colisao: alvo no caminho e terreno
tiro = FX.forca_para_alvo(0, 0, 800, 0, FX.angulo_envio(50, +1))
r = FX.simular(0, 0, tiro, FX.angulo_envio(50, +1), alvos=[(780, -30, 820, 0)])
assert r["motivo"] == "alvo" and r["alvo"] == 0, r["motivo"]
r = FX.simular(0, 0, tiro, FX.angulo_envio(50, +1), terreno=lambda x0, y0, x1, y1: 300 <= x1 and x0 <= 320)   # parede em x=300-320
assert r["motivo"] == "chao" and 290 <= r["impacto"][0] <= 320, r["impacto"]
print("colisao com boneco e com terreno OK")

# 5) perk teleguiado: um tiro que passaria ALEM do alvo e corrigido (desce a <150 px dele) e acerta
f_longe = FX.forca_para_alvo(0, 0, 920, 0, FX.angulo_envio(50, +1))
sem = FX.simular(0, 0, f_longe, FX.angulo_envio(50, +1), alvos=[(785, -40, 815, 0)])
com = FX.simular(0, 0, f_longe, FX.angulo_envio(50, +1), alvos=[(785, -40, 815, 0)], teleguiado=True, inimigos=[(800, -20)])
assert sem["motivo"] != "alvo" and com["motivo"] == "alvo" and com["corrigiu"], (sem["motivo"], com["motivo"])
print("perk teleguiado (raio 150 px, so descendo) OK")

# 6) "de costas": virado para a direita com |angulo| >= 91 (terreno inclinado: mira 85 + inclinacao -8 = -93)
assert FX.de_costas(+1, FX.angulo_envio(85, +1, inclinacao=-8)) and not FX.de_costas(+1, FX.angulo_envio(85, +1))
assert FX.de_costas(-1, -80) and not FX.de_costas(-1, -100)
print("regra do tiro de costas OK")
print("\nfisica_exata OK")
