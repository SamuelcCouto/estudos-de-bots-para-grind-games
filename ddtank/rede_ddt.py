# -*- coding: utf-8 -*-
"""
Leitura PASSIVA do trafego do DDTank (so le; nao injeta nada). Base: o codigo do proprio cliente (road7th/comm/ByteSocket.as, PackageIn.as,
PackageOut.as) descompilado do cache local.

Pacote: cabecalho de 20 bytes big-endian  [0x71AB][tamanho][checksum][codigo][clientId:int][extend1:int][extend2:int] + corpo.
Cifra (as duas direcoes, chave de 8 bytes que EVOLUI a cada byte, sem reiniciar entre pacotes):
    i = 0:  p[0] = c[0] ^ K[0]
    i > 0:  K[i%8] = ((K[i%8] + c[i-1]) ^ i) & 0xFF ;  p[i] = ((c[i] - c[i-1]) ^ K[i%8]) & 0xFF      (i = indice DENTRO do pacote)
A chave de sessao e sorteada no login (enviada por RSA), mas cada byte da chave so depende do proprio valor inicial e dos bytes
CIFRADOS -> da para recuperar o estado olhando o trafego: K[0], K[1] pelo 0x71AB; K[2], K[3] pelo tamanho; K[6], K[7] pelo codigo;
K[4], K[5] pelo checksum ((119 + soma(bytes 6..fim)) & 0x7F7F).
"""
import struct
from collections import Counter

PORTA_JOGO = 25565
# Codigos validos de pacote (ddt.data.socket.ePackageType do cliente): filtro forte para achar a chave (K6/K7) sem forca bruta
CODIGOS_PACOTE = frozenset((0, 1, 2, 3, 4, 5, 6, 7, 8, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 24, 25, 26, 27, 28, 29, 30, 31, 32,
    33, 34, 35, 36, 37, 38, 39, 40, 41, 42, 43, 44, 45, 46, 47, 48, 49, 50, 51, 52, 53, 54, 55, 56, 57, 58, 59, 60, 61, 62, 63, 64, 65, 66,
    67, 68, 69, 70, 71, 72, 73, 74, 75, 76, 77, 78, 79, 80, 81, 82, 83, 84, 85, 86, 87, 89, 90, 91, 92, 93, 94, 95, 96, 97, 98, 99, 100,
    101, 102, 103, 104, 105, 106, 107, 108, 109, 110, 111, 112, 113, 114, 115, 116, 117, 118, 119, 120, 121, 122, 123, 124, 125, 126, 127,
    128, 129, 130, 131, 132, 133, 134, 135, 136, 137, 138, 139, 140, 142, 143, 144, 145, 146, 147, 148, 149, 150, 151, 152, 153, 154, 155,
    156, 157, 158, 159, 160, 161, 162, 163, 164, 165, 166, 167, 168, 169, 170, 171, 172, 173, 174, 175, 176, 177, 178, 179, 180, 181, 182,
    183, 184, 185, 186, 187, 188, 189, 190, 191, 192, 193, 194, 195, 196, 197, 198, 199, 200, 201, 202, 203, 205, 206, 207, 208, 209, 210,
    211, 212, 213, 214, 215, 216, 217, 218, 219, 220, 221, 222, 223, 224, 225, 226, 227, 228, 229, 230, 231, 232, 233, 234, 235, 236, 237,
    238, 239, 240, 241, 242, 243, 244, 245, 246, 247, 248, 249, 250, 251, 252, 253, 254, 255, 257, 258, 259, 265, 272, 275, 278, 279, 286,
    288, 290, 297, 327, 328, 345, 352, 360, 373, 402, 403, 404, 405, 456, 478, 493, 765))
KEY_PADRAO = [174, 191, 86, 120, 171, 205, 239, 241]   # ByteSocket.KEY: chave fixa usada ate o login (depois, a sorteada)
MAGIC = 0x71AB
CAB = 20


