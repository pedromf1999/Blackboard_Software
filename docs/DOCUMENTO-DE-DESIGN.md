# Blackboard — Documento de Design

Estado na versão **15.6** (outubro de 2026). Este documento descreve o que o
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
- **Aumentar e diminuir** (13.9): os dois botões de tamanho na barra da
  imagem, ou Ctrl+= / Ctrl+-, fazem a imagem 10% maior ou menor de cada vez,
  à volta do centro (várias imagens crescem juntas, mantendo as distâncias).
  Enquanto se escreve a legenda, fazem o tamanho da legenda. A espessura do
  contorno passou para Images → Thinner / Thicker Outline.
- **Recortar** (Shift+C), **contorno** com cor e espessura, **cinzento** (G),
  opacidade, virar (H / V), redimensionar pelos cantos (mantém a proporção) e
  esticar pelas arestas.
- **Descrição** (caption): faixa por baixo da imagem, com o texto a quebrar
  linha. As quebras de linha são decididas ao tamanho da própria descrição
  e mantêm-se a qualquer zoom, como nos títulos (14.4). Os links na descrição ficam sublinhados e abrem com Ctrl+clique.
  Abre-se com T ou duplo clique.
- Um esboço feito por cima de uma imagem fica preso a ela.
- **Pré-visualização de links** (13.8): colar um endereço web sozinho
  (Ctrl+V) traz a imagem que o site oferece para partilhas (og:image,
  twitter:image ou image_src: a foto do produto, a capa do vídeo), com o
  endereço na descrição, que abre com Ctrl+clique. O link aparece logo como
  nota (14.1); 1 a 2 s depois a imagem toma o lugar dela, centrada onde a
  nota estiver nesse momento, num passo de desfazer próprio (Ctrl+Z volta à
  nota, outro Ctrl+Z tira-a). Se entretanto a nota foi apagada, desfeita ou
  escrita, a imagem não a substitui. O que estiver selecionado continua
  selecionado. Um site sem imagem, ou que recusa programas que não são
  browsers (Amazon, Behance), deixa a nota, com um aviso. Desliga-se em Settings → Images & Items. Só o colar
  vai à internet; nada mais é descarregado. Ver `beeref/link_preview.py`.
  - **YouTube** (14.5): na Europa, o YouTube mostra muitas vezes uma página
    de consentimento de cookies em vez do vídeo, e essa página não tem
    imagem. Para vídeos (link normal, youtu.be, Shorts, diretos, YouTube
    Music, telemóvel, incorporado), o código do vídeo é tirado do link e a
    capa vem diretamente de i.ytimg.com (alta resolução, senão a normal, sem
    as faixas pretas), e o ícone de gstatic.com. Mais rápido (0,1 s). Se não
    houver capa, tenta a página. Canais (@nome) e diretos já terminados
    ficam como nota. Não se mexe em cookies.
  - **Lojas e fornecedores** (14.7): muitos não declaram imagem para
    partilhas, ou declaram o logótipo. Por ordem: a imagem declarada (se não
    for logótipo); a do produto nos dados para motores de busca
    (schema.org Product); a imagem principal na página, reconhecida como as
    lojas a marcam (wp-post-image do WordPress, "Zoom" das lojas SAP como
    Kipp e Norelem, "product"/"produto" no nome, itemprop=image, carregada
    primeiro), na versão maior que houver; uma imagem grande que não seja
    banner; por fim o logótipo declarado. Ficam de fora logótipos, ícones,
    bandeiras, pagamentos, certificados, selos, marcadores vazios, SVG, GIF
    e imagens com menos de 100 px. Se uma não se ler (AVIF, que o Qt não
    lê), tenta a seguinte, e a mesma pedida em PNG quando o endereço pede
    "format=auto". Testado: AHP, Meusburger, Kipp, Norelem, Decotrust,
    Puzzle Advance, Fabory, DME com o produto; McMaster com o logótipo;
    Festo e Mouser recusam programas (proteção anti-robôs, não se contorna).
  - **Páginas montadas por JavaScript** (14.8): os dados de que são feitas
    vêm na página (`__NEXT_DATA__` e outros blocos JSON); procura-se lá uma
    imagem cujo campo diga produto e imagem (Misumi: productImageList),
    deixando de fora desenhos de medidas, ícones e logótipos. Os servidores
    da Misumi levam ~10 s por pedido, por isso a imagem chega ~20 s depois
    da nota. **GrabCAD**: para `grabcad.com/library/<modelo>` pergunta-se ao
    endereço público `community/api/v1/models/<modelo>` pela
    `preview_image`, e pede-se a versão "large" (960 px).
  - **Pinterest** funciona como qualquer site (a imagem do pin, 736 px, e o
    ícone). **Google Imagens** (14.6): um link "imgres" traz a imagem
    verdadeira diretamente, com a página de onde vem na descrição; um
    endereço `data:image/...` (o que o browser copia como "endereço" de uma
    miniatura do Google) é colado como imagem e não como nota. O link da
    página de resultados do Google não dá: só existe depois de o browser
    correr o JavaScript, e na Europa pede consentimento. Copiar a imagem,
    ou o endereço dela, funciona.
  - **Voltar a texto** (14.2): com a imagem de um link selecionada (uma
    imagem cuja descrição é só um endereço), aparece na barra dela um ícone
    de corrente, "Show as a text link", também em Images → Show Link as
    Text. A imagem dá lugar à nota com o link, no mesmo sítio; Ctrl+Z
    devolve a imagem. Com várias selecionadas, todas as de links mudam
    juntas, num só passo.
  - **E de volta à imagem** (14.3): uma nota que é só um link (sem título,
    não afixada) mostra o mesmo ícone de corrente na barra dela, "Show the
    link's preview", também em Text → Show Link Preview. Vai buscar a
    imagem e o ícone do site e troca a nota por eles, como ao colar. Uma
    nota a ser escrita é fechada primeiro.
  - **Ícone do site** (14.0) no canto superior esquerdo, num quadrado
    branco de cantos redondos com uma borda ténue (para se ver também sobre
    imagens brancas), com 12% do lado mais curto da imagem. É o ícone do
    separador do browser, no tamanho mais nítido que o site oferecer: um
    ícone de separador com 64 px ou mais, ou desenhado (SVG, lido a
    256 px); senão o ícone para telemóveis (apple-touch-icon, o mesmo
    logótipo maior); senão o maior do separador; senão `/favicon.ico`. Se
    um falhar, tenta o seguinte. Vem ao mesmo tempo que a imagem e não a
    atrasa mais de 6 s; sem ícone, a imagem vem na mesma.
  - Fica guardado no quadro (`link_icon`, PNG até 128 px nos dados da
    imagem). Versões anteriores abrem o quadro e simplesmente não o
    mostram. Não fica espelhado nem deformado ao virar ou esticar a imagem.
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
  percentagem), cor das palavras, **destaque** (o botão ao lado do conta-gotas
  na janela da cor, um quadrado branco riscado a vermelho, tira-o; 13.7), cor da caixa (o texto escolhe
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
- **Ortografia** (13.3), em duas línguas ao mesmo tempo, porque as notas
  misturam-nas: uma palavra está certa se qualquer uma a conhecer.
  - **As línguas escolhem-se** em Settings → Miscellaneous (13.4): uma
    primeira e uma segunda, que pode ser "None". No máximo duas: cada uma a
    mais deixa passar mais erros (o erro numa é palavra noutra) e demora
    mais a ler. De início: português de Portugal e inglês.
  - Línguas: português (Portugal), português (Brasil), inglês (britânico e
    americano juntos), espanhol, francês, alemão, italiano. Juntar outra é
    copiar o dicionário do LibreOffice e a lista de erros comuns para
    `beeref/assets/spelling/` e acrescentá-la a `LANGUAGES` em
    `spelling.py`.
  - Ficam prontas na primeira nota editada: menos de 1,5 s cada, 3 s o
    português do Brasil. Mudar de língua com uma nota aberta
    troca os dicionários sem fechar a nota.
  - Enquanto se escreve numa nota, as palavras que nenhuma língua conhece
    ficam sublinhadas a vermelho ondulado. Só durante a edição: o quadro fica
    limpo quando se sai. A palavra que se está a escrever só é julgada
    depois de acabada.
  - Ficam de fora: palavras em MAIÚSCULAS (siglas, títulos), letras soltas,
    endereços web e de email, nomes de ficheiro e pastas, tudo o que tenha
    algarismos. Uma palavra que o dicionário só conhece em maiúsculas ("OK",
    "PDF") também é aceite em minúsculas.
  - Clique direito numa palavra sublinhada: sugestões (primeiro na língua do
    resto da linha, ordenadas pela parecença, e à frente de todas a que só
    acrescenta acentos: "diseno" → "diseño") e "Add to Dictionary". As
    palavras acrescentadas ficam em `words.txt`, na pasta das definições,
    só neste computador.
  - **Correção automática** ao carregar espaço, Enter ou pontuação, só dos
    erros comuns das listas do LibreOffice ("nao" → "não", "teh" → "the"),
    mantendo as maiúsculas escritas. Nunca troca uma palavra que exista em
    qualquer das línguas, nem troca por símbolos (":-)" fica como está).
    Ctrl+Z logo a seguir devolve o que foi escrito.
  - Os dois interruptores estão em Settings → Miscellaneous.
  - Dicionários Hunspell do LibreOffice lidos pelo spylls (Python puro, igual
    no Windows e no Mac). São lidos em segundo plano na primeira vez que se
    edita uma nota; até lá não há sublinhados nem correções.

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
  Images & Items → "Pinned Note Text Size" (14 pt de origem); o título fica
  um pouco maior.
- A arrumação, a posição do separador e se está recolhido ficam gravados no
  quadro.

### Leitor do Spotify (15.2, local desde 15.3)
- **Ctrl+Shift+M**, o botão da nota musical no fim da barra de ferramentas
  (15.4; fica carregado enquanto o leitor está à vista) ou View → Show
  Spotify Player mostram um pequeno leitor por cima do quadro: capa, música, artista, uma linha de quanto já tocou,
  anterior / play-pausa / seguinte e o volume. A roda do rato por cima dele
  muda o volume, não o zoom. Arrasta-se por qualquer sítio fora dos botões
  e fica preso ao canto mais próximo da janela; de origem, em baixo à
  direita. Sem nada a tocar, um botão "Open Spotify". Clique direito: abrir
  o Spotify, esconder. Se estava à vista ao fechar, volta a estar ao abrir.
- **Lê o que toca no próprio computador** (`beeref/nowplaying.py`): sem
  conta, sem entrar, sem Premium e sem limite de pessoas. A 15.2 falava com
  o Spotify pela internet, o que obrigava cada pessoa a ser acrescentada à
  mão pelo dono da app no site do Spotify (no máximo 5); nunca foi
  publicada. Tocar dentro do Blackboard exigiria um navegador embutido com
  a proteção de cópia do Spotify, que o do Qt não tem.
- **Windows:** pelos controlos de música do sistema (os que aparecem ao
  carregar nas teclas de volume), com o `winrt`. Vê qualquer leitor (o
  Spotify, um vídeo no navegador...): Spotify a tocar ganha, depois
  qualquer coisa a tocar, depois o Spotify em pausa. O volume é o do
  computador, lido e mudado pelo áudio do Windows com `ctypes` -- o
  Windows não deixa um programa mudar o volume de outro. O Spotify só diz
  a posição de 4,5 em 4,5 s; entre as duas, a linha avança sozinha, nunca
  mais de 10 s para lá do que ele disse.
- **Mac:** pergunta à app do Spotify com AppleScript (`osascript`), tudo
  numa só pergunta. Nunca abre o Spotify: só pergunta se já estiver aberto,
  e não pergunta nada se não estiver instalado (perguntar por uma app que
  não existe faz o Mac perguntar onde está). Na primeira vez o Mac pergunta
  se o Blackboard pode controlar o Spotify; a frase vem de
  `NSAppleEventsUsageDescription` no `Blackboard.spec` -- sem ela o Mac
  recusa sem perguntar. A capa vem pelo endereço que o Spotify dá. O volume
  é o do Spotify. **Não testado num Mac real**: só a leitura da resposta,
  com respostas simuladas.
- **Nunca atrasa o quadro:** as perguntas são feitas numa linha de
  execução à parte, uma de cada vez (2–3 ms cada no Windows), de 1 em 1 s
  com a janela em uso, de 4 em 4 s sem ela, e nada com o leitor escondido
  (nem é criado até ser mostrado). A capa só é lida quando a música muda e
  é guardada a 128 px. A linha do progresso pinta-se a si própria por
  inteiro (`WA_OpaquePaintEvent`) e o botão play só muda de ícone quando
  muda de estado. Medido com o Spotify a tocar: 0 pinturas do quadro por
  trás do leitor em 5 s.
- O `winrt` (MIT, ~1,8 MB) só entra no Windows (`sys_platform == 'win32'`
  no `pyproject.toml`); sem ele, ou num sistema sem forma de saber, o
  leitor diz "Not available on this computer" e o resto não muda.

## 7. Pesquisar
- **Ctrl+F** abre a barra; **F3** / Find Next / Previous percorrem os
  resultados. Procura nas notas, nos títulos de notas e grupos e nas
  descrições das imagens.
- Cada resultado é escolhido e o zoom vai até a palavra ficar legível. Numa
  nota afixada, abre-a sem mexer no quadro.
- **Go Back** (14.9): na barra de pesquisa, volta à vista (ampliação e
  centro) e à seleção de antes do primeiro salto da pesquisa, mesmo depois
  de passar por vários resultados. Fica ativo só quando há para onde
  voltar. Abrir a barra de novo começa uma pesquisa nova; fechá-la esquece
  o caminho de volta. Uma nota apagada entretanto não volta a ser
  selecionada.

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
- **Quadros numa pasta que sincroniza** (Google Drive, OneDrive, Dropbox,
  iCloud): a sincronização é da app de cada serviço, não do Blackboard --
  é o que o PureRef, o BeeRef e os programas de CAD fazem, e ligar uma
  conta Google obrigava a registar uma app na Google, com a sessão a cair
  de 7 em 7 dias até ela ser verificada. O Blackboard trata do problema
  que essas pastas trazem: o mesmo quadro gravado em dois computadores.
- **Marca de gravação** (15.5): cada gravação deixa no ficheiro um número
  inventado para ela (`save_mark` em `blackboard_meta`; os ficheiros
  continuam a abrir em versões que não o conhecem). A janela lembra o
  tamanho, a hora e a marca do ficheiro tal como o leu ou gravou
  (`fileio/ondisk.py`); tamanho ou hora diferentes, com outra marca (ou sem
  marca), quer dizer que foi gravado noutro lado. Uma app de sincronização
  que só lhe toca muda a hora, não a marca.
- **Nunca grava por cima de outra versão sem perguntar** (15.5): Ctrl+S
  com o ficheiro gravado noutro lado desde que foi aberto pergunta "Saved
  somewhere else": **Save as a Copy...** (sugere ao lado, com o nome do
  computador: `BVR001 (PEDRO-PC).blk`), **Replace It** ou Cancel. Porque
  gravar só escreve o que mudou: escrito dentro da versão do outro
  computador, apagava o trabalho de lá sem aviso (medido: a nota de lá
  desapareceu). Substituir escreve o quadro inteiro de novo. Save As para
  outro sítio não pergunta.
