# Guia de passagem (sessao local de 01-02/11) - LEIA ANTES DE QUALQUER COISA

Escrito para o proximo chat comecar sem o contexto do anterior. O usuario fala portugues e quer explicacoes simples. Regras do projeto estao no
`../CLAUDE.md` (so a branch `claude/wonderful-rubin-3oyqi3`, sem PR, rodar todos os `python testes/test_*.py` antes de commitar, nao inventar
coordenadas/telas: pedir gravacao). Contexto geral: `DOCUMENTACAO.md` e `NOTAS.md` (a secao "PVP - estudo de 01/11" resume o que esta aqui).

**Estado do git:** tudo commitado e enviado (`git push origin claude/wonderful-rubin-3oyqi3`), ultimo commit `8dc6320` + este guia.
Sem PR. `dados/aprendizado.json.bak_antes_da_limpeza`, `dados/drops_vistos/`, `dados/pvp_*` e `sessoes/` sao dados locais (nao commitados).

## 0. Como trabalhar (o que funcionou nesta sessao)
- **Olhar a tela, nao so o log.** Bot em segundo plano (`python navegador.py ...` ou `python pvp.py`, saida em arquivo), um `Monitor` filtrando linhas
  uteis e uma captura em loop (`estudos/caploop.py <pasta>`: salva um jpg a cada 0,6 s, guarda os ultimos 2500; use SEM o bot rodando quando for
  medir tempos, pois as duas capturas da janela competem). Depois monte montagens com cv2 e leia as imagens.
- Cada correcao deve ter um criterio medido (acertou / tempo da volta), nao impressao. O usuario se frustrou com ciclos de "tentativa e correcao" sem resultado.
- Nao ligue o bot as cegas em mapas em que ele atira "no padrao" (sem posicao): so gasta partida.
- Nunca rode software de terceiros nao verificado (o aimbot do DDTank foi recusado de proposito). `ddtcurve` (PyPI) foi so LIDO (fisica abaixo).
- O disco C: do usuario encheu uma vez (outro download dele). Os arquivos temporarios da sessao ficam em `%TEMP%\claude\...\scratchpad`.
- Antes de ligar o PVP, confirme que NAO ha outro bot rodando (`pvp.py` e `navegador.py` usam trava de instancia unica); o painel (`painel.py`) pode ter ligado um.

## 1. Rota Leste (Ultima Luta fase 1/2 + Devoradores) - PRATICAMENTE PRONTA
Resultado medido ao vivo: volta completa ~7-8 min sem derrota (antes 11 min com derrota); fase 1 ~33 s, Devoradores ~48 s (instancia 1min20),
fase 2 2,5-5 min. Mudancas feitas (todas em `atirador.py`, `estrategias.py`, `memoria.py`, `navegador.py`, `leitura.py`):
- vigia de imagem parada (janela escondida deixava o bot cego 300 rodadas); espera depois de andar; fim do "PASS piscando = turno novo" (gap 2,5 s);
- fase 2: boss de ELITE invocado fica com a hitbox em cima do boneco -> `fugir_do_elite` (ponto vermelho no minimapa a <=7 px do azul); ponto de tiro
  x~21 (`atravessar_para_x`); tolerancia de angulo 1,5; itens pulados se o turno ja gastou >3,2 s;
- nascendo a DIREITA: `espelhar` atira do ponto x~83 (espelho de 21 em volta do boss em x~52) com a mesma mira; 2 falhas -> volta a atravessar.
  **NAO foi testado ao vivo** (o jogo estava em outra luta quando religuei). Primeira coisa a validar quando o jogo voltar a rota Leste.
- **Leitura do angulo pelos DIGITOS do mostrador** (`leitura.angulo_digitos` / `angulo_preciso`, templates/angulo_digitos.npz): o ponteiro errava 2-3 graus
  e o bot oscilava (75->69->70->67). Faltam amostras dos digitos 0, 3, 8 (ai cai no ponteiro). Desvio digitos-ponteiro medio 2 graus (`DESVIO_DIGITOS`).
- Derrotas restantes: dano alto do boss (martelo) entrando rapido; o bot NAO le a propria vida ainda (ideia: ler e usar item de cura).
Comando: `python navegador.py --atirar --rota L --cartas TODAS --chefe n [--comecar-em 2]` (`--fase`).

