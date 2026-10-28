# -*- coding: utf-8 -*-
"""Atirador contra um mundo simulado (numerico). Rode: python testes/test_atirador.py"""
import json
import os
import sys
import tempfile

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(AQUI))
import atirador as A
import memoria as M

# forca que o previsor escolhe para a situacao padrao do Mundo (Minhocao, jogador (38,67), boss (73.1,64.5))
ALVO = M.Memoria(arq_aprendizado=None).prever("MINHOCAO", (38.0, 67.0), (73.1, 64.5))["forca"]

CUSTOS = {1: 110, 2: 110, 3: 110, 4: 85, 5: 80, 6: 70, 7: 55, 8: 50}

class Mundo:
    """Simula a batalha: relogio, ponteiro do angulo, barra de forca, stamina/itens, PASS e vida do boss."""
    def __init__(self, angulo=15.0, stamina=240, setas_funcionam_em=("top", "filha"), vez_inicio=1.0, vez_fim=9.0,
                 boss_hit=True, custo_captura=0.06, exige_repeticao=False, barra_quebrada=False, taxa=38.0):
        self.taxa = taxa
        self.custo_captura = custo_captura; self.exige_repeticao = exige_repeticao; self.barra_quebrada = barra_quebrada
        self.ultimo_baixo = 0.0; self.keepalive = False
        self.t = 0.0; self.angulo = angulo; self.stamina = stamina; self.modo = "top"
        self.setas_ok = setas_funcionam_em; self.vez = (vez_inicio, vez_fim)
        self.carregando_desde = None; self.barra = 0.0; self.teclas = []; self.itens_apertados = []
        self.vida = 100.0; self.boss_hit = boss_hit; self.atirou_em = None; self.tiros = []
        self.azul, self.boss = (38.0, 67.0), (73.1, 64.5)
    # --- io do atirador
    def avancar(self, s):
        self.t += s
        if self.carregando_desde is not None:
            self.barra = min(100.0, (self.t - self.carregando_desde) * self.taxa)
            # jogo "exigente": se as repeticoes da tecla param por mais de 80 ms, considera a tecla solta e DISPARA
            if self.exige_repeticao and not self.keepalive and self.t - self.ultimo_baixo > 0.08:
                self.tiros.append(min(100.0, (self.ultimo_baixo - self.carregando_desde) * self.taxa))
                self.carregando_desde = None; self.atirou_em = self.t
    def novo_turno(self, ini, fim):
        self.vez = (ini, fim); self.atirou_em = None; self.barra = 0.0; self.vida = 100.0; self.stamina = 240
    def capturar(self):
        self.avancar(self.custo_captura)                     # custo da captura
        vez = self.vez[0] <= self.t <= self.vez[1] and self.atirou_em is None or (self.atirou_em and self.t < self.vez[1])
        if self.atirou_em and self.t > self.atirou_em + 3 and self.boss_hit and self.vida == 100.0:
            self.vida = 58.0                                 # a bala cai ~3 s depois e tira vida
        barra = 100.0 if (self.barra_quebrada and self.carregando_desde is not None and self.t - self.carregando_desde > 0.15) else self.barra
        return {"vez": vez, "ang": self.angulo, "barra": barra, "azul": self.azul, "boss": self.boss,
                "itens": [self.stamina >= CUSTOS[i] for i in range(1, 9)], "vida": self.vida}
    def tecla(self, nome, dur=0.05):
        self.teclas.append((nome, round(dur, 2)))
        if self.teclado_ok() and nome in ("cima", "baixo") and self.modo in self.setas_ok:
            self.angulo += (1 if nome == "cima" else -1) * 30.0 * dur
            if self.limites_angulo:                          # a arma nao passa do limite (muda com a inclinacao do chao)
                self.angulo = min(max(self.angulo, self.limites_angulo[0]), self.limites_angulo[1])
        if self.teclado_ok() and nome.isdigit():
            item = int(nome)
            if self.stamina >= CUSTOS[item]:
                self.stamina -= CUSTOS[item]; self.itens_apertados.append(item)
        self.avancar(dur)
    def tecla_baixo(self, nome, rep=1):
        self.ultimo_baixo = self.t
        if self.teclado_ok() and self.carregando_desde is None and self.atirou_em is None: self.carregando_desde = self.t
    def tecla_cima(self, nome):
        if self.carregando_desde is None:                    # o jogo ja disparou sozinho
            self.avancar(0.1); return
        real = min(100.0, (self.t - self.carregando_desde) * self.taxa)   # forca REAL = tempo segurado (a barra exibida pode estar velha)
        self.avancar(0.1)                                    # atraso do KEYUP
        self.tiros.append(real); self.carregando_desde = None; self.atirou_em = self.t
    def trocar_modo(self): self.modo = "filha" if self.modo == "top" else "top"
    # --- foco do teclado (so em Mundos que definem nivel_exigido)
    limites_angulo = None
    nivel_exigido = 0; foco_nivel = 1; devolvidos = 0; chat_com_foco = False; cliques_cena = 0
    def clicar_ref(self, x, y, modo="top"):
        self.cliques_cena += 1; self.chat_com_foco = False       # clicar na cena devolve o teclado ao jogo
    def preparar_teclas(self): pass
    def encerrar_teclas(self): self.devolvidos += 1
    def escalar_foco(self):
        if self.foco_nivel >= 2: return False
        self.foco_nivel += 1; return True
    def teclado_ok(self): return self.foco_nivel >= self.nivel_exigido and not self.chat_com_foco
    def dormir(self, s): self.avancar(s)

