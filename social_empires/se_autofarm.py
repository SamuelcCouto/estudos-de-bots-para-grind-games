# -*- coding: utf-8 -*-
"""
Auto-farm para Social Empires (launcher Electron + Flash).

Funciona "olhando" a janela do jogo (captura via PrintWindow, mesmo coberta por
outras janelas) e enviando cliques direto para a janela (PostMessage), sem mover
o seu mouse. Nada no launcher ou no servidor e modificado.

Ciclo:
  - bolhas "prontas" (bife/ouro/madeira/pedra)  -> clica para colher
  - postos com "zZ"                              -> abre o menu, escolhe a opcao
                                                    de 5 min e confirma SIM (todos)
  - dialogos conhecidos (AVISO, SIM, Ok, X, "Fazer mais tarde") -> trata sozinho
  - jogo em tela pequena                         -> engrenagem -> maximizar -> zoom
  - mapa fora do lugar (zoom/posicao)            -> realinha usando a prefeitura
                                                    como ancora (ou recarrega a pagina)
  - nada acontecendo por muito tempo             -> recarrega a pagina

Prioridade: postos de 5 min (ouro/madeira/pedra/bife dos postos) e o replantio deles vem
antes das plantacoes de 30 s, que gastam a madeira produzida pelos postos.

Teclas no console: P = pausar/continuar, Q = sair (Ctrl+C tambem sai).
"""
import ctypes
import ctypes.wintypes as W
import datetime
import os
import subprocess
import sys
import time

import cv2
import numpy as np

from layout import detectar_viewport, mudou as layout_mudou
from painel import Painel
from recursos import Estatisticas, ler_recursos

# --------------------------------------------------------------------------
# CONFIGURACAO
# --------------------------------------------------------------------------
INTERVALO_VARREDURA = 2.0     # segundos entre varreduras quando nao ha nada pra fazer
PAUSA_ENTRE_CLIQUES = 0.18    # segundos entre cliques de colheita
CLIQUES_POR_CHECAGEM = 4     # recaptura a tela a cada N cliques (seguranca contra dialogos)
OPCAO_PRODUCAO = 1            # 1=5 min, 2=1 h, 3=4 h, 4=8 h (ordem dos cards do menu)
MINUTOS_SEM_ATIVIDADE = 15    # recarrega a pagina se nada for detectado por esse tempo
SEGUNDOS_CHECAR_MAPA = 120    # de quanto em quanto tempo confere se o mapa saiu do lugar
SEGUNDOS_CAMPO = 150          # bolha que volta antes disso no mesmo lugar e plantacao (30 s)
# A prefeitura e a "ancora" para medir zoom e posicao do mapa (1.0 = base inteira na tela).
# O zoom e ajustado pelo controle deslizante do jogo (o scroll do mouse nao funciona com o
# jogo coberto por outra janela).
ESCALA_PADRAO = 1.0
TOLERANCIA_ESCALA = 0.08
TOLERANCIA_POSICAO = 45       # pixels (em 1920x1080)
SALVAR_DEBUG = True           # salva prints em autofarm/debug quando algo da errado

PASTA = os.path.dirname(os.path.abspath(__file__))
PASTA_TPL = os.path.join(PASTA, "templates")
PASTA_DEBUG = os.path.join(PASTA, "debug")

# --------------------------------------------------------------------------
# WIN32
# --------------------------------------------------------------------------
user32 = ctypes.windll.user32
gdi32 = ctypes.windll.gdi32
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)
except Exception:
    user32.SetProcessDPIAware()

WM_MOUSEMOVE, WM_LBUTTONDOWN, WM_LBUTTONUP = 0x0200, 0x0201, 0x0202
MK_LBUTTON = 0x0001
EnumProc = ctypes.WINFUNCTYPE(W.BOOL, W.HWND, W.LPARAM)


class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [("biSize", W.DWORD), ("biWidth", W.LONG), ("biHeight", W.LONG),
                ("biPlanes", W.WORD), ("biBitCount", W.WORD), ("biCompression", W.DWORD),
                ("biSizeImage", W.DWORD), ("biXPelsPerMeter", W.LONG),
                ("biYPelsPerMeter", W.LONG), ("biClrUsed", W.DWORD), ("biClrImportant", W.DWORD)]


PAINEL = None


def log(msg, tela=True):
    """tela=False: so vai para o log de execucao (arquivo), nao polui o console."""
    if PAINEL:
        PAINEL.log(msg, tela)
    elif tela:
        print(f"[{datetime.datetime.now():%H:%M:%S}] {msg}", flush=True)


def pids_do_launcher():
    out = subprocess.run('tasklist /FO CSV /NH /FI "IMAGENAME eq Launcher_Social_Empires.exe"',
                         capture_output=True, text=True, shell=True).stdout
    pids = set()
    for linha in out.splitlines():
        partes = linha.split('","')
        if len(partes) > 1 and partes[1].isdigit():
            pids.add(int(partes[1]))
    return pids


def achar_janela():
    pids = pids_do_launcher()
    achadas = []

    def cb(h, _):
        p = W.DWORD()
        user32.GetWindowThreadProcessId(h, ctypes.byref(p))
        if p.value in pids and user32.IsWindowVisible(h):
            buf = ctypes.create_unicode_buffer(256)
            user32.GetWindowTextW(h, buf, 256)
            if "Social Empires" in buf.value:
                r = W.RECT()
                user32.GetClientRect(h, ctypes.byref(r))
                achadas.append((r.right * r.bottom, h))
        return True

    user32.EnumWindows(EnumProc(cb), 0)
    return max(achadas)[1] if achadas else None


def capturar(hwnd):
    r = W.RECT()
    user32.GetClientRect(hwnd, ctypes.byref(r))
    w, h = r.right, r.bottom
    if w < 200 or h < 200:
        return None
    hdc = user32.GetDC(hwnd)
    mdc = gdi32.CreateCompatibleDC(hdc)
    bmp = gdi32.CreateCompatibleBitmap(hdc, w, h)
    old = gdi32.SelectObject(mdc, bmp)
    try:
        user32.PrintWindow(hwnd, mdc, 2)  # PW_RENDERFULLCONTENT
        bi = BITMAPINFOHEADER(ctypes.sizeof(BITMAPINFOHEADER), w, -h, 1, 32, 0, 0, 0, 0, 0, 0)
        buf = ctypes.create_string_buffer(w * h * 4)
        gdi32.GetDIBits(mdc, bmp, 0, h, buf, ctypes.byref(bi), 0)
        img = np.frombuffer(buf, np.uint8).reshape(h, w, 4)[:, :, :3].copy()  # BGR
    finally:
        gdi32.SelectObject(mdc, old)
        gdi32.DeleteObject(bmp)
        gdi32.DeleteDC(mdc)
        user32.ReleaseDC(hwnd, hdc)
    return img


