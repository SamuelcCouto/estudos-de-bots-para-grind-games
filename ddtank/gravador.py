# -*- coding: utf-8 -*-
"""
Gravador de sessao: voce joga normalmente e ele registra tudo para eu estudar depois.
NAO controla nada (nao clica, nao digita): so observa.

O que registra (somente com a janela do jogo em primeiro plano - o que voce faz em
outros programas nao e gravado):
  - cada clique (posicao, botao, duracao) e cada tecla (quanto tempo ficou segurada:
    segurar a barra de espaco = a forca do tiro)
  - prints do jogo: um pouco ANTES de cada acao, e DEPOIS dela (a bala, o resultado)
  - um print sempre que a tela muda de verdade (no maximo 1 por segundo)

Uso:   python gravador.py            (ou de dois cliques em GRAVAR_SESSAO.bat)
       python gravador.py --nota "rota 1, Fantasma"
Durante a gravacao:  F9 = marcador ("agora comecou a luta", "errei o tiro"...)
                     F10 = terminar (ou Ctrl+C no console)
Saida: sessoes\\<data>_<nota>\\  eventos.jsonl, resumo.txt, meta.json e frames\\
Depois rode  python empacotar.py  para gerar zips pequenos e me enviar.
"""
import argparse
import ctypes
import ctypes.wintypes as W
import datetime
import json
import os
import queue
import re
import sys
import threading
import time

import cv2
import numpy as np

import config
import janela
from janela import user32

VK_F9, VK_F10 = 0x78, 0x79
BOTOES = {0x01: "esquerdo", 0x02: "direito", 0x04: "meio"}
NOMES_EXTRAS = {0x08: "backspace", 0x09: "tab", 0x0D: "enter", 0x1B: "esc", 0x20: "espaco",
                0x21: "pgup", 0x22: "pgdn", 0x23: "end", 0x24: "home", 0x25: "esquerda",
                0x26: "cima", 0x27: "direita", 0x28: "baixo", 0x2D: "insert", 0x2E: "delete",
                0xA0: "shift", 0xA1: "shift", 0xA2: "ctrl", 0xA3: "ctrl", 0xA4: "alt", 0xA5: "alt",
                0x14: "capslock", 0xC0: "'", 0xBA: ";", 0xBC: ",", 0xBE: ".", 0xBF: "/"}
TECLAS_OBSERVADAS = [vk for vk in range(0x08, 0xFF) if vk not in (0x10, 0x11, 0x12, VK_F9, VK_F10)]

user32.GetForegroundWindow.restype = W.HWND
user32.GetAncestor.restype = W.HWND
user32.GetAncestor.argtypes = [W.HWND, W.UINT]
user32.GetAsyncKeyState.restype = ctypes.c_short


def nome_da_tecla(vk):
    if vk in NOMES_EXTRAS:
        return NOMES_EXTRAS[vk]
    if 0x30 <= vk <= 0x39 or 0x41 <= vk <= 0x5A:
        return chr(vk)
    if 0x60 <= vk <= 0x69:
        return f"num{vk - 0x60}"
    if 0x70 <= vk <= 0x87:
        return f"F{vk - 0x6F}"
    return f"VK_{vk:02X}"


def apertado(vk):
    return bool(user32.GetAsyncKeyState(vk) & 0x8000)


