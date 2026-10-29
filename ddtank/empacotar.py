# -*- coding: utf-8 -*-
"""
Empacota uma sessao gravada em zips pequenos para enviar.

  python empacotar.py                  (usa a sessao mais recente em sessoes\\)
  python empacotar.py sessoes\\2026...  (uma sessao especifica)
  python empacotar.py --tudo           (todos os prints, sem selecao)

Reduz os quadros para 1280x720 (JPEG) e divide em partes de ate 20 MB (limite do GitHub: 100 MB).
Saida: ddtank/envio/<sessao>_parte1.zip ...

Sessao longa do bot (horas): o texto vai INTEIRO (eventos, resumo, relatorio, log), mas os prints vao SELECIONADOS
para o envio nao virar gigabytes: tudo dos primeiros MINUTOS_COMPLETOS, todos os turnos de tiro, todos os problemas
(com os prints dos SEGUNDOS_ANTES_DO_PROBLEMA anteriores). O resto continua no seu disco (sessoes\\).
"""
import glob
import json
import os
import sys
import zipfile

import cv2

import config

LIMITE = 20 * 1024 * 1024
MINUTOS_COMPLETOS = 15
SEGUNDOS_ANTES_DO_PROBLEMA = 25
EVENTOS_TURNO = {"turno", "turno_aviao", "turno_sombra", "turno_pulado"}
EVENTOS_PROBLEMA = {"ordem_sem_cartas", "cartas_incompletas", "recuperacao", "desconhecida", "clique_sem_efeito",
                    "turno_pulado"}


def selecionar_prints(sessao):
    """Nomes dos prints que vao no envio (None = todos)."""
    arq = os.path.join(sessao, "eventos.jsonl")
    if not os.path.exists(arq):
        return None
    evs = []
    for linha in open(arq, encoding="utf-8"):
        try:
            evs.append(json.loads(linha))
        except ValueError:
            pass
    problemas = [e["t"] for e in evs if e.get("tipo") in EVENTOS_PROBLEMA]
    sel = set()
    for e in evs:
        t = e.get("t", 0)
        fr = e.get("frames") or []
        if (t <= MINUTOS_COMPLETOS * 60 or e.get("tipo") in EVENTOS_PROBLEMA
                or any(0 <= p - t <= SEGUNDOS_ANTES_DO_PROBLEMA for p in problemas)):
            sel.update(fr)
        elif e.get("tipo") in EVENTOS_TURNO:
            sel.update(f for f in fr if "turno_inicio" in f or "tiro_dado" in f)   # inicio e fim de cada turno
    return sel


def sessao_mais_recente():
    base = os.path.join(config.PASTA, "sessoes")
    if not os.path.isdir(base):
        sys.exit("Nao ha pasta sessoes\\. Grave uma sessao primeiro (gravador.py).")
    pastas = sorted(p for p in os.listdir(base) if os.path.isdir(os.path.join(base, p)))
    if not pastas:
        sys.exit("Nenhuma sessao encontrada.")
    return os.path.join(base, pastas[-1])


def sessoes_novas():
    """Todas as sessoes que ainda nao foram empacotadas (sem o marcador .enviada), da mais antiga a mais nova."""
    base = os.path.join(config.PASTA, "sessoes")
    if not os.path.isdir(base):
        return []
    return [os.path.join(base, p) for p in sorted(os.listdir(base))
            if os.path.isdir(os.path.join(base, p, "frames")) and not os.path.exists(os.path.join(base, p, ".enviada"))]


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    tudo = "--tudo" in sys.argv
    if "--novas" in sys.argv:
        # a gravacao da SUA jogada pode nao ser a mais recente (o bot rodou depois): empacota todas as que ainda nao foram
        novas = sessoes_novas()
        if not novas:
            print("Nenhuma sessao nova para empacotar.")
            return
        print(f"{len(novas)} sessao(oes) nova(s): " + ", ".join(os.path.basename(p) for p in novas))
        for p in novas:
            empacotar_sessao(p, tudo)
            open(os.path.join(p, ".enviada"), "w").close()
        return
    empacotar_sessao(args[0] if args else sessao_mais_recente(), tudo)


def empacotar_sessao(sessao, tudo):
    frames = os.path.join(sessao, "frames")
    saida = os.path.join(config.PASTA, "envio")
    os.makedirs(saida, exist_ok=True)
    nome = os.path.basename(os.path.normpath(sessao))
    arquivos = sorted(os.listdir(frames))
    sel = None if tudo else selecionar_prints(sessao)
    if sel is not None:
        print(f"Prints selecionados: {sum(f in sel for f in arquivos)} de {len(arquivos)} (texto completo; use --tudo para todos)")
        arquivos = [f for f in arquivos if f in sel]
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
        # artes de instancias que o bot aprendeu sozinho (Rota Sul...) e o que ele aprendeu dos tiros: viram oficiais
        aprendidos = os.path.join(config.PASTA, "dados", "modelos_aprendidos")
        if parte == 1 and os.path.isdir(aprendidos):
            for arq in sorted(os.listdir(aprendidos)):
                zf.write(os.path.join(aprendidos, arq), f"{nome}/modelos_aprendidos/{arq}")
        tiros = os.path.join(config.PASTA, "dados", "aprendizado.json")
        if parte == 1 and os.path.exists(tiros):
            zf.write(tiros, f"{nome}/aprendizado.json")
        # cronometro/placar (logs\relatorio.txt, lutas.csv, voltas.csv), combos aprendidos e o log do console do dia
        if parte == 1:
            extras = [os.path.join(config.PASTA_LOGS, a) for a in ("relatorio.txt", "lutas.csv", "voltas.csv", "teste_tela.txt", "teste_tela.png")]
            extras.append(os.path.join(config.PASTA, "dados", "combos.json"))
            dia = os.path.basename(os.path.normpath(sessao))[:8]
            extras += sorted(glob.glob(os.path.join(config.PASTA_LOGS, f"navegador_{dia}*.log")))
            for arq in extras:
                if os.path.exists(arq):
                    zf.write(arq, f"{nome}/logs/{os.path.basename(arq)}")

    abrir()
    for f in arquivos:
        img = cv2.imread(os.path.join(frames, f))
        if img is None:
            continue
        if img.shape[1] > 1280:
            img = cv2.resize(img, (1280, int(img.shape[0] * 1280 / img.shape[1])), interpolation=cv2.INTER_AREA)
        ok, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 85 if (tudo or sel is None) else 75])
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
    print('Para enviar: botao "Enviar gravacao" do BotDDT.')


if __name__ == "__main__":
    main()
