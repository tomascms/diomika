# Diomika — Relatório técnico exaustivo

**Parte 1 de N — Fundamentos**
Ficheiro: `deploy/relatorio_parts/part_01_fundamentos.md`

Este documento descreve o sistema **Diomika** tal como ele existe e funciona em produção: um catálogo profissional de almofadas e produtos de estofo vendido de empresa para empresa. Descreve as três superfícies visíveis (a loja no browser, a interface de administração instalada no computador, e a camada de dados), o que corre em cada máquina, que protocolos são usados entre elas, e — sobretudo — **porque** cada decisão foi tomada.

Nenhum segredo real (palavra-passe, token, chave de acesso, credencial de base de dados) aparece neste documento. Sempre que for necessário falar de um segredo, é referido apenas pelo **nome da variável** que o guarda (por exemplo `API_SECRET_KEY`), nunca pelo valor. Essa é uma regra de segurança do projecto, não uma cortesia editorial: o repositório de código é tratado como podendo tornar-se público a qualquer momento, e portanto nada que seja secreto pode viver lá dentro.

---

## Como ler este documento

Este relatório foi escrito para uma pessoa inteligente, curiosa e capaz de raciocinar sobre sistemas — mas que **não** trabalha em informática e a quem ninguém explicou o significado das siglas que a indústria usa como se fossem palavras comuns. A informática tem um problema cultural: comunica por abreviaturas. Diz-se "a API está atrás do Tunnel com TLS terminado na CDN e RLS no Postgres" e espera-se que o interlocutor acene. Este documento recusa esse hábito.

**Regra de ouro deste relatório:** nenhuma sigla é usada sem ser expandida na primeira vez que aparece, e a expansão vem sempre acompanhada de uma explicação em linguagem comum do que a coisa **é** e do que a coisa **faz**. Se aparecer "HTTPS" pela primeira vez, aparece como "HTTPS — *HyperText Transfer Protocol Secure*, isto é, o protocolo de conversa entre browsers e servidores, na versão encriptada". Se depois disso o documento voltar a escrever apenas "HTTPS", é porque o leitor já foi apresentado ao termo.

### Estrutura em partes

O relatório completo está dividido em vários ficheiros na pasta `deploy/relatorio_parts/`. Cada ficheiro é uma **parte** autónoma, que se pode ler sozinha, mas que assume que as partes anteriores foram lidas.

Esta é a **Parte I — Fundamentos**. O objectivo desta parte não é descrever a Diomika em detalhe técnico (isso vem nas partes seguintes); é **construir o vocabulário e os modelos mentais** necessários para que as partes seguintes sejam legíveis. É a parte que se lê primeiro e à qual se volta sempre que uma sigla parecer opaca.

### Três níveis de leitura

Cada secção desta parte está escrita para poder ser lida a três velocidades diferentes:

1. **Leitura rápida (o essencial).** Os primeiros parágrafos de cada secção dão a ideia central em linguagem comum, muitas vezes com uma analogia do mundo físico. Se o objectivo for apenas conseguir seguir uma conversa técnica sobre a Diomika, basta este nível.
2. **Leitura normal (compreender).** O corpo de cada secção explica o mecanismo — o que acontece, em que ordem, quem fala com quem. Este é o nível certo para quem quer poder tomar decisões informadas sobre o sistema, aprovar orçamentos, ou perceber o impacto de uma avaria.
3. **Leitura aplicada (a Diomika concretamente).** Cada secção termina com uma subsecção do género "na Diomika", que liga o conceito abstracto a ficheiros e caminhos reais do repositório, como `backend-api/main.py` ou `frontend-web/src/lib/api.js`. Este nível interessa a quem vai mexer no código ou operar o sistema.

### Convenções tipográficas

- `Texto em tipo monoespaçado` indica algo literal do sistema: um nome de ficheiro (`backend-api/core/middleware.py`), uma pasta (`frontend-web/`), um nome de variável de ambiente (`SUPABASE_URL`), um endereço (`https://api.diomika.com`), ou um cabeçalho de protocolo (`X-Diomika-Desktop`).
- **Negrito** marca o primeiro aparecimento de um conceito importante, ou uma decisão de engenharia que vale a pena reter.
- *Itálico* é usado para as expansões em inglês das siglas (porque as siglas são quase todas inglesas) e para ênfase leve.
- Blocos de código com moldura mostram exemplos ilustrativos. Salvo indicação em contrário, os valores nesses blocos são **inventados para o exemplo** e não correspondem a dados reais nem a segredos reais.

### O que este documento não é

Não é um roteiro de futuro. Quando o documento diz que algo existe, é porque existe no código e corre em produção. Quando algo está implementado mas desligado, o documento di-lo explicitamente com essas palavras ("implementado, desligado por omissão"). Quando algo é apenas uma possibilidade prevista pelo código mas nunca activada, o documento di-lo também ("código pronto, não activado"). Esta honestidade é deliberada: um relatório técnico que confunde o que existe com o que se gostaria de ter é pior do que não ter relatório nenhum, porque induz decisões erradas.

Também não é um manual de utilização. Não explica como criar um produto no catálogo nem como responder a um pedido de orçamento. Explica como o sistema que permite fazer essas coisas está construído.

### Uma nota sobre "porque é que isto é tão complicado"

Um leitor não-técnico que percorra este documento pode legitimamente perguntar: para vender almofadas a empresas, é preciso tudo isto? Vale a pena responder desde já, porque a resposta é o fio condutor de todo o relatório.

Grande parte da complexidade não serve para mostrar o catálogo — mostrar um catálogo é fácil. A complexidade serve para três coisas: **não ser invadido**, **não gastar dinheiro**, e **não perder dados**. A internet pública é um ambiente hostil por omissão: qualquer endereço acessível recebe, poucas horas depois de existir, tentativas automáticas de descobrir ficheiros de configuração, painéis de administração e palavras-passe fracas. Não são ataques dirigidos à Diomika; são varreduras industriais que testam todos os endereços do mundo. A arquitectura da Diomika está desenhada para que essas varreduras não encontrem nada útil.

A segunda razão é económica. A Diomika corre com um custo de infra-estrutura recorrente próximo de **zero euros por mês**, usando camadas gratuitas permanentes de vários fornecedores em vez de servidores alugados. Isso é uma vitória, mas tem um preço: obriga a escolhas de arquitectura que não seriam necessárias com um orçamento maior — como fazer trabalho pesado num computador muito pequeno, ou usar um túnel em vez de um endereço público próprio. Muitas das decisões descritas neste relatório só se compreendem à luz desta restrição.

A terceira razão é a natureza dos dados. Pedidos de orçamento de clientes empresariais contêm nomes, contactos, e às vezes preços negociados. Não é informação de altíssima sensibilidade, mas é informação que não deve andar exposta, e cuja perda ou fuga teria consequências comerciais e legais reais.

---

## Parte I — Fundamentos (o que é cada peça do puzzle)

---

### I.1 O que é a Diomika (produto de negócio)

Antes de qualquer tecnologia, é preciso entender **o que o sistema serve para fazer**. Toda a arquitectura descrita neste relatório é uma resposta a este problema de negócio, e nada nela faz sentido sem ele.

#### O problema comercial

A Diomika vende almofadas e produtos de estofo — assentos, costas, capas, composições de espuma e tecido — a **outras empresas**: fabricantes de mobiliário, retalhistas, decoradores, hotelaria. Não vende ao consumidor final que compra uma almofada para o sofá de casa.

Esta distinção parece pequena e é enorme. Uma venda a consumidor final é: a pessoa vê, gosta, mete no cesto, paga com cartão, recebe em casa. Uma venda entre empresas é quase sempre: o comprador vê o catálogo, identifica referências e cores, calcula quantidades, **pede um preço**, discute prazos e condições, e só depois se confirma uma encomenda. O preço não é público porque depende do volume, da relação comercial, do tecido escolhido e da margem negociada. Pedir a um cliente empresarial que compre com um botão de "pagar agora" é ignorar como o negócio funciona.

Consequência directa: a Diomika **não é uma loja online com pagamentos**. É um **catálogo com pedido de orçamento**. Não existe processamento de cartões, não existe carrinho que termina em pagamento, não existe integração com nenhum sistema financeiro. O que existe é: um catálogo navegável e bonito, um mecanismo para o cliente montar uma lista de interesse, e um canal fiável para essa lista chegar à Diomika como um pedido a que alguém responde.

Esta escolha remove uma quantidade imensa de complexidade e de risco. Não guardar dados de pagamento significa não ter de cumprir as normas pesadas da indústria de cartões, não ter de gerir fraude, não ter de gerir reembolsos, e não ser um alvo interessante para quem rouba dados financeiros. É uma das decisões mais valiosas do projecto, e é uma decisão de negócio, não de tecnologia.

#### As três superfícies

O sistema Diomika manifesta-se ao mundo através de três "superfícies" — três coisas que uma pessoa pode ver e usar. Vale a pena fixá-las desde já, porque o resto do relatório está organizado em torno delas.

**1. A loja.** É o sítio na internet, em `www.diomika.com`, que qualquer pessoa pode abrir num browser. Mostra categorias, produtos, fotografias, especificações técnicas, e tem formulários de contacto e de pedido de orçamento. É a cara pública. Vive na pasta `frontend-web/` do repositório.

**2. O backoffice.** É um **programa instalado no computador** de quem gere a Diomika — não é um sítio na internet. Serve para criar e editar produtos, categorias, cores, modelos; ver e responder aos pedidos de orçamento e às mensagens de contacto; registar e acompanhar encomendas; gerar documentos. Vive na pasta `backoffice-desktop/`.

**3. A interface de programação.** É a peça que ninguém vê mas que faz o trabalho: recebe pedidos das outras duas superfícies, valida-os, aplica regras de negócio, guarda e lê dados, envia e-mails. Está publicada em `api.diomika.com` e vive na pasta `backend-api/`.

Por baixo das três há uma quarta peça, que é onde a informação realmente mora: a **base de dados e o armazenamento de imagens**, alojados num serviço chamado Supabase.

#### Porque é que o backoffice é um programa instalado

Esta é a decisão de arquitectura mais invulgar da Diomika e merece explicação imediata, porque contraria a tendência da indústria — hoje quase toda a administração de sistemas se faz num painel dentro do browser.

A administração da Diomika é feita por um número muito pequeno de pessoas, sempre nos mesmos computadores. Não há centenas de utilizadores nem necessidade de acesso a partir de qualquer sítio. Nessas condições, um painel de administração acessível pelo browser é sobretudo um passivo: cria um endereço público que qualquer pessoa no mundo pode encontrar e onde qualquer pessoa pode tentar adivinhar palavras-passe. Vinte e quatro horas por dia, para sempre.

Ao fazer do backoffice um programa instalado, a Diomika consegue exigir uma coisa que um browser não pode fornecer: **prova de que o pedido vem de uma instalação oficial**. O programa instalado carrega no seu interior um segredo partilhado, colocado lá no momento em que o instalador é construído, e envia-o em todos os pedidos administrativos. Quem não tem o programa não tem o segredo; e sem o segredo os endereços administrativos comportam-se como se não existissem. Um atacante que descubra `api.diomika.com` e tente abrir a zona de administração no browser não recebe um formulário de login para atacar — recebe uma resposta de "não existe".

Isto não é uma solução perfeita e o relatório será explícito quanto aos seus limites nas partes seguintes: quem obtiver simultaneamente o instalador oficial **e** uma palavra-passe válida entra. O que a decisão consegue é eliminar toda a classe de ataques anónimos e automáticos, que é a esmagadora maioria do que realmente acontece.

#### Porque é que existe uma peça no meio

Uma pergunta natural: se os dados estão na base de dados, e a loja e o backoffice precisam de dados, porque não falam directamente com a base de dados? Porquê a peça do meio?

Três razões.

A primeira é **regras de negócio**. Criar um pedido de orçamento não é escrever uma linha numa tabela. É validar que os campos fazem sentido, verificar que quem submeteu não é um robô, garantir que uma submissão repetida por engano não cria dois pedidos, registar o pedido, enviar um e-mail de notificação, enviar uma confirmação ao cliente, e registar tudo isso de forma auditável. Essa sequência tem de viver **num** lugar, e tem de viver num lugar que o utilizador não controla.

A segunda é **confiança**. O código que corre no browser de um visitante está, por definição, nas mãos desse visitante: pode ser lido, alterado e contornado. Qualquer regra implementada só no browser é uma sugestão, não uma regra. As regras têm de ser aplicadas onde o utilizador não chega — ou seja, no servidor.

A terceira é **segredos**. Escrever na base de dados exige uma credencial poderosa. Essa credencial não pode existir no browser nem no computador do cliente; se existisse, quem a extraísse podia apagar tudo. A peça do meio é o único lugar do sistema que a possui.

#### A restrição de custo

Um último elemento de contexto sem o qual metade das decisões deste relatório parecem estranhas: a Diomika foi construída para custar **cerca de zero euros por mês** de infra-estrutura recorrente. O domínio paga-se uma vez por ano; tudo o resto usa camadas gratuitas permanentes de fornecedores estabelecidos.

Concretamente: a loja é servida por uma plataforma de alojamento estático gratuita; a peça do meio corre numa máquina virtual da camada "sempre gratuita" de um grande fornecedor de nuvem, que é muito pequena; a base de dados usa a camada gratuita do Supabase; a monitorização usa camadas gratuitas de vários serviços independentes.

Esta restrição tem consequências reais e visíveis na arquitectura. A máquina onde corre a peça do meio tem pouca memória, o que obriga a cuidado com o que se põe lá a correr. A máquina não tem um endereço público próprio bem configurado, o que motivou o uso de um túnel. E a plataforma da loja não pode correr código de servidor tradicional, o que motivou a separação entre loja e interface de programação. Nada disto é acidente; é engenharia sob restrição, que é a única engenharia que existe.

---

### I.2 O que é uma aplicação web (browser, servidor, pedido/resposta)

#### A ideia central: nada está no seu computador

Quando se abre uma página de jornal no computador, a sensação é de que o jornal "está ali". Não está. O que está no computador é um programa — o **browser** — que sabe pedir coisas a computadores distantes e mostrar o que recebe. A página que se vê foi construída no momento, a partir de ficheiros que acabaram de chegar através da rede.

Um **browser** (navegador) é um programa como o Chrome, o Firefox, o Safari ou o Edge. Faz três coisas: pede ficheiros a computadores remotos, interpreta esses ficheiros, e desenha o resultado no ecrã. É um dos programas mais complexos que existem num computador comum, precisamente porque tem de fazer isto de forma segura com ficheiros vindos de fontes desconhecidas.

Um **servidor** é um computador cuja função é estar sempre ligado à espera de pedidos, e responder-lhes. A palavra tem duas acepções que convém não confundir: o servidor-máquina (o computador físico ou virtual) e o servidor-programa (o software que atende pedidos nessa máquina). Neste relatório, quando a distinção importar, ela será feita explicitamente.

#### O ciclo pedido/resposta

Toda a web funciona sobre um único mecanismo, repetido milhões de vezes por segundo em todo o mundo: **o ciclo pedido/resposta**.

1. O browser envia um **pedido**: "dá-me o documento que está em `/produtos/almofada-lisboa`".
2. O servidor recebe o pedido, decide o que fazer, e envia uma **resposta**: um código que diz se correu bem, alguma informação sobre o que vem a seguir, e o conteúdo em si.
3. A conversa termina. O servidor não guarda memória de que aquele browser existiu.

Este último ponto é fundamental e chama-se **ausência de estado** (em inglês, *statelessness*). Cada pedido é independente. O servidor não se lembra de nada. Isto parece uma limitação — e é, do ponto de vista da conveniência — mas é a razão pela qual a web escala: qualquer servidor pode atender qualquer pedido, porque nenhum pedido depende de conversas anteriores.

A consequência prática é que tudo o que se pareça com memória tem de ser reconstruído a cada pedido. Se um administrador da Diomika fez login e depois abre a lista de produtos, o servidor não "sabe" que ele fez login — o programa tem de **reenviar a prova** de que fez login, em cada pedido, sem excepção. Essa prova é o que se chama um *token* de sessão, e a Parte sobre autenticação explica em detalhe como a Diomika o constrói.

#### Uma volta completa, em detalhe

Vale a pena percorrer uma sequência real, porque quase todos os conceitos deste relatório aparecem nela.

Um comprador de uma fábrica de mobiliário escreve `www.diomika.com` no browser.

**Passo 1 — encontrar o computador.** `www.diomika.com` é um nome, e a rede não funciona com nomes: funciona com números. O browser pergunta a um serviço de tradução de nomes qual é o número correspondente. Recebe um endereço numérico. (Este mecanismo é o assunto da secção I.5.)

**Passo 2 — abrir uma conversa segura.** O browser liga-se a esse endereço e, antes de dizer o que quer, negocia uma conversa encriptada, para que ninguém no caminho possa ler nem alterar o que vai ser trocado. O servidor apresenta um certificado que prova ser quem diz ser. (Assunto da secção I.7.)

**Passo 3 — o primeiro pedido.** O browser pede o documento raiz: "dá-me `/`". Recebe um documento em HTML — *HyperText Markup Language*, a linguagem de marcação que descreve a estrutura de uma página, isto é, o que é um título, o que é um parágrafo, o que é uma imagem.

**Passo 4 — os pedidos seguintes.** Esse documento é pequeno e quase vazio. O que ele contém são **referências** a outros ficheiros: folhas de estilo, ficheiros de código, tipos de letra, imagens. O browser lê essas referências e faz **mais pedidos** — dezenas, tipicamente. Abrir "uma página" são na realidade muitos ciclos de pedido/resposta.

**Passo 5 — o código toma conta.** Um dos ficheiros pedidos é o programa da loja, escrito em JavaScript, a linguagem de programação que os browsers sabem executar. Quando esse programa arranca, é ele que constrói a página visível. É também ele que vai buscar os dados do catálogo, com mais pedidos — agora não para páginas, mas para **dados**.

**Passo 6 — os dados.** Os produtos, as categorias, os preços de referência e as fotografias não estão no programa; estão na base de dados. O programa da loja pede-os, recebe-os num formato de troca de dados (assunto da secção I.8), e preenche o ecrã.

**Passo 7 — a interacção.** O comprador clica numa categoria. Aqui está a diferença entre a web antiga e a moderna: **a página não recarrega**. O programa que já está a correr no browser apanha o clique, vai buscar os dados da categoria, e substitui a parte do ecrã que muda. A sensação é de uma aplicação, não de um documento. (Assunto da secção I.10.)

**Passo 8 — o pedido de orçamento.** O comprador escolhe referências, indica quantidades, e submete um pedido de orçamento. Agora o fluxo inverte-se: em vez de o browser pedir informação, **envia** informação, para a interface de programação em `api.diomika.com`. Essa peça valida, verifica que não é um robô, guarda, notifica, e responde. É a única parte do fluxo em que algo no mundo muda de estado.

#### Na Diomika

A loja da Diomika é uma aplicação web no sentido pleno: os ficheiros que o browser pede estão numa plataforma de alojamento estático, e os dados vêm de dois sítios diferentes — o catálogo vem directamente do Supabase, através de `frontend-web/src/lib/catalogSupabase.js`, e as operações que escrevem algo vão para `api.diomika.com`, através de `frontend-web/src/lib/api.js`.

Essa divisão é intencional e vale a pena reter desde já, porque é uma das características distintivas da arquitectura: **ler o catálogo não passa pela peça do meio; escrever passa sempre**. Ler é uma operação inofensiva sobre dados públicos, e fazê-la directamente é mais rápido e mais barato. Escrever exige validação, regras de negócio e credenciais privilegiadas, e portanto tem de passar por onde essas coisas vivem.

---

### I.3 Cliente vs servidor

#### A distinção

Na conversa entre dois computadores, **cliente** é quem pede e **servidor** é quem responde. Não é uma característica permanente de uma máquina; é um papel numa conversa concreta. A mesma máquina pode ser servidora numa conversa e cliente noutra — e na Diomika isso acontece constantemente.

Um exemplo: a interface de programação da Diomika é **servidora** quando a loja lhe pede para registar um pedido de orçamento. Mas quando ela precisa de guardar esse pedido, passa a ser **cliente** do Supabase. E quando envia o e-mail de notificação, é cliente de um servidor de correio. Uma única acção de um comprador desencadeia uma cadeia de conversas em que os papéis mudam a cada elo.

#### Porque é que esta distinção é a base de toda a segurança

Aqui está a razão pela qual a distinção cliente/servidor domina este relatório: **o cliente é território inimigo**.

Não porque o cliente seja mal-intencionado — o comprador da fábrica de mobiliário não é. Mas porque o código que corre no computador de outra pessoa está sob o controlo dessa pessoa, e não sob o nosso. Todo o browser moderno traz ferramentas de desenvolvimento que permitem, sem qualquer conhecimento especial:

- ler todo o código que a loja enviou, incluindo comentários e nomes de variáveis;
- ver todos os pedidos que o browser fez, com todo o conteúdo enviado e recebido;
- alterar valores em memória enquanto o programa corre;
- fabricar pedidos à mão, ignorando completamente a interface.

Isto significa que existe uma regra sem excepções, e é provavelmente a regra mais importante de toda a segurança web:

> **Nunca confiar em nada que venha do cliente. Nunca esconder um segredo no cliente. Nunca aplicar uma regra apenas no cliente.**

Uma validação no browser — "este campo é obrigatório", "a quantidade tem de ser maior que zero" — é **conveniência para o utilizador honesto**, não segurança. Ajuda a pessoa a não errar, e evita uma ida ao servidor por nada. Mas não impede ninguém de enviar um pedido com o campo vazio, porque o pedido pode ser fabricado à mão. Todas as validações que **importam** têm de ser repetidas no servidor. Na Diomika elas estão declaradas em `backend-api/models/schemas.py`, e são aplicadas em cada pedido, independentemente do que o browser já tenha verificado.

#### O que pode e o que não pode viver no cliente

Esta distinção decide o desenho de todo o sistema. Vale a pena ser explícito.

**Pode viver no cliente:** o desenho visual; a navegação entre ecrãs; a formatação de números e datas; validações de conveniência; identificadores públicos (o código de um produto que já está no catálogo); chaves de acesso **desenhadas para serem públicas** e cujos poderes são restringidos do outro lado.

**Não pode viver no cliente, em circunstância alguma:** credenciais que permitam escrever ou apagar dados; chaves de serviços pagos; a lógica que decide se uma pessoa tem permissão para algo; regras de negócio cuja violação tenha consequências; segredos de qualquer tipo que não estejam já publicados.

#### O caso mais subtil: as duas chaves do Supabase

O Supabase entrega a cada projecto duas chaves de acesso muito diferentes, e a distinção entre elas é um exemplo perfeito da fronteira cliente/servidor.

A **chave anónima** (*anon key*) é desenhada para ser pública. Vai dentro do programa da loja, é visível a qualquer visitante, e não faz sentido tentar esconde-la. Ela não é, por si, uma autorização; é apenas uma identificação do projecto. O que ela pode realmente fazer é definido por regras declaradas **na base de dados** — regras que dizem, por exemplo, "com esta chave é possível ler produtos visíveis, e mais nada". Mesmo que um visitante extraia a chave e fabrique pedidos à mão, não consegue ler o que as regras não permitem.

A **chave de serviço** (*service role key*) é o oposto: ignora todas essas regras, por desenho. É a chave de administração da base de dados. Vive exclusivamente na variável `SUPABASE_KEY` no ficheiro de configuração da máquina onde corre a interface de programação, um ficheiro que nunca entra no repositório de código. Nunca é enviada a um browser, nunca é embutida num instalador, nunca aparece numa resposta.

Este par de chaves resume a filosofia: **a chave que é pública tem poderes limitados por regras do lado do servidor; a chave que tem poderes ilimitados nunca sai do servidor.**

#### O terceiro tipo de cliente: o backoffice

A Diomika tem um caso que não é browser nem servidor no sentido clássico: o programa instalado no computador do administrador. É um cliente — pede coisas à interface de programação — mas é um cliente **com propriedades especiais**.

Ao contrário de um browser, o programa instalado pode transportar um segredo que não é trivialmente visível: um valor colocado dentro do binário no momento em que o instalador é construído. Não é secreto de forma absoluta — quem tiver o ficheiro e paciência suficiente consegue extraí-lo — mas é secreto em relação a quem apenas visita `api.diomika.com` com um browser. Essa diferença de grau é suficiente para eliminar a totalidade dos ataques anónimos e automáticos.

O mecanismo, na Diomika, funciona assim: o programa instalado corre um pequeno servidor local no próprio computador, que serve a interface visual e reencaminha os pedidos para `api.diomika.com` acrescentando um cabeçalho de identificação chamado `X-Diomika-Desktop`. Do lado da interface de programação, `backend-api/core/local_only.py` compara o valor recebido com o valor esperado, usando uma comparação criptograficamente segura, e `backend-api/core/path_guard.py` bloqueia os caminhos administrativos quando a comparação falha.

Note-se o detalhe: o programa instalado é simultaneamente **servidor** (para a interface visual que corre dentro dele) e **cliente** (do serviço na nuvem). É a demonstração perfeita de que cliente e servidor são papéis, não naturezas.

