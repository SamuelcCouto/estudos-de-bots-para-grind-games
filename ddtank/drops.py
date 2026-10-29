# -*- coding: utf-8 -*-
"""
Reconhece o que veio nas CARTAS (o item de cada carta que o bot virou) comparando o icone com um catalogo.

  templates/drops/<nome>.png   itens conhecidos (o nome do arquivo e o nome do item: "abobora.png")
  dados/drops_vistos/item_NNN.png  itens novos que o bot encontrou (ele guarda o icone e conta como "item_NNN")
  dados/drops_nomes.json       {"item_003": "Abobora", ...}: da nome a um item visto (o painel mostra o nome)
Para ensinar um item novo: copie o icone de dados/drops_vistos/ para templates/drops/ com o nome certo (ou preencha
drops_nomes.json). O icone fica no meio da carta virada (o nome escrito em cima nao entra na comparacao).
"""
import glob
import json
import os

import cv2
import numpy as np

import config

ICONE = (-18, -16, 18, 20)          # (dx0, dy0, dx1, dy1) em volta do centro da carta, em px do quadro de 1280
TAMANHO = 20                        # o icone vira TAMANHOxTAMANHO para comparar
LIMIAR = 0.88                       # correlacao minima para ser "o mesmo item"
PASTA_VISTOS = os.path.join(config.PASTA, "dados", "drops_vistos")
ARQ_NOMES = os.path.join(config.PASTA, "dados", "drops_nomes.json")
PASTA_CONHECIDOS = os.path.join(config.PASTA_TEMPLATES, "drops")


def assinatura(f, centro):
    """Vetor normalizado do icone da carta virada em `centro` (x, y) do quadro de 1280."""
    x, y = centro
    dx0, dy0, dx1, dy1 = ICONE
    icone = f[y + dy0:y + dy1, x + dx0:x + dx1]
    if icone.size == 0:
        return None
    return _vetor(icone)


def _vetor(icone):
    v = cv2.resize(icone, (TAMANHO, TAMANHO), interpolation=cv2.INTER_AREA).astype(np.float32).ravel()
    v -= v.mean()
    n = float(np.linalg.norm(v))
    return v / n if n > 1e-6 else None


class Catalogo:
    def __init__(self, pasta_conhecidos=PASTA_CONHECIDOS, pasta_vistos=PASTA_VISTOS, arq_nomes=ARQ_NOMES):
        self.pasta_vistos, self.arq_nomes = pasta_vistos, arq_nomes
        self.itens = {}                         # nome -> vetor
        for pasta in (pasta_conhecidos, pasta_vistos):
            for arq in sorted(glob.glob(os.path.join(pasta, "*.png"))):
                im = cv2.imread(arq)
                v = _vetor(im) if im is not None else None
                if v is not None:
                    self.itens[os.path.basename(arq)[:-4]] = v
        try:
            self.nomes = json.load(open(arq_nomes, encoding="utf-8"))
        except (OSError, ValueError):
            self.nomes = {}

    def nome_bonito(self, chave):
        return self.nomes.get(chave) or chave.replace("_", " ").capitalize()

    def reconhecer(self, f, centro):
        """Chave do item na carta (conhecido ou novo; um item novo e salvo e passa a ser reconhecido). None se nao der."""
        v = assinatura(f, centro)
        if v is None:
            return None
        melhor, nota = None, -1.0
        for k, ref in self.itens.items():
            c = float(v @ ref)
            if c > nota:
                melhor, nota = k, c
        if melhor is not None and nota >= LIMIAR:
            return melhor
        chave = f"item_{len(glob.glob(os.path.join(self.pasta_vistos, 'item_*.png'))) + 1:03d}"
        x, y = centro
        dx0, dy0, dx1, dy1 = ICONE
        try:
            os.makedirs(self.pasta_vistos, exist_ok=True)
            cv2.imwrite(os.path.join(self.pasta_vistos, chave + ".png"), f[y + dy0:y + dy1, x + dx0:x + dx1])
        except OSError:
            pass
        self.itens[chave] = v
        return chave
