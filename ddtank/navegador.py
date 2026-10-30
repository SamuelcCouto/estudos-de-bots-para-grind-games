# -*- coding: utf-8 -*-
"""
DDTank - navegador (fase 2): percorre sozinho a rota de instancias do menu ate o chefe,
passa pelas cartas, coleta as tarefas no fim e recomeca. Sem usar o seu mouse.

  Fantasma -> Profundezas -> O Minhocao -> (tarefas) -> Central -> de novo

CHEFAO GLOBAL (Pericao, aba "Instancia do evento"): opcao C ao abrir (so ele), ou junto com a rota nos horarios
(HORARIOS_CHEFE): na hora, o bot termina a instancia em andamento, vai para o Pericao e luta ate o servidor derrubar o
chefao (vitoria = cartas); depois volta para a rota de onde parou.

A BATALHA ainda e sua (fase 3 = tiro automatico): o bot espera a luta terminar.

  python navegador.py --so-ver        so mostra a tela detectada (nao clica) - teste primeiro!
  python navegador.py --simular       diz o que clicaria, sem clicar
  python navegador.py                 liga o bot
  python navegador.py --uma-vez       faz uma volta completa e para
Teclas: F8 = pausar/continuar   F10 = sair
"""
import argparse
import datetime
import glob
import os
import random
import sys
import time
from collections import Counter

import cv2
import numpy as np

import config
import estados as estados_mod
import estrategias

# ---------------------------------------------------------------------------
# Posicoes (em pixels de uma imagem com 1280 de largura; saem da sua gravacao)
# ---------------------------------------------------------------------------
LARGURA_REF = 1280
# Pop-up "Clique no jogo para continuar jogando" (aparece quando o jogo perde o foco). Qualquer clique dentro do jogo
# o fecha, mas o clique tambem vale para o que esta POR BAIXO - entao nunca clicar no pop-up (no mapa ele cobre a
# Sala de Casamento!). Usa um ponto neutro: o chat nas telas de cidade/sala, o texto do log na batalha etc.
# ATENCAO: NUNCA clicar no CHAT (barra de mensagens embaixo, log da batalha): dar clique ali passa o foco do TECLADO para o
# campo de digitacao do chat e as setas/numeros/espaco deixam de chegar ao jogo (era o que fazia o atirador "nao responder").
# Telas de cidade/sala: canto superior esquerdo do jogo (moldura/ceu/area preta). Batalha: um ponto da CENA.
FOCO_PONTO_PADRAO = (330, 172)
FOCO_PONTO_NEUTRO = {"BATALHA": (560, 230)}
FOCO_CLICK_BATALHA = (560, 230)       # clique na cena: devolve o foco do teclado ao jogo (se o chat o tinha)
POPUP_FOCO_CAIXA = (596, 316, 696, 410)
MAPA_CENTRAL = (872, 430)
CENTRAL_JOGAR = (794, 472)
SALA_TROCAR_INSTANCIA = (697, 302)
CONFIG_SIM = (640, 529)
SALA_INICIO = (934, 473)
POPUP_SOZINHO_SIM = (575, 402)
POPUP_CARTA_SIM = (566, 391)
POPUP_AVISO_SIM = (644, 394)
SALA_ICONE_TAREFAS = (806, 533)
SALA_PORTA = (949, 522)
TAREFA_FECHAR = (881, 190)
TAREFA_BOTAO = (760, 513)
ESPERA_CONFIRMAR_TELA = 0.3   # s entre as 2 leituras que confirmam uma tela (era 0,45: ~1 s a menos por instancia)
MAX_ERROS_EM_10_MIN = 12       # falhas inesperadas seguidas que param o bot
PRESO_APOS = 120.0             # s na mesma tela (fora de batalha) ou em tela desconhecida = "preso": tenta se soltar
PRESO_REPETIR = 60.0           # s entre as tentativas de se soltar
MAX_ACOES_TAREFA = 40          # cliques no painel de tarefas por fim de rota (trava de seguranca)
MAX_ROLAGENS_TAREFA = 12
CARTAS_COLUNAS = [380, 468, 556, 644, 732, 820, 907]
CARTAS_LINHAS = [262, 380, 498]
# ordem de preferencia: fileira do meio (colunas 3, 4, 5), depois o resto
CARTAS_TODAS = [(x, y) for y in CARTAS_LINHAS for x in CARTAS_COLUNAS]
CARTAS_ENTRE_CLIQUES = 0.5        # s entre os cliques nas 3 cartas sorteadas (a tela de cartas tem cronometro de 15 s)
CARTAS_REPETIR_APOS = 3.0         # s sem virar -> clica de novo nas sorteadas; depois de 2 tentativas, sorteia outras
                                  # (o jogo trava na 3a carta: clicar a mais nao abre uma 4a nem gasta nada)
CARTAS_VIRADAS_PARA_PAGAR = 3     # 2 gratis + a 3a (VIP, com pop-up de confirmacao)
SLOTS_SALA = [(516, 242), (394, 366), (516, 366)]   # 3 vagas vazias da sala
SLOT_RECORTE = (-36, 34, -37, 43)   # recorte (dx0, dx1, dy0, dy1) da silhueta "Em Espera" ao redor do centro da vaga
SLOT_ABERTO_LIMIAR = 0.6          # aberta ~0.97-1.0; fechada (X) ~0.29; ocupada por jogador ~0.08
BRILHO_SLOT_FECHADO = 140         # fechada ~110 (marrom); ocupada por jogador e mais clara
CFG_REGIAO = (490, 395, 610, 455)  # arte da instancia selecionada na janela de configuracao
CFG_LIMIAR = 0.7                   # certa >= ~0.9; qualquer outra coisa < 0.56

# grade da aba "Instancia normal" da configuracao da sala (2 linhas x 4 colunas, centro de cada quadro)
INSTANCIA_NA_CONFIG = {
    "FANTASMA": (509, 313), "PROFUNDEZAS": (591, 313), "MINHOCAO": (675, 318), "ESCORPIAO_REI": (765, 316),
    "DRAGAO_GELADO": (505, 357), "RAINHA_LIRIS": (591, 357), "ULTIMA_LUTA": (675, 357), "GATO_PRETO": (765, 357),
}
# o Chefao Global fica na aba "Instancia do evento" (1o quadro). A janela pode abrir na ultima aba usada: o bot confere
# a aba ativa (a clara) e clica na certa antes do quadro.
INSTANCIA_NA_CONFIG["PERICAO"] = (500, 320)
# Rota Leste (gravacao 20261030_004606): A Ultima Luta (2 fases) e Devoradores. Os Devoradores ficam na 2a "pagina" da lista da aba
# normal (a lista rola de 2 em 2 linhas): clica a seta para baixo antes e confere pelo desenho do quadro.
INSTANCIA_NA_CONFIG["DEVORADORES"] = (518, 345)
PAGINA_NA_CONFIG = {"DEVORADORES": 2}            # as outras: pagina 1
LISTA_SETA = {"baixo": (828, 367), "cima": (828, 312)}
LISTA_SETA_ALTERNATIVA = (821, 325)              # onde o usuario clicou para rolar (funcionou)
LISTA_PAGINA_REGIAO = {1: (479, 301, 539, 325), 2: (488, 333, 548, 357)}   # quadro da 1a coluna/linha: Fantasma (p1) x Devoradores (p2)
LISTA_PAGINA_LIMIAR = 0.7
CARTAS_P_POS = [(x, y) for y in (256, 374, 493) for x in (738, 826, 913)]    # painel PEQUENO (3x3) da fase 1 da Ultima Luta
CARTAS_P_REPETIR_APOS = 3.0
CARTAS_ESTADOS = ("CARTAS", "POPUP_CARTA", "CARTAS_P")
ABAS_CONFIG = {"normal": (495, 284), "especial": (562, 284), "evento": (630, 284), "avancada": (698, 284)}
ABA_DA_INSTANCIA = {"PERICAO": "evento"}         # as outras: "normal"
BRILHO_ABA_ATIVA = 135                           # aba ativa ~161-163 (creme); as outras ~100 (marrom)
DIFICULDADE_BOTAO = {"NORMAL": (513, 495), "DIFICIL": (646, 495), "HEROI": (770, 495)}
# rotas: letra -> (nome, instancias em ordem). T = as duas, uma volta so (coleta as tarefas no fim de tudo).
ROTAS = {
    "N": ("Rota Norte", ["FANTASMA", "PROFUNDEZAS", "MINHOCAO"]),
    "S": ("Rota Sul", ["ESCORPIAO_REI", "DRAGAO_GELADO", "RAINHA_LIRIS"]),
}
ROTAS["L"] = ("Rota Leste", ["ULTIMA_LUTA", "DEVORADORES"])
ROTAS["T"] = ("Rota Norte e Sul", ROTAS["N"][1] + ROTAS["S"][1])
ROTAS["U"] = ("Super Rota", ROTAS["N"][1] + ROTAS["S"][1] + ROTAS["L"][1])
CUPONS_POR_ROTA = {"N": 40000, "S": 50000, "L": 60000}
FIM_ROTA_CUPOM = {3: "N", 6: "S", 8: "L"}     # indice da PROXIMA instancia (depois da ultima da rota) -> rota que acabou (Super Rota: 3+3+2)
CHEFE = "PERICAO"
ROTAS["C"] = ("Chefao Global", [CHEFE])
ROTAS["P"] = ("Pericao (comum, fora do horario do Chefao Global)", [CHEFE])
# 28/10: o boneco ja esta completo com os drops da Rota Norte -> N e T ficam DESABILITADAS no menu (nao apagadas:
# continuam funcionando com --rota N / --rota T). O menu oferece so o que esta em uso:
ROTAS_NO_MENU = ("U", "T", "S", "L", "P", "C")
ROTA_PADRAO_MENU = "S"
# cartas que interessam por rota (as outras so completam a missao da rota: o bot nao abre as cartas delas)
CARTAS_DE_INTERESSE = {"S": ["RAINHA_LIRIS"]}
APELIDOS_ROTA = {"1": "N", "2": "S", "NORTE": "N", "SUL": "S", "CUPONS": "U", "SUPER": "U", "NORTE E SUL": "T", "TODAS": "T", "TUDO": "T", "AMBAS": "T",
                 "CHEFE": "C", "CHEFAO": "C", "PERICAO": "C", "COMUM": "P", "LESTE": "L"}
# horarios do Chefao Global (relogio do PC): (inicio, fim). Mude aqui ou com --horarios-chefe 12:00-13:00,21:00-22:00
HORARIOS_CHEFE = [((12, 0), (13, 0)), ((21, 0), (22, 0))]
CHEFE_DERROTAS_FORA_DO_HORARIO = 3   # opcao C aberta fora do horario: tenta assim mesmo; depois disso, espera o horario
CHEFE_TENTATIVAS_MARCAR = 8          # cliques no quadro do Pericao sem ele ficar marcado: evento fechado -> desiste
CHEFE_AVISO_ESPERA = 300.0           # s entre os avisos "esperando o Chefao Global"
ROTA_PADRAO = ROTAS["N"][1]
# dificuldade clicada antes de confirmar, por instancia. As das rotas Norte e Sul NAO tem escolha (o quadro
# "Dificuldade" fica vazio quando uma delas esta marcada); fica para rotas futuras (ou --dificuldade).
DIFICULDADE_DA_INSTANCIA = {}
SALA_ARTE = (600, 180, 800, 300)   # arte da instancia escolhida, no meio da sala (titulo + desenho)
SALA_ARTE_LIMIAR = 0.8
PASTA_APRENDIDOS = os.path.join(config.PASTA, "dados", "modelos_aprendidos")   # artes de instancias novas (o bot aprende)

CLIQUE_SIMPLES = {                      # tela -> onde clicar para avancar
    "MAPA": MAPA_CENTRAL,
    "POPUP_SOZINHO": POPUP_SOZINHO_SIM,
    # 29/10: o Pericao pede confirmacao com outro texto ("A instancia apresenta mais desafios...", botao Concordar) e
    # o jogo avisa "O Chefao Global vai comecar em alguns minutos!" (botao sim) POR CIMA: o bot ficou 55 min parado
    "POPUP_SOZINHO2": POPUP_SOZINHO_SIM,
    "POPUP_SOZINHO3": POPUP_SOZINHO_SIM,          # 30/10: mesma confirmacao do Pericao, em outro desenho ("Concordar" em (572,405))
    "POPUP_AVISO": POPUP_AVISO_SIM,
    "POPUP_CARTA": POPUP_CARTA_SIM,
}
MODOS_ENTRADA = ["top", "filha"]
VK_F8, VK_F10 = 0x77, 0x79
ARQUIVO_PARAR = os.path.join(config.PASTA_LOGS, "parar.flag")
ARQUIVO_PAUSAR = os.path.join(config.PASTA_LOGS, "pausar.flag")   # existe = pausado (o painel cria/apaga)


