# Estudo: como chegar a um bot de DDTank que acerta sempre (02/11)

**Resumo.** O bot atual adivinha a mira por tentativa e erro (tabelas, memoria de acertos, escala chutada do minimapa). Isso nunca chega
a 100%. Nesta sessao descobri que **a fisica do tiro do DDTank e uma formula fixa e conhecida**, tirada do codigo do proprio jogo, que
esta no seu computador, e confirmada no codigo publico do servidor. Com ela, o tiro deixa de ser chute e vira conta: sabendo onde voce
esta, onde o alvo esta e o vento, a forca certa sai exata. O trabalho agora e **ler essas tres coisas com precisao**, pela tela ou
pela rede do jogo.

Regras deste estudo (usuario, 02/11): pode usar ferramentas de terceiros. Usei so ferramentas de codigo aberto e de fontes oficiais.
O aimbot pronto (executavel fechado) continua de fora: nao e confiavel e deixou de ser necessario.

---

## 1. O que descobri (com prova)

### 1.1 O jogo e Flash rodando dentro de um Electron
- `D:\DDTBETEL\BetelTank.exe` e um app **Electron** (Chromium) que carrega o plugin **Pepper Flash 32.0.0.363**
  (`resources\plugins\64bit.dll`, processo `--type=ppapi`).
