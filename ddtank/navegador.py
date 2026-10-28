# -*- coding: utf-8 -*-
"""
DDTank - navegador (fase 2): percorre sozinho a rota de instancias do menu ate o chefe,
passa pelas cartas, coleta as tarefas no fim e recomeca. Sem usar o seu mouse.

  Fantasma -> Profundezas -> O Minhocao -> (tarefas) -> Central -> de novo

A BATALHA ainda e sua (fase 3 = tiro automatico): o bot espera a luta terminar.

  python navegador.py --so-ver        so mostra a tela detectada (nao clica) - teste primeiro!
  python navegador.py --simular       diz o que clicaria, sem clicar
  python navegador.py                 liga o bot
  python navegador.py --uma-vez       faz uma volta completa e para
Teclas: F8 = pausar/continuar   F10 = sair
"""
import argparse
import datetime
import os
import sys
import time
from collections import Counter

import cv2
import numpy as np

import config
import estados as estados_mod

# ---------------------------------------------------------------------------
# Posicoes (em pixels de uma imagem com 1280 de largura; saem da sua gravacao)
# ---------------------------------------------------------------------------
LARGURA_REF = 1280
# Pop-up "Clique no jogo para continuar jogando" (aparece quando o jogo perde o foco). Qualquer clique dentro do jogo
# o fecha, mas o clique tambem vale para o que esta POR BAIXO - entao nunca clicar no pop-up (no mapa ele cobre a
# Sala de Casamento!). Usa um ponto neutro: o chat nas telas de cidade/sala, o texto do log na batalha etc.
FOCO_PONTO_PADRAO = (450, 485)
FOCO_PONTO_NEUTRO = {"BATALHA": (420, 290), "CARTAS": (590, 190), "POPUP_CARTA": (590, 190)}
POPUP_FOCO_CAIXA = (596, 316, 696, 410)
MAPA_CENTRAL = (872, 430)
CENTRAL_JOGAR = (794, 472)
SALA_TROCAR_INSTANCIA = (697, 302)
CONFIG_SIM = (640, 529)
SALA_INICIO = (934, 473)
POPUP_SOZINHO_SIM = (575, 402)
POPUP_CARTA_SIM = (566, 391)
SALA_ICONE_TAREFAS = (806, 533)
SALA_PORTA = (949, 522)
TAREFA_FECHAR = (881, 190)
TAREFA_BOTAO = (760, 513)
CARTAS_COLUNAS = [380, 468, 556, 644, 732, 820, 907]
CARTAS_LINHAS = [262, 380, 498]
# ordem de preferencia: fileira do meio (colunas 3, 4, 5), depois o resto
CARTAS_PREFERENCIA = [(556, 380), (644, 380), (732, 380)] + [(x, y) for y in (380, 262, 498) for x in CARTAS_COLUNAS]
CARTAS_VIRADAS_PARA_PAGAR = 3     # 2 gratis + a 3a (VIP, com pop-up de confirmacao)
SLOTS_SALA = [(516, 242), (394, 366), (516, 366)]   # 3 vagas vazias da sala
SLOT_RECORTE = (-36, 34, -37, 43)   # recorte (dx0, dx1, dy0, dy1) da silhueta "Em Espera" ao redor do centro da vaga
SLOT_ABERTO_LIMIAR = 0.6          # aberta ~0.97-1.0; fechada (X) ~0.29; ocupada por jogador ~0.08
BRILHO_SLOT_FECHADO = 140         # fechada ~110 (marrom); ocupada por jogador e mais clara
CFG_REGIAO = (490, 395, 610, 455)  # arte da instancia selecionada na janela de configuracao
CFG_LIMIAR = 0.7                   # certa >= ~0.9; qualquer outra coisa < 0.56

ROTA_PADRAO = ["FANTASMA", "PROFUNDEZAS", "MINHOCAO"]
INSTANCIA_NA_CONFIG = {"FANTASMA": (509, 313), "PROFUNDEZAS": (591, 313), "MINHOCAO": (675, 318)}

CLIQUE_SIMPLES = {                      # tela -> onde clicar para avancar
    "MAPA": MAPA_CENTRAL,
    "POPUP_SOZINHO": POPUP_SOZINHO_SIM,
    "POPUP_CARTA": POPUP_CARTA_SIM,
}
MODOS_ENTRADA = ["top", "filha"]
VK_F8, VK_F10 = 0x77, 0x79