class Gravador:
    def __init__(self, hwnd, pasta, amostragem=0.3, intervalo_auto=1.0, formato="jpg"):
        self.hwnd = hwnd
        self.pasta = pasta
        self.pasta_frames = os.path.join(pasta, "frames")
        os.makedirs(self.pasta_frames, exist_ok=True)
        self.amostragem = amostragem
        self.intervalo_auto = intervalo_auto
        self.formato = formato
        self.t0 = time.time()
        self.parar = threading.Event()
        self.trava = threading.Lock()
        self.ultimo = None            # (t, imagem) do ultimo quadro amostrado
        self.pendentes = []           # (quando, nome_do_arquivo): quadros "depois" a salvar
        self.n_frames = 0
        self.fila_disco = queue.Queue()
        self.eventos = []
        self.arq_eventos = open(os.path.join(pasta, "eventos.jsonl"), "w", encoding="utf-8")
        self._ultimo_auto = (0.0, None)

    # ---------- tempo / arquivos ----------
    def agora(self):
        return round(time.time() - self.t0, 3)

    def _novo_nome(self, rotulo):
        with self.trava:
            self.n_frames += 1
            n = self.n_frames
        return f"{n:04d}_{rotulo}.{self.formato}"

    def salvar(self, img, rotulo):
        nome = self._novo_nome(rotulo)
        self.fila_disco.put((os.path.join(self.pasta_frames, nome), img))
        return nome

    def agendar_depois(self, rotulo, atraso):
        """Reserva um nome e salva o primeiro quadro amostrado apos `atraso` segundos."""
        quando = time.time() + atraso
        with self.trava:
            if any(abs(q - quando) < 0.25 for q, _ in self.pendentes):
                return None   # ja tem um quadro "depois" quase na mesma hora
        nome = self._novo_nome(rotulo)
        with self.trava:
            self.pendentes.append((quando, nome))
        return nome

    # ---------- threads ----------
    def _gravar_disco(self):
        while True:
            item = self.fila_disco.get()
            if item is None:
                return
            caminho, img = item
            if caminho.endswith(".jpg"):
                cv2.imwrite(caminho, img, [cv2.IMWRITE_JPEG_QUALITY, 92])
            else:
                cv2.imwrite(caminho, img)

    def _amostrar(self):
        modo = self.modo_captura
        while not self.parar.is_set():
            ini = time.time()
            img = janela.capturar(self.hwnd, modo)
            if img is not None:
                with self.trava:
                    self.ultimo = (ini, img)
                    prontos = [p for p in self.pendentes if p[0] <= ini]
                    self.pendentes = [p for p in self.pendentes if p[0] > ini]
                for _, nome in prontos:
                    self.fila_disco.put((os.path.join(self.pasta_frames, nome), img))
                self._quadro_automatico(ini, img)
            resto = self.amostragem - (time.time() - ini)
            if resto > 0:
                time.sleep(resto)

    def _quadro_automatico(self, t, img):
        """Salva quando a tela mudou de verdade (no maximo 1 por `intervalo_auto`)."""
        ultimo_t, ultima_mini = self._ultimo_auto
        if t - ultimo_t < self.intervalo_auto:
            return
        mini = cv2.resize(cv2.cvtColor(img, cv2.COLOR_BGR2GRAY), (96, 54), interpolation=cv2.INTER_AREA)
        if ultima_mini is None or np.abs(mini.astype(np.int16) - ultima_mini).mean() > 1.5:
            nome = self.salvar(img, "auto")
            self._registrar({"t": round(t - self.t0, 3), "tipo": "tela_mudou", "frames": [nome]})
            self._ultimo_auto = (t, mini.astype(np.int16))

    # ---------- eventos ----------
    def _registrar(self, ev):
        with self.trava:
            self.eventos.append(ev)
            self.arq_eventos.write(json.dumps(ev, ensure_ascii=False) + "\n")
            self.arq_eventos.flush()
        if ev["tipo"] != "tela_mudou":
            print(f"  [{ev['t']:7.1f}s] {self.descrever(ev)}")

    def _quadro_atual(self, rotulo):
        with self.trava:
            ultimo = self.ultimo
        return self.salvar(ultimo[1], rotulo) if ultimo else None

    def _depois(self, rotulo, *atrasos):
        return [n for n in (self.agendar_depois(rotulo, a) for a in atrasos) if n]

    def _jogo_em_foco(self):
        fg = user32.GetForegroundWindow()
        return bool(fg) and user32.GetAncestor(fg, 2) == user32.GetAncestor(self.hwnd, 2)

    def _cursor(self):
        pt = W.POINT()
        user32.GetCursorPos(ctypes.byref(pt))
        user32.ScreenToClient(self.hwnd, ctypes.byref(pt))
        return pt.x, pt.y

    def rodar(self):
        threading.Thread(target=self._gravar_disco, daemon=True).start()
        amostrador = threading.Thread(target=self._amostrar, daemon=True)
        amostrador.start()
        w, h = janela.tamanho(self.hwnd)
        print(f"Gravando ({w}x{h}). F9 = marcador, F10 = terminar. Pode jogar normalmente.")
        mouse = {vk: None for vk in BOTOES}   # vk -> (t, x, y, frame_antes) enquanto apertado
        teclas = {}                            # vk -> (t, frame_antes)
        f9_antes = False
        try:
            while not self.parar.is_set():
                if apertado(VK_F10):
                    break
                f9 = apertado(VK_F9)
                if f9 and not f9_antes:
                    nome = self._quadro_atual("marcador")
                    self._registrar({"t": self.agora(), "tipo": "marcador", "frames": [nome] if nome else []})
                f9_antes = f9
                foco = self._jogo_em_foco()
                x, y = self._cursor()
                dentro = 0 <= x < w and 0 <= y < h
                for vk, nome_botao in BOTOES.items():
                    ligado = foco and dentro and apertado(vk)
                    if ligado and mouse[vk] is None:
                        mouse[vk] = (self.agora(), x, y, self._quadro_atual("clique_antes"))
                    elif not ligado and mouse[vk] is not None:
                        t, x0, y0, antes = mouse[vk]
                        mouse[vk] = None
                        ev = {"t": t, "tipo": "mouse", "botao": nome_botao, "x": x0, "y": y0,
                              "x_solto": x, "y_solto": y, "duracao": round(self.agora() - t, 3),
                              "frames": [n for n in [antes] + self._depois("clique_depois", 0.5) if n]}
                        self._registrar(ev)
                for vk in TECLAS_OBSERVADAS:
                    ligado = foco and apertado(vk)
                    if ligado and vk not in teclas:
                        teclas[vk] = (self.agora(), self._quadro_atual("tecla_antes"))
                    elif not ligado and vk in teclas:
                        t, antes = teclas.pop(vk)
                        dur = round(self.agora() - t, 3)
                        frames = [antes] if antes else []
                        if dur >= 0.25:   # tecla segurada (ex.: espaco = carregar a forca)
                            frames.append(self._quadro_atual("solta_antes"))
                            frames += self._depois("solta_depois", 0.6, 2.0)
                        else:
                            frames += self._depois("tecla_depois", 0.5)
                        self._registrar({"t": t, "tipo": "tecla", "tecla": nome_da_tecla(vk),
                                         "duracao": dur, "frames": [n for n in frames if n]})
                time.sleep(0.01)
        except KeyboardInterrupt:
            pass
        print("Finalizando (salvando os ultimos quadros)...")
        time.sleep(2.2)
        self.parar.set()
        amostrador.join(timeout=3)
        self.fila_disco.put(None)
        time.sleep(0.5)
        while not self.fila_disco.empty():
            time.sleep(0.2)
        self.arq_eventos.close()
        self._resumo()

    # ---------- resumo legivel ----------
    @staticmethod
    def descrever(ev):
        tipo = ev["tipo"]
        if tipo == "mouse":
            desc = f"clique {ev['botao']} em ({ev['x']},{ev['y']}) por {ev['duracao']}s"
            if abs(ev["x"] - ev["x_solto"]) + abs(ev["y"] - ev["y_solto"]) > 12:
                desc += f" arrastando ate ({ev['x_solto']},{ev['y_solto']})"
            return desc
        if tipo == "tecla":
            return f"tecla {ev['tecla']} segurada {ev['duracao']}s"
        return "MARCADOR (F9)" if tipo == "marcador" else "tela mudou"

    def _resumo(self):
        linhas = []
        for ev in sorted(self.eventos, key=lambda e: e["t"]):
            mm, ss = divmod(ev["t"], 60)
            frames = [f for f in ev.get("frames", []) if os.path.exists(os.path.join(self.pasta_frames, f))]
            linhas.append(f"[{int(mm):02d}:{ss:04.1f}] {self.descrever(ev)}  {' '.join(frames)}")
        with open(os.path.join(self.pasta, "resumo.txt"), "w", encoding="utf-8") as f:
            f.write("\n".join(linhas) + "\n")
        n = len(os.listdir(self.pasta_frames))
        print(f"Pronto: {len(self.eventos)} eventos, {n} quadros em {self.pasta}")


