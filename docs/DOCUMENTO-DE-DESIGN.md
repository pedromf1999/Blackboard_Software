# Blackboard — Documento de Design

Estado na versão **12.8** (outubro de 2026). Este documento descreve o que o
Blackboard faz, como cada coisa se comporta e porquê. Serve para continuar o
desenvolvimento noutro computador, e para o Claude perceber o programa antes
de lhe mexer.

---

## 1. O que é

O Blackboard é um quadro infinito para juntar referências de design: imagens,
notas, listas de tarefas, tabelas, desenhos e grupos, tudo num só ficheiro
`.blk`. É um fork pessoal do **BeeRef** (Python + PyQt6, licença GPL-3), feito
na branch `bvref` a partir da versão `0.3.4.dev0` do BeeRef.

Quem o usa é um designer de produto/industrial, que trabalha num quadro grande
(o BVR001: cerca de 550 elementos e 320 imagens, 135 MB) em dois computadores.

## 2. Princípios que atravessam tudo

1. **O quadro é a ferramenta; a interface flutua por cima.** As barras de
   botões aparecem junto ao que está escolhido e seguem-no; os painéis
   (camadas, legenda) recolhem-se para uma pega pequena.
2. **O que se mede no ecrã tem sempre o mesmo tamanho, em qualquer zoom.**
   Pegas, linhas da grelha, a distância de encaixe, os botões das notas
   afixadas.
3. **Nada se perde.** Um quadro gravado por uma versão mais nova abre sem
   apagar nada do que não percebe (aparece como elemento vermelho e é
   gravado como estava). Tudo o que se acrescenta ao ficheiro é aditivo: as
   versões antigas ignoram o que não conhecem.
4. **Desfazer é exato.** Cada ação volta exatamente ao estado anterior, incluindo
   encaixes, caixas de grupos e posições.
5. **Fluidez no quadro real.** O objetivo é 16 ms por frame (60 por segundo)
   no BVR001. Memória até 500–700 MB é aceitável.
6. **Mudar o comportamento só quando pedido.** Cada pedido é feito à parte,
   numerado, testado e mostrado antes de ser publicado.

## 3. Os elementos do quadro

### 3.1 Imagens
- Entram por arrastar, colar ou Ctrl+I; chegam com metade da janela de
  tamanho.
- **Recortar** (Shift+C), **contorno** com cor e espessura, **cinzento** (G),
  opacidade, virar (H / V), redimensionar pelos cantos (mantém a proporção) e
  esticar pelas arestas.
- **Descrição** (caption): faixa por baixo da imagem, com o texto a quebrar
  linha. Os links na descrição ficam sublinhados e abrem com Ctrl+clique.
  Abre-se com T ou duplo clique.
- Um esboço feito por cima de uma imagem fica preso a ela.
- **Memória:** as imagens ficam guardadas comprimidas, como estão no ficheiro,
  com uma cópia pequena (256 px) para desenhar enquanto não há melhor. São
  abertas ao tamanho a que são vistas, em segundo plano, e largadas 30 s
  depois de saírem de vista. Ver `beeref/imagecache.py`. **Nunca** entregar a
  imagem inteira ao `setPixmap` do Qt: foi isso que pôs um quadro de 126 MB a
  ocupar 5,3 GB.
- Formato de gravação: "Best Guess" (PNG para imagens pequenas ou com
  transparência, JPG para o resto), sempre PNG ou sempre JPG. O comando
  "Compact File" passa as imagens a JPG para encolher o ficheiro.

### 3.2 Notas (texto)
- Criar: T (ferramenta de texto) ou Ctrl+T. Começa-se logo a escrever.
- Texto rico (HTML): negrito (Ctrl+B), tamanho (Ctrl+= / Ctrl+-, por
  percentagem), cor das palavras, **destaque**, cor da caixa (o texto escolhe
  sozinho branco ou preto conforme o fundo), letra da interface ou Ranade.
- **Título:** faixa por cima da nota, com cor, alinhamento (esquerda/centro) e
  tamanho próprios. Duplo clique na faixa para escrever.
