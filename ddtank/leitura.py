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
PONTO_TAMANHO_CHEIO = 8           # nucleo (px) a partir do qual um ponto conta "inteiro" no rastreador
LEITURAS_MUDOU = 5                  # leituras seguidas sem o ponto antigo (e com um novo) = o boneco mudou de lugar
VIDA_BOSS = (725, 812, 185, 191)     # barra de vida do boss (topo): cheia termina em ~811, comeca em ~725
RETRATO_BOSS = (692, 176, 720, 200)  # x0, y0, x1, y1: retrato do boss a esquerda da barra (cinza = morto)
SATURACAO_RETRATO_MORTO = 35
# Chefao Global (Pericao): a barra de vida e a do SERVIDOR (todos batendo) e quase nao mexe com o seu tiro. O acerto se
# ve pelos NUMEROS DE DANO (laranja/amarelo com contorno vermelho) que sobem em cima do boss logo depois do tiro.
NUMEROS_DANO_CAIXA = (800, 330, 1010, 480)   # x0, y0, x1, y1: em volta do Pericao (a camera fica parada nos tiros normais)
NUMEROS_DANO_ACERTO = 800      # px laranja na caixa: tiros normais 908-5674; sem tiro/turno do boss ate ~700
POW_CENTRO = (933, 512, 957, 534)  # x0, y0, x1, y1: o "POW" do botao do especial (canto de baixo, a direita)
SATURACAO_POW_CHEIO = 60       # cheio: o POW fica vermelho e pulsa (saturacao 70-190); vazio: prata (14-48)
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


_GEOM_PONTEIRO = {}


def _coords_ponteiro(pivo, rmin, rmax, faixa, passo, lado):
    """Pixels (ys, xs) amostrados ao longo de cada direcao candidata: [angulos, 3 linhas paralelas, raios]."""
    chave = (pivo, rmin, rmax, faixa, passo, lado)
    if chave not in _GEOM_PONTEIRO:
        rs = np.arange(rmin, rmax + 1, 1.0)
        angs = np.arange(faixa[0], faixa[1] + passo, passo)
        t = np.radians(angs if lado > 0 else 180.0 - angs)[:, None, None]
        dy = np.array([-0.7, 0.0, 0.7])[None, :, None]       # tolerancia de 1 px perpendicular
        xs = np.round(pivo[0] + rs[None, None, :] * np.cos(t) - dy * np.sin(t)).astype(int)
        ys = np.round(pivo[1] - rs[None, None, :] * np.sin(t) - dy * np.cos(t)).astype(int)
        _GEOM_PONTEIRO[chave] = (angs, ys, xs)
    return _GEOM_PONTEIRO[chave]


def _ponteiro(cor, lado, pivo, rmin, rmax, faixa, passo):
    """(angulo, nota) da melhor linha vermelha/laranja saindo do pivo para o lado dado (+1 direita, -1 esquerda)."""
    angs, ys, xs = _coords_ponteiro(pivo, rmin, rmax, faixa, passo, lado)
    notas = np.percentile(cor[ys, xs].max(axis=1), 20, axis=1)
    i = int(np.argmax(notas))
    return float(angs[i]), float(notas[i])


def mira(f, pivo=MOSTRADOR_PIVO, rmin=10, rmax=28, faixa=(-30, 100), passo=0.5):
    """(angulo, lado). lado = +1 se o boneco esta virado para a DIREITA (ponteiro do lado direito do mostrador), -1 para
    a ESQUERDA (ponteiro espelhado). O angulo e sempre medido a partir do chao do lado para onde ele olha (o numero do
    mostrador; o ponteiro le ~2-5 graus abaixo do numero).
    Gravacoes: virado para a direita, nota ~98 no lado direito e ~8 no esquerdo; virado para a esquerda, ~70-115 no
    esquerdo e ~22 no direito (sobra uma marca fina do tiro anterior)."""
    fi = f.astype(np.float32)
    cor = fi[..., 2] - fi[..., 0]                    # R - B
    ad, nd = _ponteiro(cor, +1, pivo, rmin, rmax, faixa, passo)
    ae, ne = _ponteiro(cor, -1, pivo, rmin, rmax, faixa, passo)
    return (ad, 1) if nd >= ne else (ae, -1)


def angulo(f, pivo=MOSTRADOR_PIVO, rmin=10, rmax=28, faixa=(-30, 100), passo=0.5):
    """Angulo de mira em graus (do lado para onde o boneco olha). Erro medio ~2 graus."""
    return mira(f, pivo, rmin, rmax, faixa, passo)[0]


