# -*- coding: utf-8 -*-
"""Logica do painel (sem janela, testavel): monta a linha de comando do navegador.py a partir das escolhas."""
import json
import os
import shutil
import sys

import config
import navegador as N

ARQ_CONFIG = os.path.join(config.PASTA, "dados", "painel.json")
# alvo = o que o bot faz: "N" (Rota Norte), "S" (Rota Sul), "L" (Rota Leste - em desenvolvimento), "C" (Chefao Global) ou o nome
# de UM chefe (o bot luta so nele, repetidamente)
ROTAS_PAINEL = [("N", "Rota Norte", "Fantasma > Profundezas > Minhocao", True),
                ("S", "Rota Sul", "Escorpiao Rei > Dragao Gelado > Rainha Liris", True),
                ("L", "Rota Leste", "em desenvolvimento", False)]
CHEFES_PAINEL = [("FANTASMA", "Fantasma"), ("PROFUNDEZAS", "Profundezas"), ("MINHOCAO", "Minhocao"),
                 ("ESCORPIAO_REI", "Escorpiao Rei"), ("DRAGAO_GELADO", "Dragao Gelado"), ("RAINHA_LIRIS", "Rainha Liris"),
                 ("GATO_PRETO", "Gato Preto"), ("PERICAO", "Pericao (comum)"), ("C", "Chefao Global")]
NOMES_CHEFES = dict(CHEFES_PAINEL)
PADRAO = {"alvo": "S", "cartas": ["RAINHA_LIRIS"], "chefe_nos_horarios": True, "horarios": "12:00-13:00,21:00-22:00",
          "gravar": True, "gravacao_leve": False, "enviar_ao_parar": False, "reiniciar_se_cair": True, "tarefas": True}


def modo_amigo():
    """Versao dos amigos: so o essencial (sem gravacao, git, log, ferramentas). --amigo, ou um arquivo amigo.flag ao lado."""
    return "--amigo" in sys.argv or os.path.exists(os.path.join(config.PASTA, "amigo.flag"))


def instancias_do_alvo(alvo):
    if alvo in N.ROTAS and alvo in ("N", "S"):
        return list(N.ROTAS[alvo][1])
    return [N.CHEFE if alvo == "C" else alvo]


def comando_base(modulo, python="python"):
    """['python', '-u', 'navegador.py'] ou, no BotDDT.exe, ['BotDDT.exe', '--navegador'] (o mesmo .exe faz tudo)."""
    if config.CONGELADO:
        return [sys.executable, "--" + modulo]
    return [python, "-u", modulo + ".py"]


def montar_comando(cfg, python="python", amigo=False):
    """Lista de argumentos para subprocess. Tudo vai por argumento: o navegador nao pergunta nada."""
    alvo = cfg["alvo"]
    if alvo == "L":
        raise ValueError("a Rota Leste ainda esta em desenvolvimento")
    cmd = comando_base("navegador", python) + ["--atirar", "--rota", "P" if alvo == "PERICAO" else alvo]
    inst = instancias_do_alvo(alvo)
    marcadas = [i for i in cfg.get("cartas", []) if i in inst]
    if len(marcadas) == len(inst):
        cmd += ["--cartas", "TODAS"]
    else:
        cmd += ["--cartas", ",".join(marcadas) if marcadas else "NENHUMA"]
    if alvo != "C":
        cmd += ["--chefe", "s" if cfg.get("chefe_nos_horarios") else "n"]
    if cfg.get("horarios"):
        N.ler_horarios(cfg["horarios"])                 # valida (ValueError se estiver errado)
        cmd += ["--horarios-chefe", cfg["horarios"]]
    if amigo or not cfg.get("gravar", True):
        cmd.append("--sem-gravar")                      # amigos: nada de gravacao
    elif cfg.get("gravacao_leve"):
        cmd.append("--gravacao-leve")
    if not cfg.get("tarefas", True):
        cmd.append("--sem-tarefas")
    return cmd


def passos_envio():
    """Empacota e, se der (git instalado e pasta clonada), envia ao GitHub. Sem git (BotDDT.exe de amigo): so empacota, e
    os zips ficam em envio\\ para a pessoa mandar do jeito que preferir."""
    passos = [comando_base("empacotar", "python") + ["--novas"]]
    if tem_git():
        # (o "reset" limpa um conflito de arquivo que o git deixou pendente - ja impediu o envio uma vez)
        passos += [["git", "reset", "-q"], ["git", "add", "envio"], ["git", "commit", "-m", "sessao gravada"], ["git", "pull", "--rebase", "--autostash"],
                   ["git", "push"]]
    return passos


def raiz_git(pasta=None):
    """Pasta que tem o .git: o repositorio fica UM NIVEL ACIMA de ddtank\\ (o painel achava que nao havia git e nunca enviava)."""
    d = os.path.abspath(pasta or config.PASTA)
    for _ in range(4):
        if os.path.exists(os.path.join(d, ".git")):
            return d
        pai = os.path.dirname(d)
        if pai == d:
            break
        d = pai
    return None


def tem_git():
    return bool(shutil.which("git")) and raiz_git() is not None


PASSOS_ENVIO = passos_envio()
PASSO_ATUALIZAR = ["git", "pull", "--autostash"]
PASSOS_ATUALIZAR = [["git", "reset", "-q"], PASSO_ATUALIZAR]


def carregar():
    cfg = dict(PADRAO)
    try:
        velho = json.load(open(ARQ_CONFIG, encoding="utf-8"))
        if "rota" in velho and "alvo" not in velho:
            velho["alvo"] = velho.pop("rota") if velho["rota"] in ("N", "S", "C") else "S"
            velho.pop("cartas", None)
        velho.pop("rota", None)
        cfg.update(velho)
    except (OSError, ValueError):
        pass
    return cfg


def salvar(cfg):
    try:
        os.makedirs(os.path.dirname(ARQ_CONFIG), exist_ok=True)
        json.dump(cfg, open(ARQ_CONFIG, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    except OSError:
        pass