class MundoComThread(Mundo):
    """Como o IOJanela real: segurar() mantem a tecla com repeticao automatica em thread propria."""
    def segurar(self, nome):
        self.keepalive = True; self.ultimo_baixo = self.t
        if self.teclado_ok() and self.carregando_desde is None and self.atirou_em is None: self.carregando_desde = self.t
    def soltar(self, nome):
        Mundo.tecla_cima(self, nome); self.keepalive = False

class Leitor:
    def preparar(self, img): return img
    minha_vez = staticmethod(lambda f: f["vez"])
    angulo = staticmethod(lambda f: f["ang"])
    forca = staticmethod(lambda f: f["barra"])
    pontos = staticmethod(lambda f: (f["azul"], f["boss"]))
    itens = staticmethod(lambda f: f["itens"])
    vida = staticmethod(lambda f: f["vida"])

def novo(mundo, sombra=False, inst="MINHOCAO"):
    tmp = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False); tmp.close(); os.unlink(tmp.name)
    mem = M.Memoria(arq_aprendizado=tmp.name)
    logs = []
    at = A.Atirador(mundo, mem, lambda: inst, leitor=Leitor(), sombra=sombra, dormir=mundo.dormir,
                    agora=lambda: mundo.t, log=logs.append)
    return at, mem, logs, tmp.name

def rodar(at, mundo, ate=14.0):
    while mundo.t < ate:
        at.passo(); mundo.avancar(0.1)

# ------------------------------------------------------------ 1) turno completo
w = Mundo(); at, mem, logs, arq = novo(w)
rodar(at, w)
print("\n".join(logs))
assert abs(w.angulo - 31) <= 3.5, f"angulo final {w.angulo:.1f}"
assert w.itens_apertados[:2] == [2, 3], w.itens_apertados            # stamina 240: 2 (110) e 3 (110); depois nao sobra para o 4
assert 2 not in w.itens_apertados[1:], "item 2 so pode 1x por turno"
alvo = ALVO
assert len(w.tiros) == 1 and abs(w.tiros[0] - alvo) <= 6, f"forca solta {w.tiros}"
assert any("ACERTOU" in l for l in logs), "nao registrou o acerto"
assert json.load(open(arq))["tiros"][-1]["acertou"] is True
print("turno completo OK: angulo %.1f, forca solta %.0f%%, itens %s" % (w.angulo, w.tiros[0], w.itens_apertados))

# ------------------------------------------------------------ 2) mais stamina -> mais itens, respeitando limites
w = Mundo(stamina=480); at, mem, logs, arq = novo(w); rodar(at, w)
assert w.itens_apertados.count(2) == 1 and w.itens_apertados[:3] == [2, 3, 4], w.itens_apertados
assert w.itens_apertados.count(4) >= 2
print("itens com 480 de stamina:", w.itens_apertados)

# ------------------------------------------------------------ 3) setas nao chegam no modo 'top': troca de modo
w = Mundo(setas_funcionam_em=("filha",)); at, mem, logs, arq = novo(w); rodar(at, w)
assert w.modo == "filha" and abs(w.angulo - 31) <= 3.5, (w.modo, w.angulo)
print("troca de modo das setas OK")