- **Aviso de versão nova** (15.6): de 2 em 2 s, e ao voltar à janela, a
  janela pergunta ao disco o tamanho e a hora do ficheiro (só isso; o
  ficheiro só é aberto, para ler a marca, quando mudam). Mudado e igual em
  duas vezes seguidas -- para não ler um ficheiro ainda a chegar --,
  aparece uma barra por baixo da barra de ferramentas: "This board was
  saved somewhere else", com **Reload** e ✕ ("not now", até mudar de
  novo; gravar continua a perguntar). Com alterações por gravar: **Save
  Mine as a Copy...** e **Reload, Losing Mine**. Reload lê o quadro de
  novo no mesmo zoom e no mesmo sítio, sem ajustar à janela. Nunca recarrega
  sozinho: é quem trabalha que escolhe quando o quadro muda.
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
- **Respostas guardadas até mudarem** (15.0): o Qt pede a cada imagem o seu
  tamanho centenas de vezes por frame; a altura da descrição e o tamanho da
  imagem ficam guardados até `prepareGeometryChange` (e a espessura do
  contorno, que às vezes é posta diretamente). O tamanho do quadro inteiro
  (`scene.itemsBoundingRect`) fica guardado até um elemento se mexer, mudar
  de tamanho, entrar ou sair (as notas afixadas não contam); "ajustar à
  janela" mede sempre de novo.
