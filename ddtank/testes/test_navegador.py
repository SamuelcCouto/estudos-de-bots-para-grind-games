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
# cartas por visao: 21 de costas / 19 (2 abertas) / 0 reveladas
assert len(N.cartas_de_costas(img("CARTAS_COSTAS"))) == 21
assert len(N.cartas_de_costas(img("CARTAS_REVELADAS"))) == 0
# slots por cor: sala nova tem 3 abertas; sala com X tem 0
assert len(N.slots_abertos(img("SLOTS_ABERTOS"))) == 3 and len(N.slots_abertos(img("SALA_FINAL"))) == 0
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

def caixa_carta(c): return (c[0] - 40, c[1] - 55, c[0] + 40, c[1] + 55)

class Sim:
    """Jogo falso: cada tela tem um quadro real e regioes clicaveis que levam a outra tela.
    Cartas: o 1o clique numa carta so a "seleciona" (defeito real visto em jogo) se ignorar_1o=True."""
    def __init__(self, ignorar_1o=False):
        self.tela = "MAPA"; self.cap = 0; self.desde = 0; self.inst = 0
        self.instancias_clicadas = []; self.cliques = []; self.tarefas_ok = False; self.voltas = 0
        self.viradas = []; self.ignorar_1o = ignorar_1o; self.ja_ignorou = False
        self.slots = [True, True, True]          # True = aberto
        self.inicios_com_vaga_aberta = 0; self.cliques_em_slot_fechado = 0; self.jogar_cliques = 0
    def trocar(self, t): self.tela, self.desde = t, self.cap
    def quadro_cartas(self):
        f = img("CARTAS_COSTAS").copy(); rev = img("CARTAS_REVELADAS")
        for c in self.viradas:
            x0, y0, x1, y1 = caixa_carta(c); f[y0:y1, x0:x1] = rev[y0:y1, x0:x1]
        return f
    def quadro_sala(self, nome):
        f = img(nome).copy(); aberto = img("SLOTS_ABERTOS"); fechado = img("SALA_FINAL")
        for ab, c in zip(self.slots, N.SLOTS_SALA):
            x0, y0, x1, y1 = c[0] - 58, c[1] - 52, c[0] + 58, c[1] + 52
            f[y0:y1, x0:x1] = (aberto if ab else fechado)[y0:y1, x0:x1]
        return f
    def capturar(self):
        self.cap += 1; t = self.tela
        if t == "BATALHA" and self.cap - self.desde > 6: self.trocar("CARTAS"); t = "CARTAS"
        if t == "CARTAS" and len(self.viradas) >= 3 and self.cap - self.desde > 10: self.fim_cartas(); t = self.tela
        if t == "CARTAS": return self.quadro_cartas()
        if t == "PRONTA": return self.quadro_sala(["PRONTA_FANTASMA", "PRONTA_PROFUNDEZAS", "PRONTA_MINHOCAO"][self.inst])
        if t == "SALA_VAZIA" and self.inst >= 3: return img("SALA_FINAL")
        if t == "SALA_VAZIA": return self.quadro_sala("SALA_VAZIA")
        if t == "TAREFA": return img("TAREFA_SEM_OK" if self.tarefas_ok else "TAREFA_COM_OK")
        return img(t)
    def fim_cartas(self):
        self.viradas = []; self.ja_ignorou = False; self.inst += 1; self.trocar("SALA_VAZIA")
    def clicar(self, x, y, modo):
        p = (x, y); self.cliques.append((self.tela, p)); t = self.tela
        if t == "SALA_VAZIA": self.clique_slot(p)
        if t == "MAPA" and dentro(p, caixa(N.MAPA_CENTRAL)): self.trocar("CENTRAL")
        elif t == "CENTRAL" and dentro(p, caixa(N.CENTRAL_JOGAR)):
            self.jogar_cliques += 1
            self.trocar("SALA_VAZIA"); self.inst = 0; self.slots = [True, True, True]
        elif t == "SALA_VAZIA" and self.inst < 3 and dentro(p, caixa(N.SALA_TROCAR_INSTANCIA)): self.trocar("CONFIG_VAZIA")
        elif t == "SALA_VAZIA" and self.inst >= 3 and dentro(p, caixa(N.SALA_ICONE_TAREFAS)): self.trocar("TAREFA")
        elif t == "SALA_VAZIA" and self.inst >= 3 and self.tarefas_ok and dentro(p, caixa(N.SALA_TROCAR_INSTANCIA)):
            self.voltas += 1; self.tarefas_ok = False; self.inst = 0; self.trocar("CONFIG_VAZIA")   # mesma sala, nova volta
        elif t == "CONFIG_VAZIA":
            for nome, c in N.INSTANCIA_NA_CONFIG.items():
                if dentro(p, caixa(c, 30)): self.instancias_clicadas.append(nome); self.trocar("CONFIG_SEL")
        elif t == "CONFIG_SEL" and dentro(p, caixa(N.CONFIG_SIM, 60)): self.trocar("PRONTA")
        elif t == "PRONTA":
            self.clique_slot(p)
            if dentro(p, caixa(N.SALA_INICIO, 40)):
                self.inicios_com_vaga_aberta += any(self.slots); self.trocar("POPUP_SOZINHO")
        elif t == "POPUP_SOZINHO" and dentro(p, caixa(N.POPUP_SOZINHO_SIM, 40)): self.trocar("BATALHA")
        elif t == "CARTAS":
            for c in [(x, y) for y in N.CARTAS_LINHAS for x in N.CARTAS_COLUNAS]:
                if dentro(p, caixa_carta(c)) and c not in self.viradas:
                    if self.ignorar_1o and not self.ja_ignorou: self.ja_ignorou = True; return
                    if len(self.viradas) == 2: self.pendente = c; self.trocar("POPUP_CARTA")
                    else: self.viradas.append(c)
        elif t == "POPUP_CARTA" and dentro(p, caixa(N.POPUP_CARTA_SIM, 40)): self.viradas.append(self.pendente); self.trocar("CARTAS")
        elif t == "TAREFA" and not self.tarefas_ok and dentro(p, caixa(N.TAREFA_BOTAO, 50)): self.tarefas_ok = True
        elif t == "TAREFA" and self.tarefas_ok and dentro(p, caixa(N.TAREFA_FECHAR, 30)): self.trocar("SALA_VAZIA")
    def clique_slot(self, p):
        for k, c in enumerate(N.SLOTS_SALA):
            if dentro(p, (c[0] - 55, c[1] - 50, c[0] + 55, c[1] + 50)):
                if not self.slots[k]: self.cliques_em_slot_fechado += 1
                self.slots[k] = not self.slots[k]          # clicar de novo REABRE a vaga
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
    assert sim.inicios_com_vaga_aberta == 0, "iniciou a partida com vaga aberta"
    assert sim.cliques_em_slot_fechado == 0, "clicou numa vaga ja fechada (reabriria)"
    assert sim.jogar_cliques == 1, f"saiu e entrou na sala {sim.jogar_cliques}x (deveria entrar 1 vez so)"
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
for _ in range(8):
    e = nav.estado_estavel(); nav.agir(e)
    if sim.tela == "POPUP_SOZINHO": break