# ------------------------------------------------------------ 4) setas nunca funcionam: nao atira
w = Mundo(setas_funcionam_em=()); at, mem, logs, arq = novo(w); rodar(at, w)
assert w.tiros == [] and any("Pulando" in l for l in logs)
print("sem setas: nao atira (OK)")

# ------------------------------------------------------------ 5) modo sombra
w = Mundo(); at, mem, logs, arq = novo(w, sombra=True); rodar(at, w)
assert w.teclas == [] and w.tiros == []
assert any("[sombra]" in l for l in logs)
print("modo sombra OK (nenhuma tecla)")

# ------------------------------------------------------------ 6) errou: aprende e muda
w = Mundo(boss_hit=False); at, mem, logs, arq = novo(w); rodar(at, w)
assert any("ERROU" in l for l in logs)
assert json.load(open(arq))["tiros"][-1]["acertou"] is False
print("erro registrado OK")

# ------------------------------------------------------------ 7) boss morre: o navegador avisa o fim da batalha
w = Mundo(); at, mem, logs, arq = novo(w); rodar(at, w, ate=7.5)   # atirou, bala ainda no ar
at.fim_da_batalha()
assert json.load(open(arq))["tiros"][-1]["acertou"] is True
print("fim de batalha (boss morto) registra acerto OK")
print("\natirador OK")

# ------------------------------------------------------------ 8) defeito real: barra ainda mostra o tiro ANTERIOR (forca 10 em vez de 40)
class MundoBarraVelha(Mundo):
    """No inicio do turno a barra ainda mostra 48% (o tiro anterior); so zera ~0.3 s depois de apertar o espaco."""
    def __init__(self, **kw):
        super().__init__(**kw); self.barra = 48.0
    def avancar(self, s):
        self.t += s
        if self.carregando_desde is not None:
            dec = self.t - self.carregando_desde
            self.barra = 48.0 if dec < 0.3 else min(100.0, (dec - 0.3) * 38.0 + 8)   # fica velha, depois zera e sobe
w = MundoBarraVelha(); at, mem, logs, arq = novo(w); rodar(at, w)
print("\n".join(l for l in logs if "tiro dado" in l))
assert len(w.tiros) == 1 and w.tiros[0] >= 30, f"soltou cedo demais com a barra velha: {w.tiros}"
print("barra velha: OK (forca solta %.0f%%, queria ~38%%)" % w.tiros[0])

# ------------------------------------------------------------ 9) angulo final diferente do previsto -> forca recalculada
w = Mundo(setas_funcionam_em=("top", "filha")); at, mem, logs, arq = novo(w)
at.mem.prever = lambda inst, a, b: {"angulo": 45.0, "forca": 10.0, "origem": "teste", "detalhe": ""}   # previsao incoerente
w.angulo = 15.0
orig = at.ajustar_angulo
at.ajustar_angulo = lambda alvo, tol=3.0: (setattr(w, "angulo", 30.0) or True)    # o ajuste "parou" em 30 graus
rodar(at, w)
assert any("recalculada" in l for l in logs), logs
print("forca recalculada quando o angulo nao chega no previsto OK")
print("\natirador (regressoes) OK")

# ------------------------------------------------------------ 10) HIPOTESE: o jogo dispara sozinho se as repeticoes de tecla demoram (>80 ms)
w = Mundo(exige_repeticao=True, custo_captura=0.12); at, mem, logs, arq = novo(w); rodar(at, w, ate=16)
print("sem thread de repeticao (captura lenta): forca REAL", [round(x) for x in w.tiros], "(queria ~38)")
assert w.tiros and w.tiros[0] < 25, "o simulador deveria reproduzir o disparo precoce"

w = MundoComThread(exige_repeticao=True, custo_captura=0.12); at, mem, logs, arq = novo(w); rodar(at, w, ate=16)
print("com thread de repeticao (30 ms):         forca REAL", [round(x) for x in w.tiros])
assert len(w.tiros) == 1 and abs(w.tiros[0] - ALVO) <= 7, w.tiros
print("repeticao de tecla em thread propria: OK")

