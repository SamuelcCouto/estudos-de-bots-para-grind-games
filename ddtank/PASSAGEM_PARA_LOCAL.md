# DDTank Bot - passagem para a sessao LOCAL (atualizado 31/10/2026, apos a analise das gravacoes)

Leia este arquivo primeiro, depois `DOCUMENTACAO.md` (arquitetura e combinados) e `NOTAS.md` (historico tecnico).
Repo `samuelccouto/estudos-de-bots-para-grind-games`, branch `claude/wonderful-rubin-3oyqi3`, pasta local `D:\estudos-de-bots-para-grind-games\ddtank`.
Pasta `social_empires/` na raiz: manter (estudo futuro, nao mexer). Historico do git foi limpo (gravacoes antigas removidas).

## 0. ATUALIZACAO (31/10, sessao em nuvem) - leia antes do resto
**Feito hoje (commits ate 298694b):**
- Gato Preto: E 1x (slot E verde `leitura.e_disponivel`), B apos o E, item 2 de volta (combo 2,3,4). Confirmado nas gravacoes: E 1x, B 3x, item 2 usado.
- Super Rota: Norte+Sul rodaram perfeitos (~3 min cada; 90k cupons em 6min28s).
- Devoradores (Rota Leste) nunca abria: clique na seta da lista rola so alguns pixels e `pagina_da_lista` devolvia None no meio da rolagem
  (bot clicava no Dragao Gelado para sempre). Fix em `navegador.preparar_pagina` (`PAGINA_MAX_CLIQUES`). NAO testado no jogo.
- Ultima Luta fase 2: boneco nasce em x~13 (acerta), x~27 (errava 25x o mesmo tiro) ou x~78 (do outro lado do boss; derrotas por morte do boneco).
  Fix: boss com 100% que nao cai 2x = erro; `erro_apos_sem_queda: 3` na estrategia da fase 2. NAO testado no jogo.
- Pasta `social_empires/` fica (estudo futuro).

**O usuario esta testando as rotas no local agora** e vai mandar logs/gravacoes (Rota Leste, Devoradores, fase 2).

**PvP (prioridade nova):** ideia = bot "jogador perfeito" que calcula tudo (o usuario nao calcula; as gravacoes manuais tem varios erros).
- Gravacoes manuais em `envio/`: `20261031_011716` (14 min), `20261031_020551` (10 min) e `20261031_011707` (pequena). So vi por cima (mapas
  variados, VS "Combate Livre", mensagem "Nao tem forca fisica suficiente"). Analise de tiros, vento e posicoes ainda NAO feita; manter os zips ate analisar.
- A pagina do jogo tem nas laterais tabelas **"EstrAng 30/50/65/80"** (distancia x forca, distancia 1..20): ex. 30 graus: dist1=14, 2=20, 3=24, 4=28, 5=32,
  6=35, 7=38, 8=41, 9=44, 10=47, 11=50, 12=52, 13=55, 14=57, 15=60, 16=62, 17=65, 18=67, 19=69, 20=72; 50 graus: 14,20,24,28,32,35,39,42,44,48 (1-10),
  50,53,55,58,60,63,65,68,70,72 (11-20). (A tabela direita nao foi lida; os de 65 e 80 tambem nao.) Servem de semente para o modelo de fisica.
- Plano: modelo de fisica unico (gravidade, escala da forca, efeito do vento) + correcao a cada tiro; ler vento, posicao dos dois bonecos e angulo na tela.
  Confirmar que a gravacao salva o vento de cada tiro.

**VIDEOS DE CALCULO (estudar na sessao LOCAL; a nuvem nao acessa o YouTube - `www.youtube.com` bloqueado pela rede do ambiente):**
1. https://www.youtube.com/watch?v=FdiKX0I-QBI
2. https://www.youtube.com/watch?v=abftaNKei1s
3. https://www.youtube.com/watch?v=Y8rP5YC0hDs
4. https://www.youtube.com/watch?v=U-kf1nhN-zo
5. https://www.youtube.com/watch?v=S1vYDCy2MFA
Eu so leio TEXTO (titulo/descricao/legenda), nao vejo imagem nem escuto audio. Pedir ao usuario para colar a transcricao de cada video
(YouTube: "...mais" > "Mostrar transcricao") ou liberar youtube.com na rede do ambiente. Depois: extrair formulas/tabelas/regras de vento e comparar com o que o bot medir.

