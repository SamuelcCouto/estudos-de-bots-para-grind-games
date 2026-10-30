import os, sys, cv2
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import atirador as A, combos as C, estrategias as E, memoria as M
import metricas as Met, navegador as N, painel_logica as P

assert N.ROTAS["U"][1] == N.ROTAS["N"][1] + N.ROTAS["S"][1] + N.ROTAS["L"][1]
assert N.ROTAS["T"][1] == N.ROTAS["N"][1] + N.ROTAS["S"][1]
cmd = P.montar_comando(dict(P.PADRAO, alvo="U", cartas=[], tarefas=False))
assert cmd[cmd.index("--rota") + 1] == "U" and "--sem-tarefas" not in cmd
assert cmd[cmd.index("--chefe") + 1] == "s"
cmd_herdado = P.montar_comando(dict(P.PADRAO, alvo="U", cartas=[], chefe_nos_horarios=True))
assert cmd_herdado[cmd_herdado.index("--chefe") + 1] == "s"
cmd_ns = P.montar_comando(dict(P.PADRAO, alvo="T", cartas=[], tarefas=False))
assert cmd_ns[cmd_ns.index("--rota") + 1] == "T" and "--sem-tarefas" not in cmd_ns
assert cmd_ns[cmd_ns.index("--chefe") + 1] == "s"
combos = C.Combos(arq=None)
for inst in N.ROTAS["N"][1] + ["DRAGAO_GELADO", "RAINHA_LIRIS"]:
    assert combos.escolher(inst)[1] == [2, 4, 4]
assert combos.escolher("ESCORPIAO_REI")[1] == [2] + C.BUFFS
assert 2 not in combos.escolher("ULTIMA_LUTA_F2")[1]

norte = cv2.imread(os.path.join(N.config.PASTA, "testes", "frames", "TAREFA_SUPER.jpg"))
assert not N.tarefa_exige_escolha(norte) and N.painel_tarefa_visivel(norte)
leste_popup = cv2.imread(os.path.join(N.config.PASTA, "testes", "frames", "TAREFA_LESTE_ESCOLHA.png"))
popup = N.popup_escolha_recompensa(leste_popup)
assert popup == {"opcao": (588, 321), "confirmar": (642, 404), "fechar": (745, 275)}
assert N.tarefa_leste_selecionada(leste_popup)
assert N.popup_escolha_recompensa(norte) is None and not N.tarefa_leste_selecionada(norte)

class EscolhaIO:
    def __init__(self): self.cliques = []
    def clicar(self, x, y, modo): self.cliques.append((x, y))
io_escolha = EscolhaIO()
nav_escolha = N.Navegador(io_escolha, object(), N.ROTAS["L"][1],
                          dormir=lambda _: None, log=lambda _: None)
nav_escolha.ver = lambda: (leste_popup if len(io_escolha.cliques) < 2 else norte, ["TAREFA"])
assert nav_escolha.escolher_material_leste(leste_popup, popup)
assert io_escolha.cliques == [popup["opcao"], popup["confirmar"]]
io_gato = EscolhaIO()
nav_gato = N.Navegador(io_gato, object(), ["GATO_PRETO"],
                       dormir=lambda _: None, log=lambda _: None)
assert not nav_gato.escolher_material_leste(leste_popup, popup)
assert io_gato.cliques == [popup["fechar"]]
nav_coleta = N.Navegador(EscolhaIO(), object(), N.ROTAS["L"][1],
                         dormir=lambda _: None, log=lambda _: None)
sem_recompensa = cv2.imread(os.path.join(N.config.PASTA, "testes", "frames", "TAREFA_SEM_OK.jpg"))
quadros_coleta = iter([(leste_popup, ["POPUP_SOZINHO"]), (sem_recompensa, ["TAREFA"])])
nav_coleta.ver = lambda: next(quadros_coleta, (sem_recompensa, ["TAREFA"]))
nav_coleta.escolher_material_leste = lambda f, p: True
nav_coleta.clicar_e_verificar = lambda *args, **kw: True
nav_coleta.coletar_tarefas()
assert nav_coleta.ultima_coleta_tarefas == 1
sala = cv2.imread(os.path.join(N.config.PASTA, "testes", "frames", "SALA_FINAL.jpg"))
assert not N.painel_tarefa_visivel(sala)

class Captura:
    def capturar(self): return norte
class SemModelo:
    def detectar(self, _): return []
nav_tarefa = N.Navegador(Captura(), SemModelo(), ["ULTIMA_LUTA"], dormir=lambda _: None, log=lambda _: None)
assert nav_tarefa.ver()[1] == ["TAREFA"]