# ------------------------------------------------------------ 11) leitura da barra quebrada: troca para o metodo por tempo
w = MundoComThread(barra_quebrada=True); at, mem, logs, arq = novo(w)
rodar(at, w, ate=12)
w.novo_turno(13, 22); rodar(at, w, ate=26)
print("barra quebrada: forca REAL por turno", [round(x) for x in w.tiros], "| metodo agora:", at.metodo_forca)
print("\n".join(l for l in logs if "trocando o metodo" in l))
assert at.metodo_forca == "tempo" and len(w.tiros) == 2
assert w.tiros[0] < 30 and abs(w.tiros[1] - ALVO) <= 7, w.tiros
print("troca de metodo de carga apos subforca OK")
print("\natirador (hipotese da repeticao) OK")

# ------------------------------------------------------------ 12) MEDIDO NO JOGO: a barra enche a 19%/s (metade do esperado)
w = MundoComThread(taxa=19.0, vez_fim=10.5)
w.azul, w.boss = (32.0, 57.0), (90.3, 56.5)                      # Fantasma: precisa de ~76%
at, mem, logs, arq = novo(w, inst="FANTASMA"); rodar(at, w, ate=18)
print("\n".join(l for l in logs if "tiro dado" in l or "mirar" in l))
assert len(w.tiros) == 1 and 66 <= w.tiros[0] <= 86, f"forca real {w.tiros} (queria ~76)"
assert 14 <= at.taxa_forca <= 26, f"taxa aprendida {at.taxa_forca}"
print("barra a 19%%/s: forca real %.0f%% (queria ~76%%), taxa aprendida %.0f%%/s OK" % (w.tiros[0], at.taxa_forca))
print("\natirador (velocidade da barra) OK")

# ------------------------------------------------------------ 13) SEU LOG: as setas so funcionam com o jogo em primeiro plano (foco real)
class MundoFoco(MundoComThread):
    nivel_exigido = 2
w = MundoFoco(); at, mem, logs, arq = novo(w); rodar(at, w, ate=16)
print("\n".join(l for l in logs if "foco" in l or "tiro dado" in l or "Pulando" in l))
assert w.foco_nivel == 2, "nao subiu o foco"
assert abs(w.angulo - 31) <= 3.5 and len(w.tiros) == 1 and abs(w.tiros[0] - ALVO) <= 7, (w.angulo, w.tiros)
assert w.devolvidos >= 1, "nao devolveu o foco"
print("foco do teclado: subiu de nivel, atirou e devolveu o foco OK")
print("\natirador (foco) OK")

# ------------------------------------------------------------ 14) o foco do teclado esta no CHAT (clique no chat): clique na cena resolve
w = MundoComThread(); w.chat_com_foco = True; at, mem, logs, arq = novo(w); rodar(at, w, ate=16)
print("\n".join(l for l in logs if "cena" in l or "tiro dado" in l or "Pulando" in l))
assert w.cliques_cena == 1 and abs(w.angulo - 31) <= 3.5 and len(w.tiros) == 1, (w.cliques_cena, w.angulo, w.tiros)
print("teclado no chat -> clique na cena devolve o foco ao jogo OK")
print("\natirador (foco no chat) OK")

# ------------------------------------------------------------ 15) SEU LOG (Fantasma): leu "voce (71,23)" e atirou com 10-21%
# Um ponto azul falso no minimapa bem na hora do turno nao pode virar "o jogador": vale a posicao que se repete.
class MundoPontoFalso(MundoComThread):
    def capturar(self):
        q = MundoComThread.capturar(self)
        if 2.8 <= self.t <= 3.6:
            q["azul"] = (71.0, 23.0)                     # efeito/objeto azul passageiro
        return q
w = MundoPontoFalso(vez_inicio=3.0, vez_fim=11.0, taxa=38.0)
w.azul, w.boss = (32.0, 57.0), (90.3, 56.5)
at, mem, logs, arq = novo(w, inst="FANTASMA"); rodar(at, w, ate=16)
print("\n".join(l for l in logs if "mirar" in l or "tiro dado" in l))
assert any("voce (32, 57)" in l for l in logs), "usou a leitura falsa do minimapa"
assert len(w.tiros) == 1 and w.tiros[0] >= 60, f"forca {w.tiros}: no Fantasma, dessa posicao, voce acerta com 71-81%"
print("ponto azul falso no minimapa ignorado OK")

# ------------------------------------------------------------ 16) tiros antigos (leitor velho do minimapa) nao contaminam a memoria
tmp = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8")
json.dump({"tiros": [{"inst": "FANTASMA", "azul": [71, 23], "boss": [90, 56], "angulo": 20, "forca": f, "acertou": False,
                      "origem": "bot"} for f in (10, 18, 21, 21)]}, tmp); tmp.close()