- O cliente guarda tudo o que baixa como "SharedObjects" do Flash em
  `%APPDATA%\BetelTank\Pepper Data\Shockwave Flash\WritableRoot\#SharedObjects\...\flash-55-prod.ddtankbetel.com\`.
  Ali estao **308 SWFs sem criptografia**. O nucleo do jogo (15 MB) fica disfarcado de `.png`.
- Descompilei o nucleo com o **JPEXS FFDec** (descompilador de Flash, codigo aberto, ja na versao 26.3.0) e obtive o codigo
  ActionScript de fisica, rede e jogo. `estudos/extrair_cliente.py` refaz tudo; a saida vai para `cliente_extraido/` (fora do git).

### 1.2 A fisica exata (cliente = servidor)
| Fonte | O que diz |
|---|---|
| `phy/math/EulerVector.as` | `a = (F - arrasto*v)/massa; v += a*dt; x += v*dt` (Euler semi-implicito) |
| `phy/object/Physics.as` | `F_y = gravidade_mapa * fator_gravidade_bala * massa`; `F_x = vento * fator_vento_bala`; `arrasto = arrasto_mapa * arrasto_bala` |
| `game/view/RouteComputer.as` (existe no cliente Betel!) | o proprio cliente simula a rota: passo **0,04 s**, bala padrao massa 10, gravidade 70, vento 240, arrasto 1, `v0 = forca*(cos, sin)` |
| `game/view/EnergyView.as` | a barra de forca sobe **20 unidades por quadro**, maximo **2000** (1% = 1 quadro) |
| `game/model/LocalPlayer.calcBombAngle` | angulo enviado = **inclinacao do boneco no terreno** -/+ angulo do mostrador (explica o "limite que muda com o chao") |
| `GameInSocketOut.sendGameCMDShoot(x, y, forca, angulo)` | o tiro e so isso: ponto de saida, forca 0-2000, angulo |
| servidor publico DDTank 4.1 (`github.com/pnkl1999/DDTank41`, `Game.Logic/Living.cs ShootImp`, `SimpleBomb.cs`) | `vx = int(forca*cos)`, `vy = int(forca*sin)`, passo 0,04 s; tiro triplo: 2o projetil 0,9x e -5 graus, 3o 1,1x e +5 graus |
| `balllist.xml` / `loadmapsitems.xml` (os mesmos XMLs que o cliente baixa) | **1906 de 1910 balas**: massa 10, gravidade 70, vento 240, arrasto 1. **538 de 540 mapas**: gravidade 10, arrasto 2 |

Na pratica, quase todo tiro do jogo segue:
```
aceleracao_x = 24*vento - 0,2*vx        aceleracao_y = 700 - 0,2*vy        (px do mapa, y para baixo, dt = 0,04 s)
velocidade inicial = forca(0-2000) x (cos, sin) do angulo enviado
```
**Validacao (`testes/test_fisica_exata.py`).** Contra as tabelas oficiais "EstAng" (20/30/50/65 graus) do site, a formula da
**100 px do mapa por unidade da regua** (a 50 graus: 96 a 101 px), com o tiro saindo ~35 px acima do chao do alvo (a altura do cano).
O solucionador devolve a forca da tabela de 50 graus com erro maximo de 2 pontos, da distancia 5 a 20.

### 1.3 O que isso explica do bot atual
- **Escala do minimapa errada**: o bot usava 4 px por unidade em todo mapa. O minimapa e o mapa inteiro reduzido
  (`SmallMapView`: largura = largura_do_mapa x escala, maximo 240 px) e `loadmapsitems.xml` da a largura real de cada mapa
  (`ForegroundWidth`). A escala certa sai de uma conta, sem tiro de teste.
- **"Limite do angulo que muda"** e o angulo real diferente do mostrador: a inclinacao do terreno entra no angulo enviado.
- **Forca imprecisa**: a forca anda em degraus de 1 quadro. Segurar o espaco por tempo de relogio erra; o certo e contar quadros (ou ler a barra).
- A **memoria de acertos** so funcionava porque a rota Leste repete as mesmas posicoes; no PVP, que muda tudo, ela nao generaliza.

### 1.4 A rede do jogo (para ler o estado EXATO)
- O jogo conversa por TCP com `quest-55-sockets`/Cloudflare (porta 25565, do processo principal do Electron).
- Pacote: cabecalho de 20 bytes (`0x71AB`, tamanho, checksum, codigo, clientId, extend1, extend2) e cifra **XOR encadeada**.
  A chave inicial e fixa no codigo (`[174,191,86,120,171,205,239,241]`); no login o cliente sorteia uma chave de 8 bytes (enviada por RSA).
- **Fraqueza:** a chave evolui so com os bytes cifrados (`key = (key + c[i-1]) ^ i`). Descobrindo o estado uma vez, da para
  acompanhar a sessao inteira so olhando o trafego. O estado sai de texto conhecido (`0x71AB` no inicio e os campos
  clientId/extend, quase sempre zero). Ainda nao testei: precisa capturar pacotes (abaixo).
- O que o servidor manda, por exemplo, no resultado do tiro (`GameView.__shoot`): vento exato (inteiro / 10), e para cada projetil
  X, Y, VX, VY iniciais, id da bala e a **lista de eventos** (inclui o dano). Ha tambem pacotes de inicio de turno (vento,
  jogador da vez) e de movimento (posicoes). Lendo a rede, o bot sabe posicoes, vento e resultado **sem erro de imagem**.

### 1.5 RESULTADO da captura de rede (02/11, `CAPTURAR_REDE.bat`, 14 min de PVP do usuario)
- **A rede foi lida por completo.** Em ~2 s o `rede_ddt.py` recupera a chave de sessao SO pelo trafego cifrado: 1422 pacotes do
  servidor e 257 do cliente, 100% com checksum certo. Funciona com a captura comecando no meio da partida.
- **Os seus tiros, exatos** (pacote FIRE do cliente): ponto de saida (x, y) em px do mapa, forca 0-2000 e angulo. Exemplos:
  `(966, 445, 1080, -98)` e `(1420, 820, 780, -130)` sao tiros de costas.
- **A cada vez (pacote TURN): a posicao exata de TODOS os bonecos** (x, y em px do mapa), vida, energia, furia, tiros no turno,
  e o **vento** (o mesmo do tiro, conferido em 99 tiros).
- **Resultado de cada tiro (FIRE do servidor):** saida, velocidade inicial, ponto e instante da explosao e dano em cada alvo.
- **A fisica exata foi provada:** os 144 projeteis da captura explodiram a **no maximo 1,8 px** da trajetoria simulada (mediana 0,6 px).
  Sao 105 normais e 39 teleguiados (`estudos/valida_rede.py`).
- **Perk teleguiado (Z/X/C)** (servidor `SimpleBomb.StartMoving`): quando o projetil esta DESCENDO e passa a ate **150 px** de um
  inimigo, ele vai reto no inimigo (velocidade 1000, sem gravidade nem vento; evento `CHANGE_SPEED`). Com o perk, basta passar perto.
- **Evento "de costas"** (`EmperorOfPlayingBack`): conta quando voce ACERTA um jogador virado para a direita com |angulo| >= 91, ou
  virado para a esquerda com |angulo| <= 89. O angulo enviado = inclinacao do terreno -/+ mira, entao num chao inclinado a mira 85
  vira -93. O motor sabe planejar esses tiros (`fisica_exata.de_costas`).

**Consequencia:** com a leitura da rede, o bot tem **o estado exato** (posicoes, vento, vez) e **o resultado exato** de cada tiro, e a
fisica ja esta provada no proprio jogo. **Leitura AO VIVO (`rede_vivo.py`, 02/11):** sem instalar nada e sem administrador.
O jogo e aberto com o registro de rede do proprio Chromium (`--log-net-log ... --net-log-capture-mode=IncludeSocketBytes`) e o bot
le esse arquivo enquanto ele cresce. **Funcionou com o registro real de 2 PVPs (02/11):** 843 pacotes do servidor + 136 do cliente,
vez, posicoes, vento, cada tiro (inclusive teleguiado), dano e os tiros que NOS enviamos. (O Chromium 76 grava os bytes em base64 no
campo `bytes`.) O jogo reconecta as vezes: cada conexao nova recomeca a leitura sozinha.
Descartados: o socket bruto do Windows (nao ve a conexao IPv6 do jogo, testado ao vivo) e o WinDivert (o Defender bloqueia).
Cuidado: o registro grava os dados ja decifrados de todas as conexoes do launcher, inclusive o site. Fica so em `capturas_rede/`.

### 1.6 Terreno, inclinacao e ponto de saida (02/11 a noite, `terreno_jogo.py`)
- **Numero do mapa**: vem no pacote GAME_LOAD (sub 103: tempo maximo, mapa, ...). Os numeros sao os do `loadmapsitems.xml`
  (858xxx). O chao e `https://res20.ddtankbetel.com/image/map/<mapa>/fore.png` (e `dead.png` = pedra), baixado uma vez para
  `dados/mapas_jogo/`. Chao = alfa > 150 (Ground.IsEmpty).
