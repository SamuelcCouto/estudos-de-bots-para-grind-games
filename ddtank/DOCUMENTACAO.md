# DDTank Bot - documentacao completa (para continuar em outra sessao)

Atualizado em 29/10/2026. Pasta do projeto: `ddtank/` (repositorio `samuelccouto/estudos-de-bots-para-grind-games`,
branch de trabalho `claude/wonderful-rubin-3oyqi3`; na maquina do usuario: `D:\estudos-de-bots-para-grind-games\ddtank`).
Passagem para a sessao local, pendencias e links dos videos de calculo (PvP): `PASSAGEM_PARA_LOCAL.md` (secao 0 = mais recente).
Historico tecnico detalhado (cada sessao, medicoes, bugs): `NOTAS.md`. Uso rapido: `LEIA-ME.txt`.

## 1. O que e e para que serve
Bot 100% automatico para o DDTank da comunidade **Betel** (`BetelTank.exe`, janela ~1922x1034). Joga sozinho, **sem usar o
mouse/teclado do usuario** (captura por `PrintWindow`, cliques e teclas por `PostMessage`). Automacao e **permitida pela
administracao do servidor** (o usuario confirmou). **Use UM bot por vez** (mutex impede dois).
Objetivo atual: farmar **cupons** (moeda do jogo) com as instancias; as rotas antigas so valem pelos cupons
(os drops ja sao obsoletos para o boneco do usuario). Rota Norte desabilitada no menu (continua funcionando por linha de comando).

O usuario fala **portugues**, quer explicacoes intuitivas, decide o rumo; eu (Claude) implemento, testo e documento.

## 2. Como o usuario usa
`BotDDT.bat` (baixa novidades com `git pull` e abre o painel `painel.py`, tkinter, tema escuro). Cards: **Rotas** (Norte, Sul, Leste =
em desenvolvimento/desabilitada), **Chefes** (repete UM chefe: Fantasma ... Gato Preto, Pericao comum, Chefao Global; tarefas a cada 10
voltas), **Abrir cartas** (Todas / Nenhuma / uma caixinha por chefe), **Opcoes** (coletar tarefas) e, so na versao do desenvolvedor,
**Desenvolvedor** (gravacao, leve, enviar ao parar, religar, horarios) + botoes "Enviar gravacao", "Testar a minha tela", "Atualizar",
"Gravar a MINHA jogada". INICIAR / PAUSAR / PARAR no topo. **Versao dos amigos** (`painel.py --amigo` ou arquivo `amigo.flag` ao lado do
exe): sem gravacao/log/GitHub; so a aba **Relatorio** (tempo, voltas, lutas, missoes, cartas abertas e o que veio nelas -
`estatisticas.py` grava `logs/estatisticas.json`; `drops.py` reconhece o icone de cada carta virada: itens conhecidos em
`templates/drops/<nome>.png`, novos viram `item_NNN` em `dados/drops_vistos/` e podem ser nomeados em `dados/drops_nomes.json`). Tudo vira argumentos de `navegador.py --atirar ...` (nada de perguntas no terminal).
Fluxo de feedback: o usuario roda, o painel envia `envio/<sessao>_parteN.zip` ao GitHub, **eu analiso** (relatorio, log, frames)
e depois `git rm` os zips ja analisados. Teclas do bot: F8 pausa, F10 sai.

