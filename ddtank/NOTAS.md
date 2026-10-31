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

## Sessao 20261028_054433 (Rota Sul, 5 voltas, 19,5 min) - tempos
Volta da Rota Sul ~3min40-3min55 (Escorpiao ~44 s de luta, Dragao 45-60 s, Rainha ~30 s; menus ~10-12 s por instancia;
cartas ~19 s - a tela de cartas tem cronometro de 15 s; tarefas ~8 s). 1o ataque: Rainha mata; Escorpiao deixa 22-41%
(2 ataques + aviao quando nasce em x<=29); Dragao deixa 18-41% (2 ataques).
Cartas incompletas (volta 5, Dragao): usuario usando o PC -> o jogo mostrava a carta virando ~3-5 s depois do clique;
o bot (1 carta por vez, confirmando pela tela) clicou cada uma 2x e o cronometro zerou com 2 viradas.
Dragao: minimapa todo azul; o ponto do boneco gruda na plataforma azul-escura (mascara normal acha so 15/42 leituras):
mascara ESTRITA (H 109-118, S>225, V>150) junto -> 42/42; e a moldura azul-escura do minimapa fazia "pontos" nos
cantos -> leitura._sem_linhas tira tracos retos >= 13 px (h) / 11 px (v). Rastreador pondera pelo tamanho do ponto.
"Turno pulado" no Dragao = PASS piscando no turno do boss (~8 s depois do tiro); "turno extra" com vida 0 depois de
matar (Escorpiao). Os dois agora nao apertam nada.
Disco: 1 hora de gravacao completa ~870 MB -> gravacao leve por padrao (registro.PRINTS_LEVE).
Metricas: metricas.py (logs/relatorio.txt, lutas.csv, voltas.csv). Combos: combos.py (dados/combos.json).

## PENDENCIAS - fazer SO quando o usuario pedir
- (FEITO 28/10 noite) Escorpiao Rei: aviao (F) desligado - estrategias.ESTRATEGIAS["ESCORPIAO_REI"]["aviao"] = False.
- ROTA LESTE: o boneco esta quase forte o suficiente. Quando o usuario conseguir faze-la na mao, ele grava e a gente
  implementa (mesmo caminho da Rota Sul: artes aprendidas, estrategias por boss). Ate la: refinar o bot atual.

## Correcoes do usuario (28/10, 6h46)
- Cartas: o jogo TRAVA na 3a carta; nao existe 4a (nem custo). Cliques a mais sao inofensivos.
- Combos: o objetivo e a luta mais curta - menos animacao (tirar o item 3 tira o 2o tiro) se ainda matar no 1o turno.
  "Teste de fogo" = 2,3,4,4 (+ buffs): se acertando tudo nao mata, precisa upar. CRITICO existe (pequena chance de
  muito dano): so concluir "mata no 1o turno" depois de dezenas de lutas. -> combos.py reescrito (tempo de luta medio
  com margem de duvida; fogo primeiro; so explora combos mais leves se o fogo mata em >= 50%).
- Disco D: com bastante espaco: gravacao completa de volta como padrao; o empacotar seleciona os prints do envio.

## Noite 28/10 (sessao 20261028_064645, rota T, 4h30, versao com gravacao leve e combos A/B/C/D)
38 voltas, 8,4 voltas/hora, volta mediana ~6min40 (7min08 de media com 2 voltas ruins). Por instancia (mediana):
menus ~10 s, luta 29-30 s (Fantasma/Profundezas/Minhocao/Rainha, 1 turno) e ~45 s (Escorpiao 3 turnos com aviao,
Dragao 2-3), cartas 19,2 s (cronometro de 15 s da tela), tarefas ~13 s por volta. Minimapa: confianca >= 0,53 em todos
os 337 turnos; 1o ataque errou 4/40 no Dragao e 1/40 na Rainha; cartas: nenhuma incompleta (32 recliques com o jogo lento).
BUG GRAVE (corrigido): a barra de vida do boss com 1-3% fica sem vermelho (o numero na barra diz "1%") e o leitor dava 0.
Com a trava do "turno fantasma" (vida 0 depois de atacar -> nao gasta itens) o bot PAROU DE ATACAR boss vivo:
 - Dragao (volta 3): ficou em "0%" por 15min37s (boss vivo empurrando o boneco) ate a luta acabar sozinha;
 - Escorpiao (volta 19): 43 -> 26 -> "0%", o Escorpiao se curou e na Investida jogou o boneco fora -> derrota.
 Na sessao anterior (gravacao completa) o mesmo aparece: barra 100% -> 13% -> (cura) 34% -> 1% -> morto. O ESCORPIAO
 SE CURA (~20%) no turno dele. Morto = RETRATO CINZA (saturacao 6-9; vivo 82-218 nas 3 do Sul) -> leitura.boss_morto;
 vida_boss so devolve 0 com o retrato cinza (barra vazia e retrato colorido = 1).
 Os "danos do 1o ataque = 100%" com 2+ turnos desta noite sao esse bug (1% lido como 0).
Combos (versao antiga A=2,3,4 B=3,3,4 C=1,4 D=2,4): pressionados de fato A=[2,3,4], B=[3,4] (o 2o item 3 nunca fica
colorido), C=[1,4], D=[2,4,7] / [2,4,8]. 1o ataque no Escorpiao: A ~58%, B 58-85%, C 28-58%, D ~14%; Dragao: A 16-59%,
B 33-58%, C 2-14%, D 14-31%. Tridente (2) perde dano no Escorpiao (so o pe tem colisao).
Combos agora: mesmo com PRECISA UPAR, explora os outros combos e fica com a luta mais curta (o diagnostico continua sendo
o teste de fogo). Confirmacao de tela 0,45 -> 0,3 s. DURACAO_MAX_DA_VEZ 11 -> 14 s (o PASS fica na tela com o tiro voando).