- **Links** sublinhados; Ctrl+clique abre no browser.
- **Largura:** arrastar o lado da nota faz o texto quebrar de novo.
- **Listas:** uma linha começada por "- " passa a lista.
- **Listas de tarefas** (Ctrl+Shift+T): cada linha tem uma caixa; riscar uma
  tarefa leva-a para a faixa de "concluídas", que se recolhe; as tarefas
  arrastam-se pela pega; o botão de números numera as linhas.
- **Tabelas** (Alt+T): cabeçalhos, juntar e separar células, arrastar
  divisórias; colar uma tabela do Excel, Word, Sheets ou Teams cria uma
  tabela.
- Uma nota escrita ou colada por cima de um grupo entra no grupo.

### 3.3 Desenhos
- Ferramentas: esboço à mão, linha, curva, seta, seta curva, e cinco formas
  (círculo, quadrado, triângulo, pentágono, hexágono — Shift para manter a
  proporção). Esc guarda a ferramenta.
- Cor e espessura na barra que aparece junto ao desenho escolhido.
- **Linhas presas:** a ponta de uma linha ou seta agarra-se a uma nota, grupo
  ou imagem, mostra onde vai prender enquanto se desenha, contorna a caixa em
  vez de a atravessar, e cada ponta arrasta-se sozinha.

### 3.4 Grupos
- Ctrl+G agrupa, Ctrl+Shift+G desagrupa. Caixa colorida com margem e cantos
  proporcionais ao conteúdo. Grupos dentro de grupos.
- **Título** opcional: com título, há uma faixa por cima, por onde o grupo se
  agarra. **Sem título** não há faixa: agarra-se pela aresta de cima (16 px no
  ecrã), onde o cursor mostra a mão. Duplo clique nessa aresta abre a faixa
  para escrever um título.
- O que está dentro escolhe-se e edita-se diretamente; o interior vazio é
  quadro (começa uma seleção por retângulo).
- **Trancar:** um grupo trancado é uma peça só.
- Arrastar um elemento para cima de um grupo põe-no lá dentro; Alt ao
  arrastar tira-o. Colar dentro de um grupo também.
- Cada grupo guarda quando foi criado e editado (aparece no painel de
  camadas).

## 4. Ver e navegar
- **Zoom** com a roda (invertido de origem), suavizado ao longo de alguns
  frames; Ctrl + botão do meio para zoom arrastado. 1 = ver tudo, 2 = ver a
  seleção.
- **Trackpad (Mac):** dois dedos deslocam o quadro, à distância que os dedos
  andaram e continuando a deslizar depois de os levantar; a pinça faz zoom
  no ponto debaixo dos dedos, de imediato (sem a suavização da roda). É como
  no Affinity e no Illustrator. A roda de um rato continua a fazer zoom, e
  no Windows nada muda: o programa distingue os dois pelas fases do gesto,
  que só um trackpad de Mac (ou um Magic Mouse) envia. Com Shift, os dois
  dedos fazem o que a roda faria.
- **SpaceMouse** (3Dconnexion) para deslocar e fazer zoom, com velocidade e
  inversão nas definições.
- **Grelha** de linhas ou de pontos, com espaçamento que acompanha o zoom
  (passa suavemente entre níveis). Cor, tamanho e estilo nas definições.
- Cor do quadro configurável. Ecrã inteiro (F11), sempre por cima, mover a
  janela (Ctrl+M), esconder menu e barra de título.
- **Ecrã de boas-vindas** com os quadros recentes; cartão de atalhos ao
  arrancar (F1 para voltar a ver).

## 5. Escolher, mover e redimensionar
- Clique escolhe; **Shift junta** à seleção; **Ctrl tira**. Ctrl+A escolhe
  tudo (um grupo conta por tudo o que tem dentro).
- Pegas: cantos redimensionam mantendo a proporção; arestas esticam (imagens)
  ou mudam a largura (notas); fora dos cantos roda (Shift ou Ctrl rodam aos
  saltos).
- Ordem: PgUp leva ao topo, PgDown ao fundo; escolher um elemento não o traz
  para cima.
- **Painel de camadas** (Ctrl+J): árvore com os grupos, arrastar para
  reordenar, mudar nomes, cores das entradas como as dos elementos.