## 3. Arquitetura (arquivos de `ddtank/`)
| arquivo | funcao |
|---|---|
| `navegador.py` (~1550 linhas) | **cerebro**: maquina de estados de telas, rotas, cliques, cartas, tarefas, Chefao Global, vigia de "preso", pausa, `IOJanela`, `main()` com todos os argumentos |
| `atirador.py` | joga o turno da batalha: mira (angulo por setas), itens, forca (segura espaco), POW (B), aviao (F, desligado), resultado do tiro |
| `leitura.py` | todas as leituras da tela de batalha (angulo, forca, PASS, minimapa, vida do boss, itens, numeros de dano, POW) |
| `memoria.py` | previsor de (angulo, forca) por instancia: memoria de acertos + fisica com constante R aprendida; sementes em `dados/tiros_semente.json` |
| `combos.py` | escolhe a ordem de itens por instancia (luta mais curta; teste de fogo 2,3,4) |
| `metricas.py` | cronometro, relatorio (`logs/relatorio.txt`, `lutas.csv`, `voltas.csv`), diagnostico por instancia |
| `estrategias.py` | regras por instancia (aviao do Escorpiao desligado, Pericao/Chefao, angulo minimo...) |
| `estados.py` + `templates/estados.json` | detector de telas por recortes (2 por tela) + `PRIORIDADE` |
| `tela.py` | **calibracao de tela** (qualquer tamanho/zoom de janela) - SIFT + recortes; `templates/ref/*.jpg` |
| `janela.py` | Win32: capturar, clicar, teclas, foco, achar a janela (`config.EXE_JANELA`) |
| `registro.py` | grava o que o bot faz (`sessoes/`, eventos + prints) |
| `gravador.py` | grava **a jogada do usuario** (cliques, teclas e por quanto tempo, prints) - usado para mapear coisas novas |
| `empacotar.py` | zips de ate 20 MB em `envio/` (prints selecionados; `--tudo` manda todos) |
| `painel.py` / `painel_logica.py` | janela de controle / montagem da linha de comando (testavel) |
| `botddt.py`, `BUILD_EXE.bat`, `LEIA-ME_AMIGOS.txt` | empacotamento em `BotDDT.exe` (PyInstaller) - ver secao 9 |
| `config.py` | caminhos (`PASTA`, `PASTA_RECURSOS`, modo congelado) e `EXE_JANELA` |
| `testes/` | 8 arquivos `test_*.py` + `frames/` (quadros reais). Rodar todos antes de cada commit |

Dados do usuario (fora do git): `logs/`, `sessoes/` (guarda as 3 ultimas), `dados/aprendizado.json`, `dados/combos.json`,
`dados/modelos_aprendidos/` (artes de instancias novas), `dados/painel.json`.

## 4. Ideias-chave (leia antes de mexer)
- **Tudo normalizado para 1280 px de largura** (`em_1280`); os cliques voltam por `k = largura/1280`. Todos os templates/coordenadas
  do codigo sao nessa referencia. Com a calibracao (`tela.py`), `IOJanela.capturar` devolve o quadro canonico 1280x688 (k=1) e
  converte os cliques; na janela original ha o "modo legado" (nada muda).
- **Deteccao de tela**: cada estado tem 2 recortes cinza + limiar (nota = a pior dos recortes). Estados genericos `SALA` e `CONFIG`
  cobrem instancias de arte desconhecida; o bot **aprende a arte** (`cfg_X.png`/`sala_X.png` em `dados/modelos_aprendidos`).
  Estados extra: `POPUP_SOZINHO` (+`2` = confirmacao "Concordar" do Pericao), `POPUP_AVISO` (aviso "Chefao vai comecar... sim"),
  `POPUP_CARTA`, `CLIQUE_JOGO` (perdeu o foco: clicar em ponto neutro, **nunca no chat**).
- **Minimapa**: mascaras HSV (normal + estrita), remocao de tracos retos, `RastreadorMinimapa` (posicao mais frequente ponderada).
  O boneco/boss sao os pontos azul/vermelho; y para baixo.
- **Fisica**: `forca^2 = R * F(|dx|, dy, angulo)`; R por instancia (posterior em grade) aprendido com acertos/erros; escolhe a forca de
  maior chance. Boss a esquerda: o boneco **vira** (`virar_para`, le o ponteiro dos dois lados) e usa `|dx|`. `VERSAO_LEITURA=2`.
- **Vida do boss**: barra vermelha; 1-3% fica sem vermelho mas **vivo** (retrato colorido); morto = retrato cinza (`boss_morto`).
  Bug antigo: ler 1% como 0 fazia o bot parar de atacar.
- **Itens**: teclas 1-8 (1 e 3 ate 2x/turno, 2 1x). `combos.py`: teste de fogo `2,3,4` (+buffs 4,4,4,4,5,6,7,8); se mata no 1o turno,
  testa combos com menos animacao; escolhe menor tempo medio com margem de duvida (critico existe). Chefao Global: combo fixo.