mem = M.Memoria(arq_aprendizado=tmp.name); os.unlink(tmp.name)
p = mem.prever("FANTASMA", (32.0, 57.0), (90.3, 56.5))
print("memoria com 4 erros antigos:", mem.ignorados, "ignorados; previsto", round(p["forca"]), "%", p["origem"])
assert mem.ignorados == 4 and p["forca"] >= 65, p
print("\natirador (minimapa) OK")

# ------------------------------------------------------------ 17) SEU LOG (Profundezas): mira em 1 grau (o ponteiro le ~-3)
# A leitura antiga nao enxergava abaixo de 8 graus, lia lixo (90), apertava "baixo" e desistia do turno.
w = MundoComThread(angulo=-3.0)
w.azul, w.boss = (27.0, 47.8), (52.9, 48.9)
at, mem, logs, arq = novo(w, inst="PROFUNDEZAS"); rodar(at, w, ate=16)
print("\n".join(l for l in logs if "mirar" in l or "tiro dado" in l or "!" in l))
assert len(w.tiros) == 1 and abs(w.angulo - 33.5) <= 3.5, (w.angulo, w.tiros)
print("mira saindo de perto de 0 grau OK")

# ------------------------------------------------------------ 18) o angulo bate no LIMITE da arma antes do alvo
w = MundoComThread(angulo=15.0); w.limites_angulo = (0.0, 24.0)
at, mem, logs, arq = novo(w); rodar(at, w, ate=16)
print("\n".join(l for l in logs if "limite" in l or "tiro dado" in l or "recalculada" in l or "Pulando" in l))
assert len(w.tiros) == 1 and abs(w.angulo - 24) <= 1.5, ("atirou do limite?", w.angulo, w.tiros)
assert any("limite" in l for l in logs) and any("recalculada" in l for l in logs), "nao reconheceu o limite / nao recalculou a forca"
assert not any(m == "filha" for m in [w.modo]), "trocou o modo de entrada a toa (as setas funcionavam)"
print("limite do angulo: atira do limite com a forca recalculada OK")
print("\natirador (angulo baixo e limite) OK")

# ------------------------------------------------------------ 19) ROTA SUL: virar para o lado do boss e o AVIAO (F)
import math
class MundoSul(MundoComThread):
    """+ lado para onde o boneco olha (setas esquerda/direita viram; toque curto anda um pouco) e o aviao: F arma,
    o proximo tiro leva o boneco ate onde cair (balistica com R_mundo)."""
    R_mundo = 38.0
    def __init__(self, **kw):
        super().__init__(**kw); self.lado = 1; self.aviao_armado = False; self.voos = []
    def capturar(self):
        q = super().capturar(); q["lado"] = self.lado; return q
    def tecla(self, nome, dur=0.05):
        if self.teclado_ok() and nome in ("esquerda", "direita"):
            self.lado = -1 if nome == "esquerda" else 1
            self.azul = (self.azul[0] + self.lado * 0.3, self.azul[1])
        if self.teclado_ok() and nome == "f": self.aviao_armado = True
        super().tecla(nome, dur)
    def soltar(self, nome):
        n = len(self.tiros); super().soltar(nome)
        if self.aviao_armado and len(self.tiros) > n:
            forca = self.tiros[-1]; ang = math.radians(self.angulo)
            dx = forca ** 2 * math.sin(2 * ang) / self.R_mundo
            self.azul = (self.azul[0] + self.lado * dx, self.azul[1]); self.voos.append(self.azul); self.aviao_armado = False
class LeitorSul(Leitor):
    mira = staticmethod(lambda f: (f["ang"], f["lado"]))
def novo_sul(mundo, inst):
    tmp = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False); tmp.close(); os.unlink(tmp.name)
    mem = M.Memoria(arq_aprendizado=tmp.name); logs = []
    at = A.Atirador(mundo, mem, lambda: inst, leitor=LeitorSul(), dormir=mundo.dormir, agora=lambda: mundo.t, log=logs.append)
    return at, logs

