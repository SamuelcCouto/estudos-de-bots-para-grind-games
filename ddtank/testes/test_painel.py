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
assert P.montar_comando({**base, "cartas": []})[P.montar_comando({**base, "cartas": []}).index("--cartas") + 1] == "NENHUMA"
c = P.montar_comando({**base, "rota": "C"})
assert "--cartas" not in c and "--chefe" not in c and c[c.index("--rota") + 1] == "C"
c = P.montar_comando({**base, "rota": "P", "gravacao_leve": True})
assert "--cartas" not in c and "--gravacao-leve" in c
assert P.montar_comando({**base, "rota": "T"})[5] == "T"
try:
    P.montar_comando({**base, "horarios": "banana"}); raise SystemExit("horario invalido passou")
except ValueError:
    pass

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
                                                              StringVar=tk.StringVar, BooleanVar=tk.BooleanVar, Tk=lambda *a, **k: mock.MagicMock(), Text=lambda *a, **k: mock.MagicMock())
tkmod.tk = tk
sys.modules["tkinter"] = tkmod
sys.modules["tkinter.ttk"] = ttk
sys.modules["tkinter.messagebox"] = msg
import painel
p = painel.Painel(mock.MagicMock())
cfg = p.config_atual()
assert cfg["rota"] == "S" and cfg["horarios"] == "12:00-13:00,21:00-22:00", cfg
assert painel.Painel.etiqueta("[CHEFAO] hora do Chefao") == "chefe" and painel.Painel.etiqueta("   ! erro x") == "erro"
assert painel.Painel.etiqueta("[TEMPO] luta") == "tempo" and painel.Painel.etiqueta("banal") is None
with mock.patch.object(painel.subprocess, "Popen") as po:
    po.return_value.poll.return_value = None
    po.return_value.stdout = iter([])
    p.iniciar()
    assert po.called and po.call_args[0][0][2] == "navegador.py", po.call_args
print("painel (fumaca) OK")