def forca(f):
    """Enchimento da barra de forca, 0-100."""
    x0, x1, y0, y1 = BARRA_FORCA
    faixa = f[y0:y1, x0:x1].astype(int)
    b, g, r = faixa[..., 0], faixa[..., 1], faixa[..., 2]
    col = ((r > 170) & (g > 90) & (b < 140) & (r - b > 70)).mean(axis=0) > 0.5
    xs = np.where(col)[0]
    return 0.0 if len(xs) == 0 else (xs.max() + 1) / (x1 - x0) * 100


_LINHA_H = cv2.getStructuringElement(cv2.MORPH_RECT, (13, 1))
_LINHA_V = cv2.getStructuringElement(cv2.MORPH_RECT, (1, 11))


def _sem_linhas(mk):
    """Tira da mascara os tracos retos compridos (>= 13 px na horizontal, >= 11 na vertical) e 1 px em volta deles:
    a moldura do minimapa (que as vezes fica azul-escura ou vermelha) e a borda das plataformas. Os cantos da moldura
    cruzando o chao viravam "pontos" (Dragao Gelado). Um ponto (5x5) nunca e um traco desses."""
    m = mk.astype(np.uint8)
    linhas = cv2.morphologyEx(m, cv2.MORPH_OPEN, _LINHA_H) | cv2.morphologyEx(m, cv2.MORPH_OPEN, _LINHA_V)
    return m & (1 - cv2.dilate(linhas, np.ones((3, 3), np.uint8)))


def _pontos_redondos(mk):
    """[(x, y, tamanho)] dos pontos compactos da mascara, maiores primeiro. A erosao em cruz apaga o que tem ate 2 px de
    largura (moldura do minimapa, que fica verde/azul/vermelha conforme a instancia; rastro da cachoeira) e manchas
    grandes (agua, efeitos de tela) ficam de fora pelo tamanho. Fora tambem: cabecalho e as bordas."""
    nucleo = cv2.erode(_sem_linhas(mk), _CRUZ)
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


def _pontos_pequenos(mk):
    """Plano B (so quando o leitor normal nao achou nada): pontos MUITO pequenos (Gato Preto: o boneco com o buff do pet tem
    um circulo claro em volta e o miolo azul fica com ~3 px, que a erosao em cruz apaga). Componentes sem erosao, 3 a 30 px,
    compactos (preenchem >= 55% do retangulo), fora de tracos retos."""
    n, _, st, ce = cv2.connectedComponentsWithStats(_sem_linhas(mk))
    out = []
    for i in range(1, n):
        _x, _y, w, h, a = st[i]
        cx, cy = float(ce[i][0]), float(ce[i][1])
        if not (3 <= a <= 30) or w > MINIMAPA_PONTO_MAX or h > MINIMAPA_PONTO_MAX or a < 0.55 * w * h:
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
    # mascara ESTRITA: no Dragao Gelado (mapa todo azul) o ponto gruda na plataforma azul-escura de baixo e a mancha
    # fica grande demais; so o miolo bem saturado e claro do ponto separa os dois (achou o boneco em 42/42 leituras)
    estrita = (h >= 109) & (h <= 118) & (s > 225) & (v > 150)
    verm = ((h <= 6) | (h >= 172)) & (s > 170) & (v > 150)
    azuis = _pontos_redondos(azul)
    for c in _pontos_redondos(estrita):
        if all(abs(c[0] - a[0]) + abs(c[1] - a[1]) > 2.5 for a in azuis):
            azuis.append(c)
    if not azuis:
        azuis = _pontos_pequenos(azul & (s > 190))
    return sorted(azuis, key=lambda c: -c[2]), _pontos_redondos(verm)


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
        self.azuis.append([(c[0], c[1], c[2] if len(c) > 2 else PONTO_TAMANHO_CHEIO) for c in azuis[:4]])
        del self.azuis[:-self.janela]
        if vermelhos:
            self.boss = tuple(vermelhos[0][:2])

    def _mais_frequente(self, leituras):
        """(ponto, em quantas das leituras ele aparece) - nota = soma do tamanho de cada aparicao (ate
        PONTO_TAMANHO_CHEIO): o ponto do boneco (nucleo 4-20 px) vence riscos/sobras de 2 px que aparecem tanto quanto ele.
        Empate: o visto primeiro."""
        melhor, nota_m, n_m = None, 0.0, 0
        for leit in leituras:
            for p in leit:
                tams = [max((min(q[2], PONTO_TAMANHO_CHEIO) for q in l2 if self._perto(p, q)), default=0) for l2 in leituras]
                nota = float(sum(tams))
                if nota > nota_m + 1e-9:
                    melhor, nota_m, n_m = p, nota, sum(1 for t in tams if t > 0)
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
        return (float(melhor[0]), float(melhor[1])), n_m / len(self.azuis)


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


