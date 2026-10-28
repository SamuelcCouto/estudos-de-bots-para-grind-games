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


## Itens e combos (explicacao do usuario, para a fase 3)
- Os itens ficam na coluna da direita da batalha (1..8); ficam CINZA quando a stamina (energia) acaba -> validacao do bot.
- Item 1: 3 tiros, dano bem menor (quase nunca usado). Item 2: "tridente" - 3 tiros (1x por turno).
  Item 3: dispara 2x com % menos de dano. 2+3 = duas rajadas de tres. Item 4: +50% de potencia (potencializador).
  Do 4 em diante: so potencializadores (podem ser usados quantas vezes quiser, se houver stamina).
- Limites por turno: itens 1 e 3 ate 2x; item 2 ate 1x.
- Nao ha combo padrao: 2 3 4, 3 4 4, e com a evolucao 2 3 4 4 4... O bot precisa escolher o combo conforme a stamina.
- Angulo: depende da rota (regua no rosto do personagem); o usuario sobe o angulo ate pegar na hitbox do boss.
- Vento: irrelevante nas instancias (hitboxes enormes) -> backlog. O bot deve identificar a hitbox do boss.
- Tarefas ao fim de cada volta (3 bosses) NAO acumulam: tem que coletar; 3a carta e VIP, abre pop-up de custo pequeno: sempre sim.
- Painel de Tarefas: itens prontos tem selo verde "OK!"; botao "Obter recompensa" vermelho = coletavel, cinza = nada.

## Fase 2 (navegador) - decisoes tecnicas
- Visao: cada tela tem 2 recortes fixos (templates/estados/) extraidos da gravacao e um limiar calibrado;
  imagem normalizada para 1280 de largura. Cliques sao em coordenadas dessa mesma escala (x client/1280).
- Validado so no simulador com quadros da propria gravacao (testes/test_navegador.py): falta provar em jogo
  que o clique PostMessage chega (o bot alterna "janela principal" / "janela interna do Chromium").


## Velocidade da barra de forca (medido pelo TESTE_FORCA em 28/10)
Segurar o espaco 1,0 s deu 19% (nas gravacoes do usuario jogando manualmente dava ~38%/s), igual COM e SEM repeticao
de tecla -> a barra enche na METADE da velocidade quando o bot joga. Hipoteses: jogo sem foco/segundo plano
(Chromium reduz timers/frames), ou PC sobrecarregado. O atirador agora mede a taxa em todo tiro (regressao do trace da
barra), aceita ate ~2,2x o tempo esperado (MAX_SEGURANDO 7 s) e solta olhando a barra, entao funciona em qualquer velocidade.
Pendente: confirmar se o foco muda a taxa (TESTE_FORCA imprime "jogo em primeiro plano").


## Previsor de tiro (memoria.py) - versao com aprendizado de R
Modelo: forca^2 = R * F(dx, dy_up, angulo), F = dx^2 / (2 cos^2(a) (dx tan a - dy)), dx/dy em px do minimapa.
R por instancia e um posterior em grade log (prior R=38, sigma 0.7 em ln); acerto => R em [R_obs/(1+t)^2, R_obs/(1-t)^2]
(t=0.22) com chance de ser atipico; erro => descarta a mesma faixa (peso 0.1). Teste sintetico: instancia nova acerta
em <=4 tiros; geometrias variadas 32/32. LIMITES: assume boss a DIREITA do jogador (dx>0), sem vento, hitbox com
tolerancia ~22% da forca; PvP (alvo que anda, vento, alvo pequeno) precisara de vento + posicao em tempo real + muito mais dados.

