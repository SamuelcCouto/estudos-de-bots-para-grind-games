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
- Escorpiao Rei: REMOVER o aviao (F). Falta pouco upgrade para ele morrer no 1o turno do bot (antes do turno dele);
  quando o usuario avisar, tirar ESCORPIAO_REI de estrategias.ESTRATEGIAS (ou desligar o aviao la).

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
Duvidas abertas: o que acontece na rodada 200 (derrota?) e no fim do horario com o chefao vivo; se o Pericao continua
entravel fora do horario ("modo global encerrado" sugere que vira instancia normal).
