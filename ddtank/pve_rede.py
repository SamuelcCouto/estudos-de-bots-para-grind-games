# -*- coding: utf-8 -*-
"""
Mira EXATA para as instancias (PVE), a partir da rede (rede_vivo.py) + fisica (fisica_exata.py) + terreno (terreno_jogo.py).

Por que (06/11, Ultima Luta fase 2, lido na rede):
- o boss e sempre o mesmo e fica parado em (769, 320); de x~185 todo tiro acerta quando a forca esta certa, mas a janela de forca
  que acerta e pequena (~ +-3%) e a leitura da barra oscila mais que isso -> escolhemos o angulo cuja JANELA DE FORCA e a maior e
  mandamos a forca para o MEIO da janela;
- o elite ("Boxeador", id novo a cada nascimento, anda atras do boneco) bloqueia a bala: com ele a <= ~25 px em x do boneco a bala
  explode em cima de nos (4 tiros seguidos perdidos e o boneco ferido); a >= ~100 px passa. A rede mostra a posicao dele
  (ADD_LIVING + LIVING_MOVETO), entao o bot anda ate um ponto livre ANTES de atirar e a simulacao conta o elite como obstaculo.

Tudo em pixels do MAPA (os mesmos da rede), nao em unidades do minimapa.
"""
import fisica_exata as FX
import mira_exata
import terreno_jogo

CAIXA_BOSS = (-84, -120, 81, 15)        # em volta da posicao do boss da rede (769, 320): explosoes de (689..840, 204..317) acertaram
CAIXA_ELITE = (-35, -50, 35, 5)         # em volta do pe do elite
ELITE_GATILHO_PX = 110.0                # o elite anda ~100 px por vez dele: a menos disso ele estara em cima de nos na proxima; desvia ja
ELITE_FOLGA_PX = 150.0                  # ... para um ponto a essa distancia dele (antes 100: ele alcancava na vez seguinte)
ELITE_BLOQUEIA_PX = 80.0                # elite mais perto que isso (em x) do boneco = tiro perdido (medido: bloqueou a 12-21, passou a >= 107)
ELITE_ALTURA_MIN = 600                  # so conta como elite o que esta no chao (y grande); o boss fica na plataforma
JANELA_FORCA = 12                       # varre a forca de f0-12% a f0+12% (passo 1%) para achar a janela que acerta
MIN_JANELA = 3                          # janela menor que 3 pontos de forca = tiro arriscado demais (ainda assim e usado se for o melhor)
X_MAX_TIRO = 460.0                      # de x~516 quase nenhum angulo chega no centro do boss (so de raspao, 2-9% por tiro): fica ate ~460
X_MIN_TIRO = 150.0                      # parede da esquerda
FAIXA_DIREITA = (1090.0, 1450.0)        # lado direito (virado para a esquerda): so ha mira de x>=1080 (offline 06/11: x=1000-1040 nao tem; o bot ficou em 1062 e perdeu a vez)


def _caixa(pos, c):
    return (pos[0] + c[0], pos[1] + c[1], pos[0] + c[2], pos[1] + c[3])