## Minimapa (28/10, noite) - a causa da "forca fraca"
Log do usuario no Fantasma: "voce (71,23), boss (90,56)" -> dx=19, dy=-34 -> a fisica pedia 10-21% e errou 4 vezes.
O jogador estava na verdade em ~(32,57) (onde o usuario acerta com 76-81%). Leitor antigo = "maior mancha azul" com
B>170: o ponto do jogador (BGR ~(156,52,18)) quase nao passava, entao qualquer outra coisa azul vencia. Na
Profundezas ele pegava a AGUA (mancha ~16x24 em (11,34)): as 6 sementes da Profundezas estavam com o jogador errado.
Leitor novo (leitura.candidatos_minimapa): HSV - jogador H 107-124, S>170, V>120 (agua H 101-104; chao azul-escuro
do Minhocao V<120); boss H<=6 ou >=172, S>170, V>150. Erosao em cruz 3x3 apaga linhas de ate 2 px (a MOLDURA do minimapa
muda de cor: verde/azul/vermelha) e o nucleo do ponto tem que caber em 7x7; ignora cabecalho (y<14), bordas (x<3.5,
x>101.5, y>69.5). Validado em todos os 580 quadros de batalha das 2 gravacoes.
RastreadorMinimapa: o bot nunca anda -> jogador = ponto que aparece em MAIS leituras (0,4 s entre leituras); so troca se
o antigo sumir 5 leituras seguidas e outro aparecer em >=4 delas (boneco empurrado). A setinha azul acima do boneco as
vezes vira o maior ponto num quadro isolado (ex.: (26,38) na Profundezas) - o rastreador resolve.
Sementes relidas (campo "leitura": 2). Tiros sem "leitura">=2 (gravados pelo bot com o leitor velho, no
dados/aprendizado.json do usuario) sao IGNORADOS pela memoria - eles ensinavam um R errado.
R por instancia com as posicoes certas: Fantasma ~54, Minhocao ~34, Profundezas ~24 (R = escala do minimapa de cada
mapa; Profundezas varia muito: hitbox grande). Decisao da forca: a que tem MAIOR CHANCE DE ACERTO somando as hipoteses
de R (nao a mediana: com duas hipoteses separadas, a mediana cai no meio e erra as duas). Acerto antigo na mesma
situacao e repetido se a fisica der >=60% de chance para aquela forca.

## Boneco virado para a ESQUERDA (descoberto em 28/10; ainda NAO implementado)
Gravacao 20261028_021750, quadros 104-113 (Profundezas): o usuario tocou "esquerda" 0,1 s -> o boneco virou (andou ~0)
e o mostrador mudou: o numero passou de 14 para 48, o ponteiro foi para o lado ESQUERDO (48 graus a partir da
horizontal esquerda) e ficou uma linha vermelha fina do lado direito (~10-14 graus: marca do tiro anterior?).
14 -> 48 sugere que o numero = angulo da arma + inclinacao do chao (w - s = 14, w + s = 48 -> s ~17 graus).
O leitor de angulo atual so procura o ponteiro do lado direito (8-90 graus): virado para a esquerda ele leria a marca
antiga (ou 90). Para atirar no boss a esquerda (dx<0) falta: tocar esquerda, ler o ponteiro dos dois lados (ou ler o
NUMERO do mostrador), e depois tocar direita para voltar. Hoje, com o boss a esquerda, o bot usa o acerto mais
parecido e avisa no log ("boss a esquerda/em cima de voce").

## Mostrador perto de 0 grau (gravacao do bot 20261028_043449, Profundezas)
O angulo da arma continua do tiro anterior (Fantasma: 21) e o chao inclinado da Profundezas desconta ~17-20 graus: o
mostrador mostrou "1" (ponteiro quase horizontal). leitura.angulo so procurava de 8 a 90 graus -> leu lixo (90 / 25 / 8),
o bot apertou "baixo" (ja no limite), achou que as setas nao funcionavam e pulou 3 turnos. Agora a faixa e -30..100
(le -2,5 / -4,5 para o "1"; o ponteiro sempre le ~2-5 graus abaixo do numero, o que e coerente com a memoria, gravada
com o mesmo leitor). A faixa verde do mostrador = angulos permitidos naquele terreno.
Se a seta nao mexe o ponteiro, o bot testa a seta CONTRARIA: se ela mexe, o teclado funciona e o angulo esta no limite
-> volta e atira dali com a forca recalculada (antes ele trocava o modo de entrada e desistia).
Ideia futura: ler o NUMERO do mostrador (angulo exato; a cor do numero muda: amarelo/vermelho/ciano/verde).