- **Legenda** do quadro (Ctrl+L): cores com significado, que também aparecem
  no seletor de cor.
- **Encaixe entre elementos (Shift ao arrastar):** uma aresta a menos de
  10 px no ecrã da aresta de outro elemento encaixa e ficam a tocar; lado a
  lado alinha topos ou fundos, um por baixo do outro alinha esquerdas ou
  direitas. Uma linha fina mostra o encaixe. Conta-se a descrição das
  imagens e a faixa do título das notas.
- **Encaixe na grelha (Shift+G, botão na barra, View → Snap to Grid):** o que
  se move ou redimensiona cai nas linhas da grelha que se veem, por isso o
  passo segue o zoom (100 a 100 %, 25 a 300 %, 400 a 25 %, com o tamanho de
  grelha 100). Com Shift ao mesmo tempo, um elemento perto ganha.
- Arrumar imagens: Optimal / Horizontal / Vertical / Square, com intervalo
  configurável; igualar alturas, larguras ou tamanhos (Shift+H / W / S).

## 6. Notas afixadas (Pins)
- **Ctrl+P** afixa a nota à janela: fica sempre à vista, seja qual for o zoom
  ou o sítio do quadro. Ctrl+P de novo desafixa (volta ao quadro com o
  tamanho que tinha lá).
- Todas ficam num **separador "Pins"**, que se arrasta pelo cabeçalho e fica
  preso ao canto mais próximo da janela. O "–" (ou **Ctrl+Shift+P**) recolhe o
  separador.
- **Arrumação:** cada nota fica à esquerda do separador ou a 8 px à direita de
  outra, e sobe até ficar a 8 px da que está por cima. Nunca se sobrepõem; ao
  abrir, minimizar ou alargar uma, as encostadas acompanham. Largar uma nota
  em cima de outra troca-as; o separador mostra onde vai ficar.
- Cada nota **minimiza** para uma etiqueta com a cor do título.
- Os botões de minimizar e desafixar **aparecem ao passar o rato**, dentro da
  faixa do título (ou no canto, sem título).
- **Tamanho igual:** todas mostram o texto ao tamanho definido em Settings →
  Images & Items → "Pinned Note Text Size" (9 pt de origem); o título fica
  um pouco maior.
- A arrumação, a posição do separador e se está recolhido ficam gravados no
  quadro.

## 7. Pesquisar
- **Ctrl+F** abre a barra; **F3** / Find Next / Previous percorrem os
  resultados. Procura nas notas, nos títulos de notas e grupos e nas
  descrições das imagens.
- Cada resultado é escolhido e o zoom vai até a palavra ficar legível. Numa
  nota afixada, abre-a sem mexer no quadro.

## 8. Copiar e colar
- Copiar texto para outros programas leva o título e as listas com as caixas
  (`[ ]`, `[x]`) e os números, como aparecem no quadro.
- Copiar uma imagem leva a descrição; copiar um grupo leva tudo o que tem.
- Colar põe o que foi copiado onde está o rato.

## 9. Ficheiros
- Os quadros gravam-se em **`.blk`** (abre também os `.bee` do BeeRef). São
  bases de dados SQLite: as imagens numa tabela `sqlar`, as propriedades de
  cada elemento em JSON, e uma tabela `blackboard_meta` com a versão que
  gravou, a legenda e o separador de Pins.
- Gravar só escreve o que mudou. Cada quadro leva uma miniatura de como estava
  a ser visto. Ao fechar com alterações, oferece gravar.
- **Nunca** voltar a ler os elementos por uma lista de tipos conhecidos: foi
  isso que apagou grupos e desenhos duas vezes.
- Exportar: imagem do quadro (PNG, etc.) e SVG.

## 10. Desempenho (porque é que o quadro é rápido)
- **Cada nota conta as suas linhas uma vez por alteração** (tarefas, maior
  letra) em vez de dezenas de vezes por frame.
