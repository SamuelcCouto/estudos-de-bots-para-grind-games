# -*- coding: utf-8 -*-
"""
Ponto de entrada do BotDDT.exe (PyInstaller): o MESMO executavel abre o painel e, com um argumento, faz o trabalho dos
outros programas (o painel roda o bot como um processo filho do proprio .exe):
    BotDDT.exe                  painel
    BotDDT.exe --navegador ...  o bot (navegador.py --atirar ...)
    BotDDT.exe --gravador       grava a sua jogada
    BotDDT.exe --empacotar ...  empacota a gravacao para envio
Rodando do codigo-fonte (python botddt.py) funciona igual.
"""
import multiprocessing
import sys


def main(argv):
    modo = argv[1] if len(argv) > 1 else ""
    if modo in ("--navegador", "--gravador", "--empacotar"):
        modulo = modo[2:]
        sys.argv = [modulo + ".py"] + argv[2:]
        __import__(modulo).main()
    else:
        import painel
        painel.main()


if __name__ == "__main__":
    multiprocessing.freeze_support()
    main(sys.argv)