---

### I.4 Frontend vs backend

#### As duas metades

**Frontend** significa literalmente "a parte da frente": tudo o que corre no dispositivo do utilizador e produz o que ele vê e toca. **Backend** é "a parte de trás": tudo o que corre em máquinas controladas por quem opera o sistema, e que o utilizador nunca vê.

A analogia mais útil é um restaurante. A sala é o frontend: mesas, menu, empregado, apresentação do prato. A cozinha é o backend: fornecedores, câmaras frigoríficas, receitas, preparação. O cliente interage só com a sala. Mas se a cozinha falhar, a sala não tem nada para servir — e por muito bonita que a sala seja, ninguém volta se a comida for má.

A analogia esclarece uma coisa importante: as duas metades exigem competências diferentes e otimizam para objectivos diferentes. O frontend preocupa-se com clareza visual, tempo até o utilizador ver algo útil, comportamento em ecrãs de tamanhos diferentes, acessibilidade. O backend preocupa-se com correcção dos dados, permissões, resistência a falhas, e comportamento sob carga.

#### O que a divisão implica na prática

A fronteira entre frontend e backend não é uma questão de gosto; é a fronteira de confiança descrita na secção anterior. Tudo o que está do lado do frontend é público e manipulável; tudo o que está do lado do backend é privado e autoritativo.

Isto tem uma implicação que surpreende quem vem de fora: **o mesmo trabalho é frequentemente feito duas vezes, de propósito**. Uma validação de formulário é implementada no frontend, para dar feedback imediato ao utilizador sem esperar pela rede, e implementada outra vez no backend, porque a do frontend não é uma garantia. Isto não é desperdício nem falta de organização; é a consequência inevitável de o frontend não ser de confiança.

#### Frontend na Diomika

A Diomika tem **dois** frontends, o que é invulgar e vale a pena sublinhar.

O primeiro é a **loja**, em `frontend-web/`. É construída com Vue, uma biblioteca de construção de interfaces. Os seus ecrãs estão em `frontend-web/src/views/` — `HomeView.vue` para a entrada, `CategoriesView.vue` para as categorias, `ProductsView.vue` para as listagens, `ProductDetailView.vue` para a ficha de um produto, `CartView.vue` para a lista de interesse, `ContactView.vue` para o formulário de contacto, `PrivacyView.vue` para a política de privacidade. As peças reutilizáveis estão em `frontend-web/src/components/`, e a lógica partilhada em `frontend-web/src/composables/` e `frontend-web/src/lib/`.

O segundo é o **backoffice**, em `backoffice-desktop/src/`. É também construído com Vue — a mesma tecnologia, a mesma linguagem, competências reutilizáveis — mas embrulhado num programa instalável em vez de servido por um sítio na internet. Os seus ecrãs estão em `backoffice-desktop/src/views/`: `LoginView.vue`, `TableView.vue` para navegar registos, `RecordFormView.vue` para editar, `EncomendasView.vue` para encomendas, `ContactView.vue` para mensagens, `SchemaSyncView.vue` para operações de estrutura de dados.

Uma característica notável do backoffice: os formulários de edição **não estão escritos à mão**. O componente `backoffice-desktop/src/components/SchemaForm.vue` recebe uma descrição da estrutura de dados vinda do backend e constrói o formulário adequado a partir dela. A consequência prática é que acrescentar um campo a um produto não obriga a reescrever o formulário de produtos — a descrição muda, e o formulário acompanha. Esta abordagem, que o projecto chama *schema-driven* (guiada pelo esquema), é uma das decisões estruturantes da Diomika e é tratada em detalhe em parte posterior.

#### Backend na Diomika

O backend vive em `backend-api/`, escrito em Python, e está organizado em camadas com responsabilidades distintas:

- `backend-api/main.py` é a porta de entrada: monta a aplicação, instala as camadas de protecção pela ordem correcta, e registra as famílias de endereços disponíveis.
- `backend-api/routes/` contém os pontos de entrada agrupados por assunto: `categories.py`, `catalog_generic.py`, `contact.py`, `orcamentos.py`, `encomendas.py`, `admin.py`, `admin_crud.py`, `admin_auth.py`, `privacy.py`, `system.py`.
- `backend-api/core/` contém a maquinaria: autenticação, sessões, limitação de ritmo, protecção de caminhos, ligação à base de dados, registo de eventos, alertas, saúde do sistema.
- `backend-api/models/` contém as definições de forma dos dados, que são a fonte de verdade de todo o sistema.
- `backend-api/utils/` contém utilitários concretos: envio de e-mail, geração de documentos, validação de imagens, armazenamento de ficheiros.
- `backend-api/workers/` contém processos que trabalham em segundo plano, sem estar ligados a nenhum pedido.
- `backend-api/sql/` contém a evolução da estrutura da base de dados ao longo do tempo.

#### Onde a fronteira é atravessada

Convém saber exactamente onde é que os dois lados se tocam, porque é nesses pontos que a segurança se aplica.

Na loja, o frontend fala com o backend em dois sítios: `frontend-web/src/lib/api.js`, que envia os pedidos que escrevem algo para `api.diomika.com`; e `frontend-web/src/lib/catalogSupabase.js`, que lê o catálogo directamente do Supabase com a chave pública. No backoffice, o único ponto de contacto é `backoffice-desktop/src/lib/api.js`, que fala com o servidor local dentro do próprio programa, e é esse servidor local — `backoffice-desktop/electron/main.cjs` — que reencaminha para a nuvem acrescentando o cabeçalho de identificação.

Ter estes pontos de contacto reduzidos e nomeados é uma decisão consciente: significa que existe um número pequeno de ficheiros onde se pode auditar toda a comunicação entre lados, em vez de a comunicação estar espalhada por todo o código.

---

### I.5 Domínio, DNS, subdomínios (www vs api)

#### Nomes e números

Todo o computador ligado à internet é identificado por um **IP** — *Internet Protocol address*, ou endereço de Protocolo de Internet. É um número, escrito em partes: `203.0.113.42` no formato antigo e mais comum, ou algo bem mais longo e com dois-pontos no formato moderno. É o equivalente de uma morada postal: identifica um destino na rede de forma inequívoca, e é isso — e só isso — que os equipamentos de rede usam para encaminhar informação.

O problema é que os números não servem para pessoas. São difíceis de memorizar, impossíveis de dizer ao telefone sem erros, e — pior — **mudam**. Um servidor pode ser substituído e receber outro número. Se os clientes soubessem apenas o número, todos teriam de ser avisados.

A solução é o **DNS** — *Domain Name System*, ou Sistema de Nomes de Domínio. É uma lista telefónica distribuída pelo mundo inteiro que traduz nomes legíveis em números. Quando um browser precisa de contactar `www.diomika.com`, pergunta ao DNS "qual é o endereço deste nome?" e recebe um número com que consegue trabalhar. A tradução é invisível, acontece em milissegundos, e é a razão pela qual se pode mudar de servidor sem que ninguém repare.

#### Um domínio é uma propriedade alugada

Um **domínio** é um nome registado, como `diomika.com`. Não se compra: aluga-se, tipicamente ao ano, através de um registador. Quem controla o domínio controla o que os nomes por baixo dele apontam — e essa é uma das chaves mais importantes de qualquer presença na internet. Perder o controlo de um domínio é pior do que perder um servidor: um servidor substitui-se, um nome que os clientes conhecem não.

A leitura de um nome de domínio faz-se **da direita para a esquerda**, do mais geral para o mais específico. Em `www.diomika.com`: `com` é o domínio de topo, a categoria mais ampla; `diomika` é o nome registado dentro dessa categoria; `www` é um **subdomínio**, um nome criado livremente por quem controla `diomika.com`.

#### Subdomínios são de graça e por isso usam-se

Este ponto é frequentemente mal compreendido por quem está fora da área, e é importante: criar subdomínios **não custa nada e não requer autorização de ninguém**. Quem controla `diomika.com` pode criar `api.diomika.com`, `loja.diomika.com`, `interno.diomika.com`, quantos quiser, instantaneamente. Não são domínios novos; são ramos do mesmo domínio.

E cada subdomínio pode apontar para um sítio completamente diferente, gerido por um fornecedor completamente diferente. Esta é a propriedade que torna os subdomínios uma ferramenta de arquitectura e não apenas de nomenclatura.

#### Os dois nomes da Diomika

A Diomika usa dois subdomínios, com papéis deliberadamente separados:

**`www.diomika.com`** — a loja. Aponta para a plataforma de alojamento estático da Cloudflare. Quem abre este nome recebe ficheiros: documentos, código, estilos, imagens. É público, indexado por motores de busca, e desenhado para ser encontrado.

**`api.diomika.com`** — a interface de programação. Aponta, através da rede da Cloudflare, para um túnel que termina na máquina virtual onde corre o backend. Quem abre este nome num browser não recebe uma página; recebe dados, ou uma recusa. Não é para ser visitado por pessoas.

#### Porque separar, em vez de usar um caminho

Uma alternativa técnica óbvia seria não criar um segundo nome e usar em vez disso um caminho dentro do primeiro: `www.diomika.com/api/...`. Muitos sistemas fazem exactamente isso. A Diomika não, e as razões são instrutivas.

**Fornecedores diferentes.** A loja está numa plataforma que serve ficheiros a partir de centenas de localizações no mundo, e que não corre código de servidor tradicional. O backend precisa de correr Python continuamente, com memória entre pedidos e ligações abertas à base de dados. São necessidades incompatíveis, satisfeitas por infra-estruturas diferentes. Dois nomes permitem apontar cada um para onde deve.

**Regras de cache opostas.** Os ficheiros da loja devem ser guardados agressivamente em cópias locais — não mudam, e cada cópia poupada é tempo ganho. As respostas da interface de programação, pelo contrário, quase nunca devem ser guardadas: uma resposta com a lista de pedidos de orçamento não pode ser servida a partir de uma cópia antiga, e muito menos a outra pessoa. Ter nomes separados permite configurar políticas opostas sem ambiguidade.

**Regras de segurança separadas.** A rede da Cloudflare permite aplicar regras por nome. A Diomika aplica em `api.diomika.com` regras que não teriam sentido na loja — como bloquear na fronteira qualquer pedido a caminhos administrativos que não traga o cabeçalho de identificação correcto. Se tudo fosse o mesmo nome, essas regras teriam de distinguir por caminho, o que é mais frágil.

**Clareza operacional.** Quando algo falha, saber se o que falhou foi o nome da loja ou o nome da interface de programação reduz o espaço de diagnóstico à partida. A monitorização da Diomika vigia os dois nomes separadamente, e uma falha num não é confundida com falha no outro.

#### Um detalhe do mundo real: o registo de tempo de vida

Cada resposta do DNS traz consigo um **TTL** — *Time To Live*, ou tempo de vida — que diz durante quanto tempo a resposta pode ser reutilizada sem voltar a perguntar. É uma optimização essencial: sem ela, cada pedido a `www.diomika.com` obrigaria a uma consulta de nomes.

Mas tem uma consequência operacional que morde na prática: **mudanças de DNS não são instantâneas**. Se o nome `api.diomika.com` passar a apontar para outro sítio, os computadores que já tinham a resposta antiga em memória continuam a usá-la até o tempo de vida expirar. Durante esse período — minutos, às vezes mais — parte do mundo vê o destino novo e parte vê o antigo. Qualquer alteração de infra-estrutura da Diomika tem de contar com esta janela de inconsistência. Não é um defeito a corrigir; é uma propriedade do sistema com que se planeia.

#### Na Diomika

A configuração de nomes está descrita em `deploy/cloudflare/dns_plan.json`, que documenta que nomes existem e para onde apontam. As regras de fronteira aplicadas por nome estão em `deploy/cloudflare/waf_rules.json`. Manter estes ficheiros no repositório é uma decisão deliberada: a configuração de rede é parte do sistema, e um sistema cuja configuração vive apenas dentro do painel de um fornecedor é um sistema que ninguém consegue reconstruir se algo se perder.

---

### I.6 HTTP e HTTPS

#### O protocolo que sustenta a web

**HTTP** significa *HyperText Transfer Protocol* — Protocolo de Transferência de Hipertexto. É o conjunto de convenções que browsers e servidores usam para conversar. Foi criado para transferir documentos com ligações entre si, e hoje transporta tudo: páginas, vídeo, dados, comandos de máquinas a máquinas.

Um ponto que ajuda a desmistificar: HTTP é **texto legível**. Não é um formato binário obscuro. Um pedido HTTP, visto em cru, parece isto:

```
GET /api/categories HTTP/1.1
Host: api.diomika.com
Accept: application/json
User-Agent: Mozilla/5.0 (...)
```

E uma resposta parece isto:

```
HTTP/1.1 200 OK
Content-Type: application/json
Content-Length: 1842
Cache-Control: public, max-age=300

{"items": [...]}
```

Toda a web moderna assenta nisto. Perceber esta estrutura é perceber metade das conversas técnicas sobre sistemas web.

#### A anatomia de um pedido

Um pedido HTTP tem quatro partes.

**O método** (`GET`, no exemplo) declara a **intenção**: estou a ler ou estou a mudar algo?

**O caminho** (`/api/categories`) diz **o quê**: qual o recurso em questão.

**Os cabeçalhos** (as linhas seguintes) são metadados — informação sobre o pedido e não o pedido em si. `Host` diz a que nome o pedido se dirige, o que permite a uma máquina servir muitos sítios diferentes. `Accept` diz que formatos o cliente compreende. `User-Agent` identifica o programa que faz o pedido. `Authorization` transporta prova de identidade. Na Diomika, `X-Diomika-Desktop` transporta a prova de que o pedido vem do programa instalado — cabeçalhos com nome próprio, específicos de uma aplicação, são prática normal e é assim que a Diomika o faz.

**O corpo** é o conteúdo enviado, quando existe. Um pedido que apenas lê não tem corpo. Um pedido que cria um orçamento tem no corpo os dados desse orçamento.

#### Os métodos, um a um

Os métodos HTTP existem para que a **intenção** de um pedido seja legível sem interpretar o seu conteúdo. Isso permite que camadas intermédias — caches, servidores de fronteira, sistemas de segurança — tomem decisões correctas sem compreender a aplicação.

**`GET` — ler.** Pede um recurso sem alterar nada. É a operação mais comum da web e a única que pode ser guardada em cache com segurança, repetida sem consequências, e colocada num endereço partilhável. Um `GET` que altere algo é um erro de desenho grave, porque quebra as suposições de toda a infra-estrutura da internet: um sistema que faça pré-carregamento de ligações executaria a alteração sem que ninguém clicasse. Na Diomika, ler categorias, produtos, ou o estado de saúde do sistema são `GET`.

**`POST` — criar ou executar.** Envia dados para que o servidor faça algo: crie um registo, execute uma operação, processe uma submissão. Não é repetível com segurança — dois `POST` idênticos criam, em princípio, duas coisas. É por isso que os browsers avisam antes de reenviar um `POST`. Na Diomika, submeter um contacto, criar um pedido de orçamento, ou fazer login são `POST`.

**`PUT` — substituir.** Coloca um recurso num estado determinado, substituindo-o por inteiro. Tem uma propriedade valiosa chamada **idempotência**: repetir o mesmo `PUT` várias vezes tem o mesmo efeito que fazê-lo uma vez, porque o resultado final é o mesmo estado. Isto torna-o seguro em face de falhas de rede — se não se souber se o pedido chegou, pode-se simplesmente repeti-lo.

**`PATCH` — alterar parcialmente.** Envia apenas os campos que mudam, em vez do recurso completo. É mais eficiente e menos perigoso do que `PUT` quando duas pessoas editam o mesmo registo: quem altera só o preço não apaga inadvertidamente uma descrição que outra pessoa acabou de mudar. O backoffice da Diomika usa alterações parciais para edições de registos, através dos endereços de `backend-api/routes/admin_crud.py`.

**`DELETE` — remover.** Elimina um recurso. Na Diomika, quase nunca significa apagar fisicamente uma linha da base de dados. A prática dominante é marcar como inactivo ou invisível, preservando o histórico — porque num contexto comercial, apagar o produto que consta de uma encomenda antiga destrói informação com valor legal e contabilístico. A excepção deliberada é o apagamento a pedido do titular dos dados, ao abrigo da legislação de protecção de dados, tratado em `backend-api/routes/privacy.py`, onde apagar significa realmente apagar.

**`OPTIONS` — perguntar antes.** Não é usado por pessoas; é usado por browsers, automaticamente, para perguntar a um servidor de outro domínio se determinado pedido é permitido antes de o enviar. É uma peça do mecanismo de partilha entre origens, tratado na Parte sobre protocolos. Aparece nas configurações de `backend-api/main.py` porque tem de ser explicitamente permitido.

#### Os códigos de estado

Toda a resposta HTTP começa com um número de três dígitos que diz, de forma padronizada, o que aconteceu. O primeiro dígito dá a família:

- **2xx** — correu bem.
- **3xx** — está noutro sítio, vai lá.
- **4xx** — o pedido está errado; o problema é de quem pediu.
- **5xx** — o pedido podia estar certo; o problema é de quem respondeu.

A distinção entre 4xx e 5xx é a mais importante de todas em operação de sistemas, porque determina **quem tem de agir**. Um aumento de erros 4xx é normalmente um problema de integração, de um cliente mal configurado, ou de alguém a sondar o sistema. Um aumento de erros 5xx é um problema **nosso** e exige intervenção imediata. Toda a monitorização da Diomika trata estas duas famílias de forma diferente, e só a segunda gera alertas urgentes.

Os códigos que mais importam na Diomika:

**`200 OK`** — pedido bem-sucedido, resposta no corpo. O caso normal de uma leitura.

**`201 Created`** — recurso criado. Resposta correcta a um `POST` que cria algo, como um pedido de orçamento.

**`204 No Content`** — correu bem e não há nada para devolver. Típico de um apagamento.

**`304 Not Modified`** — "o que tens em cache continua válido". O browser tinha uma cópia, perguntou se mudou, e o servidor diz que não. Poupa transferência inteira do conteúdo.

**`400 Bad Request`** — o pedido é malformado ao ponto de não ser interpretável.

**`401 Unauthorized`** — falta identificação, ou a identificação é inválida. O nome é historicamente infeliz: significa "não autenticado", não "não autorizado". Na Diomika, é o que se recebe ao chamar um endereço administrativo sem um token de sessão válido, ou com um token expirado. Quando o backoffice recebe 401, a interpretação correcta é "a sessão caiu, é preciso voltar a entrar" — e é isso que `backoffice-desktop/src/lib/api.js` faz.

**`403 Forbidden`** — a identidade é conhecida mas não tem permissão. A diferença face ao 401 é essencial: 401 significa "não sei quem és", 403 significa "sei quem és e não podes". Confundir os dois na implementação leva a interfaces que pedem login a quem já está autenticado, uma frustração clássica.

**`404 Not Found`** — o recurso não existe. Na Diomika, este código tem um uso adicional que é uma decisão de segurança consciente: caminhos administrativos respondem `404` — e não `403` — quando o pedido não vem de uma origem legítima. A diferença é subtil e importante. Um `403` confirma que o caminho existe e que há algo protegido para atacar. Um `404` não confirma nada. Esta técnica — **não revelar a existência do que se protege** — está implementada em `backend-api/core/path_guard.py` e testada em `backend-api/tests/test_path_guard_hardening.py`.

**`422 Unprocessable Entity`** — o pedido está bem formado e é compreensível, mas o **conteúdo** não passa as regras de validação: falta um campo obrigatório, um valor tem o tipo errado, um e-mail não tem forma de e-mail. É o código que a framework usada pela Diomika devolve automaticamente quando os dados não correspondem à forma declarada, e a resposta indica exactamente que campos falharam.

Este código tem uma história importante no projecto, que ilustra bem como bugs subtis se manifestam. Numa fase do desenvolvimento, tentativas de login legítimas começaram a receber `422` com a indicação de que o campo da palavra-passe estava em falta — apesar de o programa o estar claramente a enviar. A causa não estava na validação nem no formulário: estava numa camada intermédia que limitava o tamanho dos pedidos e que, para o medir, **lia o corpo do pedido**. Como o corpo de um pedido só pode ser lido uma vez, quando a validação chegava ao seu turno já não havia nada para ler, e concluía correctamente que o campo faltava. A correcção foi deixar de ler o corpo e passar a confiar no cabeçalho que declara o seu tamanho. Está em `backend-api/core/middleware.py` e é discutida em detalhe na Parte sobre decisões de engenharia.

**`429 Too Many Requests`** — demasiados pedidos em demasiado pouco tempo. É a resposta da limitação de ritmo, e é um sinal de saúde, não de doença: significa que uma protecção está a funcionar. Na Diomika há limites globais e limites específicos, sendo os mais estritos os do login administrativo, contados simultaneamente por endereço de origem e por nome de utilizador.

**`500 Internal Server Error`** — algo correu mal dentro do servidor de forma imprevista. Na Diomika, em produção, a resposta ao cliente é deliberadamente vaga — apenas `{"detail": "Erro interno"}` — enquanto o detalhe completo, com o rastreio da falha, vai para os registos e para o sistema de captura de erros. A razão é que mensagens de erro detalhadas são informação valiosa para quem ataca: revelam versões de bibliotecas, caminhos de ficheiros, estrutura de tabelas. Este comportamento está em `backend-api/main.py`, no tratador global de excepções, que muda de comportamento consoante o ambiente.

**`502 Bad Gateway`** e **`503 Service Unavailable`** — a peça que atendeu o pedido não conseguiu obter resposta de quem estava atrás dela, ou o serviço não está em condições de responder. Na topologia da Diomika, um `502` em `api.diomika.com` tem um significado muito específico e muito útil: a rede da Cloudflare está de pé, mas **não conseguiu falar com a máquina virtual através do túnel**. Ou o túnel caiu, ou o contentor da aplicação está em baixo, ou a máquina reiniciou. Distinguir isto de um `500` — em que a aplicação está viva e falhou internamente — poupa tempo real de diagnóstico. O endereço `/health/ready` da Diomika responde `503` quando a aplicação está viva mas a base de dados não está acessível, permitindo distinguir "arrancou" de "está pronta para trabalhar".

#### HTTPS: o mesmo protocolo, dentro de um envelope selado

**HTTPS** é *HyperText Transfer Protocol Secure* — o mesmo HTTP, transportado dentro de um canal encriptado. O "S" final não muda nada na gramática do protocolo: os métodos são os mesmos, os cabeçalhos são os mesmos, os códigos são os mesmos. O que muda é que ninguém no caminho consegue ler nem alterar o que passa.

A diferença entre HTTP e HTTPS é a diferença entre um postal e uma carta registada em envelope selado. O postal viaja e todos os que o manuseiam podem ler o que está escrito — e, com um pouco de ousadia, riscar e reescrever. O envelope selado chega como saiu, e é detectável se alguém o tiver aberto.

"Todos os que o manuseiam" não é uma figura de estilo. Um pedido HTTP entre um browser em Lisboa e um servidor na Bélgica passa fisicamente por muitos equipamentos: o router de casa, a rede do operador, pontos de troca de tráfego, redes intermédias. Sem encriptação, qualquer um deles vê tudo — incluindo palavras-passe e dados pessoais — e qualquer um deles pode injectar conteúdo.

Hoje HTTPS não é uma opção. Os browsers marcam sítios sem encriptação como não seguros, recusam funcionalidades modernas a páginas não encriptadas, e mostram avisos que afastam visitantes. Não usar HTTPS é, na prática, não estar na web.

Na Diomika, **todo** o tráfego público é HTTPS. `www.diomika.com` e `api.diomika.com` só aceitam ligações encriptadas. Pedidos que cheguem sem encriptação são redireccionados. A única excepção é interna e não atravessa a internet: dentro da máquina virtual, o túnel entrega o pedido à aplicação através de uma ligação local não encriptada, em `127.0.0.1:8000`. Essa ligação nunca sai da máquina — encriptá-la seria encriptar uma conversa entre dois programas no mesmo computador, com custo real e benefício nulo.

#### Na Diomika

Os endereços do backend estão organizados por famílias, em `backend-api/routes/`, e a lista completa pode ser inspeccionada num documento de descrição automática que a framework gera — quando essa função está activada, o que em produção é controlado por configuração. As camadas que examinam cada pedido antes de ele chegar ao seu destino estão em `backend-api/core/middleware.py` e `backend-api/core/path_guard.py`. Os cabeçalhos de segurança que o backend acrescenta a cada resposta estão na mesma camada, e os que a loja envia estão declarados em `frontend-web/public/_headers`.

---

### I.7 TLS / SSL (encriptação em trânsito, certificados, e porque a Cloudflare termina a encriptação)

#### Dois nomes, uma tecnologia

**SSL** significa *Secure Sockets Layer* — Camada de Sockets Segura. **TLS** significa *Transport Layer Security* — Segurança da Camada de Transporte. São, na prática corrente, a mesma coisa: SSL é o nome original, criado nos anos 90; TLS é o nome do sucessor, tecnicamente diferente e muito mais seguro.