## Chefao Global - Pericao (gravacao do usuario 20261028_121648, 12h16)
Entrada: mapa -> Central "Jogar" -> sala -> trocar instancia (697,301) -> aba "Instancia do evento" (630,284) -> quadro
PERICAO (500,320; a aba tem tambem Super Mago e Macaco de Fogo) -> "Sim" (640,529; o quadro de dificuldade fica vazio)
-> fecha as 3 vagas -> Inicio -> "sozinho? Sim" -> batalha ~5 s depois. A configuracao abriu na aba normal (que tem a 5a
aba "Iniciar Batalha do Chefe"): o patch CONFIG_1 (estado generico CONFIG) ficava em cima dessa aba e nao reconhecia a
janela na aba do evento -> trocado pelo rotulo "Dificuldade" (452,465), que existe em todas as abas. Aba ativa = a mais
clara (brilho ~162 x ~100). Artes: templates/cfg_PERICAO.png e sala_PERICAO.png ("PERICAO ATE QUE DUROU").
Batalha: mesmo HUD. Minimapa: jogador (10.5, 58.4), boss parado (76.3, 61.4). INFO "Rodadas x/200". A barra de vida e
a GLOBAL (43% -> 1% em 11 min; 913 milhoes de vida; o chat mostra "Vida restante: 55% (506412524/912999995)").
Tiros do usuario: ponteiro 7 (o 1o em 4.5, depois 5 toques de "cima"), espaco 2.9-3.2 s, forca lida 78-89%, itens
2,3,4,4,4 (as vezes 7). Vento (Forca Vento, 2 digitos coloridos + seta): 0 -> 4.5 contra (ate 380 s), depois 1.0-4.0 a
favor; a forca do usuario ficou em 84-87% nos dois casos e TODOS os 39 tiros normais deram numeros de dano -> o vento
nao importa aqui. POW: botao (945,523) vermelho/pulsando quando cheio (saturacao 70-190; vazio 14-48). Usado 4x (221,
378, 552, 741 s), sempre B antes dos itens (sem o item 2 nesses turnos); o especial anda com a camera e tirou ~30 mil.
Acerto: numeros de dano (laranja/amarelo, contorno vermelho) na caixa (800,330)-(1010,480): tiros normais 908-5674 px,
fora dos tiros <= 702 -> limiar 800 (leitura.numeros_de_dano). O especial nao e conferido (camera anda).
Fim: o chefao caiu aos ~760 s (rodada 89/200) -> tela de resultado -> CARTAS normais (15 s, VIP na 3a) -> sala com o
Pericao. Chat: "Chefao Global (Novo Corsario) derrotado! Vida: 0% - modo global encerrado. Voces tem X minutos para
coletar o bau no..." (as recompensas sao pelo dano total, nao precisa fazer nada).
Implementado: estrategias.ESTRATEGIAS["PERICAO"] (chefe_global, angulo_min 0, tolerancia_angulo 1, usar_pow, combo
fixo 2,3,4), memoria aceita angulo minimo por instancia, 34 tiros do usuario em dados/tiros_semente.json, atirador
(B no POW cheio, acerto pelos numeros, espera 4 s), navegador (opcao C, --chefe, --horarios-chefe, abas, volta para a
rota onde parou, desiste se o quadro nao marcar), metricas (diagnostico CHEFAO GLOBAL), CHEFAO_GLOBAL.bat.
Duvida aberta: se o Pericao continua entravel fora do horario ("modo global encerrado" sugere que vira instancia normal).

### Decisoes do usuario sobre o Chefao Global (28/10, 15h40)
- Luta que acaba SEM cartas (morte / rodada 200 - ele nunca viu acontecer): assumir que existe. O bot volta para a sala
  e entra de novo enquanto for horario (navegador.finalizar_instancia: chefe_derrotas, sem avancar a rota). [ja faz]
- O chefao NUNCA fica vivo no fim do horario (muitos jogadores juntos). Se um dia acontecer: voltar para a rota normal
  (atualizar_chefe: fim do horario -> no_chefe = False; a luta em andamento termina antes). [ja faz]
- 21h: o usuario segue com o Chefao de novo (bot). 15h40: deixou a Rota Sul rodando; manda o log na volta.

## Melhorias pedidas pelo usuario (28/10 noite)
1. Aviao (F) do Escorpiao desligado (flag "aviao": False; o codigo continua e e testado).
2. Chefao Global 12h/21h: ainda nao testado de verdade (esperando o horario).
3. Rota Norte e "Todas" DESABILITADAS no menu (boneco completo com os drops): navegador.ROTAS_NO_MENU = S, P, C; Enter = Sul.
   N e T continuam com --rota N / --rota T.
4. Instancias especiais: mesma formula (artes aprendidas, estrategias por boss); Leste tem uma ressalva (ainda nao).
5. Pericao COMUM fora do horario: rota P (menu) = instancia "PERICAO_COMUM" para o atirador/metricas (vida propria, sem
   numeros de dano, combos testados); memoria compartilha os tiros do Pericao do chefao (mesmo mapa). Nos horarios, com
   "Chefao Global nos horarios" = sim, a rota P troca sozinha para o modo Chefao Global.
6. Cartas so das instancias que interessam: pergunta ao abrir (rota com 2+ instancias) ou --cartas RAINHA_LIRIS|TODAS.
   Padrao da Rota Sul = so Rainha Liris. Nas outras o bot nao clica em carta e espera a tela passar (nao gasta cupons;
   duvida: se o jogo entrega as 2 cartas gratis sozinho no fim do cronometro).
7. (sem texto na mensagem do usuario)
8. Painel com botoes (front): estudar - ver resposta na conversa (tkinter, sem instalar nada).