- **Conferido**: no 1o turno de cada partida a posicao da rede fica exatamente na superficie do chao (1 px, 20 partidas). Bala
  simulada com o terreno: explode a 1-5 px do ponto do servidor no terreno intacto.
- **Buracos**: cada explosao com "buraco" cava um oval de largura = Radii da bala e altura 0,6 x Radii. Em 257 explosoes reais:
  78% a ate 5 px e 93% a ate 10 px do previsto (circulo de Radii/2: 32% / 40%).
- **Inclinacao** do boneco = conta do jogo (PhysicalObj.calcObjectAngle) sobre o terreno. **Ponto de saida** do tiro
  (GamePlayer.shootPoint) = pe + (0, -3) + gira(inclinacao, (+-30, -20)); o cliente corta as casas (int). Bate com o pacote.
- **Descoberta que muda a mira**: o PONTEIRO do mostrador (o que o bot le) ja mostra o angulo REAL do tiro (com a inclinacao).
  A inclinacao so muda o ponto de saida e a faixa da arma (ponteiro = arma - direcao x inclinacao: arma de minimo 13 num morro de
  63 graus olhando para a esquerda so chega a 76, o "limite 76" visto ao vivo). A "inclinacao" que o bot aprendia era o erro de
  leitura do ponteiro (0-2 graus), exceto quando o boneco estava virado ao contrario.
- **Direcao do boneco**: o lado do ponteiro engana (num morro, virado para a esquerda, o ponteiro fica a direita). A direcao certa
  vem da rede: DIRECTION (sub 7, int +1/-1) e MOVESTART do cliente (sub 9: tipo, x, y, direcao), que tambem da a posicao atual.
