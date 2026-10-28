# -*- coding: utf-8 -*-
"""
Acesso a janela do jogo (Windows): achar, capturar e mandar cliques/teclas direto para
ela, sem mover o mouse nem roubar o foco. Mesma tecnica do bot do Social Empires.
"""
import ctypes
import ctypes.wintypes as W
import time

import numpy as np

user32 = ctypes.windll.user32
gdi32 = ctypes.windll.gdi32
kernel32 = ctypes.windll.kernel32
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)
except Exception:
    user32.SetProcessDPIAware()

WM_MOUSEMOVE, WM_LBUTTONDOWN, WM_LBUTTONUP = 0x0200, 0x0201, 0x0202
WM_KEYDOWN, WM_KEYUP = 0x0100, 0x0101
MK_LBUTTON = 0x0001
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
EnumProc = ctypes.WINFUNCTYPE(W.BOOL, W.HWND, W.LPARAM)

# nomes de teclas aceitos em tecla()/segurar_tecla() -> codigo virtual
TECLAS = {
    "espaco": 0x20, "enter": 0x0D, "esc": 0x1B, "tab": 0x09,
    "esquerda": 0x25, "cima": 0x26, "direita": 0x27, "baixo": 0x28,
    **{str(i): 0x30 + i for i in range(10)},
    **{chr(c): c for c in range(ord("A"), ord("Z") + 1)},
}


class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [("biSize", W.DWORD), ("biWidth", W.LONG), ("biHeight", W.LONG),
                ("biPlanes", W.WORD), ("biBitCount", W.WORD), ("biCompression", W.DWORD),
                ("biSizeImage", W.DWORD), ("biXPelsPerMeter", W.LONG),
                ("biYPelsPerMeter", W.LONG), ("biClrUsed", W.DWORD), ("biClrImportant", W.DWORD)]


def _exe_do_processo(pid):
    h = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if not h:
        return ""
    try:
        buf = ctypes.create_unicode_buffer(520)
        tam = W.DWORD(520)
        if kernel32.QueryFullProcessImageNameW(h, 0, buf, ctypes.byref(tam)):
            return buf.value.rsplit("\\", 1)[-1]
        return ""
    finally:
        kernel32.CloseHandle(h)


def listar_janelas():
    """Todas as janelas visiveis com titulo: lista de dicts (hwnd, titulo, exe, w, h)."""
    achadas = []

    def cb(h, _):
        if not user32.IsWindowVisible(h):
            return True
        buf = ctypes.create_unicode_buffer(256)
        user32.GetWindowTextW(h, buf, 256)
        if not buf.value.strip():
            return True
        pid = W.DWORD()
        user32.GetWindowThreadProcessId(h, ctypes.byref(pid))
        r = W.RECT()
        user32.GetClientRect(h, ctypes.byref(r))
        achadas.append({"hwnd": h, "titulo": buf.value, "exe": _exe_do_processo(pid.value),
                        "w": r.right, "h": r.bottom})
        return True

    user32.EnumWindows(EnumProc(cb), 0)
    return achadas


def achar_janela(titulo="", exe=""):
    """A maior janela cujo titulo contem `titulo` e/ou cujo .exe e `exe` (ignora maiusculas)."""
    candidatas = []
    for j in listar_janelas():
        if titulo and titulo.lower() not in j["titulo"].lower():
            continue
        if exe and exe.lower() != j["exe"].lower():
            continue
        candidatas.append((j["w"] * j["h"], j["hwnd"]))
    return max(candidatas)[1] if candidatas else None


def tamanho(hwnd):
    r = W.RECT()
    user32.GetClientRect(hwnd, ctypes.byref(r))
    return r.right, r.bottom