- **Cada elemento fica guardado já desenhado** (`DeviceCoordinateCache` do Qt,
  ligado em `SelectableMixin.init_selectable`). O scroll só repõe essas
  imagens. **Regra:** tudo o que muda o aspeto de um elemento tem de chamar o
  seu `update()`, mesmo que o elemento em si não tenha mudado (por exemplo: a
  cor do quadro, ou escolher um segundo elemento, que tira as pegas ao
  primeiro). Quando um elemento vai mudar de tamanho, o desenho guardado é
  deitado fora (`SelectableMixin.prepareGeometryChange`), por causa de um
  defeito do Qt com elementos maiores que a janela.
- **Zoom rápido:** quando começa um zoom, tira-se uma imagem do quadro e é ela
  que aumenta ou diminui; o quadro fica nítido 160 ms depois de parar, ou ao
  primeiro clique ou tecla (`BeeGraphicsView.start_quick_zoom`).
- Exportações e miniaturas desenham tudo de raiz (`scene.drawn_afresh()`).
- Números no BVR001 (12.2): scroll 13–17 ms, zoom a aproximar 9–13 ms, a
  afastar ~35 ms; memória 400–560 MB.

## 11. Versões, instalação e os dois computadores
- `VERSION` em `beeref/constants.py` sobe 0.1 em cada commit; o número no
  Help → About identifica o commit exato.
- `tools\release.ps1` verifica o estilo e os testes, compila com
  PyInstaller, faz `dist\Blackboard-<versão>.zip`, instala neste PC e marca a
  tag. Publicar é um passo à parte: `git push origin bvref --tags` e
  `gh release create`.
- O zip tem `Install.cmd`, que copia para
  `%LOCALAPPDATA%\Programs\Blackboard\Blackboard.exe` (caminho fixo) e
  associa os `.blk`. Sem direitos de administrador nem Python.
- **Abrir os quadros com duplo clique no .blk**, e não a partir de cópias em
  Downloads: é assim que abrem sempre na versão mais nova.
- O executável não é assinado: o **Smart App Control** do Windows pode
  bloqueá-lo (num dos PCs foi desligado).

### 11.1 Mac (processadores Apple, M1 e seguintes)
- Não se compila a partir do Windows: é um Mac do GitHub que o faz
  (`.github/workflows/build.yml`), sozinho, sempre que uma versão é
  publicada, e junta `Blackboard-<versão>-mac.zip` à release. Instala-se
  arrastando o `Blackboard.app` para a pasta Aplicações.
- A aplicação não é assinada: na primeira vez o Mac recusa abri-la, e é
  preciso autorizar em Definições do Sistema → Privacidade e Segurança →
  "Abrir mesmo assim".
- **O mesmo quadro tem de ficar igual nos dois sistemas.** As notas são
  escritas em Segoe UI, que o Mac não tem; no Mac são desenhadas com a
  **Blackboard Sans**, que vem dentro do programa. É uma cópia da Selawik
  (a letra gratuita que a Microsoft fez para substituir a Segoe UI): as
  mesmas larguras letra a letra, e a altura de linha acertada pela da Segoe
  UI (`tools/make_note_font.py`). O Mac mede os tamanhos em pontos de outra
  maneira (72 por polegada em vez de 96), por isso o programa pede-lhe que
  os meça como o Windows. Medido no Mac do GitHub: as mesmas notas saem com
  a mesma largura, a mesma altura e o mesmo número de linhas.
- No Mac, Ctrl é a tecla Cmd e Alt é a tecla Option; o cartão de atalhos e
  o ecrã de boas-vindas dizem-no assim.
- Teclas que o Mac não tem ou guarda para si: apagar responde também à
  tecla delete do MacBook (que é o Backspace), e o ecrã inteiro também a
  Control+Cmd+F (o F11 é do macOS). PgUp/PgDown fazem-se com Fn+setas, e
  F1/F3 com Fn. Cmd+H é do macOS (esconder a aplicação), por isso a ajuda
  só responde a F1.
- No Mac há um só Blackboard aberto: um quadro aberto com duplo clique
  toma o lugar do que está na janela, depois de perguntar se é para gravar.
- **Não funciona no Mac:** o SpaceMouse (a leitura foi escrita para
  Windows).
- Ninguém aqui tem um Mac: a compilação abre a aplicação, tira uma
  fotografia ao ecrã e guarda-a com o zip, para se ver antes de anunciar.

