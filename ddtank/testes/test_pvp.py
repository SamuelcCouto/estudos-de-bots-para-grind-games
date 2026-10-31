# -*- coding: utf-8 -*-
"""PVP v1: leitor de vento, votacao, atirador que so grava as tentativas e o laco da sala/batalha. Rode: python testes/test_pvp.py"""
import json
import os
import sys
import tempfile

import numpy as np

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(AQUI))
import memoria as M
import pvp as P
import vento as V

# ------------------------------------------------------------ 1) leitor de vento
d = V.carregar()
assert len(d["crops"]) >= 300
quadro = np.zeros((688, 1280, 3), np.uint8)
x0, y0, x1, y1 = V.RECORTE
for i in (3, 60, 150, 200, 240, 300):                      # recortes conhecidos (+, -, cada digito) postos no lugar do painel
    quadro[y0:y1, x0:x1] = d["crops"][i]
    v, c = V.ler_vento(quadro)
    assert abs(v - float(d["valores"][i])) < 0.05, (i, v, d["valores"][i])
quadro[y0:y1, x0:x1] = d["crops"][0]                        # "0.0" fantasma entre rodadas
assert V.ler_vento(quadro)[0] is None
ok, tot = V.avaliar_sem_o_proprio_trecho()                  # cada trecho de vento fora do treino: so o que ainda nao viu
assert ok / tot >= 0.62, (ok, tot)
print(f"vento: {ok}/{tot} = {ok / tot:.0%} com trechos nunca vistos (e 100% nos ja vistos) OK")
assert P.votar_vento([(1.5, 1.2), (1.5, 1.1), (1.1, 1.3)])[:1] == (1.5,) and P.votar_vento([(None, 0), (None, 0)]) == (None, 0.0, 0)

# ------------------------------------------------------------ 2) atirador PVP so grava (nao aprende, nao registra acerto)
src = open(os.path.join(AQUI, "test_atirador.py"), encoding="utf-8").read()
ns = {"__file__": os.path.join(AQUI, "test_atirador.py")}
exec(compile(src.split("# ------------------------------------------------------------ 1) turno completo")[0], "test_atirador.py", "exec"), ns)
Mundo, MundoComThread, Leitor = ns["Mundo"], ns["MundoComThread"], ns["Leitor"]

class LeitorT(Leitor):
    vida = staticmethod(lambda f: 100.0)
    itens = staticmethod(lambda f: [False] * 8)
    vento = staticmethod(lambda f: (-1.5, 1.4))

def novo(mundo):
    tmp = tempfile.mkdtemp()
    arq_mem = os.path.join(tmp, "aprendizado.json")
    mem = M.Memoria(arq_aprendizado=arq_mem)
    logs = []
    at = P.AtiradorPvp(mundo, mem, lambda: "PVP", leitor=LeitorT(), dormir=mundo.dormir, agora=lambda: mundo.t, log=logs.append,
                       arq_tentativas=os.path.join(tmp, "t.jsonl"), pasta_vento=os.path.join(tmp, "v"))
    return at, mem, logs, tmp

w = MundoComThread()
at, mem, logs, tmp = novo(w)
while w.t < 16.0:
    at.passo(); w.avancar(0.1)
print("\n".join(logs))
assert len(w.tiros) == 1 and w.itens_apertados == [], (w.tiros, w.itens_apertados)     # joga mira + forca, sem itens
linhas = [json.loads(l) for l in open(os.path.join(tmp, "t.jsonl"), encoding="utf-8")]
assert len(linhas) == 1 and linhas[0]["vento"] == -1.5 and linhas[0]["tiro"] == 1 and linhas[0]["azul"], linhas
assert abs(linhas[0]["angulo"] - w.angulo) < 1.0 and linhas[0]["forca"] > 0
assert not os.path.exists(mem.arq_aprendizado) and mem.novos == [], "o PVP nao pode gravar acerto/erro na memoria (nao sabe o resultado)"
print("atirador PVP: 1 tiro sem itens, tentativa gravada com vento e posicoes; memoria intacta OK")

# fim de partida com tiro no ar: grava e NAO conta como acerto
w = MundoComThread(); at, mem, logs, tmp = novo(w)
while w.t < 7.5:
    at.passo(); w.avancar(0.1)
assert at.pendente is not None
at.fim_da_partida()
assert at.partidas == 1 and not os.path.exists(mem.arq_aprendizado)
assert len(open(os.path.join(tmp, "t.jsonl"), encoding="utf-8").read().splitlines()) == 1
print("fim da partida com tiro no ar: grava a tentativa, sem aprender OK")