Todas as versões de SSL estão obsoletas e desactivadas há anos por serem inseguras. Tudo o que hoje funciona é TLS — actualmente nas versões 1.2 e 1.3. Mas o nome "SSL" ficou preso na linguagem da indústria: continua-se a dizer "certificado SSL" quando se quer dizer "certificado TLS", e a maioria dos fornecedores usa os dois termos como sinónimos nos seus painéis.

**Neste relatório:** quando aparecer "SSL", é uma referência ao nome histórico. O que a Diomika realmente usa é **TLS**, na versão que o browser do visitante e a rede da Cloudflare negociarem, sendo a mais recente a preferida.

#### O que a encriptação em trânsito garante — e o que não garante

Encriptação **em trânsito** significa: os dados são ilegíveis enquanto viajam pela rede. É diferente de encriptação **em repouso**, que significa que os dados são ilegíveis enquanto estão guardados em disco. São problemas distintos com soluções distintas, e confundi-los leva a conclusões erradas sobre o nível de protecção de um sistema.

O TLS resolve três problemas, e é útil enumerá-los porque são frequentemente amalgamados numa noção vaga de "segurança":

**1. Confidencialidade.** Ninguém no caminho consegue ler o conteúdo. O que passa pelos equipamentos intermédios é ruído indistinguível de aleatório.

**2. Integridade.** Ninguém no caminho consegue **alterar** o conteúdo sem que a alteração seja detectada. Isto é tão importante como a confidencialidade e muito menos discutido. Sem integridade, um equipamento intermédio poderia injectar código malicioso numa página legítima, ou trocar um número numa resposta de dados. Foi um problema real e generalizado com operadores de rede a injectar publicidade em páginas não encriptadas.

**3. Autenticidade.** O cliente tem prova de que está a falar com quem pensa estar a falar, e não com um impostor que se colocou no meio. É isto que os certificados fazem.

E o que o TLS **não** garante, e vale a pena ser explícito porque é fonte de mal-entendidos: não garante que o sítio do outro lado seja honesto; não garante que os dados estejam bem guardados depois de chegarem; não protege contra ninguém que tenha acesso legítimo a um dos extremos. Um cadeado no browser diz "esta conversa é privada e é com quem diz ser" — não diz "esta entidade é de confiança".

#### Certificados e cadeias de confiança

Um **certificado** TLS é um ficheiro que diz, essencialmente: "a chave criptográfica pública X pertence ao nome `api.diomika.com`", assinado por uma entidade em quem os browsers já confiam.

A engenharia por trás disto resolve um problema aparentemente impossível: como pode um browser que nunca viu `diomika.com` verificar que está a falar com o servidor certo? A resposta é uma **cadeia de confiança**. Todo o sistema operativo e todo o browser vêm com uma lista pré-instalada de algumas centenas de **autoridades de certificação** — entidades auditadas cujas assinaturas são aceites por omissão. Quando um servidor apresenta um certificado, o browser verifica se a assinatura foi feita por uma dessas autoridades, ou por alguém em quem uma dessas autoridades confie. Se a cadeia fechar até um ponto de confiança conhecido, o certificado é aceite.

Um certificado tem sempre **validade limitada** — hoje tipicamente semanas ou poucos meses. Isto é deliberado: limita a janela de exploração de uma chave comprometida e força a renovação automatizada. Um certificado expirado torna um sítio inacessível com um aviso alarmante, e é uma das causas mais comuns e mais evitáveis de indisponibilidade em sistemas web. Na Diomika, os certificados são **geridos pela Cloudflare**, emitidos e renovados automaticamente. Não existe processo manual de renovação, e portanto não existe a possibilidade de alguém se esquecer.

#### O aperto de mão

Antes de qualquer conteúdo ser trocado, cliente e servidor executam um **aperto de mão** (*handshake*), que consiste em:

1. O cliente anuncia que versões de TLS e que algoritmos suporta.
2. O servidor escolhe a melhor combinação comum e apresenta o seu certificado.
3. O cliente verifica o certificado contra a cadeia de confiança e contra o nome pedido.
4. Ambos derivam, através de troca de chaves, um segredo compartilhado que **nenhum observador da conversa consegue calcular**, mesmo tendo gravado tudo.
5. A partir daí, tudo o que passa é encriptado com esse segredo.

O passo 4 é a parte contra-intuitiva e brilhante: é possível dois interlocutores acordarem um segredo comum trocando mensagens em público, de tal forma que quem ouviu toda a conversa não consegue deduzir o segredo. Uma propriedade importante das versões modernas é o **sigilo futuro** (*forward secrecy*): o segredo de cada sessão é descartado no fim, e portanto mesmo que a chave privada do servidor seja comprometida mais tarde, as conversas gravadas no passado continuam indecifráveis.

Este aperto de mão custa tempo — uma ou duas idas e voltas na rede antes de qualquer dado útil. Numa ligação intercontinental, isso pode ser centenas de milissegundos. É por esta razão que a proximidade geográfica do ponto onde a encriptação termina tem impacto real na velocidade percebida, e é uma das razões pelas quais a arquitectura da Diomika é como é.

#### Terminação de TLS: onde o envelope é aberto

**Terminar TLS** significa ser o ponto onde a encriptação é desfeita e o conteúdo volta a ser legível para ser processado. Alguém tem de o fazer — de outro modo ninguém pode agir sobre o pedido.

Na Diomika, **quem termina o TLS é a Cloudflare**, na localização da sua rede mais próxima do visitante. O caminho completo é:

```
Browser do visitante
   │  HTTPS (TLS terminado aqui) ──► Cloudflare, ponto de presença mais próximo
   │
   │  Túnel autenticado e encriptado, iniciado de dentro para fora
   ▼
cloudflared, a correr dentro da máquina virtual
   │  HTTP em loopback, dentro da mesma máquina
   ▼
127.0.0.1:8000 — a aplicação FastAPI
```

Esta escolha tem quatro justificações concretas.

**Latência.** A Cloudflare tem centenas de localizações. Um visitante em Lisboa faz o aperto de mão com um equipamento em Lisboa, não com uma máquina que pode estar noutro continente. As idas e voltas caras acontecem numa distância curta.

**Gestão automática de certificados.** Emissão, renovação e configuração são responsabilidade do fornecedor. Uma classe inteira de falhas operacionais — a mais comum das quais é o certificado expirado — deixa de ser possível.

**Filtragem antes da origem.** Se o TLS fosse terminado na máquina virtual, essa máquina tinha de gastar processamento em cada aperto de mão, incluindo os de robôs a sondar e os de ataques de volume. Numa máquina da camada gratuita, com memória e processamento muito limitados, isso é um problema real. Ao terminar na fronteira, a Cloudflare processa, filtra, aplica regras de segurança, e só encaminha o que sobrevive.

**Ausência de portas abertas.** Terminar TLS na máquina exigiria uma porta pública aberta na internet, com um endereço fixo e regras de firewall. O modelo de túnel elimina isso por completo: a máquina virtual **não aceita ligações de fora**. A ligação é estabelecida **de dentro para fora** pelo programa `cloudflared`, que se liga à rede da Cloudflare e mantém essa ligação aberta. Não há nada a que um atacante possa ligar-se directamente, porque não há nada à escuta na internet. Uma varredura de portas ao endereço da máquina não encontra a interface de programação, porque ela não está lá exposta.

#### O trecho não encriptado, e porque é aceitável

Um leitor atento nota que existe um segmento sem encriptação: entre o `cloudflared` e a aplicação, em `127.0.0.1:8000`. Isso é uma vulnerabilidade?

Não, e a razão é geográfica. `127.0.0.1` é o endereço de **loopback** — o nome que um computador dá a si próprio. Tráfego para `127.0.0.1` nunca sai da máquina; nem toca na placa de rede. É comunicação entre dois programas no mesmo computador, mediada pelo sistema operativo.

Para interceptar esse tráfego seria necessário já ter execução de código dentro da máquina virtual. E quem tem execução de código dentro da máquina tem acesso directo ao ficheiro de configuração com todas as credenciais — encriptar a comunicação local não protegeria de nada. Encriptar tráfego de loopback é um custo real (processamento, complexidade, mais certificados a gerir) sem qualquer benefício de segurança correspondente. A decisão de não o fazer é uma decisão bem fundamentada, não uma omissão.

#### HSTS: fechar a porta ao primeiro pedido

Há uma falha residual no modelo: se um visitante escrever `diomika.com` sem indicar o protocolo, o browser tenta HTTP primeiro. Esse primeiro pedido, antes do redireccionamento, viaja sem protecção e é vulnerável.

**HSTS** — *HTTP Strict Transport Security*, ou Segurança Estrita de Transporte — resolve isto. É um cabeçalho que o servidor envia dizendo: "durante os próximos N segundos, nunca me contactes sem encriptação, mesmo que te peçam". O browser guarda essa instrução e, a partir daí, converte internamente qualquer tentativa de HTTP em HTTPS **antes** de enviar qualquer coisa. A janela de vulnerabilidade fecha.

Na Diomika este cabeçalho está declarado em `frontend-web/public/_headers` com um período de um ano, aplicando-se a todos os subdomínios, e com a indicação `preload` — que significa que o domínio pode ser incluído numa lista distribuída com os próprios browsers, eliminando a vulnerabilidade até no primeiro contacto de sempre. O backend aplica o mesmo cabeçalho às suas respostas em produção, através de `backend-api/core/middleware.py`.

Uma nota de prudência operacional: o HSTS é **difícil de reverter**. Uma vez que os browsers guardaram a instrução, ela vigora pelo período declarado, e não há forma de a cancelar retroactivamente nos browsers que já a receberam. Se um domínio com HSTS activo perder a capacidade de servir HTTPS, torna-se inacessível — não degradado, inacessível. É uma protecção que se activa com intenção e não por acidente.

---

### I.8 JSON (o formato de dados da API)

#### O problema que resolve

Quando um programa precisa de enviar informação estruturada a outro programa, tem de a converter numa sequência de caracteres ou bytes que possa viajar pela rede, e o receptor tem de a reconstruir do outro lado. Este par de operações chama-se serialização e desserialização, e exige que ambos os lados concordem num formato.

**JSON** — *JavaScript Object Notation*, ou Notação de Objectos JavaScript — é hoje o formato dominante para essa troca. Nasceu como a forma de escrever estruturas de dados na linguagem JavaScript, e tornou-se universal porque tem uma combinação rara de propriedades: é legível por humanos, simples de gerar e interpretar, e suportado nativamente por todas as linguagens de programação relevantes.

#### A forma

Um exemplo, ilustrativo, do género de estrutura que a interface de programação da Diomika devolve:

```json
{
  "id": "8f3a1c2e-4b5d-4e6f-9a7b-0c1d2e3f4a5b",
  "referencia": "ALM-LX-40",
  "nome": "Almofada Lisboa 40x40",
  "categoria": "almofadas-decorativas",
  "visivel": true,
  "stock_disponivel": null,
  "dimensoes": {
    "largura_cm": 40,
    "altura_cm": 40,
    "profundidade_cm": 12
  },
  "cores": ["areia", "terracota", "azul-atlantico"],
  "imagens": [
    { "ordem": 1, "path": "produtos/alm-lx-40/frente.webp" },
    { "ordem": 2, "path": "produtos/alm-lx-40/perfil.webp" }
  ]
}
```

Os valores acima são inventados para ilustração. O que importa é a **gramática**, que é minúscula. Existem exactamente seis tipos:

**Objecto** — um conjunto de pares nome/valor, entre chaves. É o equivalente de um registo ou de uma ficha: o produto acima é um objecto.

**Lista** — uma sequência ordenada de valores, entre parênteses rectos. `"cores"` é uma lista de textos; `"imagens"` é uma lista de objectos.

**Texto** — caracteres entre aspas duplas. Sempre aspas duplas; JSON não aceita aspas simples, o que é uma das causas mais frequentes de erro de sintaxe para quem vem de outras linguagens.

**Número** — inteiro ou decimal, sem aspas. `40` é número; `"40"` é texto. Esta distinção é rígida e importa: comparações e ordenações comportam-se de forma diferente.

**Booleano** — `true` ou `false`, em minúsculas, sem aspas.

**Nulo** — `null`, que significa "este campo existe e o seu valor é explicitamente desconhecido ou não aplicável". É semanticamente diferente de zero, de texto vazio, e de campo ausente — uma distinção que causa bugs quando é ignorada. No exemplo, `"stock_disponivel": null` diz "não há informação de stock", que não é o mesmo que "stock igual a zero".

Estes seis tipos podem ser encaixados uns nos outros sem limite de profundidade. É toda a linguagem. Não há datas, não há dinheiro, não há tipos definidos pelo utilizador, não há comentários. Essa pobreza deliberada é a força do formato: há muito pouco sobre que dois sistemas possam discordar.

#### As ausências que causam problemas na prática

Duas ausências merecem menção porque afectam a Diomika directamente.

**Não existe tipo de data.** Uma data em JSON é texto, e a única forma sã de o fazer é usar o formato normalizado internacional — `"2026-08-14T17:43:00Z"` — que é ordenável alfabeticamente, não ambíguo quanto à ordem de dia e mês, e explícito quanto ao fuso. Datas escritas como `"14/08/2026"` são uma armadilha, porque a mesma sequência significa coisas diferentes em convenções diferentes.

**Não existem comentários.** Não é possível anotar um documento JSON. É a razão pela qual ficheiros de configuração destinados a serem lidos e editados por pessoas raramente usam JSON puro, e é a razão pela qual a documentação sobre a forma dos dados tem de viver noutro lugar — no caso da Diomika, em `backend-api/models/schemas.py`, que é simultaneamente a definição executável e a documentação.

#### Na Diomika: o esquema é a fonte de verdade

A Diomika usa JSON como formato único de troca em toda a comunicação entre programas: da loja para o backend, do backoffice para o backend, do backend para o Supabase, e nos registos de eventos que o backend produz.

Mas há uma decisão de arquitectura mais interessante do que a simples escolha do formato. A forma de cada estrutura de dados está **declarada uma única vez**, em `backend-api/models/schemas.py`, usando uma biblioteca de validação que transforma essas declarações em verificações executadas em cada pedido. Dessa declaração única derivam, automaticamente:

1. **A validação de entrada.** Qualquer pedido cujo conteúdo não corresponda à forma declarada é rejeitado com `422` e uma indicação precisa de que campos falharam e porquê. O código da aplicação nunca vê dados malformados, porque eles não chegam lá.

2. **A documentação da interface.** A framework gera automaticamente um documento que descreve todos os endereços, os seus parâmetros e as suas respostas. É a descrição da interface sem esforço de escrita e sem risco de ficar desactualizada, porque é derivada do próprio código.

3. **Os formulários do backoffice.** O backend expõe a descrição da forma dos dados, e `backoffice-desktop/src/components/SchemaForm.vue` constrói o formulário a partir dela. Acrescentar um campo a um produto não exige tocar no formulário.

4. **A estrutura da base de dados.** Existe maquinaria — `backend-api/core/schema_engine.py` — que compara a forma declarada com a estrutura real das tabelas e ajuda a mantê-las alinhadas.

O valor desta abordagem é a eliminação de uma classe inteira de bugs: a **divergência** entre o que a base de dados guarda, o que a interface de programação aceita, e o que o formulário mostra. Em sistemas onde estas três coisas são escritas e mantidas separadamente, elas divergem — é uma questão de tempo, não de disciplina. Na Diomika, derivam de uma origem comum.

#### Registos em JSON

Uma aplicação do formato que não é óbvia: os **registos de eventos** do backend, em produção, são emitidos em JSON e não em texto corrido. Cada linha de registo é um objecto com campos nomeados — momento, gravidade, identificador do pedido, caminho, código de resposta, duração.

A vantagem é enorme para operação. Registos em texto corrido só se podem ler ou procurar por palavras. Registos estruturados podem ser **consultados**: "mostra-me todos os pedidos que demoraram mais de dois segundos, agrupados por caminho, nas últimas seis horas". É a diferença entre um diário e uma base de dados. A implementação está em `backend-api/core/structured_logging.py`, e o comportamento é automático: em produção o formato JSON é activado por omissão, em desenvolvimento fica texto legível, salvo indicação contrária.

Complementarmente, `backend-api/core/log_safe.py` instala filtros que removem valores sensíveis dos registos antes de serem escritos. Um registo é um sítio onde segredos aparecem por acidente — alguém registra um objecto inteiro que por acaso contém um token — e é um sítio de onde não se apagam facilmente, porque foram copiados para sistemas externos. Filtrar à saída é uma protecção estrutural contra um erro humano previsível.

---

### I.9 API REST (o que é uma interface de programação; o que é REST na prática)

#### O que é uma API

**API** significa *Application Programming Interface* — Interface de Programação de Aplicações. É o conjunto de operações que um programa oferece a outros programas.

A analogia mais esclarecedora é a **tomada eléctrica**. A tomada é uma interface: define uma forma física, uma tensão, uma frequência. Qualquer aparelho que respeite essa especificação funciona. Nem o aparelho precisa de saber como a electricidade é gerada, nem a central precisa de saber que aparelhos existem. Os dois lados evoluem independentemente porque o contrato entre eles é estável e público.

Uma interface de programação faz o mesmo para software. Diz: "existem estas operações, aceitam estes dados nesta forma, devolvem estes resultados nesta forma". Quem a usa não precisa de saber como está implementada, que linguagem usa, ou que base de dados tem por baixo. E — o ponto crucial — a implementação pode ser inteiramente reescrita sem que nenhum consumidor tenha de mudar, desde que o contrato se mantenha.

Isto não é abstracção pela abstracção; é o que permite que a Diomika tenha duas aplicações muito diferentes — uma loja no browser e um programa instalado — a usar a mesma lógica de negócio sem duplicação. Se as regras de criação de um orçamento estivessem escritas dentro de cada uma, existiriam duas versões dessas regras, e elas divergiriam.

#### O que é REST

**REST** significa *Representational State Transfer* — Transferência de Estado Representacional. É um **estilo** de desenho de interfaces web, descrito em 2000, que consiste essencialmente em usar a web da forma para que ela foi feita, em vez de a usar como um simples canal de transporte.

Na prática, uma interface no estilo REST caracteriza-se por:

**1. Os endereços identificam coisas, não acções.** `/api/produtos/ALM-LX-40` identifica um produto. Não é uma instrução; é a identificação de um recurso. A acção vem do método HTTP: `GET` nesse endereço lê o produto, `PATCH` altera-o, `DELETE` remove-o. Isto é o oposto do estilo em que os endereços são verbos — `/obterProduto`, `/actualizarProduto`, `/apagarProduto` — que obriga a inventar um nome para cada operação e ignora completamente a semântica que o HTTP já oferece.

**2. Os métodos HTTP transportam a intenção.** As garantias descritas na secção I.6 aplicam-se: `GET` não altera nada e pode ser guardado em cache; `PUT` pode ser repetido em segurança; `POST` não. Estas propriedades são exploradas por toda a infra-estrutura da internet.

**3. Não há estado de conversa no servidor.** Cada pedido é autónomo e transporta toda a informação necessária para ser compreendido, incluindo a identificação de quem o faz. O servidor não mantém uma sessão em memória associada a um cliente. Isto é o que permite correr várias instâncias da aplicação sem que os pedidos tenham de ir sempre à mesma.

**4. Os códigos de estado são usados corretamente.** `404` significa não existe. `422` significa dados inválidos. `401` significa não autenticado. Uma interface que responde `200 OK` com um corpo a dizer `{"erro": "não encontrado"}` está a desperdiçar o mecanismo padronizado e a obrigar cada consumidor a inventar a sua própria interpretação.

**5. Representações negociadas.** O mesmo recurso pode ser servido em formatos diferentes conforme o que o cliente pede. Na Diomika, o formato é quase sempre JSON, com a excepção notável dos documentos gerados em formato de impressão.

#### Uma nota de honestidade sobre "REST"

Convém dizer, porque este relatório se propõe não vender fumo: praticamente nenhuma interface descrita como "REST" na indústria cumpre a definição académica completa do termo. A definição original inclui exigências — nomeadamente que um cliente possa descobrir todas as operações disponíveis navegando a partir de um ponto de entrada, sem conhecimento prévio — que quase ninguém implementa, porque o custo é alto e o benefício raramente se materializa.

O que a indústria chama REST, e o que a Diomika implementa, é o conjunto de práticas pragmáticas listadas acima: endereços que identificam recursos, métodos HTTP com semântica respeitada, JSON como formato, códigos de estado usados corretamente, ausência de estado de conversa. É um estilo consistente e bem compreendido, e chamá-lo REST é a convenção aceite. Não é a definição estrita, e a diferença não tem consequências práticas.

#### A interface da Diomika, por famílias

Os endereços do backend estão agrupados por assunto em `backend-api/routes/`, e a divisão reflecte níveis de acesso muito diferentes:

**Catálogo público** — `categories.py`, `catalog_generic.py`. Leitura de categorias, produtos, modelos e cores. Acessível sem qualquer autenticação, porque o catálogo é informação comercial destinada a ser vista. As respostas trazem instruções de cache, aplicadas por uma camada dedicada, porque dados de catálogo mudam raramente e podem ser reutilizados.

**Submissões públicas** — `contact.py`, `orcamentos.py`. Recebem o que os visitantes enviam. São os endereços mais expostos do sistema: aceitam conteúdo de qualquer pessoa no mundo. Consequentemente, são os mais protegidos — verificação anti-robô, limitação de ritmo, validação estrita de conteúdo, e mecanismos que impedem que uma submissão repetida crie registos duplicados.

**Autenticação administrativa** — `admin_auth.py`. Login, renovação e encerramento de sessão. Sujeito a limites de ritmo particularmente estritos, contados por endereço de origem e por nome de utilizador simultaneamente, e a bloqueio temporário após falhas consecutivas.

**Administração** — `admin.py`, `admin_crud.py`. Criação, leitura, alteração e remoção de todos os registos do sistema. Protegido por três camadas independentes: a regra de fronteira na rede da Cloudflare, a verificação do cabeçalho de identificação do programa instalado, e a exigência de um token de sessão válido.

**Encomendas** — `encomendas.py`. Registo e acompanhamento de encomendas, e geração de documentos de encomenda.

**Sistema** — `system.py`. Operações de manutenção e diagnóstico. Restrito.

**Privacidade** — `privacy.py`. Pedidos de acesso e de apagamento de dados pessoais, ao abrigo da legislação aplicável. É um dos poucos lugares do sistema onde apagar significa realmente apagar.

**Saúde** — declarados directamente em `backend-api/main.py`. Três endereços com finalidades distintas: `/health` responde publicamente com o mínimo — está viva, e que versão corre; `/health/ready` responde se a aplicação está em condições de trabalhar, devolvendo `503` se a base de dados não estiver acessível; `/health/detail` devolve informação diagnóstica completa e está **restrito**, exigindo origem local ou credencial de operações.

Esta gradação dos endereços de saúde é uma decisão de segurança que vale a pena sublinhar. Um endereço de saúde é útil para a monitorização e, exactamente pela mesma razão, útil para quem sonda: revela versões de bibliotecas, que serviços estão ligados, se há base de dados, se há cache. A solução da Diomika é dar publicamente apenas o suficiente para a monitorização automática funcionar, e esconder o resto atrás de autorização.

#### Descrição automática da interface

A framework usada pelo backend gera automaticamente um documento que descreve toda a interface — todos os endereços, os parâmetros que aceitam, a forma das respostas, os códigos de erro possíveis. Esse documento segue uma norma da indústria chamada **OpenAPI**, e existem ferramentas que o transformam em documentação navegável e testável no browser.

Na Diomika, a disponibilidade destes documentos é **controlada por configuração**, e em produção final desligada. A razão está em `backend-api/main.py`: os caminhos da documentação só são registados se a definição correspondente estiver activa. A justificação é a mesma dos endereços de saúde — uma descrição completa e legível de todas as operações de um sistema é uma ferramenta de desenvolvimento excelente e um mapa de reconhecimento excelente. Em desenvolvimento, é indispensável. Em produção, é informação que não precisa de estar disponível ao mundo.

---

### I.10 SPA — Single-Page Application (Vue na loja)

#### O modelo antigo

Na web original, cada interacção era uma viagem completa. Clicar numa ligação enviava um pedido, o servidor construía um documento HTML inteiro, o browser descartava tudo o que tinha e desenhava o novo documento de novo. Cada clique era um ecrã branco e um recomeço.

Este modelo tem virtudes que não devem ser desprezadas — é simples, robusto, funciona sem código a correr no cliente, e é perfeitamente indexável por motores de busca. Para conteúdo que se lê, continua a ser frequentemente a escolha certa. Mas para algo que se **usa** — navegar um catálogo, filtrar, comparar, montar uma lista — a recarga constante é lenta e desconfortável, e perde todo o estado a cada passo.

#### O modelo de aplicação de página única

Uma **SPA** — *Single-Page Application*, ou Aplicação de Página Única — inverte a relação. O browser carrega **uma vez** um documento praticamente vazio e um programa em JavaScript. A partir daí, é esse programa que manda: apanha os cliques, decide o que mostrar, vai buscar apenas os **dados** de que precisa, e reescreve as partes do ecrã que mudam. O documento nunca é recarregado.

O nome é literal: existe um único documento HTML, servido em qualquer endereço. Em `frontend-web/index.html` está esse documento, e ele é essencialmente uma âncora vazia onde o programa se instala.

