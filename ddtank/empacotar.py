# -*- coding: utf-8 -*-
"""
Empacota uma sessao gravada em zips pequenos para enviar.

  python empacotar.py                  (usa a sessao mais recente em sessoes\\)
  python empacotar.py sessoes\\2026...  (uma sessao especifica)

Reduz os quadros para 1280x720 (JPEG) e divide em partes de ate 20 MB (limite do GitHub: 100 MB).
Saida: ddtank/envio/<sessao>_parte1.zip ...
"""
import os
import sys
import zipfile

import cv2

import config

LIMITE = 20 * 1024 * 1024


def sessao_mais_recente():
    base = os.path.join(config.PASTA, "sessoes")
    if not os.path.isdir(base):
        sys.exit("Nao ha pasta sessoes\\. Grave uma sessao primeiro (gravador.py).")
    pastas = sorted(p for p in os.listdir(base) if os.path.isdir(os.path.join(base, p)))
    if not pastas:
        sys.exit("Nenhuma sessao encontrada.")
    return os.path.join(base, pastas[-1])


def main():
    sessao = sys.argv[1] if len(sys.argv) > 1 else sessao_mais_recente()
    frames = os.path.join(sessao, "frames")
    saida = os.path.join(config.PASTA, "envio")
    os.makedirs(saida, exist_ok=True)
    nome = os.path.basename(os.path.normpath(sessao))
    arquivos = sorted(os.listdir(frames))
    parte, usado, zf = 0, 0, None

    def abrir():
        nonlocal parte, usado, zf
        if zf:
            zf.close()
        parte += 1
        usado = 0
        zf = zipfile.ZipFile(os.path.join(saida, f"{nome}_parte{parte}.zip"), "w", zipfile.ZIP_STORED)
        for txt in ("eventos.jsonl", "resumo.txt", "meta.json"):
            caminho = os.path.join(sessao, txt)
            if os.path.exists(caminho):
                zf.write(caminho, f"{nome}/{txt}")

    abrir()
    for f in arquivos:
        img = cv2.imread(os.path.join(frames, f))
        if img is None:
            continue
        if img.shape[1] > 1280:
            img = cv2.resize(img, (1280, int(img.shape[0] * 1280 / img.shape[1])), interpolation=cv2.INTER_AREA)
        ok, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 85])
        if usado + len(buf) > LIMITE:
            abrir()
        zf.writestr(f"{nome}/frames/{os.path.splitext(f)[0]}.jpg", buf.tobytes())
        usado += len(buf)
    zf.close()
    print(f"Pronto! {parte} arquivo(s) em: {saida}")
    try:
        os.startfile(saida)   # abre a pasta no Explorer
    except (AttributeError, OSError):
        pass
    print("Para enviar: de dois cliques em ENVIAR_SESSAO.bat (usa git).")


if __name__ == "__main__":
    main()