class MiraPve:
    def __init__(self, rede, log=print):
        self.rede = rede
        self.log = log
        self.mira = mira_exata.MiraExata(log=log)
        self.boss_y = None          # y real do boss: a rede da y=297 ate o 1o START_MOVE e depois 320 (o bicho cai); a caixa de acerto usa o real
        self._ter = None            # (mapa, n buracos, terreno)
        self._plano = None          # (chave, plano): o mesmo plano pedido duas vezes no turno nao e simulado de novo
        self._partida = None

    # ----------------------------------------------------------------------------------------------------------- estado
    def info(self):
        """O que a rede sabe agora: dict(eu=(x, y), eu_id, boss=(x, y), elites=[(x, y)], vento, mapa, buracos, est) ou None."""
        if not self.rede:
            return None
        est = self.rede.estado.copia()
        vivos = est.get("vivos") or {}
        eu_id = est.get("eu")
        if eu_id not in vivos and len(vivos) == 1:
            eu_id = next(iter(vivos))
        eu = vivos.get(eu_id)
        mons = [m for m in (est.get("monstros") or {}).values() if m.get("vivo", True)]
        if not (eu and mons and est.get("mapa") is not None):
            return None
        boss = max(mons, key=lambda m: m["vida_max"])
        elites = [(m["x"], m["y"]) for m in mons if m is not boss and m["vida_max"] < boss["vida_max"] / 2 and m["y"] >= ELITE_ALTURA_MIN]
        by = max(boss["y"], self.boss_y or 0)
        return dict(eu=(eu["x"], eu["y"]), eu_id=eu_id, boss=(boss["x"], by), direcao=1 if boss["x"] >= eu["x"] else -1, boss_vida=boss.get("vida"), elites=elites,
                    vento=float(est.get("vento") or 0.0), mapa=est["mapa"], buracos=est.get("buracos") or [], est=est)

    def terreno(self, info):
        chave = (info["mapa"], len(info["buracos"]))
        if self._ter and self._ter[0] == chave:
            return self._ter[1]
        try:
            t = terreno_jogo.terreno_da_partida(info["mapa"], info["buracos"])
        except (OSError, ValueError) as e:
            self.log(f"   [rede] nao consegui o terreno do mapa {info['mapa']}: {e}")
            t = None
        self._ter = (chave, t)
        return t

    def nova_partida(self, info):
        if info["mapa"] != self._partida:
            self.mira.reiniciar()
            self._partida = info["mapa"]

    # ----------------------------------------------------------------------------------------------------------- elite
    def elite_perto(self, info, x=None, raio=ELITE_BLOQUEIA_PX):
        """Elite mais proximo (em x) de `x` (padrao: o boneco) se estiver dentro de `raio` (padrao: o que bloqueia a bala); senao None."""
        x = info["eu"][0] if x is None else x
        perto = [e for e in info["elites"] if abs(e[0] - x) < raio]
        return min(perto, key=lambda e: abs(e[0] - x)) if perto else None

    def ponto_livre(self, info):
        """x para onde andar quando o elite esta em cima do boneco (None = nao precisa andar ou nao ha onde): ELITE_BLOQUEIA_PX+20 para
        o lado do elite que fica DENTRO da faixa boa de tiro (X_MIN_TIRO..X_MAX_TIRO), o mais perto do boneco."""
        el = self.elite_perto(info, raio=ELITE_GATILHO_PX)
        if el is None:
            return None
        lo, hi = (X_MIN_TIRO, X_MAX_TIRO) if info.get("direcao", 1) > 0 else FAIXA_DIREITA
        opcoes = []
        for folga in (ELITE_FOLGA_PX, ELITE_BLOQUEIA_PX + 20):          # primeiro a folga grande; so se nao couber na faixa, a minima
            opcoes = [x for x in (el[0] - folga, el[0] + folga) if lo <= x <= hi]
            if opcoes:
                break
        if not opcoes:
            return None
        return min(opcoes, key=lambda x: abs(x - info["eu"][0]))

    # ----------------------------------------------------------------------------------------------------------- plano
    def planejar(self, info, angulo_base, tolerancia_graus=3, direcao=None):
        """Melhor (ponteiro, forca %) de onde o boneco esta: entre os ponteiros angulo_base +- tolerancia (mexer pouco no ponteiro: cada
        grau custa tempo da vez), o de MAIOR janela de forca que acerta o boss (com o chao e o elite no caminho). A forca vai para o
        meio da janela. None = nenhum jeito de acertar (mira pela memoria)."""
        eu, boss = info["eu"], info["boss"]
        direcao = direcao or info.get("direcao", 1)
        chave = (tuple(eu), tuple(boss), info["vento"], direcao, round(angulo_base), tolerancia_graus, len(info["buracos"]),
                 tuple(sorted(info["elites"])), tuple(self.mira.arma))
        if self._plano and self._plano[0] == chave:
            return self._plano[1]
        plano = self._planejar(info, angulo_base, tolerancia_graus, direcao)
        self._plano = (chave, plano)
        return plano

    def _planejar(self, info, angulo_base, tolerancia_graus, direcao):
        eu, boss = info["eu"], info["boss"]
        ter = self.terreno(info)
        if ter is None:
            return None
        self.nova_partida(info)
        saida, inc, corr, origem = self.mira.contexto(eu, direcao, ter)
        lo, hi = self.mira.faixa(eu, direcao, inc)
        mapa = FX.MapaFisico(*ter.fisica())
        caixas = [_caixa(boss, CAIXA_BOSS)] + [_caixa(e, CAIXA_ELITE) for e in info["elites"]]
        ya = boss[1] - 55.0
        melhor = None
        for mira in range(int(max(lo, round(angulo_base) - tolerancia_graus)), int(min(hi, round(angulo_base) + tolerancia_graus)) + 1):
            ang = FX.angulo_envio(mira, direcao, corr)
            f0 = FX.forca_para_alvo(saida[0], saida[1], boss[0] - 40.0 * direcao, ya, ang, info["vento"], mapa=mapa)
            if f0 is None:
                continue
            p0 = f0 / FX.FORCA_MAX * 100.0
            acerta = {}
            for d in range(-JANELA_FORCA, JANELA_FORCA + 1):
                p = p0 + d
                if not 4 <= p <= 100:
                    continue
                r = FX.simular(saida[0], saida[1], p / 100.0 * FX.FORCA_MAX, ang, info["vento"], mapa=mapa, terreno=ter, alvos=caixas,
                               largura=ter.largura, altura=ter.altura + 200, limite_s=15.0)
                acerta[d] = r["motivo"] == "alvo" and r["alvo"] == 0
            melhor_trecho, ini = None, None                  # maior trecho seguido de forcas que acertam (d_ini, d_fim)
            for d in range(-JANELA_FORCA, JANELA_FORCA + 2):
                if acerta.get(d):
                    ini = d if ini is None else ini
                elif ini is not None:
                    if melhor_trecho is None or (d - 1 - ini) > (melhor_trecho[1] - melhor_trecho[0]):
                        melhor_trecho = (ini, d - 1)
                    ini = None
            if melhor_trecho is None:
                continue
            largura = melhor_trecho[1] - melhor_trecho[0] + 1
            centro = p0 + (melhor_trecho[0] + melhor_trecho[1]) / 2.0
            nota = (largura, -abs(mira - angulo_base))
            if melhor is None or nota > melhor["nota"]:
                melhor = dict(nota=nota, mira=mira, forca_pct=centro, janela=largura, janela_de=p0 + melhor_trecho[0],
                              janela_ate=p0 + melhor_trecho[1], saida=saida, inclinacao=inc, origem=origem, correcao=corr,
                              direcao=direcao, vento=info["vento"], eu=eu, boss=boss)
        return melhor

    def forca_para_mira(self, info, mira, direcao=None):
        """Forca (centro da janela) quando o ponteiro parou em `mira` (um pouco diferente do pedido)."""
        p = self.planejar(info, mira, tolerancia_graus=0, direcao=direcao)
        return p["forca_pct"] if p else None

    def aprender(self, info, mira_usada, tiro_cliente, direcao=None):
        return self.mira.aprender(info["eu"], direcao or info.get("direcao", 1), mira_usada, tiro_cliente)