def boss_morto(f):
    """O retrato do boss (ao lado da barra de vida) fica CINZA quando ele morre. Saturacao medida: vivo 82-218
    (Escorpiao, Dragao, Rainha), morto 6-9."""
    x0, y0, x1, y1 = RETRATO_BOSS
    return float(cv2.cvtColor(f[y0:y1, x0:x1], cv2.COLOR_BGR2HSV)[..., 1].mean()) < SATURACAO_RETRATO_MORTO


def vida_boss(f):
    """Vida do boss em % (0-100): ate onde vai a barra vermelha. Calibrada com 100% -> fim em x=811 e
    42% -> fim em x=761; para decidir se um tiro acertou o que vale e a DIFERENCA entre antes e depois.
    Barra vazia NAO e boss morto: com 1-3% a parte vermelha some (o numero na barra ainda diz "1%") e o Escorpiao
    ainda se cura no turno dele. So devolve 0 com o retrato cinza (morto); vivo com a barra vazia = 1."""
    x0, x1, y0, y1 = VIDA_BOSS
    faixa = f[y0:y1, x0:x1].astype(int)
    b, g, r = faixa[..., 0], faixa[..., 1], faixa[..., 2]
    verm = ((r > 160) & (r - np.maximum(g, b) > 70)).mean(axis=0) > 0.5
    xs = np.where(verm)[0]
    if len(xs) == 0:
        return 0.0 if boss_morto(f) else 1.0
    return float(min(100.0, max(1.0, (xs.max() + 1) / (x1 - x0) * 100)))


def numeros_de_dano(f):
    """Quantos px com a cor dos numeros de dano ha em volta do Chefao Global (0 = nenhum numero)."""
    x0, y0, x1, y1 = NUMEROS_DANO_CAIXA
    hsv = cv2.cvtColor(f[y0:y1, x0:x1], cv2.COLOR_BGR2HSV)
    return int(((hsv[..., 0] <= 32) & (hsv[..., 1] > 170) & (hsv[..., 2] > 190)).sum())


def pow_cheio(f):
    """O medidor do especial (POW, tecla B) encheu? O botao fica vermelho e pulsa."""
    x0, y0, x1, y1 = POW_CENTRO
    return float(cv2.cvtColor(f[y0:y1, x0:x1], cv2.COLOR_BGR2HSV)[..., 1].mean()) >= SATURACAO_POW_CHEIO


# ---- Gato Preto: perks Z/X/C, item E do pet --------------------------------------------------------------------
PERKS_SLOTS = {"Z": (853, 260), "X": (896, 260), "C": (942, 260)}   # "Minhas ferramentas" na SALA (centro de cada quadro)
PERK_COMPRAR = (942, 316)        # perk POW ("Enfurecer", +50% da barra do especial, 120 de vigor) em "Ferramentas a comprar"
BUFF_PET_CAIXA = (438, 498, 472, 532)   # icone VERDE que aparece na barra de itens quando o buff do item E esta ativo
BUFF_PET_MIN = 25                # px verdes (ativo ~81-92; sem o buff 0-2)


def perks_cheios(f):
    """{'Z': bool, 'X': bool, 'C': bool}: o quadro tem um perk (icone vermelho "POW") ou esta vazio (quadrado verde)?"""
    hsv = cv2.cvtColor(f, cv2.COLOR_BGR2HSV)
    out = {}
    for nome, (x, y) in PERKS_SLOTS.items():
        h = hsv[y - 9:y + 9, x - 9:x + 9]
        out[nome] = int((((h[..., 0] <= 8) | (h[..., 0] >= 170)) & (h[..., 1] > 150) & (h[..., 2] > 130)).sum()) >= 30
    return out


def buff_pet(f):
    """O buff do item E (canhao em volta do boneco) esta ativo? So aparece na SUA vez (some durante a animacao do boss)."""
    x0, y0, x1, y1 = BUFF_PET_CAIXA
    h = cv2.cvtColor(f[y0:y1, x0:x1], cv2.COLOR_BGR2HSV)
    return int(((h[..., 0] >= 45) & (h[..., 0] <= 85) & (h[..., 1] > 120) & (h[..., 2] > 110)).sum()) >= BUFF_PET_MIN