def main():
    ap = argparse.ArgumentParser(description="Grava sua sessao de jogo (so observa)")
    ap.add_argument("--titulo", default="")
    ap.add_argument("--exe", default="")
    ap.add_argument("--modo", choices=("print", "tela"), default="print")
    ap.add_argument("--nota", default="", help="nome curto da sessao, ex.: 'rota1 fantasma'")
    ap.add_argument("--amostragem", type=float, default=0.3, help="segundos entre quadros de memoria")
    ap.add_argument("--formato", choices=("jpg", "png"), default="jpg")
    args = ap.parse_args()

    hwnd = janela.resolver_janela(args.titulo or config.TITULO_JANELA, args.exe or config.EXE_JANELA)
    if not hwnd:
        sys.exit("Janela do jogo nao encontrada. Rode  python bot_ddtank.py --listar  e use --titulo/--exe.")
    nota = re.sub(r"[^A-Za-z0-9_-]+", "_", args.nota).strip("_")
    nome = f"{datetime.datetime.now():%Y%m%d_%H%M%S}" + (f"_{nota}" if nota else "")
    pasta = os.path.join(config.PASTA, "sessoes", nome)
    g = Gravador(hwnd, pasta, args.amostragem, formato=args.formato)
    g.modo_captura = args.modo
    w, h = janela.tamanho(hwnd)
    json.dump({"inicio": datetime.datetime.now().isoformat(), "janela": {"w": w, "h": h},
               "nota": args.nota, "amostragem": args.amostragem, "modo": args.modo},
              open(os.path.join(pasta, "meta.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    g.rodar()


if __name__ == "__main__":
    main()
