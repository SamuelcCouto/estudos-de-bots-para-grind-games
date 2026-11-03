# -*- coding: utf-8 -*-
"""
Terreno EXATO do mapa da partida (o mesmo desenho que o jogo usa para a colisao).

    t = Terreno.do_mapa(858914)          # numero do mapa: vem no pacote GAME_LOAD (rede_vivo.Estado.mapa)
    t.inclinacao(x, y)                    # inclinacao do boneco nesse ponto (PhysicalObj.calcObjectAngle)
    fisica_exata.simular(..., terreno=t)  # o projetil para no chao como no jogo
    t.cavar(x, y, raio)                   # buraco da explosao (o terreno muda durante a partida)

De onde vem (cliente descompilado, 02/11):
- MapLoader: https://res20.ddtankbetel.com/image/map/<ID>/<ForePic>.png (chao que quebra) e <DeadPic>.png (pedra que nao quebra);
  os dados do mapa (tamanho, gravidade, arrasto) estao em dados/jogo/loadmapsitems.xml;
- Ground.IsEmpty: o pixel e chao quando o alfa e > 150;
- Map.IsRectangleEmpty (bala): testa so os 4 cantos do retangulo;
- calcObjectAngle(16): para i = 1, 3, ..., 15 dos dois lados, desce de y+10 ate y-10 e pega o 1o ponto vazio (se ja o de baixo
  estiver vazio, nao conta); media dos pontos de cada lado (com o proprio boneco) e o angulo entre as duas medias, arredondado para
  baixo (MathUtils.GetAngleTwoPoint).
- GamePlayer.shootPoint: o tiro sai de (30, -20) no corpo do boneco (espelhado quando olha para a esquerda), girado pela inclinacao,
  com o corpo 3 px acima do pe: saida = pe + (0, -3) + gira(inclinacao, (+-30, -20)). Conferido em 40+ tiros reais (1-2 px).
- Buraco da explosao: a IMAGEM da cratera da bala (balllist.xml "Crater" -> image/bomb/crater/<id>/crater.png; Tile.Dig apaga o chao
  com ela, centrada na explosao). Em 350 explosoes reais: mediana 1,1 px, 95% a ate 5 px (03/11). Sem imagem: oval Radii x 0,6 Radii.
- O ponteiro do mostrador (o que o bot le) ja mostra o angulo REAL do tiro (com a inclinacao): a inclinacao so muda o ponto de saida e
  a faixa que a arma alcanca (mostrador = arma - inclinacao olhando para a direita, arma + inclinacao para a esquerda).
"""
import math
import os
import re
import urllib.request

import cv2
import numpy as np

import config

PASTA = os.path.join(config.PASTA, "dados", "mapas_jogo")
ARQ_MAPAS = os.path.join(config.PASTA, "dados", "jogo", "loadmapsitems.xml")
ARQ_BALAS = os.path.join(config.PASTA, "dados", "jogo", "balllist.xml")
URL_MAPA = "https://res20.ddtankbetel.com/image/map/{id}/{pic}.png"
URL_CRATERA = "https://res20.ddtankbetel.com/image/bomb/crater/{id}/crater.png"   # PathManager.solveCrater
PASTA_CRATERAS = os.path.join(config.PASTA, "dados", "crateras")
ALFA_CHAO = 150
SAIDA_NO_CORPO = (30.0, -20.0)     # GamePlayer._ballpos
CORPO_DY = -3.0                    # GamePlayer._player.y
BURACO_LARGURA, BURACO_ALTURA = 1.0, 0.6   # x Radii da bala

_INFO = {}
_BALAS = {}
_CRATERAS = {}


def _atributos(tag):
    return dict(re.findall(r'(\w+)="([^"]*)"', tag))


def info_mapa(mapa_id):
    """Dados do mapa (loadmapsitems.xml): ForePic, DeadPic, ForegroundWidth/Height, Weight, DragIndex... ou None."""
    if not _INFO and os.path.exists(ARQ_MAPAS):
        s = open(ARQ_MAPAS, encoding="utf-8", errors="replace").read()
        for tag in re.findall(r"<Item [^>]*>", s):
            a = _atributos(tag)
            if "ID" in a:
                _INFO[int(a["ID"])] = a
    return _INFO.get(int(mapa_id))


def info_bala(bala_id):
    """Dados da bala (balllist.xml): Mass, Weight, Wind, DragIndex, Radii... ou None."""
    if not _BALAS and os.path.exists(ARQ_BALAS):
        s = open(ARQ_BALAS, encoding="utf-8", errors="replace").read()
        for tag in re.findall(r"<Item [^>]*>", s):
            a = _atributos(tag)
            if "ID" in a:
                _BALAS[int(a["ID"])] = a
    return _BALAS.get(int(bala_id))