## ARQUIVO: LEIA-ME antigo (historico das sessoes; os .bat citados foram removidos em 28/10 noite - hoje so o BotDDT.bat)
```
DDTANK - FASE 1 (captura e controle da janela)
==============================================

Esta fase ainda nao joga. Ela so confirma que o bot ENXERGA o jogo e consegue
CLICAR / APERTAR TECLAS nele sem usar o seu mouse. Nada do launcher e modificado.

Requisitos: Windows, Python, e:  pip install numpy opencv-python-headless
Jogo em 1920x1080 com escala do Windows em 100% (se possivel).

Passo a passo (na pasta ddtank, com o jogo aberto e logado)
-----------------------------------------------------------
1) python bot_ddtank.py --listar
   Procure a linha do launcher/jogo e anote o EXE e um trecho do TITULO.
   Preencha TITULO_JANELA / EXE_JANELA em config.py (ou use --titulo / --exe).

2) python bot_ddtank.py --diagnostico
   Salva duas capturas em ddtank\capturas (modos "print" e "tela") e diz se estao
   pretas, brancas ou OK. Mande-me o texto que aparecer e os PNGs.

3) Deixe o jogo numa tela qualquer e teste:
   python bot_ddtank.py --clicar 960 540        (clica no meio e salva a captura com o alvo marcado)
   python bot_ddtank.py --tecla espaco --segundos 1.5

4) Para me mostrar como uma partida acontece (bala, vento, barra de forca):
   python bot_ddtank.py --gravar 1 --n 60       (60 capturas, 1 por segundo)

Se "print" der imagem PRETA, o launcher precisa ser aberto com flags que mantem o
jogo desenhando coberto (como no INICIAR_FARM.bat do Social Empires) - me avise.
Use  --modo tela  para forcar a captura por copia da tela (a janela tem que estar visivel).

Pastas: capturas\ (criada na 1a captura), logs\ e sessoes\ ficam so no seu PC; envio\ vai para o GitHub.
Coloque suas imagens-modelo do jogo em templates\ (nas proximas fases).


GRAVADOR DE SESSAO (observa voce jogando - nao controla nada)
==============================================================
Duplo clique em GRAVAR_SESSAO.bat (ou: python gravador.py --nota "rota1") e jogue a rota
normalmente. Ele registra cliques, teclas (e por quanto tempo cada uma ficou segurada: a
barra de espaco = a forca do tiro) e prints antes/depois de cada acao.
  F9  = marcador (ex.: "comecou a luta", "errei o tiro")      F10 = terminar
So grava quando a janela do jogo esta em primeiro plano; o que voce faz em outros
programas nao e registrado. (Se digitar no chat do jogo, isso aparece como teclas.)
Ao terminar, o empacotar.py gera zips de ate 20 MB em ddtank\envio\.
ATENCAO: so pode haver UMA janela do jogo aberta (uma conta). Se houver duas, o gravador
se recusa a rodar para nao gravar a janela errada.

ENVIAR / ATUALIZAR COM GIT (sem arrastar arquivos)
--------------------------------------------------
Uma vez: instale o Git (https://git-scm.com/download/win), abra o cmd e rode:
   git config --global user.name "Seu Nome"
   git config --global user.email "seu@email.com"
   cd /d D:\
   git clone --depth 1 -b claude/wonderful-rubin-3oyqi3 https://github.com/samuelccouto/estudos-de-bots-para-grind-games.git
(na primeira vez abre o navegador para voce entrar no GitHub). Use a pasta D:\estudos-de-bots-para-grind-games\ddtank.
(--depth 1 = baixa so a versao atual, sem o historico das gravacoes antigas: poucos MB.)
Ja tem a pasta no C:? Rode o MUDAR_PARA_D.bat de la (veja "DISCO D:" no fim deste arquivo).
Depois:  ATUALIZAR.bat = baixa as novidades.  ENVIAR_SESSAO.bat = envia os zips de envio\.
O GRAVAR_SESSAO.bat ja pergunta no fim se quer enviar.

ATALHOS (duplo clique):  LISTAR_JANELAS.bat | DIAGNOSTICO.bat | GRAVAR_SESSAO.bat | ENVIAR_SESSAO.bat | ATUALIZAR.bat


NAVEGADOR (fase 2) - percorre a rota de instancias sozinho
==========================================================
Rota: Fantasma -> Profundezas -> O Minhocao -> coleta as Tarefas -> Central -> recomeca.
A BATALHA ainda e sua (o tiro automatico e a fase 3): o bot espera a luta terminar.
Ele nao usa o seu mouse. Teclas: F8 = pausar/continuar, F10 = sair.

Ordem de teste (faca nesta ordem!):
 1) VER_TELA.bat       so mostra qual tela o bot reconhece, a cada segundo (nao clica).
                       Navegue pelo jogo (mapa, Central, sala, cartas...) e confira se bate.
 2) NAVEGAR_SIMULADO.bat  mostra onde clicaria, sem clicar.
 3) NAVEGAR.bat        liga de verdade. Comece com o jogo no MAPA ou na CENTRAL.
Se um clique "nao tiver efeito", o bot troca sozinho o jeito de enviar o clique (janela principal ->
janela interna do Chromium) e avisa no console. Se mesmo assim nada acontecer, me mande o log
(logs\navegador_<data>.log) e um print.
Outros comandos:  python navegador.py --uma-vez   |  --sem-tarefas  |  --comecar-em 2
Testes sem o jogo:  python testes\test_navegador.py


ATIRADOR (fase 3) - o bot joga os turnos da batalha
===================================================
Como funciona (cada turno; o botao PASS so aparece na SUA vez e dura ~8 s):
  - le a posicao sua e do boss no minimapa e decide angulo + forca pela MEMORIA dos seus tiros
    (dados\tiros_semente.json = seus 17 acertos) ou, quando a instancia tem constante confiavel, pela fisica;
  - ajusta o angulo com as setas (olhando o ponteiro), aperta os itens que estiverem COLORIDOS
    (ordem em atirador.py: ORDEM_ITENS = 2,3,4,4,4,4,5,6,7,8; limites: item 1 e 3 ate 2x, item 2 ate 1x),
    segura ESPACO olhando a barra e solta na forca certa;
  - depois olha a vida do boss: acertou/errou, e APRENDE (dados\aprendizado.json).
Teste na ordem:
 1) ATIRAR_SOMBRA.bat   so mostra o tiro que faria (nao aperta tecla). Jogue VOCE e compare: o angulo/forca
                        que ele sugere e parecido com o que voce faz? "[tiro N] ... mirar X graus, forca Y%"
 2) ATIRAR.bat          liga de verdade (navegacao + batalha). Fique olhando o primeiro turno.
Se as setas/teclas nao chegarem no jogo, o bot tenta outro modo de entrada sozinho e avisa; se nada
funcionar ele NAO atira e escreve "Pulando o tiro" - me mande o log.
Itens: python navegador.py --atirar --itens 3,4,4,5   (muda a ordem). Testes: python testes\test_atirador.py


IMPORTANTE (versao de 28/10, tarde)
===================================
* USE SO UM BOT POR VEZ (NAVEGAR, ATIRAR_SOMBRA ou ATIRAR). Abrir mais de um faz todos clicarem e apertarem
  teclas juntos, e a ordem das instancias e os tiros ficam malucos. Agora o programa recusa abrir uma 2a copia.
* O bot GRAVA o que faz (cliques, turnos de tiro, prints) em sessoes\<data>_bot\ e, ao fechar, oferece
  empacotar e enviar (EMPACOTAR_E_ENVIAR.bat). Assim eu vejo o que ele fez. (--sem-gravar desliga.)
* Se o jogo perder o foco (voce clicou em outra janela, ou no proprio .bat) aparece "Clique no jogo para continuar
  jogando". O bot reconhece esse pop-up em qualquer tela (inclusive na batalha) e fecha clicando numa AREA NEUTRA
  (o chat, o log da batalha...), nunca no pop-up: o clique atravessa o pop-up e acertaria o que esta por baixo
  (no mapa, o pop-up cobre a Sala de Casamento).
* Se o bot cair numa tela de cidade que a rota nao usa (Sala de Casamento, Leilao...), depois de 6 s ele volta
  pela porta da barra de baixo (ate 4 tentativas).
* Ordem das instancias: o bot confere qual instancia esta marcada na configuracao e na sala; se estiver
  errada ele corrige, e no fim da rota coleta as tarefas antes de recomecar.
* Vagas da sala: so clica nas que mostram "Em Espera". Vaga ocupada por outro jogador nao e tocada
  (o bot avisa no log "outro jogador entrou na sala").

* Carga da forca: a tecla ESPACO agora e mantida com repeticao automatica a cada 30 ms numa thread propria (como o
  teclado de verdade); se a forca ficar muito abaixo do alvo, o bot troca sozinho de "olhar a barra" para "soltar
  pelo relogio". Cada tiro grava o trace da barra no registro. TESTE_FORCA.bat (numa batalha, na sua vez) mede qual
  forma de segurar o espaco o jogo aceita (esperado ~38% em 1,0 s).

* FOCO DO TECLADO (28/10): o mouse funciona com o jogo em segundo plano, mas o TECLADO nao: o Chromium so entrega
  teclas a pagina em foco (por isso o pop-up "Clique no jogo" aparece e as setas nao mudam o angulo). Na batalha o bot
  pede foco antes de cada turno: 1o "virtual" (sem mexer nas suas janelas); se as setas nao funcionarem, sobe para
  "jogo em primeiro plano durante o turno" e devolve o foco para a sua janela logo depois. Para ja comecar assim:
  python navegador.py --atirar --foco 2   (ou deixe o jogo na frente). Sem foco real o teclado simplesmente nao chega.

* COMO O BOT DECIDE FORCA E ANGULO (28/10): (1) se ja acertou nessa mesma situacao (voce e o boss nas mesmas posicoes
  do minimapa) repete o angulo e usa o CENTRO da faixa de forca aprendida; (2) senao, CALCULA pela balistica
  (forca^2 = R * F(distancia, altura, angulo)); a constante R de cada instancia e APRENDIDA: cada acerto prende R
  perto do que ele implica, cada erro descarta a faixa correspondente - numa instancia nova ele acerta em ate ~4
  tiros e depois mantem; (3) o angulo preferido e o que voce costuma usar na instancia (ou 35), trocando por outro
  se a forca ficar fora de 18-85%. O que aprende vai para dados\aprendizado.json. O log mostra "fisica: R=..."
  e a incerteza (x1.3 = confiante; x3 = ainda procurando).

* MINIMAPA CORRIGIDO (28/10, noite): a causa da "forca fraca" no Fantasma era a LEITURA DO MINIMAPA. O bot achava que voce
  estava em (71,23) - la em cima do mapa - quando voce estava no chao em ~(32,57); com a posicao errada a conta da forca
  da 10-20%. O leitor antigo pegava "a maior mancha azul" (na Profundezas era a AGUA). O novo procura so pontos redondos
  da cor exata do seu marcador e, na batalha, usa a posicao que MAIS SE REPETE (um efeito azul passageiro nao engana).
  O log agora mostra "voce (32, 57) (em 90% das leituras)". Se esse numero vier baixo ou a posicao parecer estranha,
  me mande a gravacao.
  Os tiros que o bot aprendeu com a leitura antiga (dados\aprendizado.json) sao ignorados automaticamente.
  Forca: o bot escolhe a forca com MAIOR CHANCE DE ACERTO ("chance de acerto ~95%" no log); se voce ja acertou daquela
  mesma posicao, ele repete a sua forca quando a fisica concorda.
  Boss a ESQUERDA do seu boneco: ainda nao vira o boneco (precisa de mais estudo do mostrador) - ele avisa no log.

* ANGULO PERTO DE ZERO (28/10, madrugada): na Profundezas o chao inclinado faz o mostrador cair para ~1 grau. O bot so
  sabia ler o ponteiro entre 8 e 90 graus, leu errado, apertou a seta para o lado errado e desistiu do turno ("parou de
  mexer"). Agora le de -30 a 100 graus. E se uma seta nao mexer o ponteiro, ele testa a outra: se a outra funciona, o
  angulo esta no limite da arma e ele atira dali, recalculando a forca.

* TAREFAS (28/10): o bot agora coleta TODAS as tarefas concluidas (selo verde "OK!") antes de recomecar: as diarias,
  a "Super Rota Norte" e o que mais tiver. Antes, quando o botao vermelho "Obter recompensa" estava no momento mais
  escuro do brilho (ele pisca), o bot achava que nao havia nada e fechava o painel. Ele tambem rola a lista de cada
  categoria ate o fim procurando mais selos. O log mostra "[TAREFA] N recompensa(s) coletada(s)".

ROTAS NORTE, SUL E TODAS (28/10)
================================
Ao abrir NAVEGAR / ATIRAR / ATIRAR_SOMBRA o bot pergunta:
   N = Rota Norte: Fantasma > Profundezas > Minhocao
   S = Rota Sul:   Escorpiao Rei > Dragao Gelado > Rainha Liris
   T = Todas: Fantasma > Profundezas > Minhocao > Escorpiao Rei > Dragao Gelado > Rainha Liris; so depois coleta
       as tarefas e recomeca.
(Enter sem nada = Norte.) Para nao perguntar: python navegador.py --atirar --rota S   (ou N / T).
Nenhuma dessas instancias tem dificuldade para escolher; o bot nao mexe nos botoes Normal/Dificil/Heroi.
Primeira vez na Rota Sul: o bot ainda nao conhece o desenho dessas instancias. Ele APRENDE sozinho na 1a vez que as
escolhe (aparece "[APRENDI] arte de ESCORPIAO_REI..." no log) e guarda em dados\modelos_aprendidos; o EMPACOTAR manda
esses desenhos junto com a gravacao para eu transformar em oficiais. A forca dos tiros tambem e aprendida: nas
primeiras lutas de cada instancia nova ele pode errar alguns tiros ate acertar a "escala" do mapa (acerta em ~4).
Rota Leste: ainda nao.

ROTA SUL - ESCORPIAO, RAINHA E O TRIDENTE (28/10, noite)
=======================================================
* VIRAR O BONECO: o bot agora le o ponteiro dos DOIS lados do mostrador e sabe para onde o boneco olha. Se o boss
  (a Rainha corre para os dois lados) estiver do outro lado, ele toca a seta esquerda/direita (toque curto) ate virar
  e atira espelhado. Log: "virando para a esquerda (o boss esta desse lado)".
* ESCORPIAO REI - AVIAO (F): ele nao morre num turno e a "Investida do rei" joga para fora quem esta perto da borda.
  Se o boneco nasceu perto da borda (x ate ~29 ou a partir de ~77 no minimapa) e o boss tem mais de 55% de vida, o
  1o turno e um VOO: aperta F, mira no meio da arena e atira SEM itens. Depois ataca normalmente. Log: "[AVIAO]".
  No turno seguinte ele confere se o boneco saiu do lugar; se o F nao funcionar 2 vezes, desiste dele.
  As regras ficam em estrategias.py (arena, distancia da borda, destino, vida para atacar direto) - da para ajustar.
* HITBOX NO PE: o ponto vermelho do minimapa ja e a posicao do pe do boss (fica na altura do chao), entao a mira ja e
  no pe. O bot aprendeu a forca do Escorpiao na 1a sessao (~20% a ~33 graus da borda esquerda).
* TRIDENTE (item 2): os 3 projeteis caem espalhados; no Escorpiao (so o pe tem colisao) as vezes so 2 pegam. Agora o bot
  guarda quanto de vida cada tiro tirou e, ao repetir um tiro, puxa a forca para a que tirou MAIS vida (3 acertos).

CHEFAO GLOBAL - PERICAO (28/10, almoco)
=======================================
Ao abrir ATIRAR / NAVEGAR agora tem a opcao C:
   C = so o Chefao Global: o bot vai para a sala, aba "Instancia do evento", marca o PERICAO, fecha as vagas, Inicio,
       "sozinho? Sim" e luta. A luta so acaba (cartas) quando o servidor inteiro derruba o chefao. Depois ele ESPERA o
       proximo horario (12h-13h e 21h-22h) e entra de novo. Atalho: CHEFAO_GLOBAL.bat.
Escolhendo N, S ou T ele pergunta tambem:  "Chefao Global nos horarios? (S/n)"  (Enter = sim).
   Sim: o bot faz a rota normalmente; quando der 12h (ou 21h) ele termina a instancia em andamento, vai para o Pericao,
   luta ate o chefao cair e VOLTA PARA A ROTA de onde parou. Fora do horario nao muda nada.
   Horarios diferentes?  python navegador.py --atirar --horarios-chefe 12:00-13:00,21:00-22:00
Na luta (aprendido da sua gravacao 20261028_121648):
 * mira quase reta (ponteiro em 7) e forca ~85%: 39 de 39 tiros seus pegaram, com o vento de 4,5 CONTRA ate 4,0 A FAVOR.
   Ou seja, nessa distancia o vento quase nao muda o acerto - o bot nao corrige vento aqui (se comecar a errar, aparece
   no log e eu ajusto).
 * itens: sempre 2, 3 e o maximo de 4; quando a stamina nao der mais 4, os 5, 6, 7, 8 (sem testar combos).
 * POW: quando o medidor do especial enche (o botao POW fica vermelho), aperta B antes dos itens (o especial tirou ~30 mil
   de uma vez na sua gravacao; um tiro normal ~3 mil por bala).
 * a barra de vida do topo e a do SERVIDOR (todo mundo batendo) - nao diz se o SEU tiro pegou. O bot confere pelos
   NUMEROS DE DANO que sobem no boss. Log: "[tiro] numeros de dano no boss: 2500 px -> ACERTOU".
 * se a luta acabar sem cartas (rodada 200? morte?), ele entra de novo enquanto for horario. Se o quadro do Pericao nao
   marcar (evento fechado), desiste ate o proximo horario.
 * a configuracao da sala abre na ultima aba usada: o bot confere a aba clara e clica na certa (normal ou do evento).
 * relatorio: "Pericao (Chefao Global): CHEFAO GLOBAL - N lutas, turnos, tiros normais acertando X%, especiais (POW)".

QUALIDADE DE VIDA - noites inteiras (28/10)
===========================================
* DISCO D: - o bot nao aponta para o C: em lugar nenhum (tudo fica dentro da pasta do bot). O que enchia o C: era a
  propria pasta: as gravacoes antigas (envio\*.zip ~870 MB + o historico do git ~880 MB) e sessoes\ (~300 MB a cada
  20 min de gravacao completa). Para mudar:
    1) feche o bot; 2) na pasta ATUAL (C:\...\ddtank) de dois cliques em MUDAR_PARA_D.bat: ele baixa uma copia nova e
    leve em D:\estudos-de-bots-para-grind-games e copia o que o bot aprendeu (dados\aprendizado.json, combos,
    artes, logs); 3) teste um ATIRAR.bat da pasta do D:; 4) funcionando, apague a pasta antiga do C: pelo Explorer.
  O Python continua instalado no C: (ocupa pouco). Os zips ja analisados eu apago do GitHub depois de ler.
* GRAVACAO (atualizado): o bot grava TUDO no disco (sessoes\, guarda as 3 ultimas). O EMPACOTAR manda o texto inteiro
  (eventos, resumo, relatorio, csv, log do dia) e os prints SELECIONADOS: tudo dos primeiros 15 min, inicio e fim de
  cada turno de tiro e todos os problemas (com os prints dos 25 s antes). Uma noite fica em algumas centenas de MB.
  EMPACOTAR_TUDO.bat manda todos os prints (so se eu pedir). Disco pequeno: python navegador.py --atirar --gravacao-leve
* CARTAS SORTEADAS: a cada luta o bot sorteia 3 cartas diferentes e clica nas 3 em seguida (a tela tem cronometro de
  15 s; com o PC ocupado o jogo demora a mostrar a carta virando e antes o bot esperava cada uma e estourava o tempo).
  Se alguma nao virar em 3 s, clica de novo nela; depois de 2 tentativas, sorteia outra (o jogo trava na 3a carta,
  entao cliques a mais nao abrem nada).
* CRONOMETRO (logs\relatorio.txt, atualizado a cada luta; logs\lutas.csv e logs\voltas.csv acumulam tudo):
  tempo de cada luta, de cada instancia (menus + luta + cartas) e de cada volta; voltas por hora; turnos por luta;
  quanto de vida o 1o ataque tira; e o DIAGNOSTICO de cada instancia:
     OK - mata no 1o turno | PRECISA UPAR - acerta mas nao mata (e quanto falta) | PONTARIA - o 1o tiro erra.
  No console aparece "[TEMPO] Dragao Gelado: luta 45s - VITORIA em 2 turno(s), 1o ataque tirou 64%".
  O EMPACOTAR manda o relatorio, os csv e o log do dia junto com a gravacao.
* COMBOS DE ITENS (dados\combos.json) - o bot procura a LUTA MAIS CURTA em cada instancia:
  1) TESTE DE FOGO: 2,3,4,4 + os buffs que a stamina der (dano maximo), 5 lutas. Se nem ele mata no 1o turno (com os
     tiros acertando) -> PRECISA UPAR: usa sempre o dano maximo e o relatorio avisa.
  2) Se o fogo mata no 1o turno (em pelo menos metade das lutas), testa combos com MENOS ANIMACAO (cada item 3/1 e mais
     um tiro do boneco): 2,4 (tridente, 1 tiro so) / 4 (so buffs) / 3,4 / 1,4 / 3,3,4 - 3 lutas cada.
  3) Depois fica com o de menor tempo medio de luta, com margem de duvida: um combo que matou 1 vez por CRITICO
     continua sendo medido; so vence quem e rapido NA MEDIA de muitas lutas. O relatorio mostra a tabela de combos.
  --itens 2,3,4,4 fixa a sua ordem e desliga os testes.
* Outras correcoes desta gravacao: o turno "extra" depois do boss morto nao gasta mais itens; o PASS que pisca no turno
  do Dragao nao vira mais "turno pulado"; o minimapa do Dragao Gelado (mapa todo azul, moldura azul) agora acha o
  boneco em todas as leituras; depois do aviao a posicao nova do boneco e usada no ataque seguinte.
* Para deixar a noite toda: desligue a suspensao do Windows (Configuracoes > Sistema > Energia > Suspender: Nunca)
  e deixe o jogo na frente. Rode ATIRAR.bat e responda T.

* (28/10, manha) VIDA DO BOSS: com 1-3% a barra fica sem vermelho e o bot achava que o boss tinha morrido - parava de
  atacar (um Dragao ficou 15 min assim; um Escorpiao se curou e ganhou a luta). Agora "morto" = retrato do boss CINZA.
  Combos: mesmo quando precisa upar, o bot testa os outros combos e fica com a luta mais curta (no Escorpiao o 3,4 tirou
  mais vida que o 2,3,4 - o tridente espalha as balas e ele so tem colisao no pe).

MENU ATUAL (28/10 noite)
========================
  S = Rota Sul (Enter)   P = Pericao comum (fora do horario do chefao)   C = Chefao Global
  Rota Norte e Todas: desabilitadas no menu (nao apagadas): python navegador.py --atirar --rota N  (ou T)
  Depois da rota o bot pergunta em quais instancias abrir as cartas (Sul: so a Rainha Liris; as outras so completam a
  missao e ele espera a tela passar). Sem perguntar: --cartas RAINHA_LIRIS  (ou --cartas TODAS).
  O aviao (F) do Escorpiao Rei esta desligado: o boneco mata de primeira.

PAINEL COM BOTOES (28/10 noite)
===============================
Duplo clique em BotDDT.bat: abre uma janela escura onde voce escolhe a rota (Sul, Pericao comum, Chefao Global; marque
"mostrar Rota Norte..." para as antigas), em quais instancias abrir as cartas, se luta o Chefao Global nos horarios
(e quais), tarefas, gravacao, e clica INICIAR. Mostra o log ao vivo (amarelo = chefao/POW, vermelho = problema, azul =
tempos) e o relatorio. PARAR pede para o bot parar sozinho (fecha a gravacao e escreve o relatorio; ate 20 s).
"Enviar gravacao" roda o EMPACOTAR_E_ENVIAR.bat. As escolhas ficam salvas (dados\painel.json).
Por baixo o painel so roda o navegador.py --atirar com as opcoes: os .bat de antes continuam funcionando.

BotDDT.bat = TUDO EM UM (substitui os outros .bat do dia a dia): baixa as novidades (git pull) e abre o painel. No
painel: INICIAR/PARAR, "Enviar gravacao" (empacota e envia sem perguntas e sem janela preta), "enviar ao parar"
(automatico) e "Atualizar". Os .bat antigos continuam existindo, mas nao precisa mais usar.

```