# ------------------------------------------------------------------------------------------------ pcapng + TCP
def ler_pcapng(caminho):
    """[(tempo_s, src, dst, sport, dport, seq, flags, payload)] dos segmentos TCP (Ethernet/IPv4/IPv6) de um .pcapng."""
    b = open(caminho, "rb").read()
    pos, saida, ts_res = 0, [], {}
    end = "<"
    while pos + 12 <= len(b):
        tipo, tam = struct.unpack(end + "II", b[pos:pos + 8])
        if tipo == 0x0A0D0D0A:                                  # section header: descobre a ordem dos bytes
            bom = b[pos + 8:pos + 12]
            end = "<" if bom == b"\x4d\x3c\x2b\x1a" else ">"
            tipo, tam = struct.unpack(end + "II", b[pos:pos + 8])
        corpo = b[pos + 8:pos + tam - 4]
        if tipo == 6 and len(corpo) >= 20:                      # enhanced packet block
            _iface, th, tl, caplen, _orig = struct.unpack(end + "IIIII", corpo[:20])
            pkt = corpo[20:20 + caplen]
            t = ((th << 32) | tl) / 1e6
            seg = _tcp(pkt)
            if seg:
                saida.append((t,) + seg)
        pos += tam if tam >= 12 else 12
    return saida


def _tcp(pkt):
    if len(pkt) < 14:
        return None
    eth = struct.unpack("!H", pkt[12:14])[0]
    off = 14
    if eth == 0x8100:
        eth = struct.unpack("!H", pkt[16:18])[0]
        off = 18
    if eth == 0x0800:
        ihl = (pkt[off] & 0x0F) * 4
        if pkt[off + 9] != 6:
            return None
        tot = struct.unpack("!H", pkt[off + 2:off + 4])[0]
        src, dst = pkt[off + 12:off + 16].hex(), pkt[off + 16:off + 20].hex()
        tcp, fim = off + ihl, off + tot
    elif eth == 0x86DD:
        if pkt[off + 6] != 6:
            return None
        plen = struct.unpack("!H", pkt[off + 4:off + 6])[0]
        src, dst = pkt[off + 8:off + 24].hex(), pkt[off + 24:off + 40].hex()
        tcp, fim = off + 40, off + 40 + plen
    else:
        return None
    sport, dport, seq = struct.unpack("!HHI", pkt[tcp:tcp + 8])
    doff = (pkt[tcp + 12] >> 4) * 4
    flags = pkt[tcp + 13]
    return src, dst, sport, dport, seq, flags, pkt[tcp + doff:fim]


def fluxos(segmentos, porta=PORTA_JOGO):
    """Remonta os dois sentidos da conexao do jogo: {'servidor': bytes, 'cliente': bytes} + marcas de tempo por byte (inicio de segmento).
    Ignora retransmissoes (mesmo seq) e ordena por seq."""
    dirs = {}
    for t, src, dst, sp, dp, seq, fl, pl in segmentos:
        if not pl or PORTA_JOGO not in (sp, dp):
            continue
        lado = "servidor" if sp == porta else "cliente"
        dirs.setdefault((lado, src, dst, sp, dp), []).append((seq, t, pl))
    res = {}
    for (lado, *_k), segs in dirs.items():
        base = segs[0][0]                                       # seq do 1o segmento capturado
        segs.sort(key=lambda s: (s[0] - base) & 0xFFFFFFFF)
        buf, tempos, prox = bytearray(), [], 0
        for seq, t, pl in segs:
            rel = (seq - base) & 0xFFFFFFFF
            if rel + len(pl) <= prox:
                continue                                        # retransmissao
            if rel < prox:
                pl = pl[prox - rel:]
                rel = prox
            if rel > prox:
                tempos.append((len(buf), t, "BURACO"))         # pacote perdido na captura
            tempos.append((len(buf), t, "seg"))
            buf += pl
            prox = rel + len(pl)
        if lado not in res or len(buf) > len(res[lado][0]):
            res[lado] = (bytes(buf), tempos)
    return res


# ------------------------------------------------------------------------------------------------ cifra
def decifrar(c, K, ini, n):
    """Decifra o pacote c[ini:ini+n] com o estado K (lista de 8 ints), ATUALIZANDO K (como PackageIn.loadE). Devolve bytes."""
    p = bytearray(n)
    for i in range(n):
        if i == 0:
            p[0] = c[ini] ^ K[0]
        else:
            j = i & 7
            K[j] = ((K[j] + c[ini + i - 1]) ^ i) & 0xFF
            p[i] = ((c[ini + i] - c[ini + i - 1]) ^ K[j]) & 0xFF
    return bytes(p)


