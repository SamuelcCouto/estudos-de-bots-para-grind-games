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
    "FANTASMA": {"combo": "2,4,4"},
    "PROFUNDEZAS": {"combo": "2,4,4"},
    "MINHOCAO": {"combo": "2,4,4"},
    "DRAGAO_GELADO": {"combo": "2,4,4"},
    "RAINHA_LIRIS": {"combo": "2,4,4"},
    "ESCORPIAO_REI": {
        "combo": "2,4",  # tridente e todos os buffs disponiveis; sem itens 1 e 3
        # DESLIGADO a pedido do usuario (28/10): o boneco ja mata o Escorpiao no 1o turno. Para voltar: "aviao": True
        "aviao": False,
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
    "PERICAO_COMUM": {                # o Pericao FORA do horario: chefe comum (vida propria, sem numeros de dano)
        "angulo_min": 0.0, "tolerancia_angulo": 1.0, "pet_e": True, "usar_pow": True,
    },
    # ---- ROTA LESTE (gravacao 20261030_004606): A Ultima Luta (2 fases) e Devoradores ------------------------------------------------
    "ULTIMA_LUTA_F1": {               # fase 1: boss pequeno ("Boxeador", ao lado do boneco) que morre e renasce com 50%: 2 turnos
        "angulo_min": 0.0,            # mira baixa (12-20 graus, forca 15-20%); o boss pode nascer do outro lado (boneco vira)
        "combo": "2,3,4",
        "repor_perks": True,          # os perks Z/X/C sao comprados na sala ANTES desta fase (o usuario compra 3x); so se usam na fase 2
    },
    "ULTIMA_LUTA_F2": {               # fase 2: so o boss VERDE ("Juiz Ladrao") na plataforma (minimapa ~ (51, 27)); renasce com 50% e tem
                                      # armadura forte (muitos turnos). O boss pequeno da fase 1 volta para atrapalhar.
        "angulo_max": 80.0,           # boss numa plataforma alta: o usuario mirou 68-73.5 graus (o padrao e 70)
        "alvo": "mais_alto",          # o ponto vermelho de MENOR y e o boss da plataforma (o pequeno anda junto do boneco)
        "jogador_y_min": 50.0,        # o boneco fica no chao (y ~ 62): descarta cantos azuis da camera do minimapa
        "reposicionar": True,         # boss pequeno colado no boneco = tiro perdido: anda para a direita (o usuario fez 0.2-0.3 s)
        "angulo_min": 0.0,
        "combo": "1,4",               # o usuario NUNCA usou o 2 aqui: item 1 (+2 ataques) e os buffs 4; depois do B tambem o 1
        "perks": True, "repor_perks": True,
        "pet_e": True,                # (andar desfaz o buff: aperta E de novo no proximo turno)
        "usar_pow": True, "pow_exige_buff": True,
        "acerto_incerto": True,       # armadura: tiros com 0-1% de dano sao normais e nao viram "erro"
        "erro_apos_sem_queda": 3,     # 3 tiros seguidos sem tirar vida = a mira esta errada (nascimentos fora de x~13-17 repetiam 25x o mesmo tiro)
    },
    "DEVORADORES": {                  # dragao simples (Zen'Gor): 2 turnos. O boneco nasce colado na borda esquerda do minimapa (x ~ 0.7)
        "minimapa_x_min": 0.0,
        "combo": "2,3,4",
    },
    "GATO_PRETO": {                   # late game: tira o MAXIMO (perks Z/X/C, item E do pet, especial B). Gravacao 29/10.
        "angulo_min": 0.0,            # mira baixa (ponteiro em 4.5-12 na maioria dos nascimentos)
        "repor_perks": True,
        "perks": True,                # Z, X, C: perks POW (cada um enche +50% da barra do especial); repostos na SALA (navegador)
        "pet_e": True,                # E = item do pet, so liberado apos ~5 rodadas (rodada 6): o buff (canhao em volta do
                                      # boneco, mais dano, dura a luta toda) e confirmado pelo icone verde na barra de itens
        "usar_pow": True,             # B (especial: tirou ~27-34% da vida do boss de uma vez) ...
        "pow_exige_buff": True,       # ... sempre DEPOIS do buff do E ativo
        "combo": "2,3,4",             # item 2 (tridente) de volta a pedido do usuario; depois do B nao se aperta o 2
        "acerto_incerto": True,       # o boss se cura e a barra mal mexe com 1 tiro (41% -> 41% ate nos tiros do usuario): vida que
                                      # nao caiu NAO conta como erro (nao suja a memoria); so acertos (queda >= 2%) sao aprendidos
    },
    "PVP": {                            # Combate Livre (pvp.py): mira de 15 a 80 graus; E/F/itens sao do AtiradorPvp
        "angulo_min": 15.0, "angulo_max": 80.0,
    },
    "PERICAO": {
        "chefe_global": True,         # vida do servidor; acerto pelos numeros de dano; vitoria = o chefao morreu para todos
        "angulo_min": 0.0,            # mira quase reta (o ponteiro le 7); nas outras o minimo e 15
        "tolerancia_angulo": 1.0,     # graus: o ponteiro comeca em 4.5 - a 2.5 do alvo, que a tolerancia normal (3) aceitaria
        "pet_e": True,                # E quando o buff do pet estiver disponivel
        "usar_pow": True,             # B quando o POW encher (antes dos itens; o tridente nao vale junto com o especial)
        "combo": "2,3,4",             # sempre 2, 3 e o maximo de 4 (depois 5, 6, 7, 8): dano maximo, sem testar combos
    },
}


def estrategia(inst):
    return ESTRATEGIAS.get(inst, {})
