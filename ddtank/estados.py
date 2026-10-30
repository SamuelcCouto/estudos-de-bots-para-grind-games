# -*- coding: utf-8 -*-
"""
Reconhece em que tela do jogo estamos, comparando recortes fixos da tela com "assinaturas"
(templates/estados/*.png, listadas em templates/estados.json).

Tudo e feito numa imagem normalizada para 1280 de largura, o mesmo tamanho em que as
assinaturas foram extraidas das gravacoes. Cada tela tem 2 recortes e um limiar; a tela
conta como detectada quando os DOIS recortes passam do limiar.
"""
import json
import os

import cv2
import numpy as np

import config

LARGURA = 1280
TOLERANCIA = 8   # px de folga ao procurar o recorte perto da posicao esperada

# quando duas telas aparecem juntas (pop-up por cima de outra), vale a primeira da lista
PRIORIDADE = ["CLIQUE_JOGO", "POPUP_AVISO", "POPUP_CARTA", "POPUP_SOZINHO", "POPUP_SOZINHO2", "POPUP_SOZINHO3", "TAREFA", "CARTAS", "CARTAS_P", "CONFIG_SEL", "CONFIG_VAZIA",
              "CONFIG",          # janela de configuracao generica: vale quando a arte da instancia marcada e desconhecida
              "PRONTA_FANTASMA", "PRONTA_PROFUNDEZAS", "PRONTA_MINHOCAO", "SALA_VAZIA",
              "SALA",            # sala generica (painel da direita): vale quando a arte da instancia e desconhecida
              "CENTRAL", "MAPA", "BATALHA"]


def normalizar(img):
    """Imagem BGR da janela -> cinza suavizado, 1280 de largura (float32)."""
    h, w = img.shape[:2]
    if w != LARGURA:
        img = cv2.resize(img, (LARGURA, int(h * LARGURA / w)), interpolation=cv2.INTER_AREA)
    return cv2.GaussianBlur(cv2.cvtColor(img, cv2.COLOR_BGR2GRAY), (3, 3), 0).astype(np.float32)


class Detector:
    def __init__(self, pasta=None):
        pasta = pasta or config.PASTA_TEMPLATES
        cfg = json.load(open(os.path.join(pasta, "estados.json"), encoding="utf-8"))["estados"]
        self.estados = {}
        for nome, e in cfg.items():
            patches = []
            for p in e["patches"]:
                t = cv2.imread(os.path.join(pasta, "estados", p["arquivo"]), cv2.IMREAD_GRAYSCALE)
                patches.append((p["x"], p["y"], t.astype(np.float32)))
            self.estados[nome] = {"limiar": e["limiar"], "patches": patches}

    def pontuar(self, g):
        """{tela: nota 0..1} - a nota de uma tela e a pior dos seus recortes."""
        notas = {}
        for nome, e in self.estados.items():
            piores = []
            for x, y, t in e["patches"]:
                th, tw = t.shape
                roi = g[max(0, y - TOLERANCIA):y + th + TOLERANCIA, max(0, x - TOLERANCIA):x + tw + TOLERANCIA]
                if roi.shape[0] < th or roi.shape[1] < tw:
                    piores.append(0.0)
                    continue
                piores.append(float(cv2.matchTemplate(roi, t, cv2.TM_CCOEFF_NORMED).max()))
            notas[nome] = min(piores)
        return notas

    def detectar(self, g):
        """Telas detectadas, da mais prioritaria para a menos. Lista vazia = tela desconhecida."""
        notas = self.pontuar(g)
        achadas = [n for n, v in notas.items() if v >= self.estados[n]["limiar"]]
        return sorted(achadas, key=lambda n: PRIORIDADE.index(n) if n in PRIORIDADE else 99)