def _k01_do_magic(c, s):
    k0 = c[s] ^ 0x71
    k1l = ((c[s + 1] - c[s]) & 0xFF) ^ 0xAB
    return k0, ((k1l ^ 1) - c[s]) & 0xFF


def _proximos_l(c, s, k0, k1, lmax=16384):
    """Tamanhos L possiveis para o pacote em s: o byte s+L tem que decifrar para o magic 0x71AB com K0/K1 evoluidos."""
    res = []
    for i in range(1, min(lmax, len(c) - s - 2)):
        j = i & 7
        if j == 0:
            k0 = ((k0 + c[s + i - 1]) ^ i) & 0xFF
        elif j == 1:
            k1 = ((k1 + c[s + i - 1]) ^ i) & 0xFF
        L = i + 1                                               # bytes s..s+i processados -> proximo comeca em s+i+1
        q = s + L
        if L >= CAB and q + 1 < len(c) and c[q] ^ k0 == 0x71:
            k1n = ((k1 + c[q]) ^ 1) & 0xFF
            if ((c[q + 1] - c[q]) ^ k1n) & 0xFF == 0xAB:
                res.append(L)
    return res


def _limites(c, s):
    """Tenta montar a cadeia de pacotes a partir de s usando so K0/K1 + tamanhos. Devolve (lista de (ini, L), K0..K3) ou None."""
    k0, k1 = _k01_do_magic(c, s)
    for L in _proximos_l(c, s, k0, k1):
        p2 = (L >> 8) & 0xFF
        p3 = L & 0xFF
        # K2, K3 iniciais a partir do tamanho do 1o pacote
        k2l = ((c[s + 2] - c[s + 1]) & 0xFF) ^ p2
        k3l = ((c[s + 3] - c[s + 2]) & 0xFF) ^ p3
        K = [k0, k1, ((k2l ^ 2) - c[s + 1]) & 0xFF, ((k3l ^ 3) - c[s + 2]) & 0xFF, 0, 0, 0, 0]
        Kt, pos, cadeia, ok = list(K), s, [], True
        while pos + CAB <= len(c):
            Kc = list(Kt)
            cab = decifrar(c, Kc, pos, 4)
            m, Ln = struct.unpack(">HH", cab)
            if m != MAGIC or Ln < CAB:
                ok = len(cadeia) >= 20
                break
            if pos + Ln > len(c):
                break
            decifrar(c, Kt, pos, Ln)                            # so para evoluir a chave (K4..K7 ainda errados, nao importa aqui)
            cadeia.append((pos, Ln))
            pos += Ln
        if ok and len(cadeia) >= 5:
            return cadeia, K[:4]
    return None


def _melhor_byte(c, cadeia, j, nota):
    """Valor inicial de K[j] (0-255) que maximiza nota(lista de (indice_pacote, i, p)). Cada byte da chave e independente."""
    melhor = None
    for k in range(256):
        kk, vals = k, []
        for n, (ini, L) in enumerate(cadeia):
            for i in range(j if j else 0, L, 8):
                if i == 0:
                    vals.append((n, 0, c[ini] ^ kk))
                    continue
                kk = ((kk + c[ini + i - 1]) ^ i) & 0xFF
                vals.append((n, i, ((c[ini + i] - c[ini + i - 1]) ^ kk) & 0xFF))
        sc = nota(vals)
        if melhor is None or sc > melhor[0]:
            melhor = (sc, k)
    return melhor[1]


def recuperar_chave(c, codigos_validos=None, max_inicio=4096):
    """Estado da chave no inicio do 1o pacote inteiro do fluxo c. Devolve (inicio, K[8], cadeia de (ini, L))."""
    for s in range(0, min(max_inicio, len(c) - CAB)):
        r = _limites(c, s)
        if r:
            cadeia, k03 = r
            break
    else:
        raise ValueError("nao achei o inicio de pacote (0x71AB) nos primeiros bytes")
    K = k03 + _k4567_pelo_checksum(c, cadeia, k03)
    return cadeia[0][0], K, cadeia