class IOExtras:
    def __init__(self): self.teclas = []; self.buff = False
    def tecla(self, tecla, _):
        self.teclas.append(tecla)
        if tecla == "e": self.buff = True
class LeitorExtras:
    def __init__(self, io): self.io = io
    def minha_vez(self, _): return True
    def buff_pet(self, _): return self.io.buff
    def pow_cheio(self, _): return True
io_extras = IOExtras()
at_extras = A.Atirador(io_extras, M.Memoria(arq_semente=None, arq_aprendizado=None),
                       lambda: "ULTIMA_LUTA_F2", leitor=LeitorExtras(io_extras),
                       dormir=lambda _: None, log=lambda _: None)
at_extras.ver = lambda: object()
assert at_extras.preparar_extras(E.estrategia("ULTIMA_LUTA_F2"))
assert io_extras.teclas == ["e", "b"]

relogio = [0.0]
met = Met.Metricas("Super Rota de Cupons", agora=lambda: relogio[0], salvar=False, log=lambda _: None)
nav = N.Navegador(object(), object(), N.ROTAS["U"][1], usar_tarefas=False,
                  agora=lambda: relogio[0], dormir=lambda _: None, log=lambda _: None, metricas=met)
assert nav.usar_tarefas
nav.ver = lambda: (None, [])
nav.vigiar = lambda *args: None
cliques = []
nav.clicar_e_verificar = lambda estado, ponto, **kw: cliques.append((estado,ponto)) or True
for idx, rota, premio in ((2,"N",40000),(5,"S",50000),(7,"L",60000)):
    nav.idx = idx
    nav.cartas_vistas = True
    relogio[0] += 120
    nav.agir("SALA_VAZIA")
    assert nav.cupom_pendente == rota and cliques[-1][1] == N.SALA_ICONE_TAREFAS
    nav.tarefas_ok = True
    nav.ultima_coleta_tarefas = 1
    relogio[0] += 10
    nav.agir("SALA_VAZIA")
    assert nav.cupom_pendente is None and met.cupons_rotas[-1]["cupons"] == premio
assert nav.voltas == 1 and sum(r["cupons"] for r in met.cupons_rotas) == 150000
relatorio = met.texto_relatorio()
assert all(x in relatorio for x in ("40,000","50,000","60,000","/10min","/h"))
met_ns = Met.Metricas("Rota Norte e Sul", agora=lambda: relogio[0], salvar=False, log=lambda _: None)
nav_ns = N.Navegador(object(), object(), N.ROTAS["T"][1], usar_tarefas=False,
                     agora=lambda: relogio[0], dormir=lambda _: None, log=lambda _: None, metricas=met_ns)
assert nav_ns.usar_tarefas and nav_ns.super_rota_cupons
nav_ns.ver = lambda: (None, [])
nav_ns.vigiar = lambda *args: None
nav_ns.clicar_e_verificar = lambda *args, **kw: True
for idx, rota in ((2, "N"), (5, "S")):
    nav_ns.idx = idx
    nav_ns.cartas_vistas = True
    relogio[0] += 120
    nav_ns.agir("SALA_VAZIA")
    assert nav_ns.cupom_pendente == rota
    nav_ns.tarefas_ok = True
    nav_ns.ultima_coleta_tarefas = 1
    relogio[0] += 10
    nav_ns.agir("SALA_VAZIA")
assert nav_ns.voltas == 1 and [r["rota"] for r in met_ns.cupons_rotas] == ["N", "S"]
class AtiradorTeste:
    def __init__(self):
        self.pass_visivel = True
        self.lei = self
        self.passos = []
        self.fins = []
    def minha_vez(self, _): return self.pass_visivel
    def passo(self, f): self.passos.append(f)
    def fim_da_batalha(self, **kw): self.fins.append(kw)
relogio_batalha = [100.0]
falso_config = AtiradorTeste()
nav_batalha = N.Navegador(object(), object(), ["FANTASMA"], atirador=falso_config,
                           agora=lambda: relogio_batalha[0], dormir=lambda _: None, log=lambda _: None)
nav_batalha.em_batalha = True
nav_batalha.teclas = lambda: None
nav_batalha.ver = lambda: (object(), ["CONFIG_SEL"])
nav_batalha._ciclo()
assert len(falso_config.passos) == 1 and not falso_config.fins and nav_batalha.em_batalha
falso_config.pass_visivel = False
relogio_batalha[0] += 5
nav_batalha._ciclo()
assert not falso_config.fins and nav_batalha.em_batalha
print("Super rota, cupons, combos e busca da mira OK")
