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
            "TAREFA_COM_OK": "TAREFA", "TAREFA_SEM_OK": "TAREFA", "TAREFA_ATIVA_OK": "TAREFA", "TAREFA_SUPER": "TAREFA",
            "CFG_SEL_ESCORPIAO": "CONFIG_SEL", "SALA_ESCORPIAO": "SALA",
            # 28/10 21h: outro boneco/visual no painel "Informacoes do usuario" (o recorte antigo pegava o retrato)
            "CENTRAL_OUTRO_BONECO": "CENTRAL",
            # 29/10 12h: o bot ficou 55 min parado - confirmacao do Pericao com outro texto, e o aviso do chefao por cima
            "POPUP_SOZINHO_CHEFE": "POPUP_SOZINHO2", "POPUP_AVISO_CHEFE": "POPUP_AVISO"}
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
        self.tela = "MAPA"; self.cap = 0; self.desde = 0; self.inst = 0; self.aba = "normal"
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
        if t == "CONFIG_VAZIA" and self.aba == "evento": return img("CFG_EVENTO_VAZIA")
        if t == "CONFIG_SEL": return img("CFG_SEL_" + self.instancias_clicadas[-1])
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
            for aba, c in N.ABAS_CONFIG.items():
                if dentro(p, (c[0] - 30, c[1] - 12, c[0] + 30, c[1] + 12)): self.aba = aba; return
            for nome, c in N.INSTANCIA_NA_CONFIG.items():       # so os quadros da aba aberta
                if N.ABA_DA_INSTANCIA.get(nome, "normal") == self.aba and dentro(p, caixa(c, 30)):
                    self.instancias_clicadas.append(nome); self.trocar("CONFIG_SEL"); break
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

# ---------------------------------------------------------------- 8) integracao com o atirador
class AtiradorFalso:
    def __init__(self): self.passos = 0; self.fins = 0
    def passo(self, f=None): self.passos += 1
    def fim_da_batalha(self): self.fins += 1
sim = Sim(); relogio = [0.0]; falso = AtiradorFalso()
nav = N.Navegador(sim, det, atirador=falso, dormir=lambda s: relogio.__setitem__(0, relogio[0] + s), agora=lambda: relogio[0], log=lambda m: None)
sim.tela = "POPUP_SOZINHO"
for _ in range(80):
    nav.teclas = lambda: None
    e = nav.estado_estavel() if not (nav.atirador and nav.em_batalha) else None
    if e: nav.agir(e); continue
    # mesmo ramo do laco principal
    f, achadas = nav.ver()
    if achadas and achadas[0] == "BATALHA": nav.atirador.passo(f); continue
    nav.dormir(1.0)
    if sim.tela != "BATALHA" and nav.em_batalha: nav.em_batalha = False; nav.atirador.fim_da_batalha(); break
assert falso.passos > 3 and falso.fins == 1, (falso.passos, falso.fins)
print("integracao navegador+atirador OK (passos na batalha:", falso.passos, ")")

# ---------------------------------------------------------------- 9) a sala CONTINUA mostrando a ultima instancia depois das cartas
class Sim2(Sim):
    """Depois das cartas a sala volta mostrando a instancia que acabou de ser jogada (nao a tela 'Selecione')."""
    def __init__(self):
        super().__init__()
        self.sala_inst = None; self.lutas = []; self.escolhida = None; self.sala_fica = True
    def quadro_pronta(self):
        return self.quadro_sala(["PRONTA_FANTASMA", "PRONTA_PROFUNDEZAS", "PRONTA_MINHOCAO"][self.sala_inst])
    def capturar(self):
        self.cap += 1; t = self.tela
        if t == "BATALHA" and self.cap - self.desde > 6: self.trocar("CARTAS"); t = "CARTAS"
        if t == "CARTAS" and len(self.viradas) >= 3 and self.cap - self.desde > 10: self.fim_cartas(); t = self.tela
        if t == "CARTAS": return self.quadro_cartas()
        if t == "CONFIG_VAZIA" and self.aba == "evento": return img("CFG_EVENTO_VAZIA")
        if t == "CONFIG_SEL": return img("CFG_SEL_" + self.instancias_clicadas[-1])
        if t == "PRONTA": return self.quadro_pronta()
        if t == "SALA_VAZIA": return img("SALA_FINAL") if self.sala_inst is None and len(self.lutas) % 3 == 0 and self.lutas else self.quadro_sala("SALA_VAZIA")
        if t == "TAREFA": return img("TAREFA_SEM_OK" if self.tarefas_ok else "TAREFA_COM_OK")
        return img(t)
    def fim_cartas(self):
        self.viradas = []; self.ja_ignorou = False; self.lutas.append(self.sala_inst); self.trocar("PRONTA")   # sala continua na mesma instancia
    def clicar(self, x, y, modo):
        p = (x, y); self.cliques.append((self.tela, p)); t = self.tela
        if t in ("SALA_VAZIA", "PRONTA"): self.clique_slot(p)
        if t == "MAPA" and dentro(p, caixa(N.MAPA_CENTRAL)): self.trocar("CENTRAL")
        elif t == "CENTRAL" and dentro(p, caixa(N.CENTRAL_JOGAR)):
            self.jogar_cliques += 1; self.trocar("SALA_VAZIA"); self.sala_inst = None; self.slots = [True, True, True]
        elif t in ("SALA_VAZIA", "PRONTA") and dentro(p, caixa(N.SALA_TROCAR_INSTANCIA)): self.trocar("CONFIG_VAZIA")
        elif t in ("SALA_VAZIA", "PRONTA") and dentro(p, caixa(N.SALA_ICONE_TAREFAS)): self.volta_para = t; self.trocar("TAREFA")
        elif t == "CONFIG_VAZIA":
            for nome, c in N.INSTANCIA_NA_CONFIG.items():
                if N.ABA_DA_INSTANCIA.get(nome, "normal") != "normal": continue   # (aba do evento: outro teste)
                if dentro(p, caixa(c, 30)): self.escolhida = ROTA.index(nome); self.instancias_clicadas.append(nome); self.trocar("CONFIG_SEL")
        elif t == "CONFIG_SEL" and dentro(p, caixa(N.CONFIG_SIM, 60)): self.sala_inst = self.escolhida; self.trocar("PRONTA")
        elif t == "PRONTA" and dentro(p, caixa(N.SALA_INICIO, 40)):
            self.inicios_com_vaga_aberta += any(self.slots); self.trocar("POPUP_SOZINHO")
        elif t == "POPUP_SOZINHO" and dentro(p, caixa(N.POPUP_SOZINHO_SIM, 40)): self.trocar("BATALHA")
        elif t == "CARTAS":
            for c in [(x, y) for y in N.CARTAS_LINHAS for x in N.CARTAS_COLUNAS]:
                if dentro(p, caixa_carta(c)) and c not in self.viradas:
                    if len(self.viradas) == 2: self.pendente = c; self.trocar("POPUP_CARTA")
                    else: self.viradas.append(c)
        elif t == "POPUP_CARTA" and dentro(p, caixa(N.POPUP_CARTA_SIM, 40)): self.viradas.append(self.pendente); self.trocar("CARTAS")
        elif t == "TAREFA" and not self.tarefas_ok and dentro(p, caixa(N.TAREFA_BOTAO, 50)): self.tarefas_ok = True
        elif t == "TAREFA" and self.tarefas_ok and dentro(p, caixa(N.TAREFA_FECHAR, 30)):
            self.trocar(self.volta_para); self.voltas += 1; self.tarefas_ok = False