- **Cartas**: 15 s; sorteia 3 e clica em seguida; a 3a (VIP) abre um popup (`POPUP_CARTA`); se o jogo nao vira, reclica e troca. Instancias
  que nao interessam (`--cartas`/painel) **nao tem as cartas abertas**: o jogo **entrega 2 cartas sozinho** ao fim dos 15 s (confirmado).
- **Tarefas**: painel em acordeao; botao vermelho pulsa (detecta por diferenca de cor); selos "OK!"; rola a sub-lista; coleta tudo no fim da rota.
- **Chefao Global (Pericao)**: horarios 12h-13h e 21h-22h (relogio do PC; `HORARIOS_CHEFE`, `--horarios-chefe`). Opcao C (so ele) ou, nas
  rotas, "nos horarios": termina a instancia, vai ao Pericao (aba "Instancia do evento", `ABAS_CONFIG`), luta ate o servidor derrubar,
  volta a rota de onde parou. A barra de vida e a do SERVIDOR: acerto do tiro = **numeros de dano** no boss (`leitura.numeros_de_dano`);
  mira quase reta (ponteiro 7, forca ~85%, vento nao importa), **POW** (`B`) quando o botao enche. Sem cartas = derrota -> volta a sala e tenta de novo.
  Fora do horario o Pericao e chefe comum (rota P, `PERICAO_COMUM`). **Nunca testado de verdade com o bot** (o usuario manda o log).
- **Robustez**: `[ERRO]` falha inesperada nao derruba (12 em 10 min param); `[ALERTA]` preso 120 s -> Esc + botoes de janelinhas + print;
  PC nao dorme (`SetThreadExecutionState`); painel religa se cair (5x/h); pausa pelo painel (`logs/pausar.flag`) com o tempo pausado
  fora dos cronometros; parar pelo painel (`logs/parar.flag`).
- **Gravacao**: completa por padrao (`--gravacao-leve` opcional). O empacotar seleciona prints (primeiros 15 min, inicio/fim de turno, problemas).

## 5. Estado das rotas e dos numeros (29/10)
- Rota Sul (Escorpiao Rei > Dragao Gelado > Rainha Liris): ~3 min/volta com cartas so da Rainha (~19 voltas/h); Escorpiao 96% e Dragao 88% no
  1o turno **sem o aviao** (F desligado a pedido: `estrategias.ESCORPIAO_REI["aviao"]=False`), Rainha 96-100%. Rainha corre para os dois lados.
- Rota Norte (Fantasma, Profundezas, Minhocao): 100% no 1o turno; desabilitada no menu. T = Norte + Sul.
- Instancias conhecidas na grade da config (aba normal): FANTASMA, PROFUNDEZAS, MINHOCAO, ESCORPIAO_REI, DRAGAO_GELADO, RAINHA_LIRIS, ULTIMA_LUTA,
  GATO_PRETO (`INSTANCIA_NA_CONFIG`; coordenadas ja calibradas). Nenhuma tem dificuldade para escolher. Pericao: aba do evento (500,320).

## 6. Como trabalhar (combinados com o usuario)
- Commit/push **somente** na branch `claude/wonderful-rubin-3oyqi3`. Sem PR a menos que peca. Commits terminam com as linhas
  `Co-Authored-By: ...` e `Claude-Session: ...` (ver o lembrete de atribuicao da sessao).
- **Rodar todos os `testes/test_*.py` antes de commitar** (inclui `test_sintaxe.py`). Um `sed` meu ja quebrou o `empacotar.py` com aspas dentro de aspas.
- Apos analisar um envio: `git rm` dos zips (`envio/*.zip`). O usuario manda zips pelo painel; `git pull --rebase` se o push for recusado.
- Escrever codigo no estilo do entorno (portugues sem acento nos comentarios/logs, nomes em portugues).
- Nao inventar: quando faltar dado (tela nova, instancia nova), pedir a gravacao ao usuario.
- O usuario so quer ser perguntado o necessario; resumir bem, sem jargao.

