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
# --- aprendizado da constante R (forca^2 = R * F): grade logaritmica + acertos/erros ---
R_GRADE = np.exp(np.linspace(np.log(6.0), np.log(250.0), 200))
R_PRIOR_SIGMA = 0.7           # incerteza (em ln) do palpite inicial R_PADRAO
TOL_ACERTO = 0.22             # um acerto aceita forca ate +-22% da "ideal" (hitbox grande)
TOL_ERRO = TOL_ACERTO         # um erro descarta exatamente a faixa que um acerto aceitaria (o erro pode ser do angulo: peso < 1)
PESO_OUTLIER = 0.2            # um acerto "fora do padrao" nao derruba o resto
PESO_ERRO = 0.1
INCERTEZA_CONFIAVEL = 2.2       # q75/q25 de R abaixo disso = constante confiavel


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

    def posterior_r(self, inst):
        """Distribuicao de R (grade, probabilidades) para a instancia. Prior: R_PADRAO. Cada ACERTO prende R perto do
        valor que ele implica (com tolerancia e chance de ser atipico); cada ERRO descarta, fracamente, os R
        proximos do que ele implicaria. Sem dados, vale o prior."""
        logp = -0.5 * ((np.log(R_GRADE) - np.log(R_PADRAO)) / R_PRIOR_SIGMA) ** 2
        for t in self._da(inst):
            dx, dy = self._geom(t)
            if dx <= 0:
                continue
            f = fator_balistico(dx, dy, t["angulo"])
            if not f:
                continue
            r_obs = t["forca"] ** 2 / f
            if t["acertou"]:
                dentro = (R_GRADE >= r_obs / (1 + TOL_ACERTO) ** 2) & (R_GRADE <= r_obs / (1 - TOL_ACERTO) ** 2)
                logp += np.log((1 - PESO_OUTLIER) * dentro + PESO_OUTLIER)
            else:
                dentro = (R_GRADE >= r_obs / (1 + TOL_ERRO) ** 2) & (R_GRADE <= r_obs / (1 - TOL_ERRO) ** 2)
                logp += np.log(np.where(dentro, PESO_ERRO, 1.0))
        p = np.exp(logp - logp.max())
        return R_GRADE, p / p.sum()

    def r_estimado(self, inst):
        """(R mediano, incerteza = razao q75/q25) da instancia."""
        g, p = self.posterior_r(inst)
        c = np.cumsum(p)
        q = lambda x: float(g[min(np.searchsorted(c, x), len(g) - 1)])
        return q(0.5), q(0.75) / q(0.25)

    def constante_r(self, inst):
        """(R mediano, confiavel?) - confiavel = o posterior esta estreito (varios acertos coerentes)."""
        r, incerteza = self.r_estimado(inst)
        return r, incerteza < INCERTEZA_CONFIAVEL

    def _escolher_angulo(self, inst, dx, dy, r):
        """Angulo e forca para o R dado. Prefere o angulo que o usuario costuma usar nessa instancia; senao 35."""
        hist = [t["angulo"] for t in self._da(inst) if t["acertou"]]
        base = float(np.median(hist)) if hist else 35.0
        melhor = None
        for d in (0, 8, -8, 16, -16, 24, -24):
            ang = float(np.clip(base + d, ANGULO_MIN, ANGULO_MAX))
            f = fator_balistico(dx, dy, ang)
            if not f:
                continue
            p = float(np.sqrt(r * f))
            if 18 <= p <= 85:                       # forca confortavel: nem fraca demais nem no limite da barra
                return ang, p
            if melhor is None or abs(p - 50) < abs(melhor[1] - 50):
                melhor = (ang, p)
        return melhor if melhor else (base, 50.0)

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
                dx_, dy_ = boss[0] - azul[0], azul[1] - boss[1]
                r, inc = self.r_estimado(inst)
                f_ = fator_balistico(dx_, dy_, ang) if dx_ > 0 else None
                if f_ and inc < INCERTEZA_CONFIAVEL:
                    # a constante da instancia ja e confiavel: usa o CENTRO da faixa (um acerto antigo pode ter sido
                    # marginal, na borda da tolerancia) mantendo o angulo que funcionou
                    return self._limites(ang, np.sqrt(r * f_), "memoria+fisica",
                                         f"{len(perto)} acerto(s) na mesma situacao; forca pelo centro de R={r:.0f} (x{inc:.1f})")
                # erro recente nesta mesma situacao com valores parecidos: tenta mais forte, e alterna
                for e in erros:
                    if dist(e) <= DIST_MESMA_SITUACAO and abs(e["forca"] - forca) < 6 and abs(e["angulo"] - ang) < 5:
                        forca += 8 if (len(erros) % 2) else -8
                return self._limites(ang, forca, "memoria", f"{len(perto)} acerto(s) na mesma situacao (dist {melhor:.1f})")
            dx, dy = boss[0] - azul[0], azul[1] - boss[1]
            if dx > 0:
                r, inc = self.r_estimado(inst)
                ang, p = self._escolher_angulo(inst, dx, dy, r)
                return self._limites(ang, p, "fisica", f"R={r:.0f} (incerteza x{inc:.1f}), dx={dx:.0f}, dy={dy:.0f}")
            t = ordem[0]
            return self._limites(t["angulo"], t["forca"], "vizinho", f"acerto mais parecido (dist {melhor:.1f})")
        if acertos:
            return self._limites(float(np.median([t["angulo"] for t in acertos])), float(np.median([t["forca"] for t in acertos])),
                                 "vizinho", "sem leitura do minimapa: mediana dos acertos")
        if azul and boss and boss[0] - azul[0] > 0:
            dx, dy = boss[0] - azul[0], azul[1] - boss[1]
            r, inc = self.r_estimado(inst)
            ang, p = self._escolher_angulo(inst, dx, dy, r)
            return self._limites(ang, p, "fisica", f"instancia nova: R={r:.0f} (incerteza x{inc:.1f}), "
                                 f"{len(erros)} erro(s) ja registrados; dx={dx:.0f}, dy={dy:.0f}")
        return self._limites(ANGULO_PADRAO, 50.0, "padrao", "sem dados nem minimapa")

    def forca_para(self, inst, azul, boss, angulo):
        """Forca pela fisica para um angulo dado (usa a constante R da instancia ou a padrao); None se nao der."""
        if not (azul and boss):
            return None
        r, _inc = self.r_estimado(inst)
        f = fator_balistico(boss[0] - azul[0], azul[1] - boss[1], angulo)
        if not f:
            return None
        return float(np.clip(np.sqrt(r * f), FORCA_MIN, FORCA_MAX))

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
