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
FECHAR_CLIQUE_JOGO = (913, 190)
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
CARTAS_PARA_ABRIR = [(556, 380), (644, 380), (732, 380)]   # 3 cartas da fileira do meio

ROTA_PADRAO = ["FANTASMA", "PROFUNDEZAS", "MINHOCAO"]
INSTANCIA_NA_CONFIG = {"FANTASMA": (509, 313), "PROFUNDEZAS": (591, 313), "MINHOCAO": (675, 318)}

CLIQUE_SIMPLES = {                      # tela -> onde clicar para avancar
    "CLIQUE_JOGO": FECHAR_CLIQUE_JOGO,
    "MAPA": MAPA_CENTRAL,
    "CONFIG_SEL": CONFIG_SIM,
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
                 dormir=time.sleep, agora=time.time, log=print):
        self.io, self.det = io, detector
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
        self.cartas_clicadas = 0
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
        self.cartas_clicadas = 0

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
        return f, self.det.detectar(estados_mod.normalizar(f))

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
        """Chamado quando saimos das cartas: a instancia atual acabou."""
        if not self.cartas_vistas:
            return
        self.cartas_vistas = False
        self.cartas_clicadas = 0
        self.idx += 1
        if self.idx >= len(self.rota):
            self.run_completa = True
            self.log(f"*** Rota completa ({self.voltas + 1}a volta). Falta coletar as tarefas. ***")
        else:
            self.log(f"Instancia concluida. Proxima: {self.instancia}")

    def agir(self, estado):
        if estado not in ("CARTAS", "POPUP_CARTA", "BATALHA"):
            self.finalizar_instancia()
        if estado != "BATALHA":
            self.batalha_desde = None

        if estado in CLIQUE_SIMPLES:
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
            if self.run_completa and self.usar_tarefas and not self.tarefas_ok:
                if not self.clicar_e_verificar(estado, SALA_ICONE_TAREFAS, descricao="abrir Tarefas"):
                    self.pontos_tarefa["abrir"] += 1
                    if self.pontos_tarefa["abrir"] >= 3:
                        self.log("   ! nao consegui abrir as Tarefas; sigo sem coletar.")
                        self.tarefas_ok = True
            elif self.run_completa:
                self.clicar_e_verificar(estado, SALA_PORTA, descricao="voltar para a Central")
            else:
                self.clicar_e_verificar(estado, SALA_TROCAR_INSTANCIA, descricao=f"escolher instancia ({self.instancia})")
        elif estado == "CONFIG_VAZIA":
            self.clicar_e_verificar(estado, INSTANCIA_NA_CONFIG[self.instancia], descricao=f"selecionar {self.instancia}")
        elif estado.startswith("PRONTA_"):
            nome = estado.split("_", 1)[1]
            if nome != self.instancia and nome in self.rota:
                self.log(f"   sala ja esta em {nome}; sigo a partir dela.")
                self.idx = self.rota.index(nome)
            self.clicar_e_verificar(estado, SALA_INICIO, descricao=f"Inicio ({nome})", espera=6.0)
        elif estado == "CARTAS":
            self.cartas_vistas = True
            if self.cartas_clicadas < len(CARTAS_PARA_ABRIR):
                ponto = CARTAS_PARA_ABRIR[self.cartas_clicadas]
                self.cartas_clicadas += 1
                self.log(f"[CARTAS] virando a carta {self.cartas_clicadas} {ponto}")
                self.clicar(ponto)
                self.dormir(1.2)
            else:
                self.dormir(1.5)
        elif estado == "TAREFA":
            self.coletar_tarefas()
        elif estado == "BATALHA":
            if self.batalha_desde is None:
                self.batalha_desde = self.agora()
                self.log("[BATALHA] em luta - o tiro automatico e a fase 3; jogue o tiro voce mesmo por enquanto.")
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
        if agora - self.perdido_desde > 45 and agora - self.ultimo_aviso > 45:
            self.ultimo_aviso = agora
            self.log("? tela desconhecida ha mais de 45 s (carregando, ou uma tela que o bot ainda nao conhece).")


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
    args = ap.parse_args()

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
        print("Mostrando a tela detectada (Ctrl+C para sair). Navegue pelo jogo e veja se bate.")
        while True:
            img = io.capturar()
            if img is not None:
                notas = det.pontuar(estados_mod.normalizar(img))
                achadas = det.detectar(estados_mod.normalizar(img))
                top = sorted(notas.items(), key=lambda kv: -kv[1])[:3]
                print(f"{datetime.datetime.now():%H:%M:%S}  detectado: {achadas or '(desconhecida)'}   "
                      f"melhores notas: " + ", ".join(f"{n} {v:.2f}" for n, v in top))
            time.sleep(1.0)

    os.makedirs(config.PASTA_LOGS, exist_ok=True)
    arq = open(os.path.join(config.PASTA_LOGS, f"navegador_{datetime.datetime.now():%Y%m%d}.log"), "a", encoding="utf-8")

    def log(msg):
        linha = f"[{datetime.datetime.now():%H:%M:%S}] {msg}"
        print(linha, flush=True)
        arq.write(linha + "\n")
        arq.flush()

    rota = [r.strip().upper() for r in args.rota.split(",") if r.strip()]
    nav = Navegador(io, det, rota, not args.sem_tarefas, args.uma_vez, args.simular, log=log)
    nav.idx = max(0, min(len(rota) - 1, args.comecar_em - 1))
    try:
        nav.rodar()
    except KeyboardInterrupt:
        log("Parado pelo usuario.")


if __name__ == "__main__":
    main()
