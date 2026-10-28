# -*- coding: utf-8 -*-
"""
Deteccao da area util do jogo dentro da janela (viewport).

O admin do jogo as vezes abre um chat (ou outro painel) na lateral, o que estreita a area
do jogo e desloca o centro da base. Um painel lateral aparece como uma borda vertical
longa (de ponta a ponta da altura) numa das laterais da janela; o mapa do jogo nao tem
bordas assim. Retorna (x0, y0, x1, y1): so essa regiao e "jogo" - o resto e ignorado.

Uso de teste (sem o jogo): python layout.py captura.png  -> imprime o viewport e salva
captura_layout.png com a area do jogo marcada.
"""
import sys

import cv2
import numpy as np

MAX_PAINEL = 0.45    # um painel lateral ocupa no maximo essa fracao da largura
MIN_PAINEL = 100     # px: mais estreito que isso nao e painel (e borda/scrollbar)
SALTO_MINIMO = 14    # diferenca de brilho (em 3 px) que conta como "degrau"
FRACAO_BORDA = 0.85  # fracao das linhas com degrau para a coluna ser uma borda de painel


def _perfil_de_borda(g):
    """Para cada coluna c, a fracao de linhas com um degrau de brilho entre c e c+3."""
    miolo = g[int(len(g) * 0.08):int(len(g) * 0.92)]
    degrau = np.abs(miolo[:, 3:] - miolo[:, :-3]) >= SALTO_MINIMO
    return degrau.mean(axis=0)


def _grupos(colunas):
    """Agrupa colunas vizinhas (uma borda de 2-3 px dispara varias colunas seguidas)."""
    grupos, atual = [], []
    for c in colunas:
        if atual and c - atual[-1] > 3:
            grupos.append((atual[0], atual[-1]))
            atual = []
        atual.append(int(c))
    if atual:
        grupos.append((atual[0], atual[-1]))
    return grupos


def detectar_viewport(img, esquerda=True, direita=True):
    """Retorna (x0, y0, x1, y1) da area do jogo; a janela inteira se nao houver painel."""
    h, w = img.shape[:2]
    g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY).astype(np.int16)
    perfil = _perfil_de_borda(g)
    # perfil[c] cobre a transicao entre as colunas c e c+3 -> a borda fica em ~c+1..c+3
    fortes = np.where(perfil >= FRACAO_BORDA)[0]
    x0, x1 = 0, w
    limite = int(w * MAX_PAINEL)
    if direita:
        # o painel e a borda MAIS AFASTADA da lateral (descarta scrollbars dentro do chat)
        cand = [a for a, b in _grupos(fortes) if MIN_PAINEL <= w - a <= limite]
        if cand:
            x1 = min(cand)
    if esquerda:
        cand = [b + 3 for a, b in _grupos(fortes) if MIN_PAINEL <= b + 3 <= limite]
        if cand:
            x0 = max(cand)
    return x0, 0, x1, h


def mudou(a, b, tolerancia=12):
    """True se dois viewports diferem mais que `tolerancia` px em algum lado."""
    return a is None or b is None or any(abs(p - q) > tolerancia for p, q in zip(a, b))


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit("uso: python layout.py captura.png")
    imagem = cv2.imread(sys.argv[1])
    if imagem is None:
        sys.exit("nao consegui abrir a imagem")
    vp = detectar_viewport(imagem)
    print(f"viewport (x0, y0, x1, y1) = {vp}  | janela = {imagem.shape[1]}x{imagem.shape[0]}")
    marcada = imagem.copy()
    cv2.rectangle(marcada, (vp[0], vp[1] + 1), (vp[2] - 1, vp[3] - 2), (0, 0, 255), 3)
    saida = sys.argv[1].rsplit(".", 1)[0] + "_layout.png"
    cv2.imwrite(saida, marcada)
    print("salvo em", saida)
