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

# ======================================================================================
# INSTANCIA NOVA: o bot nunca viu essa constante R. Acerta por tentativa e erro inteligente?
# Mundo simulado: o tiro acerta se a forca esta a +-22% da ideal (hitbox grande). So o resultado (acertou/errou) e informado.
# ======================================================================================
import tempfile
print("\n=== instancia NOVA: busca da forca certa (so com acertou/errou) ===")
def sessao(R_real, dx=60.0, dy=0.0, n=10, tol=0.22, inst="NOVA"):
    tmp = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False); tmp.close(); os.unlink(tmp.name)
    mem = M.Memoria(arq_semente=None, arq_aprendizado=tmp.name)
    azul, boss = (20.0, 50.0), (20.0 + dx, 50.0 - dy)
    historico = []
    for k in range(n):
        p = mem.prever(inst, azul, boss)
        ideal = np.sqrt(R_real * M.fator_balistico(dx, dy, p["angulo"]))
        acertou = abs(p["forca"] - ideal) <= tol * ideal and p["forca"] < 95
        mem.registrar(inst, azul, boss, p["angulo"], p["forca"], acertou)
        historico.append((p["angulo"], p["forca"], ideal, acertou, p["origem"]))
    return historico

for R_real in (12, 28, 56, 90):
    h = sessao(R_real)
    primeiro = next((i + 1 for i, x in enumerate(h) if x[3]), None)
    linha = " ".join(f"{x[1]:.0f}{'*' if x[3] else '.'}" for x in h)
    print(f"R real {R_real:4d}: forca tentada por tiro (* acertou): {linha}   -> 1o acerto no tiro {primeiro}")
    assert primeiro is not None and primeiro <= 5, f"R={R_real}: demorou demais ({primeiro})"
    assert all(x[3] for x in h[primeiro:]), f"R={R_real}: depois de acertar voltou a errar: {h}"
print("busca ok: acerta em <=5 tiros e depois nao volta a errar")

# depois de calibrado, generaliza para OUTRAS posicoes (a instancia tem spawns/bosses diferentes)
rng = np.random.default_rng(3)
R_real = 40.0
tmp = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False); tmp.close(); os.unlink(tmp.name)
mem = M.Memoria(arq_semente=None, arq_aprendizado=tmp.name)
acertos = 0; total = 0
for k in range(40):
    dx = float(rng.uniform(30, 90)); dy = float(rng.uniform(-15, 15))
    azul, boss = (10.0, 50.0), (10.0 + dx, 50.0 - dy)
    p = mem.prever("OUTRA", azul, boss)
    ideal = np.sqrt(R_real * M.fator_balistico(dx, dy, p["angulo"]))
    ok = abs(p["forca"] - ideal) <= 0.22 * ideal and p["forca"] < 95
    mem.registrar("OUTRA", azul, boss, p["angulo"], p["forca"], ok)
    if k >= 8: acertos += ok; total += 1
print(f"geometrias variadas (spawn/boss diferentes), depois de 8 tiros de aprendizado: {acertos}/{total} acertos")
assert acertos / total >= 0.85, acertos / total
print("\ngeneralizacao OK")