# ---------------------------------------------------------------------------
# entrada/saida (trocavel nos testes)
# ---------------------------------------------------------------------------
class IOJanela:
    def __init__(self, hwnd):
        import janela
        self.j = janela
        self.hwnd = hwnd

    def capturar(self):
        return self.j.capturar(self.hwnd, "print")

    def clicar(self, x, y, modo):
        self.j.clicar(self.hwnd, x, y, modo)

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

    def trocar_modo(self):
        self.modo_teclas = "filha" if self.modo_teclas == "top" else "top"


_TPL_COSTAS = []


def cartas_de_costas(f):
    """Centros (x, y) das cartas que ainda estao viradas para baixo (inclui a que so ficou com a
    borda amarela). Compara o bauzinho do verso com o de cada uma das 21 posicoes."""
    if not _TPL_COSTAS:
        _TPL_COSTAS.append(cv2.imread(os.path.join(config.PASTA_TEMPLATES, "costas_carta.png"), cv2.IMREAD_GRAYSCALE))
    t = _TPL_COSTAS[0]
    th, tw = t.shape
    g = cv2.GaussianBlur(cv2.cvtColor(f, cv2.COLOR_BGR2GRAY), (3, 3), 0)
    achadas = []
    for y in CARTAS_LINHAS:
        for x in CARTAS_COLUNAS:
            roi = g[y - th // 2 - 8:y + th // 2 + 8, x - tw // 2 - 8:x + tw // 2 + 8]
            if roi.shape[0] >= th and roi.shape[1] >= tw and cv2.matchTemplate(roi, t, cv2.TM_CCOEFF_NORMED).max() > 0.55:
                achadas.append((x, y))
    return achadas


_TPL_SLOT = []
_TPL_CFG = {}


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


def instancia_selecionada(f):
    """Qual instancia esta marcada na janela de configuracao (pela arte), ou None."""
    if not _TPL_CFG:
        for nome in ROTA_PADRAO:
            _TPL_CFG[nome] = cv2.imread(os.path.join(config.PASTA_TEMPLATES, f"cfg_{nome}.png"), cv2.IMREAD_GRAYSCALE).astype(np.float32)
    g = cv2.GaussianBlur(cv2.cvtColor(f, cv2.COLOR_BGR2GRAY), (3, 3), 0).astype(np.float32)
    x0, y0, x1, y1 = CFG_REGIAO
    tol = 6
    roi = g[y0 - tol:y1 + tol, x0 - tol:x1 + tol]
    notas = {n: float(cv2.matchTemplate(roi, t, cv2.TM_CCOEFF_NORMED).max()) for n, t in _TPL_CFG.items()}
    melhor = max(notas, key=notas.get)
    return melhor if notas[melhor] >= CFG_LIMIAR else None


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
def botao_recompensa_ativo(f):
    """O botao 'Obter recompensa' fica vermelho quando da para coletar e cinza quando nao."""
    reg = f[500:525, 700:820].astype(int)
    b, g, r = reg[..., 0].mean(), reg[..., 1].mean(), reg[..., 2].mean()
    return r > 170 and r - g > 50 and r - b > 60


def selos_ok(f):
    """Posicoes (x, y) dos selos verdes 'OK!' na lista da esquerda do painel de Tarefas."""
    x0, y0, x1, y1 = 335, 225, 600, 560
    c = f[y0:y1, x0:x1].astype(int)
    m = ((c[..., 1] > c[..., 2] + 35) & (c[..., 1] > c[..., 0] + 35)).astype(np.uint8)
    m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8))
    n, _, st, ce = cv2.connectedComponentsWithStats(m)
    achados = [(int(ce[i][0]) + x0, int(ce[i][1]) + y0) for i in range(1, n) if st[i][4] >= 80]
    return sorted(achados, key=lambda p: p[1])


