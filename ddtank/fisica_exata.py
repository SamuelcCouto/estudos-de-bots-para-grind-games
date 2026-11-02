# -*- coding: utf-8 -*-
"""
Fisica EXATA do tiro do DDTank (a mesma do servidor e do cliente do Betel), tirada do codigo do proprio jogo:
  - cliente (Flash, descompilado do cache local): phy/math/EulerVector.as, phy/object/Physics.as, phy/object/PhysicalObj.as,
    game/view/RouteComputer.as (o simulador de rota que o proprio cliente tem), game/model/LocalPlayer.calcBombAngle,
    game/view/EnergyView.as (barra: +20 por quadro, maximo 2000);
  - servidor (emulador publico DDTank 4.1, github.com/pnkl1999/DDTank41): Living.ShootImp e Phy/Object/SimpleBomb.cs (passo 0,04 s).

Modelo (Euler semi-implicito, eixo y para BAIXO, em px do mapa):
    a = (F - arrasto * v) / massa ;  v += a * dt ;  x += v * dt          (dt = 0,04 s)
    F_x = vento * bala.Wind              F_y = mapa.Weight * bala.Weight * bala.Mass
    arrasto = mapa.DragIndex * bala.DragIndex
    v0 = (int(forca * cos(ang)), int(forca * sin(ang)))   forca em unidades 0-2000 (100% da barra = 2000; 1% = 20 = 1 quadro)
Dados (dados/jogo/*.xml, baixados por estudos/extrair_cliente.py): 538 de 540 mapas tem Weight=10, DragIndex=2; 1906 de 1910 balas
tem Mass=10, Weight=70, Wind=240, DragIndex=1 -> por padrao: ay = 700 - 0,2*vy ; ax = 24*vento - 0,2*vx.
Regua do jogo: 1 unidade = 100 px do mapa (tela de 1000 px = 10 unidades). Validado contra as tabelas EstAng (testes).
"""
import math
from dataclasses import dataclass

DT = 0.04
FORCA_MAX = 2000            # unidades do pacote de tiro (barra cheia)
FORCA_POR_QUADRO = 20       # a barra sobe isto a cada quadro com o espaco apertado (EnergyView.SHOOT_FORCE_STEP)
PX_POR_UNIDADE = 100.0      # regua 0-10 embaixo da tela
PASSO_COLISAO = 3           # PhysicalObj.moveTo testa a colisao a cada 3 px


@dataclass(frozen=True)
class Bala:
    mass: float = 10.0
    weight: float = 70.0     # fator de gravidade
    wind: float = 240.0      # fator de vento
    drag: float = 1.0        # fator de arrasto


@dataclass(frozen=True)
class MapaFisico:
    weight: float = 10.0     # gravidade do mapa (MapInfo.Weight)
    drag: float = 2.0        # resistencia do ar (MapInfo.DragIndex)


BALA_PADRAO, MAPA_PADRAO = Bala(), MapaFisico()


def angulo_envio(angulo_mira, direcao, inclinacao=0.0):
    """Angulo que vai no pacote (LocalPlayer.calcBombAngle): direcao +1 = olhando para a direita, -1 = esquerda.
    angulo_mira = o numero do mostrador (gunAngle); inclinacao = playerAngle (o boneco inclinado no terreno)."""
    return inclinacao - angulo_mira if direcao > 0 else inclinacao + angulo_mira - 180.0


def forca_unidades(pct):
    return max(0, min(FORCA_MAX, int(round(pct / 100.0 * FORCA_MAX))))


def velocidade_inicial(forca, angulo, fator=1.0, desvio=0):
    """Como o servidor: int() em cada componente. fator/desvio = 2o e 3o projetil do tiro triplo (0,9/-5 e 1,1/+5)."""
    a = (angulo + desvio) / 180.0 * math.pi
    return int(forca * fator * math.cos(a)), int(forca * fator * math.sin(a))


