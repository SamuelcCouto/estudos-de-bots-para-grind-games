# -*- coding: utf-8 -*-
"""
Painel do terminal: eventos a esquerda, recursos a direita, teclas P (pausar) e Q (sair).

Tudo o que aparece (e mais: cada colheita e um resumo dos recursos por minuto) vai
tambem para o log de execucao em autofarm/logs/.
"""
import collections
import ctypes
import datetime
import os
import shutil
import sys
import threading
import time

from recursos import NOMES

ROTULOS = {"ouro": "Ouro", "madeira": "Madeira", "bife": "Bife", "pedra": "Pedra"}
LARGURA_PAINEL = 52


def _num(v, sinal=False):
    if v is None:
        return "-"
    s = f"{abs(int(round(v))):,}".replace(",", ".")
    if sinal:
        return ("+" if v >= 0 else "-") + s
    return ("-" if v < 0 else "") + s


class Painel:
    def __init__(self, estat, pasta):
        self.estat = estat
        self.linhas = collections.deque(maxlen=400)
        self.pausado = threading.Event()
        self.sair = False
        self.interativo = sys.stdout.isatty()
        os.makedirs(os.path.join(pasta, "logs"), exist_ok=True)
        nome = f"execucao_{datetime.datetime.now():%Y-%m-%d_%H-%M-%S}.log"
        self.caminho_log = os.path.join(pasta, "logs", nome)
        self._arquivo = open(self.caminho_log, "a", encoding="utf-8")
        self._lock = threading.Lock()
        self._ultimo_resumo = time.time()

    # ---------- log ----------
    def log(self, msg, tela=True):
        linha = f"[{datetime.datetime.now():%H:%M:%S}] {msg}"
        with self._lock:
            self._arquivo.write(linha + "\n")
            self._arquivo.flush()
            if tela:
                self.linhas.append(linha)
        if tela and not self.interativo:
            print(linha, flush=True)

    def resumo_no_arquivo(self):
        """Uma linha por minuto no log de execucao com os recursos."""
        if time.time() - self._ultimo_resumo < 60 or self.estat.atual is None:
            return
        self._ultimo_resumo = time.time()
        e = self.estat
        pm = e.por_minuto()
        partes = [f"{n}={_num(e.atual[n])} (colhido {_num(e.colhido[n], True)}, "
                  f"gasto {_num(e.gasto[n])}, {_num(pm[n], True)}/min)" for n in NOMES]
        self.log("RECURSOS " + " | ".join(partes), tela=False)

    # ---------- tela ----------
    def iniciar(self):
        if not self.interativo:
            return
        k32 = ctypes.windll.kernel32
        h = k32.GetStdHandle(-11)
        modo = ctypes.c_uint32()
        if k32.GetConsoleMode(h, ctypes.byref(modo)):
            k32.SetConsoleMode(h, modo.value | 0x0004)  # cores/cursor ANSI
        sys.stdout.write("\x1b[?25l\x1b[2J")
        threading.Thread(target=self._rodar, daemon=True).start()

    def encerrar(self):
        if self.interativo:
            sys.stdout.write("\x1b[?25h\n")
            sys.stdout.flush()
        self._arquivo.close()

    def _rodar(self):
        import msvcrt
        while True:
            while msvcrt.kbhit():
                tecla = msvcrt.getwch().lower()
                if tecla == "p":
                    if self.pausado.is_set():
                        self.pausado.clear()
                        self.log("Bot RETOMADO.")
                    else:
                        self.pausado.set()
                        self.log("Bot PAUSADO (aperte P para continuar). Pode mexer no jogo.")
                elif tecla == "q":
                    self.sair = True
            try:
                self._desenhar()
            except Exception:
                pass
            time.sleep(0.5)

    def _quadro_direito(self):
        e = self.estat
        L = []
        estado = "|| PAUSADO" if self.pausado.is_set() else "> RODANDO"
        L.append(f" {estado:<20} ligado ha {e.tempo_ligado()}")
        L.append(" " + "-" * (LARGURA_PAINEL - 2))
        L.append(f" {'':8}{'atual':>10}{'inicio':>10}{'colhido':>11}{'/min':>9}")
        pm = e.por_minuto()
        for n in NOMES:
            atual = e.atual[n] if e.atual else None
            ini = e.inicio[n] if e.inicio else None
            L.append(f" {ROTULOS[n]:<8}{_num(atual):>10}{_num(ini):>10}"
                     f"{_num(e.colhido[n], True):>11}{_num(pm[n], True):>9}")
        L.append(" " + "-" * (LARGURA_PAINEL - 2))
        L.append(" Gasto desde o inicio (campos usam madeira):")
        L.append("   " + "  ".join(f"{ROTULOS[n]} {_num(e.gasto[n])}" for n in ("madeira", "ouro")))
        L.append("   " + "  ".join(f"{ROTULOS[n]} {_num(e.gasto[n])}" for n in ("bife", "pedra")))
        if e.atual and e.inicio:
            L.append(" Saldo da madeira: " + _num(e.atual["madeira"] - e.inicio["madeira"], True))
        L.append(" " + "-" * (LARGURA_PAINEL - 2))
        L.append(f" Colheitas: {_num(e.colheitas)}   Replantios: {_num(e.replantios)}")
        L.append("")
        L.append(" [P] pausar / continuar    [Q] sair")
        L.append(" /min = media dos ultimos 10 min")
        return L

    def _desenhar(self):
        cols, rows = shutil.get_terminal_size((120, 30))
        largura_dir = LARGURA_PAINEL if cols >= LARGURA_PAINEL + 40 else 0
        largura_esq = cols - largura_dir - (1 if largura_dir else 0) - 1
        direita = self._quadro_direito() if largura_dir else []
        with self._lock:
            recentes = list(self.linhas)[-(rows - 1):]
        esquerda = []
        for linha in recentes:  # quebra linhas longas (recuo de 11 = largura da hora)
            esquerda.append(linha[:largura_esq])
            resto = linha[largura_esq:]
            while resto:
                esquerda.append(" " * 11 + resto[:largura_esq - 11])
                resto = resto[largura_esq - 11:]
        esquerda = esquerda[-(rows - 1):]
        saida = ["\x1b[H"]
        for i in range(rows - 1):
            e = esquerda[i] if i < len(esquerda) else ""
            linha = e[:largura_esq].ljust(largura_esq)
            if largura_dir:
                d = direita[i] if i < len(direita) else ""
                linha += "|" + d[:largura_dir].ljust(largura_dir)
            saida.append(linha + "\n")
        sys.stdout.write("".join(saida))
        sys.stdout.flush()
