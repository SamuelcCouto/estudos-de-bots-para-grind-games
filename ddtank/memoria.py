# -*- coding: utf-8 -*-
"""
Memoria de tiros e previsor de (angulo, forca).

Cada tiro e guardado como: instancia, posicao do jogador e do boss no minimapa, angulo, forca e se
acertou. Para um tiro novo, em ordem:
  1) "memoria": ha acertos na MESMA situacao (jogador e boss em posicoes quase iguais) -> repete;
  2) "fisica": a instancia tem uma constante R confiavel (forca^2 = R * F(dx, dy, angulo)) -> calcula;
  3) "vizinho": o acerto mais parecido, mesmo que distante;
  4) "padrao": nada sabido da instancia.
Erros (nao acertou) deslocam a forca da proxima tentativa na mesma situacao.

F vem da balistica sem vento nem arrasto: v^2 = g*dx^2 / (2 cos^2(a) (dx tan(a) - dy)).
"""
import json
import os

import numpy as np

import config

ARQ_SEMENTE = os.path.join(config.PASTA, "dados", "tiros_semente.json")
ARQ_APRENDIZADO = os.path.join(config.PASTA, "dados", "aprendizado.json")
DIST_MESMA_SITUACAO = 6.0     # px de minimapa (L1, soma de jogador + boss)
ANGULO_MIN, ANGULO_MAX = 15.0, 70.0
FORCA_MIN, FORCA_MAX = 8.0, 95.0
R_PADRAO = 38.0               # mediana das instancias medidas (Minhocao ~30, Fantasma ~55)
ANGULO_PADRAO = 30.0


def fator_balistico(dx, dy_up, ang):
    """F(dx, dy, angulo) em px de minimapa; None se o angulo nao alcanca o alvo."""
    t = np.radians(ang)
    den = 2 * np.cos(t) ** 2 * (dx * np.tan(t) - dy_up)
    return None if den <= 0 else dx * dx / den


class Memoria:
    def __init__(self, arq_semente=ARQ_SEMENTE, arq_aprendizado=ARQ_APRENDIZADO):
        self.arq_aprendizado = arq_aprendizado
        self.tiros = []
        for arq in (arq_semente, arq_aprendizado):
            if arq and os.path.exists(arq):
                self.tiros += json.load(open(arq, encoding="utf-8")).get("tiros", [])
        self.novos = []

    # ---------- consulta ----------
    def _da(self, inst):
        return [t for t in self.tiros if t["inst"] == inst]

    @staticmethod
    def _geom(t):
        (bx, by), (rx, ry) = t["azul"], t["boss"]
        return rx - bx, by - ry          # dx (boss a direita > 0), dy_up (boss mais alto > 0)

    def constante_r(self, inst):
        """(R mediano, confiavel?) da instancia, a partir dos acertos."""
        rs = []
        for t in self._da(inst):
            if not t["acertou"]:
                continue
            dx, dy = self._geom(t)
            f = fator_balistico(dx, dy, t["angulo"])
            if f:
                rs.append(t["forca"] ** 2 / f)
        if len(rs) < 3:
            return (float(np.median(rs)) if rs else None), False
        r = float(np.median(rs))
        return r, bool(np.std(rs) / r < 0.45)

    def prever(self, inst, azul, boss):
        """dict(angulo, forca, origem, detalhe). azul/boss = (x, y) do minimapa ou None."""
        acertos = [t for t in self._da(inst) if t["acertou"]]
        erros = [t for t in self._da(inst) if not t["acertou"]]
        if azul and boss and acertos:
            dist = lambda t: abs(t["azul"][0] - azul[0]) + abs(t["azul"][1] - azul[1]) + abs(t["boss"][0] - boss[0]) + abs(t["boss"][1] - boss[1])
            ordem = sorted(acertos, key=dist)
            melhor = dist(ordem[0])
            if melhor <= DIST_MESMA_SITUACAO:
                # so mistura (media) acertos com angulo parecido: 54 graus/15% e 12 graus/48% sao tiros DIFERENTES
                perto = [t for t in ordem if dist(t) <= melhor + 3 and abs(t["angulo"] - ordem[0]["angulo"]) <= 8]
                ang = float(np.mean([t["angulo"] for t in perto])); forca = float(np.mean([t["forca"] for t in perto]))
                # erro recente nesta mesma situacao com valores parecidos: tenta mais forte, e alterna
                for e in erros:
                    if dist(e) <= DIST_MESMA_SITUACAO and abs(e["forca"] - forca) < 6 and abs(e["angulo"] - ang) < 5:
                        forca += 8 if (len(erros) % 2) else -8
                return self._limites(ang, forca, "memoria", f"{len(perto)} acerto(s) na mesma situacao (dist {melhor:.1f})")
            r, ok = self.constante_r(inst)
            if ok:
                ang = float(np.clip(np.median([t["angulo"] for t in acertos]), ANGULO_MIN, ANGULO_MAX))
                dx, dy = boss[0] - azul[0], azul[1] - boss[1]
                f = fator_balistico(dx, dy, ang)
                if f:
                    return self._limites(ang, np.sqrt(r * f), "fisica", f"R={r:.0f}, dx={dx:.0f}, dy={dy:.0f}")
            t = ordem[0]
            return self._limites(t["angulo"], t["forca"], "vizinho", f"acerto mais parecido (dist {melhor:.1f})")
        if acertos:
            return self._limites(float(np.median([t["angulo"] for t in acertos])), float(np.median([t["forca"] for t in acertos])),
                                 "vizinho", "sem leitura do minimapa: mediana dos acertos")
        if azul and boss:
            dx, dy = boss[0] - azul[0], azul[1] - boss[1]
            f = fator_balistico(dx, dy, ANGULO_PADRAO)
            if f:
                return self._limites(ANGULO_PADRAO, np.sqrt(R_PADRAO * f), "padrao", "instancia sem dados")
        return self._limites(ANGULO_PADRAO, 50.0, "padrao", "sem dados nem minimapa")

    @staticmethod
    def _limites(ang, forca, origem, detalhe):
        return {"angulo": float(np.clip(ang, ANGULO_MIN, ANGULO_MAX)), "forca": float(np.clip(forca, FORCA_MIN, FORCA_MAX)),
                "origem": origem, "detalhe": detalhe}

    # ---------- aprendizado ----------
    def registrar(self, inst, azul, boss, angulo, forca, acertou, origem="bot"):
        if not (azul and boss):
            return
        t = {"inst": inst, "azul": [round(azul[0], 1), round(azul[1], 1)], "boss": [round(boss[0], 1), round(boss[1], 1)],
             "angulo": round(float(angulo), 1), "forca": round(float(forca)), "acertou": bool(acertou), "origem": origem}
        self.tiros.append(t)
        self.novos.append(t)
        self.salvar()

    def salvar(self):
        os.makedirs(os.path.dirname(self.arq_aprendizado), exist_ok=True)
        antigos = []
        if os.path.exists(self.arq_aprendizado):
            antigos = json.load(open(self.arq_aprendizado, encoding="utf-8")).get("tiros", [])
        json.dump({"tiros": (antigos + self.novos)[-2000:]}, open(self.arq_aprendizado, "w", encoding="utf-8"),
                  ensure_ascii=False, indent=1)
        self.novos = []
