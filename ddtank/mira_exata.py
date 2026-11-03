# -*- coding: utf-8 -*-
"""
Planejador de tiro EXATO: estado da partida lido da rede (rede_vivo.py) + fisica do jogo (fisica_exata.py).

    mira = MiraExata()
    plano = mira.planejar(eu=(x, y), alvo=(x, y), vento=-1.3)      # px do MAPA (os da rede); direcao pelo lado do alvo
    -> dict(mira=angulo do mostrador, forca_pct, angulo_envio, direcao, folga_px, ...)
    ... depois do tiro:  mira.aprender(eu, direcao, mira_usada, tiro_do_cliente)   # ponto de saida e inclinacao EXATOS

O que nao vem da rede e como se resolve:
- ponto de saida do tiro (o cano): ~33 px acima do boneco e -37..+31 px para o lado (medido em 205 tiros reais, 02/11). Depois do 1o
  tiro de uma posicao, vale o ponto EXATO que o proprio pacote de tiro informou;
- inclinacao do boneco no terreno (entra no angulo enviado: LocalPlayer.calcBombAngle): desconhecida no 1o tiro (supoe 0 e escolhe um
  angulo perto de 45 graus, onde o alcance quase nao muda com o angulo); depois, exata pelo pacote (angulo enviado x mostrador);
- terreno: ainda nao (penaliza tiros rasantes, que batem em morro).
"""
import math

import fisica_exata as FX

OFFSET_PADRAO = (0.0, -33.0)       # ponto de saida - posicao do boneco (px do mapa), mediana de 205 tiros reais
ALVO_DY = -15.0                    # mira no corpo do inimigo (a posicao da rede e o pe)
MIRA_MIN, MIRA_MAX = 20, 80        # faixa do mostrador usada pelo planejador
LIMITE_RAIO_PX = 60.0              # o limite de mira medido vale ate esta distancia do lugar
SAIDA_MAX_PX = 70.0                # o cano fica a no maximo ~40 px do boneco: saida mais longe = posicao do boneco errada
MESMA_POSICAO_PX = 4.0             # o boneco nao saiu do lugar: o ponto de saida/inclinacao medidos continuam valendo