## 12. Mapa do código
| Ficheiro | O que faz |
|---|---|
| `beeref/__main__.py` | Arranque, janela principal, menus |
| `beeref/view.py` | A vista: zoom, scroll, ferramentas, barras, Pins, pesquisa, zoom rápido |
| `beeref/scene.py` | O quadro: seleção, ordem, grupos, arrastar, encaixes |
| `beeref/items.py` | Imagens, notas, grupos, desenhos, títulos, descrições, tarefas, tabelas |
| `beeref/selection.py` | Pegas, redimensionar, rodar, esticar, contorno de seleção |
| `beeref/imagecache.py` | Imagens comprimidas e abertas ao tamanho visto |
| `beeref/commands.py` | Os passos de desfazer/refazer |
| `beeref/actions/` | Menus, atalhos e o que cada um chama |
| `beeref/fileio/` | Ler e gravar `.blk`, exportar |
| `beeref/config/` e `beeref/widgets/settings.py` | Definições e a janela delas |
| `beeref/widgets/` | Barras, painéis (camadas, legenda), separador Pins, pesquisa |
| `tools/release.ps1`, `tools/Install.cmd` | Publicar e instalar |
| `Blackboard.spec` | Compilação com PyInstaller |
| `tests/` | ~2500 testes (pytest) |

## 13. Atalhos
| Atalho | Ação |
|---|---|
| Ctrl+N / Ctrl+O / Ctrl+S / Ctrl+Shift+S | Novo, abrir, gravar, gravar como |
| Ctrl+Shift+E | Exportar o quadro |
| Ctrl+I | Inserir imagens |
| T / Ctrl+T | Escrever uma nota |
| Ctrl+Shift+T | Lista de tarefas |
| Alt+T | Tabela |
| Ctrl+B, Ctrl+= / Ctrl+- | Negrito, texto maior / menor |
| Ctrl+Z / Ctrl+Shift+Z | Desfazer / refazer |
| Ctrl+C / Ctrl+X / Ctrl+V / Del | Copiar, cortar, colar, apagar |
| Ctrl+A / Ctrl+Shift+A | Escolher tudo / nada |
| Ctrl+G / Ctrl+Shift+G | Agrupar / desagrupar |
| PgUp / PgDown | Levar ao topo / ao fundo |
| Ctrl+F / F3 | Pesquisar / resultado seguinte |
| Ctrl+P / Ctrl+Shift+P | Afixar nota / recolher separador Pins |
| Ctrl+J / Ctrl+L | Painel de camadas / legenda |
| Shift+G | Encaixe na grelha |
| Shift + arrastar | Encaixar noutro elemento |
| Alt + arrastar | Tirar um elemento do grupo |
| Ctrl + clique | Abrir um link |
| Shift+C | Recortar imagem |
| G | Cinzento |
| H / V | Virar na horizontal / vertical |
| S | Apanhar uma cor do quadro |
| Shift+H / Shift+W / Shift+S | Igualar alturas / larguras / tamanhos |
| 1 / 2 | Ver tudo / ver a seleção |
| R | Repor a escala, rotação e viragem dos escolhidos |
| Roda / Shift+roda / Ctrl+Shift+roda | Zoom / deslocar na horizontal / na vertical |
| Botão do meio / Ctrl + botão do meio | Deslocar / zoom arrastando |
| Trackpad do Mac: dois dedos / pinça | Deslocar / zoom |
| F11 / Ctrl+M | Ecrã inteiro / mover a janela |
| F1 | Ajuda e atalhos |

Os atalhos podem ser mudados em Settings → Keyboard & Mouse.

**Conhecido:** Shift+O está atribuído a duas ações (arrumar "Optimal" e
"Outline" da imagem). Quando dois comandos partilham um atalho, o Qt pode
não executar nenhum — está por resolver.

## 14. Armadilhas já conhecidas
- **O programa fechava-se sozinho, sem erro, ao escolher um elemento depois
  de abrir outro quadro na mesma janela**, se o painel de camadas tivesse
  sido usado. Cada linha do painel guarda o elemento que representa, e
  pedir a uma linha um elemento que já não existe termina o programa na
  hora. O painel larga tudo antes de o quadro ser limpo
  (`LayersTree.forget_items`, chamado em `clear_scene`). Qualquer coisa que
  guarde elementos do quadro tem de os largar aí.
