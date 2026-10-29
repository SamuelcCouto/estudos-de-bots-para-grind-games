# -*- coding: utf-8 -*-
"""
Cronometro e placar do bot: quanto demora cada LUTA, cada INSTANCIA (escolher na sala + luta + cartas) e cada VOLTA
da rota; quantos turnos o bot precisou, se matou no 1o turno e quanto de vida o 1o ataque tirou.

Arquivos na pasta logs\\ (vao junto no EMPACOTAR):
  lutas.csv      uma linha por luta (todas as execucoes, acumulando)
  voltas.csv     uma linha por volta completa da rota
  relatorio.txt  resumo DESTA execucao, reescrito a cada luta, com o diagnostico de cada instancia:
                 mata no 1o turno / PRECISA UPAR (acerta mas nao mata) / PONTARIA (o 1o tiro erra)
"""
import csv
import datetime
import os
import time

import config
import estrategias

NOMES = {"FANTASMA": "Fantasma", "PROFUNDEZAS": "Profundezas", "MINHOCAO": "Minhocao", "ESCORPIAO_REI": "Escorpiao Rei",
         "DRAGAO_GELADO": "Dragao Gelado", "RAINHA_LIRIS": "Rainha Liris", "ULTIMA_LUTA": "A Ultima Luta",
         "GATO_PRETO": "Gato Preto", "PERICAO": "Pericao (Chefao Global)",
         "PERICAO_COMUM": "Pericao (comum)"}
TESTE_DE_FOGO = "2,3,4"      # combo de dano maximo (ver combos.py): a prova de que precisa upar
FOGO_PARA_CONCLUIR = 5
LUTAS_PARA_CONFIAR = 20      # menos lutas que isso: um "matou no 1o turno" pode ter sido CRITICO
MATA_NO_1O_OK = 0.8          # fracao de lutas mortas no 1o turno para considerar a instancia "resolvida"
ACERTA_O_1O = 0.7            # se o 1o ataque acerta menos que isso, o problema e pontaria (nao falta de dano)


def nome(inst):
    return NOMES.get(inst, inst.title())


def fmt(s):
    """segundos -> '45s', '3min05s', '2h14min'."""
    if s is None:
        return "-"
    s = int(round(s))
    if s < 60:
        return f"{s}s"
    if s < 3600:
        return f"{s // 60}min{s % 60:02d}s"
    return f"{s // 3600}h{(s % 3600) // 60:02d}min"


