# -*- coding: utf-8 -*-
"""
PVP (Combate Livre) - versao 1: o bot JOGA e GRAVA as tentativas; quem aprende com elas e a analise depois.

Uso: abra a sala de PVP no jogo (ou deixe na sala pronta) e rode `PVP.bat` (ou `python pvp.py`). O bot:
  - na SALA clica em Inicio (a cada ~12 s; `--sem-inicio` desliga), no pop-up "Clique no jogo" clica numa area neutra;
  - na BATALHA joga cada turno com o mesmo atirador das instancias (angulo pelas setas, forca segurando espaco), sem itens;
  - a cada tiro grava UMA linha em dados/pvp_tentativas.jsonl: angulo, forca, vento lido (e confianca), posicoes dos dois
    bonecos no minimapa, o que o previsor queria, e os prints do turno, do voo (ate 6) e do depois do tiro;
  - quando a partida acaba, grava um evento "partida" (duracao, tiros).
Ele NAO sabe se acertou (nao ha barra de vida de boss no PVP): o resultado de cada tiro se confere nos prints do voo.
Por isso a memoria de tiros NAO aprende nada aqui (so grava); depois da analise os acertos viram sementes.
Para a leitura do vento melhorar: recortes de leitura duvidosa vao para dados/pvp_vento_duvidoso/ (ver vento.py).
Para parar: F10, o botao PARAR do painel (logs/parar.flag) ou --minutos. F8 pausa/continua nao existe aqui (so PARAR).
"""
import argparse
import math
import datetime
import json
import os
import sys
import time

import cv2
import numpy as np

import atirador as atirador_mod
import config
import estados as estados_mod
import leitura as L
import memoria as memoria_mod
import registro as registro_mod
import vento as vento_mod
import mira_exata
import rede_vivo
import terreno_jogo
from navegador import (ARQUIVO_PARAR, FOCO_PONTO_NEUTRO, FOCO_PONTO_PADRAO, SALA_INICIO, VK_F10, IOJanela, em_1280,
                       evitar_suspensao, instancia_unica)

INSTANCIA = "PVP"
ARQ_TENTATIVAS = os.path.join(config.PASTA, "dados", "pvp_tentativas.jsonl")
PASTA_VENTO_DUVIDOSO = os.path.join(config.PASTA, "dados", "pvp_vento_duvidoso")
LEITURAS_VENTO = 3                  # leituras do painel no comeco do turno (vota o valor mais comum)
INTERVALO_VOO = 0.8                 # s entre prints do voo do tiro
MAX_PRINTS_VOO = 6
VEZ_CURTA_S = 2.0                   # a sua vez que dura menos que isso nao deu para agir (PASS so piscou)
VEZES_CURTAS_ALERTA = 3             # tantas vezes curtas seguidas = algo errado com o seu boneco (congelado? morto? sem vez?)
BATIMENTO_QUADRO_S = 20.0           # s entre prints de diagnostico durante a batalha
MAX_QUADROS_DIAG = 150              # trava por sessao (cada print ~100 KB)
LIMITE_BUSCA_S = 600.0              # busca de partida parada ha mais que isso: cancela e busca de novo
PASS_LIMIAR_PVP = 0.55              # o PASS e um texto translucido sobre o mapa: em fundos claros a nota cai (com PASS 0.7-0.9; sem 0.0-0.5)
JANELA_VEZ_S = 11.0                 # a vez confirmada vale por esse tempo desde o inicio (o PASS some no meio do turno em alguns mapas)
HOLD_VEZ_S = 1.5                    # a nota do PASS oscila no voo do tiro (0.45-0.9): so e "fim da vez" depois de 1,5 s sem PASS
ESCALA_PADRAO = 4.0                 # px de minimapa por unidade de distancia (a "caixa" de 10 unidades tem 35-48 px; ajustar por mapa em indice.json)
A_TAB, C_TAB = 6.0663e-03, -2.5415e-05   # fisica das tabelas EstrAng 20/30/50/65: distancia = (A*F^2 + C*F^3) * sen(2*angulo)
AFUNDOU_PX = 8.0                    # seu boneco desceu isso no minimapa desde o comeco da partida: o chao cedeu -> voa com o F
LONGE_PX = 58.0                     # inimigo mais longe que isso: o aviao aproxima
MAX_AVIOES_PARTIDA = 4
INTERVALO_AVIAO_TIROS = 3           # tiros entre dois avioes
ORDENS_PVP = ([3] + [4] * 8,)       # 3 (2 tiros) + 4 (buff) ate a stamina acabar; sem 1/2 (pedido do usuario 03/11: contra bots, 2 tiros fortes matam em 1 turno)
ANGULO_PVP = 55.0                   # angulo fixo: o resultado de cada tiro (acertou/errou) ajusta a escala do mapa, nao o angulo
MULT_ESCALA = (1.0, 1.12, 0.89, 1.25, 0.8, 1.4, 0.7)   # busca da escala do mapa: tenta alternando para os dois lados ate acertar
INIMIGO_BARRA = (683, 188, 722, 202)   # barra de vida VERMELHA embaixo do avatar do inimigo (x0, y0, x1, y1), quadro de 1280
PX_POR_UNID_TELA = 65.7             # px da tela principal por unidade da regua 0-10 do jogo (a mesma das tabelas de distancia: 315 -> 972 px)
TELA_JOGO = (312, 250, 980, 540)    # area do jogo (x0, y0, x1, y1) onde procurar as barras de vida dos bonecos (fora do minimapa e do HUD)
ANGULO_MAX_PVP, PASSO_ANGULO = 80.0, 10.0   # "direcao errada" (tiro bate no terreno colado em nos): sobe o angulo
MSG_ERRADA_POS = (380, 320)         # aviso "Voce atirou em uma direcao errada, tente ajusta-la antes de disparar novamente" (2 linhas)
MSG_CURTO_POS = (387, 330)          # (x, y) do aviso "O poder nao e suficiente, tente aumentar o seu poder" (tiro CURTO), quadro de 1280
MSG_CURTO_LIMIAR = 0.8
PASSO_CURTO, PASSO_OUTRO = 0.88, 1.07   # escala do mapa x isto: aviso de tiro curto -> mais forca; erro sem aviso -> um pouco menos
CAIXA_MINI = (815, 156, 985, 256)   # minimapa (x0, y0, x1, y1): o retangulo azul dele e a area VISIVEL da tela
UNID_TELA = 10.17                   # unidades da regua do jogo que cabem na tela inteira (largura do retangulo / isto = px de minimapa por unidade)
TAXA_FORCA_REDE = 27.0              # %/s segurando o espaco (medido pela rede em 8 tiros, 02/11: 1,68 s -> 45%, 3,15 s -> 88%)
QUEDA_BARRA_PX = 3                  # a barra (~22 px) encolhendo isto ou mais = acerto
PRESO_S = 120.0                     # s em tela desconhecida fora da batalha: clica numa area neutra e avisa
INTERVALO_INICIO = 12.0             # s entre dois cliques em Inicio na sala
SETA_SERVIDOR = (885, 455, 925, 495)   # seta do botao "Mesmo servidor" (ao lado do Inicio): AZUL com a sala livre, CINZA enquanto busca partida
SETA_AZUL_LIVRE = 60                   # pixels azuis: livre ~114; buscando 0 (medido na gravacao 020551)
SETA_AZUL_BUSCANDO = 20
AVISO_BUSCA = 120.0                    # s entre avisos no log enquanto espera achar partida
SAIDA_BATALHA_S = 6.0               # s seguidos fora da batalha (e sem a sua vez) = a partida acabou (a tela pisca "desconhecida" no meio da luta)
BATIMENTO_S = 30.0                  # s entre linhas de status do log durante a batalha
MAPA_RECORTE = (638, 494, 834, 552)  # miniatura do mapa na tela VS (canto de baixo, "Arena"); (636, 458, 840, 556) inclui o nome
MAPA_NOME_RECORTE = (636, 458, 840, 556)
MAPA_DIST_MAX = 10                  # bits de diferenca (de 64) para ser o mesmo mapa
PASTA_MAPAS = os.path.join(config.PASTA, "dados", "pvp_mapas")
PASTA_BARRA_CARGA = os.path.join(config.PASTA, "dados", "pvp_barra_carga")   # recortes da barra de forca durante a carga (estudo)
RECORTE_BARRA = (520, 580, 395, 765)       # y0, y1, x0, x1: a barra de forca e um pouco em volta
CARGA_INICIO_MAX = 2.5             # s esperando a barra sair do 0 (se nao sair, solta pelo relogio)
BARRA_ATRASO = 3.0                 # % que a barra lida fica atras da forca real (~0,1 s de atraso da captura; 03/11)
CARGA_JANELA = (0.7, 1.4)                  # a barra so manda soltar entre 0,7x e 1,4x do tempo estimado (a taxa real variou 27-40%/s)
PRINTS_DO_PVP = ("turno_inicio", "tiro_dado", "turno_pulado", "voo", "pos_tiro", "partida_fim", "desconhecida", "mapa", "vez", "batalha", "preso")


def pixels_azuis_seta(f):
    x0, y0, x1, y1 = SETA_SERVIDOR
    h = cv2.cvtColor(f[y0:y1, x0:x1], cv2.COLOR_BGR2HSV)
    return int(((h[..., 0] > 95) & (h[..., 0] < 125) & (h[..., 1] > 120) & (h[..., 2] > 120)).sum())


def sala_livre(f):
    """True: o botao e "Inicio" (da para clicar). False: virou "Cancele" (esta buscando partida - clicar CANCELA a busca) ou duvida."""
    return pixels_azuis_seta(f) >= SETA_AZUL_LIVRE


def sala_buscando(f):
    return pixels_azuis_seta(f) <= SETA_AZUL_BUSCANDO


