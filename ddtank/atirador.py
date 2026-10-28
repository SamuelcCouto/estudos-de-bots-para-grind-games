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
INTERVALO_MINIMAPA = 0.4      # s entre leituras do minimapa para o rastreador (posicao do jogador = a que mais se repete)
TOLERANCIA_ANGULO = 3.0       # graus
TAXA_ANGULO_INICIAL = 28.0    # graus/s com a seta apertada (aprende sozinho)
FORCA_POR_SEGUNDO = 38.0      # % da barra por segundo segurando espaco (medido nas gravacoes; o bot aprende o valor real)
ANTECIPACAO_INICIAL = 4.0     # % de folga: solta um pouco antes (atraso da captura + do KEYUP)
FOCO_CLICK_BATALHA = (560, 230)   # clique na cena de batalha (nunca no chat/log)
MAX_SEGURANDO = 7.0           # s: trava de seguranca (a carga pode andar na METADE da velocidade; ver NOTAS.md)
MARGEM_TEMPO_MINIMO = 0.35    # s: tolerancia da trava de tempo minimo


class LeitorReal:
    """Transforma o quadro da janela (qualquer tamanho) nas leituras numericas."""
    def preparar(self, img): return em_1280(img)
    minha_vez = staticmethod(L.minha_vez)
    angulo = staticmethod(L.angulo)
    forca = staticmethod(L.forca)
    pontos = staticmethod(L.pontos_minimapa)
    candidatos = staticmethod(L.candidatos_minimapa)
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
        self.taxa_forca = FORCA_POR_SEGUNDO       # % por segundo segurando (aprende no metodo "tempo")
        self.taxa_medida_antes = False
        self.metodo_forca = "barra"               # "barra" = solta olhando a barra; "tempo" = solta pelo relogio
        self.subforcas = 0
        self.antecipacao = ANTECIPACAO_INICIAL
        self.vez_desde = None
        self.agiu = False
        self.pendente = None
        self.turnos = 0
        self.falhas_tecla = 0
        self.rastreador = L.RastreadorMinimapa()
        self.ultimo_minimapa = -99.0
        self.inst_rastreada = None
        if getattr(memoria, "ignorados", 0):
            self.log(f"(memoria: {memoria.ignorados} tiro(s) antigos ignorados - foram gravados com a leitura antiga do "
                     f"minimapa, que podia confundir a agua/efeitos com o seu boneco)")

    # ------------------------------------------------------------------ leitura
    def ver(self):
        img = self.io.capturar()
        return None if img is None else self.lei.preparar(img)

    def _candidatos(self, f):
        if hasattr(self.lei, "candidatos"):
            return self.lei.candidatos(f)
        az, vm = self.lei.pontos(f)               # leitor simples (testes): um ponto de cada
        return ([az] if az else []), ([vm] if vm else [])

    def observar_minimapa(self, f, forcar=False):
        agora = self.agora()
        if not forcar and agora - self.ultimo_minimapa < INTERVALO_MINIMAPA:
            return
        self.ultimo_minimapa = agora
        self.rastreador.observar(*self._candidatos(f))

    def _resumo_minimapa(self):
        j, c = self.rastreador.jogador()
        ult = self.rastreador.azuis[-1] if self.rastreador.azuis else []
        r = lambda p: p and [round(p[0], 1), round(p[1], 1)]
        return {"jogador": r(j), "confianca": round(c, 2), "boss": r(self.rastreador.boss), "azuis_agora": [r(p) for p in ult]}

    def posicoes(self, f):
        """(jogador, boss, confianca do jogador) - jogador pelo rastreador (o que mais se repete na batalha), boss pela
        leitura mais recente."""
        self.observar_minimapa(f, forcar=True)
        azul, conf = self.rastreador.jogador()
        return azul, self.rastreador.boss, conf

    # ------------------------------------------------------------------ laco (chamado varias vezes por segundo)
    def passo(self, f=None):
        f = self.lei.preparar(f) if f is not None else self.ver()
        if f is None:
            return
        vez = self.lei.minha_vez(f)
        agora = self.agora()
        inst = self.instancia()
        if inst != self.inst_rastreada:
            self.rastreador.reiniciar()
            self.inst_rastreada = inst
        self.observar_minimapa(f)
        if self.reg and agora - self.ultima_leitura >= INTERVALO_LEITURA:
            self.ultima_leitura = agora
            self.reg.evento("leitura", [self.reg.frame(f, "leitura")], vez=bool(vez), agiu=self.agiu,
                            angulo=round(self.lei.angulo(f), 1), forca=round(self.lei.forca(f)), vida=round(self.lei.vida(f)),
                            itens=self.lei.itens(f), minimapa=self._resumo_minimapa())
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
                if self.lei.vida(f) <= 0:
                    return                            # boss morto: o PASS fica na tela ate a vitoria, nao e outro turno
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
        self.rastreador.reiniciar()               # proxima batalha: spawn novo

    # ------------------------------------------------------------------ um turno
    def devolver_foco(self):
        if hasattr(self.io, "encerrar_teclas"):
            self.io.encerrar_teclas()            # devolve o primeiro plano a janela em que voce estava

    def vez_ativa(self):
        f = self.ver()
        return f is not None and self.lei.minha_vez(f)

    def turno(self, f):
        self.turnos += 1
        inicio = self.agora()
        self.acao_em = inicio
        self.turno_abortado = False
        inst = self.instancia()
        azul, boss, conf = self.posicoes(f)
        for _ in range(3):
            if azul and boss:
                break
            self.dormir(0.1)
            g = self.ver()
            if g is not None:
                azul, boss, conf = self.posicoes(g)
        pred = self.mem.prever(inst, azul, boss)
        hp0 = self.lei.vida(f)
        itens0 = self.lei.itens(f)
        self.log(f"[tiro {self.turnos}] {inst}: voce {azul and tuple(round(v) for v in azul)} (em {conf:.0%} das leituras), "
                 f"boss {boss and tuple(round(v) for v in boss)}"
                 f" -> mirar {pred['angulo']:.0f} graus, forca {pred['forca']:.0f}% ({pred['origem']}: {pred['detalhe']})")
        fr = [self.reg.frame(f, "turno_inicio")] if self.reg else []
        if self.sombra:
            self.agiu = True
            self.log("   [sombra] nao apertei nada.")
            if self.reg:
                self.reg.evento("turno_sombra", fr, inst=inst, azul=azul, boss=boss, previsto=pred, itens_coloridos=itens0)
            return
        if hasattr(self.io, "preparar_teclas"):
            self.io.preparar_teclas()            # o Chromium so entrega teclado a pagina em foco
        ok_ang = self.ajustar_angulo(pred["angulo"])
        t_ang = self.agora() - inicio
        if self.reg:
            fr.append(self.reg.frame(self.ver(), "apos_angulo"))
        if not ok_ang:
            self.log("   ! nao consegui ajustar o angulo (as setas nao estao chegando ao jogo? ou a vez acabou). Pulando o tiro. "
                     "Dica: clique no jogo para ele ficar em primeiro plano, ou rode com --foco 2.")
            self.agiu = True
            self.devolver_foco()
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
        forca_real, soltou, trace, segurou = self.carregar(alvo_forca)
        self.devolver_foco()
        metodo_usado = self.metodo_forca
        if soltou != "vez_acabou" and alvo_forca - forca_real > 10 and forca_real < 0.75 * alvo_forca:
            self.subforcas += 1
            self.metodo_forca = "tempo" if metodo_usado == "barra" else "barra"
            self.log(f"   ! a forca ficou muito abaixo do alvo ({forca_real:.0f}% de {alvo_forca:.0f}%, soltou por '{soltou}', "
                     f"segurou {segurou:.2f}s): trocando o metodo de carga {metodo_usado} -> {self.metodo_forca}")
        else:
            self.subforcas = 0
        t_tiro = self.agora() - inicio
        self.agiu = True
        self.pendente = {"t": self.agora(), "inst": inst, "azul": azul, "boss": boss, "angulo": angulo_real,
                         "forca": forca_real, "hp0": hp0}
        self.log(f"   tiro dado: {angulo_real:.0f} graus, forca {forca_real:.0f}% (queria {alvo_forca:.0f}%); "
                 f"[{metodo_usado}, soltou por '{soltou}'] tempo: angulo {t_ang:.1f}s, itens {t_itens - t_ang:.1f}s, carga {t_tiro - t_itens:.1f}s (total {t_tiro:.1f}s)")
        if self.reg:
            fr.append(self.reg.frame(self.ver(), "tiro_dado"))
            self.reg.evento("turno", fr, inst=inst, azul=azul, boss=boss, confianca_jogador=round(conf, 2), previsto=pred, angulo_real=round(angulo_real, 1),
                            forca_real=round(forca_real), alvo_forca=round(alvo_forca), itens=apertados, itens_coloridos_inicio=itens0,
                            soltou=soltou, metodo_forca=metodo_usado, segurou_s=round(segurou, 2), trace_barra=trace[-40:],
                            taxa_forca=round(self.taxa_forca, 1), jogo_em_foco=(self.io.em_foco() if hasattr(self.io, "em_foco") else None),
                            nivel_foco=getattr(self.io, "foco_nivel", None),
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
                if sem_efeito == 2 and self._no_limite(tecla, b):
                    return True
                if sem_efeito == 1 and hasattr(self.io, "clicar_ref"):
                    # o foco do teclado pode estar no chat: um clique na CENA devolve o teclado ao jogo
                    self.log("   ! as setas nao mudaram o angulo: clicando na cena para devolver o foco do teclado ao jogo (e nao ao chat).")
                    self.io.clicar_ref(*FOCO_CLICK_BATALHA)
                    self.dormir(0.2)
                elif hasattr(self.io, "escalar_foco") and self.io.escalar_foco():
                    self.log(f"   ! as setas nao mudaram o angulo: o jogo provavelmente sem foco do teclado; "
                             f"subindo o nivel de foco para {self.io.foco_nivel} ({'foco virtual' if self.io.foco_nivel == 1 else 'jogo em primeiro plano durante o turno'}).")
                elif sem_efeito >= 2 and sem_efeito % 2 == 0 and hasattr(self.io, "trocar_modo"):
                    self.log("   ! as setas nao mudaram o angulo; tentando outro modo de entrada.")
                    self.io.trocar_modo()
                if sem_efeito >= 6:
                    return False
            else:
                sem_efeito = 0
                taxa = abs(mudou) / dur
                if 5 < taxa < 120 and mudou * erro > 0:       # aprende a velocidade do angulo
                    self.taxa_angulo = 0.6 * self.taxa_angulo + 0.4 * taxa
        return abs(alvo - self.lei.angulo(self.ver())) <= TOLERANCIA_ANGULO * 2

    def _no_limite(self, tecla, a):
        """A seta nao mexeu o ponteiro: teclado sem foco, ou o angulo ja esta no LIMITE da arma (no terreno inclinado o
        limite muda). Testa a seta contraria: se ELA mexe, o teclado funciona e estamos no limite -> volta e atira daqui
        (a forca e recalculada para o angulo real)."""
        contraria = "baixo" if tecla == "cima" else "cima"
        self.io.tecla(contraria, 0.15)
        self.dormir(0.1)
        b = self.lei.angulo(self.ver())
        if abs(b - a) < 0.8:
            return False
        self.io.tecla(tecla, 0.3)                 # volta para o limite (o mais perto possivel do alvo)
        self.dormir(0.1)
        final = self.lei.angulo(self.ver())
        self.log(f"   ! o angulo nao {'sobe' if tecla == 'cima' else 'desce'} alem de {final:.0f} graus (limite da arma neste "
                 f"terreno; a seta contraria funciona): atirando deste angulo.")
        return True

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
    def _segurar(self):
        if hasattr(self.io, "segurar"):
            self.io.segurar(TECLA_ESPACO)         # repeticao de tecla a cada ~30 ms, em thread propria
            return False
        self.io.tecla_baixo(TECLA_ESPACO, 1)
        return True                               # sem thread: o laco repete a tecla a cada leitura

    def _soltar(self):
        if hasattr(self.io, "soltar"):
            self.io.soltar(TECLA_ESPACO)
        else:
            self.io.tecla_cima(TECLA_ESPACO)

    @staticmethod
    def _taxa_do_trace(trace):
        """% por segundo da barra, pela inclinacao dos pontos (tempo, %) entre 5% e 95%. None se nao der."""
        pts = [(t, v) for t, v in trace if 5 <= v <= 95]
        if len(pts) < 3 or pts[-1][0] - pts[0][0] < 0.3:
            return None
        t, v = np.array(pts, dtype=float).T
        taxa = float(np.polyfit(t, v, 1)[0])
        return taxa if 5 < taxa < 120 else None

    def carregar(self, alvo):
        """Segura ESPACO e solta na forca alvo. Dois metodos:
          "barra": solta quando a barra chega em (alvo - antecipacao) - com trava de tempo minimo (a barra pode
                   estar mostrando o tiro anterior);
          "tempo": solta pelo relogio (alvo / taxa), sem confiar na leitura da barra.
        Nos dois, solta se a vez acabar (2 leituras seguidas sem o PASS, para um piscar nao soltar cedo).
        Devolve (forca final lida, motivo, trace [(s, %)], tempo segurado)."""
        quer = max(0.0, alvo - self.antecipacao)
        por_tempo = self.metodo_forca == "tempo"
        minimo = max(0.0, quer / self.taxa_forca - MARGEM_TEMPO_MINIMO)
        tempo_alvo = quer / self.taxa_forca
        # a barra pode encher bem mais devagar que o esperado (medido: 19%/s em vez de 38%/s): deixa ate ~2,2x o tempo
        limite = min(MAX_SEGURANDO, alvo / (0.45 * self.taxa_forca) + 0.5)
        repetir_no_laco = self._segurar()
        rep = 1
        t0 = self.agora()
        v, motivo, trace, faltas = 0.0, "tempo_limite", [], 0
        visto_baixo = False
        while self.agora() - t0 < limite:
            f = self.ver()
            dur = self.agora() - t0
            if f is not None:
                if not self.lei.minha_vez(f):
                    faltas += 1
                    if faltas >= 2:
                        motivo = "vez_acabou"
                        break
                else:
                    faltas = 0
                v = self.lei.forca(f)
                trace.append((round(dur, 2), round(v)))
                if v <= 12:
                    visto_baixo = True
                if por_tempo:
                    if dur >= tempo_alvo:
                        motivo = "tempo_alvo"
                        break
                elif v >= quer and dur >= minimo and (visto_baixo or dur >= 2 * minimo + 0.5):
                    motivo = "alvo"
                    break
            elif por_tempo and dur >= tempo_alvo:
                motivo = "tempo_alvo"
                break
            if repetir_no_laco:
                rep += 1
                self.io.tecla_baixo(TECLA_ESPACO, rep)
        segurou = self.agora() - t0
        self._soltar()
        self.dormir(0.25)
        final = self.lei.forca(self.ver())
        taxa_medida = self._taxa_do_trace(trace)
        if taxa_medida:
            # a 1a medicao real substitui o valor padrao; depois, media movel
            peso = 0.5 if self.taxa_medida_antes else 1.0
            self.taxa_forca = float(np.clip((1 - peso) * self.taxa_forca + peso * taxa_medida, 8.0, 80.0))
            self.taxa_medida_antes = True
        if final > 0:
            if motivo == "alvo":
                self.antecipacao = float(np.clip(self.antecipacao + 0.5 * (final - alvo), 0.0, 12.0))   # corrige o atraso
            elif motivo == "tempo_alvo" and segurou > 0.3 and not taxa_medida:
                self.taxa_forca = float(np.clip(0.7 * self.taxa_forca + 0.3 * (final / segurou), 8.0, 80.0))
        return (final if final > 0 else v), motivo, trace, segurou

    # ------------------------------------------------------------------ resultado
    def concluir_tiro(self, f):
        p, self.pendente = self.pendente, None
        hp1 = self.lei.vida(f)
        acertou = hp1 < p["hp0"] - 3
        self.log(f"   [tiro] vida do boss {p['hp0']:.0f}% -> {hp1:.0f}%: {'ACERTOU' if acertou else 'ERROU'}")
        self.mem.registrar(p["inst"], p["azul"], p["boss"], p["angulo"], p["forca"], acertou, origem="bot")