# a Rainha correu para a ESQUERDA do boneco: ele vira e atira para la
w = MundoSul(); w.azul, w.boss = (60.0, 55.0), (30.0, 55.0)
at, logs = novo_sul(w, "RAINHA_LIRIS"); rodar(at, w, ate=16)
print("\n".join(l for l in logs if "virando" in l or "mirar" in l or "tiro dado" in l))
assert w.lado == -1 and len(w.tiros) == 1, (w.lado, w.tiros)
print("boss a esquerda: virou e atirou OK")

# Escorpiao: nasceu colado na borda esquerda (x=18), boss com 100% -> 1o turno voa com F para o meio, sem itens;
# no turno seguinte (ja no meio) ataca com os itens
w = MundoSul(vez_inicio=1.0, vez_fim=9.0); w.azul, w.boss = (17.7, 60.6), (48.8, 60.0)
at, logs = novo_sul(w, "ESCORPIAO_REI"); rodar(at, w, ate=14)
print("\n".join(l for l in logs if "AVIAO" in l or "mirar" in l))
assert [t for t in w.teclas if t[0] == "f"] and w.voos, "nao usou o aviao"
assert w.itens_apertados == [], f"gastou itens no voo: {w.itens_apertados}"
assert 40 <= w.azul[0] <= 66, f"voou para x={w.azul[0]:.0f} (meio da arena ~53)"
w.novo_turno(w.t + 1.0, w.t + 9.0); rodar(at, w, ate=w.t + 12)
print("\n".join(l for l in logs[-6:]))
assert w.itens_apertados and len([t for t in w.teclas if t[0] == "f"]) == 1, (w.itens_apertados, w.teclas)
assert any("voo ok" in l for l in logs)
print("Escorpiao: voou para o meio no 1o turno e atacou no 2o OK")

# boss ja fraco (da para matar neste turno): ataca mesmo perto da borda
w = MundoSul(); w.azul, w.boss = (17.7, 60.6), (48.8, 60.0); w.vida = 41.0
w.capturar_original = w.capturar
at, logs = novo_sul(w, "ESCORPIAO_REI"); rodar(at, w, ate=14)
assert not [t for t in w.teclas if t[0] == "f"] and w.itens_apertados, (w.teclas, w.itens_apertados)
print("Escorpiao fraco: ataca direto OK")
print("\natirador (Rota Sul) OK")

# ------------------------------------------------------------ 20) combo de itens aprende com o dano do 1o ataque
import combos as CB
arq_c = os.path.join(tempfile.mkdtemp(), "combos.json")
w = MundoComThread()
tmp = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False); tmp.close(); os.unlink(tmp.name)
mem = M.Memoria(arq_aprendizado=tmp.name); logs = []
cb = CB.Combos(arq=arq_c)
at = A.Atirador(w, mem, lambda: "MINHOCAO", leitor=Leitor(), dormir=w.dormir, agora=lambda: w.t, log=logs.append, combos=cb)
rodar(at, w, ate=16)
at.fim_da_batalha(venceu=True, duracao=30.0)
print("\n".join(l for l in logs if "combo" in l.lower() or "vida do boss" in l))
reg = cb.dados.get("MINHOCAO", {}).get("2,3,4")
assert reg and reg[0]["dano1"] == 42.0 and reg[0]["t"] == 30.0 and reg[0]["mata1"], cb.dados     # Mundo: 100% -> 58%
print("combo registrado (tempo da luta + dano do 1o ataque) OK")

# ------------------------------------------------------------ 21) boss ja morto e o PASS ainda na tela: nao gasta nada
at.ataques_na_luta = 1
w.novo_turno(w.t + 1.0, w.t + 9.0); w.vida = 0.0
n_tiros, n_itens = len(w.tiros), len(w.itens_apertados)
w.capturar_base = w.capturar
rodar(at, w, ate=w.t + 12)
assert len(w.tiros) == n_tiros and len(w.itens_apertados) == n_itens, "atirou/gastou itens com o boss morto"
print("sem turno fantasma depois do boss morto OK")
print("\natirador (combos) OK")

# ------------------------------------------------------------ 22) SUA MADRUGADA: boss com 1% (barra vazia, retrato colorido) = VIVO
# O leitor antigo dizia 0% e o bot parou de atacar: Dragao ficou 15 min vivo; Escorpiao se curou e jogou o boneco fora.
w.novo_turno(w.t + 1.0, w.t + 9.0); w.vida = 1.0
n_tiros = len(w.tiros)
rodar(at, w, ate=w.t + 12)
assert len(w.tiros) == n_tiros + 1, "com o boss a 1% o bot tem que atacar"
print("boss com 1% de vida: ataca OK")

