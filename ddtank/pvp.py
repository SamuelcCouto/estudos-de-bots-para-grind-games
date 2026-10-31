# -*- coding: utf-8 -*-
"""
PVP (Combate Livre) - versao 1: o bot JOGA e GRAVA as tentativas; quem aprende com elas e a analise depois.

Uso: abra a sala de PVP no jogo (ou deixe na sala pronta) e rode `PVP.bat` (ou `python pvp.py`). O bot:
  - na SALA clica em Inicio (a cada ~12 s; `--sem-inicio` desliga), no pop-up "Clique no jogo" clica numa area neutra;
  - na BATALHA joga cada turno com o mesmo atirador das instancias (angulo pelas setas, forca segurando espaco), sem itens;
  - a cada tiro grava UMA linha em dados/pvp_tentativas.jsonl: angulo, forca, vento lido (e confianca), posicoes dos dois
    bonecos no minimapa, o que o previsor queria, e os prints do turno, do voo (ate 6) e do depois do tiro;
  - quando a partida acaba, grava um evento "partida" (duracao, tiros).
Ele NAO sabe se acertou (nao ha barra de vida de boss no PVP): o resultado de cada tiro se confere nos prints do voo.
Por isso a memoria de tiros NAO aprende nada aqui (so grava); depois da analise os acertos viram sementes.
Para a leitura do vento melhorar: recortes de leitura duvidosa vao para dados/pvp_vento_duvidoso/ (ver vento.py).
Para parar: F10, o botao PARAR do painel (logs/parar.flag) ou --minutos. F8 pausa/continua nao existe aqui (so PARAR).
"""
import argparse
import datetime
import json
import os
import sys
import time

import cv2
import numpy as np

import atirador as atirador_mod
import config
import estados as estados_mod
import leitura as L
import memoria as memoria_mod
import registro as registro_mod
import vento as vento_mod
from navegador import (ARQUIVO_PARAR, FOCO_PONTO_NEUTRO, FOCO_PONTO_PADRAO, SALA_INICIO, VK_F10, IOJanela, em_1280,
                       evitar_suspensao, instancia_unica)

INSTANCIA = "PVP"
ARQ_TENTATIVAS = os.path.join(config.PASTA, "dados", "pvp_tentativas.jsonl")
PASTA_VENTO_DUVIDOSO = os.path.join(config.PASTA, "dados", "pvp_vento_duvidoso")
LEITURAS_VENTO = 3                  # leituras do painel no comeco do turno (vota o valor mais comum)
INTERVALO_VOO = 0.8                 # s entre prints do voo do tiro
MAX_PRINTS_VOO = 6
INTERVALO_INICIO = 12.0             # s entre dois cliques em Inicio na sala
SETA_SERVIDOR = (885, 455, 925, 495)   # seta do botao "Mesmo servidor" (ao lado do Inicio): AZUL com a sala livre, CINZA enquanto busca partida
SETA_AZUL_LIVRE = 60                   # pixels azuis: livre ~114; buscando 0 (medido na gravacao 020551)
SETA_AZUL_BUSCANDO = 20
AVISO_BUSCA = 120.0                    # s entre avisos no log enquanto espera achar partida
SAIDA_BATALHA_S = 6.0               # s seguidos fora da batalha (e sem a sua vez) = a partida acabou (a tela pisca "desconhecida" no meio da luta)
BATIMENTO_S = 30.0                  # s entre linhas de status do log durante a batalha
MAPA_RECORTE = (638, 494, 834, 552)  # miniatura do mapa na tela VS (canto de baixo, "Arena"); (636, 458, 840, 556) inclui o nome
MAPA_NOME_RECORTE = (636, 458, 840, 556)
MAPA_DIST_MAX = 10                  # bits de diferenca (de 64) para ser o mesmo mapa
PASTA_MAPAS = os.path.join(config.PASTA, "dados", "pvp_mapas")
PRINTS_DO_PVP = ("turno_inicio", "tiro_dado", "turno_pulado", "voo", "pos_tiro", "partida_fim", "desconhecida", "mapa")


def pixels_azuis_seta(f):
    x0, y0, x1, y1 = SETA_SERVIDOR
    h = cv2.cvtColor(f[y0:y1, x0:x1], cv2.COLOR_BGR2HSV)
    return int(((h[..., 0] > 95) & (h[..., 0] < 125) & (h[..., 1] > 120) & (h[..., 2] > 120)).sum())


def sala_livre(f):
    """True: o botao e "Inicio" (da para clicar). False: virou "Cancele" (esta buscando partida - clicar CANCELA a busca) ou duvida."""
    return pixels_azuis_seta(f) >= SETA_AZUL_LIVRE


