# -*- coding: utf-8 -*-
"""
Estrategias por instancia: o que o bot faz alem de "mirar no boss e atirar".

AVIAO (tecla F): o tiro leva o boneco junto ate onde ele cair (consome o turno; o bot nao gasta itens nele).
Usado no Escorpiao Rei: o boss nao morre num turno so e a "Investida do rei" empurra o boneco; quem nasce perto da
borda esquerda cai da arena e morre na hora. Paliativo ate termos forca para mata-lo no 1o turno: se o boneco esta
perto da borda e o boss ainda tem vida demais para morrer neste turno, voa para o meio da arena primeiro.

CHEFAO GLOBAL (Pericao, aba "Instancia do evento"): um boss com ~913 milhoes de vida que o servidor inteiro ataca; a
luta e individual, o dano e somado. A barra de vida do topo e a do SERVIDOR (cai com o dano de todos), entao o acerto do
seu tiro e conferido pelos NUMEROS DE DANO que sobem no boss. Gravacao do usuario 20261028_121648: o boneco nasce em
(10.5, 58.4) e o boss fica parado em (76.3, 61.4); 39 de 39 tiros normais com o ponteiro em 7 e forca 78-89% pegaram,
com vento de 4.5 contra ate 4.0 a favor (o vento quase nao importa aqui). O POW (especial, tecla B) foi usado sempre
que encheu: o especial tirou ~30 mil de uma vez (um tiro normal ~3 mil por bala).

Posicoes em pixels do MINIMAPA (o mesmo x que aparece no log: "voce (18, 61)").
"""

ESTRATEGIAS = {
    "ESCORPIAO_REI": {
        # chao da arena, da ponta esquerda a direita (medido na gravacao do bot 20261028_052531)
        "arena": (13.0, 93.0),
        # mais perto que isso de uma borda = perigo (nasceu em x=18 e x=23 e caiu nas duas)
        "aviao_se_perto_da_borda": 16.0,
        # para onde voar: fracao da arena (0.5 = meio)
        "aviao_destino": 0.5,
        # no maximo N voos por luta (se a Investida empurrar de volta, depois do voo ele ataca)
        "aviao_max_por_luta": 1,
        # boss com essa vida (%) ou menos: ataca em vez de voar (um turno com 2, 3, 4 tirou ~59%)
        "atacar_se_vida_ate": 55.0,
    },
    "PERICAO": {
        "chefe_global": True,         # vida do servidor; acerto pelos numeros de dano; vitoria = o chefao morreu para todos
        "angulo_min": 0.0,            # mira quase reta (o ponteiro le 7); nas outras o minimo e 15
        "tolerancia_angulo": 1.0,     # graus: o ponteiro comeca em 4.5 - a 2.5 do alvo, que a tolerancia normal (3) aceitaria
        "usar_pow": True,             # B quando o POW encher (antes dos itens; o tridente nao vale junto com o especial)
        "combo": "2,3,4",             # sempre 2, 3 e o maximo de 4 (depois 5, 6, 7, 8): dano maximo, sem testar combos
    },
}


def estrategia(inst):
    return ESTRATEGIAS.get(inst, {})