- **Grelha num só pedido** (`drawRects`) em vez de um por linha.
- **A imagem do zoom rápido** é desenhada pelo caminho normal da janela
  (`viewport.render`), que aproveita o que cada elemento tem guardado, em vez
  de `QGraphicsView.render`, que redesenha tudo: o início de cada zoom
  deixou de levar ~100 ms.
- **Letras pequenas demais para ler** (abaixo de 2,5 pontos no ecrã, ~3 px)
  são desenhadas como uma barra ténue por linha (notas, descrições,
  títulos); abaixo de 0,5 nada. Nunca numa nota a ser escrita. Com o quadro
  inteiro à vista, todas as notas do BVR001 ficam abaixo de 1 px, e
  desenhá-las letra a letra era metade do tempo que o quadro levava a ficar
  nítido depois de um zoom.
- Medição (`scratchpad/perf/bench.py`, cópia do BVR001 com 419 imagens,
  115 notas e 68 grupos, janela 1700×1000): quadro inteiro à vista, mover
  9 → 3,5–4 ms por frame (pior 108 → 14 ms), zoom 24 → 6–7 ms (pior
  150 → 55–70 ms). Com só 2 núcleos os números são iguais: o limite é o
  desenho numa só linha de execução, não o processador.
- **Abrir um quadro grande** (15.1): 5,9 → 1,4 s no BVR001. O registo
  (log) escreve sem perguntar ao disco o tamanho do ficheiro a cada linha
  (`BeeRotatingFileHandler.emit` conta o que escreveu); as cópias pequenas
  das imagens abrem-se em paralelo enquanto o ficheiro é lido
  (`imagecache.small_copy`, até 4 de cada vez e sempre um núcleo a menos
  que o computador tem, deixado à janela); as pausas para a janela receber
  o que já foi lido são de 2 ms com o `time.sleep` do Python, porque as de
  10 ms do Qt duravam 16; a barra de progresso é redesenhada no máximo 25
  vezes por segundo; as linhas de registo de cada elemento passaram ao nível
  `trace`, que não é escrito; e cada elemento só pede as definições quando
  precisa delas. A memória depois de abrir fica igual.
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
| `beeref/spelling.py` e `beeref/assets/spelling/` | Ortografia: dicionários, sugestões, erros comuns |
| `beeref/nowplaying.py` e `beeref/widgets/spotify_player.py` | Leitor do Spotify: o que toca no computador e os botões; a janela dele |
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
| Ctrl+B, Ctrl+= / Ctrl+- | Negrito, texto (ou imagem) maior / menor |
| Ctrl+Z / Ctrl+Shift+Z | Desfazer / refazer |
| Ctrl+C / Ctrl+X / Ctrl+V / Del | Copiar, cortar, colar, apagar |
| Ctrl+A / Ctrl+Shift+A | Escolher tudo / nada |
| Ctrl+G / Ctrl+Shift+G | Agrupar / desagrupar |
| PgUp / PgDown | Levar ao topo / ao fundo |
| Ctrl+F / F3 | Pesquisar / resultado seguinte |
| Ctrl+P / Ctrl+Shift+P | Afixar nota / recolher separador Pins |
| Ctrl+J / Ctrl+L | Painel de camadas / legenda |
| Ctrl+Shift+M | Leitor do Spotify |
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
- **Os controlos de música do Windows nunca respondem à linha principal.**
  O Qt prepara a linha da janela de uma maneira (STA) em que as respostas
  do `winrt` só chegam pela fila de mensagens, que ninguém lê enquanto se
  espera por elas: o programa fica parado para sempre. Por isso tudo o que
  é do `winrt` vive e morre na linha à parte (`nowplaying.Asker`), que é
  preparada da outra maneira antes de mais nada; e é largado lá dentro ao
  parar (`WindowsMedia.close`) -- largado noutra linha, o Windows recusa
  (erro 0x8001010E).