def fmt_tempo(s):
    s = int(round(s))
    return f"{s}s" if s < 60 else (f"{s // 60}min{s % 60:02d}s" if s < 3600 else f"{s // 3600}h{s % 3600 // 60:02d}min")


# ---------------------------------------------------------------------------
# entrada/saida (trocavel nos testes)
# ---------------------------------------------------------------------------
class IOJanela:
    """Entrada/saida com o jogo. Calibra sozinho o tamanho/posicao do jogo na janela (tela.py): o resto do bot sempre
    ve o quadro canonico de 1280 px (como na janela original) e clica em coordenadas dele."""
    def __init__(self, hwnd, janela_mod=None, calibrar=True, log=print):
        if janela_mod is None:
            import janela as janela_mod
        self.j = janela_mod
        self.hwnd = hwnd
        self.auto, self.log = calibrar, log
        self.calib, self.tam, self.det = None, None, None
        self.calibrar_agora = calibrar
        self.ultima_calibracao = -1e9

    k = 1.0

    def capturar_bruto(self):
        return self.j.capturar(self.hwnd, "print")

    def pedir_calibracao(self):
        """Pede para calibrar de novo no proximo quadro (tela desconhecida por muito tempo, janela mudou...)."""
        if self.auto and time.time() - self.ultima_calibracao >= 60:
            self.calibrar_agora = True

    def _calibrar(self, img):
        import tela
        self.calibrar_agora = False
        self.ultima_calibracao = time.time()
        self.tam = img.shape[:2]
        self.det = self.det or estados_mod.Detector()
        self.log("[TELA] calibrando o tamanho/posicao do jogo na janela...")
        t0 = time.time()
        c = tela.calibrar(img, self.det)
        if c is None:
            if self.calib is None:
                self.log(f"[TELA] janela {self.tam[1]}x{self.tam[0]}: nao reconheci nenhuma tela conhecida para calibrar; uso o "
                         f"tamanho original. Se o bot nao reconhecer as telas, deixe o jogo no mapa/sala e tente de novo.")
            return
        self.calib = c
        self.log(f"[TELA] calibrada em {time.time() - t0:.1f}s: {c.texto((self.tam[1], self.tam[0]))} (tela usada: {c.estado})")
        if c.zoom < tela.ZOOM_MIN_BOM:
            self.log(f"[TELA] ! o jogo esta pequeno na janela (zoom {c.zoom:.2f}): o minimapa perde precisao. Prefira a janela "
                     f"maior / tela cheia.")

    def capturar(self):
        img = self.capturar_bruto()
        if img is None:
            return None
        if self.auto and (self.calibrar_agora or img.shape[:2] != self.tam):
            self._calibrar(img)
        if self.calib is not None and not self.calib.legado:
            self.k = 1.0
            return self.calib.renderizar(img)
        self.k = img.shape[1] / LARGURA_REF
        return img

    def _para_janela(self, x, y):
        if self.calib is not None and not self.calib.legado:
            x, y = self.calib.ref_para_janela(x, y)             # (no modo calibrado k = 1: x, y ja sao do quadro canonico)
        return int(round(x)), int(round(y))

    def clicar_ref(self, xr, yr, modo="top"):
        """Clique em coordenadas da imagem de 1280 de largura (usado pelo atirador)."""
        if self.calib is not None and not self.calib.legado:
            x, y = self._para_janela(xr, yr)
        else:
            x, y = int(xr * self.k), int(yr * self.k)
        self.j.clicar(self.hwnd, x, y, modo)

    def clicar(self, x, y, modo):
        self.j.clicar(self.hwnd, *self._para_janela(x, y), modo)

    def tecla_apertada(self, vk):
        return bool(self.j.user32.GetAsyncKeyState(vk) & 0x8000)

    # teclas da batalha (setas, itens, espaco); o modo de entrada e escolhido separadamente dos cliques
    modo_teclas = "top"

    def tecla(self, nome, dur=0.05):
        self.j.tecla(self.hwnd, nome, dur, self.modo_teclas)

    def tecla_baixo(self, nome, repeticao=1):
        self.j.tecla_baixo(self.hwnd, nome, self.modo_teclas, repeticao)

    def tecla_cima(self, nome):
        self.j.tecla_cima(self.hwnd, nome, self.modo_teclas)

    def segurar(self, nome):
        """Aperta e MANTEM a tecla: uma thread manda a repeticao de tecla a cada ~30 ms, como o teclado de verdade
        (o jogo pode considerar a tecla solta se as repeticoes pararem por um instante)."""
        import threading
        self._parar_repeticao = threading.Event()
        self.j.tecla_baixo(self.hwnd, nome, self.modo_teclas, 1)

        def repetir():
            rep = 2
            while not self._parar_repeticao.wait(0.03):
                self.j.tecla_baixo(self.hwnd, nome, self.modo_teclas, rep)
                rep += 1

        self._thread_repeticao = threading.Thread(target=repetir, daemon=True)
        self._thread_repeticao.start()

    def soltar(self, nome):
        if getattr(self, "_parar_repeticao", None) is not None:
            self._parar_repeticao.set()
            self._thread_repeticao.join(timeout=0.3)
        self.j.tecla_cima(self.hwnd, nome, self.modo_teclas)

    def trocar_modo(self):
        self.modo_teclas = "filha" if self.modo_teclas == "top" else "top"

    # Foco do teclado: 0 = nenhum (so PostMessage), 1 = "virtual" (avisa a janela que ganhou foco),
    # 2 = real (traz o jogo para a frente durante o turno e devolve depois). Sobe sozinho se as teclas nao chegarem.
    foco_nivel = 1
    _foco_anterior = None

    def preparar_teclas(self):
        if self.foco_nivel >= 1:
            self.j.foco_virtual(self.hwnd)
        if self.foco_nivel >= 2:
            self._foco_anterior = self.j.foco_real(self.hwnd)
            time.sleep(0.15)

    def encerrar_teclas(self):
        if self._foco_anterior:
            self.j.devolver_foco(self._foco_anterior)
            self._foco_anterior = None

    def escalar_foco(self):
        """Sobe o nivel de foco (ate 2). Devolve True se subiu."""
        if self.foco_nivel >= 2:
            return False
        self.foco_nivel += 1
        self.preparar_teclas()
        return True

    def em_foco(self):
        """O jogo e a janela em primeiro plano do Windows? (em segundo plano ele pode rodar mais devagar)"""
        fg = self.j.user32.GetForegroundWindow()
        return bool(fg) and (fg == self.hwnd or self.j.pid_da_janela(fg) == self.j.pid_da_janela(self.hwnd))


_TPL_COSTAS = []