def _somas_byte(c, cadeia, j, n_pac):
    """Para cada valor inicial k (0-255) de K[j]: (soma dos bytes decifrados em i>=6 com i%8==j, byte decifrado no indice j)
    por pacote, nos n_pac primeiros pacotes. Matrizes [256, n_pac]."""
    import numpy as np
    soma = np.zeros((256, n_pac), np.int64)
    byte_j = np.zeros((256, n_pac), np.int64)
    for k in range(256):
        kk = k
        for n, (ini, L) in enumerate(cadeia):
            if n >= n_pac:
                break
            for i in range(j, L, 8):
                kk = ((kk + c[ini + i - 1]) ^ i) & 0xFF
                p = ((c[ini + i] - c[ini + i - 1]) ^ kk) & 0xFF
                if i == j:
                    byte_j[k, n] = p
                if i >= 6:
                    soma[k, n] += p
    return soma, byte_j


def _k4567_pelo_checksum(c, cadeia, k03, n_pac=40):
    """K4..K7 exatos. 1) K6/K7: o codigo do pacote (bytes 6-7) tem que ser um codigo VALIDO do jogo (CODIGOS_PACOTE) em quase todos os
    pacotes -> sobram 1-2 pares. 2) K4/K5 pelo checksum ((119 + soma(bytes 6..fim)) & 0x7F7F == bytes 4-5), que separa por byte da
    chave: 65 mil pares testados de uma vez com numpy. (Antes: 16 milhoes x ate 118 candidatos = 1,5 min.)"""
    import numpy as np
    n_pac = min(n_pac, len(cadeia))
    s4, b4 = _somas_byte(c, cadeia, 4, n_pac)
    s5, b5 = _somas_byte(c, cadeia, 5, n_pac)
    s6, b6 = _somas_byte(c, cadeia, 6, n_pac)
    s7, b7 = _somas_byte(c, cadeia, 7, n_pac)
    base = np.zeros(n_pac, np.int64)
    K = list(k03) + [0, 0, 0, 0]
    for n, (ini, L) in enumerate(cadeia[:n_pac]):
        p = decifrar(c, K, ini, L)
        base[n] = 119 + sum(p[i] for i in range(6, L) if (i & 7) < 4)
    validos = np.zeros(65536, bool)
    validos[list(CODIGOS_PACOTE)] = True
    codigos = (b6[:, None, :] << 8) | b7[None, :, :]                   # [k6, k7, pacote]
    frac = validos[codigos].mean(axis=2)
    pares = sorted(((float(frac[a, b]), int(a), int(b)) for a, b in np.argwhere(frac >= 0.9)), reverse=True)
    if not pares:                                                       # protocolo diferente: codigos desconhecidos
        pares = [(0.0, int(a), int(b)) for a in range(256) for b in range(256)]
    alvo = (b4[:, None, :] << 8) | b5[None, :, :]                        # [k4, k5, pacote]
    for _f, k6, k7 in pares:
        x = (base + s6[k6] + s7[k7])[None, None, :] + s4[:, None, :] + s5[None, :, :]
        ok = (((x & 0x7F7F) == alvo).mean(axis=2)) > 0.99
        cand = np.argwhere(ok)
        if len(cand):
            k4, k5 = cand[0]
            return [int(k4), int(k5), k6, k7]
    raise ValueError("checksum nao fechou para nenhum K4..K7")


def cifrar(p, K):
    """Cifra um pacote como ByteSocket.send (para testes). ATUALIZA K."""
    c = bytearray(p)
    for i in range(len(c)):
        if i == 0:
            c[0] = p[0] ^ K[0]
        else:
            j = i & 7
            K[j] = ((K[j] + c[i - 1]) ^ i) & 0xFF
            c[i] = ((p[i] ^ K[j]) + c[i - 1]) & 0xFF
    return bytes(c)


