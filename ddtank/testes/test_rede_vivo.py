# -*- coding: utf-8 -*-
"""Leitor ao vivo (rede_vivo.py): TCP fora de ordem/repetido, decifrador incremental e estado da partida, sem administrador.
Rode: python testes/test_rede_vivo.py"""
import os
import random
import struct
import sys
import threading

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(AQUI))
import rede_ddt as R
import rede_vivo as V

# 1) TCP: segmentos repetidos e fora de ordem viram o fluxo certo
m = V.MontadorTCP()
texto = bytes(range(256)) * 4
partes = [(1000 + i, texto[i:i + 100]) for i in range(0, len(texto), 100)]
ordem = [partes[0], partes[2], partes[1], partes[1], partes[3]] + partes[4:] + [partes[5]]
saida = b"".join(m.segmento(s, d) for s, d in ordem)
assert saida == texto, len(saida)
print("TCP fora de ordem e repetido OK")

# 2) fluxo sintetico: chave sorteada, pacotes de vez (TURN) e tiro; entregue em pedacos de tamanhos variados
random.seed(3)
chave = [random.randrange(256) for _ in range(8)]
K, fluxo = list(chave), bytearray()


def vez(quem, turno, x0, x1):
    c = bytes([6]) + struct.pack(">?BBB?ii", True, 1, 0, 3, False, 10, 0) + struct.pack(">i", 2)
    for i, x in ((0, x0), (1, x1)):
        c += struct.pack(">i?iii?iiiiiii", i, True, x, 500, 1000, False, 600, 0, 0, 0, 0, 1, 0)
    return R.montar_pacote(R.GAME_CMD, c + struct.pack(">i?", turno, False), e1=quem)


for n in range(40):
    fluxo += R.cifrar(R.montar_pacote(10, bytes(random.randrange(4)) * random.randrange(10, 200)), K)
    if n % 4 == 0:
        fluxo += R.cifrar(vez(n % 2, n // 4 + 1, 300 + n, 900 - n), K)
fluxo = bytes(fluxo)
pedacos, i, seq = [], 0, 5000
while i < len(fluxo):
    t = random.randrange(1, 900)
    pedacos.append(("servidor", seq + i, fluxo[i:i + t]))
    i += t
eventos = []
leitor = V.LeitorAoVivo(fonte=lambda parar: iter(pedacos), ao_mudar=lambda ev, est: eventos.append(ev))
leitor.consumir(leitor.fonte(threading.Event()))
e = leitor.estado.copia()
assert e["chave_ok"]["servidor"] and e["pacotes"]["servidor"] >= 40, e["pacotes"]
vezes = [d for t, d in eventos if t == "vez"]
assert len(vezes) >= 7 and vezes[-1]["turno"] == 10 and e["vento"] == 1.3, (len(vezes), e["vento"])
assert e["vivos"][0]["x"] == 336 and e["vivos"][1]["x"] == 864 and e["vez"] == 0, e["vivos"]
print("decifrador incremental + estado da vez (posicoes, vento, quem joga) OK")

# 3) captura real, se existir: as 45 vezes e os ~1400 pacotes do servidor
cap = os.path.join(os.path.dirname(AQUI), "capturas_rede", "rede_20261102_162118.pcapng")
if os.path.exists(cap):
    ev = []
    lr = V.LeitorAoVivo(fonte=lambda parar: V.fonte_replay(cap, parar), ao_mudar=lambda x, est: ev.append(x[0]))
    lr.consumir(lr.fonte(lr.parar))
    assert lr.estado.pacotes["servidor"] == 1422 and ev.count("vez") == 45, (lr.estado.pacotes, ev.count("vez"))
    print("captura real (reprise): 1422 pacotes do servidor, 45 vezes OK")
print("\nrede_vivo OK")