ROTA = ["FANTASMA", "PROFUNDEZAS", "MINHOCAO"]
sim = Sim2(); relogio = [0.0]
nav = N.Navegador(sim, det, dormir=lambda s: relogio.__setitem__(0, relogio[0] + s), agora=lambda: relogio[0], log=lambda m: None)
for _ in range(900):
    e = nav.estado_estavel()
    if e: nav.agir(e)
    if sim.voltas >= 2: break
ordem = [ROTA[i] for i in sim.lutas]
print("instancias lutadas, na ordem:", ordem)
assert sim.voltas >= 2, "nao completou 2 voltas"
assert ordem[:6] == ROTA * 2, f"ordem errada: {ordem}"
assert all(a != b for a, b in zip(ordem, ordem[1:])), f"repetiu a mesma instancia em seguida: {ordem}"
assert sim.jogar_cliques == 1
print("ordem OK mesmo quando a sala continua mostrando a ultima instancia (nao repete o Minhocao)")

# ---------------------------------------------------------------- 10) o jogo perde o foco: pop-up "Clique no jogo"
class SimFoco(Sim2):
    """Qualquer clique dentro do jogo fecha o pop-up, MAS o clique tambem vale para o que esta por baixo
    (no mapa, o centro do pop-up cobre a Sala de Casamento)."""
    def __init__(self, tela):
        super().__init__(); self.popup = True; self.tela = tela; self.atravessou = 0; self.fechou_com = None
    def capturar(self):
        f = super().capturar()
        if self.popup:
            f = f.copy(); x0, y0, x1, y1 = N.POPUP_FOCO_CAIXA; f[y0:y1, x0:x1] = img("CLIQUE_JOGO")[y0:y1, x0:x1]
        return f
    def clicar(self, x, y, modo):
        if self.popup:
            x0, y0, x1, y1 = N.POPUP_FOCO_CAIXA
            if 305 <= x <= 985 and 155 <= y <= 580:          # dentro do jogo: fecha o pop-up
                self.popup = False; self.fechou_com = (x, y)
                if x0 <= x <= x1 and y0 <= y <= y1: self.atravessou += 1     # ...e atravessa para o que esta por baixo
            return
        super().clicar(x, y, modo)
for tela, quadro in (("MAPA", "MAPA"), ("CENTRAL", "CENTRAL"), ("BATALHA", "BATALHA"), ("CARTAS", "CARTAS"), ("SALA_VAZIA", "SALA_VAZIA")):
    sim = SimFoco(tela); relogio = [0.0]
    nav = N.Navegador(sim, det, dormir=lambda s: relogio.__setitem__(0, relogio[0] + s), agora=lambda: relogio[0], log=lambda m: None)
    f, achadas = nav.ver()
    assert achadas[0] == "CLIQUE_JOGO" and achadas[1] == tela, (tela, achadas)
    nav.agir("CLIQUE_JOGO")
    assert not sim.popup and sim.atravessou == 0, f"{tela}: clicou {sim.fechou_com} (atravessou={sim.atravessou})"
    print(f"pop-up de foco sobre {tela:10s}: fechado clicando em {sim.fechou_com} (area neutra, sem atravessar)")

# ---------------------------------------------------------------- 11) entrou numa tela de cidade desconhecida (Sala de Casamento): volta pela porta
class SimCasamento(Sim2):
    def capturar(self):
        if self.tela == "CASAMENTO": self.cap += 1; return img("DESCONHECIDA")
        return super().capturar()
    def clicar(self, x, y, modo):
        self.cliques.append((self.tela, (x, y)))
        if self.tela == "CASAMENTO":
            if dentro((x, y), caixa(N.SALA_PORTA, 40)): self.trocar("MAPA")
        elif self.tela == "MAPA" and dentro((x, y), caixa(N.MAPA_CENTRAL)): self.trocar("CASAMENTO")   # clicou na construcao errada
        else: super().clicar(x, y, modo)
sim = SimCasamento(); relogio = [0.0]; logs = []
nav = N.Navegador(sim, det, dormir=lambda s: relogio.__setitem__(0, relogio[0] + s), agora=lambda: relogio[0], log=logs.append)
nav.agir("MAPA")                                   # o bot clica e cai na tela desconhecida
assert sim.tela == "CASAMENTO"
for _ in range(60):
    e = nav.estado_estavel()
    if e is None: nav.desconhecido(); nav.dormir(0.6)
    else: break
assert sim.tela == "MAPA", (sim.tela, logs[-3:])
assert any("voltando pela porta" in l for l in logs)
print("recuperacao de tela de cidade desconhecida OK (voltou pela porta)")