## Sessoes de 28-29/10 (noite) e o travamento das 12h
- 221836 (42 min) e 233755 (7h43, rota T, 68 voltas, 8,8/h): todas as lutas vencidas, 0 derrotas. Norte e Rainha 100% no 1o
  turno; Escorpiao (com aviao, hoje desligado) 23% no 1o turno, 98% de acerto, 1,8 turnos; Dragao 71% (89% de 1o ataque).
- 105018 (Rota Sul, ate 13h03): 26 voltas, 11,7/h; Escorpiao 96% no 1o turno, Dragao 88%, Rainha 96% (sem aviao).
  TRAVOU 12:00-12:55 no Pericao: a confirmacao "A instancia apresenta mais desafios... Concordar" (texto diferente do
  POPUP_SOZINHO) nao era reconhecida (clicava em Inicio 83x) e, as 12:10, o aviso "O Chefao Global vai comecar em
  alguns minutos! ... sim" apareceu por cima. -> estados POPUP_SOZINHO2 (Concordar 575,402) e POPUP_AVISO (sim 644,394).
- Bug meu: sed no empacotar.py deixou aspas dentro de aspas (SyntaxError no envio). Regra: py_compile em todos os .py.

## Calibracao de tela (29/10): qualquer tamanho de janela
O jogo e um canvas fixo de 1000x600 px (666x399 no quadro de referencia de 1280, em (312,162)) cercado de decoracao da
pagina (static map: todo o resto muda entre telas; todos os patches de estados.json ficam dentro do canvas).
tela.py: canonico = janela*f + (tx,ty). 1) calibrar_pontos: SIFT da janela (reduzida a 1400 px) x quadros de referencia do
canvas em templates/ref/*.jpg -> estimateAffinePartial2D (escala + deslocamento, <2 s, sub-pixel); 2) confere que o quadro
canonico e uma tela conhecida; 3) plano B lento: recortes de estados.json em ~70 zooms (0.5-2.2). Janela original (f~0.666,
t~0) = modo legado (nada muda). IOJanela renderiza o quadro canonico (1280x688, k=1) e converte os cliques de volta;
recalibra se o tamanho da janela mudar ou a tela ficar desconhecida (>=15 s, no maximo 1x/90 s). navegador.testar_tela +
--testar-tela + botao do painel. Testes: testes/test_tela.py (7 janelas x 6 telas sinteticas a partir de quadros reais;
erro < 3 px). LIMITES: so testado com janelas SINTETICAS; nao sabemos como o launcher do amigo se comporta (se o canvas
for esticado sem manter a proporcao, falha); zoom < 0.75 perde o minimapa; refs vem das minhas telas (retrato etc.).

## BACKLOG (decisao do usuario, 29/10): prioridade = bot 100% funcional e independente NA MAQUINA DELE
- Adaptar o bot a outras maquinas/amigos (tamanhos de tela, personagens, launcher): tela.py ja calibra janelas de outros
  tamanhos (testado so com janelas sinteticas); falta validar com um amigo de verdade ("Testar a minha tela"), telas que
  dependem do visual do personagem e a forca de tiro de outros bonecos. NAO priorizar agora.
- Rota Leste (quando o usuario conseguir fazer na mao), instancias especiais (mesma formula), Chefao Global (testar de verdade
  no 1o horario com o bot), Pericao comum (rota P, nunca rodada de verdade).

## Robustez (29/10)
- [ERRO] falha inesperada no laco: registra o traceback, continua; 12 em 10 min param o bot.
- [ALERTA] preso: mesma tela (fora BATALHA/CARTAS/TAREFA) ou tela desconhecida por 120 s -> Esc + botoes das janelinhas
  conhecidas + print "preso" na gravacao; repete a cada 60 s.
- PC nao entra em suspensao enquanto o bot roda (SetThreadExecutionState). Painel: "religar sozinho se o bot cair" (5x/hora).
- testes/test_sintaxe.py compila todos os .py. dados/painel.json, aprendizado, combos e artes aprendidas fora do git (.gitignore).

## Sessoes 29/10 tarde (133642, 134102, 135013, 135059) e painel novo
- 135059: Rota Sul 2h50, 55 voltas, 19,4/h (cartas so da Rainha), Escorpiao 97% no 1o turno (2 derrotas em 58), Dragao 89%, Rainha 96%.
  As outras 3 eram testes curtos. Painel reformulado (cards Rotas / Chefes / Abrir cartas / Opcoes; modo desenvolvedor x amigos),
  estatisticas.py + drops.py (resumo da execucao). A gravacao do Gato Preto NAO estava no GitHub (so sessoes _bot): pedir de novo.

## 30/10: Pericao do evento (sessoes 205939...210420) e Gato Preto
- Chefao Global das 21h FUNCIONOU quando o bot chegou na batalha (21:01: tiro acertou 3666 px de numeros de dano, vitoria, cartas, espera 30/10 12:00).
  Antes disso o Inicio da sala fica "sem efeito" ~18 s (o evento so abre na hora exata) - normal.
- BUG (corrigido): 4 sessoes (210231, 210317, 210327, 210405) ficaram "ligadas" sem fazer nada: a calibracao de tela caia no plano B lento
  (~35 s por tentativa, mais de 1 min em tela desconhecida) logo no 1o quadro. Agora: 0) tela conhecida so por largura (instantaneo), 1) SIFT,
  2) plano B com orcamento de 5 s, e janela do tamanho original + tela desconhecida = modo legado na hora. Log "[TELA] calibrando...".
- Gato Preto: os "ERROU" eram falsos (o boss se cura; ate nos tiros do usuario 41% -> 41%): estrategias.GATO_PRETO["acerto_incerto"] =
  vida que nao caiu nao vira erro na memoria. 200138: 2 lutas de ~4min10, 16 turnos, 7 B.

## 30/10 madrugada: Rota Leste (gravacao 20261030_004606) - IMPLEMENTADA, NUNCA RODADA DE VERDADE
- A Rota Leste = A ULTIMA LUTA (2 fases) + DEVORADORES (rota "L"; tambem como chefes ULTIMA_LUTA / DEVORADORES).
- Fase 1: boss pequeno ("Boxeador") ao lado do boneco, 2 turnos (mira 12-20 graus, forca 15-20%); no fim vem um painel PEQUENO de cartas
  (3x3, estado CARTAS_P, 1 carta); a sala volta com a FASE 2 pronta (arte "sala_ULTIMA_LUTA_FASE2": so Inicio). Instancia de batalha do
  atirador: ULTIMA_LUTA_F1 / ULTIMA_LUTA_F2 (navegador.fase). Cartas normais (21) so no fim da fase 2.
- Fase 2: so o boss VERDE na plataforma (minimapa ~(51,27); `alvo: mais_alto`), boneco no chao (13,62; `jogador_y_min` 50), angulo ~70, forca ~54;
  boss pequeno volta e cobre o boneco -> `reposicionar` (anda 0.25 s para a direita, ate 2x); armadura forte (muitos turnos, `acerto_incerto`);
  perks Z/X/C + item E + B (so com o buff) como no Gato; combo 1,4 (o usuario nunca usou o 2 aqui). Andar desfaz o buff do E.
- Devoradores: na 2a PAGINA da lista de instancias (seta (828,367); `preparar_pagina`, `pagina_da_lista`); boneco nasce colado na borda esquerda do
  minimapa (x ~0.7: `minimapa_x_min` 0); dragao simples (Zen'Gor), 2 turnos; confirmacao "Concordar" normal.
- Sementes de tiro (15) em tiros_semente.json; artes cfg/sala e templates de pagina da lista em templates/.
- Testes: test_navegador (SimLeste de ponta a ponta) passam; NADA testado no jogo.
- O usuario continuou o projeto por conta propria (outro assistente) na pasta D:\...\ddtank\botDDTGPT; precisa subir para o GitHub
  (branch botddtgpt) para eu comparar, corrigir e unir a esta versao.

## 30/10 noite: UNIAO com a versao paralela (botDDTGPT, feita pelo usuario com outro assistente)
Comparei botDDTGPT com a base (e13e258) e com esta versao (3-way merge). O que ENTROU:
- **Super Rota (U) e Rota Norte+Sul (T)**: ordem N > missao > S > missao > L > missao; `navegador.FIM_ROTA_CUPOM` (3 / 6 / 8 = indice depois da ultima
  instancia de cada rota), `cupom_pendente`, `metricas.rota_cupom_fim` -> logs/cupons.csv e secao "CUPONS POR ROTA" no relatorio (valores informados
  pelo usuario: N 40000, S 50000, L 60000; o bot NAO le o saldo de cupons, so estima: creditado se houve coleta de missao). Painel: cards Super Rota / Rota Norte e Sul.
- **Tarefas**: reconhecimento do painel pelo cabecalho (`painel_tarefa_visivel`), recompensas de ESCOLHA MANUAL ignoradas (`tarefa_exige_escolha`),
  popup "Escolha uma recompensa" e escolha do 1o material SO na missao Super Rota Leste (`escolher_material_leste`); Gato Preto sozinho nunca coleta tarefas.
- **Saida da batalha mais robusta**: PASS visivel = ainda e a vez (animacao parecida com CONFIG_SEL nao encerra a luta); espera 12 s se a tela
  seguinte nao e clara (SALA/CENTRAL/MAPA).
- **Combos fixos pedidos pelo usuario**: Fantasma/Profundezas/Minhocao/Dragao/Rainha = 2,4,4; Escorpiao = 2,4 (por isso esses nao aprendem combos).
- test_cupons.py, frames TAREFA_LESTE_ESCOLHA / POPUP_DICAS_PERICAO, 6 sementes de tiro da Leste (F1/F2).
O que NAO entrou (decisao): a Leste deles (3 instancias na rota com ULTIMA_LUTA_FASE2 "escolhida" como se fosse outra instancia, CARTAS_ENTRADA, busca de
forca por erros consecutivos, boneco do Devoradores chutado em (15,62) - o certo e x ~0.7, mira do Gato subindo para 18 graus com o item 2) - fica a
versao com fase interna (`navegador.fase`), CARTAS_P, `minimapa_x_min` e Gato sem o item 2. Obs.: o commit e6e86b2 trouxe 4,2 GB de zips em
botDDTGPT/envio (so no historico do git, .git ficou ~5 GB); o ideal e limpar o historico.
Novo estado POPUP_SOZINHO3: a confirmacao "A instancia apresenta mais desafios" do Pericao em OUTRO desenho (frame POPUP_DICAS_PERICAO), que o detector
nao reconhecia (nota 0.85 < 0.873 do POPUP_SOZINHO antigo).

## Gato Preto: E uma vez so, B, item 2 (31/10)
- Gravacao do bot: icone verde do buff nunca detectado -> B nunca saia e o E era apertado todo turno.
- Novo `leitura.e_disponivel` (slot E da barra de itens verde = disponivel). O E e apertado so quando aceso e so 1x por luta (`pet_ok`);
  o B passa a valer depois do E usado (nao depende mais do icone do buff). Item 2 (combo "2,3,4") de volta; depois do B nao se aperta o 2.
