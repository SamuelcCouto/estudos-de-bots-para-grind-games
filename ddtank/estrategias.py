# -*- coding: utf-8 -*-
"""
Estrategias por instancia: o que o bot faz alem de "mirar no boss e atirar".

AVIAO (tecla F): o tiro leva o boneco junto ate onde ele cair (consome o turno; o bot nao gasta itens nele).
Usado no Escorpiao Rei: o boss nao morre num turno so e a "Investida do rei" empurra o boneco; quem nasce perto da
borda esquerda cai da arena e morre na hora. Paliativo ate termos forca para mata-lo no 1o turno: se o boneco esta
perto da borda e o boss ainda tem vida demais para morrer neste turno, voa para o meio da arena primeiro.

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
}


def estrategia(inst):
    return ESTRATEGIAS.get(inst, {})