## 2. PVP - NAO ACERTA AINDA (0 acertos confirmados do bot em ~30 tiros). O que se sabe
### 2.1 Como o jogo avisa o resultado (o mais valioso)
- Texto "O poder nao e suficiente, tente aumentar o seu poder" = tiro CURTO (`templates/msg_poder_curto.png`, `pvp.msg_poder_curto`).
- Texto "Voce atirou em uma direcao errada, tente ajusta-la antes de disparar novamente" = explodiu colado em nos (obstaculo na frente; no mapa do carro
  tirou 17 mil da nossa vida) -> subir o angulo 10 graus (`templates/msg_direcao_errada.png`, `pvp.msg_direcao_errada`).
- Texto "Nao tem forca fisica suficiente" = **mana/energia do turno acabou** ao tentar usar item (esclarecido pelo usuario). A barra de MANA e a verde,
  no canto inferior direito, em cima da barra vermelha de vida. O bot ja checa a energia dos itens (`itens: nenhum (sem stamina?)`); revisar se usa
  itens demais por turno (reduzi `ORDENS_PVP` para [2,3,4,4] / [1,3,4,4]).
- Ainda NAO visto: aviso de tiro LONGO. Ainda sem sinal de "passou do alvo".
- **Acerto = numero de dano na tela** (ex.: 11116, 16105, 16606, 11946 nos acertos do usuario). Melhor sinal que a barra de vida do inimigo (a barra de ~22-27 px
  mal mexe). Hoje o PVP usa a barra do inimigo (`INIMIGO_BARRA`, `QUEDA_BARRA_PX=3`) e nunca registrou acerto; **ligar `leitura.numeros_de_dano` ao PVP**
  (em `LeitorPvp.numeros_dano` esta zerado de proposito) e validar com os quadros da gravacao manual.
### 2.2 Escala do mapa (px de minimapa por unidade da regua 0-10)
- A regua 0-10 embaixo do jogo e a mesma das tabelas EstAng. Tela inteira = ~10,17 unidades (65,7 px da tela principal por unidade).
- O retangulo azul do minimapa = area visivel da tela -> largura/10,17 = escala do mapa. Medido: 92-93 px (mapa da noite/torre) = 9,0 px/un;
  60-61 px (ilhas flutuantes) = 6,0 px/un; o padrao antigo 4,0 estava errado por >2x. Implementado: `pvp.largura_caixa_minimapa` + `MemoriaPvp.medir_escala`
  (fixa com 2 leituras iguais +-3 px, grava em `dados/pvp_mapas/indice.json` campo escala/escala_ok). **Nunca foi visto funcionando ao vivo**; nos quadros da
  gravacao manual nova ele NAO achou o retangulo (None) - verificar os limites de cor/regiao (`CAIXA_MINI`) nesse layout.
- Sem acerto confirmado nao ha como validar a escala: a busca por erro (`PASSO_CURTO=0,88` mais forca; `PASSO_OUTRO=1,07`) so roda com tiro que teve posicao.
### 2.3 Posicao dos bonecos (maior problema aberto)
- O minimapa perde o ponto AZUL (nosso) em mapas de ilhas/verdes/noite -> `voce None` -> o bot atira "no padrao" (30 graus/50%), que erra por definicao.
  O ponto VERMELHO (inimigo) e lido bem. Ideia testada: nosso ponto = dentro do retangulo azul (a camera segue o nosso boneco) - achou so 1 de ~14 quadros.
- Medicao direta na tela principal (`pvp.posicoes_na_tela`: barra de vida AZUL nossa / VERMELHA do inimigo sob cada boneco, x,y em px) funciona, mas o inimigo
  raramente aparece junto com a gente na tela. Quando aparece, distancia = |dx|/65,7 unidades (ja integrado, `MemoriaPvp.tela_pos`).