- **Caminhos compridos demais impedem o `winrt` de carregar** ("O nome de
  ficheiro ou a extensão é demasiado longo"): passou dos 260 caracteres
  numa pasta temporária funda. Instalado (`%LOCALAPPDATA%\Programs\
  Blackboard`) ou descompactado em Downloads fica muito abaixo; se
  acontecer, o leitor só diz que não está disponível.
- **As barras de botões ficam por cima de tudo o que flutua sobre o
  quadro.** As etiquetas das notas afixadas minimizadas eram postas por
  cima em cada frame, e tapavam a barra da nota em edição. Agora cada coisa
  que flutua só é posta por cima no momento em que aparece, com as barras
  de volta por cima dela (`BeeGraphicsView.bring_into_sight`). Reordenar
  em cada frame custava um décimo do tempo de deslocar o quadro.
- **O traço de uma lista, e a caixa e o número de uma tarefa, copiam o
  aspeto da primeira letra da linha -- menos a cor de uma letra com
  destaque.** Essa cor é escolhida para se ler sobre o destaque (preta sobre
  amarelo ou laranja), e o traço fica ao lado do destaque, em cima da nota:
  saía preto sobre uma nota preta. Aí leva a cor que o texto tem sobre a
  nota (`BeeTextItem.marker_look`).
- **Um ficheiro largado no quadro pode não durar mais do que o próprio
  arrastar.** A miniatura que o Mac mostra depois de um screenshot é um
  ficheiro numa pasta temporária, apagado mal é largado em algum sítio; as
  imagens eram lidas um instante depois, em segundo plano, e já lá não
  estava ("1 image could not be opened"). Os ficheiros largados são abertos
  no próprio momento e ficam seguros até serem lidos (`fileio.held_open`):
  um ficheiro aberto continua legível depois de apagado. Cada ficheiro é
  lido uma só vez, para a imagem e para a orientação.
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
  ficheiro a abrir.** Os testes automáticos param lá por isso logo no
  primeiro que usa uma janela, num aviso de "ficheiro inválido", mesmo sem
  dar um caminho ao `pytest`. Ainda não correm no Mac; o guião de usos
  principais faz as vezes deles.
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
- **Texto desenhado ao tamanho do ecrã não pode decidir onde quebra a
  linha** (14.4): as letras não crescem exatamente em proporção com o zoom
  (o ecrã acerta-as aos píxeis), e uma descrição passava de 4 para 5 ou 6
  linhas ao afastar, saindo da faixa. As quebras vêm de
  `BeePixmapItem.caption_breaks`, ao tamanho da descrição, e o desenho usa
  essas mesmas quebras (`QTextLine.setNumColumns`).
- **Os dicionários são uns dois milhões de pequenos objetos** do Python. O
  coletor de lixo do Python percorre de vez em quando tudo o que existe, e
  com eles lá dentro parava a janela um quarto de segundo de cada vez. São
  lidos com o coletor desligado e postos de lado com `gc.freeze()` (13.3).
- **Pedir sugestões a três dicionários leva até meio segundo.** São
  calculadas em segundo plano assim que uma palavra fica sublinhada, para o
  clique direito abrir logo (13.3).
- **Um clique que o elemento responde sozinho** (abrir um endereço com
  Ctrl+clique, marcar uma tarefa, abrir a faixa das concluídas) não chega à
  parte que arrasta. Mexer o rato antes de o largar fazia-a procurar onde o
  arrasto começou, e o erro fechava o Blackboard (13.6). Esses cliques
  marcam `press_answered`, que `SelectableMixin` respeita até se largar o
  rato; cada clique novo limpa-o, porque o largar pode ir para o browser.
- **Descarregar com a rede do Qt, não a do Python** (13.8): o Python
  empacotado para Mac muitas vezes não tem a lista de certificados e recusa
  todos os sites https; o Qt usa a do próprio sistema, no Windows e no Mac.
- **Os dicionários são lidos fora da janela mas postos em uso dentro dela**
  (`take_up_loaded`), para nenhuma pergunta apanhar meio dicionário velho e
  meio novo ao mudar de língua. Os antigos não são entregues ao coletor de
  lixo: quase tudo neles se liberta sozinho, e procurar o resto parava a
  janela 0,7 s (13.4).