As consequências para quem usa são imediatas. A navegação entre ecrãs é instantânea, porque não há viagem ao servidor para obter estrutura — apenas, quando necessário, para obter dados. O estado sobrevive à navegação: a lista de interesse que um comprador montou não se perde ao navegar para outra categoria e voltar. E as transferências são muito menores, porque o que viaja são dados, não documentos completos com toda a estrutura repetida.

#### Rotas do lado do cliente, e o problema que criam

Numa aplicação de página única, os endereços continuam a existir e a funcionar — `www.diomika.com/produtos/almofadas` é um endereço válido, partilhável, que se pode marcar como favorito. Mas quem o interpreta é o programa no browser, não o servidor. O programa observa o endereço, decide que ecrã corresponde, e desenha-o. Isto chama-se **roteamento do lado do cliente**, e na Diomika está definido em `frontend-web/src/router/index.js`.

Há uma complicação prática e não óbvia. Se um comprador abrir directamente `www.diomika.com/produtos/almofadas` — vindo de um e-mail, ou de um resultado de busca — o browser pede esse caminho ao servidor **antes** de o programa existir. E do lado do servidor não existe nenhum ficheiro nesse caminho: só existe `index.html`.

A solução é configurar o alojamento para responder com `index.html` a qualquer caminho que não corresponda a um ficheiro real. O programa arranca, lê o endereço, e desenha o ecrã certo. Na Diomika isso está declarado em `frontend-web/public/_redirects`. É uma dessas configurações de uma linha cuja ausência produz um sintoma desconcertante: o sítio funciona perfeitamente quando se navega por dentro, e dá erro quando se abre uma ligação directa.

#### Vue e Vite

**Vue** é a biblioteca que a Diomika usa para construir os seus dois frontends. O seu contributo central é a ligação automática entre dados e ecrã: em vez de o programador escrever instruções para actualizar o ecrã quando um valor muda, declara qual é a relação entre os dados e o que se vê, e a biblioteca encarrega-se de manter os dois em sincronia. É uma diferença de paradigma com consequências grandes na quantidade de código e na quantidade de bugs de inconsistência visual.

O código escreve-se em componentes — ficheiros com extensão `.vue` que contêm, no mesmo sítio, a estrutura, o comportamento e o estilo de uma peça da interface. Um componente como `frontend-web/src/components/QtySelect.vue` encapsula tudo o que é preciso saber sobre a selecção de quantidades, e pode ser usado em qualquer ecrã.

**Vite** é a ferramenta que transforma o código-fonte em ficheiros que um browser sabe usar. Faz duas coisas muito diferentes. Em desenvolvimento, corre um servidor local que aplica alterações no ecrã quase instantaneamente, sem perder o estado da aplicação — o que muda materialmente a velocidade de trabalho. Em construção para produção, compila tudo para um conjunto optimizado de ficheiros: código minimizado, dividido por rotas para que uma primeira visita não descarregue a aplicação inteira, e com nomes que incluem uma impressão digital do conteúdo.

Esse último detalhe merece explicação porque resolve elegantemente um problema real. Um ficheiro chamado `index-a3f5c1.js` tem no nome uma impressão digital do seu conteúdo. Se o conteúdo mudar, o nome muda. Isto permite instruir os browsers a guardar esses ficheiros **para sempre** — um ano, imutáveis — com total segurança, porque uma nova versão terá um nome diferente e será pedida como se fosse um ficheiro novo. É a razão pela qual `frontend-web/public/_headers` declara cache de um ano para tudo o que está em `/assets/*`, e não declara o mesmo para o documento de entrada, que tem de ser sempre verificado.

#### Onde a loja vai buscar os dados

O programa da loja tem dois destinos, e a divisão é uma característica arquitectural da Diomika.

Para **ler o catálogo**, fala **directamente com o Supabase**, através de `frontend-web/src/lib/catalogSupabase.js`, usando a chave pública. Não passa pelo backend. A justificação: são dados públicos, a leitura não tem regras de negócio, e o Supabase serve leituras a partir da sua própria infra-estrutura, sem consumir a máquina virtual muito pequena onde corre o backend. Regras declaradas na base de dados limitam o que essa chave pode ver, e portanto delegar a leitura não é delegar confiança.

Para **enviar qualquer coisa** — contacto, pedido de orçamento — fala com `api.diomika.com`, através de `frontend-web/src/lib/api.js`. Aqui não há atalho possível: é preciso validar, verificar que não é um robô, registar, notificar, e nada disso pode acontecer no browser.

#### Limitações honestas do modelo

Uma aplicação de página única não é gratuita, e o relatório deve ser explícito quanto ao preço.

**A primeira visita é mais lenta.** Antes de o visitante ver conteúdo útil, o browser tem de descarregar e executar o programa. Uma página tradicional mostra conteúdo com o primeiro pedido. Mitigações: divisão do código por rotas, para que a primeira visita não carregue a aplicação inteira; ficheiros pequenos e comprimidos; distribuição por rede global para reduzir a distância.

**Indexação por motores de busca é mais frágil.** Os motores modernos executam JavaScript, mas fazem-no com orçamento limitado de tempo e recursos. Conteúdo que só aparece depois de várias idas ao servidor pode não ser visto. Na Diomika isto é mitigado com metadados definidos por rota — `frontend-web/src/composables/usePageMeta.js` — e com um mapa do sítio em `frontend-web/public/sitemap.xml`. É um compromisso real, atenuado pelo facto de a Diomika ser um negócio entre empresas, onde a descoberta acontece mais por relação comercial e contacto directo do que por busca orgânica.

**Requer JavaScript.** Sem JavaScript não há loja. Na prática isto afecta uma fracção desprezável de visitantes reais.

**Erros de programação são mais consequentes.** Numa página tradicional, um erro afecta a página. Numa aplicação de página única, um erro não tratado pode deixar o ecrã em branco e inutilizar a sessão inteira. Por essa razão a Diomika tem `frontend-web/src/components/AppErrorBoundary.vue`, um componente cuja única função é apanhar falhas inesperadas e mostrar algo compreensível em vez de nada.

---

### I.11 CDN — Content Delivery Network (Cloudflare Pages)

#### A física do problema

A informação viaja pela rede a uma velocidade que, embora enorme, é finita. Um pedido de Lisboa a um servidor na costa oeste dos Estados Unidos e a respectiva resposta atravessam cerca de dezoito mil quilómetros. Mesmo em fibra óptica, isso custa perto de cem milissegundos, aos quais se somam atrasos em cada equipamento do caminho.

Cem milissegundos parecem nada. Mas como se viu na secção I.6, abrir "uma página" são dezenas de pedidos, e vários deles são sequenciais — o browser só sabe que precisa de um ficheiro depois de ler outro que o referencia. Somando idas e voltas, e acrescentando o aperto de mão de encriptação, a distância geográfica transforma-se em segundos perceptíveis.

Nenhuma optimização de código resolve isto. É geografia.

#### A solução

Uma **CDN** — *Content Delivery Network*, ou Rede de Distribuição de Conteúdos — resolve o problema movendo os ficheiros para perto de quem os pede. Em vez de um servidor num lugar, existem cópias em centenas de lugares. Quando um visitante pede um ficheiro, é servido pela cópia mais próxima.

O encaminhamento faz-se em grande medida no próprio sistema de nomes: a consulta a `www.diomika.com` devolve endereços diferentes conforme a localização de quem pergunta. Um visitante em Lisboa recebe o endereço de um ponto de presença ibérico; um em Tóquio recebe outro. É invisível, automático, e é o que torna sítios globais rápidos em todo o lado.

Os benefícios acumulam-se. **Latência menor**, pelas razões descritas. **Menos carga na origem**, porque a esmagadora maioria dos pedidos é servida a partir de cópias e nunca chega ao servidor original. **Resistência a picos de tráfego**, porque a capacidade agregada da rede é muito superior à de qualquer origem. **Absorção de ataques de volume**, porque uma rede global distribui um ataque em vez de o concentrar. E, no caso da Diomika, **custo zero**, porque a distribuição de ficheiros estáticos é oferecida em camada gratuita generosa.

#### Estático e dinâmico

Uma distinção essencial: **conteúdo estático** é um ficheiro que é igual para todos — uma imagem, uma folha de estilo, um ficheiro de código compilado. **Conteúdo dinâmico** é gerado no momento e depende de quem pergunta — a lista de pedidos de orçamento de um administrador.

Conteúdo estático é ideal para distribuição em rede: pode ser copiado sem limite e servido a qualquer pessoa. Conteúdo dinâmico não pode ser copiado da mesma forma, porque servir a resposta de uma pessoa a outra pessoa seria uma falha de segurança grave.

Esta distinção é a razão pela qual a Diomika separa `www.diomika.com` de `api.diomika.com`. A loja compilada é inteiramente estática — um conjunto de ficheiros idênticos para todos os visitantes — e portanto perfeitamente adequada a distribuição global agressiva. As respostas do backend são dinâmicas e específicas, e portanto servidas de um só lugar, com instruções para não serem guardadas.

#### Cloudflare Pages

**Pages** é o serviço da Cloudflare para alojar sítios estáticos. O modelo é: entrega-se uma pasta com o resultado da compilação, e o serviço distribui-a por toda a sua rede global.

Na Diomika, o processo é o que está em `deploy/deploy_beta.py`: o Vite compila `frontend-web/` para uma pasta de distribuição, e essa pasta é enviada para o Pages. Cada envio cria uma versão distinta, com endereço próprio, o que permite testar antes de promover e reverter instantaneamente para uma versão anterior se algo estiver errado. Reverter uma loja estática é trivial — muda-se o apontador para o envio anterior — o que é uma propriedade operacional muito valiosa e uma vantagem material sobre alojamento tradicional.

Dois ficheiros de configuração merecem nota, ambos em `frontend-web/public/`:

**`_headers`** declara os cabeçalhos que a rede acrescenta às respostas. Inclui os cabeçalhos de segurança — política de conteúdo, recusa de enquadramento em outros sítios, política de referência, restrições de acesso a câmara e microfone, obrigatoriedade de encriptação — e as políticas de cache: um ano de cache imutável para tudo em `/assets/*`, cujos nomes incluem impressão digital do conteúdo.

**`_redirects`** declara as reescritas de caminho, incluindo a regra que faz qualquer caminho não correspondente a um ficheiro servir o documento de entrada, sem a qual as ligações directas para rotas internas falhariam.

#### Código na fronteira

O Pages permite, além de servir ficheiros, correr pequenas porções de código na própria rede de distribuição — na **fronteira** (*edge*), ou seja, no ponto de presença mais próximo do visitante, antes de qualquer coisa chegar mais fundo.

A Diomika usa isto para uma finalidade defensiva concreta. O ficheiro `frontend-web/functions/_middleware.js` intercepta todos os pedidos e bloqueia os que procuram caminhos que não têm razão de existir num sítio estático: ficheiros de configuração, pastas de controlo de versões, código-fonte não compilado. Estes pedidos existem em volume constante e são inteiramente automáticos — robôs a testar milhões de endereços em busca de configurações mal colocadas. Bloqueá-los na fronteira significa que nunca chegam a lado nenhum, que não geram ruído nos registos, e que uma eventual configuração mal colocada não seria descoberta por varredura.

#### Cache e o seu problema fundamental

A cache é uma das ideias mais poderosas da computação e uma das mais perigosas, e o motivo é sempre o mesmo: **uma cópia guardada pode estar desactualizada**.

Se a Diomika publicar uma correcção na loja e os browsers dos visitantes continuarem a usar a versão anterior, a correcção não existe para eles. Se a rede de distribuição tiver guardado a versão antiga de um ficheiro, serve-a a novos visitantes.

A solução — descrita já duas vezes neste documento, porque é central — é a impressão digital nos nomes de ficheiro. Ficheiros cujo nome depende do conteúdo podem ser guardados eternamente, porque um conteúdo novo tem sempre um nome novo. Apenas o documento de entrada, que aponta para os restantes, tem de ser verificado a cada visita — e é pequeno.

Este padrão resolve o problema de forma completa: cache máxima onde é seguro, verificação constante onde é necessário. Está implementado nas regras de `frontend-web/public/_headers` e é uma das razões pelas quais uma actualização da loja é visível imediatamente sem que ninguém tenha de limpar caches.

#### Cache no lado do backend

O backend tem o seu próprio tratamento de cache, mais conservador. Uma camada dedicada — `CatalogCacheHeadersMiddleware`, em `backend-api/core/middleware.py` — acrescenta instruções de cache **apenas** às respostas de catálogo, que são públicas e mudam raramente. Todas as outras respostas são marcadas como não guardáveis.

A assimetria é deliberada e é uma regra de segurança, não de desempenho. Uma resposta que contém dados específicos de um utilizador autenticado nunca pode ser guardada por uma camada intermédia, porque a consequência de um erro é servir os dados de uma pessoa a outra. O modo seguro por omissão é não guardar nada, e activar cache explicitamente apenas onde se demonstrou que é seguro.

---

### I.12 B2B vs B2C

#### As siglas

**B2B** significa *Business to Business* — de empresa para empresa. **B2C** significa *Business to Consumer* — de empresa para consumidor final.

A Diomika é **B2B**: vende a fabricantes de mobiliário, retalhistas, decoradores e hotelaria. Não vende à pessoa que quer uma almofada para o sofá.

#### Porque é que esta distinção decide a arquitectura

Esta não é uma nota de marketing colocada num relatório técnico por cortesia. É a razão de ser de várias decisões de engenharia, e sem ela essas decisões parecem lacunas.

**Preço.** Num sistema para consumidor final, o preço é público, fixo e central — é o eixo em torno do qual a interface se organiza. Num sistema entre empresas, o preço depende do volume, do tecido, do acabamento, do prazo e da relação comercial. Publicá-lo seria simultaneamente falso e comercialmente prejudicial: revela margens a concorrentes e compromete negociações. Consequência técnica directa: a Diomika **não tem sistema de preços públicos** nem lógica de cálculo de totais no frontend. O que tem é um mecanismo de pedido de orçamento.

**Pagamento.** Consumidor final paga com cartão, no momento. Empresa paga contra factura, a prazo, muitas vezes com condições negociadas. Consequência técnica: a Diomika **não processa pagamentos**. Isto elimina do sistema toda a infra-estrutura de pagamentos, toda a conformidade com normas da indústria de cartões, toda a gestão de fraude, e toda a atractividade do sistema para quem rouba dados financeiros. É provavelmente a decisão que mais reduz o risco global do projecto, e vem inteiramente do modelo de negócio.

**Carrinho.** Num sistema para consumidor final, o carrinho é o caminho para o pagamento. Na Diomika, o que `frontend-web/src/composables/useCart.js` implementa não é um carrinho de compras: é uma **lista de interesse** que o comprador monta e que se transforma num pedido de orçamento. O nome no código é "carrinho" por familiaridade, mas a semântica é diferente, e essa diferença nota-se em detalhes: não há total a pagar, não há portes, não há prazo de reserva de stock.

**Quantidades.** Um consumidor compra uma ou duas unidades. Uma empresa compra dezenas, centenas, ou pede uma cotação por metro de tecido. Os campos de quantidade, as validações e a apresentação têm de acomodar ordens de magnitude diferentes.

**Volume de tráfego.** Uma loja de consumo pode ter dezenas de milhares de visitantes por dia. Um catálogo entre empresas tem, tipicamente, dezenas a centenas — visitantes qualificados, que voltam, e cuja visita tem valor comercial elevado. Consequência técnica importante: **uma máquina virtual muito pequena é suficiente**. A arquitectura de custo quase nulo da Diomika só é viável por causa desta característica do modelo de negócio. Um sistema de consumo com o mesmo desenho não sobreviveria a uma campanha.

**Sazonalidade e picos.** O tráfego entre empresas é relativamente constante e segue o horário de trabalho. Não há picos de campanha de fim de ano. Isto reduz a necessidade de capacidade elástica — uma das grandes fontes de complexidade e de custo em sistemas de consumo.

**Identidade do utilizador.** Num sistema de consumo, cada cliente tem conta, histórico e preferências. Na Diomika, os pedidos de orçamento vêm de pessoas identificadas por nome, empresa e contacto, mas **não existe registo de contas para clientes**. Não há área reservada, não há recuperação de palavra-passe, não há gestão de perfis. A relação comercial continua fora do sistema — por e-mail, telefone e reunião — que é como funciona neste sector. Consequência técnica: a autenticação existe **apenas** para os administradores. Isso reduz drasticamente a superfície de ataque, porque a funcionalidade mais atacada de qualquer sistema web — registo e recuperação de contas de utilizadores — simplesmente não existe.

**Dados pessoais.** Menos utilizadores significa menos dados pessoais, e dados de contexto profissional em vez de dados de vida privada. Não deixa de estar sujeito à legislação de protecção de dados — daí `backend-api/routes/privacy.py` e `frontend-web/src/views/PrivacyView.vue` — mas a exposição é qualitativamente menor.

**Tolerância a interrupções.** Uma loja de consumo em baixo durante uma hora perde vendas imediatamente e de forma irrecuperável. Um catálogo entre empresas em baixo durante uma hora é um incómodo: quem queria pedir um orçamento volta, ou telefona. Isto não é desculpa para descuido — a Diomika tem monitorização activa e alertas — mas justifica não construir redundância multi-região, que multiplicaria o custo e a complexidade para resolver um risco de impacto comercial modesto.

#### O que o modelo B2B exige e o B2C não

A comparação não é toda a favor da simplicidade. Há aspectos em que a exigência é maior.

**Fidelidade das especificações técnicas.** Um comprador profissional decide com base em dimensões, composição, densidade de espuma, gramagem de tecido, resistência. Um erro numa especificação não é um detalhe cosmético: é uma encomenda errada, um custo de devolução, e perda de credibilidade. Daí a existência de `frontend-web/src/components/ModelSpecs.vue` e de estruturas de dados ricas para composições.

**Qualidade e fidelidade das imagens.** A cor de um tecido tem de estar correcta, porque decisões são tomadas a partir da fotografia. Daí a validação de imagens em `backend-api/utils/image_validation.py` e o cuidado com a entrega de imagens.

**Rastreabilidade.** Uma encomenda entre empresas tem valor contratual. É preciso saber o que foi pedido, quando, por quem, e o que foi respondido. Daí a existência de registo de auditoria (`backend-api/core/audit.py`), de geração de documentos de encomenda (`backend-api/utils/pdf_encomenda.py`), e da recusa de apagar registos históricos.

**Fiabilidade das notificações.** Se um pedido de orçamento chega e ninguém é notificado, perde-se um negócio de valor potencialmente elevado. Um pedido perdido num sistema B2B custa muito mais do que uma venda perdida num sistema B2C. É esta assimetria que justifica a complexidade da entrega garantida de notificações na Diomika — o mecanismo de fila persistente descrito na Parte sobre fluxos de dados — que seria excessiva para um caso de uso de consumo.

#### Em resumo

A Diomika é B2B, e por isso: não tem pagamentos, não tem preços públicos, não tem contas de cliente, não tem picos de tráfego, e não precisa de infra-estrutura grande. E, pela mesma razão: precisa de dados de produto rigorosos, de rastreabilidade documental, e de garantia de que nenhum pedido se perde. A arquitectura descrita neste relatório é a consequência directa deste conjunto de exigências, e não faz sentido avaliada contra outro modelo de negócio.

---

### I.13 Glossário A–Z completo

Este glossário é a peça de referência do relatório. Está ordenado alfabeticamente e cada entrada segue a mesma estrutura: o **nome completo** do termo (expandido, se for sigla), o que a coisa **é** em linguagem comum, e como a **Diomika** a usa — ou a indicação explícita de que **não é usada** ou é **opcional**.

Recomenda-se ler o glossário de uma ponta à outra na primeira vez. Muitas entradas explicam-se mutuamente, e há valor em ver o conjunto antes de precisar de uma entrada em particular.

---

#### allowlist (lista de permitidos)

Uma *allowlist* é uma lista fechada do que é **permitido**, com a regra de que tudo o que não está na lista é recusado. O oposto é uma *blocklist* (lista de bloqueados), que enumera o que é proibido e permite o resto. A diferença parece simétrica e não é: uma lista de bloqueados falha sempre que aparece uma ameaça nova que ninguém previu, enquanto uma lista de permitidos falha apenas ao recusar algo legítimo que se esqueceram de acrescentar. O primeiro tipo de falha é uma brecha de segurança silenciosa; o segundo é um incómodo visível que alguém resolve em minutos. Por isso a prática de segurança recomenda listas de permitidos sempre que a enumeração do legítimo seja viável. A Diomika usa este padrão em vários pontos independentes: os domínios autorizados a fazer pedidos ao backend estão numa lista fechada configurada em `CORS_ORIGINS`; os nomes de servidor que o backend aceita atender estão numa lista fechada em `ALLOWED_HOSTS`, com comportamento de recusa total se a lista estiver vazia; e os destinos externos que o backend pode contactar estão numa lista fechada em `backend-api/core/ssrf_guard.py`. Este último caso é particularmente importante e é explicado na entrada sobre SSRF. A regra transversal do projecto é a mesma: **negar por omissão, permitir por excepção declarada**.

#### anon key (chave anónima do Supabase)

A *anon key* é uma das duas chaves de acesso que o Supabase entrega a cada projecto, e é a que se destina a ser **pública**. Vai embutida no código do frontend, é visível a qualquer visitante que inspeccione a loja, e não faz sentido tentar mantê-la secreta — é uma identificação de projecto, não uma autorização. O que ela pode realmente fazer é decidido inteiramente por regras declaradas dentro da base de dados, através do mecanismo descrito na entrada sobre RLS. Uma chave anónima sobre uma base de dados sem essas regras é uma catástrofe — permite ler e escrever tudo; a mesma chave sobre uma base de dados com regras bem escritas é inofensiva. Na Diomika a chave anónima é configurada em `VITE_SUPABASE_ANON_KEY` e usada por `frontend-web/src/lib/supabase.js` e `frontend-web/src/lib/catalogSupabase.js`, exclusivamente para **ler** dados de catálogo destinados a ser públicos. Nunca é usada para escrever nada. Existe um verificador automático, `deploy/verify_bundle_secrets.py`, que examina o resultado da compilação da loja e falha a construção se encontrar lá dentro qualquer segredo que não devesse estar — em particular a chave de serviço, que é a chave irmã e perigosa. É o par natural da entrada sobre *service role*, e as duas devem ser lidas em conjunto.

#### API — Application Programming Interface

*Interface de Programação de Aplicações*. É o contrato pelo qual um programa oferece operações a outros programas: que operações existem, que dados aceitam, que resultados devolvem. A analogia da tomada eléctrica, usada na secção I.9, continua a ser a melhor: define-se uma forma e uma especificação, e qualquer aparelho que a respeite funciona, sem que nenhum dos lados precise de conhecer a implementação do outro. O valor prático é o desacoplamento: a implementação pode ser reescrita de raiz sem que os consumidores mudem, desde que o contrato se mantenha. Na Diomika, "a API" refere-se normalmente à aplicação Python em `backend-api/`, publicada em `api.diomika.com`, que é a interface partilhada pela loja e pelo backoffice. Ter uma única interface para as duas superfícies é o que impede que as regras de negócio existam em duas versões que divergem com o tempo. O contrato está declarado em `backend-api/models/schemas.py` e é aplicado automaticamente em cada pedido.

#### AppImage

*AppImage* é um formato de distribuição de programas para Linux que empacota a aplicação e todas as suas dependências num único ficheiro executável. O utilizador descarrega o ficheiro, dá-lhe permissão de execução, e corre — sem instalador, sem gestor de pacotes, sem privilégios de administrador. Existe porque o mundo Linux tem muitas distribuições com gestores de pacotes incompatíveis, e produzir um pacote para cada uma é impraticável para um projecto pequeno. A Diomika publica o seu backoffice em formato AppImage para utilizadores de Linux, gerado pela mesma configuração de construção em `backoffice-desktop/package.json` que produz as versões para Windows e macOS. Não é o formato principal — o uso real do backoffice é sobretudo em Windows — mas está disponível e é construído automaticamente pelo processo definido em `.github/workflows/backoffice-release.yml`. Ver também as entradas sobre EXE e DMG, que são os formatos equivalentes para os outros sistemas.

#### ASGI — Asynchronous Server Gateway Interface

*Interface Assíncrona de Ligação a Servidor*. É a especificação que define como um servidor web Python conversa com uma aplicação web Python. É a sucessora de uma norma mais antiga chamada WSGI, e a diferença essencial é o suporte para operação **assíncrona**: a capacidade de uma aplicação atender muitos pedidos em simultâneo enquanto espera por operações lentas, em vez de bloquear um recurso do sistema por cada pedido em curso. Isto importa muito quando a maior parte do tempo de um pedido é passada à espera — de uma consulta à base de dados, de um envio de e-mail, de uma resposta de um serviço externo — que é exactamente o perfil da Diomika. A norma define também o conceito de **middleware**: camadas que envolvem a aplicação e vêem todos os pedidos, tratado em entrada própria. Na Diomika, a aplicação em `backend-api/main.py` é uma aplicação ASGI, servida pelo servidor Uvicorn. Um detalhe da norma teve consequências reais no projecto: o corpo de um pedido é um fluxo que só pode ser lido **uma vez**, e uma camada que o lia esgotava-o antes de a validação o poder ver, produzindo erros de campo em falta em pedidos perfeitamente válidos. A correcção está documentada na secção I.6 e em `backend-api/core/middleware.py`.