- Sugestao: calibrar a razao tela<->minimapa nos turnos em que os dois aparecem na tela (escala = dx_minimapa / (dx_tela/65,7)), guardar por mapa.
### 2.4 Mecanica de tiro corrigida
- Carga da forca: a barra mostra o valor do tiro ANTERIOR parado -> o bot so soltava no fallback e saia 99% (queria 57%). Corrigido: solta quando a barra
  SOBE >=3 acima do minimo visto (`atirador.carregar`). Leitor `leitura.forca` agora le tambem barra vermelha/rosa (fundo claro, forca baixa); antes lia 0%.
- Ainda ocorre: turno iniciado com o contador em 0 (o hold de vez `HOLD_VEZ_S/JANELA_VEZ_S` acha que e a nossa vez depois que acabou) -> tiro "forca 0%".
- **BUG DO PERICAO ("fica alterando a mira eternamente e nunca ataca") - CORRIGIDO em 02/11 (nao visto ao vivo).** Causa: `estrategias.PERICAO`
  tinha `tolerancia_angulo` 1.0, menor que o menor toque da seta (~1,4); `ajustar_angulo` ia-e-voltava 12x e PULAVA o tiro. Agora 1,5, e
  `ajustar_angulo` aceita passar do alvo por <= `MENOR_TOQUE_ANGULO` (2) apos inverter o sinal. Teste: `test_atirador` (23b). Validar ao vivo no Pericao.
- **Numero de dano no PVP (02/11, tentado e NAO resolvido):** o acerto normal tem digitos ~12 px (dourado, contorno escuro); o critico ~20 px com estrela
  vermelha atras. Filtro so por cor + fileira de 4+ componentes NAO separa acerto de erro (fogo/faiscas da explosao e icones "50%"/relogio da HUD dao
  falsos positivos; 3 variantes testadas nos 11 tiros da gravacao manual). Caminho certo: casar templates dos digitos 0-9 (como `angulo_digitos.npz`),
  usando os numeros 13835, 13136, 16606, 16105... da gravacao como amostra; ou olhar a barra de vida do inimigo na tela principal.
### 2.5 Dados do usuario (gravacao `sessoes/20261101_235520_pvp_manual_intuicao`, F9 marca)
- 11 tiros em 4 mapas; 4 acertaram: #2 (64 graus, hold 1,42 s), #5 (46 graus, hold 1,28 s), #7 (52, 0,62 s), #8 (52, 0,77 s). Extracao: `estudos/analisa_manual.py`.
- Os holds nao batem com a forca lida (barra parada do tiro anterior) -> para ler a forca real use a barra DEPOIS de soltar so quando ela estiver estavel
  (ou o `trace` do bot). O usuario nao calcula nada: chuta ate achar angulo e forca (1-3 tiros por mapa).
- O usuario vai gravar varias partidas de PVP seguidas quando acabar o evento do Pericao (00h, boss global do servidor). Com isso: (1) rodar
  `python estudos/analisa_manual.py <pasta>/`; (2) rotular acertos pelo numero de dano; (3) ajustar escala por mapa pelo retangulo; (4) testar o modelo.

### 2.6 Gravacao longa de PVP do usuario (02/11, `20261102_111214`, 18 min, 26 tiros; quadros dos tiros 21-26 vieram corrompidos)
- Estudo dos 20 tiros legiveis (`estudos/analisa_manual.py` + `vento.ler_vento`): o usuario **trava o angulo e so varia a forca**: 52 graus (7x), 58 graus (7x),
  54-57 (5x); segura o espaco ~2 s (1,8-2,4 s) na maioria. So 2-3 tiros diferentes (22 graus/0,43 s, 71 graus, 61-64 graus/1,3 s, 0,42 s = tiros curtos).
- Vento nos tiros: -2,2 a +3,4 (a maioria 0,2-1,7); mesmo mapa da selva/halloween em quase toda a gravacao (distancia parecida) -> bom conjunto para
  calibrar UM mapa. A barra de forca depois de soltar le 53-66% nos tiros de ~2 s.
- Ainda falta rotular acerto/erro de cada tiro: nos quadros o acerto aparece como explosao laranja + numero amarelo (ex.: 9171) perto do inimigo; erro = brilho
  ciano/faisca no cenario sem numero. Sem template de digito nao da para automatizar. **Pedido para a proxima gravacao: aperte F9 NA HORA do acerto (e nao no erro).**
