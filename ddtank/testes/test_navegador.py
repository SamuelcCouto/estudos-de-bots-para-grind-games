# -*- coding: utf-8 -*-
"""Testes sem o jogo: detector de telas e o navegador contra um simulador feito com quadros reais.
Rode:  python testes/test_navegador.py"""
import os
import sys

import cv2

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(AQUI))
import estados as E
import navegador as N

FR = os.path.join(AQUI, "frames")
img = lambda nome: cv2.imread(os.path.join(FR, nome + ".jpg"))
det = E.Detector()

# ---------------------------------------------------------------- 1) detector
ESPERADO = {"CLIQUE_JOGO": "CLIQUE_JOGO", "MAPA": "MAPA", "CENTRAL": "CENTRAL", "SALA_VAZIA": "SALA_VAZIA",
            "CONFIG_VAZIA": "CONFIG_VAZIA", "CONFIG_SEL": "CONFIG_SEL", "PRONTA_FANTASMA": "PRONTA_FANTASMA",
            "POPUP_SOZINHO": "POPUP_SOZINHO", "BATALHA": "BATALHA", "CARTAS": "CARTAS", "POPUP_CARTA": "POPUP_CARTA",
            "PRONTA_PROFUNDEZAS": "PRONTA_PROFUNDEZAS", "PRONTA_MINHOCAO": "PRONTA_MINHOCAO", "SALA_FINAL": "SALA_VAZIA",
            "TAREFA_COM_OK": "TAREFA", "TAREFA_SEM_OK": "TAREFA", "TAREFA_ATIVA_OK": "TAREFA", "TAREFA_SUPER": "TAREFA"}
ruim = 0
for nome, esp in ESPERADO.items():
    got = det.detectar(E.normalizar(img(nome)))
    ok = bool(got) and got[0] == esp
    ruim += not ok
    print(("ok   " if ok else "ERRO ") + f"{nome:20s} -> {got}")
assert not det.detectar(E.normalizar(img("DESCONHECIDA"))), "tela preta nao pode ser reconhecida"
assert not ruim, f"{ruim} telas erradas"
print("detector OK\n")

# ---------------------------------------------------------------- 2) selos / botao de tarefas
assert N.botao_recompensa_ativo(img("TAREFA_COM_OK")) and not N.botao_recompensa_ativo(img("TAREFA_SEM_OK"))
assert len(N.selos_ok(img("TAREFA_COM_OK"))) == 2 and len(N.selos_ok(img("TAREFA_SEM_OK"))) == 0
print("tarefas OK\n")

# ---------------------------------------------------------------- 3) simulador do jogo
def dentro(p, caixa, margem=0):
    x, y = p
    x0, y0, x1, y1 = caixa
    return x0 - margem <= x <= x1 + margem and y0 - margem <= y <= y1 + margem

def caixa(c, r=45): return (c[0] - r, c[1] - r, c[0] + r, c[1] + r)

class Sim:
    """Jogo falso: cada tela tem um quadro real e regioes clicaveis que levam a outra tela."""
    def __init__(self):
        self.tela = "MAPA"; self.cap = 0; self.desde = 0; self.cartas = 0; self.inst = 0
        self.instancias_clicadas = []; self.cliques = []; self.tarefas_ok = False; self.voltas = 0
        self.teclas = {}
    def trocar(self, t): self.tela, self.desde = t, self.cap
    def capturar(self):
        self.cap += 1; t = self.tela
        if t == "BATALHA" and self.cap - self.desde > 6: self.trocar("CARTAS"); t = "CARTAS"
        if t == "CARTAS" and self.cartas >= 3 and self.cap - self.desde > 8: self.fim_cartas(); t = self.tela
        nome = t
        if t == "PRONTA": nome = ["PRONTA_FANTASMA", "PRONTA_PROFUNDEZAS", "PRONTA_MINHOCAO"][self.inst]
        elif t == "SALA_VAZIA" and self.inst >= 3: nome = "SALA_FINAL"
        elif t == "TAREFA": nome = "TAREFA_SEM_OK" if self.tarefas_ok else "TAREFA_COM_OK"
        return img(nome)
    def fim_cartas(self):
        self.cartas = 0; self.inst += 1; self.trocar("SALA_VAZIA")
    def clicar(self, x, y, modo):
        p = (x, y); self.cliques.append((self.tela, p)); t = self.tela
        if t == "MAPA" and dentro(p, caixa(N.MAPA_CENTRAL)): self.trocar("CENTRAL")
        elif t == "CENTRAL" and dentro(p, caixa(N.CENTRAL_JOGAR)): self.trocar("SALA_VAZIA"); self.inst = 0
        elif t == "SALA_VAZIA" and self.inst < 3 and dentro(p, caixa(N.SALA_TROCAR_INSTANCIA)): self.trocar("CONFIG_VAZIA")
        elif t == "SALA_VAZIA" and self.inst >= 3 and dentro(p, caixa(N.SALA_ICONE_TAREFAS)): self.trocar("TAREFA")
        elif t == "SALA_VAZIA" and self.inst >= 3 and self.tarefas_ok and dentro(p, caixa(N.SALA_PORTA)):
            self.trocar("CENTRAL"); self.voltas += 1; self.tarefas_ok = False
        elif t == "CONFIG_VAZIA":
            for nome, c in N.INSTANCIA_NA_CONFIG.items():
                if dentro(p, caixa(c, 30)): self.instancias_clicadas.append(nome); self.trocar("CONFIG_SEL")
        elif t == "CONFIG_SEL" and dentro(p, caixa(N.CONFIG_SIM, 60)): self.trocar("PRONTA")
        elif t == "PRONTA" and dentro(p, caixa(N.SALA_INICIO, 40)): self.trocar("POPUP_SOZINHO")
        elif t == "POPUP_SOZINHO" and dentro(p, caixa(N.POPUP_SOZINHO_SIM, 40)): self.trocar("BATALHA")
        elif t == "CARTAS" and any(dentro(p, caixa(c, 40)) for c in N.CARTAS_PARA_ABRIR):
            self.cartas += 1
            if self.cartas == 3: self.trocar("POPUP_CARTA")
        elif t == "POPUP_CARTA" and dentro(p, caixa(N.POPUP_CARTA_SIM, 40)): self.trocar("CARTAS")
        elif t == "TAREFA" and not self.tarefas_ok and dentro(p, caixa(N.TAREFA_BOTAO, 50)): self.tarefas_ok = True
        elif t == "TAREFA" and self.tarefas_ok and dentro(p, caixa(N.TAREFA_FECHAR, 30)): self.trocar("SALA_VAZIA")
    def tecla_apertada(self, vk): return False