#### Axiom

Axiom é um serviço de agregação e consulta de registos de eventos. A aplicação envia-lhe cada registo estruturado, e o serviço permite depois procurar, filtrar, agregar e construir gráficos sobre esses dados. Resolve um problema muito concreto: registos guardados apenas em ficheiros dentro de uma máquina desaparecem quando a máquina é substituída ou reiniciada, e são difíceis de consultar de forma útil. A Diomika usa Axiom na sua camada gratuita, com a implementação em `backend-api/core/structured_logging.py`, activada pela presença das variáveis `AXIOM_TOKEN` e `AXIOM_API_URL`. Há um detalhe operacional que consumiu tempo real e vale a pena registar: uma organização alojada na Europa tem de enviar os dados para um endereço de fronteira europeu, e o endereço mais antigo, de estilo americano, é recusado. O código distingue os dois formatos pelo nome do servidor de destino e escolhe o caminho correcto. Este é o tipo de detalhe que não aparece em documentação de arquitectura e que faz a diferença entre um sistema que funciona e um que falha silenciosamente. Ver também as entradas sobre Sentry, PostHog e ntfy, que compõem com Axiom a camada de observabilidade do projecto.

#### boto3

*boto3* é a biblioteca oficial em Python para falar com os serviços da Amazon Web Services, e em particular com o seu serviço de armazenamento de objectos. Aparece na Diomika por uma razão indirecta e interessante: a interface desse serviço tornou-se uma norma de facto na indústria, e vários fornecedores concorrentes — incluindo o serviço de armazenamento da Cloudflare — implementam a mesma interface deliberadamente, para que as ferramentas existentes funcionem sem adaptação. A Diomika tem `boto3` nas suas dependências em `requirements.txt` e usa-o em `backend-api/utils/storage_r2.py` para falar com o armazenamento da Cloudflare, **se** esse armazenamento estiver configurado. Não fala com a Amazon; fala com a Cloudflare através de uma biblioteca escrita para a Amazon. Este caminho está **implementado mas não activado**: o armazenamento em uso é o do Supabase, e o código alternativo só ganha vida se as variáveis com prefixo `R2_` estiverem definidas. É um exemplo de opcionalidade deliberada — uma porta de saída construída antes de ser necessária, para que a migração seja uma decisão de configuração e não um projecto de desenvolvimento.

#### bootstrap (arranque inicial)

Na informática, *bootstrap* designa o problema de arrancar um sistema que precisa de si mesmo para arrancar — a imagem de puxar-se a si próprio pelos atacadores das botas. O caso clássico é a criação do primeiro utilizador administrador: para criar utilizadores é preciso estar autenticado como administrador, e para estar autenticado é preciso existir um administrador. Alguém tem de quebrar o ciclo. A Diomika resolve-o com duas variáveis de configuração, `ADMIN_BOOTSTRAP_USER` e `ADMIN_BOOTSTRAP_PASSWORD`, lidas por `backend-api/core/admin_users.py` no arranque da aplicação, e com uma condição rigorosa: essas variáveis só têm efeito **se ainda não existir nenhum utilizador**. Uma vez criado o primeiro, são inertes — mudar o valor da variável não altera a palavra-passe de ninguém. Esta condição é correcta do ponto de vista da segurança e produziu, na prática, uma confusão operacional real: uma alteração da palavra-passe no ficheiro de configuração não teve efeito nenhum, porque o utilizador já existia, e o resultado foi login recusado com credenciais que pareciam certas. A lição está documentada na Parte sobre operações: alterar a palavra-passe de um administrador existente exige uma operação explícita, não uma alteração de configuração. O termo também aparece num segundo sentido no projecto: `backend-api/core/schema_engine.py` faz o *bootstrap* da estrutura da base de dados no arranque, garantindo que as tabelas necessárias existem, comportamento controlável pela variável `SCHEMA_BOOTSTRAP`.

#### CDN — Content Delivery Network

*Rede de Distribuição de Conteúdos*. É uma rede de servidores espalhados geograficamente que guardam cópias de ficheiros e os servem a partir do ponto mais próximo de quem os pede. Resolve um problema que nenhuma optimização de código resolve: a distância física, que se traduz em tempo de viagem da informação. Os benefícios são latência menor, muito menos carga no servidor de origem, resistência a picos de tráfego, e absorção de ataques de volume por distribuição. Está tratado em detalhe na secção I.11. Na Diomika, a loja em `www.diomika.com` é servida pela rede da Cloudflare através do serviço Pages, com os ficheiros compilados de `frontend-web/` distribuídos por centenas de localizações. A interface de programação, pelo contrário, **não** é distribuída desta forma, porque as suas respostas são dinâmicas e específicas de cada pedido — embora passe pela mesma rede, que lhe presta serviços de encriptação e filtragem sem guardar as respostas.

#### CI/CD — Continuous Integration / Continuous Delivery

*Integração Contínua* e *Entrega Contínua*. Integração contínua significa que, a cada alteração de código, um sistema automático executa uma bateria de verificações — testes, análise de segurança, tentativa de compilação — e reporta o resultado. Entrega contínua significa que o processo de publicar uma versão é automatizado e repetível, em vez de depender de passos manuais executados de memória. O valor é duplo: erros são descobertos em minutos em vez de em produção, e a publicação deixa de ser um acontecimento arriscado. A Diomika usa o sistema de automação integrado no GitHub, com a configuração em `.github/workflows/ci.yml`, que a cada alteração executa: análise de vulnerabilidades conhecidas nas dependências Python, um portão de segurança próprio (`deploy/security_gate.py`), varrimento em busca de segredos acidentalmente comprometidos, a suite de testes automatizados, a compilação da loja com verificação de que nenhum segredo ficou no resultado, e testes de ponta a ponta no browser. Existe um segundo processo em `.github/workflows/backoffice-release.yml` que constrói os instaladores do backoffice para os três sistemas operativos, e um terceiro em `.github/workflows/uptime.yml` que verifica periodicamente se os endereços de produção respondem. Nada é publicado se as verificações falharem, o que é o ponto central: as verificações não são conselhos, são condições.

#### cloudflared

*cloudflared* é o programa que estabelece um Cloudflare Tunnel. Corre na máquina que se quer publicar e abre uma ligação **de dentro para fora** até à rede da Cloudflare, mantendo-a aberta. A partir daí, os pedidos que chegam ao endereço público são encaminhados pela Cloudflare através dessa ligação já estabelecida e entregues à aplicação local. A propriedade decisiva é a direcção: como a ligação parte de dentro, **não é necessária nenhuma porta aberta na máquina**, não é necessário endereço público fixo, e não é necessária configuração de firewall para tráfego de entrada. Uma varredura de portas ao endereço da máquina não encontra nada, porque não há nada à escuta. Na Diomika, o `cloudflared` corre como serviço dentro da máquina virtual, configurado em `deploy/docker-compose.free.yml`, autenticado pelo segredo guardado em `CLOUDFLARE_TUNNEL_TOKEN`, e encaminha o tráfego de `api.diomika.com` para `http://127.0.0.1:8000`. É a peça que torna possível publicar a interface de programação sem lhe dar exposição directa à internet. Ver também as entradas sobre Tunnel e VPN.

#### Compose — Docker Compose

*Docker Compose* é a ferramenta que permite descrever, num único ficheiro de texto, um conjunto de contentores que trabalham em conjunto — que imagens usam, que variáveis de ambiente recebem, que portas expõem, que volumes montam, e por que ordem devem arrancar. Sem esta ferramenta, correr um sistema de vários contentores exige uma sequência de comandos longos, propensos a erro e difíceis de reproduzir; com ela, o comando é um só e a configuração fica registada num ficheiro que se pode versionar e revisitar. A Diomika tem dois destes ficheiros, para dois cenários diferentes. `deploy/docker-compose.free.yml` descreve o cenário de produção actual, desenhado para uma máquina virtual muito pequena: a aplicação, uma cache, e o programa do túnel, com os trabalhadores de segundo plano a correr **dentro** do processo da aplicação para poupar memória. `docker-compose.yml`, na raiz do repositório, descreve um cenário mais folgado, para uma máquina maior, com os trabalhadores como serviços independentes. A escolha entre os dois é a materialização da restrição de custo do projecto: correr menos processos é menos elegante e é o que a memória disponível permite.

#### Content-Length

`Content-Length` é um cabeçalho HTTP que declara, em bytes, o tamanho do corpo de um pedido ou de uma resposta. Permite ao receptor saber quanto conteúdo esperar e quando a mensagem termina, e permite decidir aceitar ou recusar **antes** de receber tudo. Este último ponto é a razão pela qual o cabeçalho é central numa das decisões de engenharia da Diomika. O backend limita o tamanho dos pedidos que aceita, para que ninguém possa esgotar a memória de uma máquina pequena enviando conteúdo enorme. A primeira implementação dessa limitação media o tamanho **lendo o corpo do pedido** — o que era correcto em aritmética e desastroso em prática, porque o corpo de um pedido só pode ser lido uma vez, e quando a validação chegava ao seu turno já não havia nada para ler. O sintoma foram tentativas de login legítimas rejeitadas com a indicação de que a palavra-passe estava em falta. A correcção, em `backend-api/core/middleware.py`, foi passar a confiar exclusivamente neste cabeçalho: se o valor declarado exceder o limite, recusar imediatamente; caso contrário, deixar passar sem tocar no corpo. É uma decisão consciente de preferir simplicidade e correcção a uma solução mais completa e mais frágil.

#### CORS — Cross-Origin Resource Sharing

*Partilha de Recursos entre Origens*. É o mecanismo pelo qual um browser decide se permite que código carregado de um domínio faça pedidos a outro domínio. Existe porque a regra fundamental de segurança dos browsers — a *política de mesma origem* — proíbe, por omissão, que código de um sítio leia respostas de outro. Sem essa regra, uma página maliciosa aberta noutro separador poderia ler o correio electrónico ou a conta bancária do visitante, aproveitando as sessões já abertas. Este mecanismo é a excepção controlada: o servidor de destino declara, em cabeçalhos de resposta, quais as origens autorizadas, e o browser aplica essa declaração. É importante compreender que a protecção é aplicada **pelo browser**, não pelo servidor — um programa que não seja um browser ignora estas regras completamente, e por isso este mecanismo protege os utilizadores, não o servidor. Na Diomika a configuração está em `backend-api/main.py`: em produção, apenas as origens listadas em `CORS_ORIGINS` são autorizadas; em desenvolvimento, aceitam-se endereços locais; e em ambiente de pré-produção existe uma regra que aceita os domínios temporários usados para pré-visualizações. Os cabeçalhos aceitos estão numa lista fechada declarada em `backend-api/core/middleware.py`, o que garante que o cabeçalho de identificação do programa instalado é explicitamente permitido.

#### CSP — Content Security Policy

*Política de Segurança de Conteúdos*. É um cabeçalho de resposta pelo qual um sítio declara ao browser, de forma detalhada, de onde é legítimo carregar cada tipo de recurso: código, estilos, imagens, tipos de letra, e a que destinos é legítimo enviar pedidos. O browser aplica essa declaração e **recusa** tudo o que não esteja previsto. É a defesa mais eficaz que existe contra injecção de código, porque mesmo que um atacante consiga inserir um script numa página, esse script não corre se a sua origem não estiver autorizada. É simultaneamente uma das configurações mais difíceis de acertar, porque uma política demasiado restritiva quebra funcionalidades legítimas de forma que só se descobre em uso real. A Diomika declara a sua política em `frontend-web/public/_headers`, e ela é notavelmente estrita: por omissão, apenas a própria origem; código apenas da própria origem e do serviço de verificação anti-robô da Cloudflare; pedidos apenas para a própria origem, para o Supabase, para o verificador anti-robô, para `api.diomika.com` e para o serviço de análise; imagens da própria origem, do Supabase e do armazenamento alternativo; nenhum objecto embutido; proibição absoluta de a loja ser enquadrada dentro de outro sítio. Existe um verificador automático em `deploy/verify_csp.py` que confirma que a política declarada corresponde ao esperado, porque uma política de segurança que se degrada silenciosamente ao longo do tempo é pior do que nenhuma.

#### CSRF — Cross-Site Request Forgery

*Falsificação de Pedido entre Sítios*. É um ataque em que um sítio malicioso induz o browser de uma vítima a enviar um pedido a outro sítio onde ela está autenticada, aproveitando o facto de o browser anexar automaticamente as credenciais guardadas. O exemplo clássico: uma página com uma imagem cujo endereço é, na verdade, uma operação de transferência bancária. Se o banco identificar a sessão por cookie, o browser envia o cookie, e a operação executa-se sem que a vítima tenha consciência. O ponto essencial é que este ataque depende de as credenciais serem enviadas **automaticamente** pelo browser — e a defesa mais robusta é não usar credenciais automáticas. É exactamente essa a situação da Diomika: as sessões administrativas não usam cookies; usam um token transportado no cabeçalho `Authorization`, que tem de ser **explicitamente** acrescentado por código a cada pedido. Um sítio malicioso não pode fazer o browser anexar esse cabeçalho, porque ele não é automático. A classe de ataque é, portanto, **estruturalmente inaplicável** à administração da Diomika, e não por acidente: a decisão de usar cabeçalho em vez de cookie foi tomada em parte por esta razão. Os formulários públicos, que não têm autenticação nenhuma associada, não são alvo útil deste ataque; estão protegidos contra abuso por verificação anti-robô e limitação de ritmo, que respondem a um problema diferente.

#### CSS — Cascading Style Sheets

*Folhas de Estilo em Cascata*. É a linguagem que descreve a apresentação visual de um documento web: cores, tipos de letra, espaçamentos, dimensões, posicionamento, animações, e comportamento em ecrãs de tamanhos diferentes. A separação entre estrutura (na linguagem de marcação) e apresentação (nesta linguagem) é um dos princípios fundadores da web, e permite mudar completamente o aspecto de um sítio sem tocar no seu conteúdo. O nome refere-se ao mecanismo de **cascata**: quando várias regras se aplicam ao mesmo elemento, existe um sistema de precedência que decide qual ganha — um sistema poderoso e uma fonte inesgotável de confusão. Na Diomika, cada componente Vue contém o seu próprio estilo, limitado ao seu âmbito, o que evita que uma alteração num sítio afecte outro inesperadamente. Os estilos globais e as variáveis de identidade visual estão em `frontend-web/src/assets/main.css` para a loja e em `backoffice-desktop/src/assets/theme.css` para o backoffice. Um detalhe relevante para a segurança: a política de conteúdos da loja permite estilos **apenas** da própria origem, o que impede injecção de estilos externos — uma técnica usada para exfiltrar dados de formulários.

#### CTA — Call To Action

*Chamada para Acção*. É um termo de marketing digital, não de engenharia, e designa o elemento visual que convida o visitante a dar o próximo passo — um botão, uma ligação destacada, uma frase com ênfase. Numa loja de consumo, é tipicamente "comprar agora". Aparece neste glossário porque é vocabulário corrente nas conversas sobre a loja, e porque no caso da Diomika tem um conteúdo específico determinado pelo modelo de negócio. Não havendo pagamentos nem preços públicos, a acção que a loja pretende provocar não é uma compra: é um **contacto** ou um **pedido de orçamento**. Os elementos correspondentes na Diomika conduzem a `frontend-web/src/views/ContactView.vue` ou à submissão da lista de interesse montada em `frontend-web/src/views/CartView.vue`. A distinção não é semântica: determina que a métrica de sucesso da loja é o número de pedidos qualificados recebidos, não um valor de vendas, e é isso que orienta o que se mede.

#### DB — Database (base de dados)

Uma **base de dados** é um sistema desenhado para guardar informação estruturada de forma organizada, consultável e segura, com garantias que um simples ficheiro não oferece: consultas eficientes sobre grandes volumes, acesso simultâneo por vários programas sem corrupção, integridade referencial entre dados relacionados, e recuperação em caso de falha a meio de uma operação. Estas garantias são o que distingue uma base de dados de uma pasta com ficheiros, e são muito mais difíceis de implementar do que parece. A Diomika usa PostgreSQL, alojado no Supabase, e é lá que vive toda a informação com valor do sistema: produtos, categorias, modelos, cores, composições, mensagens de contacto, pedidos de orçamento, encomendas, registos de auditoria, e a fila de notificações pendentes. A ligação está configurada em `backend-api/core/database.py` e `backend-api/core/database_url.py`, e a evolução da estrutura ao longo do tempo está registada nos ficheiros de `backend-api/sql/`. Ver também as entradas sobre PostgreSQL, SQL, RLS e Supabase.

#### Dependabot

*Dependabot* é um serviço integrado no GitHub que vigia as bibliotecas de que um projecto depende e abre automaticamente propostas de alteração quando existem versões mais recentes — em particular quando a versão em uso tem uma vulnerabilidade conhecida e publicada. Resolve um problema silencioso e muito comum: um projecto que funciona perfeitamente vai acumulando dependências desactualizadas, e uma delas acaba por ter uma falha de segurança que qualquer pessoa pode consultar num registo público. Ninguém repara, porque nada deixa de funcionar. A Diomika tem este serviço configurado em `.github/dependabot.yml`, vigiando as dependências Python declaradas em `requirements.txt` e as dependências JavaScript da loja e do backoffice. As propostas não são aplicadas automaticamente: passam pelas verificações automáticas descritas na entrada sobre CI/CD, e só são incorporadas se essas verificações passarem. Complementarmente, a verificação automática executa também uma análise de vulnerabilidades conhecidas nas dependências Python, que falha a construção se encontrar algo grave. É a diferença entre saber que se está desactualizado e descobri-lo por meio de um incidente.

#### DMG — Disk Image

*Imagem de Disco*. É o formato padrão de distribuição de aplicações em macOS. Um ficheiro com extensão `.dmg` é um disco virtual: ao ser aberto, o sistema monta-o como se fosse uma unidade externa, e o utilizador arrasta a aplicação para a pasta de aplicações. É a convenção esperada por qualquer utilizador de Mac, e distribuir de outra forma provoca desconfiança. A Diomika produz este formato para a versão macOS do backoffice, através da configuração em `backoffice-desktop/package.json` e do processo automático em `.github/workflows/backoffice-release.yml`. Há uma limitação assumida e documentada: a aplicação **não é assinada digitalmente** nem submetida ao processo de certificação da Apple, porque ambos exigem uma subscrição paga anual. A consequência prática é que, na primeira abertura, o sistema de protecção do macOS avisa que a aplicação vem de um desenvolvedor não identificado e exige um passo explícito do utilizador para a autorizar. Não impede o uso; exige instrução, que é dada no documento de acompanhamento entregue ao cliente. Ver a entrada sobre Gatekeeper.

#### DNS — Domain Name System

*Sistema de Nomes de Domínio*. É a lista telefónica distribuída da internet: traduz nomes legíveis por pessoas, como `www.diomika.com`, nos endereços numéricos que os equipamentos de rede efectivamente usam. Sem este sistema, seria necessário memorizar números para chegar a qualquer sítio, e mudar de servidor obrigaria a avisar todos os utilizadores. O sistema é hierárquico e distribuído por milhares de servidores em todo o mundo, e as suas respostas são guardadas temporariamente durante um período declarado — o que torna as consultas rápidas e as alterações não instantâneas. Está explicado em detalhe na secção I.5. Na Diomika, os nomes `www.diomika.com` e `api.diomika.com` são geridos pela Cloudflare, e a configuração está documentada em `deploy/cloudflare/dns_plan.json`. Manter essa documentação no repositório é deliberado: a configuração de rede é parte do sistema, e um sistema cuja configuração vive apenas dentro do painel de um fornecedor não é reconstruível.

#### Docker

*Docker* é a tecnologia que empacota uma aplicação junto com tudo aquilo de que ela precisa para correr — o interpretador da linguagem, as bibliotecas, os ficheiros de configuração, as variáveis de ambiente — num artefacto isolado chamado **contentor**. O problema que resolve é conhecido de qualquer pessoa que tenha trabalhado com software: "no meu computador funciona". Versões diferentes de bibliotecas, configurações diferentes do sistema, dependências instaladas há meses e esquecidas — tudo isso faz com que o mesmo código se comporte de forma diferente em máquinas diferentes. Um contentor elimina essa variabilidade: o que corre em produção é o mesmo artefacto que foi testado, bit por bit. Não é uma máquina virtual — é muito mais leve, porque partilha o núcleo do sistema operativo da máquina anfitriã em vez de simular hardware. Na Diomika, a receita de construção da imagem da aplicação está no `Dockerfile` na raiz do repositório, e a lista do que **não** deve ser incluído está em `.dockerignore` — um ficheiro cuja importância é sobretudo de segurança, porque é ele que garante que ficheiros de configuração com segredos não entram na imagem. Ver também as entradas sobre Compose e VM.

#### DSN — Data Source Name

*Nome da Fonte de Dados*. É uma cadeia de texto que contém, num único valor, todas as informações necessárias para um programa se ligar a um serviço: protocolo, credencial, servidor, e identificador do destino. A forma geral é a de um endereço web com credenciais embutidas. A vantagem é a compactação — uma única variável de configuração em vez de cinco — e o preço é que essa variável é, por natureza, um **segredo**, porque contém a credencial. Na Diomika o termo aparece sobretudo no contexto do serviço de captura de erros, cuja configuração é feita pela variável `SENTRY_DSN`. A presença dessa variável é o que activa o envio de erros; a sua ausência desactiva-o silenciosamente, e a aplicação continua a funcionar. Esse padrão — funcionalidade activada por presença de configuração, com degradação graciosa na ausência — é usado consistentemente em toda a camada de observabilidade da Diomika, e está implementado em `backend-api/core/sentry_init.py` e `backend-api/core/error_tracking.py`. O valor do segredo não consta do repositório, apenas o nome da variável.

#### Edge (fronteira)

*Edge* designa a periferia de uma rede de distribuição — o ponto de presença geograficamente mais próximo do utilizador. Correr código "na fronteira" significa executá-lo nesse ponto, antes de qualquer pedido chegar ao servidor de origem. As vantagens são latência mínima, porque o código corre a poucos milissegundos do utilizador, e filtragem antecipada, porque o que é rejeitado na fronteira nunca consome recursos da origem. As limitações são reais: o ambiente de execução é restrito, o tempo de execução é curto, e não há acesso a estado persistente local. A Diomika usa código na fronteira para uma finalidade puramente defensiva: `frontend-web/functions/_middleware.js` intercepta todos os pedidos à loja e bloqueia os que procuram caminhos que não têm razão de existir num sítio estático — ficheiros de configuração, pastas de controlo de versões, código-fonte não compilado. São pedidos automáticos, em volume constante, produzidos por robôs que varrem a internet inteira em busca de configurações mal colocadas. Bloqueá-los na fronteira significa que não chegam a lado nenhum e não geram ruído. É também na fronteira que a Cloudflare termina a encriptação e aplica as regras do seu sistema de filtragem, incluindo a regra que bloqueia acessos administrativos sem o cabeçalho correcto.

#### Electron

*Electron* é a tecnologia que permite construir aplicações de computador usando as mesmas linguagens da web. Funciona empacotando, dentro de um programa instalável, um motor de browser completo e um interpretador de JavaScript — de modo que a interface é uma página web, mas corre numa janela própria, com acesso a ficheiros locais e às capacidades do sistema operativo. O custo é o tamanho: cada aplicação carrega o seu próprio motor de browser, o que significa dezenas de megabytes mesmo para algo simples. O benefício é decisivo para um projecto pequeno: uma única base de código produz aplicações para Windows, macOS e Linux, e as competências usadas na loja aplicam-se directamente. A Diomika usa Electron para o backoffice, em `backoffice-desktop/`. O processo principal está em `backoffice-desktop/electron/main.cjs`, e faz algo mais do que abrir uma janela: corre um pequeno servidor HTTP local que serve a interface e, sobretudo, **reencaminha** os pedidos de dados para `api.diomika.com`, acrescentando o cabeçalho de identificação `X-Diomika-Desktop`. É esta capacidade de transportar um segredo que um browser não pode transportar que justifica a escolha de uma aplicação instalada em vez de um painel web.

#### EXE — Executable

*Executável*. É a extensão dos ficheiros de programa em Windows. A Diomika distribui a versão Windows do backoffice como um executável **portátil**: um único ficheiro que corre directamente, sem processo de instalação, sem escrever no registo do sistema, e sem exigir privilégios de administrador. A escolha é deliberada e tem duas razões. A primeira é reduzir atrito: um instalador que exige permissões elevadas numa máquina de empresa é frequentemente um bloqueio administrativo real. A segunda é reduzir a superfície de problemas: sem instalação, não há desinstalação incompleta, não há entradas de registo órfãs, e não há conflito com versões anteriores — actualizar é substituir o ficheiro. Tal como nos outros sistemas, o executável **não é assinado digitalmente**, porque a assinatura exige um certificado pago e um processo de validação de identidade da entidade. A consequência é um aviso do sistema de reputação do Windows na primeira execução, que exige um passo explícito do utilizador. Está documentado no ficheiro de instruções entregue ao cliente. Ver a entrada sobre SmartScreen.

