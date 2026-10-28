# DDTank (servidor Betel) - notas do projeto

## Janela
- Launcher com barra de titulo propria e barra de links no topo (Inicio, BUG 13/13, LOJA VIP...).
- O jogo (Flash) fica no centro; as laterais sao decoracao do site, com as tabelas de forca.
- Os prints do usuario incluem a barra de tarefas do Windows: a area cliente real e menor que 1920x1080.

## Fluxo da rota 1 (sem dificuldade selecionavel)
Instancias, em ordem: Fantasma -> Profundezas -> O Minhocao.
Criar sala: Central -> "Jogar" -> escolher a instancia -> "Inicio".
Ao vencer o chefe: tela de vitoria -> tela de cartas ("Fim do jogo", 21 cartas, contagem regressiva,
2 viradas gratis) -> volta.

## Tela de batalha (print do usuario)
Topo: relogio da vez (grande, com PASS), "Forca Vento", vida do inimigo (%), minimapa, rodadas (2/200),
objetivo. Embaixo: mostrador de angulo, barra de forca 0-100, vida (numero), energia, itens/habilidades.
O personagem NASCE EM LUGAR ALEATORIO: nunca usar coordenadas fixas; achar o personagem por imagem.

## Arma
"Exclusiva UltimaLuta (avancado3)", lenda. Angulo permitido 15-85 graus.

## Calculo
Tabelas do servidor (dados/tabelas_forca.json, 20/30/50/65 graus, distancia 1..20) -> balistica.py.
Duvidas: 20 graus d6/d7 (ambas 44) e 65 graus d15 (77). Regua 0-10 embaixo da tela: significado desconhecido.

## Backlog
Dificuldades das instancias; vitalidade/PvP (usuario avisa se der problema).


## Gravacao 20261028_010918 (rota 1 completa, 244 s, janela 1922x1034) - o que aprendemos
Coordenadas = pixels da area cliente 1922x1034 (menus ficam sempre no mesmo lugar; so o spawn em batalha varia).

### Cliques da navegacao (menus)
1. (inicio) tela de cartas antiga com aviso "Clique no jogo para continuar jogando": X no canto sup. dir. (1371,286)
2. Mapa da cidade -> "Central" (1309,646)
3. Central -> "Jogar" (1192,709)
4. Sala vazia "Selecione a Instancia" -> icone central (1046,454)
5. Janela de configuracao -> instancia (Fantasma 765,470 | Profundezas 888,470 | Minhocao ~1010,470) -> "sim" (962,791)
6. Sala pronta -> "Inicio" (1398,720)
7. Pop-up "A instancia apresenta mais desafios... fazer isso sozinho?" -> botao da esquerda (sim) (860,610)
   (nas salas seguintes o usuario tambem clicou nos 3 slots vazios (757,522)(635,513)(775,337) antes do Inicio)
8. BATALHA (abaixo)
9. Tela de cartas ("Fim do jogo", 21 cartas, contagem regressiva): 2 cartas gratis (clicar 2), a 3a pede
   "comprar chance de virar" -> recusar (botao da esquerda do pop-up) e a tela fecha, volta para a sala.
10. De volta a sala "Selecione a Instancia": repete 4-7 com a proxima instancia (Profundezas, depois Minhocao).
11. Apos o Minhocao: painel de Tarefa (quest): "Obter recompensa" (backlog; nao e obrigatorio para a rota)
12. Volta a Central.

### Batalha
- Antes de cada tiro o usuario aperta 2, 3 e 4 (itens/buffs: aparecem x3, +1 e POW 50% ao lado do personagem), depois
  segura ESPACO e solta. Tempos segurados nos 6 tiros: 1.77 s, 0.87 s, 0.57 s (com ajuste de angulo), 1.23 s, 1.22 s.
  Cada instancia (nivel facil) cai em 1-2 tiros.
- Mostrador de angulo embaixo a esquerda (numero grande, ex.: 15). Barra de forca 0-100 ao lado (amarela, enche).
  Setas esquerda/direita andam; cima/baixo mudam o angulo (a confirmar).
- Vento: caixa "Forca Vento" no topo, ao centro, seta + numero (nas lutas gravadas estava ~0).
- Relogio da vez: numero grande (10) com botao PASS. Vida do inimigo em % no topo.
- Texto na barra: "Pressione Espaco com forca total e realize um ataque" (tutorial) - pode atrapalhar a leitura.

### Proxima etapa (fase 2): navegador
Maquina de estados que reconhece a tela por imagem e executa os cliques acima, sem atirar (o usuario atira) ->
depois a fase 3 adiciona o tiro (achar personagem/alvo, distancia -> forca pelas tabelas, espaco pelo tempo).
