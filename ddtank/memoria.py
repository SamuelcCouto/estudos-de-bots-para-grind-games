# -*- coding: utf-8 -*-
"""
Memoria de tiros e previsor de (angulo, forca).

Cada tiro e guardado como: instancia, posicao do jogador e do boss no minimapa, angulo, forca e se
acertou. Para um tiro novo, em ordem:
  1) "memoria": ha acertos na MESMA situacao (jogador e boss em posicoes quase iguais) -> repete;
  2) "fisica": forca^2 = R * F(dx, dy, angulo). R (a escala do minimapa daquela instancia) nao e conhecido de cara:
     o bot guarda uma distribuicao de R (cada acerto prende, cada erro descarta uma faixa) e escolhe o angulo e a
     forca com MAIOR CHANCE DE ACERTO somando todas as hipoteses de R - nao a media delas (com duas hipoteses
     separadas, a media cai no meio e erra as duas);
  3) "vizinho": o acerto mais parecido, mesmo que distante;
  4) "padrao": nada sabido da instancia.

F vem da balistica sem vento nem arrasto: v^2 = g*dx^2 / (2 cos^2(a) (dx tan(a) - dy)). Boss a esquerda: o boneco
vira e o tiro e o espelho (usa |dx|; o angulo e medido do chao do lado para onde ele olha).
Tiros gravados com o leitor antigo do minimapa ("leitura" < 2) sao ignorados: as posicoes estavam erradas.
"""
import json
import os

import numpy as np

import config
import estrategias

ARQ_SEMENTE = os.path.join(config.PASTA_RECURSOS, "dados", "tiros_semente.json")
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
VERSAO_LEITURA = 2              # versao do leitor do minimapa (leitura.candidatos_minimapa + RastreadorMinimapa)
FORCAS_GRADE = np.arange(FORCA_MIN, FORCA_MAX + 0.01, 0.5)
FORCA_CONFORTO = (18.0, 88.0)   # fora disso a barra e mais imprecisa (muito fraca) ou nao ha margem (quase cheia)
DX_MINIMO = 1.0                 # px de minimapa: mais perto que isso o boss esta "em cima" (sem direcao)
CHANCE_MEMORIA_OK = 0.6         # repetir um acerto antigo se a fisica der pelo menos essa chance para a mesma forca


GRUPOS = {"PERICAO": ("PERICAO", "PERICAO_COMUM"), "PERICAO_COMUM": ("PERICAO", "PERICAO_COMUM")}   # mesmo mapa


def angulo_min(inst):
    """Menor angulo que o bot mira na instancia (o Chefao Global e com a mira quase reta: ver estrategias.py)."""
    return estrategias.estrategia(inst).get("angulo_min", ANGULO_MIN)


def angulo_max(inst):
    """Maior angulo que o bot mira na instancia (Ultima Luta fase 2: o boss esta numa plataforma alta: ~71 graus)."""
    return estrategias.estrategia(inst).get("angulo_max", ANGULO_MAX)


def fator_balistico(dx, dy_up, ang):
    """F(dx, dy, angulo) em px de minimapa; None se o angulo nao alcanca o alvo."""
    t = np.radians(ang)
    den = 2 * np.cos(t) ** 2 * (dx * np.tan(t) - dy_up)
    return None if den <= 0 else dx * dx / den