# ------------------------------------------------------------ 3) laco: sala -> Inicio; pop-up -> clique neutro; batalha -> atirador
class DetFalso:
    def __init__(self): self.estado = "SALA"
    def detectar(self, g): return [self.estado] if self.estado else []

class IOFalso:
    def __init__(self): self.cliques = []; self.livre = True
    def capturar(self):
        img = np.zeros((688, 1280, 3), np.uint8)
        if self.livre:                                       # seta azul do "Mesmo servidor" = sala livre (Inicio); cinza = buscando
            x0, y0, x1, y1 = P.SETA_SERVIDOR
            img[y0 + 5:y1 - 5, x0 + 5:x1 - 5] = (255, 80, 0)
        return img
    def clicar_ref(self, x, y, modo="top"): self.cliques.append((x, y))

class AtFalso:
    def __init__(self): self.passos = 0; self.fins = 0; self.tiros_na_partida = 0; self.mapa = None; self.turnos_feitos_na_vez = 0
    def passo(self, f): self.passos += 1
    def fim_da_partida(self, f=None): self.fins += 1

io, det, at = IOFalso(), DetFalso(), AtFalso()
t = [0.0]
laco = P.Laco(io, det, at, log=lambda m: None, agora=lambda: t[0], dormir=lambda s: t.__setitem__(0, t[0] + s))
laco.passo()
assert io.cliques == [P.SALA_INICIO], io.cliques
laco.passo()
assert len(io.cliques) == 1, "nao pode clicar Inicio de novo antes de INTERVALO_INICIO"
t[0] += P.INTERVALO_INICIO + 1
laco.passo()
assert len(io.cliques) == 2
io.livre = False                                          # clicou em Inicio e o botao virou "Cancele": buscando partida
t[0] += 3 * P.INTERVALO_INICIO
for _ in range(5):
    laco.passo()
assert len(io.cliques) == 2, "enquanto busca partida NAO pode clicar (clicar em Cancele cancela a busca)"
assert laco.buscando_desde is not None
io.livre = True                                           # busca terminou/cancelada: volta a Inicio
t[0] += P.INTERVALO_INICIO + 1
laco.passo()
assert len(io.cliques) == 3 and laco.buscando_desde is None
det.estado = "CLIQUE_JOGO"; laco.passo()
assert io.cliques[-1] == P.FOCO_PONTO_PADRAO
det.estado = "BATALHA"
for _ in range(3): laco.passo()
assert at.passos == 3 and laco.em_batalha
det.estado = "CARTAS_P"
laco.passo()
assert at.fins == 0, "uma tela estranha de 1 s no meio da luta NAO e fim de partida"
det.estado = None; laco.passo(); det.estado = "BATALHA"; laco.passo()
assert at.fins == 0 and laco.fora_desde is None
det.estado = "CARTAS_P"
for _ in range(int(P.SAIDA_BATALHA_S / 0.25) + 3):
    laco.passo(); t[0] += 0.25
