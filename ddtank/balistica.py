# -*- coding: utf-8 -*-
"""
Forca necessaria para uma distancia e um angulo, a partir das tabelas 'EstrAng' do servidor
(dados/tabelas_forca.json: angulos 20, 30, 50 e 65 graus, distancias 1..20).

Sem vento. Entre as distancias a interpolacao e linear; entre os angulos, uma parabola
ajustada nos 4 pontos (a forca tem minimo perto de 40-45 graus, entao linear nao serve).
O vento e a altura do alvo entram numa proxima etapa (calibracao com tiros reais).
"""
import json
import os

import numpy as np

_ARQ = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dados", "tabelas_forca.json")
_t = json.load(open(_ARQ, encoding="utf-8"))
ANGULOS = [int(a) for a in _t if a.isdigit()]
_DIST = np.arange(1, 21)
_TAB = np.array([_t[str(a)] for a in ANGULOS], float)   # [angulo][distancia-1]


def forca_para(distancia, angulo):
    """Forca estimada. distancia em 1..20 (fracoes valem), angulo em graus."""
    if not 1 <= distancia <= 20:
        raise ValueError("distancia fora da tabela (1..20)")
    por_angulo = [np.interp(distancia, _DIST, linha) for linha in _TAB]
    a, b, c = np.polyfit(ANGULOS, por_angulo, 2)
    return float(a * angulo ** 2 + b * angulo + c)


if __name__ == "__main__":
    for ang in (20, 30, 40, 50, 65):
        print(f"{ang:>2} graus:", " ".join(f"d{d}={forca_para(d, ang):5.1f}" for d in (1, 5, 10, 15, 20)))