def _imagem(mapa_id, pic, baixar=True):
    """PNG do mapa (com alfa), do cache local ou baixado do servidor de imagens do jogo."""
    os.makedirs(PASTA, exist_ok=True)
    arq = os.path.join(PASTA, f"{mapa_id}_{pic}.png")
    if not os.path.exists(arq):
        if not baixar:
            return None
        req = urllib.request.Request(URL_MAPA.format(id=mapa_id, pic=pic), headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=20) as r:
            dados = r.read()
        with open(arq + ".tmp", "wb") as f:
            f.write(dados)
        os.replace(arq + ".tmp", arq)
    im = cv2.imread(arq, cv2.IMREAD_UNCHANGED)
    if im is None or im.ndim != 3 or im.shape[2] != 4:
        return None
    return im


class Terreno:
    def __init__(self, chao, pedra=None, mapa_id=None, info=None):
        self.chao = chao                       # bool [y, x]: chao que quebra (fore)
        self.pedra = pedra                     # bool [y, x] ou None: pedra que nao quebra (dead)
        self.mapa_id, self.info = mapa_id, info or {}
        self.altura, self.largura = chao.shape

    @classmethod
    def do_mapa(cls, mapa_id, baixar=True):
        """Terreno do mapa `mapa_id` (None se o mapa nao existe ou nao deu para baixar)."""
        info = info_mapa(mapa_id)
        if not info:
            return None
        try:
            fore = _imagem(mapa_id, info.get("ForePic") or "fore", baixar) if info.get("ForePic", "fore") else None
            dead = _imagem(mapa_id, info["DeadPic"], baixar) if info.get("DeadPic") else None
        except OSError:
            return None
        if fore is None and dead is None:
            return None
        base = fore if fore is not None else dead
        chao = fore[..., 3] > ALFA_CHAO if fore is not None else np.zeros(base.shape[:2], bool)
        pedra = dead[..., 3] > ALFA_CHAO if dead is not None else None
        return cls(chao, pedra, mapa_id, info)

    def fisica(self):
        """(weight, drag) do mapa, para fisica_exata.MapaFisico."""
        return float(self.info.get("Weight", 10)), float(self.info.get("DragIndex", 2))

    def vazio(self, x, y):
        """Ground.IsEmpty: fora da imagem e vazio."""
        x, y = int(x), int(y)
        if x < 0 or y < 0 or x >= self.largura or y >= self.altura:
            return True
        return not (self.chao[y, x] or (self.pedra is not None and self.pedra[y, x]))

    def __call__(self, x0, y0, x1, y1):
        """Callback do fisica_exata.simular: True se o retangulo tem chao (Map.IsRectangleEmpty testa so os 4 cantos)."""
        return not (self.vazio(x0, y0) and self.vazio(x1, y0) and self.vazio(x0, y1) and self.vazio(x1, y1))

    def inclinacao(self, x, y, alcance=16):
        """PhysicalObj.calcObjectAngle: inclinacao (graus) do boneco parado em (x, y) (posicao da rede = o pe)."""
        x, y = int(x), int(y)
        dir_, esq = [], []
        for i in range(1, alcance + 1, 2):
            for lado, pts in ((1, dir_), (-1, esq)):
                for j in range(-10, 11):
                    if self.vazio(x + lado * i, y - j):
                        if j != -10:
                            pts.append((x + lado * i, y - j))
                        break
        p4 = ((x + sum(p[0] for p in dir_)) / (len(dir_) + 1), (y + sum(p[1] for p in dir_)) / (len(dir_) + 1))
        p5 = ((x + sum(p[0] for p in esq)) / (len(esq) + 1), (y + sum(p[1] for p in esq)) / (len(esq) + 1))
        return float(math.floor(math.degrees(math.atan2(p4[1] - p5[1], p4[0] - p5[0]))))

    def cavar(self, x, y, raio, raio_y=None):
        """Buraco da explosao (so no chao que quebra): redondo, ou oval com raio_y."""
        if raio > 0:
            m = np.zeros(self.chao.shape, np.uint8)
            cv2.ellipse(m, (int(round(x)), int(round(y))), (int(round(raio)), int(round(raio if raio_y is None else raio_y))), 0, 0, 360, 1, -1)
            self.chao[m > 0] = False

    def cavar_bomba(self, x, y, bala_id):
        """Buraco que a explosao da bala `bala_id` deixa: a imagem da cratera da bala (Tile.Dig apaga o chao com ela, centrada na
        explosao); sem imagem, um oval pelo Radii."""
        info = info_bala(bala_id) or {}
        mascara = cratera(info.get("Crater"))
        if mascara is not None:
            self.cavar_mascara(x, y, mascara)
            return
        r = float(info.get("Radii", 60))
        self.cavar(x, y, r * BURACO_LARGURA, r * BURACO_ALTURA)

    def cavar_mascara(self, x, y, mascara):
        """Apaga o chao onde a mascara (bool, centrada em (x, y)) e verdadeira."""
        h, w = mascara.shape
        x0, y0 = int(x - w / 2), int(y - h / 2)
        a0, b0 = max(0, x0), max(0, y0)
        a1, b1 = min(self.largura, x0 + w), min(self.altura, y0 + h)
        if a1 > a0 and b1 > b0:
            self.chao[b0:b1, a0:a1] &= ~mascara[b0 - y0:b1 - y0, a0 - x0:a1 - x0]

    def no_chao(self, x, y):
        """O pe (x, y) esta sobre o chao (vazio no pe ou 1 px acima, chao ate 2 px abaixo): o terreno daqui bate com o do jogo."""
        x, y = int(x), int(y)
        return (self.vazio(x, y - 1)) and any(not self.vazio(x, y + k) for k in range(0, 3))

    def copia(self):
        return Terreno(self.chao.copy(), None if self.pedra is None else self.pedra, self.mapa_id, self.info)