def sala_buscando(f):
    return pixels_azuis_seta(f) <= SETA_AZUL_BUSCANDO


def hash_mapa(f):
    """dHash de 64 bits da miniatura do mapa (tela VS): parecido mesmo com o fade-in da tela."""
    x0, y0, x1, y1 = MAPA_RECORTE
    g = cv2.cvtColor(f[y0:y1, x0:x1], cv2.COLOR_BGR2GRAY)
    p = cv2.resize(g, (9, 8), interpolation=cv2.INTER_AREA).astype(np.int16)
    bits = (p[:, 1:] > p[:, :-1]).ravel()
    return int("".join("1" if b else "0" for b in bits), 2)


def contraste_mapa(f):
    x0, y0, x1, y1 = MAPA_RECORTE
    return float(cv2.cvtColor(f[y0:y1, x0:x1], cv2.COLOR_BGR2GRAY).std())


class CatalogoMapas:
    """Mapas do PVP vistos na tela VS: cada um vira um id (m001, m002...) com a miniatura guardada em dados/pvp_mapas/.
    O nome do mapa a gente descobre depois olhando o PNG (e escreve em indice.json, campo "nome")."""
    def __init__(self, pasta=PASTA_MAPAS):
        self.pasta = pasta
        self.arq = os.path.join(pasta, "indice.json")
        self.mapas = json.load(open(self.arq, encoding="utf-8")) if os.path.exists(self.arq) else {}

    def identificar(self, f):
        """(id, novo?, quantas vezes ja visto) - registra o mapa se for novo."""
        h = hash_mapa(f)
        melhor = min(self.mapas.items(), key=lambda kv: bin(int(kv[1]["hash"], 16) ^ h).count("1"), default=None)
        if melhor and bin(int(melhor[1]["hash"], 16) ^ h).count("1") <= MAPA_DIST_MAX:
            mid = melhor[0]
            self.mapas[mid]["vistas"] += 1
            novo = False
        else:
            mid = f"m{len(self.mapas) + 1:03d}"
            self.mapas[mid] = {"hash": f"{h:016x}", "vistas": 1, "nome": None, "png": mid + ".png"}
            novo = True
            os.makedirs(self.pasta, exist_ok=True)
            x0, y0, x1, y1 = MAPA_NOME_RECORTE
            cv2.imwrite(os.path.join(self.pasta, mid + ".png"), f[y0:y1, x0:x1])
        try:
            os.makedirs(self.pasta, exist_ok=True)
            json.dump(self.mapas, open(self.arq, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        except OSError:
            pass
        return mid, novo, self.mapas[mid]["vistas"]


class RegistroPvp(registro_mod.Registro):
    """Como o Registro, mas so grava os prints do PVP (turno, voo, depois do tiro): uma hora inteira fica em dezenas de MB."""
    def frame(self, img, rotulo):
        if rotulo not in PRINTS_DO_PVP:
            return None
        self.leve = False
        return super().frame(img, rotulo)


class LeitorPvp(atirador_mod.LeitorReal):
    """No PVP nao ha barra de vida de boss nem itens/especial das instancias: o atirador joga so mira + forca."""
    vida = staticmethod(lambda f: 100.0)
    itens = staticmethod(lambda f: [False] * 8)
    pow_cheio = staticmethod(lambda f: False)
    buff_pet = staticmethod(lambda f: False)
    e_disponivel = staticmethod(lambda f: False)
    numeros_dano = staticmethod(lambda f: 0)
    vento = staticmethod(vento_mod.ler_vento)


def votar_vento(leituras):
    """leituras: [(valor, confianca)]. Devolve (valor mais votado, confianca media dele, quantos votos) ou (None, 0, 0)."""
    votos = {}
    for v, c in leituras:
        if v is not None:
            votos.setdefault(round(v, 1), []).append(c)
    if not votos:
        return None, 0.0, 0
    v, cs = max(votos.items(), key=lambda kv: (len(kv[1]), sum(kv[1])))
    return v, sum(cs) / len(cs), len(cs)


class AtiradorPvp(atirador_mod.Atirador):
    def __init__(self, *a, arq_tentativas=ARQ_TENTATIVAS, pasta_vento=PASTA_VENTO_DUVIDOSO, **kw):
        kw.setdefault("leitor", LeitorPvp())
        kw.setdefault("ordem_itens", [])
        super().__init__(*a, **kw)
        self.arq_tentativas = arq_tentativas
        self.pasta_vento = pasta_vento
        self.vento_turno = (None, 0.0, 0)
        self.tiros_na_partida = 0
        self.partidas = 0
        self.inicio_partida = None
        self._voo_n, self._voo_t = 0, -99.0
        self.vento_duvidoso_salvos = 0
        self.mapa = None

    # ------------------------------------------------------------------ vento
    def ler_vento(self, f):
        leituras = [self.lei.vento(f)]
        for _ in range(LEITURAS_VENTO - 1):
            self.dormir(0.15)
            g = self.ver()
            if g is not None:
                leituras.append(self.lei.vento(g))
        v, conf, votos = votar_vento(leituras)
        if v is not None and (not vento_mod.confiavel(conf) or votos < 2):
            self._guardar_duvidoso(f, v, conf)
        return v, conf, votos

    def _guardar_duvidoso(self, f, v, conf):
        try:
            os.makedirs(self.pasta_vento, exist_ok=True)
            nome = f"{datetime.datetime.now():%Y%m%d_%H%M%S}_{self.turnos}_lido_{v:+.1f}_conf{conf:.2f}.png"
            cv2.imwrite(os.path.join(self.pasta_vento, nome), vento_mod.recorte(f))
            self.vento_duvidoso_salvos += 1
        except OSError:
            pass

    # ------------------------------------------------------------------ turno / tiro
    def turno(self, f):
        if self.inicio_partida is None:
            self.inicio_partida = self.agora()
        self.vento_turno = self.ler_vento(f)
        v, conf, votos = self.vento_turno
        self.log(f"   [vento] {'?' if v is None else f'{v:+.1f}'} (confianca {conf:.2f}, {votos} leitura(s) iguais)"
                 f"{'' if v is None or vento_mod.confiavel(conf) else ' - DUVIDOSO: recorte salvo para rotular'}")
        antes = self.turnos
        super().turno(f)
        if self.pendente is not None and self.turnos > antes:
            self.pendente["vento"] = self.vento_turno
            self.pendente["quando"] = datetime.datetime.now().isoformat(timespec="seconds")
            self._voo_n, self._voo_t = 0, -99.0

    def passo(self, f=None):
        f = self.ver() if f is None else self.lei.preparar(f)
        if f is not None:
            self._amostrar_voo(f)
        super().passo(f)

    def _amostrar_voo(self, f):
        p = self.pendente
        if not p or not self.reg:
            return
        dt = self.agora() - p["t"]
        if 0.4 <= dt <= 9.0 and self._voo_n < MAX_PRINTS_VOO and self.agora() - self._voo_t >= INTERVALO_VOO:
            nome = self.reg.frame(f, "voo")
            p.setdefault("voo", []).append(nome)
            self._voo_n += 1
            self._voo_t = self.agora()

    def concluir_tiro(self, f):
        """Sem barra de vida no PVP nao da para saber o resultado aqui: so grava a tentativa (a analise confere nos prints)."""
        p, self.pendente = self.pendente, None
        if p is None:
            return
        pos = self.reg.frame(f, "pos_tiro") if (self.reg and f is not None) else None
        self.tiros_na_partida += 1
        v, conf, votos = p.get("vento", (None, 0.0, 0))
        linha = {"quando": p.get("quando"), "sessao": getattr(self.reg, "pasta", None) and os.path.basename(self.reg.pasta),
                 "partida": self.partidas + 1, "mapa": self.mapa, "tiro": self.tiros_na_partida, "angulo": round(float(p["angulo"]), 1),
                 "forca": round(float(p["forca"]), 1), "vento": v, "vento_conf": round(conf, 2), "vento_votos": votos,
                 "azul": p.get("azul"), "boss": p.get("boss"), "voo": p.get("voo", []), "pos_tiro": pos,
                 "origem_previsao": None}
        self.log(f"   [tentativa {self.partidas + 1}.{self.tiros_na_partida}] {linha['angulo']:.0f} graus, forca {linha['forca']:.0f}%, "
                 f"vento {'?' if v is None else f'{v:+.1f}'}, voce {p.get('azul')} inimigo {p.get('boss')} (resultado: ver os prints)")
        try:
            os.makedirs(os.path.dirname(self.arq_tentativas), exist_ok=True)
            with open(self.arq_tentativas, "a", encoding="utf-8") as fh:
                fh.write(json.dumps(linha, ensure_ascii=False, default=float) + "\n")
        except OSError as e:
            self.log(f"   ! nao consegui gravar a tentativa: {e}")
        if self.reg:
            self.reg.evento("pvp_tiro", [pos] + list(p.get("voo", [])), **{k: v_ for k, v_ in linha.items() if k not in ("voo", "pos_tiro")})

    def fim_da_partida(self, f=None):
        """A batalha acabou: fecha o tiro pendente (so grava) e zera o estado para a proxima partida."""
        if self.pendente is not None:
            self.concluir_tiro(f)
        dur = None if self.inicio_partida is None else self.agora() - self.inicio_partida
        self.partidas += 1
        self.log(f"=== partida {self.partidas} acabou: {self.tiros_na_partida} tiro(s), {0 if dur is None else dur:.0f}s ===")
        if self.reg:
            self.reg.evento("partida", [self.reg.frame(f, "partida_fim")] if f is not None else [], numero=self.partidas, mapa=self.mapa,
                            tiros=self.tiros_na_partida, duracao_s=None if dur is None else round(dur, 1))
        self.tiros_na_partida, self.inicio_partida = 0, None
        self.fim_da_batalha(venceu=False)             # zera rastreador/estado (venceu=False: nao registra acerto)


# ------------------------------------------------------------------------------------------------------ laco principal
class Laco:
    def __init__(self, io, det, atirador, log=print, clicar_inicio=True, agora=None, dormir=None, catalogo=None, reg=None):
        self.io, self.det, self.at, self.log = io, det, atirador, log
        self.clicar_inicio = clicar_inicio
        self.catalogo, self.reg = catalogo, reg
        self.agora = agora or time.time
        self.dormir = dormir or time.sleep
        self.em_batalha = False
        self.fora_desde = None
        self.ultimo_inicio = -1e9
        self.buscando_desde = None
        self.ultimo_aviso = 0.0
        self.ultimo_estado = None
        self.ultima_vez = None
        self.ultimo_batimento = 0.0
        self.melhor_mapa = None            # (contraste, quadro) da tela VS (o fade-in deixa os primeiros quadros escuros)
        self.parar = False

    def _guardar_mapa(self, f):
        c = contraste_mapa(f)
        if self.melhor_mapa is None or c > self.melhor_mapa[0]:
            self.melhor_mapa = (c, f.copy())

    def _fechar_mapa(self):
        """Saiu da tela VS: identifica o mapa pelo melhor quadro e avisa o atirador."""
        if self.melhor_mapa is None:
            return
        _c, f = self.melhor_mapa
        self.melhor_mapa = None
        if self.catalogo is None:
            return
        mid, novo, vistas = self.catalogo.identificar(f)
        self.at.mapa = mid
        self.log(f"(mapa {mid}: {'NOVO, miniatura guardada em dados/pvp_mapas' if novo else f'ja visto {vistas}x'})")
        if self.reg:
            self.reg.evento("mapa", [self.reg.frame(f, "mapa")], mapa=mid, novo=novo, vistas=vistas)

    def passo(self):
        img = self.io.capturar()
        if img is None:
            return
        f = em_1280(img)
        achadas = self.det.detectar(estados_mod.normalizar(f))
        estado = achadas[0] if achadas else None
        vez = bool(L.minha_vez(f))
        agora = self.agora()
        if estado != self.ultimo_estado:
            self.log(f"(tela: {estado or 'desconhecida'})")
            self.ultimo_estado = estado
        if estado == "VS_PVP":
            self._guardar_mapa(f)
            return
        self._fechar_mapa()
        if estado == "BATALHA" or vez:
            if not self.em_batalha:
                self.log("(partida comecou)")
                self.ultima_vez = None
            self.em_batalha, self.fora_desde = True, None
            if vez != self.ultima_vez:
                self.log("(SUA VEZ)" if vez else "(vez do adversario: espero)")
                self.ultima_vez = vez
            if agora - self.ultimo_batimento >= BATIMENTO_S:
                self.ultimo_batimento = agora
                self.log(f"(em batalha: {'sua vez' if vez else 'vez do adversario'}; tiros nesta partida: {self.at.tiros_na_partida})")
            self.at.passo(f)
            return
        if self.em_batalha:
            if self.fora_desde is None:
                self.fora_desde = agora
            elif agora - self.fora_desde >= SAIDA_BATALHA_S:
                self.at.fim_da_partida(f)
                self.em_batalha = False
        if estado == "CLIQUE_JOGO":
            por_baixo = next((e for e in achadas if e != "CLIQUE_JOGO"), None)
            self.io.clicar_ref(*FOCO_PONTO_NEUTRO.get(por_baixo, FOCO_PONTO_PADRAO))
            self.dormir(1.0)
        elif estado == "SALA" and self.clicar_inicio:
            if sala_livre(f):
                self.buscando_desde = None
                if agora - self.ultimo_inicio >= INTERVALO_INICIO:
                    self.ultimo_inicio = agora
                    self.log("(sala: clicando em Inicio para buscar partida)")
                    self.io.clicar_ref(*SALA_INICIO)
                    self.dormir(2.0)
            elif sala_buscando(f):
                if self.buscando_desde is None:
                    self.buscando_desde, self.ultimo_aviso = agora, agora
                    self.log("(buscando partida: o botao virou Cancele - NAO clico; espero achar)")
                elif agora - self.ultimo_aviso >= AVISO_BUSCA:
                    self.ultimo_aviso = agora
                    self.log(f"(ainda buscando partida ha {(agora - self.buscando_desde) / 60:.0f} min; continuo esperando)")

    def rodar(self, ate=None, arquivo_parar=ARQUIVO_PARAR):
        while not self.parar:
            if ate is not None and self.agora() >= ate:
                self.log("tempo acabou.")
                break
            if arquivo_parar and os.path.exists(arquivo_parar):
                try:
                    os.remove(arquivo_parar)
                except OSError:
                    pass
                self.log("Parada pedida pelo painel.")
                break
            if hasattr(self.io, "tecla_apertada") and self.io.tecla_apertada(VK_F10):
                self.log("F10: parando.")
                break
            self.passo()
            self.dormir(0.25)


def main():
    import janela
    ap = argparse.ArgumentParser(description="DDTank - PVP: joga e grava as tentativas")
    ap.add_argument("--titulo", default="")
    ap.add_argument("--exe", default="")
    ap.add_argument("--minutos", type=float, default=60.0, help="para sozinho depois desse tempo (padrao 60; 0 = sem limite)")
    ap.add_argument("--sem-inicio", action="store_true", help="nao clica em Inicio na sala (voce inicia as partidas)")
    ap.add_argument("--sombra", action="store_true", help="so mostra o tiro que faria (nao aperta teclas) e grava os prints")
    ap.add_argument("--foco", type=int, choices=(0, 1, 2), default=1)
    ap.add_argument("--sem-calibrar", action="store_true")
    args = ap.parse_args()
    if not instancia_unica():
        sys.exit("ERRO: ja existe um bot (navegador/atirador) rodando. Feche os outros antes.")
    titulo, exe = args.titulo or config.TITULO_JANELA, args.exe or config.EXE_JANELA
    hwnd = janela.resolver_janela(titulo, exe)
    if not hwnd:
        sys.exit("Janela do jogo nao encontrada. Rode LISTAR_JANELAS.bat.")
    if janela.contar_janelas(titulo, exe) > 1:
        sys.exit("ERRO: ha mais de uma janela do jogo aberta. Deixe so uma.")
    io = IOJanela(hwnd, calibrar=not args.sem_calibrar)
    io.foco_nivel = args.foco
    det = estados_mod.Detector()
    evitar_suspensao()
    os.makedirs(config.PASTA_LOGS, exist_ok=True)
    arq = open(os.path.join(config.PASTA_LOGS, f"pvp_{datetime.datetime.now():%Y%m%d}.log"), "a", encoding="utf-8")

    def log(msg):
        linha = f"[{datetime.datetime.now():%H:%M:%S}] {msg}"
        print(linha, flush=True)
        arq.write(linha + "\n")
        arq.flush()
    io.log = log
    reg = RegistroPvp("pvp")
    log(f"PVP: gravando em {reg.pasta} e em {ARQ_TENTATIVAS}. Janela: {janela.descrever_janela(hwnd)}")
    at = AtiradorPvp(io, memoria_mod.Memoria(), lambda: INSTANCIA, sombra=args.sombra, log=log, reg=reg)
    laco = Laco(io, det, at, log=log, clicar_inicio=not args.sem_inicio, catalogo=CatalogoMapas(), reg=reg)
    ate = time.time() + args.minutos * 60 if args.minutos else None
    try:
        laco.rodar(ate=ate)
    except KeyboardInterrupt:
        log("Parado pelo usuario.")
    finally:
        if laco.em_batalha:
            at.fim_da_partida()
        log(f"PVP: {at.partidas} partida(s) gravadas; recortes de vento duvidosos salvos: {at.vento_duvidoso_salvos}.")
        reg.fechar()
        print(f"Gravacao salva em {reg.pasta}. Para me mandar: botao 'Enviar gravacao' do painel (ou EMPACOTAR_E_ENVIAR.bat); "
              f"(os dados de cada tiro e os prints vao dentro dela; dados\\pvp_tentativas.jsonl fica so no seu disco).")


if __name__ == "__main__":
    main()