def cartas_de_costas(f, pontos=None):
    """Centros das cartas de costas: grade comum (21) ou entrada da Ultima Luta (9)."""
    if not _TPL_COSTAS:
        _TPL_COSTAS.append(cv2.imread(os.path.join(config.PASTA_TEMPLATES, "costas_carta.png"), cv2.IMREAD_GRAYSCALE))
    t = _TPL_COSTAS[0]
    th, tw = t.shape
    g = cv2.GaussianBlur(cv2.cvtColor(f, cv2.COLOR_BGR2GRAY), (3, 3), 0)
    achadas = []
    for x, y in (pontos or CARTAS_TODAS):
        roi = g[y - th // 2 - 8:y + th // 2 + 8, x - tw // 2 - 8:x + tw // 2 + 8]
        if roi.shape[0] >= th and roi.shape[1] >= tw and cv2.matchTemplate(roi, t, cv2.TM_CCOEFF_NORMED).max() > 0.55:
            achadas.append((x, y))
    return achadas


_TPL_SLOT = []
_TPL_CFG = {}
_TPL_SALA = {}


def estado_vagas(f):
    """Para cada uma das 3 vagas: 'aberto' (Em Espera), 'fechado' (X) ou 'ocupado' (outro jogador entrou)."""
    if not _TPL_SLOT:
        _TPL_SLOT.append(cv2.imread(os.path.join(config.PASTA_TEMPLATES, "slot_aberto.png"), cv2.IMREAD_GRAYSCALE))
    t = _TPL_SLOT[0]
    g = cv2.GaussianBlur(cv2.cvtColor(f, cv2.COLOR_BGR2GRAY), (3, 3), 0)
    dx0, dx1, dy0, dy1 = SLOT_RECORTE
    out = []
    for cx, cy in SLOTS_SALA:
        roi = g[cy + dy0 - 8:cy + dy1 + 8, cx + dx0 - 8:cx + dx1 + 8]
        if cv2.matchTemplate(roi, t, cv2.TM_CCOEFF_NORMED).max() >= SLOT_ABERTO_LIMIAR:
            out.append("aberto")
        elif g[cy - 30:cy + 30, cx - 40:cx + 40].mean() < BRILHO_SLOT_FECHADO:
            out.append("fechado")
        else:
            out.append("ocupado")
    return out


def slots_abertos(f):
    """Centros das vagas ainda abertas. Vagas fechadas ou ocupadas por outro jogador NAO entram."""
    return [c for c, e in zip(SLOTS_SALA, estado_vagas(f)) if e == "aberto"]


def _cinza(f):
    return cv2.GaussianBlur(cv2.cvtColor(f, cv2.COLOR_BGR2GRAY), (3, 3), 0).astype(np.float32)


def _carregar_modelos(prefixo):
    """{instancia: modelo cinza} de templates/<prefixo>_*.png e dos aprendidos (dados/modelos_aprendidos)."""
    out = {}
    for pasta in (config.PASTA_TEMPLATES, PASTA_APRENDIDOS):
        for arq in sorted(glob.glob(os.path.join(pasta, f"{prefixo}_*.png"))):
            nome = os.path.basename(arq)[len(prefixo) + 1:-4]
            t = cv2.imread(arq, cv2.IMREAD_GRAYSCALE)
            if t is not None:
                out[nome] = t.astype(np.float32)
    return out


def tem_modelo(prefixo, nome):
    return nome in (_TPL_CFG if prefixo == "cfg" else _TPL_SALA) or any(
        os.path.exists(os.path.join(p, f"{prefixo}_{nome}.png")) for p in (config.PASTA_TEMPLATES, PASTA_APRENDIDOS))


def tem_textura(f, regiao, minimo=18.0):
    """A regiao tem desenho (e nao um fundo liso/carregando)?"""
    x0, y0, x1, y1 = regiao
    return float(_cinza(f)[y0:y1, x0:x1].std()) >= minimo


def aprender_modelo(prefixo, nome, f, regiao):
    """Guarda o recorte `regiao` do quadro como modelo da arte de `nome` (instancia nova: o bot aprende sozinho)."""
    x0, y0, x1, y1 = regiao
    os.makedirs(PASTA_APRENDIDOS, exist_ok=True)
    cv2.imwrite(os.path.join(PASTA_APRENDIDOS, f"{prefixo}_{nome}.png"), np.clip(_cinza(f)[y0:y1, x0:x1], 0, 255).astype(np.uint8))
    (_TPL_CFG if prefixo == "cfg" else _TPL_SALA).clear()


def _melhor_modelo(f, modelos, regiao, limiar, tol=6):
    if not modelos:
        return None
    g = _cinza(f)
    x0, y0, x1, y1 = regiao
    roi = g[max(0, y0 - tol):y1 + tol, max(0, x0 - tol):x1 + tol]
    notas = {n: float(cv2.matchTemplate(roi, t, cv2.TM_CCOEFF_NORMED).max()) for n, t in modelos.items()
             if t.shape[0] <= roi.shape[0] and t.shape[1] <= roi.shape[1]}
    if not notas:
        return None
    melhor = max(notas, key=notas.get)
    return melhor if notas[melhor] >= limiar else None


def instancia_selecionada(f):
    """Qual instancia esta marcada na janela de configuracao (pela arte), ou None."""
    if not _TPL_CFG:
        _TPL_CFG.update(_carregar_modelos("cfg"))
    return _melhor_modelo(f, _TPL_CFG, CFG_REGIAO, CFG_LIMIAR)


def instancia_na_sala(f):
    """Instancia mostrada no meio da sala, pelas artes APRENDIDAS (as 3 da rota 1 tem telas proprias PRONTA_*), ou None."""
    if not _TPL_SALA:
        _TPL_SALA.update(_carregar_modelos("sala"))
    return _melhor_modelo(f, _TPL_SALA, SALA_ARTE, SALA_ARTE_LIMIAR)


_TPL_LISTA = {}


def pagina_da_lista(f):
    """Pagina da lista de instancias aberta na configuracao (1 = Fantasma..., 2 = Devoradores...), pelo desenho do 1o quadro; None
    se nao der para saber (janela nao e a de configuracao / carregando)."""
    if not _TPL_LISTA:
        for n in (1, 2):
            t = cv2.imread(os.path.join(config.PASTA_TEMPLATES, f"lista_p{n}.png"), cv2.IMREAD_GRAYSCALE)
            if t is not None:
                _TPL_LISTA[n] = t.astype(np.float32)
    g = _cinza(f)
    melhor, nota = None, 0.0
    for n, t in _TPL_LISTA.items():
        x0, y0, x1, y1 = LISTA_PAGINA_REGIAO[n]
        roi = g[y0 - 6:y1 + 6, x0 - 6:x1 + 6]
        if roi.shape[0] < t.shape[0] or roi.shape[1] < t.shape[1]:
            continue
        v = float(cv2.matchTemplate(roi, t, cv2.TM_CCOEFF_NORMED).max())
        if v > nota:
            melhor, nota = n, v
    return melhor if nota >= LISTA_PAGINA_LIMIAR else None


def evitar_suspensao():
    """Windows: enquanto o bot roda, o PC nao entra em suspensao (de madrugada ele parava com o PC dormindo). A tela pode
    apagar. Volta ao normal quando o programa fecha."""
    try:
        import ctypes
        ES_CONTINUOUS, ES_SYSTEM_REQUIRED = 0x80000000, 0x00000001
        ctypes.windll.kernel32.SetThreadExecutionState(ES_CONTINUOUS | ES_SYSTEM_REQUIRED)
        return True
    except Exception:
        return False


def instancia_unica():
    """False se ja existe outro bot rodando neste PC (varios bots clicando juntos se atrapalham)."""
    try:
        import ctypes
        k32 = ctypes.windll.kernel32
        h = k32.CreateMutexW(None, False, "Local\\DDTankBotNavegador")
        if k32.GetLastError() == 183:      # ERROR_ALREADY_EXISTS
            return False
        instancia_unica.handle = h         # mantem o mutex vivo ate o programa terminar
    except Exception:
        pass
    return True


def em_1280(img):
    h, w = img.shape[:2]
    return img if w == LARGURA_REF else cv2.resize(img, (LARGURA_REF, int(h * LARGURA_REF / w)), interpolation=cv2.INTER_AREA)


# ---------------------------------------------------------------------------
# leitura do painel de Tarefas (por cor, sem coordenadas fixas de itens)
# ---------------------------------------------------------------------------
_TPL_TAREFA_CABECALHO = []

def painel_tarefa_visivel(f):
    """Reconhece o cabecalho estavel do painel mesmo quando as recompensas mudam."""
    if not _TPL_TAREFA_CABECALHO:
        _TPL_TAREFA_CABECALHO.append(cv2.imread(os.path.join(config.PASTA_TEMPLATES, "tarefa_cabecalho.png"), cv2.IMREAD_GRAYSCALE))
    t = _TPL_TAREFA_CABECALHO[0]
    if t is None or f is None:
        return False
    area = cv2.cvtColor(f[168:212, 400:540], cv2.COLOR_BGR2GRAY)
    return cv2.matchTemplate(area, t, cv2.TM_CCOEFF_NORMED).max() >= 0.8

def botao_recompensa_ativo(f):
    """O botao 'Obter recompensa' fica vermelho quando da para coletar e cinza quando nao. O vermelho PULSA (R medio
    154-204 nas gravacoes); o cinza fica em ~(94, 92, 90). Vale a diferenca de cor, nao o brilho."""
    reg = f[500:525, 700:820].astype(int)
    b, g, r = reg[..., 0].mean(), reg[..., 1].mean(), reg[..., 2].mean()
    return r > 120 and r - g > 50 and r - b > 60


_TPL_ESCOLHER_PREMIO = []

def tarefa_exige_escolha(f):
    """A tarefa mostra premios de escolha livre; o bot nunca escolhe pelo usuario."""
    if not _TPL_ESCOLHER_PREMIO:
        t = cv2.imread(os.path.join(config.PASTA_TEMPLATES, "tarefa_escolher_premio.png"), cv2.IMREAD_GRAYSCALE)
        _TPL_ESCOLHER_PREMIO.append(t)
    t = _TPL_ESCOLHER_PREMIO[0]
    if t is None:
        return False
    area = cv2.cvtColor(f[320:360, 590:850], cv2.COLOR_BGR2GRAY)
    return cv2.matchTemplate(area, t, cv2.TM_CCOEFF_NORMED).max() >= 0.82

_TPL_POPUP_ESCOLHA = []
_TPL_SUPER_LESTE = []

def popup_escolha_recompensa(f):
    """Posicoes do popup 'Escolha uma recompensa' em um quadro normalizado para 1280."""
    if f is None:
        return None
    if not _TPL_POPUP_ESCOLHA:
        _TPL_POPUP_ESCOLHA.append(cv2.imread(os.path.join(config.PASTA_TEMPLATES, "tarefa_popup_escolha.png"), cv2.IMREAD_GRAYSCALE))
    t = _TPL_POPUP_ESCOLHA[0]
    if t is None:
        return None
    area = cv2.cvtColor(f[220:350, 450:800], cv2.COLOR_BGR2GRAY)
    _, nota, _, (x, y) = cv2.minMaxLoc(cv2.matchTemplate(area, t, cv2.TM_CCOEFF_NORMED))
    if nota < 0.82:
        return None
    x, y = x + 450, y + 220
    return {"opcao": (x + 63, y + 54), "confirmar": (x + 117, y + 137), "fechar": (x + 220, y + 8)}

def tarefa_leste_selecionada(f):
    """Confirma que a tarefa aberta e Super Rota Leste antes de escolher um item."""
    if f is None:
        return False
    if not _TPL_SUPER_LESTE:
        _TPL_SUPER_LESTE.append(cv2.imread(os.path.join(config.PASTA_TEMPLATES, "tarefa_super_leste.png"), cv2.IMREAD_GRAYSCALE))
    t = _TPL_SUPER_LESTE[0]
    if t is None:
        return False
    area = cv2.cvtColor(f[300:470, 390:620], cv2.COLOR_BGR2GRAY)
    return cv2.matchTemplate(area, t, cv2.TM_CCOEFF_NORMED).max() >= 0.90

def selos_ok(f):
    """Posicoes (x, y) dos selos verdes 'OK!' na lista da esquerda do painel de Tarefas (em itens e em categorias
    fechadas que tem alguma tarefa concluida dentro)."""
    x0, y0, x1, y1 = 335, 225, 600, 560
    c = f[y0:y1, x0:x1].astype(int)
    m = ((c[..., 1] > c[..., 2] + 35) & (c[..., 1] > c[..., 0] + 35)).astype(np.uint8)
    m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8))
    n, _, st, ce = cv2.connectedComponentsWithStats(m)
    achados = [(int(ce[i][0]) + x0, int(ce[i][1]) + y0) for i in range(1, n) if st[i][4] >= 80]
    return sorted(achados, key=lambda p: p[1])


_TPL_SETA_LISTA = []