- **No Mac, um quadro aberto com duplo clique substituía o que estava
  aberto sem perguntar nada.** O Mac entrega o ficheiro à janela que já
  existe, em vez de abrir outra como o Windows. Passa pelo mesmo caminho
  de "abrir outro quadro", que pergunta primeiro (`open_from_outside`).
- **No Mac, o que vem na linha de comandos é entregue ao programa como
  ficheiro a abrir.** Correr `pytest tests` lá fazia o programa tentar abrir
  a pasta `tests` e parar num aviso; corre-se `pytest` sem caminho.
- **No Mac, a janela "Loading images" ficava presa** por cima de um quadro
  que deixava de responder (12.5 e 12.6). O Mac mostra um diálogo modal à
  sua janela como uma "folha" que desce da barra de título; uma imagem só
  é carregada antes de a folha acabar de descer, e fechar a folha tão cedo
  deixava o Qt à espera para sempre (3 em 4 tentativas no Mac do GitHub).
  No Mac o diálogo é modal à aplicação inteira, que é uma janela normal
  (`BeeProgressDialog.modality`): 16 em 16.
- **Um erro ao ler uma imagem não pode deixar o carregamento a meio.** O
  carregamento corre à parte e só avisa quando acaba; um erro inesperado
  deixava o diálogo aberto para sempre, e o programa tomava-o por motivo
  para fechar (perguntava se queria gravar). Agora a imagem com erro entra
  na lista das que não abriram e as outras continuam
  (`fileio.load_images`).
- **Só um JPEG diz para que lado está virado.** A biblioteca que lê essa
  informação, dada um PNG, procura no meio da imagem os dois bytes que num
  JPEG a anunciam, acaba por encontrá-los num ficheiro grande e lê o que
  vem a seguir como se fizesse sentido. Só lhe são dados JPEG
  (`fileio.image.exif_rotated_image`).
- **No Mac, uma nota de 9 pontos saía com três quartos do tamanho**, dentro
  de uma caixa da largura de sempre, e todas as linhas quebravam noutro
  sítio. Dizer ao Qt só "96 por polegada" (`QT_FONT_DPI`) não chega: no Mac
  ele aumenta a janela inteira um terço. É preciso dizer-lhe também para não
  dimensionar pelo ecrã (`QT_ENABLE_HIGHDPI_SCALING=0`). Ver
  `measure_text_as_windows_does`.
- **Uma letra diz a altura das suas linhas em dois sítios**, e o Windows lê
  um e o Mac o outro. Na Selawik não coincidem (1,33 e 1,2 vezes o tamanho
  da letra), por isso a cópia que vai no programa foi acertada.
- **O que se escrevia numa nota de largura fixa não aparecia** enquanto se
  escrevia (11.6 a 12.3; notas afixadas incluídas). Depois de cada letra o Qt
  pede para redesenhar "tudo daqui para a frente", com um retângulo de dois
  mil milhões de largura, e esse tamanho não cabe no desenho guardado do
  elemento: nada era redesenhado. A nota pede agora para ser redesenhada
  inteira (`BeeTextItem.draw_afresh`, 12.4).
- **Elementos maiores que a janela** guardados desenhados ficavam deslocados
  quando mudavam de tamanho para cima ou para a esquerda (12.2). Resolvido em
  `SelectableMixin.prepareGeometryChange`.
- **Largar o rato com Shift ou Ctrl** não deixava o Qt esquecer o arrasto, e
  o elemento arrastado a seguir saltava para o canto (12.1). Em
  `SelectableMixin.mouseReleaseEvent`.
- As definições do Qt (QSettings) **não** seguem a variável APPDATA: os
  scripts de teste usam `QSettings.setPath`.
- Testes que copiam para a área de transferência falham se outro programa a
  estiver a usar; repetir, não contornar.
- O caminho do repositório tem espaços: se o PyInstaller falhar, é a primeira
  suspeita.
- Um ambiente `.venv` copiado de outro PC não funciona; refaz-se.
