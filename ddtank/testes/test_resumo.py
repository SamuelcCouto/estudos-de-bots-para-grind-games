# -*- coding: utf-8 -*-
"""Contadores da execucao (estatisticas), reconhecimento do que veio nas cartas (drops) e tarefas a cada N voltas.
Rode: python testes/test_resumo.py"""
import os
import sys
import tempfile

import cv2

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(AQUI))
import drops as D
import estatisticas as ES
import navegador as N

# ---------------------------------------------------------------- estatisticas
relogio = [1000.0]
arq = os.path.join(tempfile.mkdtemp(), "e.json")
e = ES.Estatisticas(arq=arq, agora=lambda: relogio[0], nome_rota="Rota Sul")
e.luta("RAINHA_LIRIS", True); e.luta("ESCORPIAO_REI", True); e.luta("ESCORPIAO_REI", False)
e.volta(); e.missoes(3); e.drop("abobora", 2); e.drop("item_001"); e.pausa(60)
relogio[0] += 3660
e.salvar()
txt = ES.texto_resumo(ES.ler(arq), {"abobora": "Abobora", "RAINHA_LIRIS": "Rainha Liris"})
print(txt)
assert "Voltas completas:    1" in txt and "Missoes concluidas:  3" in txt and "Cartas abertas:      3" in txt
assert "Abobora" in txt and "2" in txt and "1h00min" in txt and "derrotas: 1" in txt, txt     # 3660 s - 60 s pausado = 1h00
assert ES.texto_resumo(None).startswith("Ainda nao")
print("estatisticas OK")

# ---------------------------------------------------------------- drops: icone de cada carta virada
f = N.em_1280(cv2.imread(os.path.join(AQUI, "frames", "CARTAS_REVELADAS.jpg")))
cat = D.Catalogo(pasta_conhecidos=tempfile.mkdtemp(), pasta_vistos=tempfile.mkdtemp(), arq_nomes=os.path.join(tempfile.mkdtemp(), "n.json"))
pos = lambda col, lin: (N.CARTAS_COLUNAS[col], N.CARTAS_LINHAS[lin])
brocos_a, brocos_b = cat.reconhecer(f, pos(0, 1)), cat.reconhecer(f, pos(2, 1))      # "Brocos avancados" x2
tartaruga, suzaku = cat.reconhecer(f, pos(1, 1)), cat.reconhecer(f, pos(2, 0))
tartaruga2 = cat.reconhecer(f, pos(3, 1))                                            # "Pedra de Tartaruga Negra nivel 3"
assert brocos_a == brocos_b, (brocos_a, brocos_b)
assert tartaruga == tartaruga2 and tartaruga != brocos_a, (tartaruga, tartaruga2, brocos_a)
assert len({brocos_a, tartaruga, suzaku}) == 3
assert len(os.listdir(cat.pasta_vistos)) == len(cat.itens) and all(k.startswith("item_") for k in cat.itens)
# catalogo conhecido: o nome do arquivo vira o nome do item
conhecidos = tempfile.mkdtemp()
x, y = pos(0, 1); dx0, dy0, dx1, dy1 = D.ICONE
cv2.imwrite(os.path.join(conhecidos, "brocos.png"), f[y + dy0:y + dy1, x + dx0:x + dx1])
cat2 = D.Catalogo(pasta_conhecidos=conhecidos, pasta_vistos=tempfile.mkdtemp(), arq_nomes=os.path.join(tempfile.mkdtemp(), "n.json"))
assert cat2.reconhecer(f, pos(2, 1)) == "brocos" and cat2.nome_bonito("brocos") == "Brocos"
print("drops (icones das cartas) OK")

# ---------------------------------------------------------------- o navegador conta o que veio (so nas SUAS 3 cartas, depois de ~1 s)
relogio = [0.0]; logs = []
est = ES.Estatisticas(arq=os.path.join(tempfile.mkdtemp(), "e.json"), agora=lambda: relogio[0])
nav = N.Navegador(None, None, ["FANTASMA"], agora=lambda: relogio[0], dormir=lambda s: None, log=logs.append, estat=est, catalogo=cat2)
nav.cartas_escolhidas = [pos(0, 1), pos(2, 1), pos(1, 1)]
costas = [p for p in N.CARTAS_TODAS if p not in nav.cartas_escolhidas]
nav.contar_drops(f, costas); assert est.d["cartas"] == 0, "espera a animacao"
relogio[0] += 1.2
nav.contar_drops(f, costas)
assert est.d["cartas"] == 3 and est.d["drops"]["brocos"] == 2, est.d
nav.contar_drops(f, costas); assert est.d["cartas"] == 3, "conta uma vez so por instancia"
assert any("[CARTAS] vieram" in l for l in logs)
print("contagem no navegador OK")

# ---------------------------------------------------------------- Gato Preto: aboboras (Medalha de abobora / Brilho da Abobora) nas cartas reais
g = cv2.imread(os.path.join(AQUI, "frames", "GATO_CARTAS.jpg"))
cat3 = D.Catalogo(pasta_vistos=tempfile.mkdtemp(), arq_nomes=os.path.join(tempfile.mkdtemp(), "n.json"))      # usa templates/drops
assert {"medalha_de_abobora", "brilho_da_abobora"} <= set(cat3.itens), cat3.itens.keys()
assert cat3.reconhecer(g, pos(3, 0)) == "medalha_de_abobora" and cat3.reconhecer(g, pos(3, 1)) == "brilho_da_abobora"
est3 = ES.Estatisticas(arq=os.path.join(tempfile.mkdtemp(), "e.json"), agora=lambda: 0.0)
est3.drop("medalha_de_abobora"); est3.drop("brilho_da_abobora", 2); est3.drop("item_001")
t3 = ES.texto_resumo(ES.ler(est3.arq))
assert "Aboboras:            3" in t3, t3
print("aboboras (cartas do Gato Preto) OK")

# ---------------------------------------------------------------- Gato Preto: repor os perks Z/X/C na sala antes do Inicio
import leitura as LL
class IOCliques:
    k = 1.0
    def __init__(self): self.cliques = []
    def clicar(self, x, y, modo): self.cliques.append((x, y))
    def tecla_apertada(self, vk): return False
logs = []
nav = N.Navegador(IOCliques(), None, ["GATO_PRETO"], agora=lambda: 0.0, dormir=lambda s: None, log=logs.append)
vazio = cv2.imread(os.path.join(AQUI, "frames", "GATO_SALA_PERKS_VAZIO.jpg"))
cheio = cv2.imread(os.path.join(AQUI, "frames", "GATO_SALA_PERKS_CHEIO.jpg"))
parcial = cv2.imread(os.path.join(AQUI, "frames", "GATO_SALA_PERKS_2.jpg"))
assert nav.repor_perks(vazio) is True and nav.io.cliques.count(LL.PERK_COMPRAR) == 3 and nav.io.cliques[-1] == N.FOCO_PONTO_PADRAO
nav.io.cliques.clear()
assert nav.repor_perks(parcial) is True and nav.io.cliques.count(LL.PERK_COMPRAR) == 1, "so 1 quadro vazio: 1 perk"
assert nav.repor_perks(cheio) is False and any("repostos" in l for l in logs)
nav.perks_tentativas = 0
nav.repor_perks(vazio); nav.repor_perks(vazio)
assert nav.repor_perks(vazio) is False and any("nao consegui repor" in l for l in logs), "sem vigor: desiste em vez de ficar clicando"
print("reposicao de perks na sala OK")
print("resumo OK")
