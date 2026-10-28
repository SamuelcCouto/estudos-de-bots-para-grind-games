# -*- coding: utf-8 -*-
"""
Leitura dos recursos do topo da tela (ouro, madeira, bife, pedra) e estatisticas.

A leitura compara cada digito com amostras recortadas do proprio jogo
(templates/digitos/<digito>_<n>.png); o HUD e localizado pelo icone do ouro.
"""
import collections
import glob
import os
import time

import cv2
import numpy as np

PASTA_TPL = os.path.join(os.path.dirname(os.path.abspath(__file__)), "templates")
NOMES = ("ouro", "madeira", "bife", "pedra")
# caixa de cada numero em relacao ao canto do icone do ouro: (x0, y0, x1, y1)
CAIXAS = {"ouro": (45, 2, 140, 26), "madeira": (195, 2, 295, 26),
          "bife": (45, 43, 140, 67), "pedra": (195, 43, 295, 67)}


def _escurecimento(s):
    """Quanto cada pixel e mais escuro que o fundo da propria linha (tira o degrade da caixa)."""
    s = s.astype(np.float32)
    return np.clip(np.percentile(s, 90, axis=1, keepdims=True) - s, 0, 255)


_AMOSTRAS = []
_ICONE = None


def _carregar():
    global _ICONE
    if _ICONE is None:
        _ICONE = cv2.imread(os.path.join(PASTA_TPL, "hud_ouro.png"), cv2.IMREAD_GRAYSCALE)
        for f in glob.glob(os.path.join(PASTA_TPL, "digitos", "*.png")):
            t = cv2.imread(f, cv2.IMREAD_GRAYSCALE)
            if t is not None and t.shape == (16, 11):
                _AMOSTRAS.append((os.path.basename(f)[0], _escurecimento(t)))


def ler_recursos(img):
    """Retorna {'ouro': int, 'madeira': int, 'bife': int, 'pedra': int} ou None."""
    _carregar()
    g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    r = cv2.matchTemplate(g[0:220], _ICONE, cv2.TM_CCOEFF_NORMED)
    _, mx, _, (ix, iy) = cv2.minMaxLoc(r)
    if mx < 0.7:
        return None
    valores = {}
    for nome, (a, b, c, d) in CAIXAS.items():
        faixa = _escurecimento(g[iy + b:iy + d, ix + a:ix + c])
        largura = faixa.shape[1] - 10
        if largura <= 0:
            return None
        melhor = np.full(largura, -1.0)
        rotulo = np.full(largura, "?")
        for digito, amostra in _AMOSTRAS:
            res = cv2.matchTemplate(faixa, amostra, cv2.TM_CCOEFF_NORMED).max(axis=0)
            m = res > melhor
            melhor[m] = res[m]
            rotulo[m] = digito
        posicoes = []
        for x in np.argsort(-melhor):
            if melhor[x] < 0.75:
                break
            if all(abs(x - p) >= 6 for p in posicoes):
                posicoes.append(x)
        texto = "".join(rotulo[x] for x in sorted(posicoes))
        if not texto:
            return None
        valores[nome] = int(texto)
    return valores


class Estatisticas:
    """Acompanha os recursos: inicio, atual, quanto entrou (colhido) e quanto saiu (gasto).

    Entre duas leituras, aumento conta como colhido e queda como gasto (ex.: os campos
    gastam madeira). Leituras absurdas (erro de leitura) sao descartadas."""

    def __init__(self):
        self.inicio = None
        self.atual = None
        self.colhido = dict.fromkeys(NOMES, 0)
        self.gasto = dict.fromkeys(NOMES, 0)
        self.hora_inicio = time.time()
        self.eventos = collections.deque()  # (tempo, nome, +ganho)
        self.colheitas = 0
        self.replantios = 0
        self._suspeita = None
        self._confirmacoes = 0

    def atualizar(self, valores):
        if not valores:
            return
        if self.atual is not None:
            salto = any(abs(valores[n] - self.atual[n]) > max(20000, self.atual[n] * 0.3)
                        for n in NOMES)
            if salto:
                # pode ser erro de leitura ou um gasto real (ex.: upgrade). Se as proximas
                # leituras confirmarem o mesmo valor, aceita
                p = self._suspeita
                if p and all(abs(valores[n] - p[n]) <= max(2000, p[n] * 0.02) for n in NOMES):
                    self._confirmacoes += 1
                else:
                    self._suspeita, self._confirmacoes = dict(valores), 0
                if self._confirmacoes < 2:
                    return
            self._suspeita = None
        if self.inicio is None:
            self.inicio = dict(valores)
            self.hora_inicio = time.time()
        else:
            agora_t = time.time()
            for n in NOMES:
                delta = valores[n] - self.atual[n]
                if delta > 0:
                    self.colhido[n] += delta
                    self.eventos.append((agora_t, n, delta))
                elif delta < 0:
                    self.gasto[n] -= delta
        self.atual = dict(valores)

    def por_minuto(self, janela=600):
        """Colhido por minuto na janela recente (padrao: ultimos 10 min)."""
        agora = time.time()
        while self.eventos and agora - self.eventos[0][0] > janela:
            self.eventos.popleft()
        minutos = max(1 / 60, min(janela, agora - self.hora_inicio) / 60)
        soma = dict.fromkeys(NOMES, 0)
        for _, n, d in self.eventos:
            soma[n] += d
        return {n: soma[n] / minutos for n in NOMES}

    def tempo_ligado(self):
        s = int(time.time() - self.hora_inicio)
        return f"{s // 3600}h{s % 3600 // 60:02d}m{s % 60:02d}s"
