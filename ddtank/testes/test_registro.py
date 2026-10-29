# -*- coding: utf-8 -*-
"""Gravacao do bot e trava de instancia unica. Rode: python testes/test_registro.py"""
import ctypes
import json
import os
import sys
import tempfile
from unittest import mock

import numpy as np

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(AQUI))
import registro as R

base = tempfile.mkdtemp()
for k in range(6):                       # so as ultimas 4 sessoes ficam
    r = R.Registro("bot", base=base, max_sessoes=4)
    f = r.frame(np.full((1034, 1922, 3), 90, np.uint8), "teste")
    r.evento("bot_clique", [f], ponto=[10, 20], instancia="FANTASMA")
    r.fechar()
    os.makedirs(os.path.join(base, f"2000010{k}_000000_bot"), exist_ok=True)   # sessoes velhas fingidas
ev = [json.loads(l) for l in open(os.path.join(r.pasta, "eventos.jsonl"), encoding="utf-8")]
assert ev[0]["tipo"] == "bot_clique" and ev[0]["ponto"] == [10, 20]
assert os.path.exists(os.path.join(r.pasta, "frames", ev[0]["frames"][0])) and os.path.exists(os.path.join(r.pasta, "resumo.txt"))
import cv2
assert cv2.imread(os.path.join(r.pasta, "frames", ev[0]["frames"][0])).shape[1] == 1280      # reduzido a 1280
print("registro OK:", os.path.basename(r.pasta), "| resumo:", open(os.path.join(r.pasta, "resumo.txt"), encoding="utf-8").read().strip()[:90])

# instancia unica: o 2o GetLastError==183 (ERROR_ALREADY_EXISTS) recusa
ctypes.windll = mock.MagicMock(); ctypes.WINFUNCTYPE = ctypes.CFUNCTYPE
import navegador as N
ctypes.windll.kernel32.GetLastError.return_value = 0
assert N.instancia_unica() is True
ctypes.windll.kernel32.GetLastError.return_value = 183
assert N.instancia_unica() is False
print("trava de instancia unica OK (a segunda copia e recusada)")

# ---- empacotar --novas: empacota TODAS as sessoes ainda nao enviadas (a gravacao do usuario nao e a mais recente)
import empacotar as EMP
import config as CFG
import tempfile as _tf
raiz = _tf.mkdtemp()
antiga = CFG.PASTA
CFG.PASTA = raiz
try:
    for nome in ("20261029_100000", "20261029_110000_bot"):
        os.makedirs(os.path.join(raiz, "sessoes", nome, "frames"))
    open(os.path.join(raiz, "sessoes", "20261029_100000", ".enviada"), "w").close()
    assert [os.path.basename(p) for p in EMP.sessoes_novas()] == ["20261029_110000_bot"]
    os.makedirs(os.path.join(raiz, "sessoes", "20261029_090000", "frames"))
    assert [os.path.basename(p) for p in EMP.sessoes_novas()] == ["20261029_090000", "20261029_110000_bot"]
finally:
    CFG.PASTA = antiga
print("empacotar --novas OK")