assert at.fins == 1 and not laco.em_batalha
laco2 = P.Laco(io, DetFalso(), AtFalso(), log=lambda m: None, clicar_inicio=False, agora=lambda: 1e6, dormir=lambda s: None)
n = len(io.cliques); laco2.passo()
assert len(io.cliques) == n, "--sem-inicio nao clica"
print("laco (Inicio com intervalo, pop-up, batalha, fim de partida, --sem-inicio) OK")
# ------------------------------------------------------------ 4) mapa da tela VS: id estavel, mesmo mapa com fade-in, outro mapa = outro id
import cv2
cat = P.CatalogoMapas(pasta=os.path.join(tempfile.mkdtemp(), "mapas"))
base = np.full((688, 1280, 3), 40, np.uint8)
x0, y0, x1, y1 = P.MAPA_RECORTE
rng = np.random.default_rng(1)
miniatura = cv2.GaussianBlur(rng.integers(0, 255, (y1 - y0, x1 - x0, 3), dtype=np.uint8), (0, 0), 3)
outra = cv2.GaussianBlur(rng.integers(0, 255, (y1 - y0, x1 - x0, 3), dtype=np.uint8), (0, 0), 3)
q1 = base.copy(); q1[y0:y1, x0:x1] = miniatura
q_escuro = base.copy(); q_escuro[y0:y1, x0:x1] = (miniatura * 0.45).astype(np.uint8)     # fade-in da tela
q2 = base.copy(); q2[y0:y1, x0:x1] = outra
m1, novo1, _ = cat.identificar(q1)
m1b, novo1b, v = cat.identificar(q_escuro)
m2, novo2, _ = cat.identificar(q2)
assert novo1 and m1b == m1 and not novo1b and v == 2, (m1, m1b)
assert novo2 and m2 != m1
assert os.path.exists(os.path.join(cat.pasta, m1 + ".png")) and P.CatalogoMapas(pasta=cat.pasta).mapas[m1]["vistas"] == 2
laco3 = P.Laco(IOFalso(), DetFalso(), AtFalso(), log=lambda m: None, catalogo=cat, agora=lambda: 0.0, dormir=lambda s: None)
laco3.det.estado = "VS_PVP"; laco3.io.capturar = lambda: q1
laco3.passo(); laco3.passo()
laco3.det.estado = "BATALHA"; laco3.io.capturar = lambda: base; laco3.passo()
assert laco3.at.mapa == m1, laco3.at.mapa
print("mapas (id estavel mesmo com fade, miniatura guardada, ligado a partida) OK")
# ------------------------------------------------------------ 5) vigias: vez que so pisca, tela desconhecida, busca eterna, angulos em rodizio
import estados as E
import leitura as LE
vez_real = {"v": False}
orig_vez = P.pontuacao_pass
P.pontuacao_pass = lambda f: 0.9 if vez_real["v"] else 0.1
try:
    logs5 = []
    io5, det5, at5 = IOFalso(), DetFalso(), AtFalso()
    t5 = [0.0]
    l5 = P.Laco(io5, det5, at5, log=logs5.append, agora=lambda: t5[0], dormir=lambda s: t5.__setitem__(0, t5[0] + s))
    det5.estado = "BATALHA"
    for _ in range(P.VEZES_CURTAS_ALERTA):                 # PASS pisca e some, o bot nunca chega a agir
        vez_real["v"] = True; l5.passo(); t5[0] += 0.4
        vez_real["v"] = False; l5.passo(); t5[0] += 5
    assert any("ALERTA: varias vezes" in m for m in logs5), logs5
    # tela desconhecida por muito tempo fora da batalha -> clique neutro
    l6 = P.Laco(IOFalso(), DetFalso(), AtFalso(), log=lambda m: None, agora=lambda: t5[0], dormir=lambda s: None)
    l6.det.estado = None
    l6.passo()
    t5[0] += P.PRESO_S + 1
    l6.passo()
    assert l6.io.cliques == [P.FOCO_PONTO_PADRAO], l6.io.cliques
    # busca parada por mais de 10 min -> cancela (clique no botao) e volta a buscar
    io7 = IOFalso(); io7.livre = False
    l7 = P.Laco(io7, DetFalso(), AtFalso(), log=lambda m: None, agora=lambda: t5[0], dormir=lambda s: None)
    l7.passo()
    assert io7.cliques == []
    t5[0] += P.LIMITE_BUSCA_S + 1
    l7.passo()
    assert io7.cliques == [P.SALA_INICIO] and l7.buscando_desde is None
finally:
    P.pontuacao_pass = orig_vez
mp = P.MemoriaPvp(arq_aprendizado=None)
angs = [mp.prever("PVP", (74.0, 56.0), (13.0, 54.0))["angulo"] for _ in range(len(P.ANGULOS_PVP))]
assert angs == list(P.ANGULOS_PVP), angs
assert all(8 <= mp.prever("PVP", (74.0, 56.0), (13.0, 54.0))["forca"] <= 95 for _ in range(6))
print("vigias (vez curta, tela desconhecida, busca eterna) e angulos em rodizio OK")
# erro inesperado no passo nao derruba o laco
class LacoQuebrado(P.Laco):
    n = 0
    def passo(self):
        LacoQuebrado.n += 1
        if LacoQuebrado.n <= 3:
            raise ValueError("falha de teste")
        self.parar = True
lq = LacoQuebrado(IOFalso(), DetFalso(), AtFalso(), log=lambda m: None, agora=lambda: 0.0, dormir=lambda s: None)
lq.rodar(arquivo_parar=None)
assert LacoQuebrado.n == 4, "deveria sobreviver a 3 erros e seguir"
print("falha inesperada nao derruba o laco OK")
# ------------------------------------------------------------ 6) fisica das tabelas, histerese da vez, E/F/itens
for ang, d, f_tab in ((50, 12, 53), (30, 10, 47), (65, 5, 37), (50, 20, 72), (30, 3, 24)):
    assert abs(P.forca_tabela(d, ang) - f_tab) <= 4, (ang, d, P.forca_tabela(d, ang), f_tab)