## Tarefas: pegar TODAS (gravacao do bot 20261028_044345, 5 voltas)
Na 3a e na 5a volta a "Super Rota Norte" (passar Fantasma, Profundezas e Minhocao 1x) ficou sem coletar: o botao
"Obter recompensa" PULSA (R medio 154-204 quando ativo; cinza = (94,92,90)) e o detector exigia R>170 -> no quadro
escuro do pulso achava que nao havia o que coletar e fechava o painel. Agora: R>120 e R-G>50 e R-B>60.
Painel = arvore-acordeao: Tarefa/Missao primaria, de longo prazo, Tarefas diarias, Tarefa/Missao ativa; so uma
categoria aberta por vez; categoria FECHADA com tarefa concluida mostra o selo OK! (aberta nao mostra; os itens mostram).
Sub-lista mostra 4 itens e tem barra propria (x~573; seta de baixo = templates/seta_lista_baixo.png). Coleta: botao
vermelho -> clica; selo OK! -> clica (item seleciona, categoria abre); sem selo -> rola a sub-lista (seta) ate ela
parar de mudar; botao que nao reage 2x (mochila cheia?) e ignorado ate escolher outra tarefa. Teste com os quadros reais.

## Rotas (28/10)
Norte = Fantasma, Profundezas, Minhocao; Sul = Escorpiao Rei, Dragao Gelado, Rainha Liris (as 8 da aba "Instancia
normal": linha 1 Fantasma, Profundezas, O Minhocao, Escorpiao Rei; linha 2 Dragao Gelado, Rainha Liris, A Ultima
Luta, Gato Preto). T = Norte + Sul numa volta so. Leste: o usuario ainda nao consegue fazer.
Nenhuma das 6 tem dificuldade: com uma delas marcada, o quadro "Dificuldade" fica VAZIO (os botoes Normal/Dificil/Heroi
so aparecem com nada marcado). DIFICULDADE_DA_INSTANCIA = {} (suporte fica para rotas futuras, ou --dificuldade).
Telas genericas novas (nao dependem da arte da instancia):
- SALA: painel da direita da sala ("Minhas ferramentas"), patches (880,280) e (820,355): 1,00 em toda sala, <=0,24 no resto.
- CONFIG: cromo da janela de configuracao, (632,196) e (776,268): 1,00 na janela, <=0,24 no resto.
  (CONFIG_SEL foi minerado com a arte do Fantasma/Minhocao/Profundezas: com a arte de outra instancia nao casa.)
As artes das instancias novas sao aprendidas: CONFIG/CONFIG_SEL depois de clicar na instancia (recorte CFG_REGIAO,
so se tiver textura e a tela nao parecer CONFIG_VAZIA) e SALA depois de confirmar (recorte SALA_ARTE, apos 1 s).
Ficam em dados/modelos_aprendidos e vao no zip do EMPACOTAR (junto com dados/aprendizado.json).

## Rota Sul - 1a sessao do bot (20261028_052531): 7 lutas no Escorpiao, todas perdidas
- Spawn em x=17,7 ou 23 (minimapa); arena (chao) de x~13 a ~93; boss em 48,8 (y igual ao do jogador: o ponto vermelho
  e o PE do boss). Bot: 35% errou (passou), 48% errou, 22%/20% acertaram (vida 100 -> 86 -> 41 num turno, itens 2,3,4).
- Turno do boss: "Investida do rei!" - corre para a esquerda (48,8 -> 27) e empurra o boneco para fora -> "Falhou
  LOSE!!" -> sem cartas -> o bot repete a instancia (certo). Usuario: hitbox so no pe; usar F (aviao) para ir ao meio.
- F = aviao (icone azul ao lado do mostrador; R = outro, "16"). Implementado em atirador.turno_aviao + estrategias.py.
- Tridente: 3 projeteis; no voo (quadro 32) eles nao estao alinhados com a direcao de lancamento; as explosoes
  ficaram ~85 px (tela 1280) espalhadas. Nao deu para concluir se o espalhamento e por angulo (ai ~45 graus juntaria os
  3) ou por forca. Medida tomada: memoria pondera os acertos pelo dano (campo "dano" = % de vida tirada).
- Lados: mostrador virado para a esquerda = ponteiro do lado esquerdo (nota 70-115 contra ~22 do direito; virado para
  a direita, 98 contra 8). leitura.mira(f) -> (angulo, lado). Memoria usa |dx| (tiro espelhado).
- A tela do jogo tem as TABELAS DE FORCA do servidor (EstrAng 20/30/50/65 graus: distancia 1-10 da regua -> forca) e a
  regua 0-10 embaixo. Ideia futura: usar como semente da fisica (precisa converter minimapa -> regua por mapa).
- Artes aprendidas do Escorpiao (cfg/sala) viraram modelos oficiais em templates/.
