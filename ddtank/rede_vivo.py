# -*- coding: utf-8 -*-
"""
Leitura AO VIVO da rede do DDTank, so com a biblioteca padrao do Python (nada para instalar, sem administrador, sem driver).
So LE (nao injeta, nao altera nada).

Fonte principal (02/11): o REGISTRO DE REDE do proprio Chromium. O BetelTank e um Electron 6 (Chromium 76): aberto com
`--log-net-log=<arquivo> --net-log-capture-mode=IncludeSocketBytes`, ele grava no arquivo os bytes de cada conexao, inclusive a do
jogo (porta 25565). O bot le esse arquivo enquanto ele cresce. (Descartados: o socket bruto do Windows nao ve a conexao IPv6 do
jogo; o WinDivert e bloqueado pelo Windows Defender.)
ATENCAO: esse registro grava os bytes JA DECIFRADOS de TODAS as conexoes do launcher (inclusive o site). Se digitar a senha nessa
sessao, ela fica no arquivo: os registros ficam em capturas_rede/ (fora do git) e os antigos sao apagados a cada novo inicio.

    python rede_vivo.py --abrir-jogo          # abre o jogo com o registro ligado e mostra ao vivo: vez, posicoes, vento, tiros
    python rede_vivo.py --netlog arquivo.json # so le um registro (do jogo ja aberto assim)
    python rede_vivo.py --replay captura.pcapng   # le uma captura do CAPTURAR_REDE.bat

Uso no bot:  leitor = LeitorAoVivo(fonte=lambda parar: fonte_netlog(caminho, parar)).iniciar(); ... leitor.estado.copia()

Como funciona: separa os bytes da conexao do jogo, recupera a chave de sessao so pelo trafego (rede_ddt.recuperar_chave) e
decifra pacote a pacote.
"""
import argparse
import base64
import ctypes
import datetime
import glob
import json
import os
import re
import socket
import struct
import subprocess
import threading
import time

import rede_ddt as R

PASTA = os.path.dirname(os.path.abspath(__file__))
PASTA_LOGS = os.path.join(PASTA, "capturas_rede")
CAMINHOS_JOGO = (r"D:\DDTBETEL\BetelTank.exe", r"C:\DDTBETEL\BetelTank.exe", r"C:\Program Files\DDTBETEL\BetelTank.exe",
                 r"C:\Program Files (x86)\DDTBETEL\BetelTank.exe")
MIN_BYTES_CHAVE = {"servidor": 3000, "cliente": 500}   # o cliente manda pouco: com 500 bytes ja da para achar a chave dele
_MIN_BYTES_ANTIGO = 3000          # bytes acumulados antes de tentar achar a chave (servidor: ~1-3 s de jogo)


# ------------------------------------------------------------------------------------------------ TCP incremental
class MontadorTCP:
    """Junta os segmentos de UM sentido na ordem do seq (descarta repetidos, espera os que chegam fora de ordem)."""
    def __init__(self):
        self.prox = None
        self.pendentes = {}

    def segmento(self, seq, dados):
        if not dados:
            return b""
        if self.prox is None:
            self.prox = seq
        rel = (seq - self.prox) & 0xFFFFFFFF
        if rel >= 0x80000000:                                   # antes do que ja temos (retransmissao)
            corte = (self.prox - seq) & 0xFFFFFFFF
            if corte >= len(dados):
                return b""
            dados, seq, rel = dados[corte:], self.prox, 0
        if rel > 0:
            if len(self.pendentes) < 2000:
                self.pendentes[seq] = dados
            return b""
        saida = bytearray(dados)
        self.prox = (self.prox + len(dados)) & 0xFFFFFFFF
        while True:
            achou = False
            for s in list(self.pendentes):
                r = (s - self.prox) & 0xFFFFFFFF
                if r == 0 or r >= 0x80000000:
                    d = self.pendentes.pop(s)
                    corte = (self.prox - s) & 0xFFFFFFFF if r else 0
                    if corte < len(d):
                        saida += d[corte:]
                        self.prox = (self.prox + len(d) - corte) & 0xFFFFFFFF
                    achou = True
            if not achou:
                break
        return bytes(saida)


