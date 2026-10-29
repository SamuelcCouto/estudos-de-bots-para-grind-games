# -*- coding: utf-8 -*-
"""
Contadores da EXECUCAO atual do bot (logs/estatisticas.json), para o painel mostrar: voltas, tempo de execucao,
lutas e vitorias, missoes coletadas, cartas abertas e o que veio nelas (drops). O painel le o arquivo a cada 2 s.
"""
import json
import os
import time

import config

ARQ = os.path.join(config.PASTA_LOGS, "estatisticas.json")


class Estatisticas:
    def __init__(self, arq=ARQ, agora=time.time, nome_rota=""):
        self.arq, self.agora = arq, agora
        self.d = {"rota": nome_rota, "inicio": agora(), "pausado": 0.0, "voltas": 0, "lutas": {}, "vitorias": 0, "derrotas": 0,
                  "missoes": 0, "cartas": 0, "drops": {}, "chefao_derrotado": 0}
        self.salvar()

    def luta(self, inst, venceu):
        self.d["lutas"][inst] = self.d["lutas"].get(inst, 0) + 1
        self.d["vitorias" if venceu else "derrotas"] += 1
        self.salvar()

    def volta(self):
        self.d["voltas"] += 1
        self.salvar()

    def missoes(self, n):
        self.d["missoes"] += int(n)
        self.salvar()

    def drop(self, chave, n=1):
        self.d["cartas"] += n
        self.d["drops"][chave] = self.d["drops"].get(chave, 0) + n
        self.salvar()

    def chefao(self):
        self.d["chefao_derrotado"] += 1
        self.salvar()

    def pausa(self, dur):
        self.d["pausado"] += dur
        self.salvar()

    def salvar(self):
        self.d["atualizado"] = self.agora()
        try:
            os.makedirs(os.path.dirname(self.arq), exist_ok=True)
            tmp = self.arq + ".tmp"
            json.dump(self.d, open(tmp, "w", encoding="utf-8"), ensure_ascii=False)
            os.replace(tmp, self.arq)
        except OSError:
            pass


def ler(arq=ARQ):
    try:
        return json.load(open(arq, encoding="utf-8"))
    except (OSError, ValueError):
        return None


def fmt_duracao(s):
    s = int(max(0, s))
    return f"{s // 3600}h{s % 3600 // 60:02d}min" if s >= 3600 else f"{s // 60}min{s % 60:02d}s"


def texto_resumo(d, nomes=None, agora=None):
    """Texto do Relatorio para o painel (versao dos amigos): so o que importa."""
    if not d:
        return "Ainda nao ha dados. Clique em INICIAR."
    nomes = nomes or {}
    fim = d.get("atualizado") or (agora or time.time())
    rodando = max(0.0, fim - d["inicio"] - d.get("pausado", 0.0))
    linhas = [f"Rota: {d.get('rota', '')}", "",
              f"Tempo de execucao:   {fmt_duracao(rodando)}",
              f"Voltas completas:    {d['voltas']}",
              f"Lutas vencidas:      {d['vitorias']}" + (f"   (derrotas: {d['derrotas']})" if d["derrotas"] else ""),
              f"Missoes concluidas:  {d['missoes']}",
              f"Cartas abertas:      {d['cartas']}"]
    if d.get("chefao_derrotado"):
        linhas.append(f"Chefao Global:       {d['chefao_derrotado']} derrotado(s) com a sua ajuda")
    if d["voltas"] and rodando > 60:
        linhas.append(f"Ritmo:               {d['voltas'] / (rodando / 3600):.1f} voltas por hora")
    if d["lutas"]:
        linhas += ["", "Lutas por chefe:"] + [f"   {nomes.get(k, k.replace('_', ' ').title()):22s}{v}" for k, v in d["lutas"].items()]
    if d["drops"]:
        linhas += ["", "O que veio nas cartas:"]
        for k, v in sorted(d["drops"].items(), key=lambda kv: -kv[1]):
            linhas.append(f"   {nomes.get(k, k.replace('_', ' ').capitalize()):28s}{v}")
    return "\n".join(linhas) + "\n"
