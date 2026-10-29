# -*- coding: utf-8 -*-
"""
Calibracao da tela: faz o bot funcionar em QUALQUER tamanho de janela/monitor.

O jogo e um quadro fixo (o "canvas", 1000x600 px na janela de 1922x1034 em que o bot foi feito) cercado por decoracao
da pagina. Todo o resto do bot (templates, leitura do minimapa, cliques) usa o quadro de referencia de 1280 px de
largura em que o canvas ocupa (312, 162) com 666x399 px. Em outra janela o canvas pode estar em outro lugar
(janela maior/menor, tela cheia) e/ou em outro tamanho (zoom, escala do Windows). Esta calibracao descobre
    canonico = janela * f + (tx, ty)
procurando as imagens das telas conhecidas (templates/estados) em varias escalas, e entrega ao bot um quadro
"canonico" de 1280x688 igual ao de sempre. Os cliques fazem o caminho inverso: janela = (canonico - t) / f.
Na janela original (f ~ 0.666, t ~ 0) nada muda (modo legado: o quadro inteiro redimensionado, como antes).
"""
import glob
import os

import cv2
import numpy as np

import config
import estados as E

REF_W, REF_H = 1280, 688
CANVAS_REF = (312, 162, 666, 399)             # x, y, largura, altura do canvas no quadro de referencia
F0 = 1280.0 / 1922.0                           # fator janela -> referencia da janela original (1922 px de largura)
ZOOMS = [round(z, 3) for z in np.exp(np.linspace(np.log(0.5), np.log(2.2), 70))]   # tamanho do canvas / 1000 px
ZOOM_MIN_BOM = 0.75                            # abaixo disso o minimapa (pontos de 8 px) perde precisao


class Calibracao:
    def __init__(self, f=F0, tx=0, ty=0, nota=1.0, estado=None):
        self.f, self.tx, self.ty, self.nota, self.estado = f, int(tx), int(ty), nota, estado

    @property
    def zoom(self):
        return F0 / self.f

    @property
    def legado(self):
        """Janela original: o caminho antigo (quadro inteiro por largura) ja serve."""
        return abs(self.f - F0) / F0 < 0.008 and abs(self.tx) <= 1 and abs(self.ty) <= 1

    def renderizar(self, img):
        """Quadro da janela -> quadro canonico 1280x688 (preto fora do que a janela cobre)."""
        h, w = img.shape[:2]
        r = cv2.resize(img, (max(1, int(round(w * self.f))), max(1, int(round(h * self.f)))), interpolation=cv2.INTER_AREA)
        out = np.zeros((REF_H, REF_W, 3), np.uint8)
        x0, y0 = max(0, self.tx), max(0, self.ty)                 # onde cola no canonico
        sx0, sy0 = max(0, -self.tx), max(0, -self.ty)             # de onde copia em r
        wd, ht = min(REF_W - x0, r.shape[1] - sx0), min(REF_H - y0, r.shape[0] - sy0)
        if wd > 0 and ht > 0:
            out[y0:y0 + ht, x0:x0 + wd] = r[sy0:sy0 + ht, sx0:sx0 + wd]
        return out

    def ref_para_janela(self, x, y):
        return (x - self.tx) / self.f, (y - self.ty) / self.f

    def janela_para_ref(self, x, y):
        return x * self.f + self.tx, y * self.f + self.ty

    def texto(self, tam=None):
        t = f"zoom {self.zoom:.2f} (1.00 = canvas de 1000x600 px), deslocamento ({self.tx}, {self.ty})"
        return (f"janela {tam[0]}x{tam[1]}: " if tam else "") + t + (", modo legado (janela original)" if self.legado else "")


def _cinza(img, f):
    r = cv2.resize(img, None, fx=f, fy=f, interpolation=cv2.INTER_AREA) if abs(f - 1) > 1e-6 else img
    return cv2.GaussianBlur(cv2.cvtColor(r, cv2.COLOR_BGR2GRAY), (3, 3), 0).astype(np.float32)


def _achar(g, det, estados):
    """Procura os 2 recortes de cada tela no quadro inteiro. Devolve (nota, (tx, ty), tela) do melhor candidato cujos
    2 recortes concordam sobre onde esta o canvas, ou None."""
    melhor = None
    for nome in estados:
        e = det.estados[nome]
        if len(e["patches"]) < 2:
            continue
        achados = []
        for x, y, t in e["patches"]:
            if g.shape[0] < t.shape[0] or g.shape[1] < t.shape[1]:
                achados = None
                break
            _, v, _, loc = cv2.minMaxLoc(cv2.matchTemplate(g, t, cv2.TM_CCOEFF_NORMED))
            if v < e["limiar"] * 0.92:             # o 1o recorte ja nao bate: nem procura o 2o (e o que poupa tempo)
                achados = None
                break
            achados.append((v, x - loc[0], y - loc[1]))
        if not achados:
            continue
        txs, tys = [a[1] for a in achados], [a[2] for a in achados]
        if max(txs) - min(txs) > 3 or max(tys) - min(tys) > 3:
            continue
        nota = min(a[0] for a in achados) / e["limiar"]
        desvio = (max(txs) - min(txs)) + (max(tys) - min(tys))     # 0 quando os 2 recortes concordam (fator certo)
        obj = nota - 0.3 * desvio
        if melhor is None or obj > melhor[0]:
            melhor = (obj, (int(round(np.mean(txs))), int(round(np.mean(tys)))), nome)
    return melhor


