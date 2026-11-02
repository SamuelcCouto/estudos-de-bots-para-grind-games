# -*- coding: utf-8 -*-
"""
Extrai o cliente Flash do DDTank Betel que JA esta no computador (nao baixa o jogo) e os dados publicos de fisica.

O BetelTank.exe e um Electron com o plugin Pepper Flash 32 (resources/plugins/64bit.dll). O cliente guarda os arquivos que baixa
como SharedObjects do Flash (%APPDATA%/BetelTank/Pepper Data/.../#SharedObjects/flash-55-prod.ddtankbetel.com/*.sol): ~300 SWFs
sem criptografia (so compactados, "CWS"). O nucleo do jogo e o maior que contem as classes phy.*, game.*, road7th.comm.*.

Uso (na pasta ddtank):
    python estudos/extrair_cliente.py                      # extrai SWFs + baixa balllist/loadmapsitems/bombconfig
    python estudos/extrair_cliente.py --ffdec CAMINHO\\ffdec-cli.jar   # tambem descompila os pacotes de fisica/rede/jogo

Saida (fora do git: o codigo e os dados sao do jogo):
    cliente_extraido/swf/*.swf, cliente_extraido/nucleo.swf, cliente_extraido/fonte/scripts/... (com --ffdec)
    dados/jogo/balllist.xml, loadmapsitems.xml, bombconfig.xml
Descompilador: JPEXS FFDec (https://github.com/jindrapetrik/jpexs-decompiler, codigo aberto; precisa de Java 8+).
"""
import argparse
import os
import re
import struct
import subprocess
import urllib.request
import zlib

PASTA = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SOL = os.path.join(os.environ.get("APPDATA", ""), "BetelTank", "Pepper Data", "Shockwave Flash", "WritableRoot", "#SharedObjects")
SAIDA = os.path.join(PASTA, "cliente_extraido")
DADOS = os.path.join(PASTA, "dados", "jogo")
URL_DADOS = "https://quest-55-sockets.ddtankbetel.com/{}.xml?rnd=0.5"       # os mesmos que o cliente baixa (zlib)
MARCAS_NUCLEO = (b"phy.math:EulerVector", b"road7th.comm:ByteSocket", b"game.view:GameView")
PACOTES = ("phy.**,game.objects.**,game.model.**,game.actions.**,game.view.map.**,game.view.smallMap.**,game.view.EnergyView,"
           "game.view.GameView,game.view.RouteComputer,game.GameManager,road7th.comm.**,ddt.data.socket.**,ddt.data.BallInfo,"
           "ddt.data.map.**,ddt.manager.SocketManager,ddt.manager.GameSocketOut,ddt.manager.GameInSocketOut,ddt.manager.PathManager,"
           "ddt.manager.BallManager,ddt.manager.MapManager")


def extrair_swfs():
    os.makedirs(os.path.join(SAIDA, "swf"), exist_ok=True)
    n, nucleo = 0, None
    for raiz, _d, arqs in os.walk(SOL):
        for a in arqs:
            if not a.endswith(".sol"):
                continue
            b = open(os.path.join(raiz, a), "rb").read()
            m = re.search(rb"CWS[\x06-\x30]", b)
            if not m:
                continue
            i = m.start()
            if not 1000 < struct.unpack("<I", b[i + 4:i + 8])[0] < 80_000_000:
                continue
            try:
                raw = zlib.decompressobj().decompress(b[i + 8:])
            except zlib.error:
                continue
            fws = b"FWS" + b[i + 3:i + 4] + struct.pack("<I", len(raw) + 8) + raw
            nome = re.sub(r"[^\w\-]", "", os.path.basename(raiz))[:40] or "swf"
            destino = os.path.join(SAIDA, "swf", f"{nome}_{n:03d}.swf")
            open(destino, "wb").write(fws)
            n += 1
            if all(k in raw for k in MARCAS_NUCLEO) and (nucleo is None or len(fws) > os.path.getsize(nucleo)):
                nucleo = destino
    if nucleo:
        open(os.path.join(SAIDA, "nucleo.swf"), "wb").write(open(nucleo, "rb").read())
    print(f"{n} SWFs extraidos; nucleo do jogo: {nucleo}")
    return nucleo


def baixar_dados():
    os.makedirs(DADOS, exist_ok=True)
    for nome in ("balllist", "loadmapsitems", "bombconfig"):
        req = urllib.request.Request(URL_DADOS.format(nome), headers={"User-Agent": "Mozilla/5.0"})
        bruto = urllib.request.urlopen(req, timeout=30).read()
        try:
            texto = zlib.decompress(bruto)
        except zlib.error:
            texto = bruto
        open(os.path.join(DADOS, nome + ".xml"), "wb").write(texto)
        print(f"dados/jogo/{nome}.xml: {len(texto)} bytes")


def descompilar(ffdec, nucleo):
    cmd = ["java", "-jar", ffdec, "-selectclass", PACOTES, "-export", "script", os.path.join(SAIDA, "fonte"), nucleo]
    subprocess.run(cmd, check=True)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--ffdec", default="", help="caminho do ffdec-cli.jar (JPEXS) para descompilar o nucleo")
    ap.add_argument("--sem-dados", action="store_true")
    a = ap.parse_args()
    nuc = extrair_swfs()
    if not a.sem_dados:
        baixar_dados()
    if a.ffdec and nuc:
        descompilar(a.ffdec, nuc)
