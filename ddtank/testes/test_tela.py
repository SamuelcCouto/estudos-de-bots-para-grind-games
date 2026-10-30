# -*- coding: utf-8 -*-
"""Calibracao da tela: janelas de outros tamanhos/posicoes/zooms (montadas a partir de quadros reais).
Rode: python testes/test_tela.py"""
import os
import sys
import time

import cv2
import numpy as np

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(AQUI))
import estados as E
import navegador as N
import tela as T

det = E.Detector()
rng = np.random.default_rng(3)


def quadro(nome):
    for ext in (".jpg", ".png"):
        p = os.path.join(AQUI, "frames", nome + ext)
        if os.path.exists(p):
            return N.em_1280(cv2.imread(p))


def janela(ref, W, H, zoom, ox, oy):
    """Captura sintetica de uma janela WxH em que o canvas (recorte do quadro de referencia) tem zoom*1000 px de largura
    e o canto dele fica em (ox, oy). Fundo: ruido suave (a decoracao da pagina nao e usada pela calibracao)."""
    x, y, w, h = T.CANVAS_REF
    canvas = ref[y:y + h, x:x + w]
    cw, ch = int(round(1000 * zoom)), int(round(600 * zoom))
    canvas = cv2.resize(canvas, (cw, ch), interpolation=cv2.INTER_CUBIC if zoom > 0.67 else cv2.INTER_AREA)
    fundo = cv2.resize(rng.integers(60, 140, (max(2, H // 40), max(2, W // 40), 3)).astype(np.uint8), (W, H), interpolation=cv2.INTER_CUBIC)
    xx0, yy0 = max(0, ox), max(0, oy)
    xx1, yy1 = min(W, ox + cw), min(H, oy + ch)
    fundo[yy0:yy1, xx0:xx1] = canvas[yy0 - oy:yy1 - oy, xx0 - ox:xx1 - ox]
    return fundo


TELAS = {"CENTRAL": "CENTRAL", "BATALHA_PERICAO": "BATALHA", "SALA_VAZIA": "SALA_VAZIA", "CARTAS_COSTAS": "CARTAS",
         "MAPA": "MAPA", "CONFIG_VAZIA": "CONFIG_VAZIA"}
# (largura, altura, zoom, deslocamento do canvas na janela)
CASOS = [(1922, 1034, 1.0, 468, 243),       # a janela original (nao pode mudar nada)
         (1920, 1080, 1.0, 460, 300),       # tela cheia 1080p
         (2560, 1440, 1.0, 780, 420),       # 1440p, canvas do mesmo tamanho (centrado)
         (2560, 1440, 1.4, 500, 300),       # zoom/escala maior
         (1600, 900, 1.0, 300, 150),
         (1366, 768, 0.85, 110, 120),       # notebook pequeno, canvas reduzido
         (1280, 720, 0.75, 60, 90)]
tempos = []
for W, H, z, ox, oy in CASOS:
    for nome, esperado in TELAS.items():
        ref = quadro(nome)
        img = janela(ref, W, H, z, ox, oy)
        t0 = time.time()
        c = T.calibrar(img, det)
        tempos.append(time.time() - t0)
        assert c is not None, (W, H, z, nome, "nao calibrou")
        # verdade: canonico = janela * f + t com f = 666/(1000 z) e t = canto do canvas no canonico (312,162) - ox*f
        f_ok = 666.0 / (1000 * z)
        assert abs(c.f - f_ok) / f_ok < 0.02, (W, H, z, nome, c.f, f_ok)
        tx_ok, ty_ok = 312 - ox * c.f, 162 - oy * c.f
        assert abs(c.tx - tx_ok) <= 3 and abs(c.ty - ty_ok) <= 3, (W, H, z, nome, (c.tx, c.ty), (tx_ok, ty_ok))
        achadas = T.conferir(img, c, det)
        assert achadas and achadas[0] == esperado, (W, H, z, nome, achadas)
        # clique: o ponto "Jogar" no quadro canonico tem que cair onde esta no quadro da janela
        px, py = c.ref_para_janela(*N.CENTRAL_JOGAR)
        verdade = ((N.CENTRAL_JOGAR[0] - 312) / 666 * 1000 * z + ox, (N.CENTRAL_JOGAR[1] - 162) / 399 * 600 * z + oy)
        assert abs(px - verdade[0]) <= 4 * z + 2 and abs(py - verdade[1]) <= 4 * z + 2, (W, H, z, nome, (px, py), verdade)
    print(f"janela {W}x{H} zoom {z}: {len(TELAS)} telas calibradas e reconhecidas OK (ultima: {c.texto()})")
print(f"tempo por calibracao: media {np.mean(tempos):.2f}s, maximo {max(tempos):.2f}s")
assert T.Calibracao(T.F0, 0, 0).legado
# plano B (lento): sem os pontos de interesse, procura os recortes das telas em varias escalas
c2 = T.calibrar_recortes(janela(quadro("CENTRAL"), 1600, 900, 1.0, 300, 150), det)
assert c2 and abs(c2.f - 0.666) < 0.01 and abs(c2.tx - 112) <= 3 and abs(c2.ty - 62) <= 3, c2 and (c2.f, c2.tx, c2.ty)
print("plano B (recortes em varias escalas) OK")
# janela original = modo legado (comportamento identico ao de sempre)
ref = quadro("CENTRAL")
orig = cv2.resize(ref, (1922, int(round(ref.shape[0] * 1922 / 1280))), interpolation=cv2.INTER_CUBIC)
c = T.calibrar(orig, det)
assert c.legado, c.texto()
# tela desconhecida (preta): nao calibra e nao quebra
assert T.calibrar(np.zeros((900, 1600, 3), np.uint8), det) is None
print("\ncalibracao de tela OK")

# ---- IOJanela de ponta a ponta: janela 2560x1440 com o canvas em (500, 300), zoom 1.4 (jogo "fingido")
class JanelaFalsa:
    def __init__(self, img): self.img, self.cliques = img, []
    def capturar(self, hwnd, modo="print"): return self.img
    def clicar(self, hwnd, x, y, modo="top"): self.cliques.append((x, y))

logs = []
fake = JanelaFalsa(janela(quadro("CENTRAL"), 2560, 1440, 1.4, 500, 300))
io = N.IOJanela(1, janela_mod=fake, log=logs.append)
f = io.capturar()
assert f.shape[:2] == (688, 1280) and io.k == 1.0, (f.shape, io.k)
assert det.detectar(E.normalizar(f))[0] == "CENTRAL", "o quadro canonico e a Central"
io.clicar(*N.CENTRAL_JOGAR, "top")            # o bot clica em coordenadas canonicas...
x, y = fake.cliques[-1]
vx, vy = (N.CENTRAL_JOGAR[0] - 312) / 666 * 1400 + 500, (N.CENTRAL_JOGAR[1] - 162) / 399 * 840 + 300
assert abs(x - vx) <= 5 and abs(y - vy) <= 5, ((x, y), (vx, vy))   # ...e o clique cai em cima do botao na janela real
io.clicar_ref(560, 230, "top"); assert fake.cliques[-1] != (560, 230)
assert any("[TELA] calibrada" in l for l in logs), logs
n_cliques = len(fake.cliques)
# a janela original continua sem nenhuma conversao (modo legado)
ref = quadro("CENTRAL")
orig = cv2.resize(ref, (1922, int(round(ref.shape[0] * 1922 / 1280))), interpolation=cv2.INTER_CUBIC)
fake2 = JanelaFalsa(orig); io2 = N.IOJanela(1, janela_mod=fake2, log=lambda m: None)
f2 = io2.capturar()
assert f2.shape == orig.shape and abs(io2.k - 1922 / 1280) < 1e-9 and io2.calib.legado
io2.clicar(500, 600, "top"); assert fake2.cliques[-1] == (500, 600)
# janela que muda de tamanho no meio do jogo: calibra de novo sozinho
fake2.img = janela(quadro("CENTRAL"), 1600, 900, 1.0, 300, 150)
f3 = io2.capturar()
assert f3.shape[:2] == (688, 1280) and not io2.calib.legado and det.detectar(E.normalizar(f3))[0] == "CENTRAL"
print("IOJanela (calibra sozinho, converte cliques, janela original sem mudanca, janela que muda) OK")

# ---- diagnostico "testar a minha tela"
import tempfile
saida = []
pasta = tempfile.mkdtemp()
assert N.testar_tela(io, det, saida=saida.append, pasta=pasta) is True, saida
assert any("RESULTADO: OK" in l for l in saida) and os.path.exists(os.path.join(pasta, "teste_tela.png")) and os.path.exists(os.path.join(pasta, "teste_tela.txt"))
pequena = JanelaFalsa(janela(quadro("CENTRAL"), 1280, 720, 0.7, 60, 90))
saida = []
N.testar_tela(N.IOJanela(1, janela_mod=pequena, log=lambda m: None), det, saida=saida.append, pasta=pasta)
assert any("pequeno" in l for l in saida), saida
saida = []
assert N.testar_tela(N.IOJanela(1, janela_mod=JanelaFalsa(np.zeros((900, 1600, 3), np.uint8)), log=lambda m: None), det, saida=saida.append, pasta=pasta) is False
print("\n".join(saida[-2:]))
print("testar_tela OK")

# ---- tela desconhecida nao pode travar o bot (21h de 29/10: 4 sessoes ficaram minutos "ligadas" sem fazer nada na calibracao lenta)
t0 = time.time()
c = T.calibrar(np.zeros((1034, 1922, 3), np.uint8), det)
assert c is not None and c.legado and time.time() - t0 < 3, "janela original + tela desconhecida: modo legado na hora"
t0 = time.time()
assert T.calibrar(np.zeros((900, 1600, 3), np.uint8), det) is None and time.time() - t0 < T.ORCAMENTO_PLANO_B + 4
print("calibracao com tela desconhecida nao trava OK")
