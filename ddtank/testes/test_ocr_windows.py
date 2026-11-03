# -*- coding: utf-8 -*-
"""Numero do angulo pelo OCR do Windows (ocr_windows.py). Rode: python testes/test_ocr_windows.py
Le quadros reais gravados em sessoes/ (se existirem nesta maquina) e confere com o angulo que o jogo enviou."""
import glob
import os
import sys

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(AQUI))
import cv2
import ocr_windows as O

assert O.OcrAngulo._numero("46") == 46 and O.OcrAngulo._numero("-6") == -6 and O.OcrAngulo._numero("7 5") == 75
assert O.OcrAngulo._numero("4a") is None and O.OcrAngulo._numero("") is None and O.OcrAngulo._numero("123") is None
assert O.OcrAngulo._numero("l6") == 16 and O.OcrAngulo._numero("O") == 0
print("texto do OCR -> numero (negativo, espacos, letras parecidas) OK")

# quadros do teste ao vivo de 03/11 (o numero na tela = o angulo que a rede mostrou no tiro)
casos = {"20261103_042017_pvp/frames/0063_tiro_dado.jpg": 60, "20261103_042017_pvp/frames/0074_tiro_dado.jpg": 60,
         "20261103_042017_pvp/frames/0014_tiro_dado.jpg": 57, "20261103_042017_pvp/frames/0143_tiro_dado.jpg": 30}
pasta = os.path.join(os.path.dirname(AQUI), "sessoes")
existentes = {k: v for k, v in casos.items() if os.path.exists(os.path.join(pasta, k))}
if existentes and sys.platform == "win32":
    o = O.OcrAngulo()
    lidos = {k: o.angulo(cv2.imread(os.path.join(pasta, k))) for k in existentes}
    o.fechar()
    assert all(v is None or v == existentes[k] for k, v in lidos.items()), lidos
    assert sum(v is not None for v in lidos.values()) >= len(lidos) - 1, lidos
    print(f"OCR do Windows nos quadros reais: {lidos} OK")
else:
    print("(sem os quadros gravados ou fora do Windows: teste do OCR real pulado)")
print("\nocr_windows OK")