#### FastAPI

*FastAPI* é a framework Python com que o backend da Diomika está construído. A sua característica distintiva é usar as anotações de tipo da própria linguagem como fonte de verdade: declara-se que um endereço recebe um objecto com determinados campos de determinados tipos, e a framework passa a validar automaticamente cada pedido, a rejeitar o que não corresponde com uma indicação precisa do que falhou, a gerar a documentação da interface, e a converter os dados nos tipos certos. O programador escreve a declaração uma vez e obtém validação, conversão e documentação sem código adicional. É construída sobre a norma assíncrona descrita na entrada sobre ASGI, o que lhe permite atender muitos pedidos simultâneos enquanto espera por operações lentas. Na Diomika, a aplicação é criada em `backend-api/main.py`, os endereços estão organizados por assunto em `backend-api/routes/`, e as declarações de forma dos dados — que são o coração de todo o sistema — estão em `backend-api/models/schemas.py`. A geração automática de documentação é uma funcionalidade valiosa em desenvolvimento e **desactivada em produção** por decisão de segurança, controlada por configuração.

#### gate (portão)

*Gate*, neste projecto, designa um mecanismo específico: um segredo partilhado que prova que um pedido vem de uma instalação oficial do backoffice. Não é autenticação de utilizador — não identifica **quem** está a usar o programa — mas sim autenticação de **origem**: identifica que o pedido vem do software legítimo e não de um browser qualquer. O funcionamento é directo. Um valor secreto, com pelo menos vinte e quatro caracteres, é guardado na variável `DIOMIKA_DESKTOP_GATE` tanto no servidor como no sistema de construção. Quando o instalador do backoffice é construído, o script `backoffice-desktop/scripts/write-gate.cjs` escreve esse valor num ficheiro que fica embutido no binário — ficheiro que está excluído do controlo de versões, e portanto nunca aparece no repositório. Em cada pedido, o programa envia o valor no cabeçalho `X-Diomika-Desktop`; do outro lado, `backend-api/core/local_only.py` compara-o com o esperado usando uma comparação de tempo constante, que não revela informação pela duração da operação. Se a comparação falhar, `backend-api/core/path_guard.py` responde como se o caminho não existisse. Existe uma segunda linha de defesa independente na rede da Cloudflare, definida em `deploy/cloudflare/waf_rules.json`, que bloqueia os mesmos caminhos sem o cabeçalho correcto antes de o pedido chegar à máquina. **Isto não é um token com validade nem uma assinatura criptográfica de um pedido** — é um segredo de instalação, e o relatório é explícito quanto ao seu limite: quem obtiver o instalador oficial e uma palavra-passe válida entra. O que o mecanismo elimina por completo é a totalidade dos ataques anónimos e automáticos. A rotação exige uma nova construção, actualização da regra na rede, e actualização da configuração do servidor.

#### Gatekeeper

*Gatekeeper* é o sistema de protecção do macOS que verifica a origem das aplicações antes de as deixar correr pela primeira vez. Se uma aplicação não estiver assinada por um desenvolvedor registado junto da Apple e submetida ao processo de certificação automática, o sistema recusa abri-la com um duplo clique e apresenta um aviso de que provém de um desenvolvedor não identificado. A intenção é boa — protege utilizadores comuns de software de origem desconhecida — e o efeito colateral é penalizar projectos que não pagam a subscrição anual de desenvolvedor. A Diomika **não** assina nem certifica a versão macOS do backoffice, por decisão de custo, e essa limitação está registada explicitamente no relatório principal. A consequência para o utilizador é ter de autorizar a aplicação uma vez, através de um passo manual nas preferências do sistema; depois disso, abre normalmente. As instruções constam do ficheiro de acompanhamento entregue com o instalador. É um caso claro de compromisso assumido e documentado, em vez de omitido.

#### GCP — Google Cloud Platform

*Plataforma de Nuvem da Google*. É o conjunto de serviços de infra-estrutura da Google: máquinas virtuais, armazenamento, bases de dados, redes. A Diomika usa-a por uma razão muito específica: a existência de uma camada **sempre gratuita** que inclui uma máquina virtual pequena, permanentemente, sem prazo de expiração. É nessa máquina que corre o backend, dentro de contentores, junto com a cache e o programa do túnel. A máquina é genuinamente pequena — memória e processamento muito limitados — e essa restrição é visível em várias decisões do projecto, nomeadamente na escolha de correr os trabalhadores de segundo plano dentro do processo da aplicação em vez de como serviços separados. A criação da máquina está automatizada em `deploy/create_gcp_vm.py` e a publicação de novas versões em `deploy/deploy_vm.py`. Um detalhe do método de publicação merece nota: o código é enviado como um arquivo comprimido através de uma ligação segura, e **não** através de clonagem do repositório na máquina. A razão é evitar que a máquina tenha credenciais de acesso ao repositório — se a máquina for comprometida, o atacante não ganha acesso ao código-fonte histórico.

#### gitleaks

*gitleaks* é uma ferramenta que examina código e histórico de alterações à procura de segredos — palavras-passe, chaves de acesso, tokens — que tenham sido acidentalmente incluídos. Existe porque este acidente é extraordinariamente comum e as suas consequências são graves e duradouras: uma vez que um segredo entra no histórico de um repositório, apagá-lo do ficheiro **não o remove do histórico**, e continua recuperável por qualquer pessoa com acesso ao repositório. A única resposta correcta a um segredo comprometido é rotacioná-lo, não removê-lo. A Diomika executa esta ferramenta em dois momentos, e a redundância é intencional. O primeiro é local, antes de cada registo de alterações, através da configuração em `.pre-commit-config.yaml` — o que impede o problema de acontecer. O segundo é automático, no sistema de verificação em `.github/workflows/ci.yml` — o que garante que ninguém contorna a verificação local. As regras específicas do projecto estão em `.gitleaks.toml`. Existe ainda um verificador complementar, `deploy/verify_bundle_secrets.py`, que examina o resultado compilado da loja para garantir que nenhum segredo do lado do servidor foi incluído no que é enviado aos browsers.

#### HMAC — Hash-based Message Authentication Code

*Código de Autenticação de Mensagem baseado em Função de Dispersão*. É uma técnica criptográfica que produz uma pequena assinatura a partir de uma mensagem e de uma chave secreta, com duas propriedades essenciais: quem não conhece a chave não consegue produzir uma assinatura válida, e qualquer alteração na mensagem invalida a assinatura. Não encripta nada — a mensagem continua legível — mas prova que foi produzida por quem conhece a chave e que não foi alterada em trânsito. A distinção face a uma simples função de dispersão é a chave secreta: sem chave, qualquer pessoa pode recalcular a dispersão de uma mensagem alterada; com chave, não. A Diomika usa esta técnica em dois pontos independentes. O primeiro são os tokens de sessão administrativa: `backend-api/core/session_tokens.py` constrói um token com o formato `dms1.<dados>.<assinatura>`, onde os dados contêm o utilizador, o papel, o momento de emissão, o momento de expiração e um identificador único, e a assinatura é calculada com uma chave derivada de `API_SECRET_KEY`. Quando o token volta, a aplicação recalcula a assinatura e compara — se não coincidir, o token é forjado e é rejeitado sem mais análise. O segundo ponto é a comparação de segredos: as funções de comparação segura usadas para verificar o cabeçalho de identificação do backoffice e as chaves de máquina a máquina são comparações de tempo constante, que não revelam informação pela duração da operação.

#### HSTS — HTTP Strict Transport Security

*Segurança Estrita de Transporte HTTP*. É um cabeçalho de resposta pelo qual um sítio instrui o browser a nunca o contactar sem encriptação durante um período declarado, mesmo que alguém peça explicitamente uma ligação não encriptada. Fecha uma janela de vulnerabilidade real: quando um utilizador escreve um nome de domínio sem indicar o protocolo, o browser tenta primeiro a versão não encriptada, e esse primeiro pedido — antes de qualquer redireccionamento — viaja em claro e pode ser interceptado ou desviado. Com esta instrução guardada, o browser converte internamente qualquer tentativa em ligação encriptada **antes** de enviar qualquer coisa. Na Diomika o cabeçalho está declarado em `frontend-web/public/_headers` com validade de um ano, aplicando-se a todos os subdomínios, e com indicação de que o domínio pode ser incluído na lista pré-distribuída com os próprios browsers — o que elimina a vulnerabilidade até no primeiro contacto de sempre. O backend aplica o mesmo cabeçalho às suas respostas em produção, através de `backend-api/core/middleware.py`. Há uma advertência operacional importante: esta instrução é **difícil de reverter**, porque vigora nos browsers que já a receberam durante todo o período declarado. Um domínio que perca a capacidade de servir tráfego encriptado torna-se inacessível, não degradado.

#### HTTP — HyperText Transfer Protocol

*Protocolo de Transferência de Hipertexto*. É o conjunto de convenções pelas quais browsers e servidores conversam, e a base de toda a web. Um pedido consiste num método (que declara a intenção), um caminho (que identifica o recurso), cabeçalhos (que transportam metadados) e, opcionalmente, um corpo (que transporta conteúdo). Uma resposta consiste num código de estado, cabeçalhos e um corpo. É um protocolo de texto legível, o que facilita enormemente o diagnóstico. A sua característica mais importante é a **ausência de estado**: cada pedido é independente e o servidor não guarda memória de pedidos anteriores, o que é a razão pela qual a web escala e a razão pela qual qualquer prova de identidade tem de ser reenviada em cada pedido. Está explicado em detalhe na secção I.6. Na Diomika, todo o tráfego público usa a versão encriptada; a única utilização de HTTP sem encriptação é interna, entre o programa do túnel e a aplicação, dentro da mesma máquina, num endereço que nunca sai dela.

#### HTTPS — HyperText Transfer Protocol Secure

*Protocolo de Transferência de Hipertexto Seguro*. É o mesmo protocolo, transportado dentro de um canal encriptado. Não muda nada na gramática: os métodos, cabeçalhos e códigos de estado são idênticos. O que muda é que ninguém no caminho consegue ler nem alterar o conteúdo, e que o cliente tem prova de estar a falar com quem pensa. Hoje não é opcional: os browsers marcam sítios sem encriptação como não seguros e recusam-lhes funcionalidades modernas. Na Diomika, `www.diomika.com` e `api.diomika.com` só aceitam ligações encriptadas, com a encriptação terminada na rede da Cloudflare, no ponto de presença mais próximo de cada visitante. Pedidos não encriptados são redireccionados, e a instrução descrita na entrada sobre HSTS impede que sequer sejam tentados por browsers que já visitaram o sítio.

#### IMAP — Internet Message Access Protocol

*Protocolo de Acesso a Mensagens de Internet*. É o protocolo usado para **ler** correio electrónico de um servidor, mantendo as mensagens no servidor e sincronizando o estado entre vários dispositivos. É o complemento do protocolo de envio: um serve para enviar, este serve para ler. A Diomika tem configuração para este protocolo em `IMAP_SERVER` e `IMAP_PORT`, e a razão é uma funcionalidade específica do backoffice: permitir ver, no mesmo lugar onde se gerem os pedidos, as respostas que os clientes enviaram por correio electrónico. Isto evita que o histórico de uma conversa comercial fique dividido entre o sistema e a caixa de correio de alguém, o que é uma fonte comum de informação perdida. É uma funcionalidade **opcional**: sem as variáveis configuradas, o backoffice funciona normalmente e a leitura de correio simplesmente não está disponível. A componente de interface correspondente é `backoffice-desktop/src/components/ConversationPanel.vue`.

#### IP — Internet Protocol address

*Endereço de Protocolo de Internet*. É o número que identifica um dispositivo numa rede, e é o único identificador que os equipamentos de rede efectivamente usam para encaminhar informação — os nomes são uma comodidade humana traduzida antes de qualquer comunicação começar. Existem dois formatos em uso: o mais antigo e comum, com quatro números separados por pontos, e o moderno, mais longo e com dois-pontos, criado porque os endereços do primeiro formato esgotaram. Na Diomika, endereços de origem são usados para contabilizar limites de ritmo — quantos pedidos vêm da mesma origem num intervalo — implementado em `backend-api/core/rate_limit.py`. Há uma subtileza importante nesse uso: como o tráfego passa pela rede da Cloudflare, o endereço que a aplicação vê directamente é o do equipamento da Cloudflare, e o endereço real do visitante vem num cabeçalho acrescentado por essa rede. Ignorar esta distinção produziria um sistema em que todos os visitantes do mundo compartilham o mesmo contador de limite, o que é simultaneamente inútil e perigoso. O endereço `127.0.0.1` merece menção separada: é o endereço de **loopback**, que um computador usa para se referir a si próprio, e tráfego para ele nunca sai da máquina. É nesse endereço que a aplicação da Diomika escuta, e é essa escolha que faz com que a máquina não tenha nada à escuta na internet.

#### JSON — JavaScript Object Notation

*Notação de Objectos JavaScript*. É o formato de troca de dados dominante na web: texto legível que descreve estruturas com apenas seis tipos — objectos, listas, textos, números, booleanos e nulo. A sua pobreza deliberada é a sua força: há muito pouco sobre que dois sistemas possam discordar. Não tem tipo de data (usa-se texto no formato normalizado internacional) nem comentários. Está tratado em detalhe na secção I.8. Na Diomika é o formato de toda a comunicação entre programas: da loja para o backend, do backoffice para o backend, do backend para o Supabase. É também o formato dos registos de eventos em produção, o que os torna consultáveis em vez de apenas legíveis. A forma de cada estrutura está declarada uma única vez em `backend-api/models/schemas.py`, e dessa declaração derivam a validação de entrada, a documentação da interface, os formulários do backoffice e o alinhamento com a estrutura da base de dados.

#### JWT — JSON Web Token

*Token Web em JSON*. É uma norma muito difundida para tokens de autenticação: um valor com três partes separadas por pontos — cabeçalho, dados e assinatura — em que os dados são legíveis por quem tiver o token e a assinatura garante que não foram alterados. A grande vantagem é ser verificável sem consulta a nenhuma base de dados: quem tem a chave confirma a assinatura e confia no conteúdo. A grande desvantagem é a consequência directa dessa vantagem: **é difícil revogar**. Um token válido continua válido até expirar, e não há forma simples de o invalidar antecipadamente sem introduzir precisamente a consulta que se queria evitar. A norma tem também um historial de vulnerabilidades de implementação notório, sobretudo em torno da negociação do algoritmo de assinatura.

**A Diomika não usa JWT de biblioteca para as sessões administrativas.** Esta é uma decisão explícita e vale a pena explicar. O que `backend-api/core/session_tokens.py` implementa são tokens próprios, com o prefixo `dms1.`, cujos dados são codificados e cuja integridade é garantida por uma assinatura calculada com a técnica descrita na entrada sobre HMAC. As razões da decisão são quatro. Primeira: **revogação real**. Uma sessão pode ser invalidada imediatamente, e é — o sistema mantém uma única sessão activa por utilizador, e emitir uma nova invalida a anterior. Segunda: **tempo de inactividade**. Além do prazo absoluto, uma sessão expira se não for usada durante um período, o que a norma não prevê nativamente. Terceira: **menos superfície**. Não usar uma biblioteca externa para autenticação significa uma dependência menos, e nenhuma exposição às vulnerabilidades de implementação dessa biblioteca. Quarta: **formato sob controlo**. O formato é definido pelo projecto, e mudá-lo não exige compatibilidade com nada externo. Os prazos são configuráveis por `ADMIN_SESSION_TTL_MINUTES` e `ADMIN_SESSION_IDLE_MINUTES`, e o estado de revogação vive numa cache partilhada em produção — obrigatoriamente, porque com várias instâncias da aplicação uma revogação em memória local não seria vista pelas outras.

#### MFA — Multi-Factor Authentication / TOTP — Time-based One-Time Password

*Autenticação Multifactor* e *Palavra-passe de Uso Único Baseada em Tempo*. Autenticação multifactor significa exigir mais do que um tipo de prova de identidade: algo que se **sabe** (uma palavra-passe), algo que se **tem** (um telefone), algo que se **é** (uma impressão digital). O valor é que comprometer um factor não é suficiente — quem descobre a palavra-passe ainda não entra. A implementação mais comum do segundo factor é a palavra-passe de uso único baseada em tempo: o servidor e uma aplicação no telefone do utilizador compartilham um segredo, e ambos calculam independentemente um código de seis dígitos que muda a cada trinta segundos. Como o cálculo depende do momento actual e do segredo compartilhado, quem não tem o segredo não pode produzir o código, e o código só serve durante um intervalo curto. Na Diomika, isto está **implementado e desligado por omissão**. A implementação usa a biblioteca `pyotp`, declarada em `requirements.txt`, e é controlada pela variável `ADMIN_MFA_REQUIRED`, cujo valor por omissão é desactivado. A razão do estado é pragmática e está documentada com honestidade no relatório principal: com um número muito pequeno de administradores, palavras-passe fortes, limitação estrita de ritmo no login, bloqueio após falhas consecutivas, e o mecanismo de identificação do programa instalado, o benefício marginal de exigir um segundo factor foi considerado inferior ao custo de o operar. É uma decisão revisível por configuração, sem alteração de código.

#### middleware (camada intermédia)

*Middleware* designa código que se coloca entre a recepção de um pedido e a lógica que o trata, vendo **todos** os pedidos e podendo agir sobre todos: examinar, alterar, recusar, medir, registar. A metáfora útil é uma série de camadas concêntricas em torno da aplicação — um pedido atravessa-as todas para entrar, e a resposta atravessa-as todas na ordem inversa para sair. A ordem em que são instaladas é significativa e é fonte de erros subtis: uma camada que registra pedidos colocada depois de uma que os recusa nunca vê os recusados. Na Diomika as camadas estão em `backend-api/core/middleware.py` e `backend-api/core/path_guard.py`, e a ordem está definida em `backend-api/main.py` com um comentário explícito a alertar que a framework as aplica na ordem inversa da instalação. As camadas são: protecção de caminhos privilegiados, que responde como se o caminho não existisse quando o acesso não é legítimo; atribuição de um identificador único a cada pedido, para correlacionar registos; acrescento de cabeçalhos de segurança a todas as respostas; instruções de cache **apenas** para respostas de catálogo; alerta de latência, que sinaliza pedidos anormalmente lentos; limitação de tamanho do pedido, baseada exclusivamente no cabeçalho que declara o tamanho; e limitação global de ritmo. Em produção acrescentam-se ainda a verificação de nomes de servidor autorizados e a política de partilha entre origens.

#### ntfy

*ntfy* é um serviço muito simples de notificações por subscrição de tópico: envia-se um pedido a um endereço que representa um tópico, e quem tiver subscrito esse tópico numa aplicação de telefone recebe a notificação. Não tem contas obrigatórias, não tem configuração complexa, e é gratuito na sua instância pública. A Diomika usa-o como canal de alertas operacionais — a forma mais barata possível de fazer chegar ao telefone de quem opera o sistema um aviso de que algo está errado, sem construir infra-estrutura de notificações. A implementação está em `backend-api/core/alerts.py`, activada pela variável `ALERT_WEBHOOK_URL`, e o destino tem de constar da lista de destinos externos autorizados descrita na entrada sobre SSRF. Há uma consideração de segurança que vale a pena registar com franqueza: **quem conhece o nome do tópico pode enviar notificações para ele**. O nome do tópico é, na prática, um segredo, e por isso não consta do repositório nem de nada entregue ao cliente. As notificações também não devem transportar informação sensível, porque atravessam um serviço público.

#### OpenAPI

*OpenAPI* é uma norma para descrever, de forma legível por máquinas, tudo o que uma interface de programação oferece: todos os endereços, os métodos aceitos, os parâmetros, a forma exacta dos dados de entrada e de saída, e os códigos de erro possíveis. O valor é que essa descrição, sendo estruturada, alimenta ferramentas: documentação navegável e testável no browser, geração automática de código cliente, e testes de conformidade. A framework usada pela Diomika **gera** esta descrição automaticamente a partir das declarações de tipo do próprio código, o que significa que ela não pode ficar desactualizada — não é um documento mantido à mão, é uma consequência do código. Na Diomika, a publicação desta descrição e da documentação navegável é **controlada por configuração e desactivada em produção final**, como se vê em `backend-api/main.py`, onde os caminhos correspondentes só são registados se a definição estiver activa. A justificação é a mesma que se aplica aos endereços de saúde detalhada: uma descrição completa e legível de todas as operações de um sistema é uma ferramenta de desenvolvimento excelente e um mapa de reconhecimento igualmente excelente.

#### OS — Operating System (sistema operativo)

O **sistema operativo** é o programa fundamental que gere o hardware de um computador e oferece aos restantes programas uma interface uniforme para o usar: memória, processador, disco, rede, ecrã. Windows, macOS e as distribuições de Linux são sistemas operativos. Importa neste relatório em dois contextos distintos. O primeiro é a distribuição do backoffice: como é um programa instalado, tem de existir uma versão para cada sistema, com o formato de distribuição que cada um espera — executável portátil em Windows, imagem de disco em macOS, ficheiro autónomo em Linux. Todas são construídas a partir da mesma base de código pelo processo em `.github/workflows/backoffice-release.yml`. O segundo contexto é o servidor: a máquina virtual corre Linux, e é sobre esse sistema que os contentores da aplicação, da cache e do túnel são executados. Um detalhe relevante: os contentores partilham o núcleo do sistema da máquina anfitriã, o que é a razão pela qual são muito mais leves do que máquinas virtuais — e a razão pela qual uma máquina muito pequena consegue correr vários.

#### outbox (caixa de saída)

*Outbox* é o nome de um padrão de arquitectura que resolve um problema real e não óbvio: como garantir que uma acção externa acontece exactamente uma vez quando pode falhar. O caso concreto na Diomika é o envio de e-mail ao receber um pedido de orçamento. A abordagem ingénua — guardar o pedido na base de dados e imediatamente enviar o e-mail — tem duas formas de falhar mal. Se o envio falhar por indisponibilidade do servidor de correio, o pedido fica registado e ninguém é notificado, e o negócio perde-se em silêncio. Se o envio funcionar mas o registo falhar, envia-se notificação de algo que não existe. O padrão resolve isto separando as duas coisas no tempo: ao processar o pedido, grava-se **na mesma transacção** o registo do pedido e uma **intenção de envio** numa tabela de saída. A transacção garante que ou ambos são gravados ou nenhum é. Depois, um processo independente e contínuo lê essa tabela, tenta enviar, e marca como concluído quando consegue — repetindo mais tarde se falhar. O resultado é que uma falha temporária do servidor de correio atrasa a notificação em vez de a perder. Na Diomika a implementação está em `backend-api/core/outbox.py` e o processo que consome a fila em `backend-api/workers/outbox_worker.py`, com a evolução da estrutura da tabela registada em `backend-api/sql/migration_outbox_claim.sql`. Esta complexidade justifica-se pelo modelo de negócio: num contexto entre empresas, um pedido perdido custa muito mais do que num contexto de consumo.

#### Pages — Cloudflare Pages

*Cloudflare Pages* é o serviço de alojamento de sítios estáticos da Cloudflare. Recebe uma pasta com o resultado de uma compilação e distribui-a por toda a rede global do fornecedor, servindo cada visitante do ponto mais próximo. É gratuito em condições generosas, o que o torna adequado à restrição de custo da Diomika. Na Diomika serve `www.diomika.com`, com os ficheiros compilados de `frontend-web/` pelo processo em `deploy/deploy_beta.py`. Cada publicação cria uma versão distinta com endereço próprio, o que permite testar antes de promover e reverter instantaneamente — uma propriedade operacional muito valiosa, porque reverter uma loja estática é mudar um apontador, não repetir uma instalação. A configuração de comportamento vive em dois ficheiros dentro de `frontend-web/public/`: `_headers`, que declara cabeçalhos de segurança e políticas de cache, e `_redirects`, que declara reescritas de caminho, incluindo a regra indispensável que faz qualquer rota interna servir o documento de entrada. O serviço permite ainda correr código na fronteira, capacidade que a Diomika usa em `frontend-web/functions/_middleware.js` para bloquear sondagens automáticas.

#### Playwright

*Playwright* é uma ferramenta de automação de browsers usada para testes de ponta a ponta: abre um browser real, navega, clica, preenche formulários e verifica o que aparece no ecrã, tal como faria uma pessoa. A diferença face a testes que verificam funções isoladas é o âmbito: um teste desta natureza exercita o sistema completo — a loja, a rede, o backend, a base de dados — e por isso detecta problemas de integração que nenhum teste isolado apanha. O preço é ser mais lento e mais sensível a variações de tempo. A Diomika usa-o para uma bateria deliberadamente pequena de verificações críticas, em `frontend-web/e2e/critical.spec.js`, configurada em `frontend-web/playwright.config.js`: que o endereço de saúde do backend responde, que a página de entrada carrega, que a política de privacidade está acessível, e que os caminhos administrativos estão efectivamente bloqueados. Esta última verificação é a mais interessante, porque é um teste **de segurança** e não de funcionalidade: confirma automaticamente, a cada alteração, que uma protecção continua activa. Protecções que ninguém testa degradam-se sem que se note, e é precisamente por isso que este teste existe.