## 0b. PVP v1 (31/10, sessao local) - leia antes do resto
- **`PVP.bat`** (`pvp.py`): o bot joga e GRAVA as tentativas (~60 min, `--minutos`); F10 / PARAR do painel param. Deixar o jogo na sala do PVP; na sala clica
  Inicio (`--sem-inicio` desliga); pop-up "Clique no jogo" -> clique neutro. Usa o mesmo `Atirador` (so mira + forca, SEM itens, `LeitorPvp`: vida 100 fixa).
  NAO aprende (sem barra de vida de boss no PVP nao ha resultado do tiro): so grava; o resultado se confere nos prints do voo.
  Grava por tiro: evento `pvp_tiro` em `sessoes/<...>_pvp/eventos.jsonl` (angulo, forca, vento, azul/inimigo no minimapa, prints turno/voo/pos_tiro;
  `empacotar.py` manda todos) e a linha em `dados/pvp_tentativas.jsonl` (so local). Evento `partida` por partida.
- **`vento.py`**: le o painel "Forca Vento" (seta + "N.d"; o "0.0" rosa so contorno entre rodadas = None). kNN em `templates/vento_amostras.npz`
  (330 recortes rotulados a mao das gravacoes 011716/020551). Medido deixando cada trecho de vento de fora: 71% do vento inteiro, direcao 99%, 1o
  digito 99%, 2o digito ~78% (6/8 se confundem). Leituras duvidosas -> `dados/pvp_vento_duvidoso/*.png` (rotular e `vento.adicionar_amostra`).
- **Regras dos 5 videos**: `PVP_REGRAS_VIDEOS.md` (full: forca 95 e angulo = 90 - dist; semi full: 90 - 2*dist e forca ~60-64; vento 0.5 = 1 grau;
  sobra do vento vai na forca). Conferidas contra as tabelas EstrAng (20/30/50/65 graus, `testes/test_pvp_tabelas.py`).
- **Ainda NAO feito**: usar vento/distancia em unidades na decisao do tiro (v1 usa a fisica do `Memoria`, R=prior); detectar a caixa do minimapa
  (= 10 unidades; cor muda por mapa: verde/vermelha/azul; as primeiras tentativas de deteccao por cor falharam); fluxo Salao de jogos -> criar sala.
  Entrada vista na gravacao 020551: Mapa -> Salao de jogos -> Procura/Criar sala (clique ~(773,489) em 1280) -> sala "Combate Livre" -> Inicio (934,473).
- **PVP v1.1 (31/10 ~05h)**: itens 1-8 (ordem por turno alternando 2 e 1, so os com energia), **E** (protege o terreno; so com o slot verde, `leitura.e_disponivel`; o icone de buff do
  pet fica sempre "ligado" no PVP e nao serve), **F** (aviao: usado quando o chao cede (y do boneco +8 no minimapa), o angulo bate no limite da arma ou o inimigo esta a >58 px; ate 4/partida,
  1 a cada 3 tiros). Forca agora pelas **tabelas EstrAng** (`pvp.forca_tabela`, ajuste nas 4 tabelas; escala padrao 4 px/unidade, editavel por mapa em `dados/pvp_mapas/indice.json` campo "escala").
  A vez tem **histerese de 1,5 s** (a nota do PASS cai a 0.45 no voo do tiro: antes o bot achava que era outro turno e atirava 2x). Angulos em rodizio 45-75 (mapa m003 tem uma cabana no meio:
  tiros baixos batem no cenario, quebram o terreno e o boneco afunda).
- **Proximo passo**: o usuario roda `PVP.bat` por ~1 h (so ha bots fracos de madrugada) e envia; eu rotulo acertos pelos prints do voo, calibro vento/distancia
  e transformo os acertos em sementes (`tiros_semente.json`, instancia "PVP").