class Memoria:
    def __init__(self, arq_semente=ARQ_SEMENTE, arq_aprendizado=ARQ_APRENDIZADO):
        self.arq_aprendizado = arq_aprendizado
        self.tiros = []
        self.ignorados = 0          # tiros com posicoes do leitor antigo do minimapa
        for arq in (arq_semente, arq_aprendizado):
            if arq and os.path.exists(arq):
                for t in json.load(open(arq, encoding="utf-8")).get("tiros", []):
                    if t.get("leitura", 1) >= VERSAO_LEITURA:
                        self.tiros.append(t)
                    else:
                        self.ignorados += 1
        self.novos = []

    # ---------- consulta ----------
    def _da(self, inst):
        grupo = GRUPOS.get(inst, (inst,))
        return [t for t in self.tiros if t["inst"] in grupo]

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
            dx = abs(dx)                      # boss a esquerda = tiro espelhado (o boneco vira)
            if dx < DX_MINIMO:
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

    def _chance_por_forca(self, inst, dx, dy, ang, post=None):
        """Para cada forca de FORCAS_GRADE: probabilidade de acertar (somando as hipoteses de R). None se o angulo
        nao alcanca o alvo."""
        f = fator_balistico(dx, dy, ang)
        if not f:
            return None
        g, p = post if post else self.posterior_r(inst)
        ideal = np.sqrt(g * f)                                   # forca ideal para cada hipotese de R
        dentro = np.abs(FORCAS_GRADE[:, None] - ideal[None, :]) <= TOL_ACERTO * ideal[None, :]
        return dentro.astype(float) @ p

    def melhor_tiro(self, inst, dx, dy, angulo=None):
        """(angulo, forca, chance de acerto) com a MAIOR chance de acertar pela fisica. Prefere o angulo que costuma
        acertar nessa instancia (ou 35) e forcas confortaveis; com `angulo`, so escolhe a forca."""
        post = self.posterior_r(inst)
        if angulo is not None:
            angs = [float(angulo)]
            base = float(angulo)
        else:
            hist = [t["angulo"] for t in self._da(inst) if t["acertou"]]
            base = float(np.median(hist)) if hist else 35.0
            angs = sorted({float(np.clip(base + d, angulo_min(inst), angulo_max(inst))) for d in (0, 8, -8, 16, -16, 24, -24)})
        melhor = None
        for ang in angs:
            ch = self._chance_por_forca(inst, dx, dy, ang, post)
            if ch is None:
                continue
            conforto = np.where((FORCAS_GRADE >= FORCA_CONFORTO[0]) & (FORCAS_GRADE <= FORCA_CONFORTO[1]), 0.0, 0.08)
            nota = ch - conforto - 0.002 * abs(ang - base)
            i = int(np.argmax(nota))
            # varias forcas com a mesma nota (plato): fica no meio do plato, nao na borda
            iguais = np.where(nota >= nota[i] - 1e-6)[0]
            i = int(iguais[len(iguais) // 2])
            if melhor is None or nota[i] > melhor[3]:
                melhor = (ang, float(FORCAS_GRADE[i]), float(ch[i]), float(nota[i]))
        return (melhor[0], melhor[1], melhor[2]) if melhor else None

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
                # media ponderada pelo DANO (vida que o tiro tirou): com o tridente (3 projeteis espalhados) o tiro em que os
                # 3 pegam tira mais vida - a forca puxa para ele. Tiros sem dano gravado (sementes) pesam igual.
                pesos = [(t.get("dano") or 10.0) ** 2 for t in perto]
                ang = float(np.average([t["angulo"] for t in perto], weights=pesos))
                forca = float(np.average([t["forca"] for t in perto], weights=pesos))
                dx_, dy_ = boss[0] - azul[0], azul[1] - boss[1]
                r, inc = self.r_estimado(inst)
                ch = self._chance_por_forca(inst, abs(dx_), dy_, ang) if abs(dx_) >= DX_MINIMO else None
                if ch is not None:
                    chance_mem = float(np.interp(forca, FORCAS_GRADE, ch))
                    if chance_mem >= CHANCE_MEMORIA_OK:
                        # a fisica concorda com o que ja acertou (inclui os erros registrados nessa faixa): repete
                        return self._limites(inst, ang, forca, "memoria", f"{len(perto)} acerto(s) na mesma situacao "
                                             f"(dist {melhor:.1f}); a fisica concorda (chance ~{chance_mem:.0%})")
                    mt = self.melhor_tiro(inst, abs(dx_), dy_, angulo=ang)
                    if mt and inc < INCERTEZA_CONFIAVEL and mt[2] > chance_mem:
                        # o acerto antigo foi marginal (borda da tolerancia) ou ja errou nessa forca: mantem o angulo que
                        # funcionou e usa a forca com mais chance pela constante da instancia, que ja e confiavel
                        return self._limites(inst, ang, mt[1], "memoria+fisica",
                                             f"{len(perto)} acerto(s) na mesma situacao, mas a forca {forca:.0f}% tem so "
                                             f"~{chance_mem:.0%} de chance; pela fisica (R~{r:.0f}, x{inc:.1f}) ~{mt[2]:.0%}")
                # erro recente nesta mesma situacao com valores parecidos: tenta mais forte, e alterna
                for e in erros:
                    if dist(e) <= DIST_MESMA_SITUACAO and abs(e["forca"] - forca) < 6 and abs(e["angulo"] - ang) < 5:
                        forca += 8 if (len(erros) % 2) else -8
                return self._limites(inst, ang, forca, "memoria", f"{len(perto)} acerto(s) na mesma situacao (dist {melhor:.1f})")
            dx, dy = boss[0] - azul[0], azul[1] - boss[1]
            if abs(dx) >= DX_MINIMO:
                return self._pela_fisica(inst, abs(dx), dy, f"{len(acertos)} acerto(s) e {len(erros)} erro(s) na instancia"
                                         + ("; boss a ESQUERDA" if dx < 0 else ""))
            t = ordem[0]
            return self._limites(inst, t["angulo"], t["forca"], "vizinho", f"boss em cima de voce (dx={dx:.0f}): "
                                 f"acerto mais parecido (dist {melhor:.1f})")
        if acertos:
            return self._limites(inst, float(np.median([t["angulo"] for t in acertos])), float(np.median([t["forca"] for t in acertos])),
                                 "vizinho", "sem leitura do minimapa: mediana dos acertos")
        if azul and boss and abs(boss[0] - azul[0]) >= DX_MINIMO:
            dx, dy = boss[0] - azul[0], azul[1] - boss[1]
            return self._pela_fisica(inst, abs(dx), dy, f"instancia nova, {len(erros)} erro(s) ja registrados"
                                     + ("; boss a ESQUERDA" if dx < 0 else ""))
        return self._limites(inst, ANGULO_PADRAO, 50.0, "padrao", "sem dados nem minimapa")

    def _pela_fisica(self, inst, dx, dy, contexto):
        r, inc = self.r_estimado(inst)
        mt = self.melhor_tiro(inst, dx, dy)
        if not mt:
            return self._limites(inst, ANGULO_PADRAO, 50.0, "padrao", f"nenhum angulo alcanca o alvo (dx={dx:.0f}, dy={dy:.0f})")
        ang, p, chance = mt
        return self._limites(inst, ang, p, "fisica", f"{contexto}; R~{r:.0f} (incerteza x{inc:.1f}), dx={dx:.0f}, dy={dy:.0f}, "
                                               f"chance de acerto ~{chance:.0%}")

    def forca_para(self, inst, azul, boss, angulo):
        """Forca com maior chance de acerto para um angulo dado; None se nao der."""
        if not (azul and boss) or abs(boss[0] - azul[0]) < DX_MINIMO:
            return None
        mt = self.melhor_tiro(inst, abs(boss[0] - azul[0]), azul[1] - boss[1], angulo=angulo)
        return float(np.clip(mt[1], FORCA_MIN, FORCA_MAX)) if mt else None

    @staticmethod
    def _limites(inst, ang, forca, origem, detalhe):
        return {"angulo": float(np.clip(ang, angulo_min(inst), angulo_max(inst))), "forca": float(np.clip(forca, FORCA_MIN, FORCA_MAX)),
                "origem": origem, "detalhe": detalhe}

    # ---------- aprendizado ----------
    def registrar(self, inst, azul, boss, angulo, forca, acertou, origem="bot", dano=None):
        if not (azul and boss):
            return
        t = {"inst": inst, "azul": [round(azul[0], 1), round(azul[1], 1)], "boss": [round(boss[0], 1), round(boss[1], 1)],
             "angulo": round(float(angulo), 1), "forca": round(float(forca)), "acertou": bool(acertou), "origem": origem,
             "leitura": VERSAO_LEITURA}
        if dano is not None:
            t["dano"] = round(float(dano), 1)          # % de vida do boss que o tiro tirou
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
