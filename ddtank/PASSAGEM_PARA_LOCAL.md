# DDTank Bot - passagem para a sessao LOCAL (31/10/2026)

Leia este arquivo primeiro, depois `DOCUMENTACAO.md` (arquitetura e combinados) e `NOTAS.md` (historico tecnico).
Repo `samuelccouto/estudos-de-bots-para-grind-games`, branch `claude/wonderful-rubin-3oyqi3`, pasta local `D:\estudos-de-bots-para-grind-games\ddtank`.
Pasta `social_empires/` na raiz: manter (estudo futuro, nao mexer). Historico do git foi limpo (gravacoes antigas removidas).

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
