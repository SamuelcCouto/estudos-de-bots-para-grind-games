# -*- coding: utf-8 -*-
"""
DDTank - fase 1: achar a janela do launcher, capturar a tela e mandar cliques/teclas
sem usar o seu mouse. Ainda NAO joga: serve para confirmar que o bot enxerga e controla o jogo.

Comandos:
  python bot_ddtank.py --listar                  lista as janelas abertas (achar titulo/exe)
  python bot_ddtank.py --diagnostico             captura e diz se a imagem esta boa
  python bot_ddtank.py --print                   salva uma captura em capturas/
  python bot_ddtank.py --gravar 2 --n 30         salva 30 capturas, uma a cada 2 s
  python bot_ddtank.py --clicar 960 540          clique de teste na janela
  python bot_ddtank.py --tecla espaco --segundos 1.5   segura uma tecla (teste de forca)
Use --titulo "..." e/ou --exe "..." para escolher a janela (ou preencha config.py).
"""
import argparse
import datetime
import os
import sys
import time

import cv2
import numpy as np

import config
import janela


def achar(args):
    titulo = args.titulo or config.TITULO_JANELA
    exe = args.exe or config.EXE_JANELA
    hwnd = janela.resolver_janela(titulo, exe)
    if not hwnd:
        sys.exit(f"Janela do jogo nao encontrada (titulo='{titulo}', exe='{exe}'). "
                 "Rode --listar e use --titulo/--exe (ou preencha config.py).")
    return hwnd


def salvar(img, prefixo="captura"):
    os.makedirs(config.PASTA_CAPTURAS, exist_ok=True)
    caminho = os.path.join(config.PASTA_CAPTURAS,
                           f"{prefixo}_{datetime.datetime.now():%Y%m%d_%H%M%S_%f}.png")
    cv2.imwrite(caminho, img)
    return caminho


def cmd_listar(_):
    print(f"{'HWND':>10}  {'TAMANHO':>11}  {'EXE':<28} TITULO")
    for j in sorted(janela.listar_janelas(), key=lambda j: -j["w"] * j["h"]):
        print(f"{j['hwnd']:>10}  {j['w']:>5}x{j['h']:<5}  {j['exe']:<28} {j['titulo']}")


def veredito(img):
    if img is None:
        return "sem imagem (janela minimizada ou pequena demais)"
    m, desvio = img.mean(), img.std()
    if m < 3 and desvio < 3:
        return "PRETA (a captura nao enxerga o jogo)"
    if m > 252 and desvio < 3:
        return "BRANCA (janela ainda nao desenhou)"
    return "OK (tem conteudo)"


def cmd_diagnostico(args):
    hwnd = achar(args)
    w, h = janela.tamanho(hwnd)
    print(f"Janela hwnd={hwnd}, area cliente {w}x{h} (ideal: 1920x1080, escala do Windows em 100%).")
    for modo in ("print", "tela"):
        img = janela.capturar(hwnd, modo)
        if img is None:
            print(f"  modo '{modo}': {veredito(img)}")
            continue
        print(f"  modo '{modo}': {veredito(img)} -> {salvar(img, 'diag_' + modo)}")
    print("Me mande os PNGs de capturas/ (e o texto acima). Se 'print' deu preto e 'tela' deu OK,"
          " usaremos o modo 'tela'.")


def cmd_print(args):
    img = janela.capturar(achar(args), args.modo)
    if img is None:
        sys.exit("Nao consegui capturar.")
    print(veredito(img), "->", salvar(img))


def cmd_gravar(args):
    hwnd = achar(args)
    for i in range(args.n):
        img = janela.capturar(hwnd, args.modo)
        if img is not None:
            print(f"[{i + 1}/{args.n}] {salvar(img, 'seq')}")
        time.sleep(args.gravar)


def cmd_clicar(args):
    hwnd = achar(args)
    x, y = args.clicar
    janela.clicar(hwnd, x, y)
    time.sleep(0.8)
    img = janela.capturar(hwnd, args.modo)
    if img is not None:
        cv2.circle(img, (x, y), 18, (0, 0, 255), 3)
        print(f"Clicou em ({x},{y}). Captura depois do clique (alvo marcado): {salvar(img, 'clique')}")


def cmd_tecla(args):
    hwnd = achar(args)
    print(f"Segurando '{args.tecla}' por {args.segundos}s...")
    janela.tecla(hwnd, args.tecla, args.segundos)
    time.sleep(0.5)
    img = janela.capturar(hwnd, args.modo)
    if img is not None:
        print("Captura depois:", salvar(img, "tecla"))


def cmd_teste_forca(args):
    """Diagnostico: na SUA vez, segura o espaco 1,0 s de duas formas e le a barra de forca (esperado ~38%)."""
    import navegador as N
    import leitura as L
    io = N.IOJanela(achar(args))

    def esperar_vez():
        t0 = time.time()
        while time.time() - t0 < 120:
            img = io.capturar()
            if img is not None and L.minha_vez(N.em_1280(img)):
                time.sleep(0.6)
                return True
            time.sleep(0.2)
        return False

    print("Entre numa batalha e espere a SUA vez (aparece o botao PASS). O teste dispara 2 tiros de forca baixa.")
    for nome, repeticao in (("COM repeticao automatica de tecla (a cada 30 ms)", True), ("SEM repeticao (um unico KEYDOWN)", False)):
        print(f"\nAguardando a sua vez... ({nome})")
        if not esperar_vez():
            sys.exit("A sua vez nao chegou em 2 minutos.")
        if repeticao:
            io.segurar("espaco"); time.sleep(1.0); io.soltar("espaco")
        else:
            io.tecla_baixo("espaco", 1); time.sleep(1.0); io.tecla_cima("espaco")
        time.sleep(0.4)
        v = L.forca(N.em_1280(io.capturar()))
        foco = "SIM" if io.em_foco() else "NAO (outra janela na frente)"
        print(f"  segurou 1,0 s {nome}: barra em {v:.0f}%   (esperado ~38%)   | jogo em primeiro plano: {foco}")
    print("\nMe mande essas duas linhas. Se o jogo NAO estava em primeiro plano, rode de novo clicando no jogo antes de cada tiro.")


def main():
    ap = argparse.ArgumentParser(description="DDTank - fase 1 (captura e controle da janela)")
    ap.add_argument("--titulo", default="")
    ap.add_argument("--exe", default="")
    ap.add_argument("--modo", choices=("print", "tela"), default="print")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--listar", action="store_true")
    g.add_argument("--diagnostico", action="store_true")
    g.add_argument("--print", dest="print_", action="store_true")
    g.add_argument("--gravar", type=float, metavar="SEGUNDOS")
    g.add_argument("--clicar", type=int, nargs=2, metavar=("X", "Y"))
    g.add_argument("--tecla", metavar="NOME")
    g.add_argument("--teste-forca", dest="teste_forca", action="store_true", help="diagnostico da barra de forca (numa batalha)")
    ap.add_argument("--n", type=int, default=20, help="quantas capturas no --gravar")
    ap.add_argument("--segundos", type=float, default=1.0, help="quanto segurar a --tecla")
    args = ap.parse_args()
    if args.listar:
        cmd_listar(args)
    elif args.teste_forca:
        cmd_teste_forca(args)
    elif args.diagnostico:
        cmd_diagnostico(args)
    elif args.print_:
        cmd_print(args)
    elif args.gravar is not None:
        cmd_gravar(args)
    elif args.clicar:
        cmd_clicar(args)
    else:
        cmd_tecla(args)


if __name__ == "__main__":
    main()