for modo_k in (1.0,):
    sim = Sim()
    relogio = [0.0]
    def dormir(s): relogio[0] += s
    def agora(): return relogio[0]
    nav = N.Navegador(sim, det, uma_vez=False, dormir=dormir, agora=agora, log=lambda m: None)
    # roda ate completar 2 voltas
    passos = 0
    while sim.voltas < 2 and passos < 600:
        e = nav.estado_estavel()
        if e: nav.agir(e)
        passos += 1
    print("passos:", passos, "voltas completas:", sim.voltas)
    print("instancias escolhidas:", sim.instancias_clicadas)
    assert sim.voltas == 2, "nao completou 2 voltas"
    assert sim.instancias_clicadas == ["FANTASMA", "PROFUNDEZAS", "MINHOCAO"] * 2
    sem_efeito = [c for c in sim.cliques]
    print("total de cliques:", len(sim.cliques))
print("\nsimulador OK: o navegador percorreu a rota (3 instancias + cartas + tarefas + Central) 2 vezes seguidas")

# ---------------------------------------------------------------- 4) clique que nao chega: troca o modo de entrada
class SimSoFilha(Sim):
    """So reage a cliques no modo 'filha' (como se o jogo ignorasse a janela principal)."""
    def clicar(self, x, y, modo):
        self.modos = getattr(self, "modos", []) + [modo]
        if modo == "filha": super().clicar(x, y, modo)
sim = SimSoFilha(); relogio = [0.0]
nav = N.Navegador(sim, det, dormir=lambda s: relogio.__setitem__(0, relogio[0] + s), agora=lambda: relogio[0], log=lambda m: None)
for _ in range(40):
    e = nav.estado_estavel()
    if e: nav.agir(e)
    if sim.tela != "MAPA": break
assert sim.tela != "MAPA", "nao saiu do mapa"
assert nav.modo == 1 and "top" in sim.modos and "filha" in sim.modos
print("troca de modo OK (top -> filha apos cliques sem efeito)")

# ---------------------------------------------------------------- 5) comecar no meio: sala ja em Profundezas
sim = Sim(); sim.tela = "PRONTA"; sim.inst = 1; relogio = [0.0]
nav = N.Navegador(sim, det, dormir=lambda s: relogio.__setitem__(0, relogio[0] + s), agora=lambda: relogio[0], log=lambda m: None)
e = nav.estado_estavel(); nav.agir(e)
assert nav.idx == 1 and sim.tela == "POPUP_SOZINHO", (nav.idx, sim.tela)
print("adocao da instancia da sala OK")

# ---------------------------------------------------------------- 6) --simular nao clica
sim = Sim(); relogio = [0.0]
nav = N.Navegador(sim, det, simular=True, dormir=lambda s: relogio.__setitem__(0, relogio[0] + s), agora=lambda: relogio[0], log=lambda m: None)
nav.agir(nav.estado_estavel())
assert sim.cliques == []
print("modo simular OK (nenhum clique enviado)")
