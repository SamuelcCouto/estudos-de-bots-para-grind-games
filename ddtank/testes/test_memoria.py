# -*- coding: utf-8 -*-
"""Previsor de tiro: validacao leave-one-out nos tiros do usuario. Rode: python testes/test_memoria.py"""
import json
import os
import sys
import tempfile

import numpy as np

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(AQUI))
import memoria as M

tiros = json.load(open(M.ARQ_SEMENTE, encoding="utf-8"))["tiros"]
print(len(tiros), "tiros semente")
rs = {i: M.Memoria(arq_aprendizado=None).constante_r(i) for i in ("FANTASMA", "PROFUNDEZAS", "MINHOCAO")}
print("constante R por instancia (mediana, confiavel?):", {k: (round(v[0], 1) if v[0] else None, v[1]) for k, v in rs.items()})
assert rs["MINHOCAO"][1] and rs["FANTASMA"][1], "Minhocao e Fantasma deveriam ter R confiavel"

# leave-one-out: remove o tiro e preve a forca com os demais
print(f"\n{'instancia':12s} {'azul':>12s} {'boss':>12s} {'ang real':>8s} {'forca real':>10s} | previsto (origem)")
erros = {}
for k, t in enumerate(tiros):
    resto = [x for j, x in enumerate(tiros) if j != k]
    tmp = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8")
    json.dump({"tiros": resto}, tmp); tmp.close()
    m = M.Memoria(arq_semente=tmp.name, arq_aprendizado=None); os.unlink(tmp.name)
    p = m.prever(t["inst"], tuple(t["azul"]), tuple(t["boss"]))
    # compara a forca prevista com a que o usuario usou NO MESMO ANGULO (a fisica tambem prevê com o angulo dele)
    forca_no_mesmo_angulo = p["forca"]
    if p["origem"] == "fisica":
        dx, dy = t["boss"][0] - t["azul"][0], t["azul"][1] - t["boss"][1]
        r, _ = m.constante_r(t["inst"]); f = M.fator_balistico(dx, dy, t["angulo"])
        forca_no_mesmo_angulo = float(np.sqrt(r * f)) if f else p["forca"]
    e = forca_no_mesmo_angulo - t["forca"]
    erros.setdefault(t["inst"], []).append(e)
    print(f"{t['inst']:12s} {str(tuple(t['azul'])):>12s} {str(tuple(t['boss'])):>12s} {t['angulo']:8.1f} {t['forca']:10d} | "
          f"ang {p['angulo']:4.1f} forca {p['forca']:4.1f} ({p['origem']}); forca no angulo do usuario {forca_no_mesmo_angulo:4.1f} (erro {e:+.0f})")
print()
for k, v in erros.items():
    print(f"{k:12s} erro medio {np.mean(np.abs(v)):4.1f} pontos de forca (max {np.max(np.abs(v)):.0f}), n={len(v)}")
print("\nprevisor OK (informativo: o acerto depende da hitbox; Profundezas e a instancia com mais variacao)")
