# -*- coding: utf-8 -*-
"""
Planejador de tiro EXATO: estado da partida lido da rede (rede_vivo.py) + fisica do jogo (fisica_exata.py) + terreno do mapa
(terreno_jogo.py).

    mira = MiraExata()
    plano = mira.planejar(eu=(x, y), alvo=(x, y), vento=-1.3, terreno=t)   # px do MAPA (os da rede); direcao pelo lado do alvo
    -> dict(mira=angulo do PONTEIRO do mostrador, forca_pct, angulo_envio, direcao, folga_px, acertos, ...)
    ... depois do tiro:  mira.aprender(eu, direcao, mira_usada, tiro_do_cliente)   # confere a saida e o ponteiro

Como o jogo faz (cliente descompilado + 300 tiros reais, 02/11):
- o PONTEIRO do mostrador (o que o bot le na tela) mostra o angulo REAL do tiro, ja com a inclinacao do boneco: angulo enviado =
  -ponteiro (olhando para a direita) ou ponteiro - 180 (esquerda). A inclinacao NAO entra no angulo;
- a inclinacao muda (1) o ponto de saida: pe + (0, -3) + gira(inclinacao, (+-30, -20)) e (2) a faixa que a arma alcanca:
  ponteiro = arma - direcao x inclinacao (num morro de 63 graus olhando para a esquerda, a arma de minimo 13 so chega a 76);
- a inclinacao vem do terreno (terreno_jogo.Terreno.inclinacao, a mesma conta do jogo). Sem terreno: supoe 0 e, depois do 1o tiro de
  um lugar, usa o ponto de saida EXATO que o pacote do tiro informou;
- com o terreno, cada tiro candidato e simulado ate o fim: so vale se a bala chega no corpo do inimigo antes de bater no chao (e as
  variacoes de 1 quadro de forca e 1 grau tambem, quando possivel).
"""
import math

import fisica_exata as FX
import terreno_jogo as TJ

ALVO_DY = -15.0                    # mira no corpo do inimigo (a posicao da rede e o pe)
CORPO = (-15, -35, 15, 0)          # caixa de colisao do boneco em volta do pe (padrao dos servidores de DDTank)
MIRA_MIN, MIRA_MAX = 20, 80        # faixa do ponteiro usada pelo planejador
LIMITE_RAIO_PX = 60.0              # o limite de mira medido vale ate esta distancia do lugar (sem terreno)
SAIDA_MAX_PX = 70.0                # o cano fica a no maximo ~40 px do boneco: saida mais longe = posicao do boneco errada
MESMA_POSICAO_PX = 4.0             # o boneco nao saiu do lugar: o ponto de saida medido continua valendo
CORRECAO_MAX = 6.0                 # diferenca ponteiro x angulo enviado aceitavel (mais que isso = leitura/lado errados)
FAIXA_AMPLA = (8, 88)              # quando nada na faixa normal passa pelo terreno
CANDIDATOS_TERRENO = 16            # quantas miras (as mais tolerantes) sao simuladas com o terreno