def gira(graus, px, py):
    """Giro do Flash (rotation em graus, y para baixo)."""
    c, s_ = math.cos(math.radians(graus)), math.sin(math.radians(graus))
    return px * c - py * s_, px * s_ + py * c


def saida_do_tiro(pe, direcao, inclinacao):
    """Ponto de onde o projetil sai (GamePlayer.shootPoint): pe + (0, -3) + gira(inclinacao, (direcao*30, -20))."""
    dx, dy = gira(inclinacao, direcao * SAIDA_NO_CORPO[0], SAIDA_NO_CORPO[1])
    return math.trunc(pe[0] + dx), math.trunc(pe[1] + CORPO_DY + dy)       # o cliente manda int() (corta as casas)


_CACHE = {}


def terreno_da_partida(mapa_id, buracos, baixar=True, margem=0):
    """Terreno do mapa com os buracos das explosoes desta partida [(x, y, bala)] (guarda o mapa e os buracos ja cavados).
    margem > 0: cada buraco `margem` px menor em volta (terreno "pessimista", para a bala nao passar raspando na borda de um buraco)."""
    if mapa_id is None:
        return None
    chave = "atual" if not margem else ("atual", margem)
    c = _CACHE.get(chave)
    if not c or c[0] != mapa_id or len(c[1]) > len(buracos) or c[1] != list(buracos[:len(c[1])]):
        base = _CACHE.get(("base", mapa_id))
        if base is None:
            base = Terreno.do_mapa(mapa_id, baixar)
            if base is None:
                return None
            _CACHE[("base", mapa_id)] = base
        c = (mapa_id, [], base.copia())
    ter = c[2]
    for x, y, bala in buracos[len(c[1]):]:
        if not margem:
            ter.cavar_bomba(x, y, bala)
            continue
        info = info_bala(bala) or {}
        m = cratera(info.get("Crater"))
        if m is not None:
            k = np.ones((2 * margem + 1, 2 * margem + 1), np.uint8)
            ter.cavar_mascara(x, y, cv2.erode(m.astype(np.uint8), k).astype(bool))
        else:
            r = float(info.get("Radii", 60))
            ter.cavar(x, y, max(1.0, r * BURACO_LARGURA - margem), max(1.0, r * BURACO_ALTURA - margem))
    _CACHE[chave] = (mapa_id, list(buracos), ter)
    return ter


def cratera(cratera_id, baixar=True, alfa_minimo=105):
    """Mascara (bool) da cratera `cratera_id`: o ERASE do Flash tira alfa * (1 - a/255) do chao; com chao de alfa 255 o pixel vira vazio
    (alfa <= 150) quando a cratera tem a >= 105. None se a bala nao tem cratera ou nao deu para baixar."""
    if not cratera_id:
        return None
    if cratera_id in _CRATERAS:
        return _CRATERAS[cratera_id]
    arq = os.path.join(PASTA_CRATERAS, f"{cratera_id}_crater.png")
    m = None
    try:
        if not os.path.exists(arq) and baixar:
            os.makedirs(PASTA_CRATERAS, exist_ok=True)
            req = urllib.request.Request(URL_CRATERA.format(id=cratera_id), headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=15) as r:
                dados = r.read()
            with open(arq + ".tmp", "wb") as f:
                f.write(dados)
            os.replace(arq + ".tmp", arq)
        im = cv2.imread(arq, cv2.IMREAD_UNCHANGED) if os.path.exists(arq) else None
        if im is not None and im.ndim == 3 and im.shape[2] == 4:
            m = im[..., 3] >= alfa_minimo
    except OSError:
        m = None
    _CRATERAS[cratera_id] = m
    return m
