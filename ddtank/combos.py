# -*- coding: utf-8 -*-
"""
Escolha da combinacao de itens (ordem em que o atirador aperta 1..8) por instancia, para matar no MENOR numero de turnos.

Por que nao "economizar" itens quando ja mata no 1o turno: tirar um item poupa ~0,3 s, mas se o boss sobreviver o bot
perde um turno inteiro do boss (10-15 s). Entao:
  - instancia que ja morre no 1o turno com o combo atual -> mantem (nao mexe no que funciona);
  - instancia que NAO morre no 1o turno -> testa os outros combos (cada um pelo menos 2 vezes) e fica com o que tira
    MAIS vida no 1o ataque (medido pela barra de vida do boss). Se nenhum mata, o relatorio diz "PRECISA UPAR".
So contam 1os ataques que ACERTARAM com o boss de vida cheia (um erro nao diz nada sobre o dano do combo).
O que ele aprende fica em dados/combos.json.

Regras dos itens (do servidor): 1 = +2 ataques (-40%), 2 = tridente 3 balas (-50%), 3 = +1 ataque (-10%),
4..8 = +50/40/30/20/10% de dano. Item 1 e 3 ate 2x por turno, item 2 1x. O atirador aperta na ordem enquanto houver
stamina (icone colorido).
"""
import json
import os

import config

ARQ = os.path.join(config.PASTA, "dados", "combos.json")
COMBOS = {
    "A": [2, 3, 4, 4, 4, 4, 5, 6, 7, 8],   # padrao: tridente + ataque extra + potencializadores
    "B": [3, 3, 4, 4, 4, 4, 5, 6, 7, 8],   # dois ataques extras
    "C": [1, 4, 4, 4, 4, 5, 6, 7, 8],      # +2 ataques (-40%)
    "D": [2, 4, 4, 4, 4, 5, 6, 7, 8],      # tridente + potencializadores
}
PADRAO = "A"
AMOSTRAS_PARA_DECIDIR = 2
AMOSTRAS_MATA = 1            # 1 morte no 1o turno (com o boss cheio) ja basta para manter o combo; se depois falhar, a
                             # fracao de mortes cai abaixo de MATA_OK e ele volta a testar
MATA_OK = 0.8
JANELA = 10                  # ultimas N amostras de cada combo


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

    def _amostras(self, inst, c):
        return self.dados.get(inst, {}).get(c, [])[-JANELA:]

    def _mata(self, inst, c):
        a = self._amostras(inst, c)
        return len(a) >= AMOSTRAS_MATA and sum(d >= 99 for d in a) / len(a) >= MATA_OK

    def _media(self, inst, c):
        a = self._amostras(inst, c)
        return sum(a) / len(a) if a else None

    def escolher(self, inst):
        """(nome, ordem de itens, motivo)."""
        if self.fixo:
            return "personalizado", list(self.fixo), "ordem definida por voce (--itens)"
        if self._mata(inst, PADRAO):
            return PADRAO, list(COMBOS[PADRAO]), "mata no 1o turno: mantenho"
        for c in COMBOS:
            if self._mata(inst, c):
                return c, list(COMBOS[c]), "mata no 1o turno"
        for c in COMBOS:
            if len(self._amostras(inst, c)) < AMOSTRAS_PARA_DECIDIR:
                return c, list(COMBOS[c]), f"testando (nao mata no 1o turno com os combos ja vistos)"
        melhor = max(COMBOS, key=lambda c: self._media(inst, c) or 0)
        return melhor, list(COMBOS[melhor]), f"o que mais tira vida no 1o ataque (~{self._media(inst, melhor):.0f}%)"

    def registrar(self, inst, nome, dano):
        """dano = % de vida que o 1o ataque (boss cheio, acertando) tirou; 100 = matou."""
        if nome not in COMBOS:
            return
        self.dados.setdefault(inst, {}).setdefault(nome, []).append(round(min(100.0, float(dano)), 1))
        self.dados[inst][nome] = self.dados[inst][nome][-50:]
        if self.arq:
            try:
                os.makedirs(os.path.dirname(self.arq), exist_ok=True)
                json.dump(self.dados, open(self.arq, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
            except OSError:
                pass
