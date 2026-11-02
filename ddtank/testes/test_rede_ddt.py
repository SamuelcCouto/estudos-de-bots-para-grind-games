# -*- coding: utf-8 -*-
"""Leitura da rede do jogo (rede_ddt.py): cifra do cliente, recuperacao da chave so pelo trafego, tiros e vez.
Rode: python testes/test_rede_ddt.py"""
import os
import random
import struct
import sys

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(AQUI))
import rede_ddt as R

random.seed(7)
# fluxo sintetico do servidor: 60 pacotes variados, chave de sessao aleatoria (como a sorteada no login)
chave = [random.randrange(256) for _ in range(8)]
K, fluxo, claros = list(chave), bytearray(), []
for n in range(60):
    if n % 3 == 0:                                   # FIRE do servidor: vento, 1 bomba com 1 acao BOMB, 0 alvos
        corpo = bytes([2]) + struct.pack(">i?BBB", -13, False, 1, 0, 3) + struct.pack(">iii?iiiiii", 1, 1, 1, False, 7, 500, 400, -300, -900, 1)
        corpo += struct.pack(">H", 0) + struct.pack(">ii", 1000, 1000) + struct.pack(">i", 1) + struct.pack(">iiiiii", 2400, 2, 610, 455, 1, 0)
        corpo += struct.pack(">i", 0)
        cod = R.GAME_CMD
    else:
        corpo = bytes(random.randrange(256) if random.random() < 0.3 else 0 for _ in range(random.randrange(4, 300)))
        cod = random.choice((R.GAME_CMD, 3, 10, 68))
    p = R.montar_pacote(cod, corpo, client_id=0, e1=n % 2)
    claros.append(p)
    fluxo += R.cifrar(p, K)
fluxo = bytes(fluxo)

ini, Krec, cadeia = R.recuperar_chave(fluxo)
assert ini == 0 and len(cadeia) == 60, (ini, len(cadeia))
assert Krec == chave, (Krec, chave)
ps = R.pacotes(fluxo, ini, Krec)
assert len(ps) == 60 and all(p[6] for p in ps)
assert all(R.montar_pacote(p[1], p[5], p[2], p[3], p[4]) == claros[i] for i, p in enumerate(ps))
print("chave de sessao recuperada SO pelo trafego cifrado; 60 pacotes decifrados com checksum OK")

# comecando no meio de um pacote (captura ligada com o jogo ja rodando): acha o 1o pacote inteiro
meio = fluxo[37:]
ini2, K2, cad2 = R.recuperar_chave(meio)
ps2 = R.pacotes(meio, ini2, K2)
assert len(ps2) >= 55 and all(p[6] for p in ps2)
print("captura comecando no meio de um pacote OK")

t = R.tiro_do_servidor(ps[0][5], ps[0][3])
assert t["vento"] == -1.3 and t["bombas"][0]["vx"] == -300 and t["bombas"][0]["acoes"][0]["tipo"] == "BOMB"
assert t["bombas"][0]["acoes"][0]["p"][:2] == (610, 455)
print("tiro do servidor (vento, X/Y/VX/VY, eventos) OK")

assert R.vento_dos_digitos(False, 1, 0, 8) == -1.8 and R.vento_dos_digitos(True, 10, 0, 5) == 0.5
assert R.vento_dos_digitos(True, 1, 0, 10) == 1.0 and R.vento_dos_digitos(False, 2, 0, 10) == -2.0
print("vento pelos digitos do mostrador OK")
print("\nrede_ddt OK")