- **Forca**: a taxa de carga variou 27-40%/s (a barra sobe 1% por quadro; o quadro do Flash varia). O bot agora registra a barra
  durante a carga (`dados/pvp_barra_carga/`) e solta pela barra quando ela comprovadamente acompanha a carga.

---

## 2. A nova arquitetura proposta (o "motor exato")

```
 PERCEPCAO  ->  MODELO  ->  PLANEJADOR  ->  ACAO  ->  VERIFICACAO
```
1. **Percepcao (estado da partida).**
   Opcao A, pela tela, ja possivel:
   - id do mapa (miniatura da tela VS comparada com as imagens oficiais em `res20.ddtankbetel.com/image/map/<id>/`);
   - largura e altura do mapa (`loadmapsitems.xml`) e escala do minimapa pela conta;
   - posicoes pelos pontos do minimapa (precisao ~5-10 px do mapa, contra raio de explosao de 60);
   - vento pelos digitos (o valor mostrado E o exato);
   - angulo pelos digitos do mostrador (ja feito: `leitura.angulo_digitos`);
   - inclinacao do boneco pelo terreno (`fore.png` do mapa, mesma conta de `PhysicalObj.calcObjectAngle`).

   Opcao B, pela rede, exata: posicoes, vento, vez e resultado lidos dos pacotes, decifrados passivamente (so leitura, sem injetar nada).
2. **Modelo**: `fisica_exata.py` (feito) + terreno real (`fore.png`: pixel opaco = chao, `IsRectangleEmpty`) + retangulos dos bonecos.
3. **Planejador**: para cada angulo possivel (20-89), achar a forca que cai no alvo sem bater em obstaculo antes. Escolher o tiro
   com mais folga (centro do alvo, longe de paredes) e prever o tiro triplo e o vento. Isso substitui memoria, tabelas e busca de escala.
4. **Acao**: angulo pelos digitos (ja existe), forca por **quadros** (+20 por quadro), conferindo a barra na soltura.
5. **Verificacao**: o resultado pelo numero de dano na tela, ou pela lista de eventos do pacote (opcao B). Se o tiro previsto
   e o real divergirem, a percepcao esta errada (nao a fisica), e o bot sabe exatamente o que corrigir.

Isto vale **igual para PVP e instancias** (bosses usam a mesma fisica; muda so o alvo e as habilidades).

---

## 3. Ferramentas avaliadas