def montar_pacote(codigo, corpo, client_id=0, e1=0, e2=0):
    """Pacote em claro como PackageOut.pack (cabecalho de 20 bytes + checksum)."""
    p = bytearray(struct.pack(">HHHhiii", MAGIC, CAB + len(corpo), 0, codigo, client_id, e1, e2) + corpo)
    struct.pack_into(">H", p, 4, (119 + sum(p[6:])) & 0x7F7F)
    return bytes(p)


def checksum_ok(p):
    soma = (119 + sum(p[6:])) & 0x7F7F
    return struct.unpack(">H", p[4:6])[0] == soma


def pacotes(c, inicio, K):
    """Decifra o fluxo inteiro a partir de inicio com o estado K: [(offset, codigo, clientId, extend1, extend2, corpo, checksum_ok)]."""
    K, pos, res = list(K), inicio, []
    while pos + CAB <= len(c):
        Kc = list(K)
        m, L = struct.unpack(">HH", decifrar(c, Kc, pos, 4))
        if m != MAGIC or pos + L > len(c) or L < CAB:
            break
        p = decifrar(c, K, pos, L)
        _m, _l, _ck, cod, cid, e1, e2 = struct.unpack(">HHHhiii", p[:CAB])
        res.append((pos, cod, cid, e1, e2, p[CAB:], checksum_ok(p)))
        pos += L
    return res


# ------------------------------------------------------------------------------------------------ comandos de jogo (codigo 91)
GAME_CMD = 91
SUB = {"MOVE": 1, "FIRE": 2, "TURN": 6, "MOVESTART": 9, "DIRECTION": 7, "WIND_PIC": 241, "START_GAME": 99, "GAME_OVER": 100,
       "GAME_CREATE": 101, "GAME_LOAD": 103, "ADD_LIVING": 64, "LIVING_MOVETO": 55}
ACAO = {1: "PICK", 2: "BOMB", 3: "START_MOVE", 4: "FLY_OUT", 5: "KILL_PLAYER", 6: "TRANSLATE", 7: "FORZEN", 8: "CHANGE_SPEED",
        9: "UNFORZEN", 10: "DANER", 11: "CURE", 12: "GEM_DEFENSE", 13: "CHANGE_STATE", 14: "DO_ACTION", 15: "PLAYBUFFER",
        16: "LASER", 17: "BOMBED", 18: "PUP", 19: "AUP", 20: "PET"}


class Leitor:
    def __init__(self, b, pos=0):
        self.b, self.p = b, pos

    def i32(self):
        v = struct.unpack(">i", self.b[self.p:self.p + 4])[0]
        self.p += 4
        return v

    def u8(self):
        v = self.b[self.p]
        self.p += 1
        return v

    def bool(self):
        return self.u8() != 0

    def utf(self):
        n = struct.unpack(">H", self.b[self.p:self.p + 2])[0]
        s = self.b[self.p + 2:self.p + 2 + n].decode("utf-8", "replace")
        self.p += 2 + n
        return s


def living_novo(corpo):
    """GameView.addliving (sub 64): boss/monstro/elite que entrou na luta: tipo, id, nome, modelo, animacao, posicao (px do mapa), vida
    maxima e atual, direcao. (Os TURN so listam os jogadores: os bosses vem por aqui e se movem por START_MOVE nos tiros / LIVING_MOVETO.)"""
    r = Leitor(corpo, 1)
    tipo, ident = r.u8(), r.i32()
    nome, modelo, anim = r.utf(), r.utf(), r.utf()
    x, y = r.i32(), r.i32()
    vida_max, vida, _x = r.i32(), r.i32(), r.i32()
    direcao = r.u8()
    if direcao > 127:
        direcao -= 256
    return dict(tipo=tipo, id=ident, nome=nome, modelo=modelo, anim=anim, x=x, y=y, vida_max=vida_max, vida=vida, direcao=direcao)


def tiro_do_cliente(corpo):
    """GameInSocketOut.sendGameCMDShoot: x, y (px do mapa, ponto de saida), forca 0-2000, angulo (graus, y para baixo)."""
    x, y, forca, ang = struct.unpack(">iiii", corpo[1:17])
    return dict(x=x, y=y, forca=forca, angulo=ang)


