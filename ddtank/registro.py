# -*- coding: utf-8 -*-
"""
Gravacao do proprio bot em acao (caixa-preta): cada decisao, clique, tecla e turno de tiro, com
prints dos momentos-chave. Mesmo formato do gravador.py (eventos.jsonl + resumo.txt + frames/),
entao o empacotar.py / ENVIAR_SESSAO.bat funcionam igual.

  sessoes/<data>_bot/  eventos.jsonl  resumo.txt  frames/0001_clique_antes.jpg ...

So as ultimas MAX_SESSOES sessoes do bot ficam no disco.
"""
import datetime
import json
import os
import queue
import shutil
import threading
import time

import cv2

import config

LARGURA = 1280
MAX_SESSOES = 4


class Registro:
    def __init__(self, nota="bot", base=None, max_sessoes=MAX_SESSOES):
        base = base or os.path.join(config.PASTA, "sessoes")
        nome = f"{datetime.datetime.now():%Y%m%d_%H%M%S}_{nota}"
        self.pasta = os.path.join(base, nome)
        self.pasta_frames = os.path.join(self.pasta, "frames")
        os.makedirs(self.pasta_frames, exist_ok=True)
        self._limpar_antigas(base, nome, max_sessoes, nota)
        self.t0 = time.time()
        self.n = 0
        self.eventos = []
        self.trava = threading.Lock()
        self.arq = open(os.path.join(self.pasta, "eventos.jsonl"), "w", encoding="utf-8")
        self.fila = queue.Queue()
        self.thread = threading.Thread(target=self._gravar, daemon=True)
        self.thread.start()
        json.dump({"inicio": datetime.datetime.now().isoformat(), "tipo": "bot", "nota": nota},
                  open(os.path.join(self.pasta, "meta.json"), "w", encoding="utf-8"), ensure_ascii=False)

    @staticmethod
    def _limpar_antigas(base, atual, maximo, nota):
        try:
            antigas = sorted(p for p in os.listdir(base) if p.endswith("_" + nota) and p != atual)
            for p in antigas[:-(maximo - 1)] if maximo > 1 else antigas:
                shutil.rmtree(os.path.join(base, p), ignore_errors=True)
        except OSError:
            pass

    def agora(self):
        return round(time.time() - self.t0, 3)

    def _gravar(self):
        while True:
            item = self.fila.get()
            if item is None:
                return
            caminho, img = item
            cv2.imwrite(caminho, img, [cv2.IMWRITE_JPEG_QUALITY, 85])

    def frame(self, img, rotulo):
        """Guarda um print (reduzido a 1280 de largura). Devolve o nome do arquivo (ou None)."""
        if img is None:
            return None
        h, w = img.shape[:2]
        if w != LARGURA:
            img = cv2.resize(img, (LARGURA, int(h * LARGURA / w)), interpolation=cv2.INTER_AREA)
        with self.trava:
            self.n += 1
            nome = f"{self.n:04d}_{rotulo}.jpg"
        self.fila.put((os.path.join(self.pasta_frames, nome), img.copy()))
        return nome

    def evento(self, tipo, frames=None, **dados):
        ev = {"t": self.agora(), "tipo": tipo, "frames": [f for f in (frames or []) if f], **dados}
        with self.trava:
            self.eventos.append(ev)
            self.arq.write(json.dumps(ev, ensure_ascii=False, default=float) + "\n")
            self.arq.flush()
        return ev

    def fechar(self):
        self.fila.put(None)
        self.thread.join(timeout=10)
        self.arq.close()
        linhas = []
        for ev in self.eventos:
            mm, ss = divmod(ev["t"], 60)
            extra = {k: v for k, v in ev.items() if k not in ("t", "tipo", "frames")}
            linhas.append(f"[{int(mm):02d}:{ss:04.1f}] {ev['tipo']} {json.dumps(extra, ensure_ascii=False, default=float)}  {' '.join(ev['frames'])}")
        with open(os.path.join(self.pasta, "resumo.txt"), "w", encoding="utf-8") as f:
            f.write("\n".join(linhas) + "\n")
        return self.pasta