def _lp(x, y):
    return ((int(y) & 0xFFFF) << 16) | (int(x) & 0xFFFF)


def estacionar_mouse(hwnd):
    # move o cursor "virtual" para a barra do launcher (fora do Flash) para
    # nao deixar tooltips/labels do jogo por cima das bolhas
    user32.PostMessageW(hwnd, WM_MOUSEMOVE, 0, _lp(960, 8))


def clicar(hwnd, x, y):
    user32.PostMessageW(hwnd, WM_MOUSEMOVE, 0, _lp(x, y))
    time.sleep(0.06)
    user32.PostMessageW(hwnd, WM_LBUTTONDOWN, MK_LBUTTON, _lp(x, y))
    time.sleep(0.05)
    user32.PostMessageW(hwnd, WM_LBUTTONUP, 0, _lp(x, y))


def arrastar(hwnd, x0, y0, x1, y1):
    """Arrasta o mapa devagar e segura parado antes de soltar (evita a inercia do jogo)."""
    user32.PostMessageW(hwnd, WM_MOUSEMOVE, 0, _lp(x0, y0))
    time.sleep(0.15)
    user32.PostMessageW(hwnd, WM_LBUTTONDOWN, MK_LBUTTON, _lp(x0, y0))
    time.sleep(0.15)
    n = max(2, int(np.hypot(x1 - x0, y1 - y0) / 5))
    for i in range(1, n + 1):
        user32.PostMessageW(hwnd, WM_MOUSEMOVE, MK_LBUTTON,
                            _lp(x0 + (x1 - x0) * i / n, y0 + (y1 - y0) * i / n))
        time.sleep(0.03)
    for _ in range(8):
        user32.PostMessageW(hwnd, WM_MOUSEMOVE, MK_LBUTTON, _lp(x1, y1))
        time.sleep(0.06)
    user32.PostMessageW(hwnd, WM_LBUTTONUP, 0, _lp(x1, y1))
    time.sleep(0.1)


# --------------------------------------------------------------------------
# VISAO
# --------------------------------------------------------------------------
TEMPLATES = {}


def carregar_templates():
    for nome in os.listdir(PASTA_TPL):
        if nome.endswith(".png"):
            TEMPLATES[nome[:-4]] = cv2.imread(os.path.join(PASTA_TPL, nome), cv2.IMREAD_GRAYSCALE)


