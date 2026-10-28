# -*- coding: utf-8 -*-
"""
Atirador (fase 3): joga o turno na batalha.

Fluxo de cada turno (o botao PASS so aparece na SUA vez; dura ~8 s):
  1. decide o tiro: memoria.prever(instancia, posicao no minimapa) -> angulo e forca
  2. ajusta o angulo (setas cima/baixo em toques curtos, lendo o ponteiro)
  3. aperta os itens na ordem ORDEM_ITENS, so os que estao coloridos (ha stamina)
  4. segura ESPACO olhando a barra de forca e solta no alvo
  5. depois que o tiro cai, compara a vida do boss e APRENDE (acertou/errou)

Modo sombra (sombra=True): faz tudo menos apertar teclas; so registra o que faria.
"""
import numpy as np

import leitura as L
from navegador import em_1280

# ordem de preferencia dos itens (1..8). Repetir um numero = tentar de novo (potencializadores 4..8 podem repetir).
# Limites por turno (regras do servidor): item 1 e 3 ate 2x, item 2 ate 1x.
ORDEM_ITENS = [2, 3, 4, 4, 4, 4, 5, 6, 7, 8]
LIMITE_POR_TURNO = {1: 2, 2: 1, 3: 2}
TECLA_ESPACO = "espaco"
ESPERA_VEZ = 0.9              # s com o PASS visivel antes de agir (a faixa "Sua vez!" ainda anima)
TOLERANCIA_ANGULO = 2.5       # graus
TAXA_ANGULO_INICIAL = 28.0    # graus/s com a seta apertada (aprende sozinho)
FORCA_POR_SEGUNDO = 38.0      # % da barra por segundo segurando espaco (medido nas gravacoes)
ANTECIPACAO_INICIAL = 4.0     # % de folga: solta um pouco antes (atraso da captura + do KEYUP)
MAX_SEGURANDO = 4.0           # s: trava de seguranca


class LeitorReal:
    """Transforma o quadro da janela (qualquer tamanho) nas leituras numericas."""
    def preparar(self, img): return em_1280(img)
    minha_vez = staticmethod(L.minha_vez)
    angulo = staticmethod(L.angulo)
    forca = staticmethod(L.forca)
    pontos = staticmethod(L.pontos_minimapa)
    itens = staticmethod(L.itens_ativos)
    vida = staticmethod(L.vida_boss)