# ------------------------------------------------------------------------------------------------ decifrador incremental
class Decifrador:
    """Recebe os bytes cifrados de um sentido conforme chegam; acha a chave quando ha dados suficientes e depois devolve os pacotes
    decifrados [(codigo, clientId, extend1, extend2, corpo)]."""
    def __init__(self, minimo=3000):
        self.buf = bytearray()
        self.K = None
        self.tentativa = 0
        self.minimo = minimo

    def alimentar(self, dados):
        self.buf += dados
        if self.K is None:
            if len(self.buf) < self.minimo or len(self.buf) < self.tentativa + max(300, self.minimo // 2):
                return []
            self.tentativa = len(self.buf)
            try:
                ini, K, _cad = R.recuperar_chave(bytes(self.buf))
            except (ValueError, IndexError):
                if len(self.buf) > 200_000:
                    del self.buf[:100_000]                      # nao achou: descarta o comeco e tenta de novo depois
                    self.tentativa = 0
                return []
            del self.buf[:ini]
            self.K = K
        saida = []
        while len(self.buf) >= R.CAB:
            Kc = list(self.K)
            m, L = struct.unpack(">HH", R.decifrar(self.buf, Kc, 0, 4))
            if m != R.MAGIC or L < R.CAB:                       # perdeu a sincronia (pacote perdido): recomeca a busca da chave
                self.K, self.tentativa = None, 0
                break
            if L > len(self.buf):
                break
            p = R.decifrar(self.buf, self.K, 0, L)
            del self.buf[:L]
            if R.checksum_ok(p):
                _m, _l, _ck, cod, cid, e1, e2 = struct.unpack(">HHHhiii", p[:R.CAB])
                saida.append((cod, cid, e1, e2, p[R.CAB:]))
        return saida


# ------------------------------------------------------------------------------------------------ estado da partida
class Estado:
    """O que o bot precisa saber, sempre atualizado pelos pacotes."""
    def __init__(self):
        self.lock = threading.Lock()
        self.eu = None              # id do nosso boneco na partida (descoberto quando o cliente age na vez dele)
        self.vez = None             # id de quem esta jogando agora
        self.vez_t = 0.0
        self.turno = None
        self.vento = None
        self.vivos = {}             # id -> dict(x, y, vida, vivo, energia_max, furia, tiros, voos)
        self.ultimo_tiro = None     # resultado do ultimo tiro (servidor)
        self.meu_ultimo_tiro = None  # o que NOS enviamos (x, y, forca, angulo)
        self.pacotes = {"servidor": 0, "cliente": 0}
        self.chave_ok = {"servidor": False, "cliente": False}
        self.eventos = 0

    def copia(self):
        with self.lock:
            return dict(eu=self.eu, vez=self.vez, vez_t=self.vez_t, turno=self.turno, vento=self.vento,
                        vivos={k: dict(v) for k, v in self.vivos.items()}, ultimo_tiro=self.ultimo_tiro,
                        meu_ultimo_tiro=self.meu_ultimo_tiro, minha_vez=self.vez is not None and self.vez == self.eu,
                        pacotes=dict(self.pacotes), chave_ok=dict(self.chave_ok))

    def processar(self, lado, pacote, ao_mudar=None):
        cod, _cid, e1, _e2, corpo = pacote
        self.pacotes[lado] += 1
        if cod != R.GAME_CMD or not corpo:
            return
        sub = corpo[0]
        evento = None
        try:
            with self.lock:
                if lado == "servidor" and sub in (R.SUB["GAME_CREATE"], R.SUB["GAME_OVER"]):
                    self.vez = self.turno = self.vento = None             # partida nova: os ids dos bonecos podem mudar
                    if sub == R.SUB["GAME_CREATE"]:
                        self.eu = None
                    self.vivos = {}
                    evento = ("partida", sub)
                elif lado == "servidor" and sub == R.SUB["TURN"]:
                    v = R.vez_do_servidor(corpo, e1)
                    self.vez, self.vez_t, self.turno, self.vento = v["quem"], time.time(), v["turno"], v["vento"]
                    self.vivos = {d["id"]: d for d in v["vivos"]}
                    evento = ("vez", v)
                elif lado == "servidor" and sub == R.SUB["FIRE"]:
                    t = R.tiro_do_servidor(corpo, e1)
                    self.ultimo_tiro = t
                    evento = ("tiro", t)
                elif lado == "cliente":
                    if sub == R.SUB["FIRE"]:
                        t = R.tiro_do_cliente(corpo)
                        self.meu_ultimo_tiro = t
                        if self.vivos:                              # o boneco mais perto do ponto de saida somos nos
                            self.eu = min(self.vivos.values(), key=lambda d: (d["x"] - t["x"]) ** 2 + (d["y"] - t["y"]) ** 2)["id"]
                        evento = ("meu_tiro", t)
                    elif self.vez is not None and self.eu is None and sub in (R.SUB["MOVESTART"], R.SUB["DIRECTION"], 96):
                        self.eu = self.vez                          # o cliente so manda isso na NOSSA vez
                self.eventos += 1
        except (struct.error, IndexError):
            return
        if evento and ao_mudar:
            ao_mudar(evento, self)


# ------------------------------------------------------------------------------------------------ fontes de pacotes
def _tcp_de_ip(dados):
    """(sport, dport, seq, payload) de um pacote IPv4/IPv6 (ou TCP puro); None se nao for TCP."""
    if not dados:
        return None
    v = dados[0] >> 4
    if v == 4:
        ihl = (dados[0] & 0x0F) * 4
        if len(dados) < ihl + 20 or dados[9] != 6:
            return None
        tot = struct.unpack("!H", dados[2:4])[0] or len(dados)
        tcp, fim = ihl, min(tot, len(dados))
    elif v == 6 and len(dados) >= 60 and dados[6] == 6:
        tcp, fim = 40, min(40 + struct.unpack("!H", dados[4:6])[0], len(dados))
    else:
        tcp, fim = 0, len(dados)                                # alguns sockets IPv6 entregam sem o cabecalho IP
    if fim - tcp < 20:
        return None
    sport, dport, seq = struct.unpack("!HHI", dados[tcp:tcp + 8])
    doff = (dados[tcp + 12] >> 4) * 4
    if doff < 20 or tcp + doff > fim:
        return None
    return sport, dport, seq, dados[tcp + doff:fim]


def endereco_local_do_jogo(porta=R.PORTA_JOGO):
    """Endereco local (IPv4 ou IPv6) da conexao TCP com a porta do jogo, pelo netstat. None se o jogo nao estiver conectado."""
    try:
        out = subprocess.run(["netstat", "-ano", "-p", "TCP"], capture_output=True, text=True, timeout=10).stdout
        out += subprocess.run(["netstat", "-ano", "-p", "TCPv6"], capture_output=True, text=True, timeout=10).stdout
    except (OSError, subprocess.SubprocessError):
        return None
    for linha in out.splitlines():
        partes = linha.split()
        if len(partes) >= 4 and partes[0].upper() == "TCP" and partes[2].endswith(f":{porta}"):
            local = partes[1].rsplit(":", 1)[0].strip("[]")
            return re.sub(r"%\d+$", "", local)
    return None


def eh_admin():
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except (AttributeError, OSError):
        return False


def _abrir_socket_bruto(local):
    """Socket bruto com SIO_RCVALL no endereco local. Tenta as combinacoes que o Windows aceita (IPv6 varia entre versoes)."""
    erros = []
    if ":" in local:
        tentativas = [(socket.AF_INET6, p, (local, 0, 0, 0)) for p in (socket.IPPROTO_IPV6, socket.IPPROTO_IP, socket.IPPROTO_TCP)]
    else:
        tentativas = [(socket.AF_INET, p, (local, 0)) for p in (socket.IPPROTO_IP, socket.IPPROTO_TCP)]
    for fam, proto, end in tentativas:
        s = None
        try:
            s = socket.socket(fam, socket.SOCK_RAW, proto)
            s.bind(end)
            if fam == socket.AF_INET and proto == socket.IPPROTO_IP:
                s.setsockopt(socket.IPPROTO_IP, socket.IP_HDRINCL, 1)
            s.ioctl(socket.SIO_RCVALL, socket.RCVALL_ON)
            return s, f"{'IPv6' if fam == socket.AF_INET6 else 'IPv4'} protocolo {proto}"
        except OSError as e:
            erros.append(f"{fam}/{proto}: {e}")
            if s:
                s.close()
    raise RuntimeError("nao consegui abrir o socket bruto: " + " | ".join(erros))


def fonte_socket_bruto(parar, porta=R.PORTA_JOGO, log=print):
    """Gera (lado, seq, payload) lidos com socket bruto do Windows. Precisa de administrador e do jogo conectado."""
    local = endereco_local_do_jogo(porta)
    if local is None:
        raise RuntimeError("o jogo nao esta conectado (nenhuma conexao com a porta %d)" % porta)
    s, como = _abrir_socket_bruto(local)
    log(f"[rede] lendo pela conexao local {local} ({como})")
    s.settimeout(0.5)
    try:
        while not parar.is_set():
            try:
                dados = s.recv(65535)
            except socket.timeout:
                continue
            seg = _tcp_de_ip(dados)
            if seg and porta in (seg[0], seg[1]):
                yield ("servidor" if seg[0] == porta else "cliente"), seg[2], seg[3]
    finally:
        try:
            s.ioctl(socket.SIO_RCVALL, socket.RCVALL_OFF)
        except OSError:
            pass
        s.close()


def fonte_replay(caminho, parar, porta=R.PORTA_JOGO):
    """Mesma saida da fonte ao vivo, lendo um .pcapng (teste sem administrador)."""
    for _t, _src, _dst, sp, dp, seq, _fl, pl in R.ler_pcapng(caminho):
        if parar.is_set():
            return
        if porta in (sp, dp):
            yield ("servidor" if sp == porta else "cliente"), seq, pl


# ------------------------------------------------------------------------------------------------ registro de rede do Chromium
def _linhas_crescendo(caminho, parar, espera=0.2):
    """Linhas completas de um arquivo que ainda esta sendo escrito (como o tail -f)."""
    while not os.path.exists(caminho):
        if parar.is_set():
            return
        time.sleep(espera)
    with open(caminho, "rb") as f:
        resto = b""
        while not parar.is_set():
            bloco = f.read(1 << 20)
            if not bloco:
                time.sleep(espera)
                continue
            resto += bloco
            *linhas, resto = resto.split(b"\n")
            for ln in linhas:
                yield ln.decode("utf-8", "replace")


def fonte_netlog(caminho, parar, porta=R.PORTA_JOGO, seguir=True):
    """Gera (lado, None, bytes) da conexao do jogo a partir do registro de rede do Chromium (NetLog JSON em streaming).
    seguir=False: le so o que ja esta no arquivo (testes / analise depois)."""
    if seguir:
        linhas = _linhas_crescendo(caminho, parar)
    else:
        linhas = iter(open(caminho, encoding="utf-8", errors="replace").read().splitlines())
    cabeca, tipos, atual = [], None, None
    alvo = f":{porta}"
    for ln in linhas:
        if parar.is_set():
            return
        if tipos is None:                                       # cabecalho: {"constants": {...}, "events": [
            cabeca.append(ln)
            texto = "\n".join(cabeca)
            i = texto.find('"events"')
            if i < 0:
                continue
            const = json.loads(texto[:texto.rfind(",", 0, i)] + "}")["constants"]
            ev = const.get("logEventTypes", {})
            tipos = {ev.get("SOCKET_BYTES_RECEIVED"): "servidor", ev.get("SOCKET_BYTES_SENT"): "cliente"}
            continue
        ln = ln.strip().rstrip(",")
        if not ln.startswith("{"):
            continue
        try:
            e = json.loads(ln)
        except ValueError:
            continue
        params, fonte = e.get("params") or {}, (e.get("source") or {}).get("id")
        lado = tipos.get(e.get("type"))
        if lado and fonte == atual:
            if params.get("bytes"):                             # Chromium 76: base64 no campo "bytes"
                yield lado, None, base64.b64decode(params["bytes"])
            elif params.get("hex_encoded_bytes"):               # versoes mais novas: hexadecimal
                yield lado, None, bytes.fromhex(params["hex_encoded_bytes"])
        elif fonte != atual and params:
            for k in ("address", "address_list", "remote_address", "host_and_port"):
                v = params.get(k)
                if v and alvo in (v if isinstance(v, str) else " ".join(map(str, v))):
                    atual = fonte                               # conexao nova com o jogo (login/reconexao): recomeca a leitura
                    yield "reset", None, b""
                    break


def achar_jogo():
    """Caminho do BetelTank.exe: o processo aberto, o registro do Windows (desinstalador) ou os lugares comuns."""
    try:
        out = subprocess.run(["powershell", "-NoProfile", "-Command",
                              "(Get-Process BetelTank -ErrorAction SilentlyContinue | Select-Object -First 1).Path"],
                             capture_output=True, text=True, timeout=15).stdout.strip()
        if out and os.path.exists(out):
            return out
    except (OSError, subprocess.SubprocessError):
        pass
    try:
        import winreg
        for raiz in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
            for base in (r"Software\Microsoft\Windows\CurrentVersion\Uninstall",
                         r"Software\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall"):
                try:
                    k = winreg.OpenKey(raiz, base)
                except OSError:
                    continue
                for i in range(winreg.QueryInfoKey(k)[0]):
                    try:
                        sk = winreg.OpenKey(k, winreg.EnumKey(k, i))
                        if "betel" in winreg.QueryValueEx(sk, "DisplayName")[0].lower():
                            exe = os.path.join(winreg.QueryValueEx(sk, "InstallLocation")[0], "BetelTank.exe")
                            if os.path.exists(exe):
                                return exe
                    except OSError:
                        continue
    except ImportError:
        pass
    return next((c for c in CAMINHOS_JOGO if os.path.exists(c)), None)


def jogo_aberto():
    try:
        out = subprocess.run(["tasklist", "/FI", "IMAGENAME eq BetelTank.exe", "/NH"], capture_output=True, text=True, timeout=10).stdout
        return "BetelTank.exe" in out
    except (OSError, subprocess.SubprocessError):
        return False


def abrir_jogo_com_log(exe=None, manter=2):
    """Abre o jogo com o registro de rede ligado. Apaga os registros antigos (guarda os `manter`-1 mais novos). Devolve o caminho do novo."""
    exe = exe or achar_jogo()
    if not exe:
        raise RuntimeError("nao achei o BetelTank.exe (passe o caminho com --jogo)")
    os.makedirs(PASTA_LOGS, exist_ok=True)
    antigos = sorted(glob.glob(os.path.join(PASTA_LOGS, "netlog_*.json")))
    for velho in antigos[:max(0, len(antigos) - manter + 1)]:
        try:
            os.remove(velho)
        except OSError:
            pass
    caminho = os.path.join(PASTA_LOGS, f"netlog_{datetime.datetime.now():%Y%m%d_%H%M%S}.json")
    subprocess.Popen([exe, f"--log-net-log={caminho}", "--net-log-capture-mode=IncludeSocketBytes"], cwd=os.path.dirname(exe))
    return caminho


# ------------------------------------------------------------------------------------------------ leitor
class LeitorAoVivo:
    def __init__(self, fonte=None, ao_mudar=None, log=print):
        self.estado = Estado()
        self.fonte = fonte or fonte_socket_bruto
        self.ao_mudar, self.log = ao_mudar, log
        self.parar = threading.Event()
        self.thread = None
        self.erro = None
        self.segmentos = 0
        self.tcp = {"servidor": MontadorTCP(), "cliente": MontadorTCP()}
        self.dec = {lado: Decifrador(MIN_BYTES_CHAVE[lado]) for lado in ("servidor", "cliente")}

    def consumir(self, gerador):
        for lado, seq, pl in gerador:
            if lado == "reset":                                 # conexao nova (login de novo): chave e fluxo novos
                self.tcp = {"servidor": MontadorTCP(), "cliente": MontadorTCP()}
                self.dec = {lado: Decifrador(MIN_BYTES_CHAVE[lado]) for lado in ("servidor", "cliente")}
                self.estado.chave_ok = {"servidor": False, "cliente": False}
                continue
            self.segmentos += 1
            dados = pl if seq is None else self.tcp[lado].segmento(seq, pl)
            if not dados:
                continue
            for pac in self.dec[lado].alimentar(dados):
                self.estado.chave_ok[lado] = True
                self.estado.processar(lado, pac, self.ao_mudar)

    def _rodar(self):
        try:
            self.consumir(self.fonte(self.parar))
        except Exception as e:                                  # o bot continua pela tela se a rede falhar
            self.erro = e
            self.log(f"[rede] leitura ao vivo parou: {e}")

    def iniciar(self):
        self.thread = threading.Thread(target=self._rodar, daemon=True)
        self.thread.start()
        return self

    def encerrar(self):
        self.parar.set()


def _imprimir(evento, est):
    tipo, d = evento
    if tipo == "vez":
        quem = "EU" if d["quem"] == est.eu else str(d["quem"])
        pos = "  ".join(f"{v['id']}:({v['x']},{v['y']}){'' if v['vivo'] else ' morto'}" for v in d["vivos"])
        print(f"[vez {d['turno']}] joga: {quem}  vento {d['vento']:+.1f}  | {pos}")
    elif tipo == "tiro":
        for b in d["bombas"]:
            bomba = next((a for a in b["acoes"] if a["tipo"] == "BOMB"), None)
            tele = " (teleguiado)" if any(a["tipo"] == "CHANGE_SPEED" for a in b["acoes"]) else ""
            print(f"   [tiro de {d['atirador']}] saida ({b['x']},{b['y']}) v=({b['vx']},{b['vy']})"
                  f"{' explodiu em (%d,%d)' % bomba['p'][:2] if bomba else ''}{tele}")
        for a in d["alvos"]:
            print(f"   [acertou] boneco {a['vivo']}: dano {a['dano']}, vida agora {a['vida']}")
    elif tipo == "partida":
        print("=== partida nova ===" if d == R.SUB["GAME_CREATE"] else "=== fim da partida ===")
    elif tipo == "meu_tiro":
        print(f"   [meu tiro] saida ({d['x']},{d['y']}) forca {d['forca']} ({d['forca'] / 20:.0f}%) angulo {d['angulo']}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Le ao vivo a rede do DDTank (so leitura)")
    ap.add_argument("--abrir-jogo", action="store_true", help="abre o jogo com o registro de rede ligado e le ao vivo")
    ap.add_argument("--jogo", default=None, help="caminho do BetelTank.exe (se nao achar sozinho)")
    ap.add_argument("--netlog", help="ler um registro de rede (.json do jogo aberto com --abrir-jogo)")
    ap.add_argument("--analisar", action="store_true", help="com --netlog: le o arquivo inteiro de uma vez (depois da partida) e sai")
    ap.add_argument("--replay", help="ler um .pcapng (CAPTURAR_REDE.bat)")
    ap.add_argument("--socket-bruto", action="store_true", help="metodo antigo (administrador; nao ve conexao IPv6)")
    ap.add_argument("--segundos", type=float, default=0, help="parar sozinho depois disso (0 = ate fechar)")
    a = ap.parse_args()
    if a.replay or (a.netlog and a.analisar):
        if a.replay:
            fonte = lambda parar: fonte_replay(a.replay, parar)
        else:
            fonte = lambda parar: fonte_netlog(a.netlog, parar, seguir=False)
        leitor = LeitorAoVivo(fonte=fonte, ao_mudar=_imprimir)
        leitor.consumir(leitor.fonte(leitor.parar))
    else:
        if a.socket_bruto:
            if not eh_admin():
                raise SystemExit("O socket bruto precisa de administrador.")
            fonte = fonte_socket_bruto
        else:
            caminho = a.netlog
            if a.abrir_jogo:
                while jogo_aberto():
                    input("O jogo ja esta aberto. FECHE o jogo e aperte Enter (ele precisa abrir com o registro ligado)... ")
                caminho = abrir_jogo_com_log(a.jogo)
                print(f"Jogo aberto com o registro de rede: {caminho}")
            if not caminho:
                raise SystemExit("Use --abrir-jogo (ou --netlog arquivo).")
            fonte = lambda parar: fonte_netlog(caminho, parar)
        print("Lendo a rede do jogo ao vivo (so leitura). Entre numa partida; Ctrl+C para sair.")
        leitor = LeitorAoVivo(fonte=fonte, ao_mudar=_imprimir).iniciar()
        t0 = time.time()
        try:
            while not a.segundos or time.time() - t0 < a.segundos:
                time.sleep(5)
                e = leitor.estado.copia()
                if leitor.erro:
                    break
                if not e["chave_ok"]["servidor"]:
                    print(f"  ... ainda sem a chave: {leitor.segmentos} pedacos de dados do jogo lidos ate agora"
                          f"{' (NENHUM ainda: faca login e entre numa sala/partida)' if leitor.segmentos == 0 else ''}")
        except KeyboardInterrupt:
            pass
        leitor.encerrar()
    e = leitor.estado.copia()
    print(f"\nresumo: pacotes servidor={e['pacotes']['servidor']} cliente={e['pacotes']['cliente']}  chave={e['chave_ok']}  eu={e['eu']}")