def achar(img_gray, nome, escalas=(1.0,), limiar=0.82, todos=False, regiao=None):
    """Template matching. Retorna lista de (score, cx, cy, w, h) no sistema da imagem.

    Templates grandes sao procurados em meia resolucao (bem mais rapido)."""
    tpl0 = TEMPLATES[nome]
    ox, oy = 0, 0
    if regiao:
        x0, y0, x1, y1 = regiao
        img_gray = img_gray[y0:y1, x0:x1]
        ox, oy = x0, y0
    f = 0.5 if min(tpl0.shape) >= 36 else 1.0
    base = img_gray if f == 1.0 else cv2.resize(img_gray, None, fx=f, fy=f, interpolation=cv2.INTER_AREA)
    res_total = []
    for s in escalas:
        k = s * f
        tpl = tpl0 if k == 1.0 else cv2.resize(tpl0, None, fx=k, fy=k,
                                               interpolation=cv2.INTER_AREA if k < 1 else cv2.INTER_LINEAR)
        th, tw = tpl.shape
        if th >= base.shape[0] or tw >= base.shape[1] or th < 8:
            continue
        res = cv2.matchTemplate(base, tpl, cv2.TM_CCOEFF_NORMED)
        if todos:
            ys, xs = np.where(res >= limiar)
            for y, x in zip(ys, xs):
                res_total.append((float(res[y, x]), ox + int((x + tw / 2) / f), oy + int((y + th / 2) / f),
                                  int(tw / f), int(th / f)))
        else:
            _, mx, _, loc = cv2.minMaxLoc(res)
            if mx >= limiar:
                res_total.append((float(mx), ox + int((loc[0] + tw / 2) / f), oy + int((loc[1] + th / 2) / f),
                                  int(tw / f), int(th / f)))
    if not res_total:
        return []
    res_total.sort(key=lambda t: -t[0])
    if not todos:
        return res_total[:1]
    # supressao de nao-maximos simples
    final = []
    for r in res_total:
        if all(abs(r[1] - f[1]) > f[3] // 2 or abs(r[2] - f[2]) > f[4] // 2 for f in final):
            final.append(r)
    return final


ESCALAS_UI = (0.9, 1.0, 1.1)
ESCALAS_AMPLAS = tuple(round(0.5 + 0.05 * i, 2) for i in range(23))  # 0.5 .. 1.6


def zonas_proibidas(h, w, vp=None):
    """Areas onde nunca clicamos em 'bolhas'.

    O HUD e proporcional a 1920x1080 dentro do viewport (area do jogo, sem chat/paineis);
    tudo fora do viewport (chat do admin etc.) tambem e proibido."""
    x0, y0, x1, y1 = vp or (0, 0, w, h)
    vw, vh = x1 - x0, y1 - y0
    sx, sy = vw / 1920, vh / 1080
    zonas = [
        (x0, y0, x1, y0 + int(200 * sy)),                          # topo (recursos, xp, launcher)
        (x0, y0, x0 + int(150 * sx), y1),                          # icones da esquerda
        (x1 - int(130 * sx), y0, x1, y1),                          # icones da direita
        (x0 + int(440 * sx), y1 - int(250 * sy), x0 + int(1560 * sx), y1),  # barra de amigos/BUILD/painel de unidade
        (x0 + int(490 * sx), y0 + int(745 * sy), x0 + int(615 * sx), y0 + int(880 * sy)),  # Cast Spell / Open Book
        (x0 + int(600 * sx), y0 + int(825 * sy), x0 + int(665 * sx), y0 + int(885 * sy)),  # contador do livro
        (x0 + int(445 * sx), y0 + int(385 * sy), x0 + int(590 * sx), y0 + int(665 * sy)),  # capacete, coroa e METAS
        (x0 + int(1180 * sx), y0 + int(820 * sy), x0 + int(1420 * sx), y0 + int(940 * sy)),  # inimigos vivos
    ]
    if x0 > 0:
        zonas.append((0, 0, x0, h))        # painel a esquerda
    if x1 < w:
        zonas.append((x1, 0, w, h))        # painel a direita (chat)
    return zonas


def em_zona_proibida(x, y, zonas):
    return any(x0 <= x < x1 and y0 <= y < y1 for x0, y0, x1, y1 in zonas)


def detectar_bolhas(img, vp=None):
    """Retorna (prontas, dormindo): listas de (cx, cy, w, h)."""
    h, w = img.shape[:2]
    mn = img.min(axis=2)
    branco = (mn >= 225).astype(np.uint8)
    fechado = cv2.morphologyEx(branco, cv2.MORPH_CLOSE, np.ones((9, 9), np.uint8))
    n, _, st, _ = cv2.connectedComponentsWithStats(fechado, 8)
    zonas = zonas_proibidas(h, w, vp)
    prontas, dormindo = [], []
    def medidas(x, y, bw, bh):
        m = max(2, bw // 7)
        dentro = img[y + m:y + bh - m, x + m:x + bw - m].astype(np.int16)
        if dentro.size == 0:
            return None
        dmn, dmx = dentro.min(axis=2), dentro.max(axis=2)
        return ((dmn >= 215).mean(),                                         # branco
                (dmx < 70).mean(),                                           # escuro
                ((dmx - dmn) > 60).mean(),                                   # colorido
                (((dmx - dmn) < 30) & (dmx >= 90) & (dmx < 210)).mean())     # cinza (pedra)

    def eh_pronta(f):
        f_branco, f_escuro, f_cor, f_cinza = f
        if not (0.12 <= f_branco <= 0.55 and f_escuro < 0.15):
            return False
        # colorido = bife/ouro/madeira; cinza = pedra (fica entre ~0.35 e 0.6 conforme o zoom)
        return f_cor >= 0.3 or (f_cinza >= 0.25 and f_branco >= 0.25 and f_cor < 0.1)

    for i in range(1, n):
        x, y, bw, bh, _ = st[i]
        if not (14 <= bw <= 40):
            continue
        cx, cy = x + bw // 2, y + bh // 2
        if em_zona_proibida(cx, cy, zonas):
            continue
        f = medidas(x, y, bw, bh)
        if f is None:
            continue
        proporcao = bh / bw
        # bolha de verdade tem a borda de cima toda branca (descarta torres/bandeiras)
        topo = (mn[y + 1:y + 3, x + 3:x + bw - 3] >= 215).mean()
        if 0.8 <= proporcao <= 1.4 and topo >= 0.8 and eh_pronta(f):
            prontas.append((cx, cy, bw, bh))
        elif 1.4 < proporcao <= 2.1 and f[0] >= 0.45 and f[1] >= 0.02 and f[2] < 0.15:
            dormindo.append((cx, cy, bw, bh))
        elif proporcao > 1.4 and topo >= 0.8:
            # bolha "grudada" em algo branco logo abaixo (telhado etc.): avalia so o quadrado de cima
            qh = int(bw * 1.05)
            fq = medidas(x, y, bw, qh)
            if fq is not None and eh_pronta(fq):
                prontas.append((cx, y + qh // 2, bw, qh))
    return prontas, dormindo


ICONES = ("icone_bife", "icone_ouro", "icone_madeira", "icone_pedra")
ESCALA_REF_ICONES = 0.99  # zoom (escala da ancora) em que os templates de icone foram recortados


def detectar_icones(img, escala_ancora=None, vp=None):
    """Acha bolhas prontas pelo icone dentro delas (bife/ouro/madeira/pedra).

    Pega tambem as bolhas encostadas em outras coisas brancas (luva do zZ, telhados),
    que a analise de manchas brancas perde. Retorna lista de (cx, cy, w, h)."""
    h, w = img.shape[:2]
    zonas = zonas_proibidas(h, w, vp)
    g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    mn = img.min(axis=2)
    if escala_ancora:
        base = escala_ancora / ESCALA_REF_ICONES
        fatores = (base * 0.93, base, base * 1.07)
    else:
        fatores = tuple(round(0.7 + 0.07 * i, 2) for i in range(14))  # 0.7 .. 1.6
    achados = []
    for nome in ICONES:
        for f in fatores:
            tpl = cv2.resize(TEMPLATES[nome], None, fx=f, fy=f, interpolation=cv2.INTER_LINEAR)
            th, tw = tpl.shape
            res = cv2.matchTemplate(g, tpl, cv2.TM_CCOEFF_NORMED)
            ys, xs = np.where(res >= 0.75)
            for y, x in zip(ys, xs):
                achados.append((float(res[y, x]), x + tw // 2, y + th // 2, tw))
    achados.sort(key=lambda a: -a[0])
    final = []
    for sc, cx, cy, tw in achados:
        if any(abs(cx - f[0]) < tw * 0.8 and abs(cy - f[1]) < tw * 0.8 for f in final):
            continue
        if em_zona_proibida(cx, cy, zonas):
            continue
        # o icone tem que estar dentro de uma moldura branca (descarta fontes, telhados etc.)
        r0, r1 = tw // 2 + 1, tw // 2 + 4
        if cy - r1 < 0 or cx - r1 < 0 or cy + r1 >= h or cx + r1 >= w:
            continue
        caixa = mn[cy - r1:cy + r1, cx - r1:cx + r1] >= 215
        anel = np.ones_like(caixa)
        anel[r1 - r0:r1 + r0, r1 - r0:r1 + r0] = False
        anel[2 * r1 - 3:, :] = False  # ignora a base (rabinho da bolha / vizinho)
        if caixa[anel].mean() < 0.6:
            continue
        lado = int(tw * 25 / 19)
        final.append((cx, cy, lado, lado))
    return final


def juntar_prontas(*listas):
    final = []
    for lista in listas:
        for b in lista:
            if all(abs(b[0] - f[0]) > 12 or abs(b[1] - f[1]) > 12 for f in final):
                final.append(b)
    return final


def tipo_do_icone(img, b):
    """'bife', 'ouro', 'madeira' ou 'pedra' pela cor do icone dentro da bolha."""
    cx, cy, bw, _ = (int(v) for v in b)
    m = max(3, bw // 6)
    dentro = img[cy - bw // 2 + m:cy + bw // 2 - m, cx - bw // 2 + m:cx + bw // 2 - m]
    if dentro.size == 0:
        return "bife"
    hsv = cv2.cvtColor(dentro, cv2.COLOR_BGR2HSV)
    cor = hsv[..., 1] > 90
    if cor.mean() < 0.08:
        return "pedra"
    matiz = float(np.median(hsv[..., 0][cor]))
    if matiz < 8 or matiz > 165:
        return "bife"
    return "ouro" if matiz >= 20 else "madeira"


ESCALAS_ZZ = tuple(round(0.8 + 0.05 * i, 2) for i in range(11))  # 0.8 .. 1.3


def completar_dormindo(img, dormindo, vp=None):
    """Acha caixinhas 'zZ' por template (pega icones grudados que a analise de blobs perde)."""
    h, w = img.shape[:2]
    zonas = zonas_proibidas(h, w, vp)
    g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    final = list(dormindo)
    for _, cx, cy, tw, th in achar(g, "zz", ESCALAS_ZZ, 0.8, todos=True):
        if em_zona_proibida(cx, cy, zonas):
            continue
        s = tw / TEMPLATES["zz"].shape[1]
        bw, bh = int(27 * s), int(43 * s)        # tamanho do icone inteiro (luva + caixa)
        icy = int(cy + th / 2 + 3 * s - bh / 2)  # centro do icone inteiro
        if all(abs(cx - d[0]) > 12 or abs(icy - d[1]) > 15 for d in final):
            final.append((cx, icy, bw, bh))
    return final


ESCALAS_ANCORA = tuple(round(0.4 * 1.04 ** k, 3) for k in range(49))  # 0.4 .. 2.6


def localizar_ancora(img):
    """Acha a prefeitura. Retorna (x, y, escala) ou None (escala 1.0 = zoom padrao)."""
    g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    r = achar(g, "ancora", ESCALAS_ANCORA, 0.8)
    if not r:
        return None
    _, x, y, tw, _ = r[0]
    return x, y, tw / TEMPLATES["ancora"].shape[1]


def ponto_de_grama(img, dx, dy, vp=None):
    """Ponto de inicio de arrasto em grama lisa (nao pega construcao), com o fim fora do HUD."""
    h, w = img.shape[:2]
    x0, _, x1, _ = vp or (0, 0, w, h)
    zonas = zonas_proibidas(h, w, vp)
    b, g, r = (img[:, :, i].astype(np.int16) for i in range(3))
    grama = ((g - np.maximum(r, b)) > 25).astype(np.uint8)
    melhor = None
    for y in range(int(h * 0.22), int(h * 0.82), 40):
        for x in range(x0 + int((x1 - x0) * 0.1), x0 + int((x1 - x0) * 0.9), 40):
            ex, ey = x + dx, y + dy
            if not (x0 + 40 <= ex < x1 - 40 and 40 <= ey < h - 40):
                continue
            if em_zona_proibida(x, y, zonas) or em_zona_proibida(ex, ey, zonas):
                continue
            # area grande: um arrasto que "nao pega" vira clique, e placas "A VENDA" na grama
            # abrem a Casa de Leiloes
            patch = grama[max(0, y - 35):y + 36, max(0, x - 35):x + 36]
            frac = patch.mean()
            if frac > 0.98 and (melhor is None or frac > melhor[0]):
                melhor = (frac, x, y)
    return (melhor[1], melhor[2]) if melhor else None


def brilho(img, vp=None):
    """Brilho medio da area do jogo (o chat nao pode contar: ele muda a media da janela)."""
    if vp:
        img = img[vp[1]:vp[3], vp[0]:vp[2]]
    return img.mean()


def tela_escurecida(img, referencia, vp=None):
    return referencia is not None and brilho(img, vp) < referencia * 0.7


def modo_tela_pequena(img):
    h, w = img.shape[:2]
    faixa = img[int(h * 0.3):int(h * 0.8), int(w * 0.02):int(w * 0.18)]
    b, g = faixa[:, :, 0].mean(), faixa[:, :, 1].mean()
    return g < 60 and b > g + 5 and faixa.std() < 25  # fundo azul-escuro do site


def salvar_debug(img, nome):
    if not SALVAR_DEBUG:
        return
    os.makedirs(PASTA_DEBUG, exist_ok=True)
    arquivos = sorted(os.listdir(PASTA_DEBUG))
    for antigo in arquivos[:-30]:
        try:
            os.remove(os.path.join(PASTA_DEBUG, antigo))
        except OSError:
            pass
    cv2.imwrite(os.path.join(PASTA_DEBUG, f"{datetime.datetime.now():%Y%m%d_%H%M%S}_{nome}.png"), img)


# --------------------------------------------------------------------------
# BOT
# --------------------------------------------------------------------------
class Bot:
    def __init__(self):
        self.hwnd = None
        self.brilho_normal = None
        self.ultima_atividade = time.time()
        self.colhidos = 0
        self.replantios = 0
        # offsets (dx, dy) em unidades de largura do icone zZ, testados em ordem;
        # o que funcionar sobe para o topo da lista
        self.offsets_posto = [(0, 1.3), (0, 1.9), (-1.2, 1.9), (1.2, 1.9), (-2.0, 2.4), (0, 2.6)]
        self.precisa_zoom = False
        self.tam_janela = None
        self.vp = None           # (x0, y0, x1, y1) da area do jogo, sem chat/paineis do admin
        self._vp_novo = None     # layout candidato (precisa aparecer 2x seguidas para valer)
        self.ultimo_layout = 0.0
        self.ref_ancora = None   # onde a prefeitura fica com a base centralizada (nesta sessao)
        self.escala = None       # zoom atual medido pela ancora
        self.branca_desde = None
        self.estat = Estatisticas()
        # (x, y, hora) de cada colheita: o que volta a ficar pronto em menos de
        # SEGUNDOS_CAMPO e plantacao de 30 s; o resto (bolhas novas ou de 5 min) e posto
        self.colheitas_pos = []

    # ---------- utilidades ----------
    def cap(self):
        if not self.hwnd or not user32.IsWindow(self.hwnd):
            self.hwnd = achar_janela()
            if not self.hwnd:
                return None
            log(f"Janela do jogo encontrada (hwnd={self.hwnd}).")
        if user32.IsIconic(self.hwnd):
            # minimizado o Windows nao desenha a janela: restaura sem roubar o foco
            log("Launcher minimizado -> restaurando (sem tirar o foco da sua janela).")
            user32.ShowWindow(self.hwnd, 4)  # SW_SHOWNOACTIVATE
            time.sleep(2)
        img = capturar(self.hwnd)
        if img is not None and img.mean() > 250:  # janela nao renderizada (branca)
            if self.branca_desde is None:
                self.branca_desde = time.time()
            elif time.time() - self.branca_desde > 90:
                log("Janela branca ha 90 s -> tentando recarregar (Ctrl+R).")
                self.branca_desde = time.time()
                user32.PostMessageW(self.hwnd, 0x0100, 0x11, 0)            # Ctrl down
                user32.PostMessageW(self.hwnd, 0x0100, 0x52, 0x00130001)   # R
                user32.PostMessageW(self.hwnd, 0x0101, 0x52, 0xC0130001)
                user32.PostMessageW(self.hwnd, 0x0101, 0x11, 0xC0000001)
                self.precisa_zoom = True
            return None
        self.branca_desde = None
        return img

    def clicar(self, x, y):
        self.esperar_pausa()
        if self.vp and not (self.vp[0] <= x < self.vp[2]):
            log(f"Clique ignorado em ({int(x)},{int(y)}): fora da area do jogo {self.vp}.", tela=False)
            return
        clicar(self.hwnd, x, y)

    # ---------- layout (chat e paineis do admin) ----------
    @property
    def escala_alvo(self):
        """Zoom desejado. Com um painel lateral o jogo ocupa menos tela: a base tem que caber."""
        if not self.vp or not self.tam_janela:
            return ESCALA_PADRAO
        w, h = self.tam_janela
        return ESCALA_PADRAO * min(1.0, (self.vp[2] - self.vp[0]) / w, (self.vp[3] - self.vp[1]) / h)

    def largura_jogo(self, img):
        return (self.vp[2] - self.vp[0]) if self.vp else img.shape[1]

    def atualizar_layout(self, img):
        """Mede a area do jogo a cada captura. Retorna True se o layout mudou (chat abriu,
        fechou, mudou de tamanho...): a base foi para outro lugar, entao tudo e remedido."""
        h, w = img.shape[:2]
        self.tam_janela = (w, h)
        novo = detectar_viewport(img)
        if self.vp is None:
            self.vp = novo
            log(f"Area do jogo: {novo[2] - novo[0]}x{novo[3] - novo[1]} (janela {w}x{h}).", tela=False)
            return False
        if not layout_mudou(novo, self.vp):
            self._vp_novo = None
            return False
        # confirma em duas leituras seguidas (um quadro de transicao nao conta)
        if self._vp_novo is None or layout_mudou(novo, self._vp_novo):
            self._vp_novo = novo
            return False
        antigo, self.vp, self._vp_novo = self.vp, novo, None
        log(f"Layout mudou (chat/painel do jogo?): area {antigo} -> {novo}. Recentralizando a base.")
        salvar_debug(img, "layout_mudou")
        self.ref_ancora = None
        self.precisa_zoom = True
        self.colheitas_pos.clear()
        return True

    def esperar_pausa(self):
        while PAINEL and PAINEL.pausado.is_set() and not PAINEL.sair:
            time.sleep(0.3)

    def eh_posto(self, img, b):
        if tipo_do_icone(img, b) != "bife":
            return True  # ouro, madeira e pedra so saem dos postos
        agora = time.time()
        return not any(abs(b[0] - x) < 12 and abs(b[1] - y) < 12 and agora - t < SEGUNDOS_CAMPO
                       for x, y, t in self.colheitas_pos)

    # ---------- dialogos ----------
    def tratar_dialogos(self, img):
        """Retorna True se clicou em algo (estado mudou)."""
        g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        r = achar(g, "fazer_mais_tarde", ESCALAS_AMPLAS, 0.8, regiao=self.vp)
        if r:
            log("Tela inicial do launcher -> 'Fazer mais tarde'.")
            self.clicar(r[0][1], r[0][2])
            self.precisa_zoom = True
            time.sleep(8)
            return True

        if achar(g, "coletar_titulo", ESCALAS_UI, 0.75, regiao=self.vp):
            return self.escolher_producao(g)

        r = achar(g, "sim", ESCALAS_AMPLAS, 0.8, regiao=self.vp)
        if r:
            log("Dialogo com SIM -> SIM.")
            self.clicar(r[0][1], r[0][2])
            time.sleep(1.2)
            return True

        if achar(g, "aviso_titulo", ESCALAS_AMPLAS, 0.8, regiao=self.vp):
            r = achar(g, "aviso_x", ESCALAS_AMPLAS, 0.75, regiao=self.vp) or achar(g, "fechar_x", ESCALAS_AMPLAS, 0.75, regiao=self.vp)
            if r:
                log("AVISO -> fechar.")
                self.clicar(r[0][1], r[0][2])
                time.sleep(1.2)
                return True

        r = achar(g, "ok", ESCALAS_AMPLAS, 0.8, regiao=self.vp)
        if r:
            log("Dialogo com Ok -> Ok.")
            self.clicar(r[0][1], r[0][2])
            time.sleep(1.2)
            return True

        # X vermelho generico (somente se a tela estiver escurecida = dialogo aberto),
        # ex.: subida de nivel -> fecha no X (nunca clica em "Compartilhe!")
        escura = tela_escurecida(img, self.brilho_normal, self.vp) if self.brilho_normal \
            else brilho(img, self.vp) < 75
        if escura:
            r = achar(g, "fechar_x", ESCALAS_AMPLAS, 0.8, regiao=self.vp) or achar(g, "aviso_x", ESCALAS_AMPLAS, 0.8, regiao=self.vp)
            if r:
                log("Janela com X (ex.: subida de nivel) -> fechar.")
                salvar_debug(img, "dialogo_desconhecido")
                self.clicar(r[0][1], r[0][2])
                time.sleep(1.2)
                return True
        return False

    def fechar_janela_x(self, img):
        """Fecha qualquer janela do jogo com o X vermelho (ex.: Casa de Leiloes aberta sem querer)."""
        g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        r = achar(g, "fechar_x", ESCALAS_AMPLAS, 0.85, regiao=self.vp) or achar(g, "aviso_x", ESCALAS_AMPLAS, 0.85, regiao=self.vp)
        if not r:
            return False
        log("Janela aberta por engano -> fechar (X).")
        self.clicar(r[0][1], r[0][2])
        estacionar_mouse(self.hwnd)
        time.sleep(1.2)
        return True

    def escolher_producao(self, g):
        botoes = achar(g, "selecionar", ESCALAS_UI, 0.75, todos=True, regiao=self.vp)
        if len(botoes) < 4:
            log(f"Menu de coleta aberto mas so achei {len(botoes)} botoes SELECIONAR.")
            if not botoes:
                return False
        # ordena por linha (y) e depois coluna (x)
        linha_y = sorted(b[2] for b in botoes)
        meio = (linha_y[0] + linha_y[-1]) / 2
        ordenados = sorted(botoes, key=lambda b: (b[2] > meio + 5, b[1]))
        idx = min(OPCAO_PRODUCAO, len(ordenados)) - 1
        b = ordenados[idx]
        self.clicar(b[1], b[2])
        time.sleep(1.5)
        # confirma "colocar todas para trabalhar"
        for _ in range(3):
            img = self.cap()
            if img is None:
                break
            r = achar(cv2.cvtColor(img, cv2.COLOR_BGR2GRAY), "sim", ESCALAS_UI, 0.8, regiao=self.vp)
            if r:
                self.clicar(r[0][1], r[0][2])
                time.sleep(1.5)
                break
            time.sleep(0.8)
        self.replantios += 1
        self.estat.replantios += 1
        self.ultima_atividade = time.time()
        log(f"Producao iniciada (opcao {OPCAO_PRODUCAO}) para todos os postos do tipo. "
            f"[replantios: {self.replantios}]")
        estacionar_mouse(self.hwnd)
        return True

    # ---------- tela cheia + zoom ----------
    def entrar_tela_cheia(self, img):
        h, w = img.shape[:2]
        user32.PostMessageW(self.hwnd, WM_MOUSEMOVE, 0, _lp(w // 2, h // 2))
        time.sleep(1.0)
        img = self.cap()
        if img is None:
            return False
        g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        r = achar(g, "engrenagem", ESCALAS_AMPLAS, 0.75, regiao=(w // 2, 0, w, h))
        if not r:
            return False
        log("Jogo em tela pequena -> engrenagem -> maximizar.")
        self.clicar(r[0][1], r[0][2])
        time.sleep(2.5)
        img = self.cap()
        if img is None:
            return False
        g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        r = achar(g, "maximizar", ESCALAS_AMPLAS, 0.75, regiao=(w // 2, 0, w, h))
        if not r:
            salvar_debug(img, "sem_maximizar")
            return False
        self.clicar(r[0][1], r[0][2])
        time.sleep(3)
        self.precisa_zoom = True
        return True

    def ajustar_zoom(self):
        img = self.cap()
        if img is None:
            return
        log("Ajustando zoom e posicao do mapa.")
        self.precisa_zoom = False
        if not self.realinhar():
            self.recarregar_pagina(img, "nao consegui alinhar o mapa")

    def mapa_alinhado(self, img):
        a = localizar_ancora(img)
        if a is None or self.ref_ancora is None:
            return False
        h, w = img.shape[:2]
        x, y, s = a
        self.escala = s
        tx, ty = self.ref_ancora
        return abs(s - self.escala_alvo) <= TOLERANCIA_ESCALA and \
            np.hypot(tx - x, ty - y) <= TOLERANCIA_POSICAO * self.largura_jogo(img) / 1920

    def nuvem_bolhas(self, img):
        """Centros de todas as bolhas (prontas e zZ) - mostram onde a base esta na tela."""
        prontas, dormindo = detectar_bolhas(img, self.vp)
        prontas = juntar_prontas(prontas, detectar_icones(img, self.escala, self.vp))
        return prontas + completar_dormindo(img, dormindo, self.vp)

    def arrastar_mapa(self, img, dx, dy):
        self.colheitas_pos.clear()  # posicoes na tela mudaram: reaprende quem e plantacao
        dist = np.hypot(dx, dy)
        f = min(1.0, 250 / dist)  # arrasta no maximo 250 px por vez
        dx, dy = int(dx * f), int(dy * f)
        p = ponto_de_grama(img, dx, dy, self.vp)
        if p is None:
            salvar_debug(img, "sem_grama_para_arrastar")
            return False
        arrastar(self.hwnd, p[0], p[1], p[0] + dx, p[1] + dy)
        estacionar_mouse(self.hwnd)
        time.sleep(1.5)
        return True

    def desvio_da_base(self, img, bolhas):
        """Quanto falta arrastar para o centro da base ficar no centro da area livre da tela."""
        h, w = img.shape[:2]
        xs = [b[0] for b in bolhas]
        ys = [b[1] for b in bolhas]
        cx = (np.percentile(xs, 3) + np.percentile(xs, 97)) / 2
        cy = (np.percentile(ys, 3) + np.percentile(ys, 97)) / 2
        x0, y0, x1, y1 = self.vp or (0, 0, w, h)
        return x0 + (x1 - x0) * 970 / 1920 - cx, y0 + (y1 - y0) * 515 / 1080 - cy

    def botoes_zoom(self):
        """Posicao dos botoes de zoom do jogo: (x, y_mais, y_menos) ou None."""
        img = self.cap()
        if img is None:
            return None
        h, w = img.shape[:2]
        w = self.vp[2] if self.vp else w  # a borda direita do JOGO (nao da janela, se ha chat)
        # os botoes da direita so aparecem com o mouse por perto
        user32.PostMessageW(self.hwnd, WM_MOUSEMOVE, 0, _lp(w - 40, int(h * 0.65)))
        time.sleep(1.0)
        img = self.cap()
        if img is None:
            return None
        g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        mais = achar(g, "zoom_mais", ESCALAS_UI, 0.8, regiao=(w - 260, int(h * 0.25), w, h))
        if not mais:
            salvar_debug(img, "sem_botoes_zoom")
            return None
        # o "-" e meio transparente (o mapa atras atrapalha o template); fica 208 px abaixo do "+"
        return mais[0][1], mais[0][2], mais[0][2] + int(208 * h / 1080)

    def zoom_minimo(self, b):
        for _ in range(8):
            self.clicar(b[0], b[2])
            time.sleep(0.5)
        estacionar_mouse(self.hwnd)
        time.sleep(1.5)

    def zoom_pelos_botoes(self, b):
        """'-' ate o minimo e '+' uma vez: sempre da ~1.2 (o '+' aproxima em torno do centro)."""
        self.zoom_minimo(b)
        user32.PostMessageW(self.hwnd, WM_MOUSEMOVE, 0, _lp(b[0], b[1] + 150))
        time.sleep(0.5)
        self.clicar(b[0], b[1])
        time.sleep(0.4)
        estacionar_mouse(self.hwnd)
        time.sleep(1.8)

    def pino_do_zoom(self, b):
        """Altura (y) do pino do controle deslizante de zoom, entre o '+' e o '-'."""
        x, y0, y1 = b[0], b[1] + 18, b[2] - 12
        user32.PostMessageW(self.hwnd, WM_MOUSEMOVE, 0, _lp(x, (y0 + y1) // 2))
        time.sleep(0.8)
        img = capturar(self.hwnd)
        if img is None:
            return None
        faixa = img[y0:y1, x - 7:x + 7]
        claras = np.where((faixa.min(axis=2) > 170).mean(axis=1) > 0.6)[0]
        return int(np.median(claras)) + y0 if len(claras) else None

    def zoom_padrao(self):
        """Leva o zoom a ESCALA_PADRAO arrastando o pino do controle deslizante do jogo
        (continuo), medindo pela prefeitura a cada passo. Os botoes +/- so dao saltos grandes."""
        b = self.botoes_zoom()
        if not b:
            return False
        usou_botoes = False
        for _ in range(10):
            img = self.cap()
            if img is None:
                return False
            a = localizar_ancora(img)
            if a is None:
                if usou_botoes:
                    return False
                usou_botoes = True
                self.zoom_pelos_botoes(b)
                continue
            s = a[2]
            self.escala = s
            if abs(s - self.escala_alvo) <= TOLERANCIA_ESCALA:
                return True
            pino = self.pino_do_zoom(b)
            if pino is None:
                return False
            # ~56 px de pino por unidade de log(zoom); arrastos curtos (<14 px) o jogo ignora
            # ou trata como clique na trilha, entao o passo minimo e 14 px
            d = int(round(56 * np.log(s / self.escala_alvo)))
            d = (1 if s > self.escala_alvo else -1) * max(14, min(60, abs(d)))
            arrastar(self.hwnd, b[0], pino, b[0], pino + d)
            estacionar_mouse(self.hwnd)
            time.sleep(1.8)
        return False

    def procurar_de_longe(self):
        """Mapa perdido (so grama na tela): afasta o zoom ao maximo, acha a prefeitura,
        traz para o meio da tela e volta ao zoom padrao (o '+' aproxima em torno do centro)."""
        b = self.botoes_zoom()
        if not b:
            return False
        log("  mapa perdido -> procurando a base com o zoom minimo.")
        self.zoom_minimo(b)
        time.sleep(0.5)
        for _ in range(8):
            img = self.cap()
            if img is None:
                return False
            h, w = img.shape[:2]
            a = localizar_ancora(img)
            if a is None:
                salvar_debug(img, "nem_de_longe")
                return False
            x0, y0, x1, y1 = self.vp or (0, 0, w, h)
            dx, dy = (x0 + x1) / 2 - a[0], (y0 + y1) / 2 - a[1]
            if np.hypot(dx, dy) < 30:
                break
            if not self.arrastar_mapa(img, dx, dy):
                return False
        return self.zoom_padrao()

    def realinhar(self):
        """Corrige o zoom (botoes do jogo) e a posicao (arrasto), medindo de novo a cada passo.

        Na primeira vez da sessao centraliza a base pelas bolhas e memoriza onde a prefeitura
        ficou (funciona com qualquer layout); depois e so levar a prefeitura de volta ate la."""
        sem_ancora = 0
        poucas_bolhas = 0
        zooms = 0
        de_longe = False
        for _ in range(24):
            img = self.cap()
            if img is None:
                return False
            h, w = img.shape[:2]
            tol = TOLERANCIA_POSICAO * self.largura_jogo(img) / 1920
            a = localizar_ancora(img)
            if a is None and (self.tratar_dialogos(img) or self.fechar_janela_x(img)):
                continue  # dialogo/janela cobrindo a prefeitura
            if a is None:
                sem_ancora += 1
                if sem_ancora > 6:
                    salvar_debug(img, "ancora_sumiu")
                    return False
                if zooms == 0:
                    zooms += 1
                    if self.zoom_padrao():
                        continue
                # a prefeitura nao esta na tela: puxa a base (bolhas) para o meio
                bolhas = self.nuvem_bolhas(img)
                if len(bolhas) >= 5:
                    dx, dy = self.desvio_da_base(img, bolhas)
                    if np.hypot(dx, dy) > 60 and self.arrastar_mapa(img, dx, dy):
                        continue
                elif not de_longe:
                    de_longe = True
                    if self.procurar_de_longe():
                        continue
                time.sleep(2.0)
                continue
            x, y, s = a
            self.escala = s
            log(f"  ancora em ({x},{y}) zoom {s:.2f}")
            if abs(s - self.escala_alvo) > TOLERANCIA_ESCALA:
                zooms += 1
                if zooms > 3 or not self.zoom_padrao():
                    return False
                continue
            if self.ref_ancora is None:
                bolhas = self.nuvem_bolhas(img)
                if len(bolhas) < 10:
                    poucas_bolhas += 1
                    if poucas_bolhas > 8:
                        return False
                    time.sleep(5)  # espera as plantacoes ficarem prontas para enxergar a base
                    continue
                dx, dy = self.desvio_da_base(img, bolhas)
                if np.hypot(dx, dy) > tol:
                    if not self.arrastar_mapa(img, dx, dy):
                        return False
                    continue
                self.ref_ancora = (x, y)
                self.brilho_normal = brilho(img, self.vp)
                log(f"Base centralizada; posicao de referencia memorizada ({x},{y}).")
                return True
            dx, dy = self.ref_ancora[0] - x, self.ref_ancora[1] - y
            if np.hypot(dx, dy) <= tol:
                self.brilho_normal = brilho(img, self.vp)
                log("Mapa alinhado.")
                return True
            if not self.arrastar_mapa(img, dx, dy):
                return False
        return False

    def recarregar_pagina(self, img, motivo=None):
        motivo = motivo or f"sem atividade ha {MINUTOS_SEM_ATIVIDADE} min"
        g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        r = achar(g, "recarregar", ESCALAS_AMPLAS, 0.75, regiao=(0, 0, img.shape[1] // 3, 60))
        if r:
            log(f"{motivo.capitalize()} -> recarregando a pagina.")
            salvar_debug(img, "recarregar")
            self.clicar(r[0][1], r[0][2])
            self.precisa_zoom = True
            time.sleep(25)
        else:
            log("Sem atividade e nao achei o botao de recarregar.")
            salvar_debug(img, "sem_recarregar")
        self.ultima_atividade = time.time()

    # ---------- colheita / replantio ----------
    def colher(self, prontas, tipo):
        prontas = sorted(prontas, key=lambda b: (b[1], b[0]))
        n = 0
        for i, (cx, cy, bw, bh) in enumerate(prontas):
            if i and i % CLIQUES_POR_CHECAGEM == 0:
                estacionar_mouse(self.hwnd)
                time.sleep(0.15)
                img = self.cap()
                if img is None or tela_escurecida(img, self.brilho_normal, self.vp):
                    log("Algo abriu durante a colheita; pausando a rodada.")
                    break
                if self.vp and layout_mudou(detectar_viewport(img), self.vp):
                    log("O layout do jogo mudou durante a colheita (chat?); pausando a rodada.")
                    break
            self.clicar(cx, cy - bh * 0.05)
            self.colheitas_pos.append((cx, cy, time.time()))
            n += 1
            time.sleep(PAUSA_ENTRE_CLIQUES)
        estacionar_mouse(self.hwnd)
        agora = time.time()
        self.colheitas_pos = [c for c in self.colheitas_pos if agora - c[2] < SEGUNDOS_CAMPO]
        self.colhidos += n
        self.estat.colheitas += n
        self.ultima_atividade = agora
        log(f"Colhidos {n} {tipo} (total {self.colhidos}).", tela=False)

    def replantar(self, dormindo):
        """Abre o menu de um posto 'zZ' clicando no corpo do posto (abaixo do icone)."""
        tentativas = 0
        agora = time.time()
        # postos que falharam ha pouco vao para o fim da fila (pode ser um que esta tampado)
        falhos = getattr(self, "zz_falhos", {})
        self.zz_falhos = {k: t for k, t in falhos.items() if agora - t < 600}
        chave = lambda b: (int(b[0]) // 25, int(b[1]) // 25)
        fila = sorted(dormindo, key=lambda b: (chave(b) in self.zz_falhos, b[1], b[0]))
        for cx, cy, bw, bh in fila[:4]:
            self.zz_falhos[chave((cx, cy))] = agora
            for dx, dy in list(self.offsets_posto)[:4]:
                if tentativas >= 10:
                    return False
                tentativas += 1
                x, y = int(cx + dx * bw), int(cy + bh / 2 + dy * bw)
                img = self.cap()
                if img is None:
                    return False
                h, w = img.shape[:2]
                if em_zona_proibida(x, y, zonas_proibidas(h, w, self.vp)):
                    continue
                self.clicar(x, y)
                estacionar_mouse(self.hwnd)
                time.sleep(1.4)
                img = self.cap()
                if img is None:
                    return False
                g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
                if achar(g, "coletar_titulo", ESCALAS_UI, 0.75):
                    self.offsets_posto.remove((dx, dy))
                    self.offsets_posto.insert(0, (dx, dy))
                    self.zz_falhos.pop(chave((cx, cy)), None)
                    self.escolher_producao(g)
                    return True
                if self.tratar_dialogos(img):
                    continue
        return False

    # ---------- loop ----------
    def rodar(self):
        carregar_templates()
        log("Auto-farm iniciado. P = pausar/continuar, Q = sair.")
        if PAINEL:
            log(f"Log de execucao: {PAINEL.caminho_log}")
        ultimo_zz_falho = 0.0
        ultimo_zz_completo = 0.0
        ultimo_check_dialogo = 0.0
        ultimo_check_mapa = 0.0
        while not (PAINEL and PAINEL.sair):
            if PAINEL and PAINEL.pausado.is_set():
                # ao voltar da pausa confere logo se o mapa continua no lugar
                ultimo_check_mapa = 0.0
                self.ultima_atividade = time.time()
                time.sleep(0.3)
                continue
            img = self.cap()
            if img is None:
                log("Janela do jogo nao encontrada / sem imagem. Tentando de novo em 10 s...")
                time.sleep(10)
                continue

            pequena = modo_tela_pequena(img)
            if pequena:
                self.vp = None  # site em volta do jogo: o layout so vale com o jogo em tela cheia
            elif not tela_escurecida(img, self.brilho_normal, self.vp) \
                    and time.time() - self.ultimo_layout > 1.5:
                self.ultimo_layout = time.time()
                if self.atualizar_layout(img):
                    ultimo_check_mapa = 0.0
                    continue
            # procura dialogos quando faz sentido (tela escurecida, site, inicio) e a cada 30 s
            checar = self.brilho_normal is None or pequena or tela_escurecida(img, self.brilho_normal, self.vp) \
                or time.time() - ultimo_check_dialogo > 30
            if checar:
                ultimo_check_dialogo = time.time()
                if self.tratar_dialogos(img):
                    continue

            if pequena:
                if not self.entrar_tela_cheia(img):
                    time.sleep(5)  # ainda carregando
                continue

            if self.precisa_zoom:
                self.ajustar_zoom()
                continue

            if self.brilho_normal is None:
                self.brilho_normal = brilho(img, self.vp)

            # confere de tempos em tempos se o mapa saiu do lugar (misclick, scroll, arrasto...)
            if time.time() - ultimo_check_mapa > SEGUNDOS_CHECAR_MAPA \
                    and not tela_escurecida(img, self.brilho_normal, self.vp):
                ultimo_check_mapa = time.time()
                if not self.mapa_alinhado(img):
                    log("Mapa fora do lugar -> realinhando.")
                    if not self.realinhar():
                        self.recarregar_pagina(img, "nao consegui realinhar o mapa")
                    continue

            if not tela_escurecida(img, self.brilho_normal, self.vp):
                self.estat.atualizar(ler_recursos(img))
                if PAINEL:
                    PAINEL.resumo_no_arquivo()

            prontas, dormindo = detectar_bolhas(img, self.vp)
            prontas = juntar_prontas(prontas, detectar_icones(img, self.escala, self.vp))
            postos = [b for b in prontas if self.eh_posto(img, b)]
            campos = [b for b in prontas if b not in postos]

            # ordem de prioridade: 1) colher postos de 5 min  2) replantar postos zZ
            # 3) plantacoes de 30 s (elas gastam a madeira que os postos produzem)
            if postos:
                self.colher(postos, "de postos")
                ultimo_zz_completo = 0.0  # os zZ aparecem logo depois: confere ja
                time.sleep(0.4)
                continue

            if time.time() - ultimo_zz_falho > 60:
                if dormindo or time.time() - ultimo_zz_completo > 8:
                    ultimo_zz_completo = time.time()
                    dormindo = completar_dormindo(img, dormindo, self.vp)
                if dormindo:
                    log(f"{len(dormindo)} posto(s) parado(s) (zZ) -> replantando.")
                    if not self.replantar(dormindo):
                        log("Nao consegui abrir o menu de um posto zZ; tento de novo em 1 min.")
                        salvar_debug(self.cap() if self.cap() is not None else img, "replantio_falhou")
                        ultimo_zz_falho = time.time()
                    ultimo_zz_completo = 0.0
                    continue

            if campos:
                self.colher(campos, "de plantacoes")
                time.sleep(0.2)
                continue

            # brilho de referencia acompanha a tela "normal" (sem dialogos)
            self.brilho_normal = 0.9 * self.brilho_normal + 0.1 * brilho(img, self.vp)

            if time.time() - self.ultima_atividade > MINUTOS_SEM_ATIVIDADE * 60:
                self.recarregar_pagina(img)
                continue

            time.sleep(INTERVALO_VARREDURA)


if __name__ == "__main__":
    if "--zoom" in sys.argv:
        b = Bot()
        carregar_templates()
        b.cap()
        b.ajustar_zoom()
        sys.exit(0)
    bot = Bot()
    PAINEL = Painel(bot.estat, PASTA)
    PAINEL.iniciar()
    try:
        bot.rodar()
        log("Encerrado pela tecla Q.")
    except KeyboardInterrupt:
        log("Parado pelo usuario.")
    finally:
        PAINEL.encerrar()