def simular(x0, y0, forca, angulo, vento=0.0, bala=BALA_PADRAO, mapa=MAPA_PADRAO, terreno=None, alvos=(), raio=3,
            limite_s=20.0, largura=None, altura=None):
    """Simula o projetil. terreno(x0, y0, x1, y1) -> True se o retangulo tem chao (None = sem terreno); alvos = [(x0,y0,x1,y1)]
    (retangulos dos bonecos). Devolve dict(pontos, impacto=(x, y), motivo='alvo'|'chao'|'fora'|'tempo', alvo=indice|None)."""
    vx, vy = velocidade_inicial(forca, angulo)
    m, arf = bala.mass, mapa.drag * bala.drag
    fx, fy = vento * bala.wind, mapa.weight * bala.weight * bala.mass
    x, y, t = float(x0), float(y0), 0.0
    pontos = [(x, y)]

    def colide(px, py):
        r = (px - raio, py - raio, px + raio, py + raio)
        for i, (a0, b0, a1, b1) in enumerate(alvos):
            if r[0] <= a1 and r[2] >= a0 and r[1] <= b1 and r[3] >= b0:
                return "alvo", i
        if terreno is not None and terreno(*r):
            return "chao", None
        if largura is not None and (px < 0 or px > largura or (altura is not None and py > altura)):
            return "fora", None
        return None, None

    while t < limite_s:
        vx += (fx - arf * vx) / m * DT
        nx = x + vx * DT
        vy += (fy - arf * vy) / m * DT
        ny = y + vy * DT
        t += DT
        dist = math.hypot(nx - x, ny - y)
        if dist >= PASSO_COLISAO and (alvos or terreno is not None or largura is not None):
            n = int(max(abs(int(nx) - int(x)), abs(int(ny) - int(y))))
            k = n
            while k > 0:                                    # do ponto antigo para o novo, de 3 em 3 px (como o cliente)
                f = k / n
                px, py = x * f + nx * (1 - f), y * f + ny * (1 - f)
                motivo, idx = colide(px, py)
                if motivo:
                    pontos.append((px, py))
                    return dict(pontos=pontos, impacto=(px, py), motivo=motivo, alvo=idx, tempo=t)
                k -= PASSO_COLISAO
        x, y = nx, ny
        pontos.append((x, y))
        if terreno is None and not alvos and largura is None and vy > 0 and y >= y0 + 5000:
            break
    return dict(pontos=pontos, impacto=(x, y), motivo="tempo", alvo=None, tempo=t)


def x_na_altura(x0, y0, forca, angulo, y_alvo, vento=0.0, bala=BALA_PADRAO, mapa=MAPA_PADRAO):
    """x em que o projetil (sem terreno) desce passando pela altura y_alvo. None se nunca chega la descendo."""
    vx, vy = velocidade_inicial(forca, angulo)
    m, arf = bala.mass, mapa.drag * bala.drag
    fx, fy = vento * bala.wind, mapa.weight * bala.weight * bala.mass
    x, y = float(x0), float(y0)
    for _ in range(int(20 / DT)):
        vx += (fx - arf * vx) / m * DT
        nx = x + vx * DT
        vy += (fy - arf * vy) / m * DT
        ny = y + vy * DT
        if vy > 0 and y <= y_alvo <= ny:
            return x + (nx - x) * (y_alvo - y) / (ny - y) if ny != y else nx
        x, y = nx, ny
    return None


def forca_para_alvo(x0, y0, xa, ya, angulo, vento=0.0, bala=BALA_PADRAO, mapa=MAPA_PADRAO):
    """Menor forca (unidades 0-2000, multiplo de 20 = um quadro) cujo tiro desce sobre (xa, ya), ou None.
    Busca binaria em unidades (o x de chegada cresce com a forca para um angulo fixo)."""
    sentido = 1 if math.cos(math.radians(angulo)) >= 0 else -1

    def erro(f):
        xi = x_na_altura(x0, y0, f, angulo, ya, vento, bala, mapa)
        return None if xi is None else (xi - xa) * sentido

    lo, hi = 0, FORCA_MAX
    if erro(hi) is None or erro(hi) < 0:
        return None
    while hi - lo > 1:
        mid = (lo + hi) // 2
        e = erro(mid)
        if e is None or e < 0:
            lo = mid
        else:
            hi = mid
    melhor = min((lo, hi), key=lambda f: abs(erro(f)) if erro(f) is not None else 1e9)
    quadros = round(melhor / FORCA_POR_QUADRO)
    return quadros * FORCA_POR_QUADRO


def alcance_plano(forca_pct, angulo_mira, vento=0.0):
    """Distancia (px do mapa) no plano, olhando para a direita, saindo e caindo na mesma altura."""
    a = angulo_envio(angulo_mira, +1)
    xi = x_na_altura(0.0, 0.0, forca_unidades(forca_pct), a, 0.0, vento)
    return xi
