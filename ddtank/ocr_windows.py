# -*- coding: utf-8 -*-
"""
Numero do angulo no mostrador pelo OCR do proprio Windows (Windows.Media.Ocr, sem instalar nada): um PowerShell fica aberto
(ocr_windows.ps1) e responde cada imagem em ~0,1 s. O ponteiro lido pela geometria erra ate 2 graus; o numero e exato (03/11).

    ocr = OcrAngulo()
    ocr.angulo(quadro)   # int (pode ser negativo) ou None
"""
import os
import re
import subprocess
import tempfile
import threading

import cv2

AQUI = os.path.dirname(os.path.abspath(__file__))
NUMERO = (526, 550, 326, 372)        # y0, y1, x0, x1 do numero embaixo do pivo do mostrador (quadro de 1280)
ESCALA = 6


class OcrAngulo:
    def __init__(self, tempo_max=2.0):
        self.proc = None
        self.tempo_max = tempo_max
        self.pasta = tempfile.mkdtemp(prefix="ocr_ddt_")
        self.lock = threading.Lock()
        self.falhou = False

    def _abrir(self):
        if self.proc and self.proc.poll() is None:
            return True
        if self.falhou:
            return False
        try:
            self.proc = subprocess.Popen(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", os.path.join(AQUI, "ocr_windows.ps1")],
                                         stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, bufsize=1,
                                         creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            pronto = self.proc.stdout.readline().strip()
            if pronto != "PRONTO":
                raise OSError("OCR do Windows nao iniciou")
            return True
        except OSError:
            self.falhou = True
            self.proc = None
            return False

    def texto(self, img):
        with self.lock:
            if not self._abrir():
                return None
            self.n = getattr(self, "n", 0) + 1                # nome NOVO a cada leitura (com o mesmo nome o Windows devolvia a imagem velha)
            arq = os.path.join(self.pasta, f"n{self.n}.png")
            cv2.imwrite(arq, img)
            try:
                self.proc.stdin.write(arq + "\n")
                self.proc.stdin.flush()
                linha = self.proc.stdout.readline()
            except (OSError, ValueError):
                self.proc = None
                return None
            velho = os.path.join(self.pasta, f"n{self.n - 3}.png")
            if os.path.exists(velho):
                try:
                    os.remove(velho)
                except OSError:
                    pass
            return linha[2:].strip() if linha.startswith("R:") else None

    @staticmethod
    def _numero(t):
        if not t:
            return None
        t = t.replace(" ", "").replace("O", "0").replace("o", "0").replace("l", "1").replace("I", "1").replace("S", "5")
        m = re.fullmatch(r"(-?)(\d{1,2})", t)
        return int(m.group(1) + m.group(2)) if m else None

    def angulo(self, quadro):
        """Numero do angulo no mostrador (int) ou None. Tenta a imagem colorida e depois o canal mais claro (os numeros mudam de cor):
        em 32 quadros, 29 lidos e nenhum errado (03/11)."""
        y0, y1, x0, x1 = NUMERO
        if quadro is None or getattr(quadro, "ndim", 0) != 3 or quadro.shape[0] < y1 or quadro.shape[1] < x1:
            return None
        c = quadro[y0:y1, x0:x1]
        n = self._numero(self.texto(cv2.resize(c, None, fx=ESCALA, fy=ESCALA, interpolation=cv2.INTER_CUBIC)))
        if n is None:
            g = cv2.resize(c.max(axis=2), None, fx=ESCALA, fy=ESCALA, interpolation=cv2.INTER_CUBIC)
            n = self._numero(self.texto(cv2.copyMakeBorder(g, 30, 30, 30, 30, cv2.BORDER_CONSTANT, value=0)))
        return n

    def fechar(self):
        if self.proc:
            try:
                self.proc.stdin.write("\n")
                self.proc.stdin.flush()
                self.proc.wait(timeout=3)
            except (OSError, ValueError, subprocess.TimeoutExpired):
                self.proc.kill()
            self.proc = None
