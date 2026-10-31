# -*- coding: utf-8 -*-
"""
Leitor do VENTO do PVP (painel "Forca Vento", topo da batalha: seta + digitos "N.d").

O painel e uma seta lavanda (aponta para onde o vento sopra) com dois digitos coloridos. Entre uma rodada e outra aparece
um "0.0" fantasma (rosa, so contorno) - isso NAO e vento: devolve None. A leitura compara o recorte com amostras
rotuladas de partidas reais (templates/vento_amostras.npz, 330 recortes de 49 trechos de vento, gravacoes 20261031):
  1) direcao (+1 = sopra para a direita da tela, -1 = esquerda) e "fantasma": vizinho mais proximo do recorte inteiro;
  2) cada digito: vizinho mais proximo por gradientes (HOG) do digito; vale a cor e a forma.
Medido (deixando cada trecho de vento de fora do treino): direcao 99%, 1o digito 99%, 2o digito ~78% (6 e 8 se confundem),
vento inteiro ~77%. Por isso `ler_vento` devolve tambem a CONFIANCA e o PVP grava o recorte de cada leitura incerta
para a gente rotular mais amostras (e a leitura melhorar sozinha: ver `adicionar_amostra`).
"""
import os

import cv2
import numpy as np

import config

ARQ_AMOSTRAS = os.path.join(config.PASTA_RECURSOS, "templates", "vento_amostras.npz")
RECORTE = (600, 175, 700, 200)        # x0, y0, x1, y1 do painel (quadro de 1280 de largura)
CAIXA_DIGITO1 = (24, 41)              # faixa x do 1o digito dentro do recorte
CAIXA_DIGITO2 = (45, 66)
CONFIANCA_MINIMA = 1.08               # razao distancia(outro valor)/distancia(melhor): abaixo disso = duvida

_dados = {}


def recorte(f):
    x0, y0, x1, y1 = RECORTE
    return f[y0:y1, x0:x1]


def _gfeat(c):
    return cv2.resize(cv2.cvtColor(c, cv2.COLOR_BGR2GRAY), (50, 12)).astype(np.float32)