## 1. Estado atual (funciona / ja feito)
- Bot automatico (PrintWindow + PostMessage), painel tkinter (`BotDDT.bat` = git pull + painel), versao desenvolvedor e versao amigos (so aba Relatorio).
- Rotas: Sul (S), Norte (N, fora do menu), Leste (L) e Super Rota (U), Norte+Sul (T), Chefes (um chefe repetido), Pericao comum (P), Chefao Global (12h-13h e 21h-22h).
- Calibracao de tela (`tela.py`), deteccao de telas por patches, memoria de tiros por instancia, combos, relatorio de cupons/min, tarefas.
- Gato Preto (31/10): E so 1x (slot E verde via `leitura.e_disponivel`), B depois do E (nao depende do icone do buff), item 2 de volta (combo 2,3,4).
- Limpeza feita (LIMPAR.bat); `dados/` do usuario (aprendizado.json etc.) fica local e nao vai ao git.

## 2. Pendencias (ordem sugerida)
1. **Testar o Gato Preto de novo** apos o fix e enviar gravacao: conferir E 1x, B saindo, item 2 sem bater no chao (se bater: subir angulo minimo so quando usar o 2 e recalcular a forca com `mem.forca_para`).
   Duvida aberta: nas gravacoes do bot o canhao do pet nao apareceu mesmo apos apertar E - confirmar se o E realmente ativa.
2. **Rota Leste e Super Rota**: implementadas e testadas so em simuladores; nunca rodaram no jogo. Rodar, mandar logs, corrigir.
   (Leste = Ultima Luta fase 1 e 2 + Devoradores; fase 2: alvo = boss verde na plataforma, reposicionar quando o boss pequeno sobrepoe.)
3. **BotDDT.exe** (`BUILD_EXE.bat`, PyInstaller): nunca gerado. Gerar no Windows, testar a versao amigos (`amigo.flag`) numa janela real e em outra maquina.
4. **Adaptar a outras maquinas**: calibracao existe, validada so com janelas sinteticas; testar em outro PC/resolucao.
5. **Cupons por minuto**: comparar rotas com dados reais (metas informadas: N 40000, S 50000, L 60000 por rota); decidir a melhor.
6. **Chefao Global / Pericao comum**: validar com logs reais.
7. **PVP (novo, nao iniciado)**: bot que aprende sozinho. Plano: modelo de fisica unico para todos os mapas (gravidade, escala da forca,
   efeito do vento) com correcao a cada tiro; entradas = distancia, altura, vento, angulo. Antes: confirmar que a gravacao salva o vento de cada tiro;
   o usuario grava ~20-30 tiros com vento variado (zero, fraco, forte, a favor/contra), tiros em campo vazio (treino), alguns mapas e partidas completas.
   Depois: ler posicao dos dois bonecos e o vento na tela, tratar inimigo que se move.
8. Instancias especiais (mesma formula das outras) - depois.

## 3. Como retomar no local (checklist)
1. `git status` na branch certa; `git pull`.
2. `cd ddtank` e rodar todos: `python testes/test_*.py` (todos devem passar).
3. `dir dados` deve ter aprendizado.json, combos.json, tiros_semente.json, painel.json.
4. Abrir `BotDDT.bat`, rodar uma rota, enviar gravacao pelo painel ("Enviar gravacao"), analisar, depois `git rm` dos zips em `envio/`.

## 4. Combinados com o usuario
- Fala portugues; explicar de forma simples. Nao inventar coordenadas/telas: pedir gravacao (painel > "Gravar a MINHA jogada").
- Push so na branch `claude/wonderful-rubin-3oyqi3`; sem PR a menos que peca. Rodar todos os testes antes de commitar.
- Decisoes em vigor: Escorpiao aviao (F) desligado; cartas so dos chefes escolhidos; Pericao comum prioridade baixa;
  duas versoes de entrega (desenvolvedor e pessoal/amigos); automacao permitida pelo admin do servidor Betel.
