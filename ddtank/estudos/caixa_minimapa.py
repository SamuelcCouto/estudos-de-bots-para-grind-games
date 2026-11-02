"""Retangulo azul do minimapa do PVP = area visivel da tela (10,17 unidades da regua do jogo). Largura em px / 10,17 = px por unidade do mapa."""
import cv2, numpy as np
MINI = (815, 156, 985, 256)        # (x0, y0, x1, y1) no quadro de 1280
UNID_TELA = 10.17


def _corridas(m, eixo, minimo):
    """indices das linhas/colunas de m (0/1) que tem uma corrida continua >= minimo"""
    idx = []
    a = m if eixo == 0 else m.T
    for i in range(a.shape[1]):
        col = a[:, i]
        run = best = 0
        for v in col:
            run = run + 1 if v else 0
            best = max(best, run)
        if best >= minimo:
            idx.append(i)
    return idx


def caixa(f):
    x0, y0, x1, y1 = MINI
    h = cv2.cvtColor(f[y0:y1, x0:x1], cv2.COLOR_BGR2HSV)
    m = ((h[..., 0] >= 112) & (h[..., 0] <= 130) & (h[..., 1] >= 150) & (h[..., 2] >= 90)).astype(np.uint8)
    cols = _corridas(m, 0, 14)           # lados verticais do retangulo: corridas de >= 14 px
    if len(cols) < 2:
        return None
    # agrupa colunas vizinhas (linha de 2-3 px) e pega o par mais afastado que tenha ao menos 40 px entre si
    grupos, atual = [], [cols[0]]
    for c in cols[1:]:
        if c - atual[-1] <= 2:
            atual.append(c)
        else:
            grupos.append(atual); atual = [c]
    grupos.append(atual)
    cs = [float(np.mean(g)) for g in grupos]
    melhor = None
    for i in range(len(cs)):
        for j in range(i + 1, len(cs)):
            w = cs[j] - cs[i]
            if w >= 40:
                if melhor is None or w < melhor[0]:      # o par MAIS ESTREITO que ainda e do tamanho de uma tela
                    melhor = (w, cs[i] + x0, cs[j] + x0)
    return melhor