#### PoW — Proof of Work (prova de trabalho)

*Prova de Trabalho* é uma técnica em que se exige a quem faz um pedido que resolva primeiro um problema computacional deliberadamente custoso, cuja solução é rápida de verificar. A assimetria é o ponto: custa ao cliente e não custa ao servidor. Torna-se assim economicamente inviável fazer milhões de pedidos automáticos, porque cada um obriga a gasto real de processamento. É a técnica na base de algumas criptomoedas e é usada por alguns sistemas anti-abuso como alternativa a desafios visuais, com a vantagem de não exigir interacção do utilizador. **A Diomika não usa prova de trabalho.** Consta deste glossário porque é uma alternativa conhecida ao mecanismo efectivamente adoptado, e a comparação é esclarecedora. O que a Diomika usa é a verificação anti-robô da Cloudflare, descrita na entrada sobre Turnstile, complementada por limitação de ritmo. As razões da escolha: o serviço da Cloudflare é gratuito, não requer código de verificação do lado do cliente para além da integração básica, não penaliza dispositivos lentos ou baterias de portáteis, e beneficia da informação de reputação de uma rede que vê uma fracção enorme do tráfego mundial. Prova de trabalho continua a ser uma opção defensável se o cenário de abuso mudar, mas hoje não é usada nem necessária.

#### PostgreSQL (Postgres)

*PostgreSQL*, frequentemente abreviado para *Postgres*, é o sistema de gestão de bases de dados relacionais que a Diomika usa. É de código aberto, tem décadas de desenvolvimento, e é considerado tecnicamente um dos mais sólidos que existem. Guarda dados em tabelas com colunas de tipos definidos, permite relacionar tabelas entre si, e garante propriedades transaccionais rigorosas — nomeadamente que uma operação composta ou acontece por inteiro ou não acontece de nada, o que é essencial para o padrão descrito na entrada sobre outbox. Tem características avançadas relevantes para este projecto: tipos de dados ricos, incluindo suporte nativo para documentos estruturados; e um sistema de segurança ao nível da linha, tratado na entrada sobre RLS, que permite declarar dentro da própria base de dados quem pode ver o quê. Na Diomika o Postgres é alojado no Supabase, e é onde vive toda a informação com valor: catálogo, mensagens, pedidos de orçamento, encomendas, registos de auditoria, e a fila de notificações. A ligação está em `backend-api/core/database.py` e a evolução da estrutura em `backend-api/sql/`.

#### PostHog

*PostHog* é uma plataforma de análise de utilização de produto: registra o que os visitantes fazem — que páginas vêem, que percursos seguem, onde abandonam — e permite responder a perguntas de produto com dados em vez de intuição. A Diomika usa a sua instância europeia, na camada gratuita, com a implementação em `frontend-web/src/components/CookieBanner.vue` e configuração através de variáveis com prefixo `VITE_POSTHOG_`, definidas no momento da compilação da loja. O detalhe mais importante desta entrada não é técnico, é legal e ético: **a análise só é activada depois de consentimento explícito do visitante**. Antes de o visitante aceitar, nenhum código de análise é carregado — não é carregado e desactivado, é literalmente não carregado. Esta ordem é a correcta face à legislação europeia de protecção de dados e privacidade nas comunicações electrónicas, e é frequentemente implementada ao contrário, com o rastreio a começar antes do consentimento e o aviso a servir de decoração. A política de conteúdos da loja autoriza explicitamente os destinos do serviço, e a política de privacidade em `frontend-web/src/views/PrivacyView.vue` documenta o que é recolhido.

#### pre-commit

*pre-commit* é uma ferramenta que executa verificações automáticas **no computador do programador**, imediatamente antes de cada registo de alterações, recusando o registo se alguma verificação falhar. O valor é a antecipação: um problema detectado antes de o código sair da máquina é resolvido em segundos, enquanto o mesmo problema detectado no sistema de verificação automática obriga a esperar por uma execução completa, e detectado em produção obriga a um incidente. Na Diomika a configuração está em `.pre-commit-config.yaml` e inclui duas verificações, ambas de segurança: o varrimento em busca de segredos acidentalmente incluídos, e a verificação de que o resultado compilado da loja não contém segredos do lado do servidor. As mesmas verificações são repetidas no sistema automático descrito na entrada sobre CI/CD, e a redundância é deliberada — a verificação local é uma comodidade que se pode contornar, e portanto não pode ser a única.

#### proxy (procurador, intermediário)

Um *proxy* é um intermediário que recebe pedidos e os reencaminha a outro destino, eventualmente alterando-os no caminho. Existem duas variantes, com finalidades opostas. Um *proxy* directo actua em nome do cliente, ocultando-o do servidor. Um *proxy* inverso actua em nome do servidor, recebendo os pedidos do mundo e distribuindo-os por serviços internos que não estão directamente expostos — e é esta a variante que domina a arquitectura moderna. A Diomika tem duas destas camadas em pontos diferentes. A primeira é a rede da Cloudflare, que actua como intermediário à frente de `api.diomika.com`: termina a encriptação, aplica regras de segurança, filtra, e só depois encaminha através do túnel para a máquina virtual. A segunda é dentro do backoffice: `backoffice-desktop/electron/main.cjs` corre um pequeno servidor local que recebe os pedidos da interface e os reencaminha para a nuvem, **acrescentando** o cabeçalho de identificação. Esta segunda camada é arquitecturalmente importante e vale a pena sublinhar: é o que permite que a interface visual do backoffice não conheça o segredo. A interface fala com um endereço local; o segredo é acrescentado por uma parte do programa a que a interface não tem acesso. O destino real está configurado em `backoffice-desktop/electron/api-origin.cjs`.

#### pytest

*pytest* é a framework de testes automatizados mais usada em Python, e é a que a Diomika usa para verificar o comportamento do backend. Um teste automatizado é código que exercita outro código e verifica se o resultado é o esperado; o valor está em ser executado a cada alteração, detectando não só erros novos como **regressões** — problemas antigos que voltam porque alguém desfez inadvertidamente uma correcção. A configuração está em `pytest.ini` e os testes em `backend-api/tests/`. Vale a pena notar o que os testes da Diomika verificam, porque a lista é reveladora das prioridades do projecto: `test_path_guard_hardening.py` e `test_local_only.py` verificam que os caminhos administrativos estão bloqueados a quem não deve entrar; `test_security.py` e `test_hardening.py` verificam controlos de segurança gerais; `test_admin_session.py` verifica o ciclo de vida dos tokens de sessão, incluindo expiração e revogação; `test_idor.py` verifica que ninguém consegue acessar registos de outra pessoa manipulando identificadores; `test_storage_private.py` verifica que os ficheiros privados continuam privados; `test_privacy_erase.py` verifica que o apagamento de dados pessoais funciona realmente; `test_spam_validation.py` verifica as defesas dos formulários públicos. A maioria destes testes é **de segurança**, não de funcionalidade — o que reflecte uma convicção do projecto: uma funcionalidade que se avaria é visível e alguém reclama; uma protecção que se avaria é invisível até ser explorada.

#### R2 — Cloudflare R2

*R2* é o serviço de armazenamento de objectos da Cloudflare: guarda ficheiros — imagens, documentos, arquivos — e serve-os por endereço. A sua característica comercial distintiva, e a razão pela qual é atractivo, é não cobrar pela **saída** de dados, ao contrário do serviço equivalente da Amazon, onde o custo de transferência para fora é frequentemente a parcela dominante da factura. Implementa deliberadamente a mesma interface do serviço da Amazon, o que significa que as ferramentas e bibliotecas existentes funcionam sem adaptação — daí a presença da biblioteca `boto3` nas dependências da Diomika. Na Diomika, o suporte para este serviço está **implementado e não activado**: o código está em `backend-api/utils/storage_r2.py` e só ganha vida se as variáveis com prefixo `R2_` estiverem definidas. O armazenamento efectivamente em uso é o do Supabase. A razão de o código existir sem estar activo é estratégica: se o volume de imagens crescer ao ponto de exceder a camada gratuita do Supabase, a migração passa a ser uma decisão de configuração em vez de um projecto de desenvolvimento sob pressão. A política de conteúdos da loja já autoriza imagens provenientes dos domínios deste serviço, precisamente para que a transição não exija alterar a política.

#### rate limit (limitação de ritmo)

*Rate limiting* é a prática de restringir quantos pedidos uma origem pode fazer num intervalo de tempo, respondendo com o código `429` quando o limite é excedido. Serve três propósitos distintos que convém não confundir. Contra **ataques de adivinhação de credenciais**, torna inviável testar milhares de palavras-passe — mesmo uma palavra-passe fraca resiste se só se puder testar algumas por minuto. Contra **abuso de formulários**, impede que alguém submeta milhares de pedidos de orçamento falsos. Contra **esgotamento de recursos**, protege uma máquina pequena de ser saturada, deliberadamente ou por acidente. Na Diomika a implementação está em `backend-api/core/rate_limit.py`, com uma camada global instalada em `backend-api/main.py` e limites adicionais em rotas específicas. Os limites mais estritos são os do login administrativo, e a sua contagem é dupla e deliberada: por endereço de origem **e** por nome de utilizador. A razão da duplicação é que cada uma sozinha é contornável — contar apenas por origem permite a um atacante com muitos endereços testar uma palavra-passe por endereço, e contar apenas por utilizador permite bloquear um administrador legítimo enviando falhas em nome dele. As duas em conjunto cobrem-se mutuamente. Em produção os contadores vivem numa cache partilhada, porque contadores em memória local não seriam vistos por outras instâncias da aplicação; há um mecanismo de recurso em memória para o caso de a cache estar indisponível, que degrada a protecção sem a eliminar.

#### Redis

*Redis* é uma base de dados em memória, extremamente rápida, usada tipicamente para dados temporários: contadores, caches, filas, e estado partilhado entre processos. A diferença face a uma base de dados tradicional é que guarda tudo em memória em vez de em disco, o que a torna ordens de magnitude mais rápida e volátil — se for reiniciada, o conteúdo desaparece, salvo configuração específica. Na Diomika serve dois propósitos, ambos dependentes de uma propriedade essencial: ser **partilhada** entre todos os processos da aplicação. O primeiro são os contadores de limitação de ritmo, descritos na entrada anterior. O segundo é o estado das sessões administrativas — que sessão está activa para cada utilizador, que sessões foram revogadas, e quando cada uma foi usada pela última vez — implementado em `backend-api/core/session_tokens.py`. Este segundo uso é o que torna a cache **obrigatória** em produção final: com várias instâncias da aplicação a atender pedidos, uma revogação registada apenas na memória de uma instância não seria vista pelas outras, e uma sessão terminada continuaria a funcionar. O código é explícito quanto a isso e recusa arrancar em produção final sem a variável `REDIS_URL` definida, com um mecanismo de recurso em memória apenas para desenvolvimento e pré-produção.

#### REST — Representational State Transfer

*Transferência de Estado Representacional*. É o estilo de desenho de interfaces web que consiste em usar a web da forma para que ela foi concebida: endereços que identificam **recursos** em vez de acções, métodos HTTP que transportam a **intenção**, códigos de estado usados com o seu significado padronizado, ausência de estado de conversa no servidor, e um formato de representação negociado. Está tratado na secção I.9, incluindo uma nota de honestidade que vale a pena repetir: quase nenhuma interface descrita como REST na indústria cumpre a definição académica completa do termo, e a Diomika não é excepção. O que a Diomika implementa é o conjunto de práticas pragmáticas que a indústria designa por REST, e essa designação é a convenção aceite. A interface do backend está organizada em `backend-api/routes/`, agrupada por assunto e por nível de acesso.

#### RLS — Row Level Security

*Segurança ao Nível da Linha*. É uma funcionalidade do PostgreSQL que permite declarar, **dentro da própria base de dados**, políticas que determinam que linhas de que tabelas cada tipo de utilizador pode ler, inserir, alterar ou apagar. A diferença face a verificar permissões no código da aplicação é fundamental: a política é aplicada pelo motor da base de dados e não pode ser contornada por nenhum caminho de acesso. Mesmo que alguém consiga executar uma consulta directa, a política aplica-se. Na arquitectura da Diomika, esta funcionalidade não é um extra — é o que torna segura uma decisão central. Como o frontend da loja lê o catálogo **directamente** do Supabase com uma chave pública, não há código da aplicação a mediar essa leitura, e portanto a única protecção possível é a que vive na base de dados. As políticas declaram, em substância, que a chave pública pode ler produtos e categorias marcados como visíveis, e nada mais: não pode ver registos ocultos, não pode ver mensagens de contacto, não pode ver pedidos de orçamento, não pode ver encomendas, e não pode escrever nada. Toda a escrita passa pela interface de programação, usando a chave privilegiada que ignora as políticas por desenho e que existe apenas no servidor. As políticas estão declaradas em `deploy/supabase_pre_deploy.sql` e nos ficheiros de `backend-api/sql/`, e existe um verificador em `deploy/verify_rls.py` que confirma que continuam em vigor — porque uma política que se degrada silenciosamente expõe a base de dados inteira sem que nada deixe de funcionar.

#### S3 — Simple Storage Service

*Serviço de Armazenamento Simples*. É o serviço de armazenamento de objectos da Amazon, lançado em 2006, e a razão pela qual aparece neste glossário é sobretudo histórica e normativa: a sua interface tornou-se a norma de facto da indústria, ao ponto de vários fornecedores concorrentes a implementarem deliberadamente para que as ferramentas existentes funcionem sem adaptação. Diz-se hoje "compatível com S3" como se dissesse "compatível com uma norma". A Diomika **não usa** o serviço da Amazon. Usa a biblioteca escrita para ele — `boto3` — para falar com o serviço equivalente da Cloudflare, no caminho alternativo de armazenamento implementado em `backend-api/utils/storage_r2.py` e não activado. O armazenamento em uso é o do Supabase, que tem a sua própria interface, usada em `backend-api/utils/storage.py`. É um bom exemplo de como uma norma de facto reduz o custo de mudar de fornecedor: a portabilidade não vem de uma norma oficial, vem de a indústria ter convergido numa interface.

#### saga

*Saga* é o nome de um padrão de arquitectura para operações compostas de vários passos que podem falhar a meio, e onde não é possível envolver todos os passos numa única transacção de base de dados — tipicamente porque alguns passos são externos, como enviar um e-mail ou chamar um serviço. Uma transacção de base de dados garante que ou tudo acontece ou nada acontece; mas não se pode "desfazer" um e-mail enviado. O padrão consiste em decompor a operação em passos com estado explícito, registar o progresso de forma persistente, e definir, para cada passo, o que fazer se ele falhar — repetir, compensar, ou sinalizar para intervenção humana. A Diomika usa este padrão em `backend-api/core/saga/`, com implementações em `contact_saga.py` e `orcamento_saga.py`, apoio de registo em `logging.py`, e manutenção em `maintenance.py`. O fluxo típico de um pedido de orçamento é: validar a entrada, verificar a prova anti-robô, garantir que uma submissão repetida não cria um segundo registo, gravar o pedido, colocar as notificações na fila de saída, e responder ao cliente. Se a gravação falhar, nada é notificado. Se a notificação falhar temporariamente, o pedido está gravado e a notificação é repetida mais tarde pelo processo de segundo plano. O que este padrão consegue, e o que o justifica num sistema desta dimensão, é que **nenhuma falha parcial deixa o sistema num estado incoerente** — e, sobretudo, que nenhum pedido comercial se perde em silêncio.

#### scrypt

*scrypt* é uma função de derivação de chave desenhada especificamente para transformar palavras-passe em valores guardáveis de forma segura. A necessidade é a seguinte: um sistema nunca deve guardar palavras-passe, porque uma fuga da base de dados exporia todas as contas de todos os utilizadores — e como as pessoas reutilizam palavras-passe, exporia também contas noutros serviços. O que se guarda é o resultado de uma transformação matemática irreversível: verifica-se uma tentativa de login aplicando a mesma transformação e comparando resultados. Mas uma transformação irreversível comum não basta, porque um atacante com a base de dados pode testar milhares de milhões de palavras-passe candidatas por segundo em hardware especializado. As funções desenhadas para palavras-passe resolvem isso sendo deliberadamente **lentas** e, no caso desta, deliberadamente **exigentes em memória** — o que anula a vantagem do hardware especializado, porque memória é caro paralelizar. Na Diomika a implementação está em `backend-api/core/admin_users.py`, com parâmetros de custo explícitos e um valor aleatório único por utilizador — o *salt* — que garante que duas pessoas com a mesma palavra-passe produzem valores guardados diferentes, e que impede o uso de tabelas pré-calculadas. Não existe forma de recuperar a palavra-passe original a partir do que está guardado; um esquecimento resolve-se definindo uma nova, não recuperando a antiga.

#### SDK — Software Development Kit

*Kit de Desenvolvimento de Software*. É um conjunto de bibliotecas, ferramentas e documentação que um fornecedor disponibiliza para facilitar a integração com o seu serviço. A alternativa é falar directamente com a interface do serviço, construindo os pedidos à mão — o que é sempre possível e quase sempre mais trabalhoso e mais propenso a erro, porque implica reimplementar autenticação, tratamento de erros, repetições e casos limite. A Diomika usa vários destes kits: o do Supabase para Python, declarado em `requirements.txt` e usado no backend; o do Supabase para JavaScript, declarado em `frontend-web/package.json` e usado pela loja para ler o catálogo; o kit do serviço de captura de erros, na variante integrada com a framework do backend; a biblioteca de análise de utilização, na loja; e a biblioteca de acesso a armazenamento compatível com a norma da Amazon, no caminho alternativo não activado. Cada um destes kits é também uma dependência a manter actualizada, que é a razão pela qual existe vigilância automática de versões, descrita na entrada sobre Dependabot.

#### Sentry

*Sentry* é um serviço de captura e agregação de erros. Quando uma aplicação falha de forma imprevista, o serviço recebe o detalhe completo — a excepção, o rastreio da pilha de chamadas, o contexto do pedido, a versão do código — e agrupa ocorrências semelhantes, mostrando quantas vezes cada problema ocorreu, quando começou, e quantos utilizadores afectou. O valor é passar de "alguém disse que deu erro" para um relatório preciso e reproduzível. Na Diomika a integração está em `backend-api/core/sentry_init.py` e `backend-api/core/error_tracking.py`, activada pela presença da variável `SENTRY_DSN` e desactivada silenciosamente na sua ausência. A ligação com o tratador global de excepções em `backend-api/main.py` é a parte interessante: em produção, o cliente recebe uma mensagem deliberadamente vaga — apenas a indicação de que ocorreu um erro interno — enquanto o detalhe completo vai para os registos e para este serviço. A assimetria é intencional: mensagens de erro detalhadas são informação valiosa para quem sonda um sistema, revelando versões de bibliotecas, caminhos de ficheiros e estrutura de dados. Quem precisa do detalhe é quem opera o sistema, e é a esse que ele é entregue.

#### service role (chave de serviço do Supabase)

A *service role key* é a segunda das duas chaves que o Supabase entrega a cada projecto, e é a chave de administração: **ignora todas as políticas de segurança ao nível da linha, por desenho**. Quem a tem pode ler, alterar e apagar tudo, sem restrição. É o instrumento correcto para o código do servidor, que precisa de escrever em nome de utilizadores e de aplicar as suas próprias regras de autorização; e é uma catástrofe se sair do servidor. Na Diomika esta chave existe exclusivamente na variável `SUPABASE_KEY`, dentro do ficheiro de configuração da máquina virtual — um ficheiro que está excluído do controlo de versões e que nunca sai da máquina. Nunca é enviada a um browser, nunca é embutida num instalador do backoffice, nunca aparece numa resposta da interface de programação. Existem verificações automáticas dedicadas a garantir isto: `deploy/verify_bundle_secrets.py` examina o resultado compilado da loja e falha se encontrar lá a chave, e `deploy/verify_env_separation.py` verifica que as variáveis destinadas ao servidor não estão a ser expostas ao processo de compilação do frontend. Esta entrada deve ser lida em conjunto com a entrada sobre *anon key*: o par de chaves resume a filosofia de segurança do projecto — a chave pública tem poderes limitados por regras do lado do servidor, e a chave de poderes ilimitados nunca sai do servidor.

#### signed URL (endereço assinado)

Um *signed URL* é um endereço temporário que dá acesso a um ficheiro privado sem exigir autenticação de quem o abre. Funciona porque o próprio endereço contém uma assinatura criptográfica e um prazo de validade: quem o tem consegue abrir o ficheiro, e depois do prazo o mesmo endereço deixa de funcionar. Resolve um problema concreto e comum: mostrar imagens privadas num browser. Um browser que carrega uma imagem não sabe anexar cabeçalhos de autenticação a esse carregamento; o endereço tem de ser auto-suficiente. A alternativa — tornar todas as imagens permanentemente públicas — significa que qualquer endereço descoberto uma vez funciona para sempre, para qualquer pessoa. Na Diomika, isto é controlado pela variável `SUPABASE_STORAGE_PRIVATE`: quando activa, o armazenamento de imagens é privado e a interface de programação gera endereços assinados com prazo curto, em `backend-api/utils/storage.py` e `backend-api/utils/image_urls.py`. O comportamento correcto está verificado por testes automatizados em `backend-api/tests/test_storage_private.py`. A justificação alinha-se com o modelo de negócio: num contexto entre empresas, as fotografias de produto são material comercial, e a decisão de que não devem ser endereços públicos eternos é razoável.

#### SmartScreen

*SmartScreen* é o sistema de reputação do Windows que avisa quando um utilizador tenta executar um programa pouco conhecido, especialmente se não estiver assinado por um certificado de código reconhecido. Funciona por reputação acumulada: programas descarregados muitas vezes sem incidentes ganham confiança; programas novos ou raros são sinalizados, mesmo sendo legítimos. Isto cria uma dificuldade estrutural para projectos pequenos, porque a reputação exige volume que um projecto pequeno não tem, e o atalho — um certificado de assinatura de código — é pago e exige validação de identidade da entidade. A Diomika **não assina** o executável do backoffice, decisão de custo registada explicitamente no relatório principal. A consequência é um aviso na primeira execução, que exige um passo explícito do utilizador para prosseguir. Está documentado nas instruções entregues ao cliente. É o equivalente para Windows do que a entrada sobre Gatekeeper descreve para macOS, e o compromisso é o mesmo: uma limitação assumida e comunicada, em vez de omitida.

#### SMTP — Simple Mail Transfer Protocol

*Protocolo Simples de Transferência de Correio*. É o protocolo usado para **enviar** correio electrónico — o complemento do protocolo de leitura descrito na entrada sobre IMAP. Um programa que quer enviar uma mensagem liga-se a um servidor de correio, autentica-se, e entrega a mensagem para encaminhamento. Na Diomika a configuração está nas variáveis `MAIL_SERVER`, `MAIL_PORT`, `MAIL_USERNAME`, `MAIL_PASSWORD` e `MAIL_FROM`, e a implementação em `backend-api/utils/email_sender.py`, com a composição das mensagens em `backend-api/utils/email_body.py`. O envio é usado para notificar a Diomika de novos pedidos de orçamento e mensagens de contacto, e para enviar confirmações aos clientes. Um detalhe de arquitectura importante: os envios **não** acontecem directamente no momento em que um pedido é processado. Passam pela fila persistente descrita na entrada sobre outbox, e são executados por um processo de segundo plano em `backend-api/workers/email_worker.py`. A razão é que servidores de correio falham temporariamente com regularidade, e um pedido de orçamento perdido por causa de uma indisponibilidade momentânea do serviço de correio é um custo comercial inaceitável.

#### SPA — Single-Page Application

*Aplicação de Página Única*. É o modelo em que o browser carrega uma vez um documento e um programa, e a partir daí é o programa que gere a navegação e reescreve as partes do ecrã que mudam, buscando apenas **dados** quando necessário. A página nunca é recarregada. As vantagens são navegação instantânea, preservação de estado entre ecrãs, e transferências muito menores. As desvantagens são primeira visita mais lenta, indexação por motores de busca mais frágil, dependência de JavaScript, e maior consequência de erros não tratados. Está tratado em detalhe na secção I.10. A loja da Diomika é uma aplicação deste tipo, construída com Vue, com o roteamento em `frontend-web/src/router/index.js` e a regra de servidor indispensável em `frontend-web/public/_redirects`. O backoffice também o é, com a diferença de correr dentro de uma aplicação instalada em vez de ser servido por um sítio.

#### SQL — Structured Query Language