class Atirador:
    def __init__(self, io, memoria, instancia, leitor=None, sombra=False, dormir=None, agora=None, log=print,
                 ordem_itens=None):
        """io: capturar(), tecla_baixo(nome, repeticao), tecla_cima(nome), tecla(nome, dur), trocar_modo().
        instancia: funcao que devolve 'FANTASMA' | 'PROFUNDEZAS' | 'MINHOCAO'."""
        import time
        self.io, self.mem, self.instancia = io, memoria, instancia
        self.lei = leitor or LeitorReal()
        self.sombra, self.log = sombra, log
        self.dormir = dormir or time.sleep
        self.agora = agora or time.time
        self.ordem = ordem_itens or list(ORDEM_ITENS)
        self.taxa_angulo = TAXA_ANGULO_INICIAL
        self.antecipacao = ANTECIPACAO_INICIAL
        self.vez_desde = None
        self.agiu = False
        self.pendente = None
        self.turnos = 0
        self.falhas_tecla = 0

    # ------------------------------------------------------------------ leitura
    def ver(self):
        img = self.io.capturar()
        return None if img is None else self.lei.preparar(img)

    # ------------------------------------------------------------------ laco (chamado varias vezes por segundo)
    def passo(self, f=None):
        f = self.lei.preparar(f) if f is not None else self.ver()
        if f is None:
            return
        vez = self.lei.minha_vez(f)
        if not vez:
            if self.pendente and not self.agiu_recentemente():
                self.concluir_tiro(f)
            self.vez_desde, self.agiu = None, False
            return
        if self.pendente and self.agora() - self.pendente["t"] > 7:
            self.concluir_tiro(f)
        if self.agiu:
            return
        if self.vez_desde is None:
            self.vez_desde = self.agora()
        if self.agora() - self.vez_desde < ESPERA_VEZ:
            return
        self.turno(f)

    def agiu_recentemente(self):
        return self.pendente is not None and self.agora() - self.pendente["t"] < 2.0

    def fim_da_batalha(self):
        """O navegador avisa que saimos da batalha: se havia um tiro pendente, o boss morreu."""
        if self.pendente:
            p = self.pendente
            self.log(f"   [tiro] boss derrotado -> ACERTOU ({p['angulo']:.0f} graus, {p['forca']:.0f}%)")
            self.mem.registrar(p["inst"], p["azul"], p["boss"], p["angulo"], p["forca"], True, origem="bot")
            self.pendente = None
        self.vez_desde, self.agiu = None, False

    # ------------------------------------------------------------------ um turno
    def turno(self, f):
        self.turnos += 1
        inst = self.instancia()
        azul, boss = self.lei.pontos(f)
        for _ in range(3):
            if azul and boss:
                break
            self.dormir(0.15)
            g = self.ver()
            if g is not None:
                azul, boss = self.lei.pontos(g)
        pred = self.mem.prever(inst, azul, boss)
        hp0 = self.lei.vida(f)
        self.log(f"[tiro {self.turnos}] {inst}: voce {azul and tuple(round(v) for v in azul)}, boss {boss and tuple(round(v) for v in boss)}"
                 f" -> mirar {pred['angulo']:.0f} graus, forca {pred['forca']:.0f}% ({pred['origem']}: {pred['detalhe']})")
        if self.sombra:
            self.agiu = True
            self.log("   [sombra] nao apertei nada.")
            return
        if not self.ajustar_angulo(pred["angulo"]):
            self.log("   ! nao consegui ajustar o angulo (as setas nao estao chegando ao jogo?). Pulando o tiro.")
            self.agiu = True
            return
        self.aplicar_itens()
        angulo_real = self.lei.angulo(self.ver())
        forca_real = self.carregar(pred["forca"])
        self.agiu = True
        self.pendente = {"t": self.agora(), "inst": inst, "azul": azul, "boss": boss, "angulo": angulo_real,
                         "forca": forca_real, "hp0": hp0}
        self.log(f"   tiro dado: {angulo_real:.0f} graus, forca {forca_real:.0f}% (queria {pred['forca']:.0f}%)")

    # ------------------------------------------------------------------ angulo
    def ajustar_angulo(self, alvo):
        sem_efeito = 0
        for _ in range(12):
            f = self.ver()
            if f is None:
                return False
            a = self.lei.angulo(f)
            erro = alvo - a
            if abs(erro) <= TOLERANCIA_ANGULO:
                return True
            dur = float(np.clip(abs(erro) / self.taxa_angulo * 0.85, 0.05, 0.6))
            tecla = "cima" if erro > 0 else "baixo"
            self.io.tecla(tecla, dur)
            self.dormir(0.18)
            b = self.lei.angulo(self.ver())
            mudou = b - a
            if abs(mudou) < 0.8:
                sem_efeito += 1
                if sem_efeito == 2 and hasattr(self.io, "trocar_modo"):
                    self.log("   ! as setas nao mudaram o angulo; tentando outro modo de entrada.")
                    self.io.trocar_modo()
                if sem_efeito >= 4:
                    return False
            else:
                sem_efeito = 0
                taxa = abs(mudou) / dur
                if 5 < taxa < 120 and mudou * erro > 0:       # aprende a velocidade do angulo
                    self.taxa_angulo = 0.6 * self.taxa_angulo + 0.4 * taxa
        return abs(alvo - self.lei.angulo(self.ver())) <= TOLERANCIA_ANGULO * 2

    # ------------------------------------------------------------------ itens
    def aplicar_itens(self):
        usados = {}
        apertados = []
        for item in self.ordem:
            if usados.get(item, 0) >= LIMITE_POR_TURNO.get(item, 99):
                continue
            f = self.ver()
            if f is None:
                break
            ativos = self.lei.itens(f)
            if not any(ativos):
                break
            if not ativos[item - 1]:
                continue
            self.io.tecla(str(item), 0.08)
            usados[item] = usados.get(item, 0) + 1
            apertados.append(item)
            self.dormir(0.3)
        self.log(f"   itens: {apertados or 'nenhum (sem stamina?)'}")

    # ------------------------------------------------------------------ forca
    def carregar(self, alvo):
        """Segura ESPACO olhando a barra; solta ao chegar em (alvo - antecipacao). Devolve a forca final lida."""
        limite = min(MAX_SEGURANDO, alvo / FORCA_POR_SEGUNDO + 1.0)
        rep = 1
        self.io.tecla_baixo(TECLA_ESPACO, rep)
        t0 = self.agora()
        v = 0.0
        while self.agora() - t0 < limite:
            f = self.ver()
            if f is not None:
                v = self.lei.forca(f)
                if v >= alvo - self.antecipacao:
                    break
            rep += 1
            self.io.tecla_baixo(TECLA_ESPACO, rep)
        self.io.tecla_cima(TECLA_ESPACO)
        self.dormir(0.25)
        final = self.lei.forca(self.ver())
        if final > 0:
            sobra = final - alvo
            self.antecipacao = float(np.clip(self.antecipacao + 0.5 * sobra, 0.0, 12.0))   # corrige o atraso
        return final if final > 0 else v

    # ------------------------------------------------------------------ resultado
    def concluir_tiro(self, f):
        p, self.pendente = self.pendente, None
        hp1 = self.lei.vida(f)
        acertou = hp1 < p["hp0"] - 3
        self.log(f"   [tiro] vida do boss {p['hp0']:.0f}% -> {hp1:.0f}%: {'ACERTOU' if acertou else 'ERROU'}")
        self.mem.registrar(p["inst"], p["azul"], p["boss"], p["angulo"], p["forca"], acertou, origem="bot")
