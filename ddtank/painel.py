# -*- coding: utf-8 -*-
"""
Painel do bot (janela com botoes, no lugar de digitar no terminal). Abra com PAINEL.bat.
Escolha a rota, as cartas, o Chefao Global nos horarios e clique em INICIAR. O painel so monta e roda o
navegador.py (o mesmo de sempre) e mostra o log ao vivo e o relatorio. Usa tkinter (ja vem com o Python).
"""
import os
import queue
import subprocess
import sys
import threading
import time
import tkinter as tk
from tkinter import messagebox, ttk

import config
import painel_logica as P
import navegador as N

COR = {"fundo": "#14161c", "cartao": "#1e222b", "borda": "#2d3340", "texto": "#e6e8ee", "fraco": "#8b93a7",
       "azul": "#4c8dff", "verde": "#35c27a", "vermelho": "#ef5b5b", "amarelo": "#f0b84a"}
FONTE = ("Segoe UI", 10)
FONTE_B = ("Segoe UI", 10, "bold")
FONTE_T = ("Segoe UI", 15, "bold")
MONO = ("Consolas", 9)
RELATORIO = os.path.join(config.PASTA_LOGS, "relatorio.txt")


class Painel:
    def __init__(self, raiz):
        self.raiz = raiz
        self.cfg = P.carregar()
        self.proc = None
        self.fila = queue.Queue()
        self.inicio = None
        raiz.title("DDTank Bot - Painel")
        raiz.configure(bg=COR["fundo"])
        raiz.geometry("1040x660")
        raiz.minsize(900, 520)
        self.estilo()
        self.v_rota = tk.StringVar(value=self.cfg["rota"])
        self.v_chefe = tk.BooleanVar(value=self.cfg["chefe_nos_horarios"])
        self.v_horarios = tk.StringVar(value=self.cfg["horarios"])
        self.v_gravar = tk.BooleanVar(value=self.cfg["gravar"])
        self.v_leve = tk.BooleanVar(value=self.cfg["gravacao_leve"])
        self.v_enviar = tk.BooleanVar(value=self.cfg["enviar_ao_parar"])
        self.v_tarefas = tk.BooleanVar(value=self.cfg["tarefas"])
        self.v_avancado = tk.BooleanVar(value=self.cfg["avancado"])
        self.v_cartas = {}
        self.montar()
        self.atualizar_rota()
        self.raiz.protocol("WM_DELETE_WINDOW", self.fechar)
        self.raiz.after(100, self.tic)

    # ------------------------------------------------------------ visual
    def estilo(self):
        s = ttk.Style()
        try:
            s.theme_use("clam")
        except tk.TclError:
            pass
        s.configure(".", background=COR["fundo"], foreground=COR["texto"], font=FONTE)
        s.configure("TFrame", background=COR["fundo"])
        s.configure("Cartao.TFrame", background=COR["cartao"])
        s.configure("TLabel", background=COR["fundo"], foreground=COR["texto"])
        s.configure("Cartao.TLabel", background=COR["cartao"])
        s.configure("Fraco.TLabel", background=COR["cartao"], foreground=COR["fraco"])
        s.configure("Titulo.TLabel", font=FONTE_T)
        s.configure("TRadiobutton", background=COR["cartao"], foreground=COR["texto"], focuscolor=COR["cartao"])
        s.configure("TCheckbutton", background=COR["cartao"], foreground=COR["texto"], focuscolor=COR["cartao"])
        s.map("TRadiobutton", background=[("active", COR["cartao"])])
        s.map("TCheckbutton", background=[("active", COR["cartao"])])
        s.configure("TEntry", fieldbackground=COR["fundo"], foreground=COR["texto"], insertcolor=COR["texto"])
        s.configure("Iniciar.TButton", background=COR["verde"], foreground="#0b1a12", font=FONTE_B, padding=10, borderwidth=0)
        s.map("Iniciar.TButton", background=[("active", "#46d98c"), ("disabled", COR["borda"])])
        s.configure("Parar.TButton", background=COR["vermelho"], foreground="#220a0a", font=FONTE_B, padding=10, borderwidth=0)
        s.map("Parar.TButton", background=[("active", "#ff7373"), ("disabled", COR["borda"])])
        s.configure("Pausar.TButton", background=COR["amarelo"], foreground="#221a06", font=FONTE_B, padding=10, borderwidth=0)
        s.map("Pausar.TButton", background=[("active", "#ffd070"), ("disabled", COR["borda"])])
        s.configure("TButton", background=COR["borda"], foreground=COR["texto"], padding=8, borderwidth=0)
        s.map("TButton", background=[("active", "#3a4252")])
        s.configure("TNotebook", background=COR["fundo"], borderwidth=0)
        s.configure("TNotebook.Tab", background=COR["cartao"], foreground=COR["fraco"], padding=(14, 6))
        s.map("TNotebook.Tab", background=[("selected", COR["borda"])], foreground=[("selected", COR["texto"])])

    def cartao(self, pai, titulo):
        quadro = ttk.Frame(pai, style="Cartao.TFrame", padding=10)
        ttk.Label(quadro, text=titulo, style="Cartao.TLabel", font=FONTE_B).pack(anchor="w", pady=(0, 8))
        return quadro

    def montar(self):
        topo = ttk.Frame(self.raiz, padding=(18, 14, 18, 6))
        topo.pack(fill="x")
        ttk.Label(topo, text="DDTank Bot", style="Titulo.TLabel").pack(side="left")
        self.l_status = ttk.Label(topo, text="Parado", foreground=COR["fraco"], font=FONTE_B)
        self.l_status.pack(side="right", padx=(14, 0))
        # os botoes principais ficam NO TOPO (sempre visiveis, mesmo em tela pequena)
        self.b_parar = ttk.Button(topo, text="PARAR", style="Parar.TButton", command=self.parar, state="disabled")
        self.b_parar.pack(side="right", padx=(8, 0))
        self.b_pausar = ttk.Button(topo, text="PAUSAR", style="Pausar.TButton", command=self.pausar, state="disabled")
        self.b_pausar.pack(side="right", padx=(8, 0))
        self.b_iniciar = ttk.Button(topo, text="INICIAR", style="Iniciar.TButton", command=self.iniciar)
        self.b_iniciar.pack(side="right")
        corpo = ttk.Frame(self.raiz, padding=(18, 4, 18, 14))
        corpo.pack(fill="both", expand=True)
        # coluna da esquerda com rolagem (se a tela for pequena, rola com a roda do mouse)
        caixa = ttk.Frame(corpo)
        caixa.pack(side="left", fill="y", padx=(0, 14))
        tela = tk.Canvas(caixa, bg=COR["fundo"], highlightthickness=0, width=345)
        barra = ttk.Scrollbar(caixa, orient="vertical", command=tela.yview)
        tela.configure(yscrollcommand=barra.set)
        barra.pack(side="right", fill="y")
        tela.pack(side="left", fill="y", expand=True)
        esq = ttk.Frame(tela)
        tela.create_window((0, 0), window=esq, anchor="nw")
        esq.bind("<Configure>", lambda e: tela.configure(scrollregion=tela.bbox("all")))
        tela.bind_all("<MouseWheel>", lambda e: tela.yview_scroll(int(-e.delta / 120), "units"))
        # rota
        self.c_rota = self.cartao(esq, "O que fazer")
        self.c_rota.pack(fill="x", pady=(0, 10))
        self.f_rotas = ttk.Frame(self.c_rota, style="Cartao.TFrame")
        self.f_rotas.pack(fill="x")
        ttk.Checkbutton(self.c_rota, text="mostrar Rota Norte e Norte + Sul", variable=self.v_avancado,
                        command=self.desenhar_rotas).pack(anchor="w", pady=(8, 0))
        # cartas
        self.c_cartas = self.cartao(esq, "Abrir as cartas de")
        self.c_cartas.pack(fill="x", pady=(0, 10))
        self.f_cartas = ttk.Frame(self.c_cartas, style="Cartao.TFrame")
        self.f_cartas.pack(fill="x")
        # chefao
        c = self.cartao(esq, "Chefao Global")
        c.pack(fill="x", pady=(0, 10))
        self.k_chefe = ttk.Checkbutton(c, text="lutar nos horarios (para a rota e volta depois)", variable=self.v_chefe)
        self.k_chefe.pack(anchor="w")
        linha = ttk.Frame(c, style="Cartao.TFrame")
        linha.pack(fill="x", pady=(6, 0))
        ttk.Label(linha, text="Horarios", style="Fraco.TLabel").pack(side="left")
        ttk.Entry(linha, textvariable=self.v_horarios, width=26).pack(side="left", padx=8)
        # opcoes
        c = self.cartao(esq, "Opcoes")
        c.pack(fill="x", pady=(0, 10))
        ttk.Checkbutton(c, text="coletar as tarefas no fim de cada volta", variable=self.v_tarefas).pack(anchor="w")
        ttk.Checkbutton(c, text="gravar a sessao (para me mandar depois)", variable=self.v_gravar).pack(anchor="w")
        ttk.Checkbutton(c, text="gravacao leve (disco pequeno)", variable=self.v_leve).pack(anchor="w")
        ttk.Checkbutton(c, text="enviar a gravacao ao GitHub quando o bot parar", variable=self.v_enviar).pack(anchor="w")
        # ferramentas
        ttk.Button(esq, text="Enviar gravacao para o GitHub", command=self.enviar).pack(fill="x", pady=(0, 6))
        ttk.Button(esq, text="Atualizar o bot (baixar novidades)", command=self.atualizar).pack(fill="x", pady=(0, 6))
        ttk.Button(esq, text="Gravar a MINHA jogada (para mapear algo novo)", command=self.gravar_jogada).pack(fill="x")
        # direita: abas
        dir_ = ttk.Frame(corpo)
        dir_.pack(side="left", fill="both", expand=True)
        nb = ttk.Notebook(dir_)
        nb.pack(fill="both", expand=True)
        self.t_log = self.texto(nb, "Log ao vivo")
        self.t_rel = self.texto(nb, "Relatorio")
        for tag, cor in (("chefe", COR["amarelo"]), ("erro", COR["vermelho"]), ("tempo", COR["azul"]), ("ok", COR["verde"])):
            self.t_log.tag_configure(tag, foreground=cor)
        self.desenhar_rotas()
        self.atualizar_relatorio()

    def texto(self, nb, titulo):
        quadro = ttk.Frame(nb)
        t = tk.Text(quadro, bg=COR["cartao"], fg=COR["texto"], font=MONO, wrap="word", relief="flat", borderwidth=0,
                    insertbackground=COR["texto"], padx=10, pady=8, state="disabled")
        sb = ttk.Scrollbar(quadro, command=t.yview)
        t.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        t.pack(side="left", fill="both", expand=True)
        nb.add(quadro, text=titulo)
        return t

    # ------------------------------------------------------------ escolhas
    def desenhar_rotas(self):
        for w in self.f_rotas.winfo_children():
            w.destroy()
        rotas = P.ROTAS_PAINEL + (P.ROTAS_AVANCADAS if self.v_avancado.get() else [])
        for chave, nome, desc in rotas:
            ttk.Radiobutton(self.f_rotas, text=nome, value=chave, variable=self.v_rota_var(), command=self.atualizar_rota).pack(anchor="w")
            ttk.Label(self.f_rotas, text="     " + desc, style="Fraco.TLabel").pack(anchor="w", pady=(0, 4))

    def v_rota_var(self):
        return self.v_rota

    def atualizar_rota(self):
        chave = self.v_rota.get()
        for w in self.f_cartas.winfo_children():
            w.destroy()
        inst = P.instancias_da_rota(chave)
        self.v_cartas = {}
        if len(inst) < 2:
            ttk.Label(self.f_cartas, text="(esta rota tem uma instancia so: abre as cartas)", style="Fraco.TLabel").pack(anchor="w")
        else:
            padrao = self.cfg["cartas"] if self.cfg.get("rota") == chave else N.cartas_padrao(chave, inst)
            for i in inst:
                v = tk.BooleanVar(value=i in padrao)
                self.v_cartas[i] = v
                ttk.Checkbutton(self.f_cartas, text=i.replace("_", " ").title(), variable=v).pack(anchor="w")
            ttk.Label(self.f_cartas, text="As desmarcadas so completam a missao.", style="Fraco.TLabel").pack(anchor="w", pady=(4, 0))
        self.k_chefe.state(["disabled"] if chave == "C" else ["!disabled"])

    def config_atual(self):
        return {"rota": self.v_rota.get(), "cartas": [i for i, v in self.v_cartas.items() if v.get()],
                "chefe_nos_horarios": self.v_chefe.get(), "horarios": self.v_horarios.get().strip(),
                "gravar": self.v_gravar.get(), "gravacao_leve": self.v_leve.get(), "enviar_ao_parar": self.v_enviar.get(), "tarefas": self.v_tarefas.get(),
                "avancado": self.v_avancado.get()}

    # ------------------------------------------------------------ rodar
    def iniciar(self):
        if self.proc and self.proc.poll() is None:
            return
        cfg = self.config_atual()
        try:
            cmd = P.montar_comando(cfg, sys.executable)
        except ValueError:
            messagebox.showerror("Horarios", "Use o formato 12:00-13:00,21:00-22:00")
            return
        P.salvar(cfg)
        self.cfg = cfg
        self.escrever(self.t_log, "> " + " ".join(cmd[1:]) + "\n", "tempo")
        env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUNBUFFERED="1")
        flags = 0x08000000 if os.name == "nt" else 0          # CREATE_NO_WINDOW
        try:
            self.proc = subprocess.Popen(cmd, cwd=config.PASTA, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                         stdin=subprocess.DEVNULL, env=env, creationflags=flags)
        except OSError as e:
            messagebox.showerror("Nao consegui iniciar", str(e))
            return
        self.inicio = time.time()
        threading.Thread(target=self.ler_saida, args=(self.proc,), daemon=True).start()
        self.b_iniciar.state(["disabled"])
        self.b_parar.state(["!disabled"])
        self.b_pausar.state(["!disabled"])
        self.pausado_desde = None
        self.b_pausar.configure(text="PAUSAR")

    def pausar(self):
        """Pausa/continua o bot sem fecha-lo (arquivo logs/pausar.flag). O tempo parado nao entra nas medidas."""
        if not (self.proc and self.proc.poll() is None):
            return
        try:
            if os.path.exists(N.ARQUIVO_PAUSAR):
                os.remove(N.ARQUIVO_PAUSAR)
                self.pausado_desde = None
                self.b_pausar.configure(text="PAUSAR")
            else:
                os.makedirs(config.PASTA_LOGS, exist_ok=True)
                open(N.ARQUIVO_PAUSAR, "w").close()
                self.pausado_desde = time.time()
                self.b_pausar.configure(text="CONTINUAR")
        except OSError:
            pass

    def ler_saida(self, proc):
        for linha in proc.stdout:
            self.fila.put(linha.decode("utf-8", "replace"))
        self.fila.put(None)

    def parar(self):
        if not (self.proc and self.proc.poll() is None):
            return
        try:
            os.makedirs(config.PASTA_LOGS, exist_ok=True)
            open(N.ARQUIVO_PARAR, "w").close()              # o bot para sozinho (fecha a gravacao e escreve o relatorio)
        except OSError:
            pass
        try:
            os.remove(N.ARQUIVO_PAUSAR)                     # parado de verdade: sai da pausa
        except OSError:
            pass
        self.escrever(self.t_log, "Parando... (ate 20 s)\n", "chefe")
        self.raiz.after(20000, self.matar_se_preciso)

    def matar_se_preciso(self):
        if self.proc and self.proc.poll() is None:
            self.proc.terminate()

    def rodar_passos(self, passos, titulo):
        """Empacota/envia ou atualiza SEM janela preta e sem perguntas: a saida vai para o log do painel."""
        if getattr(self, "ocupado", False):
            return
        self.ocupado = True
        self.escrever(self.t_log, f"--- {titulo} ---\n", "chefe")

        def trabalho():
            for cmd in passos:
                cmd = [sys.executable if c == "python" else c for c in cmd]
                try:
                    r = subprocess.run(cmd, cwd=config.PASTA, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                       stdin=subprocess.DEVNULL, creationflags=0x08000000 if os.name == "nt" else 0)
                    saida = r.stdout.decode("utf-8", "replace").strip()
                except OSError as e:
                    saida, r = f"nao consegui rodar {cmd[0]}: {e}", None
                if saida:
                    self.fila.put(saida[-1500:] + "\n")
                if cmd[:2] == ["git", "commit"] and r is not None and r.returncode == 1:
                    continue                                   # nada novo para commitar: segue
                if r is None or r.returncode != 0:
                    self.fila.put(f"   ! falhou: {' '.join(cmd[:3])} (codigo {getattr(r, 'returncode', '?')})\n")
                    break
            else:
                self.fila.put(f"--- {titulo}: pronto ---\n")
            self.ocupado = False

        threading.Thread(target=trabalho, daemon=True).start()

    def enviar(self):
        self.rodar_passos(P.PASSOS_ENVIO, "empacotando e enviando a gravacao")

    def gravar_jogada(self):
        """Abre o gravador (observa voce jogando; F9 marca, F10 termina e empacota). Nao pode haver o bot rodando."""
        if self.proc and self.proc.poll() is None:
            messagebox.showinfo("Gravar", "Pare o bot antes de gravar a sua jogada.")
            return
        bat = os.path.join(config.PASTA, "GRAVAR_SESSAO.bat")
        if os.name == "nt":
            subprocess.Popen(["cmd", "/c", "start", "", bat], cwd=config.PASTA)
        else:
            messagebox.showinfo("Gravar", "Rode GRAVAR_SESSAO.bat (Windows).")

    def atualizar(self):
        if self.proc and self.proc.poll() is None:
            messagebox.showinfo("Atualizar", "Pare o bot antes de atualizar.")
            return
        self.rodar_passos([P.PASSO_ATUALIZAR], "baixando as novidades (feche e abra o BotDDT.bat para valer)")

    def fechar(self):
        if self.proc and self.proc.poll() is None:
            if not messagebox.askyesno("Bot rodando", "O bot esta rodando. Parar e fechar o painel?"):
                return
            self.proc.terminate()
        self.raiz.destroy()

    # ------------------------------------------------------------ atualizacao da tela
    def escrever(self, t, texto, tag=None):
        t.configure(state="normal")
        t.insert("end", texto, tag) if tag else t.insert("end", texto)
        if int(t.index("end-1c").split(".")[0]) > 4000:
            t.delete("1.0", "1000.0")
        t.configure(state="disabled")
        t.see("end")

    @staticmethod
    def etiqueta(linha):
        if "[CHEFAO]" in linha or "[POW]" in linha:
            return "chefe"
        if "!" in linha[:14] or "   !" in linha or "ERRO" in linha or "Traceback" in linha:
            return "erro"
        if "[TEMPO]" in linha:
            return "tempo"
        if "ACERTOU" in linha or "concluida" in linha:
            return "ok"
        return None

    def atualizar_relatorio(self):
        try:
            texto = open(RELATORIO, encoding="utf-8").read()
        except OSError:
            texto = "(o relatorio aparece depois da 1a luta)"
        self.t_rel.configure(state="normal")
        self.t_rel.delete("1.0", "end")
        self.t_rel.insert("end", texto)
        self.t_rel.configure(state="disabled")

    def tic(self):
        try:
            for _ in range(200):
                linha = self.fila.get_nowait()
                if linha is None:
                    cod = self.proc.poll() if self.proc else None
                    self.escrever(self.t_log, f"--- o bot terminou (codigo {cod}) ---\n", "chefe")
                    self.b_iniciar.state(["!disabled"])
                    self.b_parar.state(["disabled"])
                    self.b_pausar.state(["disabled"])
                    self.b_pausar.configure(text="PAUSAR")
                    self.pausado_desde = None
                    self.inicio = None
                    self.atualizar_relatorio()
                    if self.cfg.get("enviar_ao_parar") and self.cfg.get("gravar", True):
                        self.enviar()
                else:
                    self.escrever(self.t_log, linha, self.etiqueta(linha))
        except queue.Empty:
            pass
        if self.inicio and getattr(self, "pausado_desde", None):
            p = int(time.time() - self.pausado_desde)
            self.l_status.configure(text=f"PAUSADO ha {p // 60}min{p % 60:02d}s", foreground=COR["amarelo"])
        elif self.inicio:
            s = int(time.time() - self.inicio)
            self.l_status.configure(text=f"Rodando ha {s // 3600}h{s % 3600 // 60:02d}min{s % 60:02d}s", foreground=COR["verde"])
            if s % 10 == 0:
                self.atualizar_relatorio()
        else:
            self.l_status.configure(text="Parado", foreground=COR["fraco"])
        self.raiz.after(500, self.tic)


def main():
    os.chdir(config.PASTA)
    raiz = tk.Tk()
    Painel(raiz)
    raiz.mainloop()


if __name__ == "__main__":
    main()