def capturar(hwnd, modo="print"):
    """Imagem BGR da area cliente da janela, ou None.

    modo 'print': PrintWindow (funciona com a janela coberta por outras).
    modo 'tela' : copia da tela (BitBlt) - so serve com a janela visivel, mas pega
                  casos em que o PrintWindow devolve preto."""
    w, h = tamanho(hwnd)
    if w < 100 or h < 100:
        return None
    hdc = user32.GetDC(hwnd)
    mdc = gdi32.CreateCompatibleDC(hdc)
    bmp = gdi32.CreateCompatibleBitmap(hdc, w, h)
    old = gdi32.SelectObject(mdc, bmp)
    try:
        if modo == "print":
            user32.PrintWindow(hwnd, mdc, 2)  # PW_RENDERFULLCONTENT
        else:
            gdi32.BitBlt(mdc, 0, 0, w, h, hdc, 0, 0, 0x00CC0020)  # SRCCOPY
        bi = BITMAPINFOHEADER(ctypes.sizeof(BITMAPINFOHEADER), w, -h, 1, 32, 0, 0, 0, 0, 0, 0)
        buf = ctypes.create_string_buffer(w * h * 4)
        gdi32.GetDIBits(mdc, bmp, 0, h, buf, ctypes.byref(bi), 0)
        return np.frombuffer(buf, np.uint8).reshape(h, w, 4)[:, :, :3].copy()
    finally:
        gdi32.SelectObject(mdc, old)
        gdi32.DeleteObject(bmp)
        gdi32.DeleteDC(mdc)
        user32.ReleaseDC(hwnd, hdc)


def _lp(x, y):
    return ((int(y) & 0xFFFF) << 16) | (int(x) & 0xFFFF)


def mover(hwnd, x, y):
    user32.PostMessageW(hwnd, WM_MOUSEMOVE, 0, _lp(x, y))


def clicar(hwnd, x, y):
    mover(hwnd, x, y)
    time.sleep(0.06)
    user32.PostMessageW(hwnd, WM_LBUTTONDOWN, MK_LBUTTON, _lp(x, y))
    time.sleep(0.05)
    user32.PostMessageW(hwnd, WM_LBUTTONUP, 0, _lp(x, y))


def arrastar(hwnd, x0, y0, x1, y1, passo_px=5):
    mover(hwnd, x0, y0)
    time.sleep(0.15)
    user32.PostMessageW(hwnd, WM_LBUTTONDOWN, MK_LBUTTON, _lp(x0, y0))
    time.sleep(0.15)
    n = max(2, int(np.hypot(x1 - x0, y1 - y0) / passo_px))
    for i in range(1, n + 1):
        user32.PostMessageW(hwnd, WM_MOUSEMOVE, MK_LBUTTON,
                            _lp(x0 + (x1 - x0) * i / n, y0 + (y1 - y0) * i / n))
        time.sleep(0.03)
    user32.PostMessageW(hwnd, WM_LBUTTONUP, 0, _lp(x1, y1))


def _vk(tecla):
    if isinstance(tecla, int):
        return tecla
    return TECLAS[tecla.lower() if len(tecla) > 1 else tecla.upper()]


def _lparam_tecla(vk, subindo=False, repeticao=1):
    scan = user32.MapVirtualKeyW(vk, 0)
    lp = (scan << 16) | repeticao
    if subindo:
        lp |= (1 << 30) | (1 << 31)
    return lp


def tecla(hwnd, nome, duracao=0.05):
    """Aperta e solta uma tecla (ou segura por `duracao` segundos, ex.: barra de espaco
    para carregar a forca do tiro)."""
    vk = _vk(nome)
    user32.PostMessageW(hwnd, WM_KEYDOWN, vk, _lparam_tecla(vk))
    fim = time.time() + duracao
    while time.time() < fim:   # o Windows repete a tecla enquanto ela esta segura
        time.sleep(min(0.03, max(0.0, fim - time.time())))
        user32.PostMessageW(hwnd, WM_KEYDOWN, vk, _lparam_tecla(vk, repeticao=2) | (1 << 30))
    user32.PostMessageW(hwnd, WM_KEYUP, vk, _lparam_tecla(vk, subindo=True))