class MiraExata:
    def __init__(self, log=print):
        self.log = log
        self.medidas = {}          # direcao -> dict(pos=(x, y), offset=(dx, dy), correcao=graus): o que o pacote do NOSSO tiro mostrou
        self.limites = []          # [(pos, subindo, mira)]: o ponteiro nao passou disso AQUI (sem terreno para saber a inclinacao)
        self.arma = [None, None]   # faixa da ARMA (graus, sem inclinacao), aprendida nos limites com a inclinacao conhecida

    def reiniciar(self):
        """Partida nova: os bonecos mudam de lugar (e o mapa). A faixa da arma continua."""
        self.medidas = {}
        self.limites = []

    def _medida(self, eu, direcao):
        m = self.medidas.get(direcao)
        if m and abs(m["pos"][0] - eu[0]) <= MESMA_POSICAO_PX and abs(m["pos"][1] - eu[1]) <= MESMA_POSICAO_PX:
            return m
        return None

    def contexto(self, eu, direcao, terreno=None):
        """(saida, inclinacao, correcao do ponteiro, origem). origem: 'terreno' (exato), 'medida' (pacote do tiro anterior daqui) ou
        'estimada'. inclinacao None = desconhecida."""
        m = self._medida(eu, direcao)
        corr = m["correcao"] if m else 0.0
        if terreno is not None and terreno.no_chao(eu[0], eu[1]):
            inc = terreno.inclinacao(eu[0], eu[1])
            return TJ.saida_do_tiro(eu, direcao, inc), inc, corr, "terreno"
        if m:
            return (eu[0] + m["offset"][0], eu[1] + m["offset"][1]), None, corr, "medida"
        return TJ.saida_do_tiro(eu, direcao, 0.0), None, 0.0, "estimada"

    def saida_e_inclinacao(self, eu, direcao, terreno=None):
        saida, inc, _corr, origem = self.contexto(eu, direcao, terreno)
        return saida, inc, origem != "estimada"

    def aprender(self, eu, direcao, mira_usada, tiro_cliente):
        """Depois de NOSSO tiro: o pacote FIRE do cliente tem o ponto de saida e o angulo EXATOS. Guarda a saida (para o proximo tiro
        daqui, quando nao ha terreno) e a correcao do ponteiro (angulo enviado x ponteiro lido; normalmente 0-2 graus)."""
        if not (eu and tiro_cliente):
            return None
        ang = float(tiro_cliente["angulo"])
        corr = ang + mira_usada if direcao > 0 else ang - mira_usada + 180.0
        corr = (corr + 180.0) % 360.0 - 180.0
        if abs(corr) > CORRECAO_MAX:                         # o boneco estava virado para o outro lado ou o ponteiro foi mal lido
            return None
        if abs(tiro_cliente["x"] - eu[0]) > SAIDA_MAX_PX or abs(tiro_cliente["y"] - eu[1]) > SAIDA_MAX_PX:
            return None                                     # o tiro saiu longe de onde achavamos estar (posicao velha): nao vale
        self.medidas[direcao] = dict(pos=tuple(eu), offset=(tiro_cliente["x"] - eu[0], tiro_cliente["y"] - eu[1]), correcao=corr,
                                     inclinacao=corr)
        return self.medidas[direcao]

    def limite(self, subindo, mira, pos=None, direcao=None, inclinacao=None):
        """O ponteiro nao passou de `mira` aqui. Com a inclinacao conhecida, vira a faixa da ARMA (vale em qualquer lugar):
        arma = ponteiro + direcao x inclinacao. Sem ela, guarda so para este lugar."""
        self.limites = (self.limites + [(tuple(pos) if pos else (0, 0), bool(subindo), float(mira))])[-20:]
        if direcao and inclinacao is not None:
            arma = float(mira) + direcao * inclinacao
            i = 1 if subindo else 0
            self.arma[i] = arma
            return arma
        return None

    def faixa(self, eu, direcao, inclinacao, faixa=(MIRA_MIN, MIRA_MAX)):
        """Faixa do ponteiro que da para usar aqui: a da arma deslocada pela inclinacao e/ou os limites medidos neste lugar."""
        lo, hi = faixa
        if inclinacao is not None:
            if self.arma[0] is not None:
                lo = max(lo, int(math.ceil(self.arma[0] - direcao * inclinacao)))
            if self.arma[1] is not None:
                hi = min(hi, int(math.floor(self.arma[1] - direcao * inclinacao)))
        perto = [(sub_, m) for pos, sub_, m in self.limites if abs(pos[0] - eu[0]) <= LIMITE_RAIO_PX and abs(pos[1] - eu[1]) <= LIMITE_RAIO_PX]
        lo = max([lo] + [int(math.ceil(m)) for s_, m in perto if not s_])
        hi = min([hi] + [int(math.floor(m)) for s_, m in perto if s_])
        return lo, hi

    def prever(self, saida, angulo_envio, forca, vento, y_alvo, mapa=FX.MAPA_PADRAO):
        return FX.x_na_altura(saida[0], saida[1], forca, angulo_envio, y_alvo, vento, mapa=mapa)

    def forca_para(self, eu, alvo, vento, mira, direcao=None, terreno=None):
        """Forca (%) para uma mira ja definida (ex.: o ponteiro parou 2 graus fora do pedido)."""
        direcao = direcao or (1 if alvo[0] >= eu[0] else -1)
        saida, _inc, corr, _o = self.contexto(eu, direcao, terreno)
        mapa = FX.MapaFisico(*terreno.fisica()) if terreno is not None else FX.MAPA_PADRAO
        f = FX.forca_para_alvo(saida[0], saida[1], alvo[0], alvo[1] + ALVO_DY, FX.angulo_envio(mira, direcao, corr), vento, mapa=mapa)
        return None if f is None else f / FX.FORCA_MAX * 100.0

    def _simula(self, saida, ang, f, vento, terreno, caixa, mapa):
        return FX.simular(saida[0], saida[1], f, ang, vento, mapa=mapa, terreno=terreno, alvos=[caixa], largura=terreno.largura,
                          altura=terreno.altura + 200, limite_s=15.0)

    def planejar(self, eu, alvo, vento, direcao=None, faixa=(MIRA_MIN, MIRA_MAX), terreno=None):
        """Melhor (ponteiro, forca %) para cair no alvo. Escolhe a mira mais TOLERANTE (a que menos muda o ponto de queda com 1 quadro
        de forca e 1 grau) entre as que, com o terreno, chegam no corpo do inimigo sem bater no chao antes."""
        vento = float(vento or 0.0)
        direcao = direcao or (1 if alvo[0] >= eu[0] else -1)
        saida, inc, corr, origem = self.contexto(eu, direcao, terreno)
        lo, hi = self.faixa(eu, direcao, inc, faixa)
        mapa = FX.MapaFisico(*terreno.fisica()) if terreno is not None else FX.MAPA_PADRAO
        xa, ya = alvo[0], alvo[1] + ALVO_DY
        candidatos = []
        for mira in range(int(lo), int(hi) + 1):
            ang = FX.angulo_envio(mira, direcao, corr)
            f = FX.forca_para_alvo(saida[0], saida[1], xa, ya, ang, vento, mapa=mapa)
            if f is None or not 4 * FX.FORCA_POR_QUADRO <= f <= FX.FORCA_MAX:
                continue
            x0 = self.prever(saida, ang, f, vento, ya, mapa)
            if x0 is None:
                continue
            desvios = []
            for df, da in ((FX.FORCA_POR_QUADRO, 0), (-FX.FORCA_POR_QUADRO, 0), (0, 1), (0, -1)):
                xi = self.prever(saida, ang + da, f + df, vento, ya, mapa)
                desvios.append(abs(xi - x0) if xi is not None else 999.0)
            folga = max(desvios)
            rasante = 2.0 * max(0, 40 - mira) if terreno is None else 0.5 * max(0, 30 - mira)   # sem terreno: rasante bate em morro
            candidatos.append(dict(nota=folga + rasante + abs(x0 - xa), mira=mira, forca=f, forca_pct=f / FX.FORCA_MAX * 100.0,
                                   angulo_envio=ang, direcao=direcao, folga_px=folga, queda_x=x0, saida=saida, inclinacao=inc,
                                   correcao=corr, origem=origem, medido=origem != "estimada", alvo=(xa, ya), vento=vento,
                                   acertos=None, faixa=(lo, hi)))
        if not candidatos:
            return None
        candidatos.sort(key=lambda c: c["nota"])
        if terreno is None:
            return candidatos[0]
        caixa = (alvo[0] + CORPO[0], alvo[1] + CORPO[1], alvo[0] + CORPO[2], alvo[1] + CORPO[3])
        melhor = None
        for c in candidatos[:CANDIDATOS_TERRENO if faixa == (MIRA_MIN, MIRA_MAX) else len(candidatos)]:
            r = self._simula(saida, c["angulo_envio"], c["forca"], vento, terreno, caixa, mapa)
            c["impacto"], c["motivo"] = r["impacto"], r["motivo"]
            if r["motivo"] != "alvo":
                continue
            acertos = 1 + sum(self._simula(saida, c["angulo_envio"] + da, c["forca"] + df, vento, terreno, caixa, mapa)["motivo"] == "alvo"
                              for df, da in ((FX.FORCA_POR_QUADRO, 0), (-FX.FORCA_POR_QUADRO, 0), (0, 1), (0, -1)))
            c["acertos"] = acertos
            if melhor is None or (acertos, -c["nota"]) > (melhor["acertos"], -melhor["nota"]):
                melhor = c
            if acertos == 5 and c["nota"] <= candidatos[0]["nota"] + 5:
                break
        if melhor is None:
            if faixa == (MIRA_MIN, MIRA_MAX):                # tudo bloqueado: tenta rasante e quase vertical (por cima/por baixo)
                c = self.planejar(eu, alvo, vento, direcao, FAIXA_AMPLA, terreno)
                if c and not c.get("bloqueado"):
                    return c
            return dict(candidatos[0], bloqueado=True)
        return melhor


def resultado_do_tiro(tiro_servidor, alvo_id):
    """Do resultado do servidor: onde explodiu (1o projetil) e se O PROJETIL acertou o alvo. O dano do projetil vem nos eventos da
    propria bomba (KILL_PLAYER: alvo, dano, ...); a lista "alvos" do pacote e o ataque do PET (02/11: o usuario viu o pet dar o dano
    que o leitor tinha contado como acerto do tiro)."""
    bombas = tiro_servidor.get("bombas") or []
    b = bombas[0] if bombas else None
    bomba = next((a for a in b["acoes"] if a["tipo"] == "BOMB"), None) if b else None
    dano = sum(a["p"][1] for bb in bombas for a in bb["acoes"] if a["tipo"] == "KILL_PLAYER" and a["p"][0] == alvo_id)
    dano_pet = sum(a["dano"] for a in tiro_servidor.get("alvos", []) if a["vivo"] == alvo_id)
    return dict(explodiu=bomba["p"][:2] if bomba else None, dano=dano, acertou=dano > 0, dano_pet=dano_pet,
                teleguiado=bool(b and any(a["tipo"] == "CHANGE_SPEED" for a in b["acoes"])))
