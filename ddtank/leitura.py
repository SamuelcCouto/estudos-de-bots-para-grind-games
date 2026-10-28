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
MINIMAPA_Y_CONTEUDO = 14             # px do minimapa: acima disso ficam o cabecalho (facil/normal, 2/200, botoes) e a moldura
MINIMAPA_Y_MAX = 69.5                # abaixo: moldura de baixo
MINIMAPA_X_LIM = (3.5, 101.5)        # fora: molduras dos lados
MINIMAPA_PONTO_MAX = 7               # px: o nucleo de um ponto (jogador/boss) cabe num quadrado 7x7
_CRUZ = cv2.getStructuringElement(cv2.MORPH_CROSS, (3, 3))
LEITURAS_MUDOU = 5                  # leituras seguidas sem o ponto antigo (e com um novo) = o boneco mudou de lugar
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


def _pontos_redondos(mk):
    """[(x, y, tamanho)] dos pontos compactos da mascara, maiores primeiro. A erosao em cruz apaga o que tem ate 2 px de
    largura (moldura do minimapa, que fica verde/azul/vermelha conforme a instancia; rastro da cachoeira) e manchas
    grandes (agua, efeitos de tela) ficam de fora pelo tamanho. Fora tambem: cabecalho e as bordas."""
    nucleo = cv2.erode(mk.astype(np.uint8), _CRUZ)
    n, _, st, ce = cv2.connectedComponentsWithStats(nucleo)
    out = []
    for i in range(1, n):
        _x, _y, w, h, a = st[i]
        cx, cy = float(ce[i][0]), float(ce[i][1])
        if w > MINIMAPA_PONTO_MAX or h > MINIMAPA_PONTO_MAX or a < 2:
            continue
        if cy < MINIMAPA_Y_CONTEUDO or cy > MINIMAPA_Y_MAX or not (MINIMAPA_X_LIM[0] <= cx <= MINIMAPA_X_LIM[1]):
            continue
        out.append((cx, cy, int(a)))
    return sorted(out, key=lambda c: -c[2])


def candidatos_minimapa(f):
    """(pontos azuis, pontos vermelhos) do minimapa: listas [(x, y, tamanho)], maiores primeiro.
    Coordenadas em pixels do minimapa (y cresce para baixo).
    Cores (HSV do OpenCV, medidas nas 3 instancias): ponto do jogador H 111-116, S > 200 (a agua da Profundezas e
    H 101-104: fica de fora); faixa azul-escura do chao do Minhocao tem V < 120; boss H 0-6 ou >= 172."""
    x0, x1, y0, y1 = MINIMAPA
    hsv = cv2.cvtColor(f[y0:y1, x0:x1], cv2.COLOR_BGR2HSV).astype(int)
    h, s, v = hsv[..., 0], hsv[..., 1], hsv[..., 2]
    azul = (h >= 107) & (h <= 124) & (s > 170) & (v > 120)
    verm = ((h <= 6) | (h >= 172)) & (s > 170) & (v > 150)
    return _pontos_redondos(azul), _pontos_redondos(verm)


def pontos_minimapa(f):
    """((x, y) do jogador - ponto azul, (x, y) do boss - ponto vermelho); cada um None se nao achar.
    So um quadro: na batalha use RastreadorMinimapa, que filtra leituras passageiras."""
    az, vm = candidatos_minimapa(f)
    return (az[0][:2] if az else None), (vm[0][:2] if vm else None)


class RastreadorMinimapa:
    """Acompanha o minimapa durante a batalha.
    Jogador: o bot nunca anda, entao a posicao certa e a que MAIS SE REPETE nas leituras (um ponto azul passageiro -
    efeito, tiro, animacao - nao engana, mesmo que esconda o boneco por um instante). Se o boneco for empurrado, a
    posicao nova assume depois de LEITURAS_MUDOU leituras (~2 s).
    Boss: anda; vale a leitura mais recente (ou a ultima conhecida, se o ponto sumiu por um instante)."""
    def __init__(self, janela=30, raio=2.5):
        self.janela, self.raio = janela, raio
        self.azuis = []          # uma lista de candidatos (x, y) por leitura, mais antiga primeiro
        self.boss = None

    def reiniciar(self):
        self.azuis, self.boss = [], None

    def observar(self, azuis, vermelhos):
        """azuis/vermelhos: listas de (x, y[, tamanho]) de UM quadro."""
        self.azuis.append([tuple(c[:2]) for c in azuis[:4]])
        del self.azuis[:-self.janela]
        if vermelhos:
            self.boss = tuple(vermelhos[0][:2])

    def _mais_frequente(self, leituras):
        """(ponto, em quantas das leituras ele aparece) - empate: o visto primeiro."""
        melhor, n_m = None, 0
        for leit in leituras:
            for p in leit:
                n = sum(1 for l2 in leituras if any(self._perto(p, q) for q in l2))
                if n > n_m:
                    melhor, n_m = p, n
        return melhor, n_m

    def _perto(self, p, q):
        return abs(p[0] - q[0]) + abs(p[1] - q[1]) <= self.raio

    def jogador(self):
        """((x, y) ou None, confianca 0..1 = fracao das leituras da janela em que o ponto apareceu).
        Vale o ponto que aparece em MAIS leituras; so troca de lugar se o ponto antigo sumir por LEITURAS_MUDOU leituras
        seguidas e outro aparecer em quase todas elas (boneco empurrado)."""
        if not self.azuis:
            return None, 0.0
        melhor, n_m = self._mais_frequente(self.azuis)
        recentes = self.azuis[-LEITURAS_MUDOU:]
        if melhor is not None and len(recentes) == LEITURAS_MUDOU and not any(self._perto(melhor, q) for l2 in recentes for q in l2):
            novo, n_novo = self._mais_frequente(recentes)
            if novo is not None and n_novo >= LEITURAS_MUDOU - 1:
                melhor = novo
                n_m = sum(1 for l2 in self.azuis if any(self._perto(novo, q) for q in l2))
        if melhor is None:
            return None, 0.0
        # posicao refinada: media dos pontos do grupo nas ultimas leituras
        grupo = [q for l2 in self.azuis[-5:] for q in l2 if self._perto(melhor, q)]
        if grupo:
            melhor = (float(np.mean([q[0] for q in grupo])), float(np.mean([q[1] for q in grupo])))
        return melhor, n_m / len(self.azuis)


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