def tiro_do_servidor(corpo, quem):
    """GameView.__shoot: vento (/10), projeteis (X, Y, VX, VY, bala, eventos) e alvos atingidos (dano, vida)."""
    r = Leitor(corpo, 1)
    vento = r.i32() / 10.0
    r.bool(); r.u8(); r.u8(); r.u8()
    bombas = []
    for _ in range(r.i32()):
        b = dict(numero=r.i32(), contagem=r.i32(), buraco=r.bool(), id=r.i32(), x=r.i32(), y=r.i32(), vx=r.i32(), vy=r.i32(),
                 bala=r.i32())
        b["particula"] = r.utf()
        b["raio_mod"], b["poder_mod"] = r.i32() / 1000, r.i32() / 1000
        b["acoes"] = []
        for _a in range(r.i32()):
            t, tipo, p1, p2, p3, p4 = (r.i32() for _k in range(6))
            b["acoes"].append(dict(tempo=t, tipo=ACAO.get(tipo, tipo), p=(p1, p2, p3, p4)))
        bombas.append(b)
    alvos = []
    try:
        for _ in range(r.i32()):
            alvos.append(dict(vivo=r.i32(), dano=r.i32(), vida=r.i32(), furia=r.i32()))
    except struct.error:
        pass
    return dict(atirador=quem, vento=vento, bombas=bombas, alvos=alvos)


def vento_dos_digitos(positivo, d1, d2, d3):
    """Vento como o mostrador do jogo (Game.GetVane): d1 = unidade, d2 = o ponto (sempre 0), d3 = decimo; 10 = zero.
    Medido em 99 tiros: o vento da vez e exatamente o vento do tiro (ex.: (False, 1, 0, 8) = -1.8; (True, 10, 0, 5) = 0.5)."""
    v = (d1 % 10) + (d3 % 10) / 10.0
    return v if positivo else -v


def vez_do_servidor(corpo, quem):
    """ChangePlayerAction.syncMap (sub 6): vento (digitos), tempo do turno, caixas e TODOS os bonecos (id, vivo, x, y em px do mapa,
    vida, energia, furia, tiros no turno, voos), numero do turno. `quem` = id de quem joga agora (extend1)."""
    r = Leitor(corpo, 1)
    pos, d1, d2, d3 = r.bool(), r.u8(), r.u8(), r.u8()
    out = dict(quem=quem, vento=vento_dos_digitos(pos, d1, d2, d3), oculto=r.bool(), tempo_turno=r.i32(), caixas=[], vivos=[])
    for _ in range(r.i32()):
        out["caixas"].append(dict(id=r.i32(), x=r.i32(), y=r.i32(), tipo=r.i32()))
    for _ in range(r.i32()):
        d = dict(id=r.i32(), vivo=r.bool(), x=r.i32(), y=r.i32(), vida=r.i32())
        r.bool()
        d["energia_max"] = r.i32()
        r.i32()
        d["furia"] = r.i32()
        r.i32(); r.i32()
        d["tiros"], d["voos"] = r.i32(), r.i32()
        out["vivos"].append(d)
    out["turno"] = r.i32()
    return out


def ler_partida(caminho_pcapng):
    """Le uma captura e devolve a linha do tempo da partida: [('vez', dict) | ('tiro_servidor', dict) | ('tiro_cliente', dict)]."""
    f = fluxos(ler_pcapng(caminho_pcapng))
    eventos = []
    for lado in ("servidor", "cliente"):
        if lado not in f:
            continue
        c = f[lado][0]
        ini, K, _ = recuperar_chave(c)
        for off, cod, cid, e1, e2, corpo, ok in pacotes(c, ini, K):
            if cod != GAME_CMD or not corpo or not ok:
                continue
            sub = corpo[0]
            try:
                if lado == "servidor" and sub == SUB["TURN"]:
                    eventos.append((lado, off, "vez", vez_do_servidor(corpo, e1)))
                elif lado == "servidor" and sub == SUB["FIRE"]:
                    eventos.append((lado, off, "tiro_servidor", tiro_do_servidor(corpo, e1)))
                elif lado == "cliente" and sub == SUB["FIRE"]:
                    eventos.append((lado, off, "tiro_cliente", tiro_do_cliente(corpo)))
            except (struct.error, IndexError):
                pass
    return eventos