def _patch(c, a, b, w=12, h=16):
    """Recorte w x h em volta do maior componente 'tinta' (digito + contorno) da faixa x a..b. None se nao achou."""
    sub = c[1:20, a:b]
    hsv = cv2.cvtColor(sub, cv2.COLOR_BGR2HSV)
    m = (((hsv[..., 1] > 105) & (hsv[..., 2] > 70)) | (hsv[..., 2] < 100)).astype(np.uint8)
    n, _lb, st, cen = cv2.connectedComponentsWithStats(m, connectivity=8)
    if n < 2:
        return None
    i = 1 + int(np.argmax(st[1:, 4]))
    if st[i, 4] < 20:
        return None
    cx, cy = int(cen[i][0]), int(cen[i][1])
    pad = cv2.copyMakeBorder(sub, 10, 10, 10, 10, cv2.BORDER_REPLICATE)
    return pad[cy + 10 - h // 2:cy + 10 + h // 2, cx + 10 - w // 2:cx + 10 + w // 2]


def _hog(p):
    g = cv2.cvtColor(p, cv2.COLOR_BGR2GRAY)
    g = cv2.resize(g, (24, 32), interpolation=cv2.INTER_CUBIC).astype(np.float32)
    hsv = cv2.cvtColor(cv2.resize(p, (24, 32), interpolation=cv2.INTER_CUBIC), cv2.COLOR_BGR2HSV).astype(np.float32)
    tinta = np.maximum(hsv[..., 1] - 70, 0) + np.maximum(120 - hsv[..., 2], 0)
    out = []
    for ch in (g, tinta):
        gx = cv2.Sobel(ch, cv2.CV_32F, 1, 0, ksize=3)
        gy = cv2.Sobel(ch, cv2.CV_32F, 0, 1, ksize=3)
        mag = np.hypot(gx, gy)
        ang = (np.arctan2(gy, gx) % np.pi) / np.pi * 8
        for r in range(4):
            for c in range(3):
                mm = mag[r * 8:(r + 1) * 8, c * 8:(c + 1) * 8]
                aa = ang[r * 8:(r + 1) * 8, c * 8:(c + 1) * 8].astype(int) % 8
                out.extend(np.bincount(aa.ravel(), weights=mm.ravel(), minlength=8))
    v = np.array(out, np.float32)
    return v / (np.linalg.norm(v) + 1e-6)


def _alvo(v):
    a = abs(float(v))
    d1 = int(a + 1e-6)
    return d1, int(round((a - d1) * 10))


def _preparar(crops, valores, grupos):
    n = len(crops)
    d = {"crops": crops, "valores": valores, "grupos": grupos, "g": [_gfeat(c) for c in crops],
         "h1": [None] * n, "h2": [None] * n}
    for i, c in enumerate(crops):
        if np.isnan(valores[i]):
            continue
        p1, p2 = _patch(c, *CAIXA_DIGITO1), _patch(c, *CAIXA_DIGITO2)
        d["h1"][i] = None if p1 is None else _hog(p1)
        d["h2"][i] = None if p2 is None else _hog(p2)
    return d


def carregar(arq=None):
    arq = arq or ARQ_AMOSTRAS
    if arq not in _dados:
        z = np.load(arq)
        _dados[arq] = _preparar(z["crops"], z["valores"], z["grupos"])
    return _dados[arq]


def _classificar(c, d, excluir_grupo=None):
    """(valor, confianca) ou (None, 0) para o recorte `c` do painel."""
    n = len(d["crops"])
    ok = [i for i in range(n) if excluir_grupo is None or d["grupos"][i] != excluir_grupo]
    g = _gfeat(c)
    dist = {i: float(np.abs(g - d["g"][i]).mean()) for i in ok}
    melhor = min(dist, key=dist.get)
    if np.isnan(d["valores"][melhor]):
        return None, 1.0                                  # o "0.0" fantasma entre rodadas
    vizinhos = [i for i in ok if not np.isnan(d["valores"][i])]
    lado = 1 if d["valores"][min(vizinhos, key=dist.get)] >= 0 else -1
    p1, p2 = _patch(c, *CAIXA_DIGITO1), _patch(c, *CAIXA_DIGITO2)
    if p1 is None or p2 is None:
        return None, 0.0
    h = (_hog(p1), _hog(p2))
    digs, confs = [], []
    for pos, chave in ((0, "h1"), (1, "h2")):
        por_digito = {}
        for i in vizinhos:
            if d[chave][i] is None:
                continue
            e = float(np.linalg.norm(h[pos] - d[chave][i]))
            dig = _alvo(d["valores"][i])[pos]
            if dig not in por_digito or e < por_digito[dig]:
                por_digito[dig] = e
        ordem = sorted(por_digito.items(), key=lambda kv: kv[1])
        digs.append(ordem[0][0])
        confs.append(ordem[1][1] / max(ordem[0][1], 1e-6) if len(ordem) > 1 else 9.0)
    return lado * (digs[0] + digs[1] / 10.0), min(confs)


def ler_vento(f):
    """f: quadro de 1280 de largura. Devolve (vento, confianca) - vento com sinal (+ sopra para a direita da tela, - para a
    esquerda), 0.1 de resolucao - ou (None, 0.0) se nao ha painel de vento valido (fantasma entre rodadas, outra tela)."""
    return _classificar(recorte(f), carregar())


def confiavel(conf):
    return conf >= CONFIANCA_MINIMA


def avaliar_sem_o_proprio_trecho():
    """Deixa cada trecho de vento de fora do treino e mede o acerto. Devolve (acertos, total) do vento inteiro."""
    d = carregar()
    ok = tot = 0
    for i in range(len(d["crops"])):
        if np.isnan(d["valores"][i]):
            continue
        v, _c = _classificar(d["crops"][i], d, excluir_grupo=d["grupos"][i])
        tot += 1
        ok += v is not None and abs(v - float(d["valores"][i])) < 0.05
    return ok, tot


def adicionar_amostra(c, valor, arq=None):
    """Acrescenta um recorte rotulado (valor=None para o fantasma) ao arquivo de amostras: a leitura melhora com mais dados."""
    arq = arq or ARQ_AMOSTRAS
    z = np.load(arq)
    crops = np.concatenate([z["crops"], c[None]])
    valores = np.concatenate([z["valores"], [np.nan if valor is None else valor]]).astype(np.float32)
    grupos = np.concatenate([z["grupos"], [int(z["grupos"].max()) + 1]]).astype(np.int16)
    np.savez_compressed(arq, crops=crops, valores=valores, grupos=grupos)
    _dados.pop(arq, None)