# ---------------------------------------------------------------- 12) NENHUM ponto neutro pode cair no CHAT (daria o foco do teclado ao campo de texto)
CHAT_CIDADE = (330, 450, 600, 530)        # mensagens + campo de digitacao (mapa, Central, salas)
CHAT_BATALHA = (320, 255, 545, 340)       # log de mensagens no canto superior esquerdo da batalha
for nome, p in list(N.FOCO_PONTO_NEUTRO.items()) + [("padrao", N.FOCO_PONTO_PADRAO), ("atirador", N.FOCO_CLICK_BATALHA)]:
    for caixa_chat in (CHAT_CIDADE, CHAT_BATALHA):
        x0, y0, x1, y1 = caixa_chat
        assert not (x0 <= p[0] <= x1 and y0 <= p[1] <= y1), f"ponto neutro '{nome}' {p} cai no chat {caixa_chat}"
print("nenhum ponto neutro cai no chat OK")

# ---------------------------------------------------------------- SUA 5a RUN: varias tarefas concluidas, pegar TODAS
# Quadros reais (gravacao do bot 20261028_044345): 2 diarias com OK! + a categoria "Tarefa/Missao ativa" FECHADA com OK!
# (dentro dela: "Super Rota Norte"). O botao vermelho PULSA: no quadro mais escuro o detector antigo achava que estava
# cinza e fechava o painel sem coletar a Super Rota Norte.
assert N.botao_recompensa_ativo(img("TAREFA_SUPER_PULSO_FRACO")), "botao no brilho fraco do pulso nao reconhecido"
assert not N.botao_recompensa_ativo(img("TAREFA_ATIVA_FECHADA_OK")) and not N.botao_recompensa_ativo(img("TAREFA_TUDO_COLETADO"))
assert N.seta_rolar_lista(img("TAREFA_SUPER_PULSO_FRACO")) is not None

class SimTarefas:
    """So o painel de tarefas: estados = quadros reais; cliques levam de um ao outro.
    escondida=True: ao rolar a sub-lista aparece mais uma tarefa concluida (que estava abaixo das 4 visiveis)."""
    def __init__(self, escondida=False):
        self.q = "TAREFA_DIARIAS_2OK"; self.coletadas = []; self.fechou = False; self.cliques = []
        self.escondida = escondida; self.rolou = 0
    def capturar(self): return img(self.q)
    def clicar(self, x, y, modo):
        p = (x, y); self.cliques.append((self.q, p)); q = self.q
        if dentro(p, caixa(N.TAREFA_FECHAR, 30)): self.fechou = True; return
        botao = dentro(p, caixa(N.TAREFA_BOTAO, 50))
        if q == "TAREFA_DIARIAS_2OK" and botao: self.coletadas.append("diaria 1"); self.q = "TAREFA_COLETOU_1"
        elif q == "TAREFA_COLETOU_1" and botao: self.coletadas.append("diaria 2"); self.q = "TAREFA_ATIVA_FECHADA_OK"
        elif q == "TAREFA_ATIVA_FECHADA_OK" and dentro(p, (440, 425, 560, 460)): self.q = "TAREFA_SUPER_PULSO_FRACO"
        elif q == "TAREFA_SUPER_PULSO_FRACO" and botao: self.coletadas.append("Super Rota Norte"); self.q = "TAREFA_TUDO_COLETADO"
        elif q == "TAREFA_TUDO_COLETADO" and dentro(p, (563, 437, 583, 457)):    # setinha da sub-lista
            self.rolou += 1
            if self.escondida and self.rolou == 1:
                self.escondida = False; self.q = "TAREFA_SUPER_PULSO_FRACO"         # apareceu outra concluida
        elif q == "TAREFA_SUPER_PULSO_FRACO" and dentro(p, (563, 437, 583, 457)): pass
    def tecla_apertada(self, vk): return False

for escondida in (False, True):
    st = SimTarefas(escondida)
    relogio = [0.0]
    logs = []
    nav = N.Navegador(st, det, dormir=lambda s: relogio.__setitem__(0, relogio[0] + s), agora=lambda: relogio[0], log=logs.append)
    nav.coletar_tarefas()
    print("\n".join("   " + l for l in logs))
    esperado = ["diaria 1", "diaria 2", "Super Rota Norte"] + (["Super Rota Norte"] if escondida else [])
    assert st.coletadas == esperado, st.coletadas
    assert st.fechou and st.rolou >= 1, (st.fechou, st.rolou)
    print(f"tarefas: coletou {st.coletadas} (escondida na lista: {escondida}) e so depois fechou OK")
print("\ncoleta de TODAS as tarefas OK")

# ---------------------------------------------------------------- ROTA SUL: o Escorpiao (artes reais aprendidas na 1a gravacao)
assert N.instancia_selecionada(img("CFG_SEL_ESCORPIAO")) == "ESCORPIAO_REI" and N.instancia_na_sala(img("SALA_ESCORPIAO")) == "ESCORPIAO_REI"
print("artes do Escorpiao reconhecidas (configuracao e sala) OK")

# ---------------------------------------------------------------- ROTA SUL: instancias que o bot nunca viu
# Escorpiao Rei -> Dragao Gelado -> Rainha Liris (sem escolha de dificuldade). As artes (na configuracao e na sala) aqui sao
# desenhos inventados: o bot nao tem modelo delas, entao tem que APRENDER na 1a vez e reconhecer depois (inclusive a
# sala que continua mostrando a instancia que acabou de ser jogada).
import shutil, tempfile
import numpy as np
APRENDIDOS_TESTE = tempfile.mkdtemp()
N.PASTA_APRENDIDOS = APRENDIDOS_TESTE; N._TPL_CFG.clear(); N._TPL_SALA.clear()
# modelos oficiais SEM as artes da Rota Sul (aqui as artes sao inventadas: o bot tem que aprender do zero)
MODELOS_TESTE = os.path.join(tempfile.mkdtemp(), "templates")
shutil.copytree(N.config.PASTA_TEMPLATES, MODELOS_TESTE,
                ignore=lambda _d, nomes: [n for n in nomes if n.startswith(("cfg_", "sala_")) and not n.startswith(("cfg_FANTASMA", "cfg_PROFUNDEZAS", "cfg_MINHOCAO"))])
PASTA_TEMPLATES_REAL = N.config.PASTA_TEMPLATES
N.config.PASTA_TEMPLATES = MODELOS_TESTE