def proxima_acao_tarefa(f, vezes):
    """('botao', ponto) | ('item', ponto) | ('fim', None) para o quadro atual do painel."""
    if botao_recompensa_ativo(f):
        return "botao", TAREFA_BOTAO
    for bx, by in selos_ok(f):
        chave = (bx // 25, by // 25)
        if vezes[chave] < 2:
            vezes[chave] += 1
            return "item", (max(350, bx - 80), by)   # clica no nome da tarefa, a esquerda do selo
    return "fim", None


# ---------------------------------------------------------------------------
class Navegador:
    def __init__(self, io, detector, rota=None, usar_tarefas=True, uma_vez=False, simular=False,
                 dormir=time.sleep, agora=time.time, log=print, atirador=None, reg=None):
        self.io, self.det = io, detector
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
        self.usar_tarefas, self.uma_vez, self.simular = usar_tarefas, uma_vez, simular
        self.dormir, self.agora, self.log = dormir, agora, log
        self.k = 1.0
        self.modo = 0                     # indice em MODOS_ENTRADA
        self.falhas_clique = 0
        self.parar, self.pausado = False, False
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
        self.run_completa = False
        self.tarefas_ok = False
        self.cartas_vistas = False
        self.tentativas_carta = Counter()
        self.tentativas_slot = 0
        self.tentativas_cfg = 0
        self.trocas_pronta = 0
        self.avisou_ocupado = False
        self.lutou = False

    @property
    def instancia(self):
        return self.rota[min(self.idx, len(self.rota) - 1)]

    # ---------- visao ----------
    def ver(self):
        img = self.io.capturar()
        if img is None:
            return None, None
        self.k = img.shape[1] / LARGURA_REF
        f = em_1280(img)
        self.ultimo_quadro = f
        self.achadas_atual = self.det.detectar(estados_mod.normalizar(f))
        return f, self.achadas_atual

    def estado_estavel(self):
        """Tela detectada de forma igual em 2 leituras seguidas (None = desconhecida/transicao)."""
        _, a = self.ver()
        if not a:
            return None
        self.dormir(0.45)
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

    def teclas(self):
        if self.io.tecla_apertada(VK_F10):
            self.parar = True
        if self.io.tecla_apertada(VK_F8):
            self.pausado = not self.pausado
            self.log("PAUSADO (F8 para continuar)" if self.pausado else "Continuando.")
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
        if self.falhas_clique >= 2:
            self.modo = (self.modo + 1) % len(MODOS_ENTRADA)
            self.falhas_clique = 0
            self.log(f"   ! trocando o modo de entrada para '{MODOS_ENTRADA[self.modo]}'. Se continuar sem "
                     "efeito, me mande o log e um print.")
        return False

    def finalizar_instancia(self):
        """Chamado ao sair das cartas/batalha: a instancia atual acabou."""
        if not self.cartas_vistas:
            if self.lutou:
                self.lutou = False
                self.log(f"   [ORDEM] ! a luta de {self.instancia} acabou SEM passar pelas cartas; repito {self.instancia}.")
                if self.reg:
                    self.reg.evento("ordem_sem_cartas", [self.reg.frame(self.ultimo_quadro, "sem_cartas")], instancia=self.instancia, idx=self.idx)
            return
        self.cartas_vistas = False
        self.lutou = False
        self.tentativas_carta = Counter()
        antes = self.instancia
        self.idx += 1
        if self.idx >= len(self.rota):
            self.run_completa = True
            self.log(f"*** {antes} concluida: rota completa ({self.voltas + 1}a volta). Falta coletar as tarefas. ***")
        else:
            self.log(f"[ORDEM] {antes} concluida. Proxima: {self.instancia} (idx {self.idx})")
        if self.reg:
            self.reg.evento("ordem", [], concluida=antes, proxima=None if self.run_completa else self.instancia, idx=self.idx,
                            run_completa=self.run_completa)

    def agir(self, estado):
        if self.reg and estado != self.ultimo_estado_reg:
            self.reg.evento("estado", [self.reg.frame(self.ultimo_quadro, "estado_" + estado)], estado=estado,
                            instancia=self.instancia, idx=self.idx, voltas=self.voltas, run_completa=self.run_completa)
        self.ultimo_estado_reg = estado
        self.ultimo_conhecido = estado
        self.recuperacoes = 0
        if estado not in ("CARTAS", "POPUP_CARTA", "BATALHA", "CLIQUE_JOGO"):
            self.finalizar_instancia()
        if estado != "BATALHA":
            self.batalha_desde = None

        sala = estado == "SALA_VAZIA" or estado.startswith("PRONTA_")
        if sala and self.run_completa:
            # a rota acabou: coleta as tarefas e so entao comeca outra volta (a sala pode continuar mostrando a
            # ultima instancia - antes o bot "aceitava" essa sala e repetia o Minhocao sem parar)
            if self.usar_tarefas and not self.tarefas_ok:
                if not self.clicar_e_verificar(estado, SALA_ICONE_TAREFAS, descricao="abrir Tarefas"):
                    self.pontos_tarefa["abrir"] += 1
                    if self.pontos_tarefa["abrir"] >= 3:
                        self.log("   ! nao consegui abrir as Tarefas; sigo sem coletar.")
                        self.tarefas_ok = True
                return
            self.voltas += 1
            self.log(f"=== Volta {self.voltas} concluida. Recomecando na mesma sala pela {self.rota[0]}. ===")
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
                self.log(f"=== Volta {self.voltas} concluida (tarefas coletadas). ===")
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
            self.clicar_e_verificar(estado, INSTANCIA_NA_CONFIG[self.instancia], descricao=f"selecionar {self.instancia}")
        elif estado == "CONFIG_SEL":
            self.adotar_primeira = False
            f, _e = self.ver()
            sel = instancia_selecionada(f) if f is not None else None
            if sel == self.instancia:
                self.tentativas_cfg = 0
                self.clicar_e_verificar(estado, CONFIG_SIM, descricao=f"confirmar {self.instancia}")
            else:
                self.tentativas_cfg += 1
                if sel is None and self.tentativas_cfg <= 3:
                    self.dormir(0.7)                       # a arte pode ainda estar carregando
                    return
                self.log(f"[CONFIG_SEL] marcada: {sel or 'nenhuma/desconhecida'}; quero {self.instancia} -> clicando nela")
                self.clicar(INSTANCIA_NA_CONFIG[self.instancia])
                self.dormir(1.0)
        elif estado.startswith("PRONTA_"):
            nome = estado.split("_", 1)[1]
            if nome != self.instancia and nome in self.rota:
                if self.adotar_primeira:
                    self.log(f"   sala ja esta em {nome}; sigo a partir dela (so na 1a vez).")
                    self.idx = self.rota.index(nome)
                else:
                    self.trocas_pronta += 1
                    if self.trocas_pronta > 3:
                        self.log(f"   ! nao consegui trocar a sala de {nome} para {self.instancia}; sigo com {nome}.")
                        self.idx = self.rota.index(nome)
                    else:
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
            self.clicar_e_verificar(estado, SALA_INICIO, descricao=f"Inicio ({nome})", espera=6.0)
        elif estado == "CARTAS":
            self.cartas_vistas = True
            f, _e = self.ver()
            if f is None:
                return
            costas = cartas_de_costas(f)
            viradas = len(CARTAS_LINHAS) * len(CARTAS_COLUNAS) - len(costas)
            if viradas >= CARTAS_VIRADAS_PARA_PAGAR:
                self.dormir(1.5)       # ja viramos as 3 (ou a contagem acabou e tudo abriu)
                return
            alvo = next((p for p in CARTAS_PREFERENCIA if p in costas and self.tentativas_carta[p] < 2), None)
            if alvo is None:
                self.dormir(1.0)
                return
            self.tentativas_carta[alvo] += 1
            self.log(f"[CARTAS] {viradas} virada(s); virando a carta em {alvo}")
            self.clicar(alvo)
            self.dormir(1.3)
        elif estado == "TAREFA":
            self.coletar_tarefas()
        elif estado == "BATALHA":
            self.lutou = True
            if self.batalha_desde is None:
                self.batalha_desde = self.agora()
                self.em_batalha = True
                self.log("[BATALHA] " + ("o bot joga os turnos." if self.atirador else
                                         "em luta - o tiro automatico e opcional (--atirar); jogue voce mesmo."))
            if self.atirador:
                self.atirador.passo()
                self.dormir(0.05)
            else:
                self.dormir(1.5)
        else:
            self.dormir(1.0)

    def coletar_tarefas(self):
        self.log("[TAREFA] coletando recompensas (selo OK! + botao vermelho)")
        vezes = Counter()
        for _ in range(14):
            f, _e = self.ver()
            if f is None:
                break
            acao, ponto = proxima_acao_tarefa(f, vezes)
            if acao == "fim":
                break
            self.log(f"   {'coletando' if acao == 'botao' else 'abrindo tarefa'} {ponto}")
            self.clicar(ponto)
            self.dormir(1.4)
        self.tarefas_ok = True
        self.clicar_e_verificar("TAREFA", TAREFA_FECHAR, descricao="fechar painel")

    # ---------- laco principal ----------
    def rodar(self):
        self.log("Navegador ligado. F8 = pausar/continuar, F10 = sair.")
        while not self.parar:
            self.teclas()
            if self.pausado:
                self.esperar_pausa()
                continue
            if self.atirador and self.em_batalha:
                # na batalha o tempo importa (a sua vez dura ~8 s): sem a dupla leitura de confirmacao
                f, achadas = self.ver()
                if achadas and achadas[0] == "CLIQUE_JOGO":
                    self.agir("CLIQUE_JOGO")          # o jogo perdeu o foco: nao responde ate clicar nele
                    continue
                if achadas and achadas[0] == "BATALHA":
                    self.fora_da_batalha_desde = None
                    self.atirador.passo(f)
                    continue
                agora = self.agora()
                self.fora_da_batalha_desde = self.fora_da_batalha_desde or agora
                if agora - self.fora_da_batalha_desde < 3.0 and not (achadas and achadas[0] in ("CARTAS", "POPUP_CARTA")):
                    self.dormir(0.15)
                    continue
                self.em_batalha = False
                self.fora_da_batalha_desde = None
                self.atirador.fim_da_batalha()
            estado = self.estado_estavel()
            if estado is None:
                self.desconhecido()
                self.dormir(0.6)
                continue
            self.perdido_desde = None
            self.agir(estado)
        self.log("Navegador encerrado.")

    def desconhecido(self):
        agora = self.agora()
        if self.perdido_desde is None:
            self.perdido_desde = agora
        parado = agora - self.perdido_desde
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
        if parado > 45 and agora - self.ultimo_aviso > 45:
            self.ultimo_aviso = agora
            self.log("? tela desconhecida ha mais de 45 s (carregando, ou uma tela que o bot ainda nao conhece).")
            if self.reg:
                self.reg.evento("desconhecida", [self.reg.frame(self.ultimo_quadro, "desconhecida")], desde_s=round(parado))


# ---------------------------------------------------------------------------
def main():
    import janela
    ap = argparse.ArgumentParser(description="DDTank - navegador da rota de instancias")
    ap.add_argument("--titulo", default="")
    ap.add_argument("--exe", default="")
    ap.add_argument("--rota", default=",".join(ROTA_PADRAO), help="instancias em ordem, ex.: FANTASMA,PROFUNDEZAS,MINHOCAO")
    ap.add_argument("--comecar-em", type=int, default=1, help="numero da instancia (1 a 3) em que a rota comeca")
    ap.add_argument("--sem-tarefas", action="store_true")
    ap.add_argument("--uma-vez", action="store_true")
    ap.add_argument("--so-ver", action="store_true", help="so mostra a tela detectada (nao clica)")
    ap.add_argument("--simular", action="store_true", help="mostra o que clicaria, sem clicar")
    ap.add_argument("--atirar", action="store_true", help="o bot joga os turnos da batalha (tiro, itens)")
    ap.add_argument("--sombra", action="store_true", help="na batalha, so mostra o tiro que faria (nao aperta teclas)")
    ap.add_argument("--itens", default="", help="ordem dos itens, ex.: 2,3,4,4,4,5,6,7,8")
    ap.add_argument("--sem-gravar", action="store_true", help="nao grava prints/eventos do bot em sessoes\\")
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
    io = IOJanela(hwnd)
    det = estados_mod.Detector()
    print("Janela:", janela.descrever_janela(hwnd))

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

    os.makedirs(config.PASTA_LOGS, exist_ok=True)
    arq = open(os.path.join(config.PASTA_LOGS, f"navegador_{datetime.datetime.now():%Y%m%d}.log"), "a", encoding="utf-8")

    def log(msg):
        linha = f"[{datetime.datetime.now():%H:%M:%S}] {msg}"
        print(linha, flush=True)
        arq.write(linha + "\n")
        arq.flush()

    rota = [r.strip().upper() for r in args.rota.split(",") if r.strip()]
    reg = None
    if not args.sem_gravar:
        import registro
        reg = registro.Registro("bot")
        log(f"Gravando o bot em: {reg.pasta}")
    nav = Navegador(io, det, rota, not args.sem_tarefas, args.uma_vez, args.simular, log=log, reg=reg)
    if args.atirar or args.sombra:
        import atirador as atirador_mod
        import memoria as memoria_mod
        ordem = [int(x) for x in args.itens.split(",") if x.strip()] or None
        nav.atirador = atirador_mod.Atirador(io, memoria_mod.Memoria(), lambda: nav.instancia, sombra=args.sombra, log=log,
                                             ordem_itens=ordem, reg=reg)
    nav.idx = max(0, min(len(rota) - 1, args.comecar_em - 1))
    try:
        nav.rodar()
    except KeyboardInterrupt:
        log("Parado pelo usuario.")
    finally:
        if reg:
            reg.fechar()
            print(f"Gravacao salva em {reg.pasta}  (rode EMPACOTAR_E_ENVIAR.bat para me mandar)")


if __name__ == "__main__":
    main()
