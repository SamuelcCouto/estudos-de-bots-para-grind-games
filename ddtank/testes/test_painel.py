# -*- coding: utf-8 -*-
"""Painel: linha de comando montada a partir das escolhas + fumaca da janela com tkinter falso. Rode: python testes/test_painel.py"""
import os
import sys
import types
from unittest import mock

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(AQUI))
import painel_logica as P

base = dict(P.PADRAO)
c = P.montar_comando(base)
print(" ".join(c))
assert c[:5] == ["python", "-u", "navegador.py", "--atirar", "--rota"] and c[5] == "S"
assert c[c.index("--cartas") + 1] == "RAINHA_LIRIS" and c[c.index("--chefe") + 1] == "s"
assert "--sem-gravar" not in c and "--sem-tarefas" not in c
c = P.montar_comando({**base, "cartas": ["ESCORPIAO_REI", "DRAGAO_GELADO", "RAINHA_LIRIS"], "chefe_nos_horarios": False, "gravar": False, "tarefas": False})
assert c[c.index("--cartas") + 1] == "TODAS" and c[c.index("--chefe") + 1] == "n" and "--sem-gravar" in c and "--sem-tarefas" in c
c = P.montar_comando({**base, "cartas": []}); assert c[c.index("--cartas") + 1] == "NENHUMA"
c = P.montar_comando({**base, "alvo": "C", "cartas": ["PERICAO"]})
assert "--chefe" not in c and c[c.index("--rota") + 1] == "C" and c[c.index("--cartas") + 1] == "TODAS"
# chefe unico: o bot luta so nele
c = P.montar_comando({**base, "alvo": "GATO_PRETO", "cartas": ["GATO_PRETO"]})
assert c[c.index("--rota") + 1] == "GATO_PRETO" and c[c.index("--cartas") + 1] == "TODAS", c
c = P.montar_comando({**base, "alvo": "ESCORPIAO_REI", "cartas": []})
assert c[c.index("--rota") + 1] == "ESCORPIAO_REI" and c[c.index("--cartas") + 1] == "NENHUMA"
c = P.montar_comando({**base, "alvo": "PERICAO", "cartas": ["PERICAO"], "gravacao_leve": True})
assert c[c.index("--rota") + 1] == "P" and "--gravacao-leve" in c
assert P.montar_comando({**base, "alvo": "N"})[5] == "N"
try:
    P.montar_comando({**base, "alvo": "L"}); raise SystemExit("Rota Leste nao existe ainda")
except ValueError:
    pass
try:
    P.montar_comando({**base, "horarios": "banana"}); raise SystemExit("horario invalido passou")
except ValueError:
    pass
# versao dos amigos: nunca grava
assert "--sem-gravar" in P.montar_comando({**base, "gravar": True}, amigo=True)
assert P.instancias_do_alvo("S") == ["ESCORPIAO_REI", "DRAGAO_GELADO", "RAINHA_LIRIS"] and P.instancias_do_alvo("C") == ["PERICAO"]
# config antiga do painel (rota/avancado) migra
import json, tempfile
arq = os.path.join(tempfile.mkdtemp(), "p.json"); json.dump({"rota": "P", "cartas": ["X"], "avancado": True}, open(arq, "w"))
P.ARQ_CONFIG = arq
assert P.carregar()["alvo"] == "S" and "rota" not in P.carregar()

# os argumentos montados sao aceitos pelo navegador (nada de perguntas): rota/cartas/chefe
import navegador as N
assert N.rota_dos_argumentos("P")[1] == ["PERICAO"] and N.ler_horarios("12:00-13:00,21:00-22:00")
print("linha de comando OK")

# fumaca da janela com um tkinter falso (so pega erro de nome/atributo no nosso codigo)
tk = mock.MagicMock(); tk.TclError = Exception
var = lambda value=None: mock.MagicMock(get=mock.Mock(return_value=value))
tk.StringVar = lambda value="": var(value); tk.BooleanVar = lambda value=False: var(value)
ttk = mock.MagicMock(); msg = mock.MagicMock()
tkmod = types.ModuleType("tkinter"); tkmod.__dict__.update(tk=tk, ttk=ttk, messagebox=msg, TclError=Exception,
                                                              StringVar=tk.StringVar, BooleanVar=tk.BooleanVar, Tk=lambda *a, **k: mock.MagicMock(), Text=lambda *a, **k: mock.MagicMock(), Canvas=lambda *a, **k: mock.MagicMock())
tkmod.tk = tk
sys.modules["tkinter"] = tkmod
sys.modules["tkinter.ttk"] = ttk
sys.modules["tkinter.messagebox"] = msg
import painel
p = painel.Painel(mock.MagicMock())
cfg = p.config_atual()
assert cfg["alvo"] == "S" and cfg["horarios"] == "12:00-13:00,21:00-22:00", cfg
assert painel.Painel.etiqueta("[CHEFAO] hora do Chefao") == "chefe" and painel.Painel.etiqueta("   ! erro x") == "erro"
assert painel.Painel.etiqueta("[TEMPO] luta") == "tempo" and painel.Painel.etiqueta("banal") is None
with mock.patch.object(painel.subprocess, "Popen") as po:
    po.return_value.poll.return_value = None
    po.return_value.stdout = iter([])
    p.iniciar()
    assert po.called and po.call_args[0][0][2] == "navegador.py", po.call_args
print("painel (fumaca) OK")
assert painel.Painel.etiqueta("[ALERTA] preso em SALA") == "erro" and painel.Painel.etiqueta("[ERRO] falha") == "erro"
print("painel (alertas) OK")

# ---- empacotamento (BotDDT.exe): o mesmo exe faz tudo; dados ao lado do exe, templates de dentro do pacote
import importlib
import config as CFG
import painel_logica as PL
import botddt
chamados = []
sys.modules["navegador"] = types.SimpleNamespace(main=lambda: chamados.append(("navegador", list(sys.argv))))
botddt.main(["BotDDT.exe", "--navegador", "--atirar", "--rota", "S"])
assert chamados == [("navegador", ["navegador.py", "--atirar", "--rota", "S"])], chamados
del sys.modules["navegador"]
antes = (CFG.CONGELADO, sys.executable)
CFG.CONGELADO = True
try:
    c = PL.montar_comando(PL.PADRAO)
    assert c[0] == sys.executable and c[1] == "--navegador" and "-u" not in c, c
    assert PL.comando_base("empacotar") == [sys.executable, "--empacotar"]
finally:
    CFG.CONGELADO = antes[0]
src = open(os.path.join(os.path.dirname(AQUI), "config.py"), encoding="utf-8").read()
assert "_MEIPASS" in src and "PASTA_RECURSOS" in src
print("empacotamento (BotDDT.exe: entrada unica, comandos, caminhos) OK")

# ---- versao dos amigos: sem log/gravacao; so o resumo
sys.argv.append("--amigo")
try:
    pa = painel.Painel(mock.MagicMock())
    assert pa.amigo and pa.t_log is None and pa.t_rel is None and pa.cfg["gravar"] is False
    pa.escrever(None, "--- o bot caiu ---\n", "erro"); assert pa.aviso == "o bot caiu"
    pa.atualizar_relatorio()
    with mock.patch.object(painel.subprocess, "Popen") as po:
        po.return_value.poll.return_value = None
        po.return_value.stdout = iter([])
        pa.iniciar()
        assert "--sem-gravar" in po.call_args[0][0]
finally:
    sys.argv.remove("--amigo")
print("painel dos amigos OK")