# pergunta da rota ao abrir
respostas = iter(["x", "s"])
assert N.perguntar_rota(entrada=lambda _p: next(respostas), saida=lambda *_a: None) == "S"
assert N.perguntar_rota(entrada=lambda _p: "", saida=lambda *_a: None) == "S", "Enter = Sul (Norte desabilitada no menu)"
assert N.perguntar_rota(entrada=lambda _p: "t", saida=lambda *_a: None) == "T"
nome_t, rota_t, _ = N.rota_dos_argumentos("T")
assert rota_t == ["FANTASMA", "PROFUNDEZAS", "MINHOCAO", "ESCORPIAO_REI", "DRAGAO_GELADO", "RAINHA_LIRIS"], rota_t
print("pergunta N/S/T OK; T =", " > ".join(rota_t))

def arte_inventada(seed, h, w):
    rng = np.random.default_rng(seed)
    return cv2.resize(rng.integers(0, 255, (max(1, h // 8), max(1, w // 8), 3)).astype(np.uint8), (w, h), interpolation=cv2.INTER_NEAREST)

class SimNova(Sim2):
    def __init__(self):
        super().__init__(); self.dif_cliques = []; self.dif_desde_config = False; self.confirmou_sem_dif = 0
    def quadro_pronta(self):
        f = self.quadro_sala("PRONTA_FANTASMA").copy()
        x0, y0, x1, y1 = N.SALA_ARTE
        f[y0 - 5:y1 + 5, x0 - 5:x1 + 5] = arte_inventada(10 + self.sala_inst, y1 - y0 + 10, x1 - x0 + 10)
        return f
    def capturar(self):
        t = self.tela
        if t == "CONFIG_SEL":
            self.cap += 1
            f = img("CFG_SEL_FANTASMA").copy()      # painel inteiro da arte trocado: o detector nao reconhece CONFIG_SEL
            f[390:462, 452:652] = arte_inventada(20 + self.escolhida, 72, 200)
            return f
        if t == "SALA_VAZIA" and self.sala_inst is None and self.lutas and len(self.lutas) % len(ROTA) == 0:
            self.cap += 1; return img("SALA_FINAL")
        return super().capturar()
    def clicar(self, x, y, modo):
        if self.tela == "CONFIG_SEL":
            for nome, c in N.DIFICULDADE_BOTAO.items():
                if dentro((x, y), caixa(c, 25)): self.dif_cliques.append(nome); self.dif_desde_config = True; return
            if dentro((x, y), caixa(N.CONFIG_SIM, 60)):
                self.confirmou_sem_dif += not self.dif_desde_config
            for nome, c in N.INSTANCIA_NA_CONFIG.items():   # clicar em outra instancia na grade troca a selecao
                if dentro((x, y), caixa(c, 30)) and nome in ROTA: self.escolhida = ROTA.index(nome); self.instancias_clicadas.append(nome); return
        if self.tela == "CONFIG_VAZIA": self.dif_desde_config = False
        super().clicar(x, y, modo)

nome_s, ROTA_SUL, dif = N.rota_dos_argumentos("S")
ROTA = ROTA_SUL                     # Sim2 usa a variavel global ROTA
sim = SimNova(); relogio = [0.0]; logs = []
nav = N.Navegador(sim, det, rota=ROTA_SUL, dificuldade=dif, dormir=lambda s: relogio.__setitem__(0, relogio[0] + s),
                  agora=lambda: relogio[0], log=logs.append)
for _ in range(1200):
    e = nav.estado_estavel()
    if e: nav.agir(e)
    if sim.voltas >= 2: break
ordem = [ROTA_SUL[i] for i in sim.lutas]
print("\n".join("   " + l for l in logs if "APRENDI" in l))
print(f"{nome_s}, instancias lutadas:", ordem, "| dificuldades clicadas:", sim.dif_cliques)
assert sim.voltas >= 2 and ordem[:6] == ROTA_SUL * 2, (sim.voltas, ordem)
assert sim.dif_cliques == [], f"clicou em dificuldade numa instancia que nao tem: {sim.dif_cliques}"
aprendidos = sorted(os.listdir(APRENDIDOS_TESTE))
print("artes aprendidas:", aprendidos)
assert aprendidos == sorted([f"{p}_{n}.png" for p in ("cfg", "sala") for n in ROTA_SUL]), aprendidos
assert sum("APRENDI" in l for l in logs) == 6, "aprendeu de novo o que ja sabia"
shutil.rmtree(APRENDIDOS_TESTE); N._TPL_CFG.clear(); N._TPL_SALA.clear()
N.config.PASTA_TEMPLATES = PASTA_TEMPLATES_REAL
print("Rota Sul OK (aprende as artes sozinho, mantem a ordem, nao mexe na dificuldade)")

# ---------------------------------------------------------------- CARTAS com o PC ocupado (sua run): jogo LENTO
# A tela de cartas tem cronometro de 15 s. Com o PC ocupado a carta so aparece virada ~3,5 s depois do clique. Antes o
# bot clicava de novo na mesma carta a cada 2 s e o tempo acabava antes da 3a. Agora: sorteia 3, clica nas 3 em
# seguida e repete nas que nao viraram. E as cartas variam de uma luta para outra. (O jogo trava na 3a carta.)
class SimCartasLento:
    def __init__(self, relogio, atraso=3.5):
        self.rel, self.atraso = relogio, atraso
        self.tela = "CARTAS"; self.viradas = []; self.pendentes = {}; self.clicadas = []; self.popup = None
    def _atualiza(self):
        for c, tf in sorted(self.pendentes.items(), key=lambda kv: kv[1]):
            if self.rel[0] >= tf and self.tela == "CARTAS":
                del self.pendentes[c]
                if len(self.viradas) == 2: self.tela = "POPUP_CARTA"; self.popup = c    # a 3a pede confirmacao
                else: self.viradas.append(c)
    def capturar(self):
        self._atualiza()
        if self.tela == "POPUP_CARTA": return img("POPUP_CARTA")
        f = img("CARTAS_COSTAS").copy(); rev = img("CARTAS_REVELADAS")
        for c in self.viradas:
            x0, y0, x1, y1 = caixa_carta(c); f[y0:y1, x0:x1] = rev[y0:y1, x0:x1]
        return f
    def clicar(self, x, y, modo):
        if self.tela == "POPUP_CARTA":
            if dentro((x, y), caixa(N.POPUP_CARTA_SIM, 40)): self.viradas.append(self.popup); self.tela = "CARTAS"
            return
        for c in N.CARTAS_TODAS:
            if dentro((x, y), caixa_carta(c)) and c not in self.viradas and c not in self.pendentes:
                if c not in self.clicadas: self.clicadas.append(c)
                self.pendentes[c] = self.rel[0] + self.atraso
    def tecla_apertada(self, vk): return False

escolhas = []
for rodada in range(2):
    relogio = [0.0]; st = SimCartasLento(relogio)
    nav = N.Navegador(st, det, dormir=lambda s: relogio.__setitem__(0, relogio[0] + s), agora=lambda: relogio[0], log=lambda m: None)
    nav.rng.seed(rodada)
    while relogio[0] < 15.0 and len(st.viradas) < 3:
        e = nav.estado_estavel()
        if e: nav.agir(e)
        else: nav.dormir(0.3)
    print(f"cartas (jogo lento): {len(st.viradas)} viradas em {relogio[0]:.1f}s de 15s; cartas clicadas {st.clicadas}")
    assert len(st.viradas) == 3 and relogio[0] < 15.0, (st.viradas, relogio[0])
    assert len(st.clicadas) == 3, f"clicou em {len(st.clicadas)} cartas diferentes (com o jogo lento, bastam as 3 sorteadas)"
    escolhas.append(sorted(st.clicadas))
assert escolhas[0] != escolhas[1], "as cartas deveriam ser sorteadas (variar entre lutas)"
print("cartas sorteadas e abertas a tempo mesmo com o jogo lento OK")

# ---------------------------------------------------------------- cronometro ligado no navegador (2 voltas da Rota Norte)
import metricas as MET
ROTA = ["FANTASMA", "PROFUNDEZAS", "MINHOCAO"]
sim = Sim2(); relogio = [0.0]
metr = MET.Metricas("Rota Norte", agora=lambda: relogio[0], log=lambda m: None, salvar=False)
nav = N.Navegador(sim, det, dormir=lambda s: relogio.__setitem__(0, relogio[0] + s), agora=lambda: relogio[0],
                  log=lambda m: None, metricas=metr)
for _ in range(900):
    e = nav.estado_estavel()
    if e: nav.agir(e)
    if nav.voltas >= 2: break          # (a volta do navegador fecha quando ele volta a sala depois das tarefas)
r = metr.por_instancia()
print("cronometro no navegador:", {k: (v["lutas"], round(v["luta_media"], 1), v["instancia_media"] and round(v["instancia_media"], 1)) for k, v in r.items()},
      "| voltas:", [round(V["duracao"], 1) for V in metr.voltas])
assert [r[i]["lutas"] for i in ROTA] == [2, 2, 2] and all(r[i]["vitorias"] == 2 for i in ROTA)
assert all(r[i]["instancia_media"] and r[i]["instancia_media"] > r[i]["luta_media"] for i in ROTA)
assert len(metr.voltas) == 2 and all(V["lutas"] == 3 for V in metr.voltas)
print("cronometro de lutas/instancias/voltas OK")

# ---------------------------------------------------------------- CHEFAO GLOBAL (Pericao, aba "Instancia do evento")
# Gravacao do usuario 20261028_121648: a configuracao pode abrir na ultima aba usada; o Pericao fica no 1o quadro da aba
# do evento; a sala mostra a arte "PERICAO ATE QUE DUROU"; a luta so acaba (cartas) quando o servidor derruba o chefao.
import datetime
assert N.aba_ativa(img("CFG_NORMAL_VAZIA")) == "normal" and N.aba_ativa(img("CFG_EVENTO_VAZIA")) == "evento"
assert N.aba_ativa(img("CFG_SEL_PERICAO")) == "evento" and N.aba_ativa(img("CFG_SEL_ESCORPIAO")) == "normal"
assert det.detectar(E.normalizar(img("CFG_SEL_PERICAO")))[0] == "CONFIG", "config do evento (sem a aba 'Iniciar Batalha do Chefe')"
assert det.detectar(E.normalizar(img("CFG_EVENTO_VAZIA")))[0] == "CONFIG_VAZIA"
assert N.instancia_selecionada(img("CFG_SEL_PERICAO")) == "PERICAO" and N.instancia_na_sala(img("SALA_PERICAO")) == "PERICAO"
assert N.instancia_selecionada(img("CFG_SEL_ESCORPIAO")) == "ESCORPIAO_REI" and N.instancia_na_sala(img("SALA_ESCORPIAO")) == "ESCORPIAO_REI"
H = N.HORARIOS_CHEFE
d = lambda h, m: datetime.datetime(2026, 10, 28, h, m)
assert N.janela_do_chefe(d(12, 30), H) == (d(12, 0), d(13, 0)) and N.janela_do_chefe(d(13, 0), H) is None
assert N.janela_do_chefe(d(21, 59), H) == (d(21, 0), d(22, 0)) and N.janela_do_chefe(d(11, 59), H) is None
assert N.proximo_chefe(d(13, 5), H) == d(21, 0) and N.proximo_chefe(d(22, 30), H) == d(12, 0) + datetime.timedelta(days=1)
assert N.ler_horarios("12:00-13:00, 21:30-22") == [((12, 0), (13, 0)), ((21, 30), (22, 0))]
assert N.rota_dos_argumentos("C")[1] == ["PERICAO"]
respostas = iter(["c"])
assert N.perguntar_rota(entrada=lambda p: next(respostas), saida=lambda m: None) == "C"
assert N.perguntar_chefe(entrada=lambda p: "", saida=lambda m: None) is True
assert N.perguntar_chefe(entrada=lambda p: "n", saida=lambda m: None) is False

class SimChefe:
    """Sala que guarda a instancia escolhida; configuracao com ABAS (reabre na ultima aba usada); Pericao na aba do
    evento; tarefas no fim da rota."""
    BASE = {"FANTASMA": "PRONTA_FANTASMA", "PROFUNDEZAS": "PRONTA_PROFUNDEZAS", "MINHOCAO": "PRONTA_MINHOCAO",
            "PERICAO": "SALA_PERICAO", None: "SALA_VAZIA"}
    def __init__(self):
        self.tela = "SALA"; self.cap = 0; self.desde = 0; self.sala_inst = None; self.sel = None; self.aba = "normal"
        self.slots = [True, True, True]; self.viradas = []; self.lutas = []; self.abas_clicadas = []
        self.tarefas_ok = False; self.tarefas_abertas = 0; self.batalha_dura = 6
    def trocar(self, t): self.tela, self.desde = t, self.cap
    def quadro_sala(self):
        f = img(self.BASE[self.sala_inst]).copy(); aberto = img("SLOTS_ABERTOS"); fechado = img("SALA_FINAL")
        for ab, c in zip(self.slots, N.SLOTS_SALA):
            x0, y0, x1, y1 = c[0] - 58, c[1] - 52, c[0] + 58, c[1] + 52
            f[y0:y1, x0:x1] = (aberto if ab else fechado)[y0:y1, x0:x1]
        return f
    def quadro_cartas(self):
        f = img("CARTAS_COSTAS").copy(); rev = img("CARTAS_REVELADAS")
        for c in self.viradas:
            x0, y0, x1, y1 = caixa_carta(c); f[y0:y1, x0:x1] = rev[y0:y1, x0:x1]
        return f
    def capturar(self):
        self.cap += 1; t = self.tela
        if t == "BATALHA" and self.cap - self.desde > self.batalha_dura: self.trocar("CARTAS"); t = "CARTAS"
        if t == "CARTAS" and len(self.viradas) >= 3 and self.cap - self.desde > 10:
            self.viradas = []; self.lutas.append(self.sala_inst); self.trocar("SALA"); t = "SALA"
        if t == "CARTAS": return self.quadro_cartas()
        if t == "SALA": return self.quadro_sala()
        if t == "CONFIG":
            aba_sel = N.ABA_DA_INSTANCIA.get(self.sel, "normal")
            if self.sel and aba_sel == self.aba:
                return img({"PERICAO": "CFG_SEL_PERICAO", "FANTASMA": "CFG_SEL_FANTASMA", "PROFUNDEZAS": "CFG_SEL_PROFUNDEZAS",
                            "MINHOCAO": "CFG_SEL_MINHOCAO"}[self.sel])
            return img("CFG_EVENTO_VAZIA" if self.aba == "evento" else "CFG_NORMAL_VAZIA")
        if t == "TAREFA": return img("TAREFA_SEM_OK" if self.tarefas_ok else "TAREFA_COM_OK")
        return img(t)
    def clicar(self, x, y, modo):
        p = (x, y); t = self.tela
        if t == "SALA":
            for k, c in enumerate(N.SLOTS_SALA):
                if dentro(p, (c[0] - 55, c[1] - 50, c[0] + 55, c[1] + 50)): self.slots[k] = not self.slots[k]
            if dentro(p, caixa(N.SALA_TROCAR_INSTANCIA)): self.sel = self.sala_inst; self.trocar("CONFIG")
            elif dentro(p, caixa(N.SALA_ICONE_TAREFAS)): self.tarefas_abertas += 1; self.trocar("TAREFA")
            elif self.sala_inst and dentro(p, caixa(N.SALA_INICIO, 40)): self.trocar("POPUP_SOZINHO")
        elif t == "CONFIG":
            for aba, c in N.ABAS_CONFIG.items():
                if dentro(p, (c[0] - 30, c[1] - 12, c[0] + 30, c[1] + 12)): self.aba = aba; self.abas_clicadas.append(aba); return
            for nome, c in N.INSTANCIA_NA_CONFIG.items():
                if N.ABA_DA_INSTANCIA.get(nome, "normal") == self.aba and dentro(p, caixa(c, 30)): self.sel = nome; return
            if self.sel and dentro(p, caixa(N.CONFIG_SIM, 60)): self.sala_inst = self.sel; self.trocar("SALA")
        elif t == "POPUP_SOZINHO" and dentro(p, caixa(N.POPUP_SOZINHO_SIM, 40)): self.trocar("BATALHA")
        elif t == "CARTAS":
            for c in [(x, y) for y in N.CARTAS_LINHAS for x in N.CARTAS_COLUNAS]:
                if dentro(p, caixa_carta(c)) and c not in self.viradas and len(self.viradas) < 3: self.viradas.append(c)
        elif t == "TAREFA" and not self.tarefas_ok and dentro(p, caixa(N.TAREFA_BOTAO, 50)): self.tarefas_ok = True
        elif t == "TAREFA" and self.tarefas_ok and dentro(p, caixa(N.TAREFA_FECHAR, 30)): self.tarefas_ok = False; self.trocar("SALA")
    def tecla_apertada(self, vk): return False

def rodar_chefe(sim, nav, ate, max_passos=3000):
    for _ in range(max_passos):
        e = nav.estado_estavel()
        if e: nav.agir(e)
        if ate(): break

# (a) Rota Norte + Chefao nos horarios: o bot comeca 11:59:45 (o simulador e rapido: ~15 s por instancia); ao meio-dia termina a instancia em andamento, vai para o
#     Pericao (troca de aba), luta ate as cartas e depois volta para a rota DE ONDE PAROU (troca de aba de novo)
sim = SimChefe(); relogio = [0.0]; logs = []
inicio = datetime.datetime(2026, 10, 28, 11, 59, 45)
nav = N.Navegador(sim, det, ["FANTASMA", "PROFUNDEZAS", "MINHOCAO"], dormir=lambda s: relogio.__setitem__(0, relogio[0] + s),
                  agora=lambda: relogio[0], log=logs.append, chefe="horarios",
                  relogio=lambda: inicio + datetime.timedelta(seconds=relogio[0]))
rodar_chefe(sim, nav, lambda: len(sim.lutas) >= 6)
print("Chefao nos horarios - lutas:", sim.lutas, "| abas clicadas:", sim.abas_clicadas,
      f"| relogio {(inicio + datetime.timedelta(seconds=relogio[0])):%H:%M:%S}")
print("\n".join(l for l in logs if "CHEFAO" in l))
assert sim.lutas.count("PERICAO") == 1, sim.lutas
rota_sem_chefe = [l for l in sim.lutas if l != "PERICAO"]
assert rota_sem_chefe == ["FANTASMA", "PROFUNDEZAS", "MINHOCAO", "FANTASMA", "PROFUNDEZAS"][:len(rota_sem_chefe)], sim.lutas
assert sim.lutas.index("PERICAO") >= 1, "comecou antes do meio-dia: a 1a instancia e da rota"
assert sim.abas_clicadas[:2] == ["evento", "normal"], sim.abas_clicadas
assert not nav.no_chefe and nav.chefe_feito_em is not None
print("Chefao Global nos horarios: entra na hora, volta para a rota de onde parou OK")

# (b) opcao C (so o Chefao): comeca ja; depois da vitoria espera o proximo horario e volta (horarios curtos no teste)
sim = SimChefe(); relogio = [0.0]; logs = []
inicio = datetime.datetime(2026, 10, 28, 12, 10, 0)
horarios = [((12, 0), (12, 30)), ((12, 40), (13, 0))]
nav = N.Navegador(sim, det, ["PERICAO"], dormir=lambda s: relogio.__setitem__(0, relogio[0] + s), agora=lambda: relogio[0],
                  log=logs.append, chefe="so", horarios_chefe=horarios,
                  relogio=lambda: inicio + datetime.timedelta(seconds=relogio[0]))
rodar_chefe(sim, nav, lambda: len(sim.lutas) >= 2)
hora = lambda: inicio + datetime.timedelta(seconds=relogio[0])
print("so o Chefao - lutas:", sim.lutas, f"| relogio {hora():%H:%M:%S}")
assert sim.lutas == ["PERICAO", "PERICAO"] and hora() >= datetime.datetime(2026, 10, 28, 12, 40), (sim.lutas, hora())
assert any("esperando o proximo Chefao Global" in l for l in logs) and sim.tarefas_abertas == 0
print("opcao C: luta, espera o proximo horario e luta de novo OK")

# (c) evento fechado: o quadro do Pericao nao fica marcado -> desiste ate o proximo horario e segue a rota
class SimSemEvento(SimChefe):
    def clicar(self, x, y, modo):
        if self.tela == "CONFIG" and self.aba == "evento" and dentro((x, y), caixa(N.INSTANCIA_NA_CONFIG["PERICAO"], 30)):
            return                                            # quadro bloqueado
        super().clicar(x, y, modo)
sim = SimSemEvento(); relogio = [0.0]; logs = []
inicio = datetime.datetime(2026, 10, 28, 12, 5, 0)
nav = N.Navegador(sim, det, ["FANTASMA", "PROFUNDEZAS", "MINHOCAO"], dormir=lambda s: relogio.__setitem__(0, relogio[0] + s),
                  agora=lambda: relogio[0], log=logs.append, chefe="horarios",
                  relogio=lambda: inicio + datetime.timedelta(seconds=relogio[0]))
rodar_chefe(sim, nav, lambda: len(sim.lutas) >= 2)
print("evento fechado - lutas:", sim.lutas)
assert sim.lutas[:2] == ["FANTASMA", "PROFUNDEZAS"] and any("desisto do Chefao Global" in l for l in logs), (sim.lutas, logs[-5:])
print("evento fechado: desiste e segue a rota OK")

# ---------------------------------------------------------------- 28/10 noite: Norte desabilitada, Pericao comum, cartas so de algumas
saida_menu = []
N.perguntar_rota(entrada=lambda p: "", saida=saida_menu.append)
assert "Norte" not in " ".join(saida_menu) and "Todas" not in " ".join(saida_menu), "N e T saem do menu"
assert N.rota_dos_argumentos("N")[1] == ["FANTASMA", "PROFUNDEZAS", "MINHOCAO"] and len(N.rota_dos_argumentos("T")[1]) == 6, "...mas continuam"
assert N.perguntar_rota(entrada=lambda p: "p", saida=lambda m: None) == "P" and N.rota_dos_argumentos("P")[1] == ["PERICAO"]
ROTA_S = N.ROTAS["S"][1]
assert N.cartas_padrao("S", ROTA_S) == ["RAINHA_LIRIS"]
assert N.perguntar_cartas("S", ROTA_S, entrada=lambda p: "", saida=lambda m: None) == ["RAINHA_LIRIS"]
assert N.perguntar_cartas("S", ROTA_S, entrada=lambda p: "t", saida=lambda m: None) is None
assert N.perguntar_cartas("S", ROTA_S, entrada=lambda p: "1, 3", saida=lambda m: None) == ["ESCORPIAO_REI", "RAINHA_LIRIS"]
assert N.perguntar_cartas("P", ["PERICAO"], entrada=lambda p: "", saida=lambda m: None) is None, "rota de 1 instancia: nao pergunta"
r = iter(["9", "2"])
assert N.perguntar_cartas("S", ROTA_S, entrada=lambda p: next(r), saida=lambda m: None) == ["DRAGAO_GELADO"]

# Pericao comum (rota P, sem horario): a luta e do chefe COMUM (nome de instancia proprio) e entra pela aba do evento
sim = SimChefe(); relogio = [0.0]; logs = []
inicio = datetime.datetime(2026, 10, 28, 15, 0, 0)
metr = MET.Metricas("Pericao comum", agora=lambda: relogio[0], log=lambda m: None, salvar=False)
nav = N.Navegador(sim, det, ["PERICAO"], dormir=lambda s: relogio.__setitem__(0, relogio[0] + s), agora=lambda: relogio[0],
                  log=logs.append, chefe="horarios", metricas=metr, relogio=lambda: inicio + datetime.timedelta(seconds=relogio[0]))
assert nav.instancia_batalha == "PERICAO_COMUM"
rodar_chefe(sim, nav, lambda: len(sim.lutas) >= 2 or nav.voltas >= 1)
print("Pericao comum - lutas:", sim.lutas, "| abas:", sim.abas_clicadas, "| metricas:", list(metr.por_instancia()))
assert sim.lutas[:1] == ["PERICAO"] and sim.abas_clicadas[:1] == ["evento"] and "PERICAO_COMUM" in metr.por_instancia()
assert not nav.no_chefe, "fora do horario: chefe comum"
import estrategias as EST, memoria as MEM
assert not EST.estrategia("PERICAO_COMUM").get("chefe_global") and MEM.angulo_min("PERICAO_COMUM") == 0.0
m = MEM.Memoria(arq_aprendizado=None)
assert m.prever("PERICAO_COMUM", (10.5, 58.4), (76.3, 61.4))["origem"] == "memoria", "usa os tiros do mesmo mapa (chefao)"

# cartas puladas: so abre as da Rainha (o jogo nao recebe clique de carta nas outras)
class SimCartasSul(SimChefe):
    BASE = {**SimChefe.BASE, "ESCORPIAO_REI": "SALA_ESCORPIAO", "DRAGAO_GELADO": "SALA_ESCORPIAO", "RAINHA_LIRIS": "SALA_ESCORPIAO"}
    def __init__(self):
        super().__init__(); self.cliques_cartas = 0; self.rota = ROTA_S; self.k = 0
    def clicar(self, x, y, modo):
        if self.tela == "CARTAS": self.cliques_cartas += 1
        super().clicar(x, y, modo)
    def capturar(self):
        if self.tela == "CARTAS" and not self.viradas and self.cap - self.desde > 25:      # a tela passa sozinha (cronometro)
            self.lutas.append(self.sala_inst); self.trocar("SALA"); return self.quadro_sala()
        return super().capturar()
# (so o comportamento de pular as cartas: sem cliques na tela de cartas quando a instancia nao interessa)
nav = N.Navegador(SimCartasSul(), det, ["ESCORPIAO_REI"], dormir=lambda s: None, agora=lambda: 0.0, log=logs.append,
                  cartas_em=["RAINHA_LIRIS"])
nav.io.trocar("CARTAS"); nav.cartas_vistas = False
nav.agir("CARTAS")
assert nav.cartas_puladas and nav.io.cliques_cartas == 0, "nao clica em carta de instancia que nao interessa"
nav.cartas_em = {"ESCORPIAO_REI"}
nav.cartas_puladas = False
nav.agir("CARTAS")
assert nav.io.cliques_cartas > 0, "instancia que interessa: abre"
print("cartas so das instancias escolhidas OK")
print("\nmelhorias 28/10 noite OK")

# ---------------------------------------------------------------- PAUSAR pelo painel: o tempo parado fica fora dos cronometros
import tempfile
arq_pausa = os.path.join(tempfile.mkdtemp(), "pausar.flag")
sim = Sim(); relogio = [100.0]; logs = []
metr = MET.Metricas("teste", agora=lambda: relogio[0], log=lambda m: None, salvar=False)
nav = N.Navegador(sim, det, dormir=lambda s: relogio.__setitem__(0, relogio[0] + s), agora=lambda: relogio[0], log=logs.append, metricas=metr)
nav.arquivo_pausar = arq_pausa
metr.instancia_inicio("FANTASMA", 0); metr.batalha_inicio("FANTASMA", 0); nav.batalha_desde = relogio[0]
relogio[0] += 10
open(arq_pausa, "w").close(); nav.teclas()
assert nav.pausado and any("PAUSADO" in l for l in logs)
relogio[0] += 600                                  # 10 min pausado
os.remove(arq_pausa); nav.teclas()
assert not nav.pausado and abs(nav.pausado_total - 600) < 1 and any("Ficou pausado 10min00s" in l for l in logs), logs[-2:]
relogio[0] += 20
metr.batalha_fim(True)
assert abs(metr.lutas[0]["duracao"] - 30) < 1, metr.lutas[0]["duracao"]       # 10 + 20 s, sem os 600 s parado
assert "Tempo pausado" in metr.texto_relatorio() and abs(nav.batalha_desde - 700) < 1
print("pausa do painel: tempo parado fora das medidas OK")

# ---------------------------------------------------------------- VIGIA de "preso" e falhas inesperadas (12h de 29/10: 55 min clicando em "Inicio")
class SimPreso(SimChefe):
    """Uma janelinha por cima: nenhum clique faz nada (como a confirmacao do Pericao que o bot nao conhecia)."""
    def clicar(self, x, y, modo): self.cliques_recebidos = getattr(self, "cliques_recebidos", []) + [(x, y)]
    def tecla(self, nome, dur=0.05): self.teclas_recebidas = getattr(self, "teclas_recebidas", []) + [nome]
sim = SimPreso(); sim.sala_inst = "FANTASMA"; relogio = [0.0]; logs = []
nav = N.Navegador(sim, det, ["FANTASMA", "PROFUNDEZAS", "MINHOCAO"], dormir=lambda s: relogio.__setitem__(0, relogio[0] + s),
                  agora=lambda: relogio[0], log=logs.append)
nav.teclas = lambda: None
while relogio[0] < 200:
    e = nav.estado_estavel()
    if e: nav.agir(e)
alertas = [l for l in logs if "[ALERTA]" in l]
print(alertas[:1])
assert alertas and "preso em" in alertas[0] and 120 <= float(alertas[0].split("ha ")[1].split("min")[0].replace("s", "") if "min" not in alertas[0].split("ha ")[1][:6] else 120) , alertas
assert "esc" in sim.teclas_recebidas and (575, 402) in sim.cliques_recebidos and (644, 394) in sim.cliques_recebidos, "tenta Esc e os botoes das janelinhas"
assert len(alertas) <= 2, "nao fica avisando a cada passo"
print("vigia de preso OK")

# falha inesperada no meio do laco: o bot registra e continua; muitas seguidas param
sim = SimChefe(); relogio = [0.0]; logs = []
nav = N.Navegador(sim, det, ["FANTASMA"], dormir=lambda s: relogio.__setitem__(0, relogio[0] + s), agora=lambda: relogio[0], log=logs.append)
nav.teclas = lambda: None
chamadas = [0]
orig_estado = nav.estado_estavel
def quebra():
    chamadas[0] += 1
    if chamadas[0] in (2, 3):
        raise ValueError("falha de teste")
    if chamadas[0] > 30:
        nav.parar = True
    return orig_estado()
nav.estado_estavel = quebra
nav.rodar()
assert sum("[ERRO] falha inesperada" in l for l in logs) == 2 and chamadas[0] > 30, (chamadas[0], logs[-3:])
nav = N.Navegador(SimChefe(), det, ["FANTASMA"], dormir=lambda s: relogio.__setitem__(0, relogio[0] + s), agora=lambda: relogio[0], log=logs.append)
nav.teclas = lambda: None
def sempre(): raise RuntimeError("sempre quebra")
nav.estado_estavel = sempre
logs.clear(); nav.rodar()
assert nav.parar and any("parando para nao fazer bobagem" in l for l in logs)
print("falhas inesperadas: continua, e para se for demais OK")