_REFS = []
SIFT_LARGURA_MAX = 1400          # a janela e reduzida a isso para achar os pontos (rapido); o fator volta ao tamanho real
SIFT_MIN_INLIERS = 18


def _refs():
    """Quadros de referencia do canvas (templates/ref/*.jpg, 666x399): pontos SIFT calculados uma vez."""
    if not _REFS:
        sift = cv2.SIFT_create(nfeatures=2500)
        for arq in sorted(glob.glob(os.path.join(config.PASTA_TEMPLATES, "ref", "*.jpg"))):
            im = cv2.imread(arq, cv2.IMREAD_GRAYSCALE)
            if im is not None:
                k, d = sift.detectAndCompute(im, None)
                if d is not None and len(k) >= 20:
                    _REFS.append((os.path.basename(arq)[:-4], np.float32([p.pt for p in k]), d))
    return _REFS


def calibrar_pontos(img):
    """Descobre o fator/deslocamento casando PONTOS DE INTERESSE (SIFT, indiferentes a escala) da janela com os quadros de
    referencia do canvas. Rapido (~1 s) e funciona em qualquer zoom. Devolve Calibracao ou None."""
    refs = _refs()
    if not refs:
        return None
    h, w = img.shape[:2]
    pre = min(1.0, SIFT_LARGURA_MAX / float(w))
    pequena = cv2.resize(img, None, fx=pre, fy=pre, interpolation=cv2.INTER_AREA) if pre < 1 else img
    sift = cv2.SIFT_create(nfeatures=3000)
    k, d = sift.detectAndCompute(cv2.cvtColor(pequena, cv2.COLOR_BGR2GRAY), None)
    if d is None or len(k) < SIFT_MIN_INLIERS:
        return None
    pts = np.float32([p.pt for p in k])
    bf = cv2.BFMatcher(cv2.NORM_L2)
    melhor = None
    for nome, rp, rd in refs:
        bons = [m[0] for m in bf.knnMatch(rd, d, k=2) if len(m) == 2 and m[0].distance < 0.75 * m[1].distance]
        if len(bons) < SIFT_MIN_INLIERS:
            continue
        src, dst = np.float32([pts[m.trainIdx] for m in bons]), np.float32([rp[m.queryIdx] for m in bons])
        M, inl = cv2.estimateAffinePartial2D(src, dst, method=cv2.RANSAC, ransacReprojThreshold=2.5)
        if M is None or inl is None:
            continue
        n = int(inl.sum())
        if n >= SIFT_MIN_INLIERS and (melhor is None or n > melhor[0]):
            melhor = (n, nome, M)
    if melhor is None:
        return None
    n, nome, M = melhor
    escala = float(np.hypot(M[0, 0], M[1, 0]))
    if abs(M[1, 0]) > 0.05 * escala:                      # girado: nao e a tela do jogo
        return None
    f = escala * pre                                       # janela (tamanho real) -> canvas de referencia
    tx, ty = M[0, 2] + CANVAS_REF[0], M[1, 2] + CANVAS_REF[1]   # (o recorte de referencia comeca em (312, 162))
    return Calibracao(f, int(round(tx)), int(round(ty)), float(n), "pontos:" + nome)


def calibrar(img, det=None, log=print):
    """Calibracao de um quadro da janela (BGR, tamanho real): primeiro pelos pontos de interesse (rapido), conferindo que
    o quadro canonico resultante e uma tela conhecida; senao, procurando os recortes das telas em varias escalas (lento).
    None se nada deu certo."""
    det = det or E.Detector()
    try:
        c = calibrar_pontos(img)
    except cv2.error:
        c = None
    if c is not None and (conferir(img, c, det) or c.legado):
        return c
    return calibrar_recortes(img, det)


def calibrar_recortes(img, det):
    estados = [n for n in det.estados if n not in ("CLIQUE_JOGO",)]
    # 1) primeiro o tamanho original (o caso comum e o mais rapido), 2) varia o zoom
    ordem = sorted(ZOOMS, key=lambda z: abs(np.log(z)))
    for z in ordem:
        f = F0 / z
        g = _cinza(img, f)
        r = _achar(g, det, estados)
        if r:
            nota, (tx, ty), nome = r
            return _refinar(img, det, estados, f, Calibracao(f, tx, ty, nota, nome))
    return None


def _refinar(img, det, estados, f0, atual):
    """Ajuste fino do fator (a grade do zoom e de ~1.9%): passos de 0.6% e depois de 0.2%, ficando com a melhor nota."""
    melhor = atual
    for passo in (0.006, 0.002):
        base = melhor.f
        for k in (-3, -2, -1, 1, 2, 3):
            f = base * (1 + k * passo)
            r = _achar(_cinza(img, f), det, [melhor.estado] if melhor.estado else estados)
            if r and r[0] > melhor.nota + 1e-4:
                melhor = Calibracao(f, r[1][0], r[1][1], r[0], r[2])
    return melhor


def conferir(img, calib, det=None):
    """Telas reconhecidas no quadro canonico gerado por `calib`."""
    det = det or E.Detector()
    return det.detectar(E.normalizar(calib.renderizar(img)))