- Mudanca de 02/11: Profundezas esta em manutencao -> `navegador.EM_MANUTENCAO` tira da Rota Norte/T/Super Rota (a Super Rota agora e Fantasma > Minhocao > Sul > Leste;
  `FIM_ROTA_CUPOM` e calculado pelo tamanho das rotas). Para voltar, esvazie `EM_MANUTENCAO`.

### 2.7 Fase 2 da Ultima Luta - decisao do usuario (02/11): sem atravessar, sem tentativa e erro
- Regra de atravessar para a esquerda REMOVIDA da fase 2 (`"atravessar": False`, `"espelho_sempre": True`): nasceu a direita, atira de la (ponto espelhado x~83) com a conta
  (fisica + vento); nao volta a atravessar depois de 2 erros. A conta ja difere do lado esquerdo (62% x 51% para o mesmo dx).
- Os erros de 02/11 eram de EXECUCAO, nao de formula: (1) `passada_angulo` (aceitar passar do alvo ate 2 graus, feito para o Pericao) valia para todas as lutas e
  deixou a fase 2 mirar 72 em vez de 74 -> agora so o Pericao (`"passada_angulo": 2.0`); (2) a forca passava 16-25% do alvo porque o teto da antecipacao era 12% -> `ANTECIPACAO_MAX` 40.
- Dados 01/11: do lado direito o bot nunca acertou (0/12); do esquerdo acertava 118/169. **Nao validado ao vivo; aguardando gravacao do usuario.**

## 3. Fisica (ddtcurve 0.2.1, PyPI, so lido)
`ddtc.predict(angulo, vento, dx, dy)`: arrasto linear r=0.90289815, vento w=6.33592869, gravidade g=-184.11666458, dx/dy em "telas"; 100% = forca maxima.
Reproduz os acertos da rota Leste com UMA escala por mapa (erro medio ~2 pontos de forca): `estudos/fit_ddtcurve.py`. O PVP usa as TABELAS do jogo
(`forca_tabela`, `A_TAB/C_TAB`) + escala; considerar trocar pelo modelo do ddtcurve (inclui vento, que o PVP le em `vento.py` mas nao usa na forca).

## 4. Sistema de VITALIDADE (a implementar; so especificado)
Regras (usuario, 01/11): cada INSTANCIA GANHA consome 10 de vitalidade (perder nao desconta); cada PVP (vitoria) recupera 15; maximo 300. Nao ha barra:
aparece o texto "Voce perdeu: 10 de vitalidade. Te restam 290. Jogue PvP para ganhar mais vitalidade." no meio da tela quando desce a tela de vitoria da
instancia. Plano: ler "Te restam N" (OCR leve, ex. `rapidocr-onnxruntime`, ou templates dos digitos como o angulo); rota Leste enquanto N > 0;
com N = 0 jogar PVP ate N = 300 (100%); precisa de PVP que ganhe (mais um motivo para o PVP acertar).

## 5. Outros pendentes
- Instancia "O Mago" (parecida com Gato Preto): habilidades aleatorias (debuff em que so valem perks Z/X/C/R ou E; reflexo de dano: critico nos mata;
  turno do boss mostra a skill). Precisa gravacao do usuario. Visto: "Refletido: 100000 / Total: 100000", "Rodadas 12/200".
- Fase 2 Leste: ler a propria vida e curar; rotulos dos digitos 0/3/8 do angulo.
- `estudos/caixa_minimapa.py` e `pvp.largura_caixa_minimapa` precisam ser revalidados com quadros novos.

## 6. Mapa rapido de arquivos
`pvp.py` (AtiradorPvp, MemoriaPvp, LeitorPvp, CatalogoMapas, Laco) | `atirador.py` (turno, ajustar_angulo, carregar, aplicar_itens) | `memoria.py` |
`estrategias.py` (regras por instancia) | `leitura.py` (leituras da tela) | `navegador.py` (maquina de estados da rota) | `vento.py` |
`templates/` (msg_*.png, angulo_digitos.npz, estados.json...) | `dados/pvp_mapas/indice.json` (mapas + escala) | `estudos/` (scripts de analise) |
`testes/test_*.py` (13 testes, todos passam) | `PVP.bat`, `GRAVAR_SESSAO.bat` (gravador manual: F9 marca, F10 termina).
