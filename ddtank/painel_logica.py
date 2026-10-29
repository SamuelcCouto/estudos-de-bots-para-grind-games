# -*- coding: utf-8 -*-
"""Logica do painel (sem janela, testavel): monta a linha de comando do navegador.py a partir das escolhas."""
import json
import os
import shutil
import sys

import config
import navegador as N

ARQ_CONFIG = os.path.join(config.PASTA, "dados", "painel.json")
ROTAS_PAINEL = [("S", "Rota Sul", "Escorpiao Rei > Dragao Gelado > Rainha Liris"),
                ("P", "Pericao comum", "o chefe fora do horario do Chefao Global"),
                ("C", "Chefao Global", "so ele: luta e espera o proximo horario")]
ROTAS_AVANCADAS = [("N", "Rota Norte", "Fantasma > Profundezas > Minhocao (desabilitada no dia a dia)"),
                   ("T", "Norte + Sul", "as seis, em sequencia")]
PADRAO = {"rota": "S", "cartas": ["RAINHA_LIRIS"], "chefe_nos_horarios": True, "horarios": "12:00-13:00,21:00-22:00",
          "gravar": True, "gravacao_leve": False, "enviar_ao_parar": False, "reiniciar_se_cair": True, "tarefas": True, "avancado": False}


def instancias_da_rota(chave):
    return list(N.ROTAS[chave][1])


def comando_base(modulo, python="python"):
    """['python', '-u', 'navegador.py'] ou, no BotDDT.exe, ['BotDDT.exe', '--navegador'] (o mesmo .exe faz tudo)."""
    if config.CONGELADO:
        return [sys.executable, "--" + modulo]
    return [python, "-u", modulo + ".py"]


def montar_comando(cfg, python="python"):
    """Lista de argumentos para subprocess. Tudo vai por argumento: o navegador nao pergunta nada."""
    rota = cfg["rota"]
    cmd = comando_base("navegador", python) + ["--atirar", "--rota", rota]
    inst = instancias_da_rota(rota)
    if len(inst) > 1:
        marcadas = [i for i in cfg.get("cartas", []) if i in inst]
        if len(marcadas) == len(inst):
            cmd += ["--cartas", "TODAS"]
        else:
            cmd += ["--cartas", ",".join(marcadas) if marcadas else "NENHUMA"]
    if rota != "C":
        cmd += ["--chefe", "s" if cfg.get("chefe_nos_horarios") else "n"]
    if cfg.get("horarios"):
        N.ler_horarios(cfg["horarios"])                 # valida (ValueError se estiver errado)
        cmd += ["--horarios-chefe", cfg["horarios"]]
    if not cfg.get("gravar", True):
        cmd.append("--sem-gravar")
    elif cfg.get("gravacao_leve"):
        cmd.append("--gravacao-leve")
    if not cfg.get("tarefas", True):
        cmd.append("--sem-tarefas")
    return cmd


def passos_envio():
    """Empacota e, se der (git instalado e pasta clonada), envia ao GitHub. Sem git (BotDDT.exe de amigo): so empacota, e
    os zips ficam em envio\\ para a pessoa mandar do jeito que preferir."""
    passos = [comando_base("empacotar", "python")]
    if shutil.which("git") and os.path.isdir(os.path.join(config.PASTA, ".git")):
        passos += [["git", "add", "envio"], ["git", "commit", "-m", "sessao gravada"], ["git", "pull", "--rebase", "--autostash"],
                   ["git", "push"]]
    return passos


def tem_git():
    return bool(shutil.which("git")) and os.path.isdir(os.path.join(config.PASTA, ".git"))


PASSOS_ENVIO = passos_envio()
PASSO_ATUALIZAR = ["git", "pull", "--autostash"]


def carregar():
    cfg = dict(PADRAO)
    try:
        cfg.update(json.load(open(ARQ_CONFIG, encoding="utf-8")))
    except (OSError, ValueError):
        pass
    return cfg


def salvar(cfg):
    try:
        os.makedirs(os.path.dirname(ARQ_CONFIG), exist_ok=True)
        json.dump(cfg, open(ARQ_CONFIG, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    except OSError:
        pass