class Metricas:
    def __init__(self, rota_nome="", pasta=None, agora=time.time, log=print, salvar=True, combos=None):
        self.combos = combos          # combos.Combos: a tabela de combos (todas as execucoes) vai no relatorio
        self.pasta = pasta or config.PASTA_LOGS
        self.agora, self.log, self.salvar = agora, log, salvar
        self.rota_nome = rota_nome
        self.inicio = agora()
        self.lutas, self.voltas = [], []
        self.inst = None              # instancia em andamento: {"inst", "volta", "t0"}
        self.luta = None              # luta em andamento
        self.volta_t0 = None
        self.volta_lutas = []
        self.pausado_total = 0.0
        if salvar:
            os.makedirs(self.pasta, exist_ok=True)

    def descontar_pausa(self, dur):
        """O bot ficou `dur` s pausado: empurra os relogios em andamento para esse tempo nao entrar nas medidas."""
        self.pausado_total += dur
        self.inicio += dur
        for d in (self.inst, self.luta):
            if d:
                d["t0"] += dur
        if self.volta_t0 is not None:
            self.volta_t0 += dur

    # ------------------------------------------------------------------ eventos (chamados pelo navegador/atirador)
    def instancia_inicio(self, inst, volta):
        if self.inst and self.inst["inst"] == inst:
            return
        t = self.agora()
        self.inst = {"inst": inst, "volta": volta, "t0": t}
        if self.volta_t0 is None:
            self.volta_t0 = t

    def batalha_inicio(self, inst, volta=0):
        self.instancia_inicio(inst, volta)
        self.luta = {"inst": inst, "volta": volta, "t0": self.agora(), "turnos": 0, "ataques": 0, "avioes": 0,
                     "pulados": 0, "danos": [], "acertos": 0, "erros": 0, "especiais": 0, "combo": None, "itens": None}

    def turno(self, tipo, itens=None, combo=None, especial=False):
        """tipo: 'ataque' | 'aviao' | 'pulado'. especial = usou o POW (tecla B) neste ataque."""
        if not self.luta:
            return
        L = self.luta
        if tipo == "pulado":
            L["pulados"] += 1
            return
        L["turnos"] += 1
        if tipo == "aviao":
            L["avioes"] += 1
            return
        L["ataques"] += 1
        L["especiais"] += bool(especial)
        if L["combo"] is None:
            L["combo"], L["itens"] = combo, itens

    def resultado_tiro(self, dano, acertou):
        """acertou None = nao deu para conferir (especial do Chefao Global: a camera anda)."""
        if not self.luta:
            return
        self.luta["danos"].append(round(float(dano), 1))
        if acertou is not None:
            self.luta["acertos" if acertou else "erros"] += 1

    def batalha_fim(self, venceu):
        L, self.luta = self.luta, None
        if not L:
            return
        L["t1"] = self.agora()
        L["duracao"] = L["t1"] - L["t0"]
        L["venceu"] = bool(venceu)
        L["dano_1o"] = L["danos"][0] if L["danos"] else None
        L["acertou_1o"] = bool(L["danos"]) and L["danos"][0] > 3
        L["matou_no_1o"] = bool(venceu) and L["turnos"] == 1
        L["tempo_instancia"] = None
        self.lutas.append(L)
        self.volta_lutas.append(L)
        extra = (f", 1o ataque tirou {L['dano_1o']:.0f}%" if L["dano_1o"] is not None else "") + \
                (f", {L['avioes']} aviao" if L["avioes"] else "")
        self.log(f"[TEMPO] {nome(L['inst'])}: luta {fmt(L['duracao'])} - "
                 f"{'VITORIA' if venceu else 'DERROTA'} em {L['turnos']} turno(s) do bot{extra}")
        self._csv_luta(L)
        self.escrever_relatorio()

    def instancia_fim(self, inst):
        """Cartas viradas e de volta a sala: a instancia acabou (desde que comecou a ser escolhida)."""
        if not self.inst or self.inst["inst"] != inst:
            return
        dur = self.agora() - self.inst["t0"]
        ult = next((L for L in reversed(self.lutas) if L["inst"] == inst), None)
        if ult is not None and ult.get("tempo_instancia") is None:
            ult["tempo_instancia"] = dur
        self.log(f"[TEMPO] {nome(inst)}: instancia completa em {fmt(dur)} (menus + luta + cartas)")
        self.inst = None

    def volta_fim(self, volta):
        t = self.agora()
        if self.volta_t0 is None:
            return
        V = {"volta": volta, "t0": self.volta_t0, "duracao": t - self.volta_t0,
             "lutas": len(self.volta_lutas), "derrotas": sum(not L["venceu"] for L in self.volta_lutas),
             "tempo_em_luta": sum(L["duracao"] for L in self.volta_lutas)}
        self.voltas.append(V)
        self.volta_t0, self.volta_lutas = t, []
        self.log(f"[TEMPO] === volta {volta} em {fmt(V['duracao'])} ({V['lutas']} lutas, {V['derrotas']} derrota(s); "
                 f"{fmt(V['tempo_em_luta'])} dentro das lutas) ===")
        self._csv_volta(V)
        self.escrever_relatorio()

    # ------------------------------------------------------------------ resumo
    def por_instancia(self):
        ordem = []
        for L in self.lutas:
            if L["inst"] not in ordem:
                ordem.append(L["inst"])
        out = {}
        for inst in ordem:
            ls = [L for L in self.lutas if L["inst"] == inst]
            vit = [L for L in ls if L["venceu"]]
            com_1o = [L for L in ls if L["dano_1o"] is not None]
            acertou = [L for L in com_1o if L["acertou_1o"]]
            tins = [L["tempo_instancia"] for L in ls if L.get("tempo_instancia")]
            fogo = [L for L in vit if L["combo"] == TESTE_DE_FOGO and L["acertou_1o"]]
            out[inst] = {
                "n_fogo": len(fogo),
                "fogo_mata_1o": sum(L["ataques"] == 1 for L in fogo) / len(fogo) if fogo else None,
                "dano_fogo": sum(L["dano_1o"] for L in fogo) / len(fogo) if fogo else None,
                "lutas": len(ls), "vitorias": len(vit), "derrotas": len(ls) - len(vit),
                "luta_media": sum(L["duracao"] for L in ls) / len(ls),
                "instancia_media": sum(tins) / len(tins) if tins else None,
                "turnos_medios": sum(L["turnos"] for L in vit) / len(vit) if vit else None,
                "mata_no_1o": sum(L["matou_no_1o"] for L in ls) / len(ls),
                "acerta_o_1o": len(acertou) / len(com_1o) if com_1o else None,
                "dano_1o_medio": sum(L["dano_1o"] for L in acertou) / len(acertou) if acertou else None,
                "avioes": sum(L["avioes"] for L in ls), "pulados": sum(L["pulados"] for L in ls),
                "acertos": sum(L["acertos"] for L in ls), "erros": sum(L["erros"] for L in ls),
                "especiais": sum(L.get("especiais", 0) for L in ls), "turnos_total": sum(L["turnos"] for L in ls),
            }
        return out

    @staticmethod
    def diagnostico(inst, r):
        n = r["lutas"]
        if estrategias.estrategia(inst).get("chefe_global"):
            tiros = r["acertos"] + r["erros"]
            pont = (f"tiros normais acertando {r['acertos'] / tiros:.0%} ({r['acertos']} de {tiros}, pelos numeros de dano)"
                    if tiros else "nenhum tiro normal conferido ainda")
            return (f"CHEFAO GLOBAL - {n} luta(s), {r['turnos_total']} turno(s) do bot; {pont}; {r['especiais']} especial(is) "
                    f"(POW). Vitoria = o servidor inteiro derrubou o chefao; derrota = rodada 200, morte ou fim do horario.")
        poucas = f" (so {n} lutas: pode ter sido critico - confirmo com {LUTAS_PARA_CONFIAR}+)" if n < LUTAS_PARA_CONFIAR else ""
        if r["mata_no_1o"] >= MATA_NO_1O_OK:
            return f"OK - mata no 1o turno ({r['mata_no_1o']:.0%} das {n} lutas){poucas}."
        if r["acerta_o_1o"] is not None and r["acerta_o_1o"] < ACERTA_O_1O:
            return (f"PONTARIA - o 1o tiro erra em {1 - r['acerta_o_1o']:.0%} das lutas; o bot ainda esta aprendendo a "
                    f"forca deste mapa (ou o boss se mexe/tem hitbox pequena).")
        if r["n_fogo"] >= FOGO_PARA_CONCLUIR and r["fogo_mata_1o"] < 0.2:
            mult = 100.0 / max(r["dano_fogo"], 1.0)
            return (f"PRECISA UPAR - TESTE DE FOGO (itens 2,3,4,4 + buffs) acertando: o 1o ataque tira ~{r['dano_fogo']:.0f}% "
                    f"e o boss sobrevive ({r['n_fogo']} lutas; matou no 1o em {r['fogo_mata_1o']:.0%}). Precisa de ~{mult:.1f}x "
                    f"o dano. Hoje leva {r['turnos_medios'] or 0:.1f} turnos.")
        if r["n_fogo"] and r["fogo_mata_1o"] is not None and r["fogo_mata_1o"] < MATA_NO_1O_OK:
            return (f"QUASE - com o teste de fogo mata no 1o turno em {r['fogo_mata_1o']:.0%} das {r['n_fogo']} lutas "
                    f"(1o ataque ~{r['dano_fogo']:.0f}%): critico ajuda; um pouco de upgrade resolve.")
        if r["dano_1o_medio"] is not None:
            return (f"ainda testando combos - 1o ataque ~{r['dano_1o_medio']:.0f}% em media; o veredito sai do teste de fogo "
                    f"({r['n_fogo']}/{FOGO_PARA_CONCLUIR} lutas).")
        return "sem dados suficientes ainda."

    def texto_relatorio(self):
        agora = self.agora()
        rod = agora - self.inicio
        linhas = [f"RELATORIO DO BOT - {self.rota_nome}   (atualizado {datetime.datetime.now():%d/%m %H:%M:%S})", ""]
        nv = len(self.voltas)
        if nv:
            durs = [V["duracao"] for V in self.voltas]
            linhas.append(f"Rodando ha {fmt(rod)} | {nv} volta(s) completa(s) | {nv / (rod / 3600):.1f} voltas/hora | "
                          f"volta media {fmt(sum(durs) / nv)} (mais rapida {fmt(min(durs))}, mais lenta {fmt(max(durs))})")
            em_luta = sum(V["tempo_em_luta"] for V in self.voltas) / nv
            linhas.append(f"Por volta: {fmt(em_luta)} dentro das lutas e {fmt(sum(durs) / nv - em_luta)} em menus, salas, "
                          f"cartas e tarefas.")
        else:
            linhas.append(f"Rodando ha {fmt(rod)} | nenhuma volta completa ainda")
        if self.pausado_total:
            linhas.append(f"Tempo pausado (fora das medidas): {fmt(self.pausado_total)}")
        res = self.por_instancia()
        if res:
            linhas += ["", f"{'INSTANCIA':16s}{'lutas':>6s}{'vit':>5s}{'derr':>5s}{'luta media':>12s}{'instancia':>11s}"
                           f"{'turnos':>8s}{'mata 1o':>9s}{'1o ataque':>11s}"]
            for inst, r in res.items():
                turnos = "%.1f" % r["turnos_medios"] if r["turnos_medios"] else "-"
                dano = "%.0f%%" % r["dano_1o_medio"] if r["dano_1o_medio"] is not None else "-"
                linhas.append(f"{nome(inst):16s}{r['lutas']:6d}{r['vitorias']:5d}{r['derrotas']:5d}"
                              f"{fmt(r['luta_media']):>12s}{fmt(r['instancia_media']):>11s}"
                              f"{turnos:>8s}{r['mata_no_1o']:>9.0%}{dano:>11s}")
            linhas += ["", "DIAGNOSTICO"]
            for inst, r in res.items():
                extra = (f" ({r['avioes']} voo(s) de aviao)" if r["avioes"] else "") + \
                        (f" ({r['pulados']} turno(s) pulado(s))" if r["pulados"] else "")
                linhas.append(f"  {nome(inst)}: {self.diagnostico(inst, r)}{extra}")
        tab = self.combos.texto() if self.combos else []
        if tab:
            linhas += ["", "COMBOS DE ITENS (todas as execucoes; o bot usa o de luta mais curta; 2,3,4 = teste de fogo)"] + tab
        return "\n".join(linhas) + "\n"

    def escrever_relatorio(self):
        if not self.salvar:
            return
        try:
            with open(os.path.join(self.pasta, "relatorio.txt"), "w", encoding="utf-8") as f:
                f.write(self.texto_relatorio())
        except OSError:
            pass

    # ------------------------------------------------------------------ csv
    def _csv(self, arq, cab, linha):
        if not self.salvar:
            return
        caminho = os.path.join(self.pasta, arq)
        novo = not os.path.exists(caminho)
        try:
            with open(caminho, "a", newline="", encoding="utf-8") as f:
                w = csv.writer(f, delimiter=";")
                if novo:
                    w.writerow(cab)
                w.writerow(linha)
        except OSError:
            pass

    def _csv_luta(self, L):
        self._csv("lutas.csv",
                  ["data", "rota", "volta", "instancia", "luta_s", "resultado", "turnos_bot", "ataques", "avioes", "pulados",
                   "dano_1o_ataque", "danos", "matou_no_1o_turno", "combo", "itens"],
                  [datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), self.rota_nome, L["volta"], L["inst"],
                   round(L["duracao"], 1), "vitoria" if L["venceu"] else "derrota", L["turnos"], L["ataques"], L["avioes"],
                   L["pulados"], L["dano_1o"] if L["dano_1o"] is not None else "", "/".join(f"{d:.0f}" for d in L["danos"]),
                   "sim" if L["matou_no_1o"] else "nao", L["combo"] or "", ",".join(map(str, L["itens"] or []))])

    def _csv_volta(self, V):
        self._csv("voltas.csv", ["data", "rota", "volta", "volta_s", "lutas", "derrotas", "tempo_em_luta_s"],
                  [datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), self.rota_nome, V["volta"], round(V["duracao"], 1),
                   V["lutas"], V["derrotas"], round(V["tempo_em_luta"], 1)])
