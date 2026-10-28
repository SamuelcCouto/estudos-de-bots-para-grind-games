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

CUSTOS = {1: 110, 2: 110, 3: 110, 4: 85, 5: 80, 6: 70, 7: 55, 8: 50}

class Mundo:
    """Simula a batalha: relogio, ponteiro do angulo, barra de forca, stamina/itens, PASS e vida do boss."""
    def __init__(self, angulo=15.0, stamina=240, setas_funcionam_em=("top", "filha"), vez_inicio=1.0, vez_fim=9.0,
                 boss_hit=True):
        self.t = 0.0; self.angulo = angulo; self.stamina = stamina; self.modo = "top"
        self.setas_ok = setas_funcionam_em; self.vez = (vez_inicio, vez_fim)
        self.carregando_desde = None; self.barra = 0.0; self.teclas = []; self.itens_apertados = []
        self.vida = 100.0; self.boss_hit = boss_hit; self.atirou_em = None; self.tiros = []
        self.azul, self.boss = (38.0, 67.0), (73.1, 64.5)
    # --- io do atirador
    def avancar(self, s):
        self.t += s
        if self.carregando_desde is not None:
            self.barra = min(100.0, (self.t - self.carregando_desde) * 38.0)
    def capturar(self):
        self.avancar(0.06)                                   # custo da captura
        vez = self.vez[0] <= self.t <= self.vez[1] and self.atirou_em is None or (self.atirou_em and self.t < self.vez[1])
        if self.atirou_em and self.t > self.atirou_em + 3 and self.boss_hit and self.vida == 100.0:
            self.vida = 58.0                                 # a bala cai ~3 s depois e tira vida
        return {"vez": vez, "ang": self.angulo, "barra": self.barra, "azul": self.azul, "boss": self.boss,
                "itens": [self.stamina >= CUSTOS[i] for i in range(1, 9)], "vida": self.vida}
    def tecla(self, nome, dur=0.05):
        self.teclas.append((nome, round(dur, 2)))
        if nome in ("cima", "baixo") and self.modo in self.setas_ok:
            self.angulo += (1 if nome == "cima" else -1) * 30.0 * dur
        if nome.isdigit():
            item = int(nome)
            if self.stamina >= CUSTOS[item]:
                self.stamina -= CUSTOS[item]; self.itens_apertados.append(item)
        self.avancar(dur)
    def tecla_baixo(self, nome, rep=1):
        if self.carregando_desde is None: self.carregando_desde = self.t
    def tecla_cima(self, nome):
        real = min(100.0, (self.t - self.carregando_desde) * 38.0)   # forca REAL = tempo segurado (a barra exibida pode estar velha)
        self.avancar(0.1)                                    # atraso do KEYUP
        self.tiros.append(real); self.carregando_desde = None; self.atirou_em = self.t
    def trocar_modo(self): self.modo = "filha" if self.modo == "top" else "top"
    def dormir(self, s): self.avancar(s)

class Leitor:
    def preparar(self, img): return img
    minha_vez = staticmethod(lambda f: f["vez"])
    angulo = staticmethod(lambda f: f["ang"])
    forca = staticmethod(lambda f: f["barra"])
    pontos = staticmethod(lambda f: (f["azul"], f["boss"]))
    itens = staticmethod(lambda f: f["itens"])
    vida = staticmethod(lambda f: f["vida"])

def novo(mundo, sombra=False):
    tmp = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False); tmp.close(); os.unlink(tmp.name)
    mem = M.Memoria(arq_aprendizado=tmp.name)
    logs = []
    at = A.Atirador(mundo, mem, lambda: "MINHOCAO", leitor=Leitor(), sombra=sombra, dormir=mundo.dormir,
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
alvo = 38.0
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
at.ajustar_angulo = lambda alvo: (setattr(w, "angulo", 30.0) or True)    # o ajuste "parou" em 30 graus
rodar(at, w)
assert any("recalculada" in l for l in logs), logs
print("forca recalculada quando o angulo nao chega no previsto OK")
print("\natirador (regressoes) OK")