*Linguagem de Consulta Estruturada*. É a linguagem padronizada para interrogar e manipular bases de dados relacionais. É declarativa, o que significa que se descreve o **resultado desejado** e não os passos para o obter — o motor da base de dados decide como executar a consulta da forma mais eficiente. Uma consulta descreve que colunas se querem, de que tabelas, com que condições, com que ordenação e com que agrupamentos. Na Diomika, a linguagem aparece em dois contextos. O primeiro é a definição da estrutura da base de dados: `deploy/supabase_pre_deploy.sql` contém a preparação de produção, incluindo as políticas de segurança ao nível da linha, e `backend-api/sql/` contém a evolução da estrutura ao longo do tempo em ficheiros nomeados por assunto. O segundo contexto é a execução controlada de operações de estrutura, através de `backend-api/core/sql_runner.py`, usada pelo mecanismo que mantém a base de dados alinhada com as declarações de forma dos dados. Existe uma classe de vulnerabilidade associada a esta linguagem, chamada injecção, em que dados fornecidos por um utilizador são interpretados como comandos; a defesa correcta é usar sempre consultas parametrizadas, em que os dados nunca são concatenados no texto do comando, e é o que os kits de acesso usados pela Diomika fazem por omissão.

#### SSH — Secure Shell

*Consola Segura*. É o protocolo usado para obter acesso remoto encriptado à linha de comandos de outra máquina, e é a ferramenta padrão de administração de servidores. A autenticação faz-se preferencialmente por par de chaves criptográficas em vez de palavra-passe: guarda-se a parte pública no servidor e a parte privada na máquina do administrador, e a posse da parte privada é a prova de identidade. É materialmente mais seguro do que palavra-passe, porque não há nada para adivinhar. Na Diomika este protocolo é usado para administrar a máquina virtual e é o meio pelo qual `deploy/deploy_vm.py` publica novas versões — enviando o código como arquivo comprimido através de uma ligação segura. Duas notas importantes. Primeira: o acesso a este protocolo **não** é entregue ao cliente. O que o cliente recebe é o instalador do backoffice; a administração da infra-estrutura permanece com quem a opera, e essa fronteira está documentada explicitamente no relatório principal. Segunda: como a máquina virtual usa um túnel para publicar a interface de programação, este é o único caminho de acesso administrativo à máquina, e a sua protecção é proporcionalmente importante.

#### SSL — Secure Sockets Layer

*Camada de Sockets Segura*. É o nome histórico da tecnologia de encriptação de comunicações na web, criada nos anos 90. **Todas** as suas versões estão obsoletas e desactivadas por serem inseguras; o que hoje funciona é o seu sucessor, descrito na entrada sobre TLS. O nome sobreviveu na linguagem da indústria — diz-se "certificado SSL" para significar "certificado TLS", e a maioria dos painéis de fornecedores usa os dois termos indistintamente. Neste relatório, qualquer aparição de "SSL" é uma referência ao nome histórico; o que a Diomika efectivamente usa é TLS, na versão mais recente que o browser do visitante e a rede da Cloudflare consigam negociar.

#### SSRF — Server-Side Request Forgery

*Falsificação de Pedido do Lado do Servidor*. É uma classe de ataque em que se induz o servidor a fazer um pedido a um destino escolhido pelo atacante. É perigosa por uma razão específica: o servidor está **dentro** da rede, e portanto consegue chegar a lugares que o atacante não consegue alcançar directamente. Em ambientes de nuvem, existe tipicamente um endereço interno de serviço de metadados que devolve credenciais da máquina a quem o consultar de dentro — e um pedido induzido a esse endereço pode devolver ao atacante as credenciais de acesso à conta de nuvem inteira. É um vector de ataque com historial de comprometimentos graves e muito reais. A Diomika defende-se de forma sistemática. Qualquer pedido que o backend faça para fora — alertas, envio de registos para o serviço de agregação, verificação anti-robô — passa obrigatoriamente por uma função de validação em `backend-api/core/ssrf_guard.py`, que impõe três regras: só o protocolo encriptado é aceito; o servidor de destino tem de constar de uma lista fechada de destinos autorizados; e endereços de rede privada, de loopback e do serviço de metadados de nuvem são bloqueados explicitamente. Os destinos autorizados por omissão são os que o sistema realmente precisa: a Cloudflare, o serviço de notificações, e os pontos de ingestão do serviço de agregação de registos. Existe um verificador em `deploy/verify_ssrf_coverage.py` que confirma que nenhum caminho de código faz pedidos externos sem passar por esta validação — porque uma protecção que cobre nove de dez caminhos não protege nada.

#### TLS — Transport Layer Security

*Segurança da Camada de Transporte*. É a tecnologia que encripta comunicações na internet, sucessora da descrita na entrada sobre SSL, actualmente nas versões 1.2 e 1.3. Garante três coisas distintas: **confidencialidade**, porque ninguém no caminho consegue ler; **integridade**, porque ninguém no caminho consegue alterar sem que se detecte; e **autenticidade**, porque o certificado apresentado pelo servidor prova a sua identidade contra uma cadeia de entidades em que o browser já confia. Está explicado em detalhe na secção I.7, incluindo o mecanismo do aperto de mão e o conceito de terminação. Na Diomika, a encriptação é terminada pela rede da Cloudflare, no ponto de presença mais próximo de cada visitante, com certificados emitidos e renovados automaticamente pelo fornecedor. Existe um único trecho do caminho sem encriptação, entre o programa do túnel e a aplicação, num endereço de loopback que nunca sai da máquina — e a secção I.7 explica porque essa decisão é correcta e não uma omissão.

#### TOTP — Time-based One-Time Password

*Palavra-passe de Uso Único Baseada em Tempo*. É o mecanismo dos códigos de seis dígitos que mudam a cada trinta segundos, gerados por aplicações de autenticação em telefones. Funciona por um segredo compartilhado entre o servidor e a aplicação: ambos calculam independentemente o mesmo código a partir desse segredo e do momento actual. Quem não tem o segredo não pode produzir o código, e o código expira rapidamente. É a forma mais comum de segundo factor de autenticação. Na Diomika está **implementado e desligado por omissão**, usando a biblioteca `pyotp` e controlado pela variável `ADMIN_MFA_REQUIRED`. Ver a entrada sobre MFA, onde a decisão está explicada.

#### TTL — Time To Live

*Tempo de Vida*. É a duração durante a qual um valor guardado permanece válido antes de ter de ser renovado ou de deixar de existir. É um conceito transversal que aparece em vários contextos deste relatório, com o mesmo significado e consequências diferentes. Nas respostas do sistema de nomes, determina durante quanto tempo uma tradução pode ser reutilizada — e é a razão pela qual alterações de configuração de rede não são instantâneas e criam uma janela em que parte do mundo vê o destino antigo. Nas instruções de cache HTTP, determina quanto tempo um browser ou uma rede de distribuição pode reutilizar uma resposta. Nos tokens de sessão da Diomika, determina a validade absoluta de uma sessão, configurada em `ADMIN_SESSION_TTL_MINUTES`, complementada por um prazo de inactividade em `ADMIN_SESSION_IDLE_MINUTES`. Nos endereços assinados de acesso a imagens privadas, determina durante quanto tempo o endereço funciona. Nos contadores de limitação de ritmo, determina a janela de contagem. Em todos os casos, o valor exprime o mesmo compromisso: um prazo curto é mais seguro e mais lento; um prazo longo é mais rápido e mais arriscado.

#### Tunnel — Cloudflare Tunnel

*Túnel da Cloudflare* é a tecnologia que publica um serviço na internet **sem abrir portas** na máquina onde ele corre. O funcionamento é o inverso do modelo tradicional: em vez de a máquina esperar ligações do exterior, um programa dentro dela — descrito na entrada sobre cloudflared — estabelece uma ligação de saída até à rede da Cloudflare e mantém-na aberta. Os pedidos que chegam ao endereço público são encaminhados por dentro dessa ligação já estabelecida. As consequências de segurança são substanciais: nenhuma porta aberta, nenhuma regra de firewall de entrada, nenhum endereço público a proteger, e nada que uma varredura de portas possa encontrar. A protecção não é uma configuração que se possa esquecer de aplicar — é uma propriedade da topologia. Na Diomika, o túnel publica `api.diomika.com` encaminhando para `http://127.0.0.1:8000` dentro da máquina virtual, configurado em `deploy/docker-compose.free.yml` e autenticado pelo segredo em `CLOUDFLARE_TUNNEL_TOKEN`. Um efeito colateral útil para o diagnóstico: um erro `502` em `api.diomika.com` significa especificamente que a rede está de pé mas não consegue falar com a máquina — o túnel caiu, ou o contentor está em baixo — o que é uma informação muito mais precisa do que um erro genérico.

#### Turnstile — Cloudflare Turnstile

*Turnstile* é o serviço da Cloudflare de verificação de que um pedido vem de uma pessoa e não de um programa automático. É o substituto moderno dos desafios visuais de identificar imagens: na maioria dos casos não exige interacção nenhuma do utilizador, resolvendo o desafio em segundo plano com base em sinais do browser e na informação de reputação de uma rede que observa uma fracção enorme do tráfego mundial. O funcionamento tem duas metades, e a segunda é a que importa. O frontend obtém um valor de prova, usando uma chave pública que pode ser visível — na Diomika, `VITE_TURNSTILE_SITE_KEY`, integrada em `frontend-web/src/composables/useTurnstile.js`. Esse valor é enviado com a submissão, e o **backend verifica-o junto do serviço da Cloudflare**, usando uma chave secreta que só existe no servidor — `TURNSTILE_SECRET_KEY`, com a verificação em `backend-api/utils/turnstile.py`. Esta segunda metade é indispensável e é frequentemente omitida em integrações apressadas: sem verificação do lado do servidor, a prova é apenas decoração, porque um atacante que fabrique pedidos directamente ignora completamente o widget. A Diomika usa este mecanismo nos formulários públicos de contacto e de pedido de orçamento, complementado por limitação de ritmo, que responde a um problema diferente — o abuso por parte de quem consegue resolver a verificação.

#### UA — User Agent

*Agente de Utilizador*. É o cabeçalho HTTP pelo qual um programa se identifica ao fazer um pedido: que browser, que versão, que sistema operativo. Historicamente foi usado para adaptar respostas a capacidades diferentes de browsers diferentes, prática hoje desencorajada porque o valor é trivialmente falsificável e porque existem formas melhores de detectar capacidades. Continua a ser útil para dois fins legítimos: estatísticas agregadas de utilização, e detecção de padrões de abuso — robôs frequentemente usam valores por omissão de bibliotecas, ou valores ausentes, ou valores manifestamente inconsistentes. Na Diomika, este cabeçalho é registado nos registos estruturados para diagnóstico e análise de padrões, e pode contribuir para decisões de bloqueio. Nunca é usado como base de autorização — a regra é a mesma que se aplica a tudo o que vem do cliente: pode informar uma decisão, não pode ser a decisão.

#### UptimeRobot

*UptimeRobot* é um serviço de monitorização externa de disponibilidade: verifica periodicamente, de fora, se um endereço responde, e avisa quando deixa de responder. O adjectivo "externa" é o essencial desta entrada. Monitorização interna — a própria aplicação a verificar-se — tem um ponto cego fatal: se a aplicação estiver em baixo, não verifica nada e não avisa ninguém. Monitorização externa não tem esse problema, porque o observador é independente do observado. A Diomika usa este serviço na camada gratuita, com verificações independentes para `www.diomika.com` e para o endereço de saúde de `api.diomika.com`. A separação é deliberada: as duas superfícies estão em infra-estruturas diferentes e podem falhar independentemente, e saber qual das duas falhou reduz imediatamente o espaço de diagnóstico. Existe uma verificação secundária, redundante, no processo automático `.github/workflows/uptime.yml`, apoiada pelo script `deploy/uptime_check.py` — porque um serviço de monitorização gratuito é ele próprio um ponto de falha, e ter dois observadores independentes é barato.

#### URI / URL — Uniform Resource Identifier / Uniform Resource Locator

*Identificador Uniforme de Recurso* e *Localizador Uniforme de Recurso*. Um identificador nomeia um recurso; um localizador nomeia-o **e** diz como chegar a ele. Na prática corrente, quase tudo o que se chama identificador é também localizador, e os dois termos usam-se indistintamente. A anatomia de um endereço vale a pena decompor, porque cada parte aparece em decisões deste relatório. Em `https://api.diomika.com/api/produtos?categoria=almofadas`: `https` é o **esquema**, que diz que protocolo usar; `api.diomika.com` é o **servidor**, que o sistema de nomes traduz num endereço numérico; `/api/produtos` é o **caminho**, que identifica o recurso dentro do servidor; e `?categoria=almofadas` são os **parâmetros de consulta**, que refinam o pedido. Há uma consequência de segurança que merece destaque: os parâmetros de consulta aparecem em registos de servidores, em históricos de browsers e em cabeçalhos de referência enviados a terceiros. Nunca devem transportar informação sensível — nem palavras-passe, nem tokens. É uma das razões pelas quais a Diomika transporta os tokens de sessão no cabeçalho `Authorization` e não no endereço.

#### uvicorn

*uvicorn* é o servidor que executa a aplicação do backend da Diomika. A distinção entre framework e servidor confunde quem vem de fora e é simples: a framework define o que a aplicação faz com cada pedido; o servidor é o programa que escuta na rede, recebe os pedidos, entrega-os à aplicação segundo a norma descrita na entrada sobre ASGI, e devolve as respostas. São responsabilidades distintas, e a separação permite trocar um sem tocar no outro. Na Diomika o servidor é iniciado dentro do contentor da aplicação, configurado nos ficheiros de composição, e escuta em `127.0.0.1:8000` — deliberadamente no endereço de loopback, para que não aceite ligações de fora da máquina. Para desenvolvimento local, `backend-api/main.py` tem um arranque directo na porta 8001, ajustável pela variável `DIOMIKA_API_PORT`. A escolha de portas diferentes para desenvolvimento e produção não é arbitrária: reduz a probabilidade de um erro de configuração fazer com que um ambiente fale acidentalmente com o outro.

#### UUID — Universally Unique Identifier

*Identificador Universalmente Único*. É um valor de 128 bits, escrito em cinco grupos de dígitos hexadecimais separados por hífenes, com a propriedade de poder ser gerado de forma independente por qualquer sistema, sem coordenação com nenhum outro, com probabilidade praticamente nula de colisão. A vantagem face a identificadores sequenciais é dupla. A primeira é operacional: podem ser gerados no cliente, antes de qualquer ida ao servidor, o que simplifica fluxos de criação. A segunda é de segurança e é a mais importante: identificadores sequenciais são **adivinháveis**. Um sistema em que o pedido de orçamento número 1247 é acessível em `/orcamentos/1247` convida qualquer pessoa a tentar 1246 e 1248 — uma classe de vulnerabilidade conhecida como referência directa insegura a objecto. Com identificadores aleatórios, não há sequência para percorrer. A Diomika usa este tipo de identificador nas suas tabelas principais, e a protecção não depende apenas da imprevisibilidade: existe verificação explícita de autorização em cada acesso, e essa verificação está testada automaticamente em `backend-api/tests/test_idor.py`. A imprevisibilidade é uma camada, não a defesa.

#### Vite

*Vite* é a ferramenta de construção usada pelos dois frontends da Diomika. Faz duas coisas muito diferentes. Em desenvolvimento, corre um servidor local que aplica alterações no ecrã quase instantaneamente, sem recarregar a página e sem perder o estado da aplicação — uma diferença que altera materialmente a velocidade de trabalho. Em construção para produção, compila todo o código-fonte num conjunto optimizado de ficheiros: minimizados, divididos por rota para que uma primeira visita não descarregue a aplicação inteira, e — o detalhe mais consequente — com nomes que incluem uma impressão digital do conteúdo. Essa impressão digital é o que permite instruir os browsers a guardar os ficheiros por um ano com total segurança, porque uma versão nova tem sempre um nome novo. É a base da política de cache declarada em `frontend-web/public/_headers`. As configurações estão em `frontend-web/vite.config.js` e `backoffice-desktop/vite.config.js`. As variáveis de ambiente com prefixo `VITE_` são as únicas que esta ferramenta injecta no código compilado, e essa convenção é uma protecção real: uma variável de servidor sem esse prefixo não pode acidentalmente ser incluída no que é enviado aos browsers.

#### VM — Virtual Machine (máquina virtual)

Uma **máquina virtual** é um computador simulado por software dentro de um computador físico. Tem o seu próprio sistema operativo, a sua própria memória atribuída, o seu próprio disco, e comporta-se como uma máquina independente — embora partilhe hardware com outras máquinas virtuais no mesmo anfitrião. É a tecnologia que sustenta praticamente toda a computação em nuvem: um fornecedor compra servidores grandes e aluga fatias deles. A Diomika usa uma máquina virtual pequena da camada sempre gratuita do fornecedor descrito na entrada sobre GCP, e é nela que corre o backend, junto com a cache e o programa do túnel, todos em contentores. A restrição de recursos dessa máquina é real e visível em decisões concretas: os trabalhadores de segundo plano correm **dentro** do processo da aplicação, controlado pela variável `RUN_EMBEDDED_WORKERS`, em vez de como serviços separados, precisamente para poupar memória. A criação está automatizada em `deploy/create_gcp_vm.py`, a publicação de versões em `deploy/deploy_vm.py`, e as considerações para o caso de o sistema crescer estão documentadas em `deploy/SCALE.md`. Note-se a diferença face a um contentor: uma máquina virtual simula hardware e tem o seu próprio núcleo de sistema; um contentor partilha o núcleo do anfitrião e é muito mais leve. A Diomika usa as duas tecnologias em conjunto — contentores dentro de uma máquina virtual.

#### VPN — Virtual Private Network (vs. Tunnel)

*Rede Privada Virtual*. É uma tecnologia que cria uma ligação encriptada entre um dispositivo e uma rede, fazendo com que o dispositivo se comporte como se estivesse fisicamente dentro dessa rede. É usada tipicamente para dois fins: dar a trabalhadores remotos acesso a recursos internos de uma empresa, e ocultar o tráfego de um utilizador do seu operador de rede. **A Diomika não usa este tipo de rede**, e a distinção face à tecnologia que efectivamente usa merece ser explicitada, porque as duas são frequentemente confundidas.

Uma rede privada virtual dá acesso a **uma rede**: quem se liga passa a poder alcançar tudo o que está dessa rede, sujeito a regras adicionais. Requer um servidor com um endereço público a aceitar ligações, requer distribuição e gestão de credenciais por dispositivo, e requer configuração em cada cliente. Um túnel, na acepção da entrada sobre Tunnel, publica **um serviço específico**, em sentido inverso: a ligação parte de dentro, não há nada a aceitar ligações do exterior, não há credenciais a distribuir aos utilizadores, e o cliente é um browser comum sem configuração nenhuma. Para o caso de uso da Diomika — publicar uma interface de programação na internet, para clientes que não são administradores da rede — o túnel é claramente a ferramenta certa. Uma rede privada virtual seria a ferramenta certa se o objectivo fosse dar a um administrador acesso a vários recursos internos da máquina, o que não é o caso: a administração é feita através do protocolo descrito na entrada sobre SSH.

#### Vue

*Vue* é a biblioteca de construção de interfaces usada pelos dois frontends da Diomika. O seu contributo central é a ligação automática entre dados e apresentação: em vez de escrever instruções para actualizar o ecrã quando um valor muda, declara-se a relação entre os dados e o que se vê, e a biblioteca mantém os dois em sincronia. Isto elimina uma classe inteira de bugs — os de inconsistência visual, em que o ecrã mostra um estado que já não corresponde aos dados. O código organiza-se em componentes, ficheiros com extensão `.vue` que reúnem no mesmo lugar a estrutura, o comportamento e o estilo de uma peça da interface. Na Diomika, a loja está em `frontend-web/src/` e o backoffice em `backoffice-desktop/src/`, ambos com a mesma tecnologia — o que significa que as competências e os padrões são reutilizáveis entre os dois, uma vantagem material para uma equipa pequena. A navegação usa a biblioteca de roteamento oficial, declarada em `frontend-web/src/router/index.js` e `backoffice-desktop/src/router/index.js`.

#### WAF — Web Application Firewall

*Firewall de Aplicação Web*. É um sistema de filtragem que examina pedidos HTTP e bloqueia os que correspondem a padrões de ataque, actuando antes de o pedido chegar à aplicação. Distingue-se de uma firewall de rede convencional por operar ao nível da aplicação: uma firewall de rede decide com base em endereços e portas, enquanto esta decide com base em caminhos, cabeçalhos, parâmetros e conteúdo. A Diomika usa o sistema da Cloudflare, com as regras específicas do projecto documentadas em `deploy/cloudflare/waf_rules.json`. A regra mais importante é uma que espelha, na fronteira da rede, a protecção que a aplicação já aplica internamente: bloqueia pedidos a caminhos administrativos que não tragam o cabeçalho de identificação correcto. A duplicação é **intencional** e é um exemplo do princípio de defesa em profundidade. Se a aplicação for republicada com uma configuração errada, ou se uma alteração de código introduzir inadvertidamente uma brecha na protecção interna, a regra na fronteira continua a bloquear — e vice-versa. Duas protecções independentes falham em conjunto muito menos frequentemente do que uma falha sozinha, e o custo de manter a segunda é baixo.

#### worker (trabalhador)

Um *worker* é um processo que executa trabalho de forma independente dos pedidos que chegam do exterior. A necessidade surge de uma restrição do ciclo pedido/resposta: quem submete um formulário espera uma resposta rápida, e há trabalho que não pode ser feito nesse tempo — enviar vários e-mails, gerar documentos, processar imagens, limpar registos antigos. A solução é registar a intenção e responder imediatamente, deixando a execução para um processo que trabalha em segundo plano. Na Diomika existem dois: `backend-api/workers/email_worker.py`, que envia os e-mails pendentes, e `backend-api/workers/outbox_worker.py`, que processa a fila persistente descrita na entrada sobre outbox. A forma como correm é uma consequência directa da restrição de recursos do projecto e vale a pena notar. No cenário de produção actual, correm **dentro** do processo da aplicação, em fios de execução separados, geridos por `backend-api/core/background_workers.py` e activados pela variável `RUN_EMBEDDED_WORKERS` — o que poupa a memória que processos separados consumiriam numa máquina muito pequena. No cenário alternativo descrito em `docker-compose.yml`, correm como serviços independentes, que é a solução mais robusta porque isola falhas. A escolha é um compromisso assumido: menos elegante, e o que a memória disponível permite.

#### XSS — Cross-Site Scripting

*Injecção de Script entre Sítios*. É a classe de vulnerabilidade em que um atacante consegue inserir código numa página que outros utilizadores vão ver, e esse código corre no browser das vítimas com todos os privilégios da página legítima — podendo ler tokens, ler conteúdo, e fazer pedidos em nome do utilizador. O vector clássico é conteúdo fornecido por utilizadores que é apresentado sem tratamento: se alguém escreve uma etiqueta de script num campo de texto e esse texto é inserido no documento sem escape, o código executa-se. A Diomika defende-se em três camadas independentes. A primeira é a biblioteca de interface: o Vue trata o texto como texto por omissão, escapando automaticamente qualquer conteúdo inserido, e é necessário usar explicitamente um mecanismo especial para inserir marcação em cru — o que o código da Diomika não faz para conteúdo de origem externa. A segunda é a política de conteúdos declarada em `frontend-web/public/_headers`, que só autoriza código da própria origem e do serviço de verificação anti-robô; mesmo que uma injecção conseguisse passar, o código não correria. A terceira é a validação e sanitização do lado do servidor, em `backend-api/core/text_safe.py` e nas declarações de forma dos dados, que rejeita ou limpa conteúdo suspeito antes de ele ser guardado. Três camadas independentes, cada uma suficiente por si, é a resposta proporcionada a uma classe de vulnerabilidade que continua a ser das mais exploradas na web.

---

## Fim da Parte I

Esta parte estabeleceu o vocabulário e os modelos mentais necessários para ler o resto do relatório: o ciclo pedido/resposta, a fronteira de confiança entre cliente e servidor, a tradução de nomes em endereços, o protocolo e os seus métodos e códigos, a encriptação em trânsito e onde termina, o formato de troca de dados, o estilo da interface de programação, o modelo de aplicação de página única, a distribuição geográfica de conteúdos, e as consequências do modelo de negócio entre empresas. O glossário serve de referência permanente e deve ser consultado sempre que um termo parecer opaco nas partes seguintes.

Três ideias transversais atravessaram toda esta parte e vale a pena fixá-las, porque são o fio condutor de tudo o que vem depois:

1. **O cliente nunca é de confiança.** Toda a validação que importa acontece no servidor; nenhum segredo com poder real vive no cliente; nenhuma regra é aplicada apenas onde o utilizador pode alterá-la.
2. **Negar por omissão, permitir por excepção declarada.** Listas fechadas em vez de listas de proibições, em todos os pontos onde a enumeração do legítimo é viável: origens autorizadas, nomes de servidor aceitos, destinos externos contactáveis, tipos de recurso carregáveis.
3. **Defesa em profundidade.** Protecções duplicadas em camadas independentes — na fronteira da rede e na aplicação, na base de dados e no código — porque duas protecções independentes falham em conjunto muito menos vezes do que uma falha sozinha.

As partes seguintes aplicam este vocabulário à arquitectura concreta: a topologia de runtime e o caminho exacto de cada pedido, os fluxos de dados e as sagas, o modelo de autenticação e autorização em detalhe, a camada de observabilidade, o processo de publicação e as operações, e as limitações honestas do sistema tal como ele está hoje.