assert nav.idx == 1 and sim.tela == "POPUP_SOZINHO" and not any(sim.slots), (nav.idx, sim.tela, sim.slots)
print("adocao da instancia da sala OK")

# ---------------------------------------------------------------- 6) --simular nao clica
sim = Sim(); relogio = [0.0]
nav = N.Navegador(sim, det, simular=True, dormir=lambda s: relogio.__setitem__(0, relogio[0] + s), agora=lambda: relogio[0], log=lambda m: None)
nav.agir(nav.estado_estavel())
assert sim.cliques == []
print("modo simular OK (nenhum clique enviado)")

# ---------------------------------------------------------------- 7) defeito real: 1o clique em carta ignorado
sim = Sim(ignorar_1o=True); relogio = [0.0]
nav = N.Navegador(sim, det, dormir=lambda s: relogio.__setitem__(0, relogio[0] + s), agora=lambda: relogio[0], log=lambda m: None)
sim.tela = "CARTAS"; viu_popup = False; max_viradas = 0
for _ in range(40):
    e = nav.estado_estavel()
    if e == "POPUP_CARTA": viu_popup = True
    if e: nav.agir(e)
    max_viradas = max(max_viradas, len(sim.viradas))
    if sim.tela == "SALA_VAZIA": break
assert viu_popup, "com o 1o clique ignorado o bot nao chegou ao pop-up da 3a carta"
assert max_viradas == 3, max_viradas
print("cartas OK mesmo com o 1o clique ignorado (3 viradas, pop-up atendido)")
