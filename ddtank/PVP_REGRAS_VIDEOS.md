# PVP - regras de calculo extraidas dos 5 videos (31/10/2026)
Fonte: legendas automaticas do YouTube (plugin `watch`); quadros NAO foram revistos. Conferido contra as tabelas EstrAng
(`testes/test_pvp_tabelas.py`). Angulo 90 = tiro reto para cima (ponto zero).

## Medir a distancia (d)
- Minimapa: o quadrado branco transparente tem **10 unidades** de ponta a ponta; a regua azul de baixo vai de 0 a 10.
  Pontas do quadrado em cima de um boneco, ler onde o outro cai. Acima de 10: somar quadrados (ex.: 10 + 5 = 15).
- Sem metodo exato alem de 10-15 (so experiencia).

## Full (arma que vai ate 90 graus)  - videos 1, 2, 4, 5
- Forca **95** (video 4: "90/100 e o ponto zero"; 95 na pratica). Angulo = **90 - d**.
- Alvo mais baixo que voce (relevo): forca um pouco menor (92); mais alto: um pouco maior.

## Semi full - video 3 (Strik)
- Angulo = **90 - 2*d**, forca **60 a 64** (so isso). Ex.: d=7 -> 76 graus; d=10 -> 70 graus. Vale "ate certo ponto".
- A fisica das tabelas da forca ~57-61 para esses angulos (coerente).

## Vento (todos os videos concordam)
- **0.5 de vento = 1 grau**; 1.0 = 2 graus. Contra (seta para voce) -> **abaixa** o angulo; a favor -> **sobe**.
- Sobra menor que 0.5 vai na forca (video 1): 1.7 contra = -3 graus e +2 de forca (97); 3.2 = -6 graus, forca 97; 3.0 = -6 graus, 95.
  (Video 2 faz o inverso na excecao: vento 2.0 "nao certinho" -> baixou forca 95 -> 92.)
- Angulos baixos (65 e 70 graus, tabelas): vento pesa menos; no 65 o video 5 nao desconta; no 70 sobe 2 por 1.2 a favor.

## Tabelas do jogo (laterais da tela)
EstrAng 20/30/50/65/70 (distancia x forca). Ex.: 65 graus, d=5 -> forca 37; 70 graus, d=5 -> 43.

## Falta validar com dados reais (gravar tiros com vento)
- Regra do vento (2 graus/1.0) e sobra para a forca; efeito do relevo; semi full na pratica; escala d (minimapa) -> d (regua).