## 7. Backlog / proximos passos (ordem de prioridade do usuario)
1. **Gato Preto** - IMPLEMENTADO em 29/10 (nunca rodado pelo bot de verdade; falta o usuario testar e mandar o log). Da gravacao
   `20261029_180936` (4 runs, ~15 turnos e rodadas 32-38/200 cada; boss generico que so se cura, barra de vida REAL):
   (a) **perks POW Z/X/C**: na SALA, em "Minhas ferramentas"; acabam apos o uso; repostos clicando 1x por quadro vazio no perk
   "Enfurecer" (+50% da barra do B, 120 vigor) em "Ferramentas a comprar" (`leitura.PERK_COMPRAR` (942,316), `perks_cheios`,
   `navegador.repor_perks`, antes do Inicio); (b) **item E = pet**: so libera na rodada 6 (3o turno); o bot aperta E no inicio de cada turno
   ate o **icone verde** da barra de itens (`leitura.buff_pet`, so visivel na SUA vez) aparecer; o buff (canhao em volta do boneco) dura a
   luta toda e o boneco fica parado; (c) 1 perk por turno (Z, X, C) ate o POW encher; (d) **B so com o buff ativo** (tira 27-34% da vida do boss
   de uma vez) e **depois do B nao se aperta o 2**; (e) `estrategias.GATO_PRETO` (angulo_min 0, combo 2,3,4); sementes de tiro em
   `tiros_semente.json` (17 acertos; 3 posicoes de nascimento: (26,57), (18,53), (5,43.5); boss em (88.8,53.3)); (f) minimapa: o buff poe um
   circulo em volta do boneco e o miolo azul fica com ~3 px -> `leitura._pontos_pequenos` (plano B, so quando nada foi achado); (g) drops:
   **aboboras** (Medalha de abobora / Brilho da Abobora) vem nas CARTAS -> `templates/drops/*.png` + linha "Aboboras" no relatorio;
   (h) diagnostico "LUTA LONGA" em `metricas`. Entrada pela aba normal (GATO_PRETO (765,357)), cartas todas abertas (padrao de chefe unico).
   Duvidas: vento (0-2.8, parece nao mandar), se a forca/angulo das sementes serve para todos os nascimentos (o bot aprende), vigor para os perks.
   **Roteiro do teste do Gato Preto (31/10, local):** jogo no mapa/sala sem janelinhas; `BotDDT.bat` > Chefes > Gato Preto (cartas todas abertas);
   Desenvolvedor: gravacao completa + enviar ao parar; INICIAR e deixar 3-4 voltas (F8 pausa, F10 sai); PARAR > "Enviar gravacao"; usuario aperta
   F9 em: usou o E, B saiu, item 2 bateu no chao, errou, morreu; anotar se o canhao do pet aparece. Conferir na analise: (1) E so 1x (slot E verde,
   `leitura.e_disponivel`); (2) B depois do E; (3) item 2 sem bater no chao (se bater: subir angulo minimo so com o 2 e recalcular a forca com
   `mem.forca_para`); (4) duvida aberta: o canhao do pet nao apareceu nas gravacoes do bot mesmo apos E - confirmar se o E ativa de fato.
2. **Empacotamento facil** (BotDDT.exe sem Python): scaffold pronto, **falta gerar/testar no Windows** (secao 9).
3. **Cupons por minuto**: cada rota/instancia da X cupons; objetivo = descobrir qual rende mais cupons por minuto corrido (rota mais
   rapida repetida pode ganhar da mais cara e lenta). Falta: usuario informar os cupons de cada instancia/rota; o `metricas.py` ja da
   o tempo de volta - acrescentar "cupons/hora" ao relatorio. **Rota Leste**: mapear quando o boneco conseguir faze-la na mao (tem uma ressalva
   que o usuario ainda nao explicou). Instancias especiais depois (mesma formula).
4. Testar o Chefao Global e o Pericao comum quando o usuario mandar logs (Pericao comum nao e prioridade: drops fracos; fica para amigos).
5. Backlog sem prioridade: adaptar a outras maquinas/amigos (a calibracao de tela existe, validada so com janelas sinteticas); forca de
   tiro de outros bonecos; telas que dependem do visual do personagem.