# ------------------------------------------------------------ 23) CHEFAO GLOBAL (Pericao): vida do servidor, acerto pelos numeros
# A barra do topo e a vida de TODOS (fica em 43% aqui, nao muda com o seu tiro); o acerto e pelos numeros de dano que
# sobem no boss ~1-3 s depois. Mira quase reta (ponteiro em 7; comeca em 4.5) e POW (tecla B) quando encher.
import metricas as MT

class MundoPericao(MundoComThread):
    def __init__(self, **kw):
        super().__init__(angulo=4.5, **kw)
        self.azul, self.boss = (10.5, 58.4), (76.3, 61.4)
        self.pow = False; self.especiais = 0
    def novo_turno(self, ini, fim):
        super().novo_turno(ini, fim); self.vida = 43.0
    def capturar(self):
        f = super().capturar()
        f["vida"] = 43.0                                            # vida do servidor: nao cai com o seu tiro
        a = self.atirou_em
        f["numeros"] = 2500 if (a and self.boss_hit and a + 1.5 <= self.t <= a + 3.5) else 250
        f["pow"] = self.pow
        return f
    def tecla(self, nome, dur=0.05):
        if nome == "b" and self.pow:
            self.pow = False; self.especiais += 1
        super().tecla(nome, dur)

class LeitorPericao(Leitor):
    numeros_dano = staticmethod(lambda f: f["numeros"])
    pow_cheio = staticmethod(lambda f: f["pow"])

w = MundoPericao(); w.vida = 43.0
tmp = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False); tmp.close(); os.unlink(tmp.name)
mem = M.Memoria(arq_aprendizado=tmp.name); logs = []
met = MT.Metricas("Chefao Global", salvar=False, agora=lambda: w.t, log=logs.append)
cb = CB.Combos(arq=None)
at = A.Atirador(w, mem, lambda: "PERICAO", leitor=LeitorPericao(), dormir=w.dormir, agora=lambda: w.t, log=logs.append,
                combos=cb, metricas=met)
met.batalha_inicio("PERICAO")
rodar(at, w, ate=16)
print("\n".join(logs))
assert 5.9 <= w.angulo <= 8.0, f"mira do Pericao: {w.angulo:.1f} (memoria: ponteiro ~7; comecou em 4.5)"
assert len(w.tiros) == 1 and 76 <= w.tiros[0] <= 92, w.tiros
assert w.itens_apertados[:2] == [2, 3], w.itens_apertados
novos = [t for t in mem.tiros if t.get("origem") == "bot"]
assert len(novos) == 1 and novos[0]["acertou"], novos
assert any("numeros de dano no boss" in l and "ACERTOU" in l for l in logs)
# 2o turno: o POW encheu -> B antes dos itens; o resultado do especial nao e conferido (a camera anda)
w.novo_turno(w.t + 1.0, w.t + 9.0); w.pow = True
n_teclas = len(w.teclas)
rodar(at, w, ate=w.t + 14)
seq = [t[0] for t in w.teclas[n_teclas:]]
assert w.especiais == 1 and seq.index("b") < seq.index("3"), seq
assert len([t for t in mem.tiros if t.get("origem") == "bot"]) == 1, "o especial nao entra na memoria"
# 3o turno: o tiro nao pega (sem numeros) -> registra o erro
w.novo_turno(w.t + 1.0, w.t + 9.0); w.boss_hit = False
rodar(at, w, ate=w.t + 14)
bot = [t for t in mem.tiros if t.get("origem") == "bot"]
assert len(bot) == 2 and not bot[-1]["acertou"], bot
met.batalha_fim(venceu=True)
at.fim_da_batalha(venceu=True, duracao=60.0)
r = met.por_instancia()["PERICAO"]
diag = MT.Metricas.diagnostico("PERICAO", r)
print(diag)
assert r["acertos"] == 1 and r["erros"] == 1 and r["especiais"] == 1 and diag.startswith("CHEFAO GLOBAL"), r
assert "PERICAO" not in cb.dados, "Chefao Global: combo fixo, nada a aprender"
assert cb.escolher("PERICAO")[0] == "2,3,4"
print("\nChefao Global (mira reta, numeros de dano, POW) OK")