def hash_mapa(f):
    """dHash de 64 bits da miniatura do mapa (tela VS): parecido mesmo com o fade-in da tela."""
    x0, y0, x1, y1 = MAPA_RECORTE
    g = cv2.cvtColor(f[y0:y1, x0:x1], cv2.COLOR_BGR2GRAY)
    p = cv2.resize(g, (9, 8), interpolation=cv2.INTER_AREA).astype(np.int16)
    bits = (p[:, 1:] > p[:, :-1]).ravel()
    return int("".join("1" if b else "0" for b in bits), 2)


def contraste_mapa(f):
    x0, y0, x1, y1 = MAPA_RECORTE
    return float(cv2.cvtColor(f[y0:y1, x0:x1], cv2.COLOR_BGR2GRAY).std())


class CatalogoMapas:
    """Mapas do PVP vistos na tela VS: cada um vira um id (m001, m002...) com a miniatura guardada em dados/pvp_mapas/.
    O nome do mapa a gente descobre depois olhando o PNG (e escreve em indice.json, campo "nome")."""
    def __init__(self, pasta=PASTA_MAPAS):
        self.pasta = pasta
        self.arq = os.path.join(pasta, "indice.json")
        self.mapas = json.load(open(self.arq, encoding="utf-8")) if os.path.exists(self.arq) else {}

    def escala(self, mid):
        """px de minimapa por unidade de distancia deste mapa (campo "escala" de indice.json; sem ele, ESCALA_PADRAO)."""
        return float(self.mapas.get(mid, {}).get("escala") or ESCALA_PADRAO)

    def escala_travada(self, mid):
        return bool(self.mapas.get(mid, {}).get("escala_ok"))

    def definir_escala(self, mid, escala, ok):
        """Grava a escala de um mapa (ok=True: um tiro acertou com ela; nas proximas partidas vale direto)."""
        if mid not in self.mapas:
            return
        self.mapas[mid]["escala"] = round(float(escala), 3)
        self.mapas[mid]["escala_ok"] = bool(ok)
        try:
            json.dump(self.mapas, open(self.arq, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        except OSError:
            pass

    def identificar(self, f):
        """(id, novo?, quantas vezes ja visto) - registra o mapa se for novo."""
        h = hash_mapa(f)
        melhor = min(self.mapas.items(), key=lambda kv: bin(int(kv[1]["hash"], 16) ^ h).count("1"), default=None)
        if melhor and bin(int(melhor[1]["hash"], 16) ^ h).count("1") <= MAPA_DIST_MAX:
            mid = melhor[0]
            self.mapas[mid]["vistas"] += 1
            novo = False
        else:
            mid = f"m{len(self.mapas) + 1:03d}"
            self.mapas[mid] = {"hash": f"{h:016x}", "vistas": 1, "nome": None, "png": mid + ".png"}
            novo = True
            os.makedirs(self.pasta, exist_ok=True)
            x0, y0, x1, y1 = MAPA_NOME_RECORTE
            cv2.imwrite(os.path.join(self.pasta, mid + ".png"), f[y0:y1, x0:x1])
        try:
            os.makedirs(self.pasta, exist_ok=True)
            json.dump(self.mapas, open(self.arq, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        except OSError:
            pass
        return mid, novo, self.mapas[mid]["vistas"]


ANGULOS_PVP = (45.0, 60.0, 70.0, 55.0, 75.0, 65.0, 50.0)      # angulos alternados: variedade ajuda a calibrar a fisica (o resultado se confere nos prints)


class MemoriaPvp(memoria_mod.Memoria):
    """Angulo em rodizio e forca pelas TABELAS do jogo (distancia em unidades = dx_minimapa / escala; alvo mais baixo/alto que
    voce corrige a distancia pela balistica). Nao aprende com o resultado (o PVP nao o conhece): so grava; os acertos entram
    depois, pela analise dos prints."""
    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self.n_pvp = 0
        self.escala = ESCALA_PADRAO
        self.escala_base = ESCALA_PADRAO
        self.escala_ok = False             # um tiro ja acertou com a escala atual neste mapa
        self.i_busca = 0
        self.angulo = ANGULO_PVP           # sobe 10 graus a cada aviso de "direcao errada" (obstaculo na frente)
        self.larguras = []                 # larguras do retangulo do minimapa vistas neste mapa

    def novo_mapa(self, escala, ok):
        self.escala_base, self.escala_ok, self.i_busca = escala, ok, 0
        self.escala = escala
        self.angulo = ANGULO_PVP
        self.larguras = []

    def medir_escala(self, largura):
        """Guarda a largura do retangulo; com 2 leituras iguais (+-3 px) a escala do mapa vira largura/10,17 e fica travada.
        Devolve a escala se acabou de fixar, senao None."""
        if largura is None or self.escala_ok:
            return None
        self.larguras = (self.larguras + [float(largura)])[-6:]
        if len(self.larguras) >= 2 and abs(self.larguras[-1] - self.larguras[-2]) <= 3:
            self.escala = float(np.median(self.larguras[-2:])) / UNID_TELA
            self.escala_base, self.escala_ok = self.escala, True
            return self.escala
        return None

    def resultado(self, acertou, curto=False, errada=False):
        """Acertou: trava a escala (vale para o mapa). Errou com o aviso do jogo de tiro CURTO: mais forca (escala menor); erro sem
        aviso: um pouco menos de forca (pode ter passado, ou bateu no terreno)."""
        if errada and not acertou:
            self.angulo = min(self.angulo + PASSO_ANGULO, ANGULO_MAX_PVP)      # o problema e o angulo, nao a forca: a escala fica
        elif acertou:
            self.escala_ok = True
        elif not self.escala_ok and not self.tela_pos:
            self.i_busca += 1
            self.escala = float(np.clip(self.escala * (PASSO_CURTO if curto else PASSO_OUTRO), 1.5, 12.0))
        return self.escala, self.escala_ok

    tela_pos = None                        # ((x, y) nosso, (x, y) inimigo) na tela principal neste turno (None = usa o minimapa)

    def melhor_tiro(self, inst, dx, dy, angulo=None):
        ang = 55.0 if angulo is None else float(angulo)
        f_chao = memoria_mod.fator_balistico(dx, 0.0, ang)
        f_alvo = memoria_mod.fator_balistico(dx, dy, ang)
        if not f_chao or not f_alvo:
            return None
        d_efetiva = (dx / (PX_POR_UNID_TELA if self.tela_pos else self.escala)) * (f_alvo / f_chao)
        return ang, float(np.clip(forca_tabela(d_efetiva, ang), memoria_mod.FORCA_MIN, memoria_mod.FORCA_MAX)), 0.5

    plano_rede = None                      # plano EXATO deste turno (rede + fisica; mira_exata.py). None = metodo antigo
    forca_rede = None                      # funcao(mira) -> forca % para a mira que o mostrador realmente parou

    def forca_para(self, inst, azul, boss, angulo):
        if self.plano_rede and self.forca_rede:
            return self.forca_rede(angulo)
        if self.tela_pos:
            azul, boss = self.tela_pos
        if not (azul and boss) or abs(boss[0] - azul[0]) < memoria_mod.DX_MINIMO:
            return None
        mt = self.melhor_tiro(inst, abs(boss[0] - azul[0]), azul[1] - boss[1], angulo=angulo)
        return None if mt is None else mt[1]

    def prever(self, inst, azul, boss):
        if self.plano_rede:
            pl = self.plano_rede
            return {"angulo": float(pl["mira"]), "forca": float(pl["forca_pct"]), "origem": "rede+fisica exata",
                    "detalhe": f"angulo enviado {pl['angulo_envio']:.0f}, vento {pl['vento']:+.1f}, cai em x={pl['queda_x']:.0f} "
                               f"(alvo {pl['alvo'][0]:.0f}), folga {pl['folga_px']:.0f} px/1%-1grau, saida {pl['origem']}"
                               + ("" if pl.get("acertos") is None else f", {pl['acertos']}/5 variacoes acertam com o terreno")}
        if self.tela_pos:
            azul, boss = self.tela_pos
        if azul and boss and abs(boss[0] - azul[0]) >= memoria_mod.DX_MINIMO:
            ang = self.angulo
            self.n_pvp += 1
            mt = self.melhor_tiro(inst, abs(boss[0] - azul[0]), azul[1] - boss[1], angulo=ang)
            if mt:
                if self.tela_pos:
                    estado, esc = "medido na tela principal", PX_POR_UNID_TELA
                else:
                    estado = "TRAVADA: ja acertou neste mapa" if self.escala_ok else f"busca {self.i_busca + 1}/{len(MULT_ESCALA)}"
                    esc = self.escala
                return self._limites(inst, ang, mt[1], "pvp-tabela",
                                     f"angulo {ang:.0f}; forca pelas tabelas (escala {esc:.2f} px/unid, {estado})")
        return super().prever(inst, azul, boss)


class RegistroPvp(registro_mod.Registro):
    """Como o Registro, mas so grava os prints do PVP (turno, voo, depois do tiro): uma hora inteira fica em dezenas de MB."""
    def frame(self, img, rotulo):
        if rotulo not in PRINTS_DO_PVP:
            return None
        self.leve = False
        return super().frame(img, rotulo)


class LeitorPvp(atirador_mod.LeitorReal):
    """No PVP nao ha barra de vida de boss nem especial das instancias: o atirador joga mira + itens + forca.
    A sua vez tem histerese: a nota do PASS oscila quando o tiro voa, e sem isso o bot achava que era outro turno e atirava de novo."""
    vida = staticmethod(lambda f: 100.0)
    pow_cheio = staticmethod(lambda f: False)
    numeros_dano = staticmethod(lambda f: 0)
    buff_pet = staticmethod(lambda f: False)          # o icone do buff do pet aparece sempre "ligado" no PVP: nao serve
    vento = staticmethod(vento_mod.ler_vento)

    msg_curto = staticmethod(lambda f: msg_poder_curto(f))
    msg_errada = staticmethod(lambda f: msg_direcao_errada(f))

    @staticmethod
    def vida_inimigo(f):
        """Largura (px) da barra de vida vermelha do inimigo (~22 com a vida cheia); 0 se nao achou."""
        x0, y0, x1, y1 = INIMIGO_BARRA
        r = f[y0:y1, x0:x1].astype(int)
        m = (r[..., 2] > 170) & (r[..., 1] < 110) & (r[..., 0] < 130)
        return int(m.sum(1).max()) if m.size else 0

    def __init__(self, agora=None):
        self.agora = agora or time.time
        self.ultima_vez = -1e9
        self.inicio_vez = -1e9

    def minha_vez(self, f):
        """True na sua vez. A nota do PASS cai a 0.3-0.4 no meio do turno em alguns mapas/posicoes (texto translucido sobre fundo
        claro): depois que a vez foi confirmada (nota >= limiar), ela vale por JANELA_VEZ_S desde o inicio, mesmo sem PASS."""
        t = self.agora()
        if pontuacao_pass(f) >= PASS_LIMIAR_PVP or contador_da_vez(f):
            if t - self.ultima_vez > HOLD_VEZ_S:
                self.inicio_vez = t                       # PASS reapareceu depois de sumir: vez nova
            self.ultima_vez = t
            return True
        if t - self.ultima_vez < HOLD_VEZ_S:
            return True
        return self.ultima_vez > -1e8 and t - self.inicio_vez < JANELA_VEZ_S


def largura_caixa_minimapa(f):
    """Largura (px) do retangulo azul do minimapa (a tela inteira = 10,17 unidades), ou None se nao achou. Mede a ESCALA do mapa sem tiro
    nenhum: o padrao de 4 px/unid estava errado por mais de 2x nos mapas largos (92 px -> 9,0 px/unid; 01/11)."""
    if not isinstance(f, np.ndarray) or f.ndim != 3 or f.shape[0] < CAIXA_MINI[3]:
        return None
    x0, y0, x1, y1 = CAIXA_MINI
    h = cv2.cvtColor(f[y0:y1, x0:x1], cv2.COLOR_BGR2HSV)
    m = ((h[..., 0] >= 112) & (h[..., 0] <= 130) & (h[..., 1] >= 150) & (h[..., 2] >= 90)).astype(np.uint8)
    lados = cv2.erode(m, np.ones((14, 1), np.uint8)).any(axis=0)         # colunas com uma corrida vertical azul de >= 14 px
    cols = np.where(lados)[0]
    if len(cols) < 2:
        return None
    grupos, atual = [], [cols[0]]
    for c in cols[1:]:
        if c - atual[-1] <= 2:
            atual.append(c)
        else:
            grupos.append(atual)
            atual = [c]
    grupos.append(atual)
    cs = [float(np.mean(g)) for g in grupos]
    larg = [cs[j] - cs[i] for i in range(len(cs)) for j in range(i + 1, len(cs)) if cs[j] - cs[i] >= 40]
    return min(larg) if larg else None


_TPL_MSG = {}


def _msg_jogo(f, arq, pos):
    """Aviso de texto do jogo (letras brancas sobre faixa escura): casa a mascara das letras, que nao depende do fundo."""
    if arq not in _TPL_MSG:
        _TPL_MSG[arq] = cv2.imread(os.path.join(config.PASTA_TEMPLATES, arq), cv2.IMREAD_GRAYSCALE)
    t = _TPL_MSG[arq]
    if t is None or f is None or f.ndim != 3 or f.shape[0] < 420:
        return False
    x0, y0 = pos
    th, tw = t.shape
    h = cv2.cvtColor(f[y0 - 8:y0 + th + 8, x0 - 20:x0 + tw + 20], cv2.COLOR_BGR2HSV)
    roi = ((h[..., 1] < 45) & (h[..., 2] > 225)).astype(np.float32) * 255
    if roi.shape[0] < th or roi.shape[1] < tw:
        return False
    return float(cv2.matchTemplate(roi, t.astype(np.float32), cv2.TM_CCOEFF_NORMED).max()) >= MSG_CURTO_LIMIAR


def msg_poder_curto(f):
    """"O poder nao e suficiente, tente aumentar o seu poder": o tiro ficou CURTO (feedback do jogo, 4 de 4 tiros curtos, 01/11)."""
    return _msg_jogo(f, "msg_poder_curto.png", MSG_CURTO_POS)


def msg_direcao_errada(f):
    """"Voce atirou em uma direcao errada...": o tiro explodiu colado no boneco (terreno/obstaculo na frente; no mapa do carro tirou 17 mil
    da nossa propria vida). Resposta: subir o angulo."""
    return _msg_jogo(f, "msg_direcao_errada.png", MSG_ERRADA_POS)


def barras_na_tela(f):
    """Barras de vida finas embaixo dos bonecos na tela principal: [(x, y, largura)] azuis (a nossa) e vermelhas (inimigos).
    Funciona em qualquer mapa (o minimapa de mapas verdes/ilhas perde o ponto azul) e mede a distancia na MESMA unidade das tabelas."""
    x0, y0, x1, y1 = TELA_JOGO
    h = cv2.cvtColor(f[y0:y1, x0:x1], cv2.COLOR_BGR2HSV)
    saida = {}
    for nome, m in (("azul", (h[..., 0] >= 100) & (h[..., 0] <= 125) & (h[..., 1] >= 170) & (h[..., 2] >= 150)),
                    ("verm", ((h[..., 0] <= 6) | (h[..., 0] >= 172)) & (h[..., 1] >= 170) & (h[..., 2] >= 170))):
        n, _lb, st, _c = cv2.connectedComponentsWithStats(m.astype(np.uint8), connectivity=8)
        saida[nome] = [(int(x + x0 + w / 2), int(y + y0), int(w)) for x, y, w, hh, a in st[1:]
                       if 14 <= w <= 40 and 2 <= hh <= 7 and a >= 0.7 * w * hh]
    return saida


def posicoes_na_tela(f):
    """((x, y) do nosso boneco, (x, y) do inimigo) na tela principal, ou None se nao houver exatamente uma barra azul e uma vermelha."""
    if not isinstance(f, np.ndarray) or f.ndim != 3:
        return None
    b = barras_na_tela(f)
    if len(b["azul"]) != 1 or len(b["verm"]) != 1:
        return None
    (ax, ay, _), (rx, ry, _) = b["azul"][0], b["verm"][0]
    return (float(ax), float(ay)), (float(rx), float(ry))


def distancia_tabela(forca, ang):
    """Distancia (unidades da regua) que um tiro de `forca`% alcanca no plano com `ang` graus (fisica ajustada nas tabelas do jogo)."""
    sen2 = np.sin(np.radians(2 * ang))
    return (A_TAB * forca ** 2 + C_TAB * forca ** 3) * sen2


def forca_tabela(dist, ang):
    """Forca (%) para alcancar `dist` unidades com `ang` graus (inverte distancia_tabela, que cresce com a forca ate ~159%)."""
    lo, hi = 0.0, 100.0
    for _ in range(40):
        meio = (lo + hi) / 2
        if distancia_tabela(meio, ang) < dist:
            lo = meio
        else:
            hi = meio
    return (lo + hi) / 2


_TPL_PASS = []


def pontuacao_pass(f):
    """Nota (0-1) do "PASS" da sua vez no quadro - a mesma leitura de leitura.minha_vez, mas devolvendo a nota."""
    if not _TPL_PASS:
        _TPL_PASS.append(cv2.imread(os.path.join(config.PASTA_TEMPLATES, "pass.png"), cv2.IMREAD_GRAYSCALE))
    t = _TPL_PASS[0]
    th, tw = t.shape
    g = cv2.GaussianBlur(cv2.cvtColor(f, cv2.COLOR_BGR2GRAY), (3, 3), 0)
    x, y = L.PASS_POS
    roi = g[y - 6:y + th + 6, x - 8:x + tw + 8]
    return float(cv2.matchTemplate(roi, t, cv2.TM_CCOEFF_NORMED).max())


CONTADOR_CAIXA = (596, 205, 662, 262)     # numero vermelho do contador do turno (acima do "PASS"): so existe na sua vez
CONTADOR_ALTURA_MIN, CONTADOR_AREA_MIN = 14, 100


def contador_da_vez(f):
    """True se o numero vermelho/laranja do contador do turno esta na tela. Muito mais robusto que o texto "PASS" (translucido: em
    mapas de fundo claro a nota cai a 0.4-0.5 mesmo com voce atirando). Medido em 1552 quadros de batalha: acerta 100% dos quadros
    da sua vez (incl. os 6 do mapa claro) e 0% dos de fora."""
    if f is None or f.ndim != 3 or f.shape[0] < CONTADOR_CAIXA[3]:
        return False
    x0, y0, x1, y1 = CONTADOR_CAIXA
    h = cv2.cvtColor(f[y0:y1, x0:x1], cv2.COLOR_BGR2HSV)
    m = (((h[..., 0] <= 18) | (h[..., 0] >= 170)) & (h[..., 1] >= 150) & (h[..., 2] >= 170)).astype(np.uint8)
    m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8))
    n, _lb, st, _c = cv2.connectedComponentsWithStats(m, connectivity=8)
    if n < 2:
        return False
    i = 1 + int(np.argmax(st[1:, 4]))
    return bool(st[i, 3] >= CONTADOR_ALTURA_MIN and st[i, 4] >= CONTADOR_AREA_MIN)


def votar_vento(leituras):
    """leituras: [(valor, confianca)]. Devolve (valor mais votado, confianca media dele, quantos votos) ou (None, 0, 0)."""
    votos = {}
    for v, c in leituras:
        if v is not None:
            votos.setdefault(round(v, 1), []).append(c)
    if not votos:
        return None, 0.0, 0
    v, cs = max(votos.items(), key=lambda kv: (len(kv[1]), sum(kv[1])))
    return v, sum(cs) / len(cs), len(cs)


class AtiradorPvp(atirador_mod.Atirador):
    def __init__(self, *a, arq_tentativas=ARQ_TENTATIVAS, pasta_vento=PASTA_VENTO_DUVIDOSO, rede=None, **kw):
        kw.setdefault("leitor", LeitorPvp(agora=kw.get("agora")))
        kw.setdefault("ordem_itens", list(ORDENS_PVP[0]))
        super().__init__(*a, **kw)
        self.rede = rede                   # rede_vivo.LeitorAoVivo (estado exato da partida) ou None (so tela)
        self.taxa_rede = TAXA_FORCA_REDE   # % de forca por segundo segurando o espaco, calibrada pela forca REAL de cada tiro (rede)
        self.taxas_medidas = [TAXA_FORCA_REDE] * 3
        self.segurou_rede = None
        self.trace_rede = []               # [(s, % lido na barra)] da ultima carga no modo rede
        self.recortes_salvos = 0
        self.pasta_barra = PASTA_BARRA_CARGA     # None = nao salva recortes (testes)
        self.mira = mira_exata.MiraExata(log=self.log)
        self.turno_rede = None             # (eu_id, eu, alvo_id, alvo, plano) deste turno
        self.arq_tentativas = arq_tentativas
        self.pasta_vento = pasta_vento
        self.vento_turno = (None, 0.0, 0)
        self.tiros_na_partida = 0
        self.partidas = 0
        self.inicio_partida = None
        self._voo_n, self._voo_t = 0, -99.0
        self.vento_duvidoso_salvos = 0
        self.mapa = None
        self.turnos_feitos_na_vez = 0
        self.itens_ultimo = []
        self.y_ref = None                  # y do seu boneco no minimapa no comeco da partida (o chao cedendo = y subindo)
        self.limite_recente = False        # o angulo bateu no limite da arma no ultimo turno (terreno inclinado/buraco)
        self.ultimo_aviao_tiro = -99
        self.e_usos = 0
        self.motivo_aviao = ""
        self.hp_inimigo0 = None
        self.salvar_escala = None          # funcao (mapa, escala, ok) que grava a escala no catalogo (o Laco liga)

    # ------------------------------------------------------------------ vento
    def ler_vento(self, f):
        leituras = [self.lei.vento(f)]
        for _ in range(LEITURAS_VENTO - 1):
            self.dormir(0.15)
            g = self.ver()
            if g is not None:
                leituras.append(self.lei.vento(g))
        v, conf, votos = votar_vento(leituras)
        if v is not None and (not vento_mod.confiavel(conf) or votos < 2):
            self._guardar_duvidoso(f, v, conf)
        return v, conf, votos

    def _guardar_duvidoso(self, f, v, conf):
        try:
            os.makedirs(self.pasta_vento, exist_ok=True)
            nome = f"{datetime.datetime.now():%Y%m%d_%H%M%S}_{self.turnos}_lido_{v:+.1f}_conf{conf:.2f}.png"
            cv2.imwrite(os.path.join(self.pasta_vento, nome), vento_mod.recorte(f))
            self.vento_duvidoso_salvos += 1
        except OSError:
            pass

    # ------------------------------------------------------------------ itens / E / F
    def aplicar_itens(self, ordem=None):
        r = super().aplicar_itens(ordem)
        self.itens_ultimo = list(r)
        return r

    def preparar_extras(self, est):
        """E (protege o terreno em volta do boneco) sempre que o slot do E estiver verde. Nunca o B (especial)."""
        f = self.ver()
        disp = getattr(self.lei, "e_disponivel", None)
        if disp is not None and f is not None and self.lei.minha_vez(f) and disp(f):
            self.io.tecla("e", 0.08)
            self.dormir(0.5)
            g = self.ver()
            if g is not None and not disp(g):
                self.e_usos += 1
                self.log(f"   [E] usado (terreno em volta protegido; {self.e_usos}x nesta sessao)")
            else:
                self.log("   [E] apertei, mas o slot continua verde (tento de novo no proximo turno)")
        return False

    def _no_limite(self, tecla, a):
        r = super()._no_limite(tecla, a)
        if r:
            self.limite_recente = True
            g = self.ver()
            if g is not None:
                lim = self.lei.angulo(g)
                pl = self.turno_rede[4] if self.turno_rede else None
                arma = self.mira.limite(tecla == "cima", lim, self.turno_rede[1] if self.turno_rede else None,
                                        pl["direcao"] if pl else None, pl["inclinacao"] if pl else None)
                extra = f" (arma {arma:.0f} graus sem a inclinacao: vale em qualquer lugar)" if arma is not None else ""
                self.log(f"   [rede] limite da arma guardado: ponteiro {'max' if tecla == 'cima' else 'min'} {lim:.0f} graus aqui{extra}")
        return r

    def posicoes(self, f):
        if self.turno_rede:                                  # px do MAPA, exatos (rede): so para virar e prever
            _eu_id, eu, _alvo_id, alvo, _pl = self.turno_rede
            return eu, alvo, 1.0
        return super().posicoes(f)

    def _plano_pela_rede(self):
        """Na NOSSA vez: posicoes, vento e alvo pela rede -> plano exato. None se a rede nao tiver o estado desta vez."""
        if not self.rede:
            return None
        self._t_plano = time.time()
        est = self.rede.estado.copia()
        for _ in range(15):                                  # o pacote da vez chega ~0,2 s depois (registro do Chromium)
            if est["chave_ok"]["servidor"] and est["vivos"] and est["vez"] is not None and time.time() - est["vez_t"] < 30:
                break
            self.dormir(0.15)
            est = self.rede.estado.copia()
        else:
            self.log("   [rede] sem o estado da vez (registro do jogo atrasado ou sem chave): mira pela tela")
            return None
        eu_id = est["eu"]
        if eu_id is None and len(est["vivos"]) == 2:
            eu_id = self._eu_pelo_minimapa(est["vivos"])        # o ponto AZUL do minimapa e o nosso: mesmo lado (esquerda/direita)
        if eu_id is None:
            if time.time() - est["vez_t"] > 4.0:
                self.log("   [rede] ainda nao sei qual boneco e o nosso e a troca de vez nao e recente: mira pela tela")
                return None
            eu_id = est["vez"]                                  # vez recente + a tela mostra a nossa vez: quem joga somos nos
        if est["vez"] != eu_id:
            self.log(f"   [rede] a rede diz que a vez e do boneco {est['vez']} (nos somos {eu_id}): nao atiro (a tela se enganou?)")
            self.agiu = True
            return "nao_e_a_vez"
        if est["eu"] is not None and est["vez"] != est["eu"]:
            self.log(f"   [rede] a rede diz que a vez e do boneco {est['vez']} (nos somos {est['eu']}): mira pela tela")
            return None
        eu = est["vivos"].get(eu_id)
        inimigos = [v for k, v in est["vivos"].items() if k != eu_id and v["vivo"]]
        if not eu or not inimigos:
            return None
        if len(est["vivos"]) > 2:
            self.log("   [rede] mais de 2 bonecos: escolho o mais perto (times ainda nao identificados)")
        alvo = min(inimigos, key=lambda v: abs(v["x"] - eu["x"]))
        ter = self._terreno(est)
        t0 = time.time()
        plano = self.mira.planejar((eu["x"], eu["y"]), (alvo["x"], alvo["y"]), est["vento"], terreno=ter)
        if not plano:
            self.log(f"   [rede] nenhuma mira {mira_exata.MIRA_MIN}-{mira_exata.MIRA_MAX} alcanca o alvo: mira pela tela")
            return None
        self.turno_rede = (eu_id, (eu["x"], eu["y"]), alvo["id"], (alvo["x"], alvo["y"]), plano)
        self.terreno_rede = ter
        self.mem.forca_rede = lambda mira: self.mira.forca_para((eu["x"], eu["y"]), (alvo["x"], alvo["y"]), est["vento"], mira,
                                                                plano["direcao"], ter)
        inc = plano["inclinacao"]
        olhando = (est.get("direcao") or {}).get(eu_id)
        if ter is None:
            sobre_terreno = "sem terreno"
        elif plano.get("bloqueado"):
            sobre_terreno = "BLOQUEADO pelo terreno em todas as miras"
        else:
            sobre_terreno = f"{plano['acertos']}/5 acertam com o terreno do mapa {est['mapa']}"
        self.log(f"   [rede] voce (boneco {eu_id}) em ({eu['x']}, {eu['y']}), alvo {alvo['id']} em ({alvo['x']}, {alvo['y']}), "
                 f"vento {est['vento']:+.1f} -> mira {plano['mira']} graus, forca {plano['forca_pct']:.0f}% "
                 f"(saida {plano['saida']} {plano['origem']}, inclinacao {'?' if inc is None else f'{inc:+.0f}'}, "
                 f"ponteiro {plano['faixa'][0]}-{plano['faixa'][1]}, {sobre_terreno}, "
                 f"olhando para a {'?' if olhando is None else ('direita' if olhando > 0 else 'esquerda')}; {time.time() - t0:.1f}s)")
        return plano

    def _terreno(self, est):
        """Terreno do mapa desta partida com os buracos ja feitos (None se o mapa nao veio pela rede ou nao deu para baixar)."""
        if est.get("mapa") is None:
            return None
        try:
            return terreno_jogo.terreno_da_partida(est["mapa"], est.get("buracos") or [])
        except (OSError, ValueError) as e:
            self.log(f"   [rede] nao consegui o terreno do mapa {est['mapa']}: {e}")
            return None

    def lado(self, f):
        """Para onde o boneco olha: pela rede (DIRECTION/MOVESTART do nosso cliente). O ponteiro NAO serve: ele mostra o angulo real
        do tiro, e num morro (63 graus, olhando para a esquerda) ele fica do lado direito (02/11)."""
        if self.turno_rede and self.rede:
            d = (self.rede.estado.copia().get("direcao") or {}).get(self.turno_rede[0])
            if d in (1, -1):
                return d
        return super().lado(f)

    def virar_para(self, lado):
        """Modo rede: toca a seta e espera o jogo confirmar a direcao pela rede (ate ~1 s por toque)."""
        if not (self.turno_rede and self.rede):
            return super().virar_para(lado)
        eu_id = self.turno_rede[0]
        if (self.rede.estado.copia().get("direcao") or {}).get(eu_id) is None:
            return super().virar_para(lado)                   # a rede ainda nao viu a direcao (inicio da partida): pelo ponteiro
        nome = "direita" if lado > 0 else "esquerda"
        for dur in atirador_mod.TOQUES_VIRAR:
            d = (self.rede.estado.copia().get("direcao") or {}).get(eu_id)
            if d == lado:
                return True
            f = self.ver()
            if f is None or not self.lei.minha_vez(f):
                return False
            diz = "?" if d is None else ("direita" if d > 0 else "esquerda")
            self.log(f"   virando para a {nome} (o alvo esta desse lado; a rede diz {diz}): toque de {dur:.2f}s")
            self.io.tecla(nome, dur)
            for _ in range(25):                               # o pacote de direcao/posicao chega 1-2 s depois do toque (03/11)
                self.dormir(0.1)
                if (self.rede.estado.copia().get("direcao") or {}).get(eu_id) == lado:
                    break
        ok = (self.rede.estado.copia().get("direcao") or {}).get(eu_id) == lado
        if not ok:
            self.log("   ! a rede nao confirmou que o boneco virou")
        return ok

    def _eu_pelo_minimapa(self, vivos):
        """Qual boneco somos, pelo minimapa: o ponto azul (nos) a esquerda ou a direita do vermelho (inimigo)."""
        f = self.ver()
        if f is None:
            return None
        self.observar_minimapa(f, forcar=True)
        azul, _c = self.rastreador.jogador()
        boss = self.rastreador.boss
        if not (azul and boss) or abs(azul[0] - boss[0]) < 3:
            return None
        a, b = sorted(vivos.values(), key=lambda v: v["x"])
        eu = a if azul[0] < boss[0] else b
        self.log(f"   [rede] pelo minimapa somos o boneco {eu['id']} (ponto azul {'a esquerda' if azul[0] < boss[0] else 'a direita'})")
        return eu["id"]

    def _resultado_pela_rede(self, p):
        """Depois do NOSSO tiro: ponto de saida/inclinacao exatos (pacote do cliente) e o resultado do servidor."""
        r = p.get("rede")
        if not r or not self.rede:
            return None
        res = None
        for _ in range(20):
            est = self.rede.estado.copia()
            meus = [t for ts, t in est["meus_tiros"] if ts >= r["t"] - 1.0]
            eu_id = est["eu"] if est["eu"] is not None else r["eu_id"]   # o pacote do NOSSO tiro confirma qual boneco somos
            dos = [t for ts, t in est["tiros"] if ts >= r["t"] - 1.0 and t["atirador"] == eu_id]
            if meus and dos:
                break
            self.dormir(0.15)
        if not meus:
            self.log("   [rede] o jogo NAO registrou tiro nosso nesta vez (nao era a nossa vez? as teclas nao chegaram?): sem resultado")
            self.segurou_rede = None
            return None
        if eu_id != r["eu_id"]:
            self.log(f"   [rede] ! o plano usou o boneco {r['eu_id']}, mas somos o {eu_id} (corrigido para as proximas vezes)")
        if meus and self.segurou_rede and self.segurou_rede > 0.8:
            taxa = (meus[0]["forca"] / 20.0) / self.segurou_rede
            self.log(f"   [rede] barra lida durante a carga (s, %): {self._resumo_trace(self.trace_rede)} | real {meus[0]['forca'] / 20:.0f}%")
            if 10 < taxa < 60:
                antes = self.taxa_rede
                self.taxas_medidas = (self.taxas_medidas + [taxa])[-7:]
                self.taxa_rede = float(np.median(self.taxas_medidas))     # mediana: uma medida estranha (48,8%/s) nao estraga
                self.log(f"   [rede] forca real {meus[0]['forca'] / 20:.0f}% em {self.segurou_rede:.2f}s -> {taxa:.1f}%/s "
                         f"(taxa da carga {antes:.1f} -> {self.taxa_rede:.1f}%/s, mediana das ultimas)")
        self.segurou_rede = None
        lado_real = 1 if math.cos(math.radians(meus[0]["angulo"])) >= 0 else -1
        longe = max(abs(meus[0]["x"] - r["eu"][0]), abs(meus[0]["y"] - r["eu"][1]))
        if longe > mira_exata.SAIDA_MAX_PX:
            self.log(f"   [rede] ! o tiro saiu de ({meus[0]['x']}, {meus[0]['y']}), {longe:.0f} px longe de onde o plano achava que estavamos "
                     f"{r['eu']}: posicao velha (o boneco caiu/foi empurrado?). Nao aprendo saida deste tiro")
        elif lado_real != r["plano"]["direcao"]:
            self.log(f"   [rede] ! o tiro saiu para a {'direita' if lado_real > 0 else 'esquerda'} (angulo {meus[0]['angulo']}), o plano era para a "
                     f"{'direita' if r['plano']['direcao'] > 0 else 'esquerda'}: o boneco nao virou. Nao aprendo inclinacao deste tiro")
        else:
            m = self.mira.aprender(r["eu"], r["plano"]["direcao"], p["angulo"], meus[0])
            sp = r["plano"]["saida"]
            corr = f"; correcao {m['correcao']:+.0f}" if m else ""
            self.log(f"   [rede] tiro enviado: saida ({meus[0]['x']}, {meus[0]['y']}) (prevista {sp[0]:.0f}, {sp[1]:.0f}, {r['plano']['origem']}), "
                     f"forca {meus[0]['forca'] / 20:.0f}%, angulo {meus[0]['angulo']} (ponteiro lido {p['angulo']:.0f}{corr})")
        if dos:
            res = mira_exata.resultado_do_tiro(dos[0], r["alvo_id"])
            ex = res["explodiu"]
            self.log(f"   [rede] RESULTADO: {'ACERTOU' if res['acertou'] else 'errou'} (dano do tiro {res['dano']}"
                     f"{', do pet ' + str(res['dano_pet']) if res.get('dano_pet') else ''})"
                     f"{f', explodiu em ({ex[0]}, {ex[1]})' if ex else ''}; alvo em ({r['alvo'][0]}, {r['alvo'][1]}), "
                     f"previsto x={r['plano']['queda_x']:.0f}{' (teleguiado)' if res['teleguiado'] else ''}")
        return res

    @staticmethod
    def _resumo_trace(trace, n=12):
        if len(trace) <= n:
            return " ".join(f"{t:.2f}:{v}" for t, v in trace)
        passo = len(trace) / n
        return " ".join(f"{t:.2f}:{v}" for t, v in (trace[int(i * passo)] for i in range(n))) + f" ... {trace[-1][0]:.2f}:{trace[-1][1]}"

    @staticmethod
    def _barra_viva(trace):
        """A barra da tela esta mostrando a carga DESTE tiro? So se ela foi vista baixa (<= 12%) e depois subiu sem voltar, a uma
        velocidade possivel (15-60%/s). Se ela fica parada no valor do tiro anterior, nao e."""
        i0 = next((i for i, (_t, v) in enumerate(trace) if v <= 12), None)
        if i0 is None:
            return False
        sub_ = trace[i0:]
        if len(sub_) < 4 or sub_[-1][1] - sub_[0][1] < 8:
            return False
        if any(b[1] < a[1] - 4 for a, b in zip(sub_, sub_[1:])):
            return False
        dt = sub_[-1][0] - sub_[0][0]
        return dt > 0 and 15 <= (sub_[-1][1] - sub_[0][1]) / dt <= 60

    def carregar(self, alvo):
        """Modo rede: solta pelo TEMPO (forca = taxa x tempo segurando, taxa calibrada pela forca real que a rede informa a cada
        tiro), a nao ser que a barra da tela esteja comprovadamente acompanhando a carga (vista baixa e subindo): ai solta pela
        barra, dentro de 0,7-1,4x do tempo estimado. A barra ficava parada no valor do tiro anterior e o bot soltava errado (pediu
        64%, sairam 88% e 45%; 02/11); e so o tempo variou demais (44% tanto com 1,15 s quanto com 1,62 s)."""
        if not self.turno_rede:
            return super().carregar(alvo)
        alvo = self._forca_agora(alvo)
        alvo = float(min(alvo, 97.0))
        self.dormir(0.4)          # logo depois dos itens o jogo ignorava o espaco: sairam 14% e 5% segurando ~2 s (03/11)
        t_alvo = alvo / self.taxa_rede
        repetir = self._segurar()
        t0, rep, motivo = self.agora(), 1, "tempo_rede"
        faltas, trace, recortes, ult_rec = 0, [], [], -1.0
        salvar = self.pasta_barra is not None and self.recortes_salvos < 4
        t_ini = None                       # quando a barra comecou a subir (o jogo as vezes so comeca a carregar 1-2 s depois, 03/11)
        while True:
            dur = self.agora() - t0
            base = t_ini if t_ini is not None else 0.0
            if t_ini is None and trace and dur < CARGA_INICIO_MAX and not any(v > 0 for _t, v in trace[-3:]) and len(trace) >= 3:
                pass                           # a barra ainda esta em 0: a carga nao comecou; espera (ate CARGA_INICIO_MAX)
            elif dur - base >= t_alvo * (CARGA_JANELA[1] if self._barra_viva(trace) else 1.0):
                break
            f = self.ver()
            if f is not None and isinstance(f, np.ndarray):
                if not self.lei.minha_vez(f):
                    faltas += 1
                    if faltas >= 2:
                        motivo = "vez_acabou"
                        break
                else:
                    faltas = 0
                v = L.forca_carga(f) if isinstance(f, np.ndarray) and f.ndim == 3 else self.lei.forca(f)
                trace.append((round(dur, 2), int(round(v))))
                if t_ini is None and v >= 2:
                    t_ini = max(0.0, dur - 0.1)
                if salvar and dur - ult_rec >= 0.12:
                    y0, y1, x0, x1 = RECORTE_BARRA
                    recortes.append((dur, f[y0:y1, x0:x1].copy()))
                    ult_rec = dur
                if self._barra_viva(trace) and dur - (t_ini or 0.0) >= CARGA_JANELA[0] * t_alvo:
                    # as leituras saem a cada ~0,25 s (a barra anda ~7% entre elas): preve quando chega no alvo e solta na hora certa
                    pts = [(t, x) for t, x in trace if x >= 2]
                    taxa = (pts[-1][1] - pts[0][1]) / (pts[-1][0] - pts[0][0]) if len(pts) >= 2 and pts[-1][0] > pts[0][0] else self.taxa_rede
                    falta = (alvo - BARRA_ATRASO - v) / max(taxa, 5.0)
                    if falta <= 0.3:
                        if falta > 0:
                            self.dormir(falta)
                        motivo = "barra_rede"
                        break
            if repetir:
                rep += 1
                self.io.tecla_baixo(atirador_mod.TECLA_ESPACO, rep)
            self.dormir(0.01)
        segurou = self.agora() - t0
        self._soltar()
        self.segurou_rede = segurou
        self.trace_rede = trace
        if salvar and recortes:
            self.dormir(0.3)
            f = self.ver()
            if f is not None and isinstance(f, np.ndarray):
                y0, y1, x0, x1 = RECORTE_BARRA
                recortes.append((segurou + 0.3, f[y0:y1, x0:x1].copy()))
            try:
                os.makedirs(self.pasta_barra, exist_ok=True)
                tag = datetime.datetime.now().strftime("%H%M%S")
                for t, img in recortes:
                    cv2.imwrite(os.path.join(self.pasta_barra, f"{tag}_{t:05.2f}s.png"), img)
                self.recortes_salvos += 1
            except (OSError, cv2.error):
                pass
        forca = trace[-1][1] if motivo == "barra_rede" else min(100.0, segurou * self.taxa_rede)
        return forca, motivo, trace, segurou

    def _forca_agora(self, alvo):
        """Na hora de carregar: forca para o angulo que o ponteiro REALMENTE mostra, com a posicao e a direcao atuais (rede): virar
        pode andar uns px e o ponteiro para 1-2 graus fora do pedido."""
        eu_id, eu0, _aid, alvo_pos, pl = self.turno_rede
        est = self.rede.estado.copia() if self.rede else None
        f = self.ver()
        if est is None or f is None or not isinstance(f, np.ndarray):
            return alvo
        v = est["vivos"].get(eu_id)
        eu = (v["x"], v["y"]) if v else eu0
        d = (est.get("direcao") or {}).get(eu_id) or pl["direcao"]
        if d != pl["direcao"]:
            self.log(f"   [rede] ! o boneco esta olhando para a {'direita' if d > 0 else 'esquerda'}, o alvo esta do outro lado")
            return alvo
        mira = self.lei.angulo(f)
        nova = self.mira.forca_para(eu, alvo_pos, pl["vento"], mira, d, getattr(self, "terreno_rede", None))
        if nova is None:
            return alvo
        if abs(nova - alvo) >= 1.0 or tuple(eu) != tuple(eu0):
            self.log(f"   [rede] forca recalculada na hora: ponteiro em {mira:.0f}, voce em {tuple(eu)}: {alvo:.0f}% -> {nova:.0f}%")
        return nova

    def plano_aviao(self, inst, azul, vida):
        """Destino (x, y) do voo com F, ou None. Usa o aviao quando o chao cedeu (boneco desceu no minimapa), quando o angulo bate
        no limite da arma (terreno inclinado/buraco) ou quando o inimigo esta longe (aproxima). Consome o turno."""
        limite, self.limite_recente = self.limite_recente, False
        if self.turno_rede:
            return None                                      # mira exata pela rede (o aviao usa medidas do minimapa)
        if self.sombra or not azul or self.aviao_indisponivel or self.avioes_na_luta >= MAX_AVIOES_PARTIDA:
            return None
        if self.y_ref is None:
            self.y_ref = azul[1]
        boss = self.rastreador.boss
        if self.tiros_na_partida - self.ultimo_aviao_tiro < INTERVALO_AVIAO_TIROS or not boss:
            return None
        afundou = azul[1] - self.y_ref >= AFUNDOU_PX
        longe = abs(boss[0] - azul[0]) >= LONGE_PX
        if not (afundou or limite or longe):
            return None
        lado = 1 if boss[0] > azul[0] else -1
        passo = min(abs(boss[0] - azul[0]) * 0.4, 28.0)
        self.motivo_aviao = "chao cedeu" if afundou else ("angulo no limite" if limite else "inimigo longe")
        return (azul[0] + lado * passo, azul[1])

    def turno_aviao(self, f, inst, azul, boss, destino, hp0):
        """Tiro de F: o boneco e levado pelo aviao ate onde ele cair (consome o turno; sem itens)."""
        dx, dy = destino[0] - azul[0], azul[1] - destino[1]
        mt = self.mem.melhor_tiro(inst, abs(dx), dy, angulo=50.0)
        if not mt:
            return
        ang, forca, _ch = mt
        self.log(f"[aviao {self.avioes_na_luta + 1}] {self.motivo_aviao}: voce em x={azul[0]:.0f}, y={azul[1]:.0f} -> voando com F para "
                 f"x={destino[0]:.0f}: mirar {ang:.0f} graus, forca {forca:.0f}%")
        fr = [self.reg.frame(f, "turno_inicio")] if self.reg else []
        if self.sombra:
            self.agiu = True
            return
        if hasattr(self.io, "preparar_teclas"):
            self.io.preparar_teclas()
        self.virar_para(1 if dx > 0 else -1)
        self.io.tecla("f", 0.08)
        self.dormir(0.25)
        if not self.ajustar_angulo(ang):
            self.log("   ! [AVIAO] nao consegui ajustar o angulo; pulando o turno.")
            self.agiu = True
            self.devolver_foco()
            return
        angulo_real = self.lei.angulo(self.ver())
        if abs(angulo_real - ang) > 3:
            alt = self.mem.forca_para(inst, azul, (destino[0], destino[1]), angulo_real)
            if alt:
                forca = alt
        forca_real, soltou, trace, segurou = self.carregar(forca)
        self.devolver_foco()
        self.agiu = True
        self.avioes_na_luta += 1
        self.ultimo_aviao_tiro = self.tiros_na_partida
        self.aviao_pendente = {"de": azul}
        self.y_ref = None                              # o boneco vai para outro lugar: nova referencia
        self.rastreador.reiniciar()
        self.log(f"   [AVIAO] tiro dado: {angulo_real:.0f} graus, forca {forca_real:.0f}% (queria {forca:.0f}%)")
        if self.reg:
            fr.append(self.reg.frame(self.ver(), "tiro_dado"))
            self.reg.evento("pvp_aviao", fr, motivo=self.motivo_aviao, de=azul, destino=destino, angulo=round(angulo_real, 1),
                            forca=round(forca_real), vento=self.vento_turno[0])

    # ------------------------------------------------------------------ turno / tiro
    def turno(self, f):
        if self.inicio_partida is None:
            self.inicio_partida = self.agora()
        self.vento_turno = self.ler_vento(f)
        v, conf, votos = self.vento_turno
        self.log(f"   [vento] {'?' if v is None else f'{v:+.1f}'} (confianca {conf:.2f}, {votos} leitura(s) iguais)"
                 f"{'' if v is None or vento_mod.confiavel(conf) else ' - DUVIDOSO: recorte salvo para rotular'}")
        antes = self.turnos
        self.mem.tela_pos = posicoes_na_tela(f) if hasattr(self.mem, "tela_pos") else None
        if self.mem.tela_pos:
            (ax, ay), (rx, ry) = self.mem.tela_pos
            self.log(f"   [tela] voce ({ax:.0f}, {ay:.0f}) inimigo ({rx:.0f}, {ry:.0f}): {abs(rx - ax) / PX_POR_UNID_TELA:.1f} unidades de distancia, "
                     f"{(ay - ry) / PX_POR_UNID_TELA:+.1f} de altura (medido na tela principal)")
        if hasattr(self.mem, "medir_escala"):
            fixou = self.mem.medir_escala(largura_caixa_minimapa(f))
            if fixou:
                self.log(f"   [escala] retangulo do minimapa = {self.mem.larguras[-1]:.0f} px = {UNID_TELA} unidades -> escala do mapa "
                         f"{fixou:.2f} px/unidade (medida, nao chutada)")
                if self.salvar_escala and self.mapa:
                    self.salvar_escala(self.mapa, fixou, True)
        self.hp_inimigo0 = self._ler_barra_inimigo(f)
        self.turnos_feitos_na_vez += 1
        self.ordem = list(ORDENS_PVP[self.tiros_na_partida % len(ORDENS_PVP)])
        self.combo_luta = None                       # o atirador reescolhe a ordem (sem combos): a deste turno
        self.itens_ultimo = []
        self.turno_rede, self.mem.plano_rede, self.mem.forca_rede = None, None, None
        plano = self._plano_pela_rede()
        if plano == "nao_e_a_vez":
            self.turnos_feitos_na_vez -= 1
            return
        self.mem.plano_rede = plano
        try:
            super().turno(f)
        finally:
            if self.pendente is not None and self.turnos > antes:
                self.pendente["tela"] = bool(self.mem.tela_pos)
                if self.turno_rede:
                    eu_id, eu, alvo_id, alvo, plano = self.turno_rede
                    self.pendente["rede"] = dict(t=self._t_plano, eu_id=eu_id, eu=eu, alvo_id=alvo_id, alvo=alvo, plano=plano)
            self.mem.tela_pos = None
            self.turno_rede, self.mem.plano_rede = None, None
        if self.pendente is not None and self.turnos > antes:
            self.pendente["hp_inimigo0"] = self.hp_inimigo0
            self.pendente["vento"] = self.vento_turno
            self.pendente["itens"] = list(self.itens_ultimo)
            self.pendente["quando"] = datetime.datetime.now().isoformat(timespec="seconds")
            self._voo_n, self._voo_t = 0, -99.0

    def passo(self, f=None):
        f = self.ver() if f is None else self.lei.preparar(f)
        if f is not None:
            self._amostrar_voo(f)
            if self.pendente is not None and hasattr(self.lei, "msg_curto"):
                if not self.pendente.get("curto") and self.lei.msg_curto(f):
                    self.pendente["curto"] = True
                if not self.pendente.get("errada") and self.lei.msg_errada(f):
                    self.pendente["errada"] = True
        super().passo(f)

    def _amostrar_voo(self, f):
        p = self.pendente
        if not p or not self.reg:
            return
        dt = self.agora() - p["t"]
        if 0.4 <= dt <= 9.0 and self._voo_n < MAX_PRINTS_VOO and self.agora() - self._voo_t >= INTERVALO_VOO:
            nome = self.reg.frame(f, "voo")
            p.setdefault("voo", []).append(nome)
            self._voo_n += 1
            self._voo_t = self.agora()

    def _ler_barra_inimigo(self, f, n=3):
        """Mediana de n leituras da barra de vida do inimigo (o JPEG/anti-alias varia +-2 px)."""
        ler = getattr(self.lei, "vida_inimigo", None)
        if ler is None:
            return None
        vals = [ler(f)] if f is not None else []
        for _ in range(n - 1):
            self.dormir(0.1)
            g = self.ver()
            if g is not None:
                vals.append(ler(g))
        vals = [v for v in vals if v > 0]
        return float(np.median(vals)) if vals else None

    def concluir_tiro(self, f):
        """Resultado do tiro pela barra de vida do inimigo (encolheu >= QUEDA_BARRA_PX = acerto). Acerto trava a escala do mapa; erro
        passa para a proxima da busca (MULT_ESCALA)."""
        p, self.pendente = self.pendente, None
        if p is None:
            return
        hp0, hp1 = p.get("hp_inimigo0"), self._ler_barra_inimigo(f)
        acertou = None if hp0 is None or hp1 is None else (hp0 - hp1) >= QUEDA_BARRA_PX
        res_rede = self._resultado_pela_rede(p)
        if res_rede is not None:
            p["rede_resultado"] = res_rede
            acertou = res_rede["acertou"]                    # a rede sabe com certeza (dano no alvo)
        esc_usada = getattr(self.mem, "escala", None)
        if res_rede is not None:
            pass                                             # resultado exato ja registrado pela rede (a barra/escala nao valem aqui)
        elif acertou is not None and hasattr(self.mem, "resultado") and p.get("tela"):
            self.log(f"   [resultado] barra do inimigo {hp0:.0f} -> {hp1:.0f} px: {'ACERTOU' if acertou else 'ERROU'} (tiro medido na tela principal)")
        elif acertou is not None and hasattr(self.mem, "resultado") and p.get("azul") and p.get("boss") and float(p.get("forca") or 0) >= 10:      # sem posicao no minimapa o tiro foi no padrao: nao diz nada da escala
            esc, ok = self.mem.resultado(acertou, curto=bool(p.get("curto")), errada=bool(p.get("errada")))
            self.log(f"   [resultado] barra do inimigo {hp0:.0f} -> {hp1:.0f} px: {'ACERTOU' if acertou else 'ERROU'}"
                     f"{' (o jogo avisou: tiro CURTO)' if p.get('curto') else ''}"
                     f"{' (o jogo avisou: DIRECAO ERRADA -> angulo ' + format(self.mem.angulo, '.0f') + ')' if p.get('errada') else ''}; escala do mapa "
                     f"{esc_usada:.2f} -> {esc:.2f}{' (travada)' if ok else ''}")
            if self.salvar_escala and self.mapa:
                self.salvar_escala(self.mapa, esc_usada if acertou else esc, ok)
        p["acertou"], p["escala"] = acertou, esc_usada
        if p.get("curto") and acertou is None:
            self.log("   [resultado] o jogo avisou: tiro CURTO (sem leitura da barra do inimigo)")
        pos = self.reg.frame(f, "pos_tiro") if (self.reg and f is not None) else None
        self.tiros_na_partida += 1
        v, conf, votos = p.get("vento", (None, 0.0, 0))
        linha = {"quando": p.get("quando"), "sessao": getattr(self.reg, "pasta", None) and os.path.basename(self.reg.pasta),
                 "partida": self.partidas + 1, "mapa": self.mapa, "tiro": self.tiros_na_partida, "angulo": round(float(p["angulo"]), 1),
                 "forca": round(float(p["forca"]), 1), "vento": v, "vento_conf": round(conf, 2), "vento_votos": votos,
                 "itens": p.get("itens", []), "azul": p.get("azul"), "boss": p.get("boss"), "voo": p.get("voo", []), "pos_tiro": pos,
                 "origem_previsao": None, "acertou": p.get("acertou"), "escala": p.get("escala"),
                 "barra_inimigo": [p.get("hp_inimigo0"), hp1], "rede": p.get("rede"), "rede_resultado": p.get("rede_resultado")}
        self.log(f"   [tentativa {self.partidas + 1}.{self.tiros_na_partida}] {linha['angulo']:.0f} graus, forca {linha['forca']:.0f}%, "
                 f"vento {'?' if v is None else f'{v:+.1f}'}, voce {p.get('azul')} inimigo {p.get('boss')} (resultado: ver os prints)")
        try:
            os.makedirs(os.path.dirname(self.arq_tentativas), exist_ok=True)
            with open(self.arq_tentativas, "a", encoding="utf-8") as fh:
                fh.write(json.dumps(linha, ensure_ascii=False, default=float) + "\n")
        except OSError as e:
            self.log(f"   ! nao consegui gravar a tentativa: {e}")
        if self.reg:
            self.reg.evento("pvp_tiro", [pos] + list(p.get("voo", [])), **{k: v_ for k, v_ in linha.items() if k not in ("voo", "pos_tiro")})

    def fim_da_partida(self, f=None):
        """A batalha acabou: fecha o tiro pendente (so grava) e zera o estado para a proxima partida."""
        if self.pendente is not None:
            self.concluir_tiro(f)
        dur = None if self.inicio_partida is None else self.agora() - self.inicio_partida
        self.partidas += 1
        self.log(f"=== partida {self.partidas} acabou: {self.tiros_na_partida} tiro(s), {0 if dur is None else dur:.0f}s ===")
        if self.reg:
            self.reg.evento("partida", [self.reg.frame(f, "partida_fim")] if f is not None else [], numero=self.partidas, mapa=self.mapa,
                            tiros=self.tiros_na_partida, duracao_s=None if dur is None else round(dur, 1))
        self.tiros_na_partida, self.inicio_partida = 0, None
        self.y_ref, self.limite_recente, self.ultimo_aviao_tiro = None, False, -99
        self.mira.reiniciar()
        self.fim_da_batalha(venceu=False)             # zera rastreador/estado (venceu=False: nao registra acerto)


# ------------------------------------------------------------------------------------------------------ laco principal
class Laco:
    def __init__(self, io, det, atirador, log=print, clicar_inicio=True, agora=None, dormir=None, catalogo=None, reg=None):
        self.io, self.det, self.at, self.log = io, det, atirador, log
        self.clicar_inicio = clicar_inicio
        self.catalogo, self.reg = catalogo, reg
        self.agora = agora or time.time
        self.dormir = dormir or time.sleep
        self.em_batalha = False
        self.fora_desde = None
        self.ultimo_inicio = -1e9
        self.buscando_desde = None
        self.ultimo_aviso = 0.0
        self.ultimo_estado = None
        self.ultima_vez = None
        self.ultimo_batimento = 0.0
        self.melhor_mapa = None            # (contraste, quadro) da tela VS (o fade-in deixa os primeiros quadros escuros)
        self.parar = False
        self.nota_pass = 0.0
        self.contador = False
        self.vez_desde = None              # quando o PASS apareceu (None = sem PASS)
        self.vezes_curtas = 0
        self.ultimo_quadro_diag = -1e9
        self.quadros_diag = 0
        self.desconhecida_desde = None
        self.ultimo_preso = -1e9

    def _guardar_mapa(self, f):
        c = contraste_mapa(f)
        if self.melhor_mapa is None or c > self.melhor_mapa[0]:
            self.melhor_mapa = (c, f.copy())

    def _fechar_mapa(self):
        """Saiu da tela VS: identifica o mapa pelo melhor quadro e avisa o atirador."""
        if self.melhor_mapa is None:
            return
        _c, f = self.melhor_mapa
        self.melhor_mapa = None
        if self.catalogo is None:
            return
        mid, novo, vistas = self.catalogo.identificar(f)
        self.at.mapa = mid
        if hasattr(getattr(self.at, "mem", None), "escala"):
            self.at.mem.novo_mapa(self.catalogo.escala(mid), self.catalogo.escala_travada(mid))
            self.at.salvar_escala = self.catalogo.definir_escala
        self.log(f"(mapa {mid}: {'NOVO, miniatura guardada em dados/pvp_mapas' if novo else f'ja visto {vistas}x'})")
        if self.reg:
            self.reg.evento("mapa", [self.reg.frame(f, "mapa")], mapa=mid, novo=novo, vistas=vistas)

    def _diag(self, f, rotulo, **dados):
        """Print de diagnostico (limitado): mostra o que o jogo esta mostrando quando algo estranho acontece."""
        if not self.reg or f is None or self.quadros_diag >= MAX_QUADROS_DIAG:
            return
        self.quadros_diag += 1
        self.reg.evento("pvp_diag", [self.reg.frame(f, rotulo)], motivo=rotulo, **dados)

    def _acompanhar_vez(self, f, vez, agora):
        """Mede quanto tempo a sua vez dura: PASS que so pisca (<2 s) nao da para jogar - guarda print e avisa se repetir."""
        if vez and self.vez_desde is None:
            self.vez_desde = agora
            if agora - self.ultimo_quadro_diag >= 5.0:
                self.ultimo_quadro_diag = agora
                self._diag(f, "vez", nota_pass=round(self.nota_pass, 2), contador=self.contador)
        elif not vez and self.vez_desde is not None:
            dur = agora - self.vez_desde
            self.vez_desde = None
            if dur < VEZ_CURTA_S and self.at.turnos_feitos_na_vez == 0:
                self.vezes_curtas += 1
                self.log(f"(a sua vez durou so {dur:.1f} s e o bot nao chegou a agir ({self.vezes_curtas} seguida(s)))")
                if self.vezes_curtas >= VEZES_CURTAS_ALERTA:
                    self.log("ALERTA: varias vezes seguidas que acabam na hora. Seu boneco pode estar congelado/morto/sem turno. Veja o jogo.")
                    self._diag(f, "vez", alerta=True, vezes_curtas=self.vezes_curtas)
                    self.vezes_curtas = 0
            else:
                self.vezes_curtas = 0
            self.at.turnos_feitos_na_vez = 0

    def passo(self):
        img = self.io.capturar()
        if img is None:
            return
        f = em_1280(img)
        achadas = self.det.detectar(estados_mod.normalizar(f))
        estado = achadas[0] if achadas else None
        nota = pontuacao_pass(f)
        lei = getattr(self.at, "lei", None)
        self.contador = contador_da_vez(f)
        vez = bool(lei.minha_vez(f)) if lei is not None else nota >= PASS_LIMIAR_PVP     # com histerese (ver LeitorPvp)
        self.nota_pass = nota
        agora = self.agora()
        if estado != self.ultimo_estado:
            self.log(f"(tela: {estado or 'desconhecida'})")
            self.ultimo_estado = estado
        if estado == "VS_PVP":
            self._guardar_mapa(f)
            return
        self._fechar_mapa()
        if estado == "BATALHA" or vez:
            self.desconhecida_desde = None
            self._acompanhar_vez(f, vez, agora)
            if self.em_batalha and agora - self.ultimo_quadro_diag >= BATIMENTO_QUADRO_S and not vez:
                self.ultimo_quadro_diag = agora
                self._diag(f, "batalha", tiros=self.at.tiros_na_partida, nota_pass=round(nota, 2))
            if not self.em_batalha:
                self.log("(partida comecou)")
                self.ultima_vez = None
            self.em_batalha, self.fora_desde = True, None
            if vez != self.ultima_vez:
                self.log(f"(SUA VEZ; PASS {nota:.2f}, contador {'sim' if self.contador else 'nao'})" if vez else f"(vez do adversario: espero; PASS {nota:.2f})")
                self.ultima_vez = vez
            if agora - self.ultimo_batimento >= BATIMENTO_S:
                self.ultimo_batimento = agora
                self.log(f"(em batalha: {'sua vez' if vez else 'vez do adversario'}; PASS {nota:.2f}; tiros nesta partida: {self.at.tiros_na_partida})")
            self.at.passo(f)
            return
        if self.em_batalha:
            if self.fora_desde is None:
                self.fora_desde = agora
            elif agora - self.fora_desde >= SAIDA_BATALHA_S:
                self.at.fim_da_partida(f)
                self.em_batalha = False
        if estado in (None, "TAREFA") and not self.em_batalha:
            if self.desconhecida_desde is None:
                self.desconhecida_desde = agora
            elif agora - self.desconhecida_desde >= PRESO_S and agora - self.ultimo_preso >= PRESO_S:
                self.ultimo_preso = agora
                self.log(f"ALERTA: ha {(agora - self.desconhecida_desde):.0f} s em tela desconhecida fora da batalha; clicando numa area neutra")
                self._diag(f, "preso")
                self.io.clicar_ref(*FOCO_PONTO_PADRAO)
        else:
            self.desconhecida_desde = None
        if estado == "CLIQUE_JOGO":
            por_baixo = next((e for e in achadas if e != "CLIQUE_JOGO"), None)
            self.io.clicar_ref(*FOCO_PONTO_NEUTRO.get(por_baixo, FOCO_PONTO_PADRAO))
            self.dormir(1.0)
        elif estado == "SALA" and self.clicar_inicio:
            if sala_livre(f):
                self.buscando_desde = None
                if agora - self.ultimo_inicio >= INTERVALO_INICIO:
                    self.ultimo_inicio = agora
                    self.log("(sala: clicando em Inicio para buscar partida)")
                    self.io.clicar_ref(*SALA_INICIO)
                    self.dormir(2.0)
            elif sala_buscando(f):
                if self.buscando_desde is None:
                    self.buscando_desde, self.ultimo_aviso = agora, agora
                    self.log("(buscando partida: o botao virou Cancele - NAO clico; espero achar)")
                elif agora - self.buscando_desde >= LIMITE_BUSCA_S:
                    self.log("ALERTA: busca de partida parada ha mais de 10 min: cancelo e busco de novo")
                    self.io.clicar_ref(*SALA_INICIO)
                    self.buscando_desde, self.ultimo_inicio = None, agora
                    self.dormir(2.0)
                elif agora - self.ultimo_aviso >= AVISO_BUSCA:
                    self.ultimo_aviso = agora
                    self.log(f"(ainda buscando partida ha {(agora - self.buscando_desde) / 60:.0f} min; continuo esperando)")

    def rodar(self, ate=None, arquivo_parar=ARQUIVO_PARAR):
        while not self.parar:
            if ate is not None and self.agora() >= ate:
                self.log("tempo acabou.")
                break
            if arquivo_parar and os.path.exists(arquivo_parar):
                try:
                    os.remove(arquivo_parar)
                except OSError:
                    pass
                self.log("Parada pedida pelo painel.")
                break
            if hasattr(self.io, "tecla_apertada") and self.io.tecla_apertada(VK_F10):
                self.log("F10: parando.")
                break
            try:
                self.passo()
            except KeyboardInterrupt:
                raise
            except Exception as e:                       # uma falha inesperada NAO derruba uma gravacao de 1 hora
                import traceback
                agora = self.agora()
                self.erros = [t for t in getattr(self, "erros", []) if agora - t < 600] + [agora]
                self.log(f"[ERRO] {type(e).__name__}: {e} ({len(self.erros)} nos ultimos 10 min)")
                self.log(traceback.format_exc().strip().splitlines()[-3])
                if len(self.erros) >= 12:
                    self.log("Muitos erros seguidos: parando.")
                    break
                self.dormir(1.0)
            self.dormir(0.25)


def main():
    import janela
    ap = argparse.ArgumentParser(description="DDTank - PVP: joga e grava as tentativas")
    ap.add_argument("--titulo", default="")
    ap.add_argument("--exe", default="")
    ap.add_argument("--minutos", type=float, default=60.0, help="para sozinho depois desse tempo (padrao 60; 0 = sem limite)")
    ap.add_argument("--sem-inicio", action="store_true", help="nao clica em Inicio na sala (voce inicia as partidas)")
    ap.add_argument("--sombra", action="store_true", help="so mostra o tiro que faria (nao aperta teclas) e grava os prints")
    ap.add_argument("--foco", type=int, choices=(0, 1, 2), default=1)
    ap.add_argument("--sem-calibrar", action="store_true")
    ap.add_argument("--sem-rede", action="store_true", help="nao le a rede do jogo (mira so pela tela, como antes)")
    args = ap.parse_args()
    if not instancia_unica():
        sys.exit("ERRO: ja existe um bot (navegador/atirador) rodando. Feche os outros antes.")
    titulo, exe = args.titulo or config.TITULO_JANELA, args.exe or config.EXE_JANELA
    hwnd = janela.resolver_janela(titulo, exe)
    if not hwnd:
        sys.exit("Janela do jogo nao encontrada. Rode LISTAR_JANELAS.bat.")
    if janela.contar_janelas(titulo, exe) > 1:
        sys.exit("ERRO: ha mais de uma janela do jogo aberta. Deixe so uma.")
    io = IOJanela(hwnd, calibrar=not args.sem_calibrar)
    io.foco_nivel = args.foco
    det = estados_mod.Detector()
    evitar_suspensao()
    os.makedirs(config.PASTA_LOGS, exist_ok=True)
    arq = open(os.path.join(config.PASTA_LOGS, f"pvp_{datetime.datetime.now():%Y%m%d}.log"), "a", encoding="utf-8")

    def log(msg):
        linha = f"[{datetime.datetime.now():%H:%M:%S}] {msg}"
        print(linha, flush=True)
        arq.write(linha + "\n")
        arq.flush()
    io.log = log
    reg = RegistroPvp("pvp")
    log(f"PVP: gravando em {reg.pasta} e em {ARQ_TENTATIVAS}. Janela: {janela.descrever_janela(hwnd)}")
    rede = None
    if not args.sem_rede:
        caminho = rede_vivo.registro_do_jogo_aberto()
        if caminho:
            rede = rede_vivo.LeitorAoVivo(fonte=lambda parar: rede_vivo.fonte_netlog(caminho, parar), log=log).iniciar()
            log(f"[rede] lendo a rede do jogo ({os.path.basename(caminho)}): mira EXATA (posicoes, vento e resultado de cada tiro)")
        else:
            log("[rede] o jogo NAO foi aberto com o registro de rede: mira so pela tela. Para a mira exata, feche o jogo e abra pelo "
                "ABRIR_JOGO.bat (ou TESTAR_REDE.bat) antes do PVP.bat.")
    at = AtiradorPvp(io, MemoriaPvp(), lambda: INSTANCIA, sombra=args.sombra, log=log, reg=reg, rede=rede)
    laco = Laco(io, det, at, log=log, clicar_inicio=not args.sem_inicio, catalogo=CatalogoMapas(), reg=reg)
    ate = time.time() + args.minutos * 60 if args.minutos else None
    try:
        laco.rodar(ate=ate)
    except KeyboardInterrupt:
        log("Parado pelo usuario.")
    finally:
        if laco.em_batalha:
            at.fim_da_partida()
        log(f"PVP: {at.partidas} partida(s) gravadas; recortes de vento duvidosos salvos: {at.vento_duvidoso_salvos}.")
        reg.fechar()
        print(f"Gravacao salva em {reg.pasta}. Para me mandar: botao 'Enviar gravacao' do painel (ou EMPACOTAR_E_ENVIAR.bat); "
              f"(os dados de cada tiro e os prints vao dentro dela; dados\\pvp_tentativas.jsonl fica so no seu disco).")


if __name__ == "__main__":
    main()