def seta_rolar_lista(f):
    """(x, y) da setinha 'para baixo' da sub-lista aberta (as tarefas de uma categoria; so mostra 4 por vez) ou None.
    A barra da sub-lista fica em x~573; a seta de baixo e o ponto MAIS BAIXO dessa coluna parecido com o modelo
    (a seta de cima e o fim do cursor tambem parecem um pouco). A barra da lista de fora (x~591) nao conta."""
    if not _TPL_SETA_LISTA:
        _TPL_SETA_LISTA.append(cv2.imread(os.path.join(config.PASTA_TEMPLATES, "seta_lista_baixo.png"), cv2.IMREAD_GRAYSCALE))
    t = _TPL_SETA_LISTA[0]
    th, tw = t.shape
    x0, y0 = 555, 220
    g = cv2.cvtColor(f[y0:565, x0:600], cv2.COLOR_BGR2GRAY)
    r = cv2.matchTemplate(g, t, cv2.TM_CCOEFF_NORMED)
    ys, xs = np.where(r > 0.6)
    cands = [(int(x) + x0 + tw // 2, int(y) + y0 + th // 2) for y, x in zip(ys, xs)]
    cands = [p for p in cands if 568 <= p[0] <= 578]
    return max(cands, key=lambda p: p[1]) if cands else None


def recorte_sublista(f, seta):
    """Pedaco da sub-lista acima da seta (para saber se rolar mudou alguma coisa)."""
    return cv2.cvtColor(f[seta[1] - 85:seta[1] + 8, 335:580], cv2.COLOR_BGR2GRAY).astype(np.float32)


def recorte_painel_tarefa(f):
    """Painel de tarefas sem a faixa do botao (que pulsa): para saber se um clique mudou alguma coisa."""
    return cv2.cvtColor(f[200:490, 340:880], cv2.COLOR_BGR2GRAY).astype(np.float32)


def proxima_acao_tarefa(f, vezes, ignorar_botao=False):
    """('botao', ponto) | ('item', ponto) | ('fim', None) para o quadro atual do painel.
    vezes: Counter de cliques por posicao de selo (no maximo 2 por posicao; zere depois de cada coleta/rolagem)."""
    if botao_recompensa_ativo(f) and not ignorar_botao:
        return "botao", TAREFA_BOTAO
    for bx, by in selos_ok(f):
        chave = (bx // 25, by // 25)
        if vezes[chave] < 2:
            vezes[chave] += 1
            return "item", (max(350, bx - 80), by)   # clica no nome da tarefa, a esquerda do selo
    return "fim", None


def aba_ativa(f):
    """Aba da janela de configuracao que esta aberta ('normal', 'evento'...) - a mais clara - ou None."""
    brilho = {n: float(f[y - 8:y + 8, x - 25:x + 25].mean()) for n, (x, y) in ABAS_CONFIG.items()}
    melhor = max(brilho, key=brilho.get)
    return melhor if brilho[melhor] >= BRILHO_ABA_ATIVA else None


def janela_do_chefe(agora, horarios=HORARIOS_CHEFE):
    """(inicio, fim) do horario do Chefao Global em que `agora` (datetime) esta, ou None."""
    for (h0, m0), (h1, m1) in horarios:
        ini = agora.replace(hour=h0, minute=m0, second=0, microsecond=0)
        fim = agora.replace(hour=h1, minute=m1, second=0, microsecond=0)
        if ini <= agora < fim:
            return ini, fim
    return None


def proximo_chefe(agora, horarios=HORARIOS_CHEFE):
    """Inicio (datetime) do proximo horario do Chefao Global depois de `agora`."""
    out = []
    for (h0, m0), _fim in horarios:
        ini = agora.replace(hour=h0, minute=m0, second=0, microsecond=0)
        out.append(ini if ini > agora else ini + datetime.timedelta(days=1))
    return min(out)


def ler_horarios(texto):
    """'12:00-13:00,21:00-22:00' -> [((12, 0), (13, 0)), ((21, 0), (22, 0))]."""
    out = []
    for parte in texto.split(","):
        ini, fim = parte.strip().split("-")
        hm = lambda t: tuple(int(x) for x in (t.strip().split(":") + ["0"])[:2])
        out.append((hm(ini), hm(fim)))
    return out


def texto_horarios(horarios):
    return " e ".join(f"{h0}h{m0:02d}-{h1}h{m1:02d}" for (h0, m0), (h1, m1) in horarios)


# ---------------------------------------------------------------------------
class Navegador:
    def __init__(self, io, detector, rota=None, usar_tarefas=True, uma_vez=False, simular=False,
                 dormir=time.sleep, agora=time.time, log=print, atirador=None, reg=None, dificuldade=None,
                 metricas=None, chefe=None, horarios_chefe=None, relogio=datetime.datetime.now, cartas_em=None,
                 estat=None, catalogo=None, tarefas_a_cada=1):
        """chefe: None (sem Chefao Global) | "horarios" (rota + Chefao nos horarios) | "so" (opcao C: so o Chefao,
        comecando agora; depois espera os horarios)."""
        self.io, self.det = io, detector
        self.chefe_modo = chefe
        self.estat = estat                # estatisticas.Estatisticas (contadores do painel) ou None
        self.catalogo = catalogo          # drops.Catalogo (o que veio nas cartas) ou None
        self.tarefas_a_cada = max(1, int(tarefas_a_cada))   # coleta as tarefas a cada N voltas (lutando um chefe so: 10)
        self.drops_contados, self.cartas_3_em = False, None
        self.cartas_em = set(cartas_em) if cartas_em else None   # None = abre as cartas de todas as instancias
        self.cartas_puladas = False
        self.horarios = horarios_chefe or HORARIOS_CHEFE
        self.relogio = relogio            # relogio de parede (datetime) para os horarios
        self.no_chefe = chefe == "so"     # lutando o Chefao Global agora (a rota fica pausada onde estava)
        self.chefe_forcado = chefe == "so"   # opcao C: tenta ja, mesmo fora do horario
        self.chefe_feito_em = None        # quando o servidor derrubou o chefao (nao volta no mesmo horario)
        self.chefe_derrotas = 0
        self.chefe_tentativas_marcar = 0
        self.chefe_aviso = -1e9
        self.tentativas_aba = 0
        self.tentativas_pagina = 0
        self.fase = 1                     # A Ultima Luta tem 2 fases (a 2a comeca depois do painel pequeno de cartas)
        self.cartas_p_clicadas, self.cartas_p_em = 0, None
        self.metr = metricas              # metricas.Metricas (cronometro de lutas/instancias/voltas) ou None
        self.luta_ativa = False
        self.rng = random.Random()
        self.cartas_escolhidas, self.cartas_clicadas_em, self.cartas_rodadas = None, None, 0
        self.cartas_max_viradas, self.quadro_cartas = 0, None
        self.dificuldade = dificuldade    # None = a de cada instancia (DIFICULDADE_DA_INSTANCIA) | "NORMAL" | "DIFICIL" | "HEROI"
        self.perks_tentativas = 0         # reposicao dos perks Z/X/C na sala (Gato Preto)
        self.clicou_cfg = None            # instancia clicada por ultimo na configuracao
        self.confirmada = None            # instancia confirmada ("Sim") por ultimo: a sala deve mostrar ela
        self.dificuldade_clicada = False
        self.reg = reg                    # gravacao do bot em acao (registro.Registro) ou None
        self.ultimo_quadro = None
        self.achadas_atual = []
        self.ultimo_conhecido = None
        self.ultima_recuperacao = -99.0
        self.recuperacoes = 0
        self.ultimo_estado_reg = None
        self.adotar_primeira = True       # 1a sala "pronta" que o bot ve: segue a partir dela; depois, ordem estrita
        self.atirador = atirador          # None = a batalha e sua; senao ele joga os turnos
        self.em_batalha = False
        self.fora_da_batalha_desde = None
        self.rota = rota or list(ROTA_PADRAO)
        self.super_rota_cupons = self.rota in (ROTAS["U"][1], ROTAS["T"][1])
        self.cupom_pendente = None
        self.ultima_coleta_tarefas = 0
        # Gato Preto sozinho tem recompensa com escolha manual; nunca abrir/coletar tarefas.
        self.usar_tarefas, self.uma_vez, self.simular = (usar_tarefas or self.super_rota_cupons) and self.rota != ["GATO_PRETO"], uma_vez, simular
        self.dormir, self.agora, self.log = dormir, agora, log
        self.k = 1.0
        self.modo = 0                     # indice em MODOS_ENTRADA
        self.falhas_clique = 0
        self.parar, self.pausado = False, False
        self.pausa_desde, self.pausado_total = None, 0.0
        self.ultima_calib_pedida = -1e9
        self.tela_desde, self.tela_atual = None, None      # vigia: ha quanto tempo esta na mesma tela
        self.preso_aviso, self.preso_vezes = -1e9, 0
        self.voltas = 0
        self.novo_ciclo()
        self.cartas_vistas = False
        self.perdido_desde = None
        self.batalha_desde = None
        self.ultimo_aviso = 0.0
        self.pontos_tarefa = Counter()

    # ---------- estado da rota ----------
    def novo_ciclo(self):
        self.idx = 0
        self.fase = 1
        self.cartas_p_clicadas, self.cartas_p_em = 0, None
        self.run_completa = False
        self.tarefas_ok = False
        self.cartas_vistas = False
        self.tentativas_carta = Counter()
        self.cartas_escolhidas, self.cartas_rodadas, self.cartas_max_viradas = None, 0, 0
        self.tentativas_slot = 0
        self.tentativas_cfg = 0
        self.trocas_pronta = 0
        self.avisou_ocupado = False
        self.lutou = False
        self.confirmada = None

    @property
    def instancia(self):
        if self.no_chefe:
            return CHEFE
        return self.rota[min(self.idx, len(self.rota) - 1)]

    @property
    def instancia_batalha(self):
        """Nome da instancia para o atirador/metricas: o Pericao fora do horario e um chefe COMUM (vida propria)."""
        if self.instancia == "ULTIMA_LUTA":
            return f"ULTIMA_LUTA_F{self.fase}"
        return "PERICAO_COMUM" if self.instancia == CHEFE and not self.no_chefe else self.instancia

    @property
    def instancia_metr(self):
        """Nome da instancia para o cronometro de INSTANCIA (menus + luta + cartas): so a base (as fases entram na mesma)."""
        return "PERICAO_COMUM" if self.instancia == CHEFE and not self.no_chefe else self.instancia

    # ---------- Chefao Global ----------
    def chefe_pendente(self, agora=None):
        """Estamos num horario do Chefao Global em que o servidor ainda nao o derrubou?"""
        agora = agora or self.relogio()
        jan = janela_do_chefe(agora, self.horarios)
        return jan is not None and (self.chefe_feito_em is None or self.chefe_feito_em < jan[0])

    def atualizar_chefe(self, estado):
        """Fora da batalha: entra/sai do Chefao Global conforme o horario. Devolve True se o bot deve so ESPERAR
        (opcao C fora do horario)."""
        if not self.chefe_modo:
            return False
        agora = self.relogio()
        pendente = self.chefe_pendente(agora)
        if self.no_chefe:
            if pendente or self.chefe_forcado:
                return False
            self.no_chefe = False
            if self.chefe_modo == "horarios":
                self.log(f"[CHEFAO] fim do horario do Chefao Global: voltando para a rota ({self.instancia})")
                return False
        if pendente:
            if estado in ("POPUP_SOZINHO", "POPUP_SOZINHO2", "POPUP_SOZINHO3", "POPUP_AVISO") or (self.chefe_modo == "horarios" and estado not in (
                    "SALA_VAZIA", "SALA", "CONFIG_VAZIA", "CONFIG_SEL", "CONFIG", "CENTRAL", "MAPA")
                    and not estado.startswith("PRONTA_")):
                return False              # no meio de outra coisa (tarefas, comecando a luta): troca na proxima tela
            self.no_chefe = True
            self.chefe_derrotas = self.chefe_tentativas_marcar = 0
            self.log("[CHEFAO] hora do Chefao Global (" + texto_horarios(self.horarios) + "): indo para o Pericao" +
                     (f" (a rota fica pausada; depois volto para {self.rota[min(self.idx, len(self.rota) - 1)]})"
                      if self.chefe_modo == "horarios" else ""))
            return False
        if self.chefe_modo == "so":
            t = self.agora()
            if t - self.chefe_aviso >= CHEFE_AVISO_ESPERA:
                self.chefe_aviso = t
                self.log(f"[CHEFAO] esperando o proximo Chefao Global: {proximo_chefe(agora, self.horarios):%d/%m %H:%M} "
                         f"(horarios: {texto_horarios(self.horarios)}). F10 sai.")
            for _ in range(10):
                self.dormir(1.0)
                self.teclas()
                if self.parar:
                    break
            return True
        return False

    def desistir_do_chefe(self, motivo):
        self.log(f"[CHEFAO] ! {motivo}: desisto do Chefao Global ate o proximo horario" +
                 (f"; voltando para a rota ({self.rota[min(self.idx, len(self.rota) - 1)]})" if self.chefe_modo == "horarios" else ""))
        self.no_chefe = self.chefe_forcado = False
        self.chefe_feito_em = self.relogio()

    def preparar_pagina(self, f):
        """A lista de instancias da aba normal rola: os Devoradores ficam na pagina 2. Clica a seta ate a pagina certa (confere pelo
        desenho do 1o quadro); True = rolou (o quadro certo so aparece depois)."""
        quer = PAGINA_NA_CONFIG.get(self.instancia, 1)
        atual = pagina_da_lista(f) if f is not None else None
        if atual is None or atual == quer:
            self.tentativas_pagina = 0
            return False
        self.tentativas_pagina += 1
        if self.tentativas_pagina > 6:
            self.log(f"   ! nao consegui rolar a lista para a pagina {quer}; sigo assim mesmo")
            self.tentativas_pagina = 0
            return False
        ponto = LISTA_SETA["baixo" if quer > atual else "cima"] if self.tentativas_pagina % 2 else LISTA_SETA_ALTERNATIVA
        self.log(f"[CONFIG] lista na pagina {atual}; {self.instancia} fica na pagina {quer} -> clicando em {ponto}")
        self.clicar(ponto)
        self.dormir(0.8)
        return True

    def abrir_aba(self, f):
        """Na configuracao: a aba da instancia desejada (normal / do evento) esta aberta? Se nao, clica nela e devolve
        True (o quadro so aparece depois que a aba troca)."""
        quer = ABA_DA_INSTANCIA.get(self.instancia, "normal")
        ativa = aba_ativa(f) if f is not None else None
        if ativa is None or ativa == quer or self.tentativas_aba >= 3:
            self.tentativas_aba = 0
            return False
        self.tentativas_aba += 1
        self.log(f"[CONFIG] aba aberta: {ativa}; {self.instancia} fica na aba '{quer}' -> clicando nela")
        self.clicar(ABAS_CONFIG[quer])
        self.dormir(0.8)
        return True

    # ---------- visao ----------
    def ver(self):
        img = self.io.capturar()
        if img is None:
            return None, None
        self.k = img.shape[1] / LARGURA_REF
        f = em_1280(img)
        self.ultimo_quadro = f
        self.achadas_atual = self.det.detectar(estados_mod.normalizar(f))
        if "TAREFA" not in self.achadas_atual and painel_tarefa_visivel(f):
            if self.achadas_atual and self.achadas_atual[0] == "CLIQUE_JOGO":
                self.achadas_atual.insert(1, "TAREFA")
            elif not self.achadas_atual or not self.achadas_atual[0].startswith("POPUP_"):
                self.achadas_atual.insert(0, "TAREFA")
        return f, self.achadas_atual

    def estado_estavel(self):
        """Tela detectada de forma igual em 2 leituras seguidas (None = desconhecida/transicao)."""
        _, a = self.ver()
        if not a:
            return None
        self.dormir(ESPERA_CONFIRMAR_TELA)
        _, b = self.ver()
        return a[0] if b and a[0] == b[0] else None

    def estado_rapido(self):
        _, e = self.ver()
        return e[0] if e else None

    # ---------- acoes ----------
    def esperar_pausa(self):
        while self.pausado and not self.parar:
            self.dormir(0.3)
            self.teclas()

    arquivo_parar = None              # o painel (painel.py) pede para parar criando este arquivo
    pausa_pelo_painel = False
    arquivo_pausar = None             # ...e para pausar/continuar criando/apagando este

    def _pausar(self, origem):
        self.pausado, self.pausa_desde = True, self.agora()
        self.log(f"PAUSADO ({origem}). O relogio das lutas/voltas para ate continuar.")

    def _continuar(self):
        dur = self.agora() - self.pausa_desde if self.pausa_desde is not None else 0.0
        self.pausado, self.pausa_desde = False, None
        self.pausado_total += dur
        if self.batalha_desde is not None:
            self.batalha_desde += dur
        if self.metr:
            self.metr.descontar_pausa(dur)
        if self.estat:
            self.estat.pausa(dur)
        self.log(f"Continuando. Ficou pausado {fmt_tempo(dur)} (total pausado: {fmt_tempo(self.pausado_total)}); "
                 f"esse tempo nao entra nos cronometros.")

    def teclas(self):
        if self.arquivo_parar and os.path.exists(self.arquivo_parar):
            try:
                os.remove(self.arquivo_parar)
            except OSError:
                pass
            self.log("Parada pedida pelo painel.")
            self.parar = True
        if self.arquivo_pausar:
            quer = os.path.exists(self.arquivo_pausar)
            if quer and not self.pausado:
                self._pausar("botao do painel")
            elif not quer and self.pausado and self.pausa_pelo_painel:
                self._continuar()
            self.pausa_pelo_painel = quer
        if self.io.tecla_apertada(VK_F10):
            self.parar = True
        if self.io.tecla_apertada(VK_F8):
            if self.pausado:
                self._continuar()
                if self.arquivo_pausar and os.path.exists(self.arquivo_pausar):
                    try:
                        os.remove(self.arquivo_pausar)    # F8 continua: o painel tambem volta ao estado "rodando"
                    except OSError:
                        pass
                    self.pausa_pelo_painel = False
            else:
                self._pausar("F8")
            self.dormir(0.5)

    def clicar(self, ponto):
        self.esperar_pausa()
        x, y = ponto
        if self.reg:
            self.reg.evento("bot_clique", [self.reg.frame(self.ultimo_quadro, "clique_antes")], ponto=list(ponto),
                            modo=MODOS_ENTRADA[self.modo], instancia=self.instancia, idx=self.idx, estado=self.ultimo_estado_reg)
        if self.simular:
            self.log(f"   [simulando] clicaria em {ponto}")
            return
        self.io.clicar(int(x * self.k), int(y * self.k), MODOS_ENTRADA[self.modo])

    def clicar_e_verificar(self, estado, ponto, espera=4.0, descricao=""):
        """Clica e espera a tela mudar. Sem efeito 2x seguidas -> troca o modo de entrada."""
        self.log(f"[{estado}] {descricao} {ponto}")
        self.clicar(ponto)
        if self.simular:
            self.dormir(1.0)
            return True
        t0 = self.agora()
        while self.agora() - t0 < espera:
            self.dormir(0.4)
            if self.estado_rapido() != estado:
                self.falhas_clique = 0
                if self.reg:
                    self.reg.evento("bot_clique_ok", [self.reg.frame(self.ultimo_quadro, "clique_depois")], de=estado)
                return True
        self.falhas_clique += 1
        self.log(f"   ! clique sem efeito ({self.falhas_clique}x, modo '{MODOS_ENTRADA[self.modo]}')")
        if self.reg:
            self.reg.evento("clique_sem_efeito", [self.reg.frame(self.ultimo_quadro, "clique_sem_efeito")], estado=estado,
                            ponto=list(ponto), vezes=self.falhas_clique)
        if self.falhas_clique >= 2:
            self.modo = (self.modo + 1) % len(MODOS_ENTRADA)
            self.falhas_clique = 0
            self.log(f"   ! trocando o modo de entrada para '{MODOS_ENTRADA[self.modo]}'. Se continuar sem "
                     "efeito, me mande o log e um print.")
        return False

    def finalizar_instancia(self):
        """Chamado ao sair das cartas/batalha: a instancia atual acabou."""
        if not self.cartas_vistas:
            if self.lutou and self.no_chefe:
                self.lutou = False
                self.chefe_derrotas += 1
                self.log(f"   [CHEFAO] a luta acabou sem cartas (rodada 200? o boneco morreu?) - {self.chefe_derrotas}a derrota; entro de novo.")
                if self.chefe_forcado and not self.chefe_pendente() and self.chefe_derrotas >= CHEFE_DERROTAS_FORA_DO_HORARIO:
                    self.desistir_do_chefe(f"{self.chefe_derrotas} derrotas fora do horario ({texto_horarios(self.horarios)})")
                return
            if self.lutou:
                self.lutou = False
                self.log(f"   [ORDEM] ! a luta de {self.instancia} acabou SEM passar pelas cartas; repito {self.instancia}.")
                if self.reg:
                    self.reg.evento("ordem_sem_cartas", [self.reg.frame(self.ultimo_quadro, "sem_cartas")], instancia=self.instancia, idx=self.idx)
            return
        self.cartas_vistas = False
        self.lutou = False
        self.confirmada = None
        self.tentativas_carta = Counter()
        pulou, self.cartas_puladas = self.cartas_puladas, False
        if self.cartas_max_viradas < CARTAS_VIRADAS_PARA_PAGAR and not pulou:
            self.log(f"   ! [CARTAS] so {self.cartas_max_viradas} carta(s) abriram em {self.instancia} (o tempo da tela acabou?)")
            if self.reg:
                self.reg.evento("cartas_incompletas", [self.reg.frame(self.quadro_cartas, "cartas_incompletas")],
                                instancia=self.instancia, viradas=self.cartas_max_viradas)
        self.cartas_escolhidas, self.cartas_rodadas, self.cartas_max_viradas = None, 0, 0
        self.drops_contados, self.cartas_3_em = False, None
        if self.no_chefe:
            # vitoria no Chefao Global = o servidor inteiro derrubou o chefao (a luta individual so acaba assim)
            if self.metr:
                self.metr.instancia_fim(CHEFE)
            if self.estat:
                self.estat.chefao()
            self.no_chefe = self.chefe_forcado = False
            self.chefe_feito_em = self.relogio()
            self.log("*** [CHEFAO] Chefao Global derrotado pelo servidor! Recompensas pelo dano total de cada um. " +
                     (f"Voltando para a rota: {self.instancia} ***" if self.chefe_modo == "horarios" else
                      f"Proximo: {proximo_chefe(self.chefe_feito_em, self.horarios):%d/%m %H:%M} ***"))
            if self.reg:
                self.reg.evento("chefe_derrotado", [], proxima=self.instancia)
            return
        antes = self.instancia
        self.idx += 1
        if self.metr:
            self.metr.instancia_fim("PERICAO_COMUM" if antes == CHEFE else antes)
        self.fase = 1
        if self.super_rota_cupons:
            self.cupom_pendente = FIM_ROTA_CUPOM.get(self.idx) if self.idx <= len(self.rota) else None
        if self.idx >= len(self.rota):
            self.run_completa = True
            self.log(f"*** {antes} concluida: rota completa ({self.voltas + 1}a volta)." +
                     (" Falta coletar as tarefas. ***" if self.usar_tarefas else " ***"))
        else:
            self.log(f"[ORDEM] {antes} concluida. Proxima: {self.instancia} (idx {self.idx})")
        if self.reg:
            self.reg.evento("ordem", [], concluida=antes, proxima=None if self.run_completa else self.instancia, idx=self.idx,
                            run_completa=self.run_completa)

    def agir(self, estado):
        if estado != self.tela_atual:
            self.tela_atual, self.tela_desde, self.preso_vezes = estado, self.agora(), 0
        elif estado not in ("BATALHA", "CARTAS", "POPUP_CARTA", "CARTAS_P", "TAREFA", "CLIQUE_JOGO"):
            self.vigiar(estado, self.tela_desde)
        if self.reg and estado != self.ultimo_estado_reg:
            self.reg.evento("estado", [self.reg.frame(self.ultimo_quadro, "estado_" + estado)], estado=estado,
                            instancia=self.instancia, idx=self.idx, voltas=self.voltas, run_completa=self.run_completa)
        self.ultimo_estado_reg = estado
        self.ultimo_conhecido = estado
        self.recuperacoes = 0
        if self.luta_ativa and estado not in ("BATALHA", "CLIQUE_JOGO"):
            self.luta_ativa = False
            if self.metr:
                self.metr.batalha_fim(venceu=estado in CARTAS_ESTADOS)
            if self.estat:
                self.estat.luta(self.instancia_batalha, estado in CARTAS_ESTADOS)
        if estado not in ("CARTAS", "POPUP_CARTA", "CARTAS_P", "BATALHA", "CLIQUE_JOGO"):
            self.finalizar_instancia()
            if self.atualizar_chefe(estado):
                return                    # opcao C fora do horario: esperando
        if estado != "BATALHA":
            self.batalha_desde = None

        sala = estado in ("SALA_VAZIA", "SALA") or estado.startswith("PRONTA_")
        if self.metr and (not self.run_completa or self.no_chefe) and (sala or estado.startswith("CONFIG")) and not (sala and self.cupom_pendente):
            self.metr.instancia_inicio(self.instancia_metr, self.voltas)
        if sala and self.cupom_pendente and not self.no_chefe:
            if not self.tarefas_ok and self.usar_tarefas:
                if not self.clicar_e_verificar(estado, SALA_ICONE_TAREFAS, descricao=f"coletar missao da rota {self.cupom_pendente}"):
                    self.pontos_tarefa["abrir"] += 1
                    if self.pontos_tarefa["abrir"] >= 3:
                        self.log("   ! nao consegui abrir Tarefas; segmento sem cupons confirmados")
                        self.tarefas_ok = True
                return
            if self.metr:
                self.metr.rota_cupom_fim(self.cupom_pendente, CUPONS_POR_ROTA[self.cupom_pendente],
                                        self.ultima_coleta_tarefas if self.usar_tarefas else 0)
            self.log(f"[CUPONS] segmento {self.cupom_pendente} concluido; {self.ultima_coleta_tarefas} tarefa(s) coletada(s)")
            self.cupom_pendente = None
            self.ultima_coleta_tarefas = 0
            if not self.run_completa:
                self.tarefas_ok = False
        if sala and self.run_completa and not self.no_chefe:
            # a rota acabou: coleta as tarefas e so entao comeca outra volta (a sala pode continuar mostrando a
            # ultima instancia - antes o bot "aceitava" essa sala e repetia o Minhocao sem parar)
            if self.usar_tarefas and not self.super_rota_cupons and not self.tarefas_ok and (self.voltas + 1) % self.tarefas_a_cada == 0:
                if not self.clicar_e_verificar(estado, SALA_ICONE_TAREFAS, descricao="abrir Tarefas"):
                    self.pontos_tarefa["abrir"] += 1
                    if self.pontos_tarefa["abrir"] >= 3:
                        self.log("   ! nao consegui abrir as Tarefas; sigo sem coletar.")
                        self.tarefas_ok = True
                return
            self.voltas += 1
            if self.estat:
                self.estat.volta()
            self.log(f"=== Volta {self.voltas} concluida. Recomecando na mesma sala pela {self.rota[0]}. ===")
            if self.metr:
                self.metr.volta_fim(self.voltas)
            self.novo_ciclo()
            self.pontos_tarefa.clear()
            if self.reg:
                self.reg.evento("volta", [], voltas=self.voltas)
            if self.uma_vez:
                self.parar = True
                return

        if estado == "CLIQUE_JOGO":
            por_baixo = next((e for e in self.achadas_atual if e != "CLIQUE_JOGO"), None)
            ponto = FOCO_PONTO_NEUTRO.get(por_baixo, FOCO_PONTO_PADRAO)
            self.clicar_e_verificar(estado, ponto, descricao=f"jogo sem foco (tela por baixo: {por_baixo}); clicando em area neutra")
        elif estado in CLIQUE_SIMPLES:
            self.clicar_e_verificar(estado, CLIQUE_SIMPLES[estado], descricao="clicando")
        elif estado == "CENTRAL":
            if self.run_completa:
                self.voltas += 1
                if self.estat:
                    self.estat.volta()
                self.log(f"=== Volta {self.voltas} concluida (tarefas coletadas). ===")
                if self.metr:
                    self.metr.volta_fim(self.voltas)
                self.novo_ciclo()
                if self.uma_vez:
                    self.parar = True
                    return
            self.clicar_e_verificar(estado, CENTRAL_JOGAR, descricao="Jogar")
        elif estado == "SALA_VAZIA":
            f, _e = self.ver()
            abertos = slots_abertos(f) if f is not None else []
            if abertos and self.tentativas_slot < 6:
                self.tentativas_slot += 1
                self.log(f"[{estado}] fechando vaga aberta da sala {abertos[0]} ({len(abertos)} aberta(s))")
                self.clicar(abertos[0])
                self.dormir(0.9)
                return
            self.clicar_e_verificar(estado, SALA_TROCAR_INSTANCIA, descricao=f"escolher instancia ({self.instancia})")
        elif estado == "CONFIG_VAZIA":
            self.adotar_primeira = False
            self.dificuldade_clicada = False
            if self.abrir_aba(self.ultimo_quadro) or self.preparar_pagina(self.ultimo_quadro):
                return
            if self.no_chefe:
                self.chefe_tentativas_marcar += 1
                if self.chefe_tentativas_marcar > CHEFE_TENTATIVAS_MARCAR:
                    self.desistir_do_chefe("o quadro do Pericao nao responde na configuracao (evento fechado?)")
                    return
            self.clicou_cfg = self.instancia
            self.clicar_e_verificar(estado, INSTANCIA_NA_CONFIG[self.instancia], descricao=f"selecionar {self.instancia}")
        elif estado in ("CONFIG_SEL", "CONFIG"):
            # CONFIG = janela de configuracao com uma instancia marcada cuja arte o detector nao conhece (Rota Sul...)
            self.adotar_primeira = False
            f, _e = self.ver()
            sel = instancia_selecionada(f) if f is not None else None
            if (sel is None and f is not None and self.clicou_cfg == self.instancia and not tem_modelo("cfg", self.instancia)
                    and self.tentativas_cfg >= 1 and tem_textura(f, CFG_REGIAO)
                    and self.det.pontuar(estados_mod.normalizar(f)).get("CONFIG_VAZIA", 0) < 0.45):
                # instancia nova (sem modelo da arte): o bot clicou nela e a arte ja carregou -> aprende
                self.log(f"   [APRENDI] arte de {self.instancia} na configuracao (instancia nova)")
                aprender_modelo("cfg", self.instancia, f, CFG_REGIAO)
                sel = self.instancia
            if sel == self.instancia:
                self.tentativas_cfg = 0
                self.chefe_tentativas_marcar = 0
                dif = self.dificuldade or DIFICULDADE_DA_INSTANCIA.get(self.instancia)
                if dif and not self.dificuldade_clicada:
                    self.dificuldade_clicada = True
                    self.log(f"[CONFIG_SEL] dificuldade {dif}")
                    self.clicar(DIFICULDADE_BOTAO[dif])
                    self.dormir(0.6)
                    return
                if self.clicar_e_verificar(estado, CONFIG_SIM, descricao=f"confirmar {self.instancia}"):
                    self.confirmada = self.instancia
                    self.dificuldade_clicada = False
            else:
                self.tentativas_cfg += 1
                if sel is None and self.tentativas_cfg <= 3:
                    self.dormir(0.7)                       # a arte pode ainda estar carregando
                    return
                if self.abrir_aba(f) or self.preparar_pagina(f):
                    return
                if self.no_chefe:
                    self.chefe_tentativas_marcar += 1
                    if self.chefe_tentativas_marcar > CHEFE_TENTATIVAS_MARCAR:
                        self.desistir_do_chefe("o Pericao nao fica marcado na configuracao (evento fechado?)")
                        return
                self.log(f"[CONFIG_SEL] marcada: {sel or 'nenhuma/desconhecida'}; quero {self.instancia} -> clicando nela")
                self.clicou_cfg = self.instancia
                self.dificuldade_clicada = False
                self.clicar(INSTANCIA_NA_CONFIG[self.instancia])
                self.dormir(1.0)
        elif estado == "SALA":
            # sala com uma instancia cuja arte nao tem tela propria (instancia nova da rota): reconhece pela arte
            # aprendida; se acabamos de confirmar a instancia na configuracao, e ela -> aprende a arte
            f, _e = self.ver()
            nome = instancia_na_sala(f) if f is not None else None
            if nome and nome.endswith("_FASE2"):
                nome = nome[:-6]                          # a sala da Ultima Luta ja com a 2a fase pronta (so da Inicio)
                if nome == self.instancia and self.fase != 2:
                    self.log(f"[FASE] sala de {nome} com a 2a fase pronta")
                    self.fase = 2
            if nome is None and f is not None and self.confirmada == self.instancia:
                self.dormir(1.0)                          # a arte pode estar terminando de carregar
                f, achadas = self.ver()
                if f is None or (achadas and achadas[0] != "SALA"):
                    return
                if tem_textura(f, SALA_ARTE):
                    self.log(f"   [APRENDI] arte de {self.instancia} na sala (instancia nova)")
                    aprender_modelo("sala", self.instancia, f, SALA_ARTE)
                nome = self.instancia
            if nome is None:
                self.clicar_e_verificar(estado, SALA_TROCAR_INSTANCIA, descricao=f"sala com instancia desconhecida: escolher {self.instancia}")
                return
            self.sala_pronta(estado, nome)
        elif estado.startswith("PRONTA_"):
            self.sala_pronta(estado, estado.split("_", 1)[1])
        elif estado == "CARTAS_P":
            # painel PEQUENO (3x3, fase 1 da Ultima Luta): 1 carta; depois a sala volta com a 2a fase pronta
            self.lutou = False
            self.fase = 2
            agora = self.agora()
            if self.cartas_p_clicadas < 3 and (self.cartas_p_em is None or agora - self.cartas_p_em >= CARTAS_P_REPETIR_APOS):
                p = self.rng.choice(CARTAS_P_POS)
                self.log(f"[CARTAS] painel pequeno (fase 1): abrindo a carta {p}")
                self.clicar(p)
                self.cartas_p_clicadas += 1
                self.cartas_p_em = agora
            self.dormir(0.5)
        elif estado == "CARTAS":
            self.cartas_p_clicadas, self.cartas_p_em = 0, None
            self.cartas_vistas = True
            if self.cartas_em is not None and self.instancia not in self.cartas_em and not self.no_chefe:
                if not self.cartas_puladas:
                    self.cartas_puladas = True
                    self.log(f"[CARTAS] nao abro as cartas de {self.instancia} (so completa a missao); espero a tela passar")
                self.dormir(1.0)
                return
            f, _e = self.ver()
            if f is None:
                return
            self.quadro_cartas = f
            pontos_cartas = CARTAS_TODAS
            costas = cartas_de_costas(f, pontos_cartas)
            viradas = len(pontos_cartas) - len(costas)
            self.cartas_max_viradas = max(self.cartas_max_viradas, viradas)
            if viradas >= CARTAS_VIRADAS_PARA_PAGAR:
                self.contar_drops(f, costas)
                self.dormir(1.0)       # ja viramos as 3 (ou a contagem acabou e tudo abriu)
                return
            if self.cartas_escolhidas is None:
                # sorteia 3 cartas e clica nas 3 em seguida (a tela tem cronometro de 15 s; com o PC ocupado o jogo
                # demora a mostrar a carta virando - esperar cada uma virar antes da proxima estourava o tempo).
                # O jogo trava na 3a: cliques a mais nao abrem outra.
                livres = [p for p in pontos_cartas if p in costas] or list(pontos_cartas)
                self.cartas_escolhidas = self.rng.sample(livres, min(CARTAS_VIRADAS_PARA_PAGAR, len(livres)))
                self.log(f"[CARTAS] cartas sorteadas: {self.cartas_escolhidas}")
                for p in self.cartas_escolhidas:
                    self.clicar(p)
                    self.dormir(CARTAS_ENTRE_CLIQUES)
                self.cartas_clicadas_em = self.agora()
                return
            pend = [p for p in self.cartas_escolhidas if p in costas]
            if pend and self.agora() - self.cartas_clicadas_em >= CARTAS_REPETIR_APOS and self.cartas_rodadas < 5:
                self.cartas_rodadas += 1
                if self.cartas_rodadas > 2:
                    # as sorteadas nao viram (clique nao pega nessa posicao?): troca por outras de costas
                    outras = [p for p in costas if p not in self.cartas_escolhidas]
                    novas = self.rng.sample(outras, min(len(pend), len(outras)))
                    self.cartas_escolhidas = [p for p in self.cartas_escolhidas if p not in pend] + novas
                    pend = novas
                self.log(f"[CARTAS] {viradas} virada(s); clicando de novo: {pend}")
                for p in pend:
                    self.clicar(p)
                    self.dormir(0.4)
                self.cartas_clicadas_em = self.agora()
                return
            self.dormir(0.4)
        elif estado == "TAREFA":
            if self.usar_tarefas:
                self.coletar_tarefas()
            else:
                self.tarefas_ok = True
                self.log("[TAREFA] coleta desativada; fechando sem tocar nas recompensas")
                self.clicar_e_verificar("TAREFA", TAREFA_FECHAR, descricao="fechar painel sem coletar")
        elif estado == "BATALHA":
            self.lutou = True
            if self.batalha_desde is None:
                self.batalha_desde = self.agora()
                self.em_batalha = True
                if not self.luta_ativa:
                    self.luta_ativa = True
                    if self.metr:
                        self.metr.batalha_inicio(self.instancia_batalha, self.voltas)
                self.log("[BATALHA] " + ("o bot joga os turnos." if self.atirador else
                                         "em luta - o tiro automatico e opcional (--atirar); jogue voce mesmo."))
            if self.atirador:
                self.atirador.passo()
                self.dormir(0.05)
            else:
                self.dormir(1.5)
        else:
            self.dormir(1.0)

    def repor_perks(self, f):
        """Gato Preto: os perks POW (Z, X, C) acabam depois do uso e so se repoe na SALA: clica no perk em "Ferramentas a comprar"
        uma vez por quadro vazio. True = estava repondo (volta depois para conferir). Se nao repuser (sem vigor?), desiste."""
        import leitura as L
        vazios = [k for k, cheio in L.perks_cheios(f).items() if not cheio]
        if not vazios:
            if self.perks_tentativas:
                self.log("[PERKS] Z, X e C repostos")
            return False
        if self.perks_tentativas >= 2:
            self.log(f"   ! [PERKS] nao consegui repor {', '.join(vazios)} (falta vigor?); sigo sem eles")
            return False
        self.perks_tentativas += 1
        self.log(f"[PERKS] quadros vazios: {', '.join(vazios)}; comprando {len(vazios)} perk(s) POW (tentativa {self.perks_tentativas})")
        for _ in vazios:
            self.clicar(L.PERK_COMPRAR)
            self.dormir(0.7)
        self.clicar(FOCO_PONTO_PADRAO)          # tira o balao que o mouse parado em cima do icone abre
        self.dormir(0.5)
        return True

    def contar_drops(self, f, costas):
        """Cartas viradas: le o icone de cada uma das SUAS 3 cartas (esperando ~1 s a animacao) e conta no catalogo."""
        if self.drops_contados or not self.catalogo or not self.cartas_escolhidas:
            return
        agora = self.agora()
        if self.cartas_3_em is None:
            self.cartas_3_em = agora
            return
        if agora - self.cartas_3_em < 1.0:
            return
        self.drops_contados = True
        achados = []
        for p in self.cartas_escolhidas:
            if p in costas:
                continue
            chave = self.catalogo.reconhecer(f, p)
            if chave:
                achados.append(chave)
                if self.estat:
                    self.estat.drop(chave)
        if achados:
            self.log("[CARTAS] vieram: " + ", ".join(self.catalogo.nome_bonito(c) for c in achados))

    def sala_pronta(self, estado, nome):
        """Sala com a instancia `nome` escolhida: confere a ordem, fecha as vagas e da Inicio."""
        if nome != self.instancia:
            if self.adotar_primeira and nome in self.rota and not self.no_chefe:
                self.log(f"   sala ja esta em {nome}; sigo a partir dela (so na 1a vez).")
                self.idx = self.rota.index(nome)
            else:
                if self.adotar_primeira and nome in self.rota:
                    self.idx = self.rota.index(nome)      # depois do Chefao Global, a rota segue daqui
                    self.adotar_primeira = False
                self.trocas_pronta += 1
                if self.trocas_pronta > 3 and self.no_chefe:
                    self.desistir_do_chefe(f"nao consegui trocar a sala de {nome} para o Pericao")
                    return
                if self.trocas_pronta > 3 and nome in self.rota:
                    self.log(f"   ! nao consegui trocar a sala de {nome} para {self.instancia}; sigo com {nome}.")
                    self.idx = self.rota.index(nome)
                else:
                    # (instancia de OUTRA rota na sala: troca sempre - lutar nela baguncaria a ordem)
                    self.clicar_e_verificar(estado, SALA_TROCAR_INSTANCIA,
                                            descricao=f"sala esta em {nome} mas a ordem pede {self.instancia}: trocando")
                    return
        self.adotar_primeira = False
        self.trocas_pronta = 0
        f, _e = self.ver()
        vagas = estado_vagas(f) if f is not None else []
        if "ocupado" in vagas and not self.avisou_ocupado:
            self.avisou_ocupado = True
            self.log(f"   ! outro jogador entrou na sala (vagas: {vagas}). Nao mexo na vaga dele; sigo.")
        abertos = [c for c, e in zip(SLOTS_SALA, vagas) if e == "aberto"]
        if abertos and self.tentativas_slot < 6:
            self.tentativas_slot += 1
            self.log(f"[{estado}] fechando vaga aberta {abertos[0]} (vagas: {vagas})")
            self.clicar(abertos[0])
            self.dormir(0.9)
            return
        est_sala = estrategias.estrategia(self.instancia_batalha)
        if (est_sala.get("repor_perks") or est_sala.get("perks")) and f is not None and self.repor_perks(f):
            return
        self.perks_tentativas = 0
        self.clicar_e_verificar(estado, SALA_INICIO, descricao=f"Inicio ({nome})", espera=6.0)

    def escolher_material_leste(self, f, popup):
        """Escolhe o primeiro material irrelevante e confirma somente na missao Super Rota Leste."""
        leste_esperada = self.cupom_pendente == "L" or self.rota == ROTAS["L"][1]
        if not leste_esperada or not tarefa_leste_selecionada(f):
            self.log("   [TAREFA] escolha de outra missao: deixo para voce")
            self.clicar(popup["fechar"])
            self.dormir(0.4)
            return False
        self.log("   [TAREFA] Super Rota Leste: escolhendo material e confirmando a recompensa")
        for tentativa in range(2):
            self.clicar(popup["opcao"])
            self.dormir(0.35)
            g, _ = self.ver()
            if g is None or popup_escolha_recompensa(g) is None:
                return False
            self.clicar(popup["confirmar"])
            for _ in range(5):
                self.dormir(0.4)
                g, _ = self.ver()
                if g is not None and popup_escolha_recompensa(g) is None:
                    return True
            self.log(f"   [TAREFA] confirmacao da escolha ainda aberta (tentativa {tentativa + 1}/2)")
        return False

    def coletar_tarefas(self):
        """Coleta TODAS as tarefas concluidas (selo verde 'OK!'): clica na tarefa, depois no botao vermelho; categoria
        fechada com selo -> abre; sem selo visivel -> rola a sub-lista ate o fim procurando mais. So fecha o painel
        quando nao sobra selo nem lista para rolar."""
        if not self.usar_tarefas or self.rota == ["GATO_PRETO"]:
            self.tarefas_ok = True
            self.log("[TAREFA] coleta desativada; fechando sem tocar nas recompensas")
            self.clicar_e_verificar("TAREFA", TAREFA_FECHAR, descricao="fechar painel sem coletar")
            return
        self.log("[TAREFA] procurando tarefas concluidas (selo OK!)")
        vezes = Counter()
        coletadas, sem_reacao, rolagens, ignorar_botao = 0, 0, 0, False
        for _ in range(MAX_ACOES_TAREFA):
            f, achadas = self.ver()
            if f is None:
                break
            popup = popup_escolha_recompensa(f)
            if popup is not None:
                if self.escolher_material_leste(f, popup):
                    coletadas += 1
                    sem_reacao, rolagens, ignorar_botao = 0, 0, False
                    vezes.clear()
                    continue
                ignorar_botao = True
                break
            if achadas and "TAREFA" not in achadas and not self.simular:
                self.log(f"   (o painel de tarefas sumiu: tela {achadas[0]})")
                break
            leste_esperada = self.cupom_pendente == "L" or self.rota == ROTAS["L"][1]
            if tarefa_exige_escolha(f) and not (leste_esperada and tarefa_leste_selecionada(f)) and not ignorar_botao:
                ignorar_botao = True
                self.log("   [TAREFA] recompensa com escolha manual; ignorando esta tarefa")
            acao, ponto = proxima_acao_tarefa(f, vezes, ignorar_botao)
            if acao == "botao":
                antes = recorte_painel_tarefa(f)
                self.log(f"   coletando recompensa {ponto}")
                self.clicar(ponto)
                self.dormir(1.4)
                g, _e = self.ver()
                if g is not None and popup_escolha_recompensa(g) is not None:
                    continue  # so conta a missao depois de confirmar o item no popup
                if g is not None and botao_recompensa_ativo(g) and float(np.abs(recorte_painel_tarefa(g) - antes).mean()) < 2.5:
                    sem_reacao += 1                   # nada mudou: o clique nao pegou (ou o jogo recusa, ex.: mochila cheia)
                    if sem_reacao >= 2:
                        self.log("   ! o botao de recompensa nao reage; seguindo para as outras tarefas")
                        ignorar_botao = True
                else:
                    coletadas += 1
                    sem_reacao = 0
                    vezes.clear()                     # a lista muda depois de coletar
                    rolagens = 0
                continue
            if acao == "item":
                ignorar_botao, sem_reacao = False, 0
                self.log(f"   abrindo tarefa com selo OK! {ponto}")
                self.clicar(ponto)
                self.dormir(1.1)
                continue
            # nenhum selo visivel: pode haver tarefas concluidas escondidas mais abaixo na sub-lista
            seta = seta_rolar_lista(f)
            if seta is None or rolagens >= MAX_ROLAGENS_TAREFA:
                break
            antes = recorte_sublista(f, seta)
            self.clicar(seta)
            self.dormir(0.6)
            g, _e = self.ver()
            if g is None or float(np.abs(recorte_sublista(g, seta) - antes).mean()) < 2.5:
                break                                 # a lista nao andou: chegou ao fim
            rolagens += 1
            vezes.clear()
            self.log(f"   rolando a lista de tarefas ({rolagens}x) para procurar mais")
        self.ultima_coleta_tarefas = coletadas
        self.log(f"[TAREFA] {coletadas} recompensa(s) coletada(s)")
        if self.estat and coletadas:
            self.estat.missoes(coletadas)
        if self.reg:
            self.reg.evento("tarefas", [], coletadas=coletadas, rolagens=rolagens)
        self.tarefas_ok = True
        self.clicar_e_verificar("TAREFA", TAREFA_FECHAR, descricao="fechar painel")

    # ---------- laco principal ----------
    def rodar(self):
        self.log("Navegador ligado. F8 = pausar/continuar, F10 = sair.")
        erros = []
        while not self.parar:
            try:
                self._ciclo()
            except KeyboardInterrupt:
                raise
            except Exception:
                # uma falha inesperada nao pode derrubar o bot de madrugada: registra e tenta de novo
                import traceback
                t = self.agora()
                erros = [e for e in erros if t - e < 600] + [t]
                self.log("[ERRO] falha inesperada (o bot continua):\n" + traceback.format_exc())
                if self.reg:
                    self.reg.evento("erro_inesperado", [self.reg.frame(self.ultimo_quadro, "erro")] if self.ultimo_quadro is not None else [],
                                    texto=traceback.format_exc()[-1500:])
                if len(erros) >= MAX_ERROS_EM_10_MIN:
                    self.log(f"[ERRO] {len(erros)} falhas em 10 min: parando para nao fazer bobagem. Me mande o log.")
                    self.parar = True
                self.dormir(2.0)
        self.log("Navegador encerrado.")

    def _ciclo(self):
        self.teclas()
        if self.pausado:
            self.esperar_pausa()
            return
        if self.atirador and self.em_batalha:
            # na batalha o tempo importa (a sua vez dura ~8 s): sem a dupla leitura de confirmacao
            f, achadas = self.ver()
            if achadas and achadas[0] == "CLIQUE_JOGO":
                self.agir("CLIQUE_JOGO")          # o jogo perdeu o foco: nao responde ate clicar nele
                return
            if achadas and achadas[0] == "BATALHA":
                self.fora_da_batalha_desde = None
                self.atirador.passo(f)
                return
            cartas_apos_luta = bool(achadas and achadas[0] in CARTAS_ESTADOS)
            # O Fantasma pode ser confundido com CONFIG_SEL durante a animacao da batalha.
            # O PASS visivel e evidencia mais forte de que ainda e a nossa vez.
            if not cartas_apos_luta and f is not None and hasattr(self.atirador, "lei") and self.atirador.lei.minha_vez(f):
                self.fora_da_batalha_desde = None
                self.atirador.passo(f)
                return
            agora = self.agora()
            self.fora_da_batalha_desde = self.fora_da_batalha_desde or agora
            tela_final_clara = bool(achadas and achadas[0] in ("SALA", "SALA_VAZIA", "CENTRAL", "MAPA"))
            espera_saida = 3.0 if tela_final_clara else 12.0
            if agora - self.fora_da_batalha_desde < espera_saida and not cartas_apos_luta:
                self.dormir(0.15)
                return
            self.em_batalha = False
            self.fora_da_batalha_desde = None
            self.atirador.fim_da_batalha(venceu=bool(achadas and achadas[0] in CARTAS_ESTADOS),
                                         duracao=(agora - self.batalha_desde) if self.batalha_desde else None)
        estado = self.estado_estavel()
        if estado is None:
            self.desconhecido()
            self.dormir(0.6)
            return
        self.perdido_desde = None
        self.agir(estado)

    def vigiar(self, chave, desde):
        """Vigia de "preso": a mesma tela (ou uma tela desconhecida) por mais de PRESO_APOS s. Tenta se soltar com Esc e
        com o botao de cada janelinha conhecida, avisa no log e guarda um print para eu ver o que e. (O bot ja ficou 55 min
        clicando em "Inicio" com uma janelinha nova por cima.)"""
        agora = self.agora()
        if desde is None or agora - desde < PRESO_APOS or agora - self.preso_aviso < PRESO_REPETIR:
            return
        if self.chefe_modo == "so" and not self.no_chefe:
            return                                      # opcao C esperando o proximo horario: parado de proposito
        self.preso_aviso = agora
        self.preso_vezes += 1
        self.log(f"[ALERTA] preso em {chave} ha {fmt_tempo(agora - desde)}: tentando se soltar (tentativa {self.preso_vezes}). "
                 f"Se nao resolver, veja o jogo e me mande o log.")
        if self.reg:
            self.reg.evento("preso", [self.reg.frame(self.ultimo_quadro, "preso")] if self.ultimo_quadro is not None else [],
                            tela=chave, segundos=round(agora - desde), vezes=self.preso_vezes)
        if self.simular:
            return
        if hasattr(self.io, "tecla"):
            try:
                self.io.tecla("esc", 0.08)
            except Exception:
                pass
            self.dormir(0.5)
        # os botoes das janelinhas conhecidas (um clique fora de lugar numa tela comum e inofensivo)
        for ponto in (POPUP_AVISO_SIM, POPUP_SOZINHO_SIM, POPUP_CARTA_SIM, FOCO_PONTO_PADRAO):
            self.clicar(ponto)
            self.dormir(0.6)

    def desconhecido(self):
        agora = self.agora()
        if self.perdido_desde is None:
            self.perdido_desde = agora
        parado = agora - self.perdido_desde
        self.vigiar("tela desconhecida", self.perdido_desde)
        # parou numa tela de cidade que a rota nao usa (Sala de Casamento, Leilao...): volta pela porta da barra de baixo
        if (parado >= 6 and self.ultimo_conhecido in ("MAPA", "CENTRAL", "CLIQUE_JOGO") and not self.em_batalha
                and agora - self.ultima_recuperacao >= 8 and self.recuperacoes < 4):
            self.ultima_recuperacao = agora
            self.recuperacoes += 1
            self.log(f"? tela desconhecida ha {parado:.0f} s depois de {self.ultimo_conhecido} (tela fora da rota?): "
                     f"voltando pela porta {SALA_PORTA} (tentativa {self.recuperacoes}/4)")
            if self.reg:
                self.reg.evento("recuperacao", [self.reg.frame(self.ultimo_quadro, "recuperacao")], de=self.ultimo_conhecido)
            self.clicar(SALA_PORTA)
            return
        if parado >= 15 and hasattr(self.io, "pedir_calibracao") and agora - self.ultima_calib_pedida >= 90:
            self.ultima_calib_pedida = agora
            self.io.pedir_calibracao()                # talvez o jogo mudou de tamanho/lugar na janela: calibra de novo
        if parado > 45 and agora - self.ultimo_aviso > 45:
            self.ultimo_aviso = agora
            self.log("? tela desconhecida ha mais de 45 s (carregando, ou uma tela que o bot ainda nao conhece).")
            if self.reg:
                self.reg.evento("desconhecida", [self.reg.frame(self.ultimo_quadro, "desconhecida")], desde_s=round(parado))


# ---------------------------------------------------------------------------
def rota_dos_argumentos(texto, dificuldade=None):
    """'N' / 'S' / 'T' (ou 1, 2, norte, sul...) -> rota pronta; 'A,B,C' -> essas instancias.
    Devolve (nome, instancias, dificuldade forcada ou None = a de cada instancia)."""
    chave = APELIDOS_ROTA.get(texto.strip().upper(), texto.strip().upper())
    if chave in ROTAS:
        nome, rota = ROTAS[chave]
        return nome, list(rota), dificuldade
    rota = [r.strip().upper() for r in texto.split(",") if r.strip()]
    desconhecidas = [r for r in rota if r not in INSTANCIA_NA_CONFIG]
    if desconhecidas or not rota:
        raise SystemExit(f"Rota invalida: {texto}. Use N, S ou T, ou instancias de: {', '.join(INSTANCIA_NA_CONFIG)}")
    return "rota personalizada", rota, dificuldade


def perguntar_rota(entrada=input, saida=print):
    """Pergunta no console qual rota fazer. Enter sem nada (ou console sem teclado) = Sul. Norte (N) e Todas (T) estao
    desabilitadas no menu (o boneco ja esta completo com os drops do Norte) mas ainda funcionam se digitadas."""
    saida("Qual rota?  [S] Sul (Escorpiao Rei, Dragao Gelado, Rainha Liris)")
    saida("            [L] Leste (A Ultima Luta, 2 fases, Devoradores)")
    saida("            [U] Super Rota (Norte > Sul > Leste; missao apos cada rota)")
    saida("            [T] Rota Norte e Sul (missao apos cada rota)")
    saida("            [P] Pericao comum (fora do horario do Chefao Global)")
    saida(f"            [C] Chefao Global (Pericao) - so ele: comeca agora e depois espera os horarios "
          f"({texto_horarios(HORARIOS_CHEFE)})")
    for _ in range(5):
        try:
            r = entrada("Rota (S/L/P/C, Enter = S): ").strip().upper()
        except EOFError:
            return ROTA_PADRAO_MENU
        if r == "":
            return ROTA_PADRAO_MENU
        if r[0] in ("S", "L", "U", "P", "C", "N", "T"):
            return r[0]
        saida("   responda S, L, P ou C")
    return ROTA_PADRAO_MENU


def cartas_padrao(chave, rota):
    return [i for i in CARTAS_DE_INTERESSE.get(chave, rota) if i in rota]


def perguntar_cartas(chave, rota, entrada=input, saida=print):
    """Em quais instancias abrir as cartas? Devolve a lista (todas = None). As outras so completam a missao."""
    if len(rota) < 2:
        return None
    padrao = cartas_padrao(chave, rota)
    saida("Abrir as cartas de quais instancias? As outras o bot so joga a luta e espera a tela passar.")
    for n, i in enumerate(rota, 1):
        saida(f"   [{n}] {i}" + ("   (padrao)" if i in padrao else ""))
    for _ in range(5):
        try:
            r = entrada(f"Cartas (numeros separados por virgula, T = todas, Enter = padrao): ").strip().upper()
        except EOFError:
            r = ""
        if r == "":
            return None if set(padrao) == set(rota) else padrao
        if r[0] == "T":
            return None
        try:
            escolhidas = [rota[int(x) - 1] for x in r.replace(" ", "").split(",") if x]
            if escolhidas and all(int(x) >= 1 for x in r.replace(" ", "").split(",") if x):
                return escolhidas
        except (ValueError, IndexError):
            pass
        saida("   responda numeros da lista (ex.: 3 ou 1,3), T ou Enter")
    return None if set(padrao) == set(rota) else padrao


def testar_tela(io, det, saida=print, pasta=None):
    """Diagnostico "a minha tela funciona?": calibra a janela atual e diz o que reconheceu. Grava logs/teste_tela.txt e
    logs/teste_tela.png (o que o bot enxerga) para mandar ao desenvolvedor. Devolve True se calibrou e reconheceu uma tela."""
    import tela
    pasta = pasta or config.PASTA_LOGS
    os.makedirs(pasta, exist_ok=True)
    linhas = []

    def dizer(t):
        linhas.append(t)
        saida(t)

    img = io.capturar_bruto()
    if img is None:
        dizer("ERRO: nao consegui capturar a janela do jogo.")
        return False
    h, w = img.shape[:2]
    dizer(f"Janela do jogo: {w}x{h} px")
    c = tela.calibrar(img, det)
    ok = False
    if c is None:
        dizer("RESULTADO: nao reconheci nenhuma tela conhecida do jogo. Deixe o jogo no MAPA ou numa SALA (sem janelinhas "
              "abertas) e tente de novo. Se continuar, mande logs/teste_tela.png e este texto.")
        enxerga = cv2.resize(img, (1280, int(h * 1280 / w)), interpolation=cv2.INTER_AREA)
    else:
        dizer(f"Calibracao: {c.texto()} (pela tela {c.estado})")
        canon = c.renderizar(img)
        achadas = det.detectar(estados_mod.normalizar(canon))
        dizer(f"Tela reconhecida: {achadas[0] if achadas else 'nenhuma (tela que o bot ainda nao conhece)'}")
        ok = bool(achadas)
        if c.zoom < tela.ZOOM_MIN_BOM:
            dizer("AVISO: o jogo esta pequeno na janela; o minimapa fica impreciso e os tiros podem errar. Use a janela maior ou tela cheia.")
        if c.zoom > 1.8:
            dizer("AVISO: o jogo esta muito ampliado; confira se o zoom/escala do Windows nao esta exagerado.")
        dizer("RESULTADO: " + ("OK - o bot enxerga o jogo como esperado." if ok else
                               "calibrou, mas a tela atual nao e uma das conhecidas (normal em telas novas)."))
        enxerga = canon
    try:
        cv2.imwrite(os.path.join(pasta, "teste_tela.png"), enxerga)
        with open(os.path.join(pasta, "teste_tela.txt"), "w", encoding="utf-8") as f:
            f.write("\n".join(linhas) + "\n")
    except OSError:
        pass
    return ok


def perguntar_chefe(horarios=HORARIOS_CHEFE, entrada=input, saida=print):
    """Fazer o Chefao Global nos horarios, no meio da rota? Enter = sim."""
    saida(f"Fazer o CHEFAO GLOBAL (Pericao) nos horarios ({texto_horarios(horarios)})? Na hora, o bot termina a instancia "
          f"em andamento, luta contra o chefao ate ele cair e depois volta para a rota.")
    for _ in range(5):
        try:
            r = entrada("Chefao Global nos horarios? (S/n): ").strip().upper()
        except EOFError:
            return True
        if r == "" or r[0] == "S":
            return True
        if r[0] == "N":
            return False
        saida("   responda S ou N")
    return True


def main():
    import janela
    ap = argparse.ArgumentParser(description="DDTank - navegador da rota de instancias")
    ap.add_argument("--titulo", default="")
    ap.add_argument("--exe", default="")
    ap.add_argument("--rota", default=None, help="N (Norte), S (Sul), L (Leste), U (Super Cupons), T (Norte+Sul) ou C (so o Chefao Global); ou instancias em ordem, ex.: "
                    "ESCORPIAO_REI,DRAGAO_GELADO (instancias: " + ", ".join(INSTANCIA_NA_CONFIG) + "). Sem isso, pergunta ao abrir.")
    ap.add_argument("--dificuldade", default=None, choices=sorted(DIFICULDADE_BOTAO),
                    help="clica nessa dificuldade antes de confirmar (as rotas Norte e Sul nao tem escolha)")
    ap.add_argument("--chefe", choices=("s", "n"), default=None,
                    help="Chefao Global nos horarios, no meio da rota (s/n). Sem isso: pergunta ao abrir (com --rota: nao)")
    ap.add_argument("--horarios-chefe", default="", help="horarios do Chefao Global, ex.: 12:00-13:00,21:00-22:00")
    ap.add_argument("--cartas", default=None, help="instancias cujas cartas o bot abre, ex.: RAINHA_LIRIS (ou TODAS). "
                    "Sem isso, pergunta ao abrir (so se a rota tiver mais de uma instancia)")
    ap.add_argument("--tarefas-a-cada", type=int, default=0,
                    help="coleta as tarefas a cada N voltas (padrao: toda volta; lutando um chefe so: a cada 10)")
    ap.add_argument("--comecar-em", type=int, default=1, help="numero da instancia (1, 2, 3...) em que a rota comeca")
    ap.add_argument("--sem-tarefas", action="store_true")
    ap.add_argument("--uma-vez", action="store_true")
    ap.add_argument("--so-ver", action="store_true", help="so mostra a tela detectada (nao clica)")
    ap.add_argument("--testar-tela", action="store_true", help="diagnostico: calibra o tamanho da janela e diz o que o bot enxerga")
    ap.add_argument("--sem-calibrar", action="store_true", help="nao calibra o tamanho da janela (usa so o tamanho original)")
    ap.add_argument("--simular", action="store_true", help="mostra o que clicaria, sem clicar")
    ap.add_argument("--atirar", action="store_true", help="o bot joga os turnos da batalha (tiro, itens)")
    ap.add_argument("--sombra", action="store_true", help="na batalha, so mostra o tiro que faria (nao aperta teclas)")
    ap.add_argument("--itens", default="", help="ordem dos itens, ex.: 2,3,4,4,4,5,6,7,8")
    ap.add_argument("--foco", type=int, choices=(0, 1, 2), default=1,
                    help="foco do teclado na batalha: 0 nenhum, 1 virtual (padrao; sobe sozinho), 2 jogo em primeiro plano durante o turno")
    ap.add_argument("--sem-gravar", action="store_true", help="nao grava prints/eventos do bot em sessoes\\")
    ap.add_argument("--gravacao-leve", action="store_true",
                    help="grava so o texto + prints de turnos/problemas (para disco pequeno). Padrao: grava tudo")
    args = ap.parse_args()

    if not args.so_ver and not instancia_unica():
        sys.exit("ERRO: ja existe um bot (navegador/atirador) rodando. Feche os outros .bat antes: "
                 "varios bots juntos clicam e apertam teclas ao mesmo tempo e se atrapalham.")
    titulo, exe = args.titulo or config.TITULO_JANELA, args.exe or config.EXE_JANELA
    hwnd = janela.resolver_janela(titulo, exe)
    if not hwnd:
        sys.exit("Janela do jogo nao encontrada. Rode LISTAR_JANELAS.bat.")
    if janela.contar_janelas(titulo, exe) > 1:
        sys.exit("ERRO: ha mais de uma janela do jogo aberta. Deixe so uma.")
    io = IOJanela(hwnd, calibrar=not args.sem_calibrar)
    io.foco_nivel = args.foco
    det = estados_mod.Detector()
    print("Janela:", janela.descrever_janela(hwnd))

    if args.testar_tela:
        sys.exit(0 if testar_tela(io, det) else 1)

    if args.so_ver:
        print("Telas que o bot conhece (so as da rota de instancias):")
        print("  " + ", ".join(det.estados))
        print("Qualquer outra tela (Salao de jogos, PvP, resultado, carregando...) aparece como (desconhecida): normal.")
        print("Navegue pelo jogo; so imprimo quando a tela muda. Ctrl+C para sair.\n")
        ultimo = None
        while True:
            img = io.capturar()
            if img is not None:
                g = estados_mod.normalizar(img)
                achadas = det.detectar(g)
                if achadas != ultimo:
                    notas = det.pontuar(g)
                    top = sorted(notas.items(), key=lambda kv: -kv[1])[:3]
                    print(f"{datetime.datetime.now():%H:%M:%S}  detectado: {achadas or '(desconhecida)'}   "
                          f"mais parecidas: " + ", ".join(f"{n} {v:.2f}" for n, v in top), flush=True)
                    ultimo = achadas
            time.sleep(0.7)

    evitar_suspensao()
    os.makedirs(config.PASTA_LOGS, exist_ok=True)
    arq = open(os.path.join(config.PASTA_LOGS, f"navegador_{datetime.datetime.now():%Y%m%d}.log"), "a", encoding="utf-8")

    def log(msg):
        linha = f"[{datetime.datetime.now():%H:%M:%S}] {msg}"
        print(linha, flush=True)
        arq.write(linha + "\n")
        arq.flush()

    escolha = args.rota or perguntar_rota()
    nome_rota, rota, dificuldade = rota_dos_argumentos(escolha, args.dificuldade)
    horarios = ler_horarios(args.horarios_chefe) if args.horarios_chefe else HORARIOS_CHEFE
    chave = APELIDOS_ROTA.get(escolha.strip().upper(), escolha.strip().upper())
    if chave == "C":
        chefe = "so"
    elif args.chefe:
        chefe = "horarios" if args.chefe == "s" else None
    else:
        chefe = "horarios" if (not args.rota and perguntar_chefe(horarios)) else None
    if args.cartas:
        cartas_em = None if args.cartas.strip().upper() in ("TODAS", "T") else [c.strip().upper() for c in args.cartas.split(",") if c.strip()]
    elif args.rota:
        cartas_em = cartas_padrao(chave, rota) if chave in CARTAS_DE_INTERESSE else None
        cartas_em = None if cartas_em and set(cartas_em) == set(rota) else cartas_em
    else:
        cartas_em = perguntar_cartas(chave, rota)
    reg = None
    if not args.sem_gravar:
        import registro
        reg = registro.Registro("bot", leve=args.gravacao_leve)
        log(f"Gravando o bot em: {reg.pasta} ({'leve: eventos + prints dos turnos e de problemas' if args.gravacao_leve else 'tudo'})")
    import combos as combos_mod
    import metricas as metricas_mod
    ordem = [int(x) for x in args.itens.split(",") if x.strip()] or None
    combos = combos_mod.Combos(fixo=ordem)
    metr = metricas_mod.Metricas(nome_rota, log=log, combos=combos)
    import drops as drops_mod
    import estatisticas as estat_mod
    estat = estat_mod.Estatisticas(nome_rota=nome_rota)
    tarefas_a_cada = args.tarefas_a_cada or (10 if len(rota) == 1 and chave not in ("C",) else 1)
    log(f"Cronometro: logs\\relatorio.txt (resumo, atualizado a cada luta), logs\\lutas.csv e logs\\voltas.csv")
    io.log = log
    nav = Navegador(io, det, rota, not args.sem_tarefas or chave in ("U", "T"), args.uma_vez, args.simular, log=log, reg=reg,
                    dificuldade=dificuldade, metricas=metr, chefe=chefe, horarios_chefe=horarios, cartas_em=cartas_em,
                    estat=estat, catalogo=drops_mod.Catalogo(), tarefas_a_cada=tarefas_a_cada)
    log("Cartas: " + ("abre todas" if not cartas_em else "so de " + ", ".join(cartas_em) + " (as outras so completam a missao)"))
    log(f"{nome_rota}: {' -> '.join(rota)}" + (f" (dificuldade {dificuldade} em todas)" if dificuldade else ""))
    if chefe == "so":
        log(f"Chefao Global: comeco agora; depois de cada vitoria, espero o proximo horario ({texto_horarios(horarios)}).")
    elif chefe:
        log(f"Chefao Global nos horarios {texto_horarios(horarios)}: a rota pausa e volta depois.")
    if chefe and not (args.atirar or args.sombra):
        log("(sem --atirar: no Chefao Global e voce quem atira - use o BotDDT (o painel liga o atirador))")
    if args.atirar or args.sombra:
        import atirador as atirador_mod
        import memoria as memoria_mod
        nav.atirador = atirador_mod.Atirador(io, memoria_mod.Memoria(), lambda: nav.instancia_batalha, sombra=args.sombra, log=log,
                                             ordem_itens=ordem, reg=reg, metricas=metr, combos=combos)
    nav.idx = max(0, min(len(rota) - 1, args.comecar_em - 1))
    nav.arquivo_parar = ARQUIVO_PARAR
    nav.arquivo_pausar = ARQUIVO_PAUSAR
    if os.path.exists(ARQUIVO_PAUSAR):
        os.remove(ARQUIVO_PAUSAR)         # pedido de pausa velho
    if os.path.exists(ARQUIVO_PARAR):
        os.remove(ARQUIVO_PARAR)          # pedido de parada velho
    try:
        nav.rodar()
    except KeyboardInterrupt:
        log("Parado pelo usuario.")
    finally:
        metr.escrever_relatorio()
        print("\n" + metr.texto_relatorio())
        if reg:
            reg.fechar()
            print(f"Gravacao salva em {reg.pasta}  (rode EMPACOTAR_E_ENVIAR.bat para me mandar)")


if __name__ == "__main__":
    main()
