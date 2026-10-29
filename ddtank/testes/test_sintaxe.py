# -*- coding: utf-8 -*-
"""Todo .py do bot compila (um sed meu ja deixou aspas dentro de aspas no empacotar.py e quebrou o envio)."""
import glob
import os
import py_compile
import sys
import tempfile

AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.dirname(AQUI)
ruins = []
for arq in sorted(glob.glob(os.path.join(RAIZ, "*.py")) + glob.glob(os.path.join(AQUI, "*.py"))):
    try:
        py_compile.compile(arq, cfile=os.path.join(tempfile.mkdtemp(), "x.pyc"), doraise=True)
    except py_compile.PyCompileError as e:
        ruins.append(str(e))
assert not ruins, "\n".join(ruins)
# o painel precisa importar (tkinter falso: o ambiente de teste nao tem)
print("sintaxe de todos os .py OK")