| Ferramenta | Para que | Situacao |
|---|---|---|
| **JPEXS FFDec** (GitHub oficial, Java) | descompilar o cliente Flash | **usado** (26.3.0; Java 8 ja instalado) |
| Emulador publico DDTank 4.1 (`pnkl1999/DDTank41`, C#) | conferir fisica do servidor, protocolo, **scripts das habilidades dos bosses** (Mago, Pericao) | **usado**; consultar de novo para as instancias |
| `balllist.xml`, `loadmapsitems.xml`, `bombconfig.xml`, `image/map/<id>/fore.png` | parametros da fisica, tamanho e terreno de cada mapa | **usado** (baixados como o cliente baixa) |
| Python + numpy (+ numba se precisar de velocidade) | simulador e planejador | **feito** em Python puro (ja e rapido o bastante) |
| OpenCV | leitura de tela (minimapa, digitos, mensagens) | continua |
| **pktmon** (ja vem no Windows) ou **Npcap + scapy** | capturar o trafego do jogo (opcao B) | **proximo passo**: precisa de um comando seu como administrador |
| Frida (hook de funcoes, codigo aberto) | alternativa a captura: ler os bytes direto no processo | reserva, se a captura nao servir |
| RapidOCR / Windows OCR (`winocr`) | textos: "Te restam N" (vitalidade), numero de dano, mensagens novas | recomendado para a vitalidade |
| `windows-capture` (Windows Graphics Capture) | captura mais rapida que PrintWindow e que funciona com a janela coberta | opcional |
| YOLO / redes neurais | achar bonecos na tela | **desnecessario**: a UI e fixa e a fisica e exata |
| Aprendizado por reforco | "aprender a jogar" | **desnecessario**: o tiro e um problema deterministico |
| Visao de LLM (API do Claude) | entender telas novas e inesperadas (fallback) | opcional, para robustez |
| Cheat Engine, editar o cliente, ativar a "linha pontilhada" (`dottelineEnable`, existe no cliente) | — | **fora**: mexe no jogo, maior risco de ban, e nao e necessario |
| Aimbot pronto (executavel fechado) | — | **fora**: sem codigo, risco de virus/roubo de conta, e agora inutil |

---

## 4. Plano com criterio de aceite em cada etapa

| Etapa | O que | Aceite (medido) |
|---|---|---|
| 0 ✅ | Fisica exata + dados do jogo (`fisica_exata.py`, `estudos/extrair_cliente.py`) | testes contra as tabelas oficiais passam |
| 0b ✅ | Rede decifrada (`rede_ddt.py`): chave, tiros, vez, posicoes, vento, resultado; fisica conferida em 144 projeteis | erro <= 1,8 px |
| 1 | **Replay**: aplicar o motor nas gravacoes que ja temos (rota Leste do bot, PVP do usuario) | a forca prevista bate com a dos acertos (+-2 pontos) |
| 2 | Percepcao pela tela v2: id do mapa, escala do minimapa pela largura real, posicoes, vento, inclinacao pelo `fore.png` | erro de posicao < 15 px do mapa em 50 quadros rotulados |
| 3 | Rede AO VIVO: leitor em tempo real (pydivert/Npcap, admin) alimentando o bot com o estado da vez | estado lido < 1 s apos o pacote TURN |
| 4 (PVP ligado, falta o teste ao vivo) | `mira_exata.py` + `pvp.py`: a vez da rede vira o plano (mira mais tolerante + forca exata); depois do tiro, saida/inclinacao exatas e o resultado do servidor. Abrir o jogo pelo `ABRIR_JOGO.bat` | >= 95% de acerto no 1o tiro em 50 tiros seguidos |
| 5 | Instancias com bosses (Pericao, Mago...) usando as regras dos scripts do servidor; vitalidade (Leste/PVP) | rodadas sem derrota |

**Sobre os "100%".** Com estado exato (rede) e a fisica do jogo, o tiro vira conta. O que ainda pode impedir um acerto:
- obstaculo que nao deixa nenhuma trajetoria passar (ai o certo e andar ou usar o aviao);
- habilidade aleatoria do boss (escudo, reflexo, invisibilidade);
- o alvo se mover entre a leitura e o tiro.
A meta realista e **acertar sempre que existir tiro possivel** e saber dizer quando nao existe.

**Riscos.** Bot e leitura do trafego violam as regras de quase todo servidor. O risco de ban existe mesmo sem alterar nada no
cliente. No PVP, o bot joga contra pessoas. A leitura passiva da rede e da tela nao altera o jogo, mas a decisao de usar e sua.

## 5. Arquivos desta etapa
- `fisica_exata.py`: simulador e solucionador exatos (sem dependencias); `testes/test_fisica_exata.py`: validacao com as tabelas.
- `estudos/extrair_cliente.py`: extrai os SWFs do cache, baixa os XMLs de dados e descompila (com `--ffdec`).
- `rede_ddt.py` (+ `testes/test_rede_ddt.py`): le o .pcapng, recupera a chave, decifra e interpreta tiros/vez/posicoes/vento.
- `estudos/valida_rede.py <captura.pcapng>`: confere a fisica contra as explosoes informadas pelo servidor.
- `CAPTURAR_REDE.bat`: captura so a porta do jogo (pede administrador sozinho); saida em `capturas_rede/` (fora do git).
- Locais, fora do git: `cliente_extraido/` (SWFs e codigo descompilado, ~150 MB) e `dados/jogo/` (XMLs).
- Codigo do cliente mais util para o proximo passo: `cliente_extraido/fonte/scripts/` em `phy/`, `game/view/RouteComputer.as`,
  `game/view/GameView.as` (`__shoot`), `game/actions/ChangePlayerAction.as` (vez/vento), `road7th/comm/` (cifra),
  `ddt/manager/GameInSocketOut.as` (pacotes enviados), `ddt/data/socket/CrazyTankPackageType.as` (codigos).
