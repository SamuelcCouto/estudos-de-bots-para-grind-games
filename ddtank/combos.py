# -*- coding: utf-8 -*-
"""
Escolha da combinacao de itens (ordem em que o atirador aperta 1..8) por instancia, para a LUTA MAIS CURTA.

O que conta e o TEMPO da luta (do inicio da batalha ate a vitoria), medido pelo bot:
  - matar no 1o turno e o que mais economiza (cada turno do boss sao 10-15 s);
  - entre combos que matam no 1o turno, o que tem MENOS ANIMACAO ganha: o item 3 (+1 ataque) e o 1 (+2 ataques)
    fazem o boneco atirar de novo (mais uma animacao); o 2 (tridente) sao 3 balas num tiro so; 4..8 so aumentam o dano.
    Ex.: se o Fantasma morre com 2,4,4,4, tirar o 3 poupa a animacao do 2o tiro.
TESTE DE FOGO = 2,3,4,4 (+ os buffs que a stamina der): 5 lutas primeiro. Se nem ele mata no 1o turno (com os tiros
acertando), a instancia precisa de UPGRADE (o relatorio avisa) - e mesmo assim o bot procura o combo de luta mais curta:
no Escorpiao (so o pe tem colisao) o 3,4 tirou 58-85% no 1o ataque contra ~58% do 2,3,4 (o tridente espalha as balas).
CRITICO: um tiro pode critar e matar "por sorte". Por isso nenhuma conclusao sai de poucas lutas: a escolha usa a media
do tempo com uma margem de duvida (que so diminui depois de muitas lutas), e um combo que matou uma vez por sorte volta a
ser testado ate a media mostrar o que ele realmente faz.
O que ele aprende fica em dados/combos.json (uma entrada por luta vencida: tempo, matou no 1o turno, dano do 1o ataque).

Regras dos itens (servidor): 1 = +2 ataques (-40%), 2 = tridente 3 balas (-50%), 3 = +1 ataque (-10%),
4..8 = +50/40/30/20/10% de dano. Item 1 e 3 ate 2x por turno, item 2 1x. O atirador aperta na ordem enquanto houver
stamina (icone colorido).
"""
import json
import math
import os

import config

ARQ = os.path.join(config.PASTA, "dados", "combos.json")
BUFFS = [4, 4, 4, 4, 5, 6, 7, 8]
# nome -> ordem de itens. Os buffs do fim entram enquanto a stamina der.
COMBOS = {
    "2,3,4": [2, 3] + BUFFS,     # TESTE DE FOGO: tridente + 1 ataque extra (2 animacoes de tiro)
    "2,4": [2] + BUFFS,          # tridente, 1 animacao so
    "4": list(BUFFS),            # so buffs: 1 bala, 1 animacao
    "3,4": [3] + BUFFS,          # 2 tiros simples
    "1,4": [1] + BUFFS,          # 3 tiros (-40%)
    "3,3,4": [3, 3] + BUFFS,     # 3 tiros (-10%)
}
TESTE_DE_FOGO = "2,3,4"
# depois do teste de fogo, testa primeiro os de MENOS animacao
ORDEM_TESTE = ["2,4", "4", "3,4", "1,4", "3,3,4"]
MIN_AMOSTRAS = 3             # lutas de cada combo antes de comparar
FOGO_PARA_CONCLUIR = 5       # lutas do teste de fogo para concluir "nem ele mata no 1o turno"
FOGO_MATA_MIN = 0.2          # teste de fogo matando no 1o turno em menos que isso (com >= 5 lutas) = precisa upar
FOGO_PARA_EXPLORAR = 0.5     # so testa combos com menos animacao se o fogo mata no 1o turno pelo menos nisso (abaixo
                             # disso as mortes podem ser critico: continua no dano maximo e medindo)
Z_DUVIDA = 1.0               # margem de duvida (desvios-padrao da media) - otimista: testa mais o que ainda e incerto
DESCARTE_SEM_MATAR = 6       # combo que nunca matou no 1o turno em N lutas, enquanto o fogo mata: sai da lista
JANELA = 40                  # ultimas N lutas de cada combo