mp = P.MemoriaPvp(arq_aprendizado=None)
pr = mp.prever("PVP", (20.0, 50.0), (68.0, 50.0))        # inimigo no mesmo nivel, 48 px = 12 unidades (escala 4)
assert pr["origem"] == "pvp-tabela" and 45 <= pr["forca"] <= 70, pr
mais_baixo = mp.melhor_tiro("PVP", 48.0, -20.0, angulo=45.0)[1]
plano = mp.melhor_tiro("PVP", 48.0, 0.0, angulo=45.0)[1]
assert mais_baixo < plano, "alvo mais baixo pede menos forca"
mp.escala = 3.0
assert mp.melhor_tiro("PVP", 48.0, 0.0, angulo=45.0)[1] > plano, "escala menor (mapa 'apertado') = mais unidades = mais forca"
print("fisica das tabelas (forca por distancia/angulo, alvo mais baixo, escala por mapa) OK")

relogio = [100.0]
notas = {"n": 0.9}
orig_nota = P.pontuacao_pass
P.pontuacao_pass = lambda f: notas["n"]
try:
    lp = P.LeitorPvp(agora=lambda: relogio[0])
    assert lp.minha_vez(None)
    notas["n"] = 0.45                                        # a nota cai por 1 quadro no voo do tiro
    relogio[0] += 0.5
    assert lp.minha_vez(None), "uma queda curta da nota NAO e o fim da vez (era o que fazia atirar 2x no mesmo turno)"
    relogio[0] += P.HOLD_VEZ_S
    assert not lp.minha_vez(None)
finally:
    P.pontuacao_pass = orig_nota
print("vez com histerese OK")

w = MundoComThread()
at, mem, logs, tmp = novo(w)
at.rastreador.boss = (80.0, 50.0)
assert at.plano_aviao("PVP", (30.0, 50.0), 100.0) is None and at.y_ref == 50.0          # nada de errado: atira normal
assert at.plano_aviao("PVP", (30.0, 59.0), 100.0)[0] > 30.0 and at.motivo_aviao == "chao cedeu"    # desceu 9 px: aviao para o lado do inimigo
at.rastreador.boss = (10.0, 50.0)
dest = at.plano_aviao("PVP", (30.0, 59.0), 100.0)
assert dest and dest[0] < 30.0, "inimigo a esquerda: voa para a esquerda"
at.ultimo_aviao_tiro, at.tiros_na_partida = 5, 6
assert at.plano_aviao("PVP", (30.0, 59.0), 100.0) is None, "espera INTERVALO_AVIAO_TIROS tiros entre avioes"
at.tiros_na_partida = 9
at.y_ref = 59.0
at.limite_recente = True
assert at.plano_aviao("PVP", (30.0, 59.0), 100.0) and at.motivo_aviao == "angulo no limite"
at.y_ref = 59.0
at.rastreador.boss = (95.0, 59.0)
assert at.plano_aviao("PVP", (30.0, 59.0), 100.0) and at.motivo_aviao == "inimigo longe"
at.aviao_indisponivel = True
assert at.plano_aviao("PVP", (30.0, 59.0), 100.0) is None
print("aviao F (chao cedeu / angulo no limite / inimigo longe, intervalo, desistir) OK")

class LeitorItens(LeitorT):
    itens = staticmethod(lambda f: [True] * 8)
    e_disponivel = staticmethod(lambda f: not w2.e_apertado)
w2 = MundoComThread()
w2.e_apertado = False
orig_tecla = w2.tecla
def tecla_e(nome, dur=0.05):
    if nome == "e":
        w2.e_apertado = True
    orig_tecla(nome, dur)
w2.tecla = tecla_e
at2, mem2, logs2, tmp2 = novo(w2)
at2.lei = LeitorItens()
while w2.t < 16.0:
    at2.passo(); w2.avancar(0.1)
assert at2.e_usos == 1 and any("[E] usado" in l for l in logs2), logs2
assert at2.ordem == list(P.ORDENS_PVP[0]) and at2.itens_ultimo, (at2.ordem, at2.itens_ultimo)
linhas2 = [json.loads(l) for l in open(os.path.join(tmp2, "t.jsonl"), encoding="utf-8")]
assert linhas2 and linhas2[0]["itens"] == at2.itens_ultimo and 2 in linhas2[0]["itens"], linhas2
print("E (so com o slot verde) e itens por turno gravados OK")
print("\npvp OK")
