# -*- coding: utf-8 -*-
"""
Leituras da tela de BATALHA. Todas recebem o quadro BGR ja normalizado para 1280 de largura
(navegador.em_1280) e devolvem numeros. Calibradas nas gravacoes do usuario (ver NOTAS.md).
"""
import os

import cv2
import numpy as np

import config

# ---- onde ficam as coisas (pixels de uma imagem com 1280 de largura) -------------------
PASS_POS = (626, 265)          # canto do recorte do botao "PASS" (so aparece na SUA vez)
PASS_LIMIAR = 0.65             # na vez: >= 0.79; fora dela: < 0.25
MOSTRADOR_PIVO = (345.2, 526.0)  # pivo do ponteiro do angulo
BARRA_FORCA = (414, 745, 544, 556)   # x0, x1, y0, y1 da barra de forca
MINIMAPA = (872, 976, 172, 244)      # x0, x1, y0, y1
VIDA_BOSS = (725, 812, 185, 191)     # barra de vida do boss (topo): cheia termina em ~811, comeca em ~725
ITENS_X = (951, 975)
ITENS_Y0, ITENS_PASSO, ITENS_ALTURA = 247, 25.7, 22
SATURACAO_ITEM_ATIVO = 75      # colorido ~87-127, cinza ~23-63

_TPL_PASS = []


def minha_vez(f):
    """True se o botao PASS esta visivel (= e a vez do jogador)."""
    if not _TPL_PASS:
        _TPL_PASS.append(cv2.imread(os.path.join(config.PASTA_TEMPLATES, "pass.png"), cv2.IMREAD_GRAYSCALE))
    t = _TPL_PASS[0]
    th, tw = t.shape
    g = cv2.GaussianBlur(cv2.cvtColor(f, cv2.COLOR_BGR2GRAY), (3, 3), 0)
    x, y = PASS_POS
    roi = g[y - 6:y + th + 6, x - 8:x + tw + 8]
    return float(cv2.matchTemplate(roi, t, cv2.TM_CCOEFF_NORMED).max()) >= PASS_LIMIAR


def angulo(f, pivo=MOSTRADOR_PIVO, rmin=10, rmax=28, faixa=(8, 90), passo=0.5):
    """Angulo de mira em graus, pela direcao do ponteiro (linha vermelha/laranja saindo do pivo).
    Erro medio ~2 graus (o ponteiro laranja tende a ler ~3 graus abaixo do vermelho)."""
    fi = f.astype(np.float32)
    cor = fi[..., 2] - fi[..., 0]                    # R - B
    rs = np.arange(rmin, rmax + 1, 1.0)
    angs = np.arange(faixa[0], faixa[1] + passo, passo)
    notas = np.empty(len(angs))
    for k, a in enumerate(angs):
        t = np.radians(a)
        v = []
        for dy in (-0.7, 0.0, 0.7):                  # tolerancia de 1 px perpendicular
            xs = np.round(pivo[0] + rs * np.cos(t) - dy * np.sin(t)).astype(int)
            ys = np.round(pivo[1] - rs * np.sin(t) - dy * np.cos(t)).astype(int)
            v.append(cor[ys, xs])
        notas[k] = np.percentile(np.max(v, axis=0), 20)
    return float(angs[int(notas.argmax())])


def forca(f):
    """Enchimento da barra de forca, 0-100."""
    x0, x1, y0, y1 = BARRA_FORCA
    faixa = f[y0:y1, x0:x1].astype(int)
    b, g, r = faixa[..., 0], faixa[..., 1], faixa[..., 2]
    col = ((r > 170) & (g > 90) & (b < 140) & (r - b > 70)).mean(axis=0) > 0.5
    xs = np.where(col)[0]
    return 0.0 if len(xs) == 0 else (xs.max() + 1) / (x1 - x0) * 100


def pontos_minimapa(f):
    """((x, y) do jogador - ponto azul, (x, y) do boss - ponto vermelho); cada um None se nao achar.
    Coordenadas em pixels do minimapa (y cresce para baixo)."""
    x0, x1, y0, y1 = MINIMAPA
    m = f[y0:y1, x0:x1].astype(int)
    b, g, r = m[..., 0], m[..., 1], m[..., 2]
    azul = (b > 170) & (r < 100) & (g < 150) & (b - r > 90)
    verm = (r > 190) & (g < 90) & (b < 90)

    def centro(mk):
        n, _, st, ce = cv2.connectedComponentsWithStats(mk.astype(np.uint8))
        if n < 2:
            return None
        i = 1 + int(np.argmax(st[1:, 4]))
        return (float(ce[i][0]), float(ce[i][1]))

    return centro(azul), centro(verm)


def itens_ativos(f):
    """Lista de 8 booleanos: o item 1..8 esta colorido (ha stamina para ele)? So vale na sua vez,
    com a coluna de itens visivel."""
    hsv = cv2.cvtColor(f, cv2.COLOR_BGR2HSV)
    x0, x1 = ITENS_X
    out = []
    for k in range(8):
        ya = int(ITENS_Y0 + k * ITENS_PASSO)
        out.append(float(hsv[ya:ya + ITENS_ALTURA, x0:x1, 1].mean()) > SATURACAO_ITEM_ATIVO)
    return out


def vida_boss(f):
    """Vida do boss em % (0-100): ate onde vai a barra vermelha. Calibrada com 100% -> fim em x=811 e
    42% -> fim em x=761; para decidir se um tiro acertou o que vale e a DIFERENCA entre antes e depois."""
    x0, x1, y0, y1 = VIDA_BOSS
    faixa = f[y0:y1, x0:x1].astype(int)
    b, g, r = faixa[..., 0], faixa[..., 1], faixa[..., 2]
    verm = ((r > 160) & (r - np.maximum(g, b) > 70)).mean(axis=0) > 0.5
    xs = np.where(verm)[0]
    if len(xs) == 0:
        return 0.0
    return float(min(100.0, max(0.0, (xs.max() + 1) / (x1 - x0) * 100)))