class Combos:
    def __init__(self, arq=ARQ, fixo=None):
        """fixo: ordem de itens definida pelo usuario (--itens): sem testes."""
        self.arq, self.fixo = arq, fixo
        self.dados = {}
        if arq and os.path.exists(arq):
            try:
                self.dados = json.load(open(arq, encoding="utf-8"))
            except (OSError, ValueError):
                self.dados = {}
        # formato antigo (lista de danos por combo A/B/C/D): descarta
        for inst in list(self.dados):
            if not isinstance(self.dados[inst], dict) or any(not isinstance(v, list) or (v and not isinstance(v[0], dict))
                                                             for v in self.dados[inst].values()):
                del self.dados[inst]

    # ---------------------------------------------------------------- estatisticas
    def lutas(self, inst, c):
        return [x for x in self.dados.get(inst, {}).get(c, []) if x.get("venceu", True)][-JANELA:]

    def resumo(self, inst, c):
        """(n, tempo medio, desvio, fracao que matou no 1o turno, dano medio do 1o ataque)."""
        ls = self.lutas(inst, c)
        if not ls:
            return 0, None, None, None, None
        ts = [x["t"] for x in ls]
        m = sum(ts) / len(ts)
        dp = math.sqrt(sum((t - m) ** 2 for t in ts) / (len(ts) - 1)) if len(ts) > 1 else m
        mata = sum(bool(x.get("mata1")) for x in ls) / len(ls)
        danos = [x["dano1"] for x in ls if x.get("dano1") is not None]
        return len(ls), m, dp, mata, (sum(danos) / len(danos) if danos else None)

    def precisa_upar(self, inst):
        n, _m, _dp, mata, _d = self.resumo(inst, TESTE_DE_FOGO)
        return n >= FOGO_PARA_CONCLUIR and mata < FOGO_MATA_MIN

    # ---------------------------------------------------------------- escolha
    def escolher(self, inst):
        """(nome, ordem de itens, motivo)."""
        if self.fixo:
            return "personalizado", list(self.fixo), "ordem definida por voce (--itens)"
        nf, mf, _dpf, mataf, danof = self.resumo(inst, TESTE_DE_FOGO)
        if nf < FOGO_PARA_CONCLUIR:
            return TESTE_DE_FOGO, list(COMBOS[TESTE_DE_FOGO]), f"teste de fogo (dano maximo), luta {nf + 1}/{FOGO_PARA_CONCLUIR}"
        precisa = self.precisa_upar(inst)
        aviso = (f"PRECISA UPAR (nem o teste de fogo mata no 1o turno: {mataf:.0%} de {nf} lutas, 1o ataque "
                 f"~{danof or 0:.0f}%); enquanto isso, ") if precisa else ""
        if not precisa and mataf < FOGO_PARA_EXPLORAR:
            return TESTE_DE_FOGO, list(COMBOS[TESTE_DE_FOGO]), (
                f"o teste de fogo mata no 1o turno so em {mataf:.0%} de {nf} lutas (critico?): dano maximo e continuo medindo")
        for c in ORDEM_TESTE:
            n = self.resumo(inst, c)[0]
            if n < MIN_AMOSTRAS and not self._descartado(inst, c, mataf):
                return c, list(COMBOS[c]), (aviso + (f"testando outro combo (o boss morre em mais turnos: o que tira mais "
                                            f"vida pode encurtar a luta)" if precisa else "testando um combo com menos animacao")
                                            + f", luta {n + 1}/{MIN_AMOSTRAS}")
        notas = {}
        for c in COMBOS:
            n, m, dp, mata, _d = self.resumo(inst, c)
            if n == 0 or self._descartado(inst, c, mataf):
                continue
            notas[c] = m - Z_DUVIDA * dp / math.sqrt(n)        # otimista: incerteza grande -> testa mais
        melhor = min(notas, key=notas.get)
        n, m, _dp, mata, _d = self.resumo(inst, melhor)
        return melhor, list(COMBOS[melhor]), aviso + f"luta mais curta: {m:.0f}s em media em {n} lutas (mata no 1o turno {mata:.0%})"

    def _descartado(self, inst, c, mata_fogo):
        if c == TESTE_DE_FOGO:
            return False
        n, _m, _dp, mata, _d = self.resumo(inst, c)
        return n >= DESCARTE_SEM_MATAR and mata == 0 and (mata_fogo or 0) >= 0.5

    # ---------------------------------------------------------------- registro
    def registrar_luta(self, inst, nome, duracao, mata1, dano1=None, venceu=True):
        """Uma luta terminada com o combo `nome`: duracao (s), matou no 1o ataque?, dano do 1o ataque (%)."""
        if nome not in COMBOS or duracao is None:
            return
        reg = {"t": round(float(duracao), 1), "mata1": bool(mata1), "venceu": bool(venceu)}
        if dano1 is not None:
            reg["dano1"] = round(min(100.0, float(dano1)), 1)
        self.dados.setdefault(inst, {}).setdefault(nome, []).append(reg)
        self.dados[inst][nome] = self.dados[inst][nome][-200:]
        if self.arq:
            try:
                os.makedirs(os.path.dirname(self.arq), exist_ok=True)
                json.dump(self.dados, open(self.arq, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
            except OSError:
                pass

    def texto(self):
        """Tabela para o relatorio."""
        linhas = []
        for inst, cs in self.dados.items():
            for c in COMBOS:
                n, m, _dp, mata, dano = self.resumo(inst, c)
                if n:
                    linhas.append(f"  {inst:16s} combo {c:6s}: {n:3d} lutas, luta media {m:5.1f}s, mata no 1o turno "
                                  f"{mata:4.0%}" + (f", 1o ataque ~{dano:.0f}%" if dano is not None else "")
                                  + ("   <- PRECISA UPAR (teste de fogo)" if c == TESTE_DE_FOGO and self.precisa_upar(inst) else ""))
        return linhas