class MiraExata:
    def __init__(self, log=print):
        self.log = log
        self.medidas = {}          # direcao -> dict(pos=(x, y), offset=(dx, dy), inclinacao=graus)
        self.limites = []          # [(pos, subindo, mira)]: o mostrador nao passou disso AQUI (muda com o terreno: 49 e 42 graus, 02/11)

    def reiniciar(self):
        """Partida nova: os bonecos mudam de lugar (e o mapa)."""
        self.medidas = {}
        self.limites = []

    def _medida(self, eu, direcao):
        m = self.medidas.get(direcao)
        if m and abs(m["pos"][0] - eu[0]) <= MESMA_POSICAO_PX and abs(m["pos"][1] - eu[1]) <= MESMA_POSICAO_PX:
            return m
        return None

    def saida_e_inclinacao(self, eu, direcao):
        m = self._medida(eu, direcao)
        if m:
            return (eu[0] + m["offset"][0], eu[1] + m["offset"][1]), m["inclinacao"], True
        return (eu[0] + OFFSET_PADRAO[0], eu[1] + OFFSET_PADRAO[1]), 0.0, False

    def aprender(self, eu, direcao, mira_usada, tiro_cliente):
        """Depois de NOSSO tiro: o pacote FIRE do cliente tem o ponto de saida e o angulo EXATOS que o servidor usou."""
        if not (eu and tiro_cliente):
            return None
        ang = float(tiro_cliente["angulo"])
        inc = ang + mira_usada if direcao > 0 else ang - mira_usada + 180.0
        inc = (inc + 180.0) % 360.0 - 180.0
        if abs(inc) > 35:                                   # inclinacao absurda: o boneco estava virado para o outro lado ou o mostrador mentiu
            return None
        if abs(tiro_cliente["x"] - eu[0]) > SAIDA_MAX_PX or abs(tiro_cliente["y"] - eu[1]) > SAIDA_MAX_PX:
            return None                                     # o tiro saiu longe de onde achavamos estar (posicao velha): nao vale
        self.medidas[direcao] = dict(pos=tuple(eu), offset=(tiro_cliente["x"] - eu[0], tiro_cliente["y"] - eu[1]), inclinacao=inc)
        return self.medidas[direcao]

    def limite(self, subindo, mira, pos=None):
        """O mostrador nao passou de `mira` aqui (limite da arma no terreno): o planejador nao pede mais do que isso perto deste lugar
        (antes perdia ~6 s tentando)."""
        self.limites = (self.limites + [(tuple(pos) if pos else (0, 0), bool(subindo), float(mira))])[-20:]

    def prever(self, saida, angulo_envio, forca, vento, y_alvo):
        return FX.x_na_altura(saida[0], saida[1], forca, angulo_envio, y_alvo, vento)

    def forca_para(self, eu, alvo, vento, mira, direcao=None):
        """Forca (%) para uma mira ja definida (ex.: o mostrador parou 2 graus fora do pedido)."""
        direcao = direcao or (1 if alvo[0] >= eu[0] else -1)
        saida, inc, _ = self.saida_e_inclinacao(eu, direcao)
        f = FX.forca_para_alvo(saida[0], saida[1], alvo[0], alvo[1] + ALVO_DY, FX.angulo_envio(mira, direcao, inc), vento)
        return None if f is None else f / FX.FORCA_MAX * 100.0

    def planejar(self, eu, alvo, vento, direcao=None, faixa=(MIRA_MIN, MIRA_MAX)):
        """Melhor (mira do mostrador, forca %) para cair no alvo. Escolhe a mira mais TOLERANTE: a que menos muda o ponto de queda com
        1% de forca a mais/menos e 1 grau de mira (e 3 graus de inclinacao quando ela ainda e desconhecida)."""
        vento = float(vento or 0.0)
        direcao = direcao or (1 if alvo[0] >= eu[0] else -1)
        saida, inc, medido = self.saida_e_inclinacao(eu, direcao)
        perto = [(sub_, m) for pos, sub_, m in self.limites if abs(pos[0] - eu[0]) <= LIMITE_RAIO_PX and abs(pos[1] - eu[1]) <= LIMITE_RAIO_PX]
        maxs, mins = [m for s_, m in perto if s_], [m for s_, m in perto if not s_]
        faixa = (max([faixa[0]] + [int(math.ceil(m)) for m in mins]), min([faixa[1]] + [int(math.floor(m)) for m in maxs]))
        xa, ya = alvo[0], alvo[1] + ALVO_DY
        melhor = None
        for mira in range(int(faixa[0]), int(faixa[1]) + 1):
            ang = FX.angulo_envio(mira, direcao, inc)
            f = FX.forca_para_alvo(saida[0], saida[1], xa, ya, ang, vento)
            if f is None or not 4 * FX.FORCA_POR_QUADRO <= f <= FX.FORCA_MAX:
                continue
            x0 = self.prever(saida, ang, f, vento, ya)
            if x0 is None:
                continue
            desvios = []
            for df, da in ((FX.FORCA_POR_QUADRO, 0), (-FX.FORCA_POR_QUADRO, 0), (0, 1), (0, -1)) + (((0, 3), (0, -3)) if not medido else ()):
                xi = self.prever(saida, ang + da, f + df, vento, ya)
                desvios.append(abs(xi - x0) if xi is not None else 999.0)
            folga = max(desvios)
            nota = folga + 2.0 * max(0, 40 - mira) + abs(x0 - xa)        # rasante bate no terreno (ainda sem mapa de terreno)
            if melhor is None or nota < melhor["nota"]:
                melhor = dict(nota=nota, mira=mira, forca=f, forca_pct=f / FX.FORCA_MAX * 100.0, angulo_envio=ang, direcao=direcao,
                              folga_px=folga, queda_x=x0, saida=saida, inclinacao=inc, medido=medido, alvo=(xa, ya), vento=vento)
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
