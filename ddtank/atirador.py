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
ESPERA_VEZ = 0.35             # s com o PASS visivel antes de agir (o jogo aceita teclas durante a faixa "Sua vez!")
DURACAO_MAX_DA_VEZ = 11.0     # s: se o PASS nunca some, considera que comecou outro turno
INTERVALO_LEITURA = 1.0       # s entre leituras gravadas no registro (diagnostico)
TOLERANCIA_ANGULO = 3.0       # graus
TAXA_ANGULO_INICIAL = 28.0    # graus/s com a seta apertada (aprende sozinho)
FORCA_POR_SEGUNDO = 38.0      # % da barra por segundo segurando espaco (medido nas gravacoes)
ANTECIPACAO_INICIAL = 4.0     # % de folga: solta um pouco antes (atraso da captura + do KEYUP)
MAX_SEGURANDO = 4.0           # s: trava de seguranca
MARGEM_TEMPO_MINIMO = 0.35    # s: tolerancia da trava de tempo minimo


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
                 ordem_itens=None, reg=None):
        """io: capturar(), tecla_baixo(nome, repeticao), tecla_cima(nome), tecla(nome, dur), trocar_modo().
        instancia: funcao que devolve 'FANTASMA' | 'PROFUNDEZAS' | 'MINHOCAO'."""
        import time
        self.io, self.mem, self.instancia = io, memoria, instancia
        self.lei = leitor or LeitorReal()
        self.sombra, self.log, self.reg = sombra, log, reg
        self.ultima_leitura = -99.0
        self.acao_em = None
        self.turno_abortado = False
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
        agora = self.agora()
        if self.reg and agora - self.ultima_leitura >= INTERVALO_LEITURA:
            self.ultima_leitura = agora
            self.reg.evento("leitura", [self.reg.frame(f, "leitura")], vez=bool(vez), agiu=self.agiu,
                            angulo=round(self.lei.angulo(f), 1), forca=round(self.lei.forca(f)), vida=round(self.lei.vida(f)),
                            itens=self.lei.itens(f))
        if not vez:
            if self.pendente and not self.agiu_recentemente():
                self.concluir_tiro(f)
            self.vez_desde, self.agiu = None, False
            return
        if self.pendente and agora - self.pendente["t"] > 7:
            self.concluir_tiro(f)
        if self.agiu:
            # o PASS nunca sumiu entre dois turnos (ex.: o boss nao joga): depois de uma vez inteira, e outro turno
            if self.acao_em is not None and agora - self.acao_em > DURACAO_MAX_DA_VEZ:
                self.log("   (o PASS continua visivel ha muito tempo: tratando como um novo turno)")
                self.agiu, self.vez_desde = False, None
            else:
                return
        if self.vez_desde is None:
            self.vez_desde = agora
        if agora - self.vez_desde < ESPERA_VEZ:
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
    def vez_ativa(self):
        f = self.ver()
        return f is not None and self.lei.minha_vez(f)

    def turno(self, f):
        self.turnos += 1
        inicio = self.agora()
        self.acao_em = inicio
        self.turno_abortado = False
        inst = self.instancia()
        azul, boss = self.lei.pontos(f)
        for _ in range(3):
            if azul and boss:
                break
            self.dormir(0.1)
            g = self.ver()
            if g is not None:
                azul, boss = self.lei.pontos(g)
        pred = self.mem.prever(inst, azul, boss)
        hp0 = self.lei.vida(f)
        itens0 = self.lei.itens(f)
        self.log(f"[tiro {self.turnos}] {inst}: voce {azul and tuple(round(v) for v in azul)}, boss {boss and tuple(round(v) for v in boss)}"
                 f" -> mirar {pred['angulo']:.0f} graus, forca {pred['forca']:.0f}% ({pred['origem']}: {pred['detalhe']})")
        fr = [self.reg.frame(f, "turno_inicio")] if self.reg else []
        if self.sombra:
            self.agiu = True
            self.log("   [sombra] nao apertei nada.")
            if self.reg:
                self.reg.evento("turno_sombra", fr, inst=inst, azul=azul, boss=boss, previsto=pred, itens_coloridos=itens0)
            return
        ok_ang = self.ajustar_angulo(pred["angulo"])
        t_ang = self.agora() - inicio
        if self.reg:
            fr.append(self.reg.frame(self.ver(), "apos_angulo"))
        if not ok_ang:
            self.log("   ! nao consegui ajustar o angulo (as setas nao estao chegando ao jogo? ou a vez acabou). Pulando o tiro.")
            self.agiu = True
            if self.reg:
                self.reg.evento("turno_pulado", fr, inst=inst, motivo="angulo", previsto=pred, tempo_s=round(t_ang, 2))
            return
        apertados = self.aplicar_itens()
        t_itens = self.agora() - inicio
        if self.reg:
            fr.append(self.reg.frame(self.ver(), "apos_itens"))
        angulo_real = self.lei.angulo(self.ver())
        alvo_forca = pred["forca"]
        if abs(angulo_real - pred["angulo"]) > 3:
            alt = self.mem.forca_para(inst, azul, boss, angulo_real)
            if alt:
                self.log(f"   angulo ficou em {angulo_real:.0f} (queria {pred['angulo']:.0f}): forca recalculada {pred['forca']:.0f}% -> {alt:.0f}%")
                alvo_forca = alt
        forca_real, soltou = self.carregar(alvo_forca)
        t_tiro = self.agora() - inicio
        self.agiu = True
        self.pendente = {"t": self.agora(), "inst": inst, "azul": azul, "boss": boss, "angulo": angulo_real,
                         "forca": forca_real, "hp0": hp0}
        self.log(f"   tiro dado: {angulo_real:.0f} graus, forca {forca_real:.0f}% (queria {alvo_forca:.0f}%); "
                 f"tempo: angulo {t_ang:.1f}s, itens {t_itens - t_ang:.1f}s, carga {t_tiro - t_itens:.1f}s (total {t_tiro:.1f}s)")
        if self.reg:
            fr.append(self.reg.frame(self.ver(), "tiro_dado"))
            self.reg.evento("turno", fr, inst=inst, azul=azul, boss=boss, previsto=pred, angulo_real=round(angulo_real, 1),
                            forca_real=round(forca_real), itens=apertados, itens_coloridos_inicio=itens0, soltou=soltou,
                            tempos={"angulo": round(t_ang, 2), "itens": round(t_itens - t_ang, 2), "carga": round(t_tiro - t_itens, 2)})

    # ------------------------------------------------------------------ angulo
    def ajustar_angulo(self, alvo):
        sem_efeito = 0
        for _ in range(12):
            f = self.ver()
            if f is None or not self.lei.minha_vez(f):
                return False
            a = self.lei.angulo(f)
            erro = alvo - a
            if abs(erro) <= TOLERANCIA_ANGULO:
                return True
            dur = float(np.clip(abs(erro) / self.taxa_angulo * 0.85, 0.05, 0.6))
            tecla = "cima" if erro > 0 else "baixo"
            self.io.tecla(tecla, dur)
            self.dormir(0.1)
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
            if not self.lei.minha_vez(f):
                break
            ativos = self.lei.itens(f)
            if not any(ativos):
                break
            if not ativos[item - 1]:
                continue
            self.io.tecla(str(item), 0.08)
            usados[item] = usados.get(item, 0) + 1
            apertados.append(item)
            self.dormir(0.12)
        self.log(f"   itens: {apertados or 'nenhum (sem stamina?)'}")
        return apertados

    # ------------------------------------------------------------------ forca
    def carregar(self, alvo):
        """Segura ESPACO olhando a barra; solta ao chegar em (alvo - antecipacao) ou se a vez acabar.
        Trava de seguranca: a barra sobe ~38%/s, entao NUNCA solta antes do tempo minimo para o alvo - assim uma
        barra ainda mostrando o tiro anterior nao faz o bot soltar de cara (forca 10 quando era preciso 40).
        Devolve (forca final lida, motivo da soltura)."""
        quer = max(0.0, alvo - self.antecipacao)
        minimo = max(0.0, quer / FORCA_POR_SEGUNDO - MARGEM_TEMPO_MINIMO)
        limite = min(MAX_SEGURANDO, alvo / FORCA_POR_SEGUNDO + 1.0)
        rep = 1
        self.io.tecla_baixo(TECLA_ESPACO, rep)
        t0 = self.agora()
        v, motivo = 0.0, "tempo"
        while self.agora() - t0 < limite:
            f = self.ver()
            dur = self.agora() - t0
            if f is not None:
                if not self.lei.minha_vez(f):
                    motivo = "vez_acabou"
                    break
                v = self.lei.forca(f)
                if v >= quer and dur >= minimo:
                    motivo = "alvo"
                    break
            rep += 1
            self.io.tecla_baixo(TECLA_ESPACO, rep)
        self.io.tecla_cima(TECLA_ESPACO)
        self.dormir(0.25)
        final = self.lei.forca(self.ver())
        if final > 0 and motivo == "alvo":
            sobra = final - alvo
            self.antecipacao = float(np.clip(self.antecipacao + 0.5 * sobra, 0.0, 12.0))   # corrige o atraso
        return (final if final > 0 else v), motivo

    # ------------------------------------------------------------------ resultado
    def concluir_tiro(self, f):
        p, self.pendente = self.pendente, None
        hp1 = self.lei.vida(f)
        acertou = hp1 < p["hp0"] - 3
        self.log(f"   [tiro] vida do boss {p['hp0']:.0f}% -> {hp1:.0f}%: {'ACERTOU' if acertou else 'ERROU'}")
        self.mem.registrar(p["inst"], p["azul"], p["boss"], p["angulo"], p["forca"], acertou, origem="bot")