## 8. Como mapear uma instancia nova (ex.: Gato Preto)
1. Painel > "Gravar a MINHA jogada" (ou `GRAVAR_SESSAO.bat`): o gravador observa e salva cliques, teclas (e a duracao: espaco = forca) e prints.
2. Jogue a run inteira **desde a sala**: escolher a instancia, Inicio, a luta toda, as cartas, voltar a sala. Faca 2-3 runs.
3. **F9 = marcador** nos momentos importantes (comecou a luta, usou o item E, boss mudou de fase, errei, morri); F10 termina e empacota.
4. Anote em texto: o que o item E faz e quando usar; padroes do boss (ataca em qual turno, cura, empurra); quanto tempo leva.
5. "Enviar gravacao". Eu extraio: cliques da entrada, posicoes no minimapa, forca/angulo dos tiros (viram sementes em `tiros_semente.json`),
   itens usados, tela de resultado, e crio `estrategias.py`/rota. O bot **aprende sozinho** a arte da instancia na 1a vez.
Ferramentas uteis que usei: extrair eventos de `eventos.jsonl`, `leitura.*` sobre os frames, comparar recortes e criar patches de
`templates/estados`, ver `NOTAS.md` ("Chefao Global - Pericao") como exemplo completo de mapeamento.

## 9. Empacotamento em .exe (para amigos)
Escolha: **PyInstaller `--onedir`** (pasta `BotDDT\` com `BotDDT.exe`; sem instalar Python/pip/git). `botddt.py` e a entrada unica (painel; ou
`--navegador/--gravador/--empacotar` para os processos filhos); `config.py` detecta `sys.frozen` (dados ao lado do .exe, templates/sementes
de `_MEIPASS`). `BUILD_EXE.bat` instala o PyInstaller, gera `dist\BotDDT` e `BotDDT.zip`. Sem git, o painel so empacota (os zips ficam em `envio\`)
e "Atualizar" pede o zip novo. **Nao foi gerado nem testado** (ambiente Linux): rodar `BUILD_EXE.bat` no Windows do usuario e corrigir o que falhar
(imports ocultos do cv2, antivirus/SmartScreen avisando "app nao reconhecido" - normal em exe sem assinatura, ~150-200 MB).
Alternativa se der problema: pacote "Python portatil" (embeddable) + `BotDDT.bat`.

## 10. Armadilhas conhecidas
- Nunca clicar no chat/barra de mensagens (rouba o foco do teclado do jogo).
- Popup "Clique no jogo para continuar" (`CLIQUE_JOGO`): clicar em ponto neutro; o clique tambem vale para o que esta por baixo.
- Hitbox do Escorpiao so no pe; tridente (item 2) espalha 3 balas; item 3 duplica o tiro (mais animacao).
- Escorpiao se cura ~20% no turno dele; "Investida do rei" joga para fora quem esta perto da borda (por isso existiu o aviao F).
- O Pericao pede confirmacao com texto diferente (`POPUP_SOZINHO2`); o aviso do Chefao aparece por cima (`POPUP_AVISO`). Janelinhas novas = bot "preso":
  o vigia avisa; mande o log para eu criar o estado.
- JPEG recomprimido apaga o pontinho azul do minimapa: frames de teste do minimapa em PNG.
- Retrato do personagem muda entre contas: nao usar recortes sobre o retrato como assinatura de tela (a Central ja quebrou por isso).

## 11. Testes
`python testes/test_X.py` (cada um imprime "... OK"): `test_leitura` (quadros reais), `test_memoria`, `test_atirador` (mundo simulado), `test_navegador`
(simulador do jogo com quadros reais: rotas, cartas, tarefas, chefao, preso, erros), `test_metricas`, `test_registro`, `test_tela` (janelas sinteticas),
`test_painel` (comandos + fumaca com tkinter falso: **a janela real nunca foi vista por mim**), `test_sintaxe`. O ambiente de nuvem nao tem tkinter.
