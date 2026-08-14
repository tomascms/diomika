# Diomika — Relatório técnico, Partes II a IV

**Ficheiro:** `deploy/relatorio_parts/part_02_arquitectura.md`
**Conteúdo:** Parte II (arquitectura do sistema), Parte III (a loja pública), Parte IV (a API).
**Audiência:** pessoa inteligente sem formação em informática. Cada sigla é expandida na primeira aparição *desta parte*, mesmo que já tenha aparecido na Parte I (`part_01_fundamentos.md`) — assim esta parte pode ser lida isoladamente.
**Segurança:** este texto não contém passwords, tokens, chaves nem valores secretos. Todos os segredos vivem apenas no ficheiro `.env` (local e na máquina de produção) e em pastas ignoradas pelo Git. Quando aparece um nome como `API_SECRET_KEY`, é o **nome da variável**, nunca o seu valor.

---

## Convenção de leitura

Ao longo do texto usamos três marcas:

- **Caminho concreto** — sempre que existe um ficheiro real, ele é citado com o caminho completo a partir da raiz do projecto, por exemplo `backend-api/main.py`. Podes abrir e confirmar tudo o que aqui está escrito.
- **Porquê** — parágrafos que explicam a *decisão*, não a mecânica. São os mais importantes para quem herdar o sistema.
- **Erro típico** — armadilhas reais, algumas delas já sofridas neste projecto (ver, por exemplo, a secção IV.5).

---

# Parte II — Arquitectura do sistema Diomika

## II.0 O sistema em cinco frases

1. Um visitante abre `www.diomika.com` e recebe uma **loja** feita de ficheiros estáticos (texto, imagens, código de página) servidos pela rede da Cloudflare.
2. Essa loja, já dentro do navegador (*browser*, o programa com que se navega na internet: Chrome, Safari, Firefox, Edge), vai buscar dados de catálogo — categorias, modelos, produtos.
3. Quando o visitante **escreve** algo (uma mensagem de contacto, um pedido de orçamento), esse conteúdo não vai directamente para a base de dados: vai para a **API** (Application Programming Interface — Interface de Programação de Aplicações; na prática, um servidor que recebe pedidos estruturados e devolve respostas estruturadas).
4. A API não está exposta na internet. Vive numa **máquina virtual** minúscula na Google Cloud e só é alcançável através de um **túnel** que a própria máquina abre para fora.
5. Os dados persistentes (tabelas, imagens) vivem no **Supabase**, um serviço gerido que corre PostgreSQL (uma base de dados relacional profissional, gratuita e de código aberto).

Tudo o resto neste capítulo é o detalhe dessas cinco frases.

---

## II.1 Diagrama narrado do tráfego

Vamos seguir **um único clique** desde o dedo do visitante até ao disco onde os dados repousam, e depois de volta. Em cada salto (*hop*) indicamos: que máquina, que software, que protocolo, o que está cifrado e o que não está.

### Vista de conjunto

```
[1] Telemóvel/PC do visitante
      │  browser (Chrome/Safari/…)
      │  HTTPS (cifrado)
      ▼
[2] Rede Cloudflare (centro de dados mais próximo — "edge")
      │  ├── Cloudflare Pages: serve dist/ (HTML, CSS, JS, imagens)
      │  └── Pages Function: frontend-web/functions/_middleware.js
      │
      ├──────────────► [3a] Supabase (https://<projecto>.supabase.co)
      │                      leitura de catálogo, chave anónima + RLS
      │
      │  HTTPS para api.diomika.com (cifrado)
      ▼
[3b] Rede Cloudflare (edge) → interior do túnel
      │  ligação estabelecida DE DENTRO da VM para fora (cifrada)
      ▼
[4] VM GCP e2-micro, Ubuntu 22.04 (us-central1)
      │  processo: cloudflared (container, rede do host)
      │  HTTP simples para http://127.0.0.1:8000  ← nunca sai da máquina
      ▼
[5] Docker: porta publicada 127.0.0.1:8000 → container "api"
      │  uvicorn (servidor) → ASGI → FastAPI (backend-api/main.py)
      │  middlewares → routers → função Python
      ├──────────────► [6] Redis (container "redis", rede interna Docker)
      └──────────────► [7] Supabase (HTTPS, chave de serviço) / PostgreSQL (TLS)
```

Agora salto por salto.

### Salto 1 — do dedo ao pedido: o navegador

**Máquina:** o telemóvel ou computador do visitante.
**Software:** um navegador.

O visitante escreve `www.diomika.com`. Antes de existir qualquer pedido de página, o navegador precisa de traduzir esse nome num endereço numérico. Essa tradução chama-se **DNS** (Domain Name System — Sistema de Nomes de Domínio), a lista telefónica da internet: transforma `www.diomika.com` num **IP** (Internet Protocol address — endereço de Protocolo de Internet), algo como `104.x.x.x`.

O DNS do domínio `diomika.com` é servido pela Cloudflare. A resposta que o navegador recebe **não é** o endereço da nossa máquina virtual: é um endereço da rede Cloudflare. Isto é deliberado e voltaremos a ele em II.3.

**Cifrado?** A consulta DNS pode ou não ser cifrada, dependendo do navegador e da rede (muitos usam hoje DNS sobre HTTPS). O nome do site é, em geral, o dado menos secreto de toda a cadeia.

### Salto 2 — o aperto de mão TLS e a entrega da loja

**Máquina:** um servidor da Cloudflare no centro de dados mais próximo do visitante (a Cloudflare usa *anycast*: o mesmo endereço IP existe em centenas de cidades e a rede entrega ao mais próximo).
**Software:** o proxy da Cloudflare + Cloudflare **Pages** (o serviço de alojamento de sites estáticos).
**Protocolo:** **HTTPS** (HyperText Transfer Protocol Secure — Protocolo de Transferência de Hipertexto Seguro), que é HTTP dentro de **TLS** (Transport Layer Security — Segurança da Camada de Transporte, o sucessor do antigo SSL).

Antes de qualquer conteúdo circular, navegador e servidor fazem um *handshake* TLS: o servidor apresenta um **certificado** que prova que é mesmo `www.diomika.com`, os dois negociam chaves de sessão e a partir daí tudo o que passa está cifrado. O visitante vê o cadeado.

O que a Cloudflare devolve são os ficheiros produzidos pelo *build* da loja, isto é, o conteúdo da pasta `frontend-web/dist/`. Ficheiros reais, hoje, nesse directório:

| Ficheiro | Papel |
|---|---|
| `frontend-web/dist/index.html` | A única página HTML. Contém `<div id="app">` e as tags que carregam o resto. |
| `frontend-web/dist/assets/index-D846eMr6.js` | O código da aplicação (JavaScript), minificado. |
| `frontend-web/dist/assets/index-BSd52LHk.css` | Os estilos. |
| `frontend-web/dist/assets/ProductDetailView-szP-m2_w.js` | Um pedaço carregado só quando alguém abre a página de um produto. |
| `frontend-web/dist/_headers` | Instruções de cabeçalhos para a Cloudflare (ver III.7). |
| `frontend-web/dist/robots.txt` | Instruções para motores de busca. |

Antes de servir, a Cloudflare executa uma pequena função nossa no *edge*: `frontend-web/functions/_middleware.js`. É código JavaScript que corre **na rede da Cloudflare**, não no navegador nem na nossa máquina, e cuja única função é responder `404 Not Found` a pedidos de caminhos como `/.env` ou `/src/...` (detalhe em III.6).

**Cifrado?** Sim, integralmente entre navegador e Cloudflare. **O que não está cifrado:** nada neste salto; mas note-se que o *conteúdo* servido é público por natureza — qualquer pessoa pode descarregar e ler `index-D846eMr6.js`. Isto tem uma consequência enorme, tratada em III.8: **tudo o que entra no pacote da loja é público**.

### Salto 3a — o navegador fala directamente com o Supabase

Depois de a página arrancar, o código Vue decide o que mostrar. Para **ler catálogo**, o navegador contacta directamente o Supabase, em `https://<projecto>.supabase.co`, usando a biblioteca oficial (`@supabase/supabase-js`) configurada em `frontend-web/src/lib/supabase.js`.

**Máquina:** infra-estrutura do Supabase (que por baixo corre em AWS).
**Software:** PostgREST — uma camada que expõe tabelas PostgreSQL como *endpoints* HTTP — mais o PostgreSQL propriamente dito.
**Protocolo:** HTTPS.
**Credencial:** a chave **anónima** (`VITE_SUPABASE_ANON_KEY`), que é pública por desenho.

Se isto soa alarmante — "o navegador tem uma chave da base de dados?" — a resposta está em duas palavras: **RLS** (Row Level Security — Segurança ao Nível da Linha). É um mecanismo do PostgreSQL que decide, linha a linha, o que cada identidade pode ver. A chave anónima só consegue ler o que as políticas RLS permitirem, e as consultas do ficheiro `frontend-web/src/lib/catalogSupabase.js` filtram sempre por `visibilidade = true`. Não existe nenhuma escrita por esta via.

**Cifrado?** Sim (HTTPS). **Exposto?** A chave anónima sim, e isso é aceitável — desde que as políticas RLS estejam corretas. A segurança não está no segredo da chave; está nas políticas. A Parte V trata isto em profundidade.

### Salto 3b — o navegador fala com a nossa API

Para **escrever** (formulário de contacto, pedido de orçamento) e para algumas leituras de reserva, o navegador contacta `https://api.diomika.com`. O endereço base está em `frontend-web/src/lib/api.js`, lido da variável `VITE_API_BASE_URL`.

O DNS de `api.diomika.com` aponta, também, para a Cloudflare — concretamente para um registo que representa um **túnel** (na prática um nome do tipo `<identificador>.cfargotunnel.com`). Do ponto de vista do navegador nada disto se nota: ele faz um pedido HTTPS normal, com certificado válido, para `api.diomika.com`.

O pedido leva consigo cabeçalhos que o nosso próprio código gerou:

```javascript
// frontend-web/src/lib/api.js
h['Content-Type'] = 'application/json'
h['X-Request-Id'] = crypto.randomUUID()
```

O `X-Request-Id` é um identificador único por pedido. Serve para, mais tarde, cruzar "o cliente viu este erro" com "esta linha do registo do servidor". Aparece nas mensagens de erro apresentadas ao utilizador de forma abreviada (`(ref: 3f2a1b9c)`).

**Cifrado?** Sim, do navegador até ao *edge* da Cloudflare.

### Salto 4 — do edge da Cloudflare para dentro da máquina virtual

Aqui está a parte contra-intuitiva e a peça central da arquitectura.

A nossa máquina virtual **não tem nenhuma porta aberta para a internet**. Não existe ninguém a ouvir do lado de fora. Então como é que o pedido entra?

Dentro da máquina corre um programa chamado **cloudflared** (o cliente do Cloudflare Tunnel, antigamente "Argo Tunnel"). Quando arranca, o cloudflared **liga-se para fora**, à rede Cloudflare, e mantém essa ligação aberta. Autentica-se com um token de túnel (a variável `CLOUDFLARE_TUNNEL_TOKEN`, cujo valor não aparece em nenhum documento). A partir desse momento existe um canal permanente, cifrado, iniciado de dentro para fora.

Quando o *edge* recebe um pedido para `api.diomika.com`, não abre uma ligação nova para a nossa máquina — **reutiliza o canal que a máquina já abriu**, e envia o pedido por lá.

**Máquina:** a VM `diomika-api`, criada por `deploy/create_gcp_vm.py`.
**Software:** container `cloudflare/cloudflared:2024.12.2`, definido em `deploy/docker-compose.free.yml`.
**Protocolo:** ligação cifrada iniciada pelo cloudflared (tipicamente QUIC sobre UDP, com HTTP/2 sobre TCP como alternativa).
**Cifrado?** Sim, ponta a ponta neste segmento, com autenticação mútua garantida pelo token.

Uma analogia útil: em vez de instalares uma porta na tua casa com uma fechadura (que qualquer pessoa pode tentar arrombar), tu ligas o telefone à central e ficas em linha. Quem quiser falar contigo fala pela central, na chamada que tu iniciaste. Não há porta. Não há fechadura para arrombar.

### Salto 5 — do cloudflared para a API: o interior da máquina

O cloudflared recebe o pedido e tem de o entregar à aplicação. A configuração do túnel diz-lhe que a **origem** (*origin*) do serviço é `http://127.0.0.1:8000`. Trataremos isto em detalhe em II.7.

Repare-se: **`http://`, não `https://`**. Neste único salto o tráfego circula em HTTP simples, sem cifra. Isto é seguro por uma razão precisa: `127.0.0.1` é o endereço de *loopback*, que nunca sai da máquina (II.6). O pacote nasce e morre dentro do mesmo sistema operativo, passando pelo núcleo (*kernel*) e não por nenhum cabo de rede.

Do outro lado dessa porta 8000 está o Docker. Em `deploy/docker-compose.free.yml`:

```yaml
api:
  ports:
    - "127.0.0.1:8000:8000"
```

Isto lê-se como: "publica a porta 8000 do container, mas **apenas** no endereço `127.0.0.1` da máquina anfitriã". O Docker encaminha o que chega a `127.0.0.1:8000` (anfitriã) para a porta 8000 dentro do container.

**Detalhe importante e frequentemente mal compreendido:** neste encaminhamento, o endereço de origem que a aplicação *vê* não é `127.0.0.1`, mas um endereço da rede interna do Docker (tipicamente algo em `172.16.0.0/12`, a *gateway* da ponte Docker). Esta é a razão pela qual `deploy/env.free.example` inclui:

```
TRUSTED_PROXY_IPS=127.0.0.1,::1,172.16.0.0/12
```

E é também a razão pela qual o acesso administrativo **não** passa a estar aberto só porque o tráfego vem "de dentro": a função `peer_is_loopback()` em `backend-api/core/local_only.py` inspecciona o endereço TCP real do interlocutor, e tráfego que venha pelo túnel não é loopback verdadeiro. Quem quiser administrar tem de estar realmente na máquina (por SSH) ou apresentar o cabeçalho da aplicação de secretária. Ver Parte V.

### Salto 6 — dentro do container: uvicorn, ASGI, FastAPI

**Software:** `uvicorn` a servir a aplicação definida em `backend-api/main.py`. O comando está no `Dockerfile`:

```dockerfile
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000} --workers ${UVICORN_WORKERS:-4}"]
```

O `--host 0.0.0.0` significa "ouve em todas as interfaces" — mas **dentro do container**, que é um universo fechado. A fronteira real foi imposta uma camada acima, pelo `127.0.0.1:8000:8000`. É uma boa ilustração de defesa em camadas: cada camada assume que a de cima pode falhar.

O pedido atravessa então, por esta ordem, a pilha de middlewares (IV.4), chega ao *router* certo (IV.3) e finalmente à função Python que faz o trabalho.

### Salto 7 — a API fala com o mundo exterior

A função Python precisa, quase sempre, de dois vizinhos:

**Redis** (container `redis`, `redis:7-alpine`). Usado para contagem de pedidos por IP (limitação de ritmo) e para sessões partilhadas entre processos. A ligação é `redis://redis:6379/0` — o nome `redis` é resolvido pela rede interna do Docker. **Cifrado?** Não. É tráfego dentro da rede virtual interna da máquina, entre dois containers, e nunca atravessa a internet; a porta está publicada apenas em `127.0.0.1:6379`.

**Supabase.** Duas vias:

1. A biblioteca oficial, por HTTPS, com a chave de serviço (`SUPABASE_KEY`) — poderosa, ignora RLS, e por isso vive **exclusivamente** no `.env` da máquina. Nunca no navegador.
2. Ligação directa a PostgreSQL com `psycopg2`, usada por exemplo pelo diagnóstico em `backend-api/core/health.py`, que força cifra:

```python
if "sslmode=" not in url:
    url += ("&" if "?" in url else "?") + "sslmode=require"
```

**Cifrado?** Sim em ambas.

### A viagem de volta

A resposta faz o caminho inverso, e cada camada acrescenta algo:

1. A função devolve um dicionário Python; o FastAPI converte-o em **JSON** (JavaScript Object Notation — um formato de texto para dados estruturados).
2. `BodySizeLimitMiddleware`, `LatencyAlertMiddleware` (mede o tempo total e alerta se passar do limiar), `CatalogCacheHeadersMiddleware` (acrescenta `Cache-Control` a leituras públicas), `SecurityHeadersMiddleware` (acrescenta os cabeçalhos de segurança), `RequestIdMiddleware` (devolve o `X-Request-Id`).
3. O uvicorn escreve a resposta HTTP.
4. O cloudflared reenvia pelo túnel.
5. O *edge* da Cloudflare cifra para o navegador e, se houver `Cache-Control` favorável, pode guardar uma cópia para servir o próximo visitante sem incomodar a nossa máquina.
6. O navegador recebe, o Vue actualiza o ecrã.

### Resumo: o que está cifrado e o que não está

| Segmento | Protocolo | Cifrado | Porquê é aceitável |
|---|---|---|---|
| Navegador → Cloudflare | HTTPS/TLS | Sim | Certificado gerido pela Cloudflare |
| Navegador → Supabase | HTTPS/TLS | Sim | Chave anónima + RLS |
| Cloudflare → cloudflared (túnel) | QUIC/HTTP2 cifrado | Sim | Ligação iniciada de dentro, autenticada por token |
| cloudflared → uvicorn | HTTP simples | **Não** | Só *loopback*; o pacote nunca sai da máquina |
| API → Redis | protocolo Redis | **Não** | Rede interna Docker; porta só em `127.0.0.1` |
| API → Supabase | HTTPS / PostgreSQL+TLS | Sim | `sslmode=require`, CA via `certifi` |
| Administrador → VM | SSH | Sim | Chave `id_ed25519`, sem password |

---

## II.2 Porquê separar a loja (Pages) da API (VM)

Seria possível ter tudo numa máquina: um servidor a entregar as páginas e, ao lado, a aplicação. Muitos projectos fazem isso. Aqui separou-se deliberadamente. Sete razões, por ordem de importância.

**1. Natureza diferente do trabalho.** A loja é **estática**: os mesmos ficheiros para todos, sem cálculo, sem estado. A API é **dinâmica**: valida, decide, escreve, envia email. Servir ficheiros iguais a milhares de pessoas é um problema resolvido de forma perfeita por uma rede de distribuição de conteúdos — **CDN** (Content Delivery Network — Rede de Distribuição de Conteúdos), que coloca cópias em centenas de cidades. Uma máquina única em Iowa nunca competiria com isso para um visitante em Lisboa.

**2. Raio de explosão.** Se a API cair (erro de código, falta de memória, actualização mal feita), a loja **continua no ar**. O catálogo continua a ser lido directamente do Supabase. O visitante navega, vê produtos, e apenas o formulário de contacto falha, com mensagem clara. O inverso também vale: um pico de tráfego na loja não consome os recursos escassos da máquina.

**3. Onde vivem os segredos.** Esta é a razão de segurança. A loja é código público: qualquer pessoa lê o JavaScript. Portanto na loja só podem existir credenciais desenhadas para serem públicas — a chave anónima do Supabase, a chave pública do Turnstile, o endereço da API. Os segredos verdadeiros — chave de serviço do Supabase, password de correio, segredo do Turnstile, `API_SECRET_KEY` — vivem apenas no `.env` da máquina virtual, nunca compilados em nada. A separação física torna esta regra fácil de verificar; existe até um verificador automático, `deploy/verify_bundle_secrets.py`.

**4. Ritmos de publicação diferentes.** Mudar um texto na página "Sobre" não deve exigir reiniciar a API. Corrigir uma regra de negócio na API não deve obrigar a reconstruir a loja. Cada lado tem o seu ciclo: a loja publica-se com `deploy/deploy_beta.py --pages-deploy`; a API com `deploy/deploy_vm.py`.

**5. Custo.** A Cloudflare Pages tem um plano gratuito generoso para sites estáticos. A máquina e2-micro Always Free é gratuita. O único custo do projecto é o domínio. Se a loja estivesse na máquina, a máquina teria de aguentar todo o tráfego de imagens e ficheiros, e 1 GB de memória não dá para muito.

**6. Fronteira explícita.** Porque são origens diferentes, o navegador impõe **CORS** (Cross-Origin Resource Sharing — Partilha de Recursos entre Origens): a API tem de declarar explicitamente quem pode falar com ela. Isso está em `backend-api/main.py`, com a lista vinda de `CORS_ORIGINS`. Em produção, `backend-api/core/config.py` até **recusa arrancar** se essa lista contiver `localhost`. Uma fronteira que o próprio navegador vigia é uma fronteira que não esquecemos de configurar.

**7. Simplicidade operacional.** Não há servidor web para configurar na máquina, não há certificados TLS para renovar, não há `nginx` para afinar. A Cloudflare faz tudo isso. Menos peças, menos coisas para correr mal às três da manhã.

**Custo desta escolha** (sejamos honestos): há duas plataformas para conhecer em vez de uma; a configuração de CORS é uma fonte real de confusão para quem chega; e existem dois caminhos de leitura de catálogo (directo ao Supabase, ou pela API), o que duplica lógica — ver `frontend-web/src/lib/catalogSupabase.js` e `backend-api/routes/catalog_generic.py`. A duplicação é intencional (redundância), mas é uma dívida a vigiar.

---

## II.3 Porquê Cloudflare Tunnel em vez de abrir a porta 8000 na internet

A alternativa óbvia seria: abrir a porta 8000 (ou 443) na *firewall* da Google Cloud, apontar `api.diomika.com` ao endereço IP da máquina, instalar um certificado, pronto. Milhões de servidores no mundo funcionam assim. Porque não aqui?

**Uma porta aberta é uma superfície de ataque permanente.** No momento em que um endereço IP público passa a aceitar ligações, começa a receber tentativas automáticas. Não é uma figura de estilo: existem projectos que varrem continuamente todo o espaço de endereços IPv4 e publicam o que encontram. Um servidor novo recebe tentativas de intrusão em minutos. Cada uma dessas tentativas consome recursos de uma máquina com 1 GB de memória.

Com o túnel, um varrimento de portas à nossa máquina encontra **apenas SSH** (Secure Shell — o canal cifrado de administração, protegido por chave criptográfica, sem password). A aplicação simplesmente não está lá para ser encontrada.

**O endereço IP não é publicado.** O DNS de `api.diomika.com` aponta para a Cloudflare. Um atacante que queira contornar as protecções e bater directamente à porta da origem precisa primeiro de descobrir *onde* é a origem — e essa informação não está no DNS. Não é impossível de descobrir, mas deixa de ser trivial.

**Tudo passa obrigatoriamente pelas defesas.** Como não existe caminho alternativo, o **WAF** (Web Application Firewall — Firewall de Aplicação Web) da Cloudflare, a mitigação de ataques de negação de serviço distribuída, e as regras de `deploy/cloudflare/waf_rules.json` estão sempre no caminho. Numa porta aberta, quem soubesse o IP contornava tudo.

**Certificados deixam de ser um problema.** A cifra termina no *edge* da Cloudflare, que gere e renova o certificado. Nunca há um certificado a expirar na nossa máquina às duas da manhã de um domingo.

**Só ligações de saída.** Muitas redes e provedores restringem ligações de entrada, ou mudam o endereço IP atribuído. O cloudflared só precisa de conseguir sair. Se o IP da máquina mudar, ou se ela for recriada, o túnel volta a ligar-se e o domínio continua a funcionar — sem tocar no DNS.

**A porta 8000 fica genuinamente fechada.** Note-se que aqui há duas fechaduras independentes: (a) a *firewall* da Google não tem regra de entrada para 8000; (b) mesmo que tivesse, o Docker publicou a porta só em `127.0.0.1`, pelo que não existe nada a ouvir na interface de rede externa. Uma configuração errada numa não abre a outra.

**O preço a pagar.** Dependemos da Cloudflare como intermediário obrigatório: se a Cloudflare tiver uma avaria, a API fica inacessível mesmo estando viva. O token do túnel é um segredo crítico — quem o tiver pode reencaminhar tráfego. O cloudflared é uma peça extra que tem de estar viva; se morrer, a API "desaparece" da internet ainda que esteja perfeitamente funcional (razão pela qual `restart: unless-stopped` está definido). E a versão está fixada (`2024.12.2`) para evitar surpresas de actualização automática, o que significa que alguém tem de a actualizar deliberadamente de tempo a tempo.

---

## II.4 Porquê GCP e2-micro Always Free (e o que é uma máquina virtual)

### O que é uma máquina virtual

Um computador físico num centro de dados tem, por exemplo, 64 núcleos de processamento e 512 GB de memória. Seria absurdo dedicá-lo inteiro a uma aplicação pequena. Então corre-se nele um **hipervisor**: um programa que divide o computador físico em vários computadores *simulados*, cada um com a ilusão de ter o seu processador, a sua memória, o seu disco e o seu sistema operativo.

Cada um desses computadores simulados é uma **VM** (Virtual Machine — Máquina Virtual). De dentro, é indistinguível de uma máquina real: arranca, tem nome, tem endereço IP, instala-se software, liga-se por SSH. A diferença é que o "hardware" é uma abstracção, e o vizinho na mesma máquina física não te pode ver.

**GCP** significa Google Cloud Platform — Plataforma de Nuvem da Google, o serviço onde alugamos (neste caso, não pagamos) essa máquina virtual.

### O que é exactamente a nossa máquina

Criada por `deploy/create_gcp_vm.py`, com estes parâmetros literais:

```python
"--machine-type=e2-micro",
"--image-family=ubuntu-2204-lts",
"--image-project=ubuntu-os-cloud",
"--boot-disk-size=30GB",
"--boot-disk-type=pd-standard",
"--tags=diomika-api",
```

- **`e2-micro`** — o tamanho. Aproximadamente 1 GB de memória e capacidade de processamento partilhada, com possibilidade de "picos" curtos acima da quota base. É pouco. É de propósito.
- **`ubuntu-2204-lts`** — Ubuntu 22.04, versão **LTS** (Long Term Support — Suporte de Longo Prazo), com actualizações de segurança durante anos. Estabilidade acima de novidade.
- **`30GB` `pd-standard`** — disco de 30 gigabytes, do tipo mais barato (disco magnético em rede). Suficiente: as imagens e os dados não estão aqui, estão no Supabase.
- **`--zona us-central1-a`** (por omissão no script) — não é uma escolha estética. O programa "Always Free" da Google só se aplica a certas regiões dos Estados Unidos.
- **Acesso** — apenas por chave SSH pública (`~/.ssh/id_ed25519.pub`), enviada na criação. Sem passwords.

O script guarda o endereço obtido no `.env` local como `REMOTE_VM_SSH`, para que `deploy/deploy_vm.py` saiba onde publicar. E imprime um aviso que vale a pena repetir aqui: **não clicar em "Activate"** na consola da Google, porque isso converte a conta em conta paga e o "Always Free" deixa de ser o modo por omissão.

### O que "Always Free" significa e as consequências no desenho

"Always Free" é uma quota permanente (não um período de avaliação): uma instância e2-micro numa região elegível, dentro de limites de tráfego de saída. Zero euros por mês, indefinidamente.

**Porquê.** O objectivo declarado do projecto é custo total de zero excepto o domínio (`deploy/FREE_STACK.md`). Isto tem valor humano, não só financeiro: um sistema que não gera factura mensal não morre porque alguém se esqueceu de renovar um cartão de crédito.

Mas a escassez molda todo o desenho, e vale a pena tornar explícita essa cadeia de consequências:

| Restrição | Consequência no código |
|---|---|
| ~1 GB de memória | Redis configurado sem persistência (`--save "" --appendonly no`): serve de contador volátil, não de base de dados. |
| Um só processo confortável | Os trabalhadores de fundo correm **dentro** da API, em *threads*, e não em containers separados: `RUN_EMBEDDED_WORKERS: "true"` (ver IV.7). |
| Processamento partilhado | Respostas de catálogo são guardadas em memória com tempo de vida (`CATALOG_CACHE_TTL=60`) e recebem `Cache-Control`, para a Cloudflare responder sem incomodar a máquina. |
| Tráfego de saída contabilizado | As imagens são servidas pelo Supabase Storage ou pela Cloudflare R2, nunca pela máquina. |
| Uma única máquina, uma única região | Latência maior para a Europa nas escritas — aceitável, porque as escritas são raras (formulários), e as leituras vêm do *edge*. |

**Quando isto deixa de servir.** O documento `deploy/SCALE.md` existe precisamente para esse dia. Os sinais: alertas frequentes de latência (`ALERT_LATENCY_MS`), `429 Demasiados pedidos` legítimos, memória esgotada. O caminho de saída está preparado — mais processos `uvicorn`, trabalhadores em containers próprios, uma máquina maior — e nenhuma dessas mudanças exige reescrever a aplicação.

---

## II.5 Docker e `deploy/docker-compose.free.yml`

### O que é um contentor

Instalar software numa máquina é uma fonte inesgotável de problemas: a versão do Python é diferente, falta uma biblioteca do sistema, uma actualização parte outra coisa. A frase clássica é "no meu computador funciona".

Um **contentor** (*container*) resolve isto empacotando a aplicação **com** tudo aquilo de que depende: o interpretador, as bibliotecas, os ficheiros do sistema. O que se obtém é um pacote que corre igual em qualquer máquina Linux.

Distinção essencial:

- **Imagem** — o molde, imutável, construído a partir de uma receita (o `Dockerfile`). Como um DVD.
- **Contentor** — uma execução dessa imagem. Como o filme a passar. Pode-se parar, apagar e recriar sem afectar a imagem.

Um contentor **não** é uma máquina virtual: partilha o núcleo do sistema operativo da máquina anfitriã, e por isso arranca em segundo e consome muito menos memória. Ganha isolamento de ficheiros, de processos e de rede, mas não isolamento de *hardware*.

### A receita: `Dockerfile`

```dockerfile
FROM python:3.12-slim
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    curl \
    && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY backend-api/ ./backend-api/
ENV PYTHONPATH=/app/backend-api
ENV UVICORN_WORKERS=4
WORKDIR /app/backend-api
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000} --workers ${UVICORN_WORKERS:-4}"]
```

Linha a linha, e porque cada linha está nessa posição:

- `python:3.12-slim` — base oficial, variante reduzida (sem ferramentas de compilação nem documentação). Menos software instalado significa menos vulnerabilidades possíveis e imagem mais pequena, o que importa quando o disco e a rede são modestos.
- `libpq5` é a biblioteca cliente do PostgreSQL, necessária ao `psycopg2`. `curl` existe por uma razão muito concreta: é a ferramenta usada pela verificação de saúde do contentor.
- `--no-install-recommends` e `rm -rf /var/lib/apt/lists/*` — instalar o mínimo e apagar os índices de pacotes. Sem isto, a imagem carrega dezenas de megabytes inúteis para sempre.
- Copiar **primeiro** `requirements.txt` e só depois o código é uma optimização deliberada. O Docker guarda em cache cada passo; como as dependências mudam raramente e o código muda a toda a hora, esta ordem evita reinstalar tudo a cada alteração de uma linha de Python. Numa máquina lenta, é a diferença entre uma publicação de vinte segundos e uma de cinco minutos.
- `PYTHONPATH=/app/backend-api` — diz ao Python onde procurar os módulos, o que permite escrever `from core.config import get_settings` em vez de caminhos relativos frágeis.
- O `CMD` usa `${PORT:-8000}` e `${UVICORN_WORKERS:-4}`: valores com omissão sensata, sobreponíveis por ambiente.

### A orquestração: `deploy/docker-compose.free.yml`

Um `Dockerfile` descreve *uma* imagem. Um ficheiro **compose** descreve um *conjunto* de serviços, as suas ligações e a ordem de arranque. Um único comando levanta tudo:

```bash
docker compose -f deploy/docker-compose.free.yml --profile tunnel up -d --build
```

#### Serviço `redis`

```yaml
redis:
  image: redis:7-alpine
  restart: unless-stopped
  command: ["redis-server", "--save", "", "--appendonly", "no"]
  ports:
    - "127.0.0.1:6379:6379"
  healthcheck:
    test: ["CMD", "redis-cli", "ping"]
```

O Redis é um armazém de dados em memória, extremamente rápido. Aqui tem dois papéis: contar pedidos por endereço IP (limitação de ritmo) e guardar sessões de administração de forma partilhada entre processos.

`--save "" --appendonly no` desliga as duas formas de persistência em disco. **Porquê:** os dados são intrinsecamente descartáveis (um contador de pedidos do último minuto), e escrever em disco custa memória (o mecanismo de gravação duplica temporariamente páginas) e desgasta o disco. Se o Redis reiniciar, perdem-se contadores e sessões — os utilizadores voltam a autenticar-se, e é tudo. Consequência assumida.

`127.0.0.1:6379` — nunca acessível de fora. Um Redis exposto na internet sem password é uma das formas mais rápidas conhecidas de perder um servidor.

`healthcheck` com `redis-cli ping` — o Docker pergunta periodicamente "estás vivo?" e marca o serviço como saudável só quando responde. Isto alimenta a ordem de arranque abaixo.

#### Serviço `api`

```yaml
api:
  build:
    context: ..
    dockerfile: Dockerfile
  restart: unless-stopped
  ports:
    - "127.0.0.1:8000:8000"
  env_file:
    - ../.env
  environment:
    DIOMIKA_ENV: production
    DIOMIKA_DOMAIN: diomika.com
    RUN_EMBEDDED_WORKERS: "true"
    PYTHONPATH: /app/backend-api
    TRUST_PROXY: "1"
    REDIS_URL: redis://redis:6379/0
    SUPABASE_STORAGE_PRIVATE: "1"
  depends_on:
    redis:
      condition: service_healthy
  healthcheck:
    test: ["CMD", "curl", "-f", "http://127.0.0.1:8000/health"]
    interval: 30s
    timeout: 10s
    retries: 3
    start_period: 40s
```

- `context: ..` — o contexto de construção é a raiz do projecto (o ficheiro compose está em `deploy/`), porque o `Dockerfile` precisa de `requirements.txt` e de `backend-api/`.
- `env_file: ../.env` — **aqui é que os segredos entram**, lidos do ficheiro `.env` da raiz na máquina. Esse ficheiro não está no repositório e nunca deve estar.
- O bloco `environment` sobrepõe-se ao `env_file` e fixa aquilo que não deve depender de distracção humana: ambiente de produção, trabalhadores embutidos, endereço do Redis, armazenamento privado. Note-se que `SUPABASE_STORAGE_PRIVATE: "1"` é obrigatório em produção — `backend-api/core/config.py` recusa arrancar sem ele.
- `depends_on: redis: condition: service_healthy` — não basta o Redis *existir*, tem de estar a responder. Sem esta condição, a API arrancaria antes e falharia na primeira tentativa de contar pedidos.
- `restart: unless-stopped` — se o processo morrer, o Docker relança. Se um humano o parou explicitamente, respeita.
- `healthcheck` a chamar `/health` com `start_period: 40s` — os primeiros 40 segundos não contam como falha, porque o arranque inclui verificação de esquema da base de dados. Esta verificação de saúde é o que permite ao serviço seguinte esperar pela API.

#### Serviço `cloudflared`

```yaml
cloudflared:
  image: cloudflare/cloudflared:2024.12.2
  restart: unless-stopped
  profiles: ["tunnel"]
  network_mode: host
  command: tunnel run
  environment:
    TUNNEL_TOKEN: ${CLOUDFLARE_TUNNEL_TOKEN}
  depends_on:
    api:
      condition: service_healthy
```

- `profiles: ["tunnel"]` — este serviço só arranca se se pedir explicitamente `--profile tunnel`. Permite levantar a API sozinha para testes locais na máquina, sem a publicar no mundo.
- `network_mode: host` — o contentor **não** tem rede isolada; usa directamente a pilha de rede da máquina. É esta linha que faz com que, para o cloudflared, `127.0.0.1:8000` signifique o `127.0.0.1` da máquina, onde o Docker publicou a API. Sem ela, `127.0.0.1` seria o próprio contentor do cloudflared e o túnel não encontraria nada — resultando num erro `502 Bad Gateway`. O comentário no ficheiro diz exactamente isto.
- `TUNNEL_TOKEN: ${CLOUDFLARE_TUNNEL_TOKEN}` — o token é lido do ambiente (que vem do `.env`), não escrito no ficheiro. É por isso que o comando de publicação em `deploy/deploy_vm.py` usa `--env-file .env`.
- `depends_on: api: service_healthy` — **a ordem certa e não a inversa**. Nunca se anuncia ao mundo um serviço que ainda não está pronto a responder. Se o túnel abrisse primeiro, os visitantes veriam erros durante a janela de arranque.
- Versão fixada em vez de `latest` — publicações reprodutíveis. A mesma ordem de comandos produz hoje e em Março o mesmo resultado.

---

## II.6 Loopback `127.0.0.1` — o que significa e porque a API só escuta aí

### O conceito

Todo o computador com rede tem uma interface especial, virtual, chamada **loopback**. O seu endereço é `127.0.0.1` na versão 4 do protocolo IP e `::1` na versão 6. O nome `localhost` normalmente aponta para lá.

A propriedade que define o loopback: **um pacote enviado para `127.0.0.1` nunca sai da máquina**. Não desce ao cabo de rede nem ao rádio Wi-Fi. O núcleo do sistema operativo recebe-o e entrega-o imediatamente a um processo local. Fisicamente, é uma cópia de memória.

Uma analogia: escrever um recado e deixá-lo na tua própria secretária, em vez de o pôr no correio. Não há carteiro, não há caixa de correio, não há ninguém a poder interceptá-lo pelo caminho — porque não há caminho.

Consequência directa: **um serviço que só escuta em `127.0.0.1` é inalcançável do exterior**, independentemente de *firewalls*. Não é uma porta trancada; é uma porta que não existe do lado de fora.

### Como isto se aplica à Diomika, em três níveis

**Nível 1 — publicação da porta pelo Docker.** A sintaxe `"127.0.0.1:8000:8000"` tem três partes: *endereço da anfitriã* : *porta na anfitriã* : *porta no contentor*. Se estivesse escrito apenas `"8000:8000"`, o Docker interpretaria como `0.0.0.0:8000`, isto é, todas as interfaces — incluindo a que dá para a internet. Esta única omissão é uma das causas mais comuns de bases de dados e painéis administrativos expostos acidentalmente. Aqui está explícito, e o comentário no ficheiro diz "Só localhost na VM".

**Nível 2 — o desenvolvimento local.** No fim de `backend-api/main.py`:

```python
_port = int(os.getenv("DIOMIKA_API_PORT") or "8001")
uvicorn.run(app, host="127.0.0.1", port=_port)
```

Ao desenvolver no Windows, a API só aceita ligações da própria máquina. Um portátil numa rede Wi-Fi de café não fica a servir uma API de desenvolvimento a estranhos. E o servidor de desenvolvimento do Vite faz o mesmo (`host: "127.0.0.1"` em `frontend-web/vite.config.js`).

**Nível 3 — decisões de autorização.** O loopback é usado como *prova de proximidade física*. Em `backend-api/core/local_only.py`:

```python
def peer_is_loopback(request: Request) -> bool:
    """IP do peer TCP — não usar X-Forwarded-For (fácil de forjar)."""
    if request.client and request.client.host:
        peer = request.client.host.strip().lower()
        return peer in _LOOPBACK or peer.startswith("127.")
    return False
```

O comentário no código é a parte importante. Existe um cabeçalho chamado `X-Forwarded-For` que os intermediários usam para dizer "o cliente original era este IP". **Qualquer pessoa pode escrever o que quiser nesse cabeçalho.** Se a autorização administrativa dependesse dele, bastaria enviar `X-Forwarded-For: 127.0.0.1` para passar por administrador. Por isso, para decisões de autorização, olha-se exclusivamente para o endereço real da ligação TCP, que não se pode falsificar sem controlar o caminho de rede.

O mesmo raciocínio, invertido, aparece na limitação de ritmo (`backend-api/core/rate_limit.py`): aí *queremos* saber o IP real do visitante, que vem no `X-Forwarded-For` posto pela Cloudflare. Mas só se confia nesse cabeçalho quando duas condições se cumprem: `TRUST_PROXY=1` **e** o interlocutor imediato pertencer à lista `TRUSTED_PROXY_IPS`:

```python
def get_client_ip(request: Request) -> str:
    if trust_proxy_headers() and _peer_is_trusted_proxy(request):
        forwarded_for = request.headers.get("x-forwarded-for") or ...
```

Confiar no cabeçalho para *contar*, nunca para *autorizar*: é uma distinção subtil e correcta.

**Nota operacional já referida em II.1:** como o tráfego do túnel atravessa a publicação de porta do Docker, o endereço que a API vê para esse tráfego é o da rede interna do Docker, não `127.0.0.1`. Portanto pedidos vindos do túnel **não** contam como loopback para efeitos administrativos — o que é exactamente o comportamento desejado. Administrar exige estar mesmo na máquina (via SSH), ou usar a aplicação de secretária oficial com o seu cabeçalho de porta (`DIOMIKA_DESKTOP_GATE`).

---

## II.7 A origem do túnel (`http://127.0.0.1:8000`)

### O que "origem" significa aqui

Um túnel Cloudflare é, conceptualmente, uma tabela de encaminhamento com uma única pergunta: *"quando chegar um pedido para o nome público X, a que endereço local o devo entregar?"* Esse endereço local é a **origem** (*origin*).

Para a Diomika, a regra é: `api.diomika.com` → `http://127.0.0.1:8000`.

Três observações sobre esta linha, cada uma com uma razão:

**`http` e não `https`.** Não faria sentido cifrar aqui. Cifrar existe para proteger dados em trânsito num meio hostil; entre `127.0.0.1` e `127.0.0.1` não há trânsito nem meio. Se se usasse `https`, seria necessário gerar e renovar um certificado para uso interno — trabalho e mais uma coisa a expirar, sem qualquer ganho de segurança.

**`127.0.0.1` e não o nome do contentor.** Podia ser `http://api:8000` (o nome do serviço na rede Docker). Optou-se pelo loopback porque o cloudflared corre com `network_mode: host`, ou seja, fora da rede virtual do Docker; para ele, os nomes de serviço Docker não existem, mas o `127.0.0.1` da máquina — onde a porta está publicada — existe. A escolha e a linha `network_mode: host` são interdependentes: mudar uma sem a outra parte o sistema.

**`8000` e não `8001`.** Convenção interna do projecto, documentada no cabeçalho de `backend-api/main.py`: 8001 para desenvolvimento local no Windows, 8000 para Docker e para a máquina de produção. Ter portas diferentes evita conflitos quando se corre a API localmente enquanto se investiga a de produção por um túnel SSH.

### Como a configuração é aplicada

Isto não se faz à mão. `deploy/deploy_vm.py` tem uma função dedicada:

```python
def update_tunnel_origin(env: dict[str, str], origin: str) -> None:
```

Que executa, na prática:

1. Listar os túneis da conta pela API da Cloudflare (`/cfd_tunnel?is_deleted=false`).
2. Encontrar o chamado `diomika-api`; se não existir, aborta com `ERRO: tunnel diomika-api nao encontrado`.
3. Escrever a configuração em `/cfd_tunnel/{id}/configurations`, com a origem passada por argumento — cujo valor por omissão é literalmente `http://127.0.0.1:8000`:

```python
parser.add_argument("--update-tunnel-origin", default="http://127.0.0.1:8000")
parser.add_argument("--skip-tunnel-update", action="store_true")
```

E logo depois, na máquina:

```
sudo docker compose --env-file .env -f deploy/docker-compose.free.yml --profile tunnel up -d --build;
sleep 8; curl -sf http://127.0.0.1:8000/health; echo
```

**Porquê este `curl` no fim.** Uma publicação que "não deu erro" não é uma publicação que funciona. O `curl -sf` ao endereço de saúde falha com código de erro se a API não responder, e o *script* reporta `ERRO compose na VM`. É a diferença entre "o comando correu" e "o sistema está bom".

### O que falha quando a origem está errada

Vale a pena saber diagnosticar, porque os sintomas são enganadores:

| Sintoma | Causa provável |
|---|---|
| `502 Bad Gateway` em `api.diomika.com`, mas `curl http://127.0.0.1:8000/health` funciona na máquina | A origem do túnel não corresponde: falta `network_mode: host`, ou a porta configurada está errada. |
| O domínio não resolve | Falta o registo DNS a apontar para o túnel, ou o túnel não tem o nome público associado. |
| `403` em `/admin/...` a partir do exterior | Não é avaria: é `PrivilegedPathMiddleware` e `admin_must_be_local` a funcionarem (Parte V). |
| `530` ou erro de túnel | O contentor `cloudflared` não está a correr, ou o token é inválido. |
| Funciona uns minutos e cai | Ordem de arranque errada, ou a API a ser reiniciada por falta de memória. |

---

## II.8 A alternativa `docker-compose.yml` na raiz (VPS tudo-em-um)

Existe no repositório um segundo ficheiro compose, na raiz: `docker-compose.yml`. Não é lixo nem duplicação acidental — é um caminho alternativo, deliberadamente guardado, e o seu próprio cabeçalho o diz:

```yaml
# Opção avançada: tudo num VPS (Hetzner, DigitalOcean, etc.)
# Uso: docker compose up -d
# Requer ficheiro .env na raiz com todas as variáveis.
```

**VPS** significa Virtual Private Server — Servidor Privado Virtual: essencialmente uma máquina virtual alugada a um provedor, geralmente por 4 a 10 euros por mês, com mais memória e mais processamento do que a e2-micro gratuita.

Diferenças estruturais em relação ao caminho canónico:

| Aspecto | `deploy/docker-compose.free.yml` (canónico) | `docker-compose.yml` (raiz, alternativo) |
|---|---|---|
| Publicação de porta | `127.0.0.1:8000:8000` — só loopback | `8000:8000` — **todas as interfaces** |
| Servidor | `--host 0.0.0.0` dentro do contentor, fronteira imposta acima | `command: uvicorn main:app --host 0.0.0.0 --port 8000` |
| Exposição pública | Cloudflare Tunnel | À responsabilidade de quem opera (proxy inverso, certificados, *firewall*) |
| Redis | Presente, obrigatório | **Ausente** |
| Trabalhadores de fundo | Embutidos na API (`RUN_EMBEDDED_WORKERS: "true"`) | Contentores dedicados: `email-worker` e `outbox-worker` |
| Frontend | Cloudflare Pages | Bloco `nginx` comentado, servindo `frontend-web/dist` |
| Verificação de saúde | `curl -f .../health` | `python -c "import urllib.request; ..."` (não requer `curl`) |
| Custo | Zero | Mensalidade do VPS |

O ponto mais interessante é a forma dos trabalhadores:

```yaml
email-worker:
  build: .
  command: python workers/email_worker.py
outbox-worker:
  build: .
  command: python workers/outbox_worker.py
```

Três contentores a partir da **mesma imagem**, distinguidos apenas pelo comando. Isto é isolamento adequado: se o trabalhador de email ficar preso à espera de um servidor de correio lento, a API não sofre; se o trabalhador falhar, reinicia sozinho sem levar a API consigo. É a forma correcta — e é exactamente a que **não** cabe em 1 GB de memória, porque cada contentor carrega o seu próprio interpretador Python e as suas bibliotecas.

**Quando usar cada um.** Se o objectivo é custo zero e o tráfego é modesto, o caminho gratuito. Se o tráfego cresce, ou se se quiser eliminar a dependência da Cloudflare como intermediário obrigatório, ou se for preciso separar trabalhadores por razões de fiabilidade, então o VPS. Nesse cenário, é obrigatório acrescentar: um proxy inverso com TLS (por exemplo Caddy, que gera certificados automaticamente), uma *firewall* que não deixe a porta 8000 aberta ao mundo, e um Redis — porque `backend-api/core/config.py` recusa arrancar em produção final sem `REDIS_URL`.

**Porque os dois ficheiros coexistem.** Um sistema com apenas um caminho de publicação está preso a esse caminho. Manter a alternativa documentada e sintaticamente válida significa que a migração é uma decisão de uma tarde, não um projecto de reescrita. O ficheiro `deploy/SCALE.md` descreve esse percurso.

---

# Parte III — A loja (`frontend-web`)

## III.1 Vue 3 + Vite: o que são e o ciclo build → `dist/`

### O problema que o Vue resolve

Sem ferramentas, construir uma página interactiva significa manipular o documento à mão: encontrar um elemento, mudar-lhe o texto, acrescentar outro, apagar um terceiro. Com dez elementos é irritante; com um catálogo, um carrinho e um formulário é insustentável, porque o programador passa a ser responsável por manter o ecrã sincronizado com os dados em todos os caminhos possíveis.

O **Vue** inverte essa responsabilidade. Descreve-se *como o ecrã deve ser em função dos dados*, e o Vue encarrega-se de descobrir o que mudar quando os dados mudam. Chama-se **reactividade**. Se `carrinho` ganha um item, tudo o que depende de `carrinho` actualiza-se sozinho.

A unidade de organização é o **componente**: um pedaço de interface autónomo, com a sua marcação, a sua lógica e os seus estilos, num único ficheiro `.vue`. Exemplos reais neste projecto:

- `frontend-web/src/components/QtySelect.vue` — selector de quantidade.
- `frontend-web/src/components/CookieBanner.vue` — a faixa de consentimento (III.5).
- `frontend-web/src/components/Breadcrumbs.vue` — a trilha de navegação.
- `frontend-web/src/components/AppErrorBoundary.vue` — apanha erros de componentes filhos e mostra algo digno em vez de um ecrã branco.
- `frontend-web/src/components/LoadingState.vue` — o estado "a carregar", reutilizado em vez de reinventado em cada página.

O ponto de entrada é curto e vale a pena ler inteiro (`frontend-web/src/main.js`):

```javascript
const app = createApp(App)
app.use(router)
useRouteMeta(router)
app.config.errorHandler = (err) => {
  console.error('[Diomika]', err)
}
app.mount('#app')
```

Criar a aplicação, ligar o encaminhador de rotas, activar a gestão de metadados de página (títulos e descrições, para motores de busca), instalar um tratador global de erros, e "montar" tudo dentro do elemento `#app` do `index.html`.

### O que o Vite faz

**Vite** é a ferramenta de construção. Tem duas caras completamente diferentes.

**Em desenvolvimento**, é um servidor. Arranca em menos de um segundo e serve os ficheiros ao navegador quase sem transformação, aproveitando o facto de os navegadores modernos entenderem módulos JavaScript nativamente. Quando se grava um ficheiro, só esse módulo é substituído no navegador, sem recarregar a página — o estado da aplicação (o carrinho, o formulário meio preenchido) sobrevive. A configuração está em `frontend-web/vite.config.js`:

```javascript
server: {
  host: "127.0.0.1",
  port: 5173,
  strictPort: true,
  proxy: {
    '/api': {
      target: 'http://127.0.0.1:8001',
      changeOrigin: true,
      rewrite: (p) => p.replace(/^\/api/, ''),
    },
  },
},
```

Quatro decisões:

- `host: "127.0.0.1"` — só a própria máquina (ver II.6).
- `strictPort: true` — se a porta 5173 estiver ocupada, **falha** em vez de escolher outra silenciosamente. Evita a confusão de estar a testar na porta errada.
- O `proxy` de `/api` para `http://127.0.0.1:8001` faz com que, em desenvolvimento, o navegador pense que a API está na mesma origem que a loja. Isso elimina completamente os problemas de CORS localmente.
- `rewrite` retira o prefixo `/api`, porque a API não o espera.

Isto liga-se directamente a `frontend-web/src/lib/api.js`:

```javascript
const base = (import.meta.env.DEV ? '/api' : prodBase)
```

Em desenvolvimento, caminho relativo (e o proxy resolve). Em produção, o endereço absoluto de `VITE_API_BASE_URL`.

**Em produção**, o Vite é um compilador. `npm run build` executa `vite build` e produz a pasta `frontend-web/dist/`. O que acontece nesse processo:

1. **Compilação** dos ficheiros `.vue` para JavaScript que o navegador entende.
2. **Empacotamento** de centenas de ficheiros pequenos em poucos ficheiros grandes (menos pedidos de rede).
3. **Divisão em pedaços** (*code splitting*): cada `import()` dinâmico no encaminhador gera um ficheiro separado, carregado apenas quando necessário.
4. **Minificação** com `esbuild`: remover espaços, encurtar nomes de variáveis. `index-D846eMr6.js` é código legível transformado em algo denso e ilegível — mais pequeno e mais rápido a descarregar.
5. **Nomes com impressão digital** (*hash*): `index-D846eMr6.js` inclui um resumo do conteúdo. Se o conteúdo mudar, o nome muda. Isto permite dizer aos navegadores "guarda este ficheiro durante um ano" sem risco de servirem versão antiga — porque a versão nova tem outro nome. É a razão pela qual `/assets/*` pode ter `Cache-Control: public, max-age=31536000, immutable` (III.7).
6. **Substituição de variáveis** — o tema de III.8.
7. **Cópia literal de `public/`** — o que está em `frontend-web/public/` vai para `dist/` sem transformação: é assim que `_headers` e `robots.txt` chegam ao destino.

Duas linhas da configuração de construção merecem nota:

```javascript
build: {
  sourcemap: false,
  minify: 'esbuild',
},
```

`sourcemap: false` desliga os mapas de origem — ficheiros que permitiriam reconstituir o código original a partir do minificado. Úteis para depurar, mas em produção expõem a estrutura interna do projecto a qualquer curioso. Decisão de segurança, não de desempenho.

E uma linha fácil de ignorar mas essencial:

```javascript
envDir: path.resolve(fileURLToPath(new URL('.', import.meta.url)), '..'),
```

Diz ao Vite para procurar o ficheiro `.env` na **raiz do projecto**, um nível acima de `frontend-web/`. Assim existe um único ficheiro de configuração para todo o sistema, em vez de um por pasta.

### O ciclo completo, do teclado ao visitante

```
editar frontend-web/src/views/HomeView.vue
        │
        ▼  npm run dev  →  http://127.0.0.1:5173  (segundos, com recarga instantânea)
        │
        ▼  npm run build  →  frontend-web/dist/  (compilação, minificação, hashes)
        │
        ▼  python deploy/deploy_beta.py --pages-deploy
        │
        ▼  Cloudflare Pages distribui dist/ por centenas de cidades
        │
        ▼  visitante recebe do centro de dados mais próximo
```

---

## III.2 As rotas da loja

A loja é uma **SPA** (Single Page Application — Aplicação de Página Única). O nome é literal: existe um só ficheiro HTML, `index.html`. Quando o visitante "muda de página", nenhum documento novo é pedido ao servidor — o JavaScript troca componentes e reescreve o endereço na barra do navegador usando a **History API** (a interface do navegador que permite manipular o histórico sem recarregar).

O mapa está em `frontend-web/src/router/index.js`:

| Caminho | Nome | Componente | Carregamento |
|---|---|---|---|
| `/` | `home` | `frontend-web/src/views/HomeView.vue` | imediato |
| `/categorias` | `categories` | `frontend-web/src/views/CategoriesView.vue` | diferido |
| `/produtos/:categoryId?` | `products` | `frontend-web/src/views/ProductsView.vue` | imediato |
| `/produto/:id` | `product-detail` | `frontend-web/src/views/ProductDetailView.vue` | diferido |
| `/carrinho` | `cart` | `frontend-web/src/views/CartView.vue` | diferido |
| `/contacto` (alias `/contact`) | `contact` | `frontend-web/src/views/ContactView.vue` | diferido |
| `/sobre` | `about` | `frontend-web/src/views/AboutView.vue` | diferido |
| `/privacidade` | `privacy` | `frontend-web/src/views/PrivacyView.vue` | diferido |
| `/:pathMatch(.*)*` | `not-found` | `frontend-web/src/views/NotFoundView.vue` | diferido |

Detalhes com intenção por trás:

**Imediato vs diferido.** `HomeView` e `ProductsView` são importados no topo do ficheiro, logo entram no pacote principal. Os restantes usam `() => import('@/views/...')`, o que instrui o Vite a criar um ficheiro separado — visível em `dist/assets/CartView-mwY8EAek.js`, `dist/assets/ContactView-CtA35hVz.js`, e assim por diante. **Porquê:** quem chega à loja vai quase certamente à página inicial e ao catálogo; não faz sentido fazê-lo descarregar o código da página de privacidade. Quem visita `/privacidade` paga um pedido extra — e não se importa.

**`:categoryId?`** — o `?` marca parâmetro opcional: `/produtos` e `/produtos/abc-123` resolvem para a mesma vista.

**`alias: ['/contact']`** — o endereço em inglês continua a funcionar, provavelmente porque foi partilhado ou indexado em algum momento. Endereços não devem morrer.

**A rota apanha-tudo.** `/:pathMatch(.*)*` corresponde a qualquer coisa não reconhecida e mostra `NotFoundView`. Isto é obrigatório numa SPA, senão um endereço mal escrito resulta em ecrã branco.

**Comportamento de deslocamento.** Detalhe de qualidade raramente feito bem:

```javascript
scrollBehavior(to, _from, savedPosition) {
  if (to.hash) {
    return { el: to.hash, behavior: 'smooth', top: 80 }
  }
  if (savedPosition) return savedPosition
  return { top: 0 }
}
```

Ao seguir uma ligação com âncora, desliza suavemente até ela deixando 80 pixéis de folga (porque há um cabeçalho fixo que taparia o alvo). Ao usar o botão "voltar", regressa à posição exacta onde o visitante estava. Nos restantes casos, começa no topo. Sem isto, navegar numa SPA dá a sensação estranha de "aterrar a meio da página".

### A consequência da SPA que obriga a III.6

Para que `www.diomika.com/carrinho` funcione quando escrito directamente na barra de endereço, o servidor tem de devolver `index.html` para **qualquer** caminho — o encaminhador só entra em acção depois de o JavaScript arrancar. A Cloudflare Pages faz isso automaticamente para sites de página única.

Efeito colateral desagradável: um pedido a `/.env` também receberia `index.html`, com estado `200 OK`. Para um programa automático de varrimento, `200 OK` em `/.env` parece um achado. Daí a existência de `frontend-web/functions/_middleware.js` (III.6).

---

## III.3 Como o navegador fala com o Supabase e como fala com a API

Há dois canais de dados, com propósitos distintos e uma regra simples: **leituras públicas podem ir directas ao Supabase; escritas vão sempre pela API.**

### Canal A — directo ao Supabase (leitura)

Configurado em `frontend-web/src/lib/supabase.js`:

```javascript
const supabaseUrl = import.meta.env.VITE_SUPABASE_URL || ''
const supabaseAnonKey = import.meta.env.VITE_SUPABASE_ANON_KEY || ''
export const supabaseConfigured = Boolean(supabaseUrl && supabaseAnonKey)
export const supabase = supabaseConfigured ? createClient(supabaseUrl, supabaseAnonKey) : null
```

As consultas estão em `frontend-web/src/lib/catalogSupabase.js`. Exemplo real:

```javascript
const { data, error } = await supabase
  .from('categories')
  .select(CATEGORY_FIELDS)
  .eq('visibilidade', true)
  .order('nome')
```

Traduzido: "da tabela `categories`, dá-me estes campos, apenas onde `visibilidade` é verdadeira, ordenado por nome". Isto viaja como um pedido HTTPS e o PostgREST converte-o em SQL (Structured Query Language — Linguagem de Consulta Estruturada, a linguagem das bases de dados relacionais).

Note-se que `CATEGORY_FIELDS` é uma lista explícita — `id,nome,slug,imagem,tipo_catalogo,carrinho_step,carrinho_min` — e não `*`. Pedir só o necessário significa menos dados a viajar e menos risco de expor um campo interno por descuido. O mesmo cuidado aparece em `modelDetailForTipo`, que remove explicitamente uma bandeira interna antes de entregar ao interface:

```javascript
if (data.categories) {
  const { visibilidade: _v, ...publicCat } = data.categories
  data.categories = publicCat
}
```

**Sobre a chave anónima.** Está no código público. Qualquer pessoa a pode extrair em trinta segundos. Isto não é uma falha: é o desenho do Supabase. A chave identifica o projecto e o *papel* (anónimo); o que esse papel pode fazer é decidido pelas políticas RLS no servidor. Se as políticas estiverem certas, a chave é inofensiva; se estiverem erradas, nenhum esconderijo a salvaria. Existe um verificador, `deploy/verify_rls.py`, precisamente porque tudo depende disso.

**Porquê ir directo.** Latência (o Supabase tem presença global; a nossa máquina é uma só, em Iowa) e alívio da máquina — leituras de catálogo são a maioria absoluta do tráfego e nem chegam a tocar-lhe.

### Canal B — pela API

Configurado em `frontend-web/src/lib/api.js`. Duas funções, `apiGet` e `apiPost`, com três protecções que valem a pena:

**Verificação na construção.** Se faltar a configuração, o *build* de produção falha de imediato:

```javascript
if (!import.meta.env.DEV && !prodBase) {
  throw new Error('VITE_API_BASE_URL em falta — configure antes do build de produção.')
}
```

**Tempo limite explícito.** Sem isto, um pedido a um servidor que não responde fica pendurado indefinidamente e o utilizador olha para uma roda a girar para sempre:

```javascript
const DEFAULT_TIMEOUT_MS = 25000
const controller = new AbortController()
const timer = setTimeout(() => controller.abort(), timeoutMs)
```

Ao esgotar-se, a mensagem é em português e accionável: *"O servidor demorou demasiado a responder. Tente novamente."*

**Erros legíveis com referência.** `parseApiDetail` sabe lidar com as várias formas que o FastAPI usa para reportar erros (texto simples, lista de erros de validação, objecto) e acrescenta os primeiros oito caracteres do identificador de pedido: `(ref: 3f2a1b9c)`. Quando o cliente liga a dizer "deu erro", esse fragmento localiza a linha exacta no registo do servidor. É uma das funcionalidades mais baratas e mais úteis de todo o sistema.

### Como se escolhe entre os dois canais

Em `frontend-web/src/composables/useCatalog.js`:

```javascript
metaCache.value = supabaseConfigured
  ? getCatalogMeta()
  : await apiGet('/catalogo/meta')
```

E o mesmo padrão em `fetchCategoryModels` e `fetchModelDetail`. Se o Supabase estiver configurado, vai directo; caso contrário, recorre à API. **Porquê:** redundância. Se as chaves do Supabase forem retiradas do pacote, ou se as políticas RLS forem endurecidas, a loja continua a funcionar pela API. Custo: a mesma lógica de catálogo existe em dois lugares (JavaScript em `catalogSupabase.js`, Python em `backend-api/core/catalog_service.py`), o que exige disciplina para manter coerente.

### Quando a API é obrigatória

Escritas. Sempre. Porque envolvem coisas que **não podem** estar no navegador:

- Verificar o resultado do Turnstile — exige o **segredo** `TURNSTILE_SECRET_KEY`.
- Enviar email — exige credenciais **SMTP** (Simple Mail Transfer Protocol — Protocolo Simples de Transferência de Correio).
- Escrever nas tabelas com a chave de serviço, que ignora RLS.
- Executar a *saga* transaccional (`backend-api/core/saga/contact_saga.py`), que coordena escrita, email e registo de eventos.
- Impor limites de ritmo e chaves de idempotência (evitar duplicados quando o utilizador clica duas vezes).

Nenhuma destas coisas pode existir em código público, e nenhuma pode ser confiada ao cliente.

---

## III.4 Turnstile (anti-bot) — o fluxo completo

### O problema

Um formulário público na internet recebe *spam* automático. Não por malícia dirigida — por varrimento indiscriminado. Sem defesa, a caixa de entrada enche-se e as mensagens verdadeiras perdem-se.

A defesa clássica era o **CAPTCHA** (Completely Automated Public Turing test to tell Computers and Humans Apart — teste público totalmente automatizado para distinguir computadores de humanos): decifrar letras distorcidas, identificar semáforos. Funciona mal e trata pessoas reais como suspeitas, com custo particular para quem tem dificuldades visuais.

**Turnstile** é a alternativa da Cloudflare: analisa sinais do navegador (comportamento, características do ambiente, reputação) e, na maioria dos casos, aprova em silêncio. O visitante vê um pequeno indicador a confirmar. Sem enigmas.

### O fluxo, passo a passo

**Passo 1 — duas chaves, uma pública e uma secreta.** A *site key* (`VITE_TURNSTILE_SITE_KEY`) identifica o widget e é pública, embutida no pacote. A *secret key* (`TURNSTILE_SECRET_KEY`) vive apenas no `.env` do servidor. Esta assimetria é toda a segurança do mecanismo.

**Passo 2 — resolver que chave usar.** `frontend-web/src/composables/useTurnstile.js` tem uma função dedicada, e a razão está no comentário do código:

```javascript
function resolveTurnstileSiteKey() {
  // Em localhost a chave de produção falha (hostname não autorizado no widget CF).
  // Usa a sitekey de teste "always passes" só em desenvolvimento local.
  if (isLocalHost()) return TEST_SITE_KEY
  const configured = (import.meta.env.VITE_TURNSTILE_SITE_KEY || '').trim()
  ...
}
```

A Cloudflare exige que o widget declare em que domínios pode ser usado. Em `localhost` a chave real recusa. Sem este desvio, seria impossível testar o formulário localmente. A chave de teste `1x00000000000000000000AA` é pública e documentada pela Cloudflare, e aprova sempre — inofensiva porque o servidor também está em modo de desenvolvimento.

**Passo 3 — carregar o *script* da Cloudflare.** Feito uma só vez, com protecções contra duplicação:

```javascript
script.src = 'https://challenges.cloudflare.com/turnstile/v0/api.js?render=explicit'
```

`render=explicit` significa "não desenhes nada automaticamente; eu digo-te quando e onde". Necessário numa SPA, onde o formulário aparece e desaparece conforme a navegação. Repare-se que este domínio tem de constar do CSP em `frontend-web/public/_headers`, em `script-src` e `frame-src` — caso contrário o navegador bloqueia o carregamento (III.7).

**Passo 4 — desenhar o widget e receber o testemunho.** Quando a verificação passa, a Cloudflare chama a nossa função de retorno com um *token* (testemunho) de curta duração:

```javascript
callback: (t) => { token.value = t; loadError.value = '' },
'expired-callback': () => { token.value = '' },
```

O `expired-callback` é importante: os testemunhos expiram. Se o visitante abrir o formulário e só o submeter vinte minutos depois, o testemunho já não vale — e o código limpa-o para que a submissão não avance com algo inválido.

**Passo 5 — mensagens de erro que ensinam.** Um detalhe pequeno com grande valor operacional:

```javascript
loadError.value = isLocalHost()
  ? 'Verificação anti-spam falhou em local. Recarregue a página.'
  : 'Verificação anti-spam indisponível neste domínio. No Cloudflare Turnstile, autorize este hostname (ex. www.diomika.com) e volte a tentar.'
```

A segunda mensagem descreve a causa mais provável **e a acção correctiva**. Quem publicar num domínio novo e esquecer a autorização recebe a instrução em vez de um mistério.

**Passo 6 — submeter.** O testemunho vai no corpo do pedido como `cf_turnstile_response`, definido no modelo em `backend-api/routes/contact.py`:

```python
website: str | None = None  # honeypot — deve ficar vazio
cf_turnstile_response: str | None = None
```

**Passo 7 — o servidor verifica, e é aqui que está a segurança.** Em `backend-api/utils/turnstile.py`:

```python
resp = requests.post(
    "https://challenges.cloudflare.com/turnstile/v0/siteverify",
    data=payload,
    timeout=10,
    verify=_VERIFY,
)
data = resp.json()
if not data.get("success"):
    raise ValueError("Verificação anti-spam inválida")
```

O servidor pergunta à Cloudflare: *"este testemunho é válido, foi emitido para o meu sítio, e ainda não foi usado?"* Envia o segredo e, opcionalmente, o IP do visitante. Um atacante que invente um testemunho falha aqui, porque não tem o segredo nem consegue fazer a Cloudflare confirmar algo que não emitiu.

Três detalhes de robustez: `timeout=10` (não ficar preso se a Cloudflare demorar); `verify=_VERIFY` a apontar para as autoridades de certificação do `certifi` (não confiar no armazém do sistema, que numa máquina antiga pode estar desactualizado); e a versão assíncrona:

```python
async def verify_turnstile_async(token: str | None, remote_ip: str | None = None) -> None:
    """Não bloqueia o event loop — usa thread para HTTP sync."""
    await asyncio.to_thread(verify_turnstile, token, remote_ip)
```

Sem isto, um pedido a aguardar resposta da Cloudflare bloquearia o processamento de **todos** os outros pedidos (ver IV.1).

**Passo 8 — comportamento de reserva.** Se não houver segredo configurado:

```python
if not secret:
    if settings.is_production:
        raise ValueError("Verificação anti-spam indisponível")
    return
```

Em desenvolvimento, deixa passar. Em produção, **recusa**. Chama-se *fail closed* — falhar fechado: quando em dúvida, negar. E, uma camada antes, `backend-api/core/config.py` nem deixa a API arrancar em produção sem `TURNSTILE_SECRET_KEY`, e recusa arrancar se as chaves configuradas forem as de teste.

### As outras três camadas do mesmo formulário

O Turnstile não trabalha sozinho. Em `backend-api/routes/contact.py`, o mesmo pedido atravessa:

1. **Interruptor de funcionalidade** — `if not flag("CONTACT_FORM", True)` permite desligar o formulário sem publicar código novo (devolve `503`).
2. **Limite de ritmo** — `rate_limit(request, "contact_form", max_calls=5, window_seconds=60)`: cinco submissões por minuto por IP.
3. **Chave de idempotência** — obrigatória em produção; se o mesmo pedido chegar duas vezes, a resposta guardada é devolvida em vez de se criar um duplicado. Se estiver a ser processado, devolve `409`.
4. **Armadilha de mel** (*honeypot*) — um campo `website` invisível para humanos. Programas automáticos preenchem todos os campos que encontram; humanos não vêem este. Se vier preenchido, `400` e registo de aviso:

```python
if msg.website:
    logger.warning("Honeypot activado de %s", request.client.host if request.client else "?")
    raise HTTPException(status_code=400, detail="Pedido inválido")
```

Quatro camadas independentes. Nenhuma é perfeita; juntas, o formulário fica muito pouco atraente para automatismos.

---

## III.5 Cookies, consentimento e PostHog

### O contexto legal e ético

O **RGPD** (Regulamento Geral sobre a Protecção de Dados — a lei europeia de privacidade) e a legislação sobre comunicações electrónicas exigem consentimento **prévio** para armazenar informação no dispositivo do utilizador com fins não estritamente necessários. Analítica de utilização não é estritamente necessária. Logo: consentimento antes, não depois.

Muitos sítios cumprem isto na aparência — mostram a faixa e carregam a analítica de imediato. Aqui não é o caso, e isso é verificável no código.

### O que é o PostHog

Uma ferramenta de **analítica de produto**: quantas pessoas visitaram, que páginas, onde abandonaram, o que clicaram. Informação útil para decidir o que melhorar. Não é o mesmo que rastreio publicitário, mas envolve identificadores persistentes no dispositivo, o que a coloca dentro do âmbito do consentimento.

Está configurada para o servidor europeu, `https://eu.i.posthog.com`, por omissão — os dados ficam na União Europeia.

### O mecanismo

Todo o comportamento cabe em `frontend-web/src/components/CookieBanner.vue`. É curto e vale a pena ler com atenção:

```javascript
const CONSENT_KEY = 'diomika_cookie_consent'
const posthogKey = import.meta.env.VITE_POSTHOG_KEY || ''
const posthogHost = import.meta.env.VITE_POSTHOG_HOST || 'https://eu.i.posthog.com'

const loadPosthog = async () => {
  if (!posthogKey || window.__diomikaPosthog) return
  try {
    const { default: posthog } = await import('posthog-js')
    posthog.init(posthogKey, { api_host: posthogHost, persistence: 'localStorage', autocapture: true, capture_pageview: true })
    window.__diomikaPosthog = true
  } catch { /* ignore */ }
}
```

E a decisão inicial:

```javascript
onMounted(() => {
  const saved = localStorage.getItem(CONSENT_KEY)
  if (saved === 'accepted') { loadPosthog(); return }
  if (saved === 'rejected') return
  // Sem key PostHog: não mostrar banner (nada a consentir além do essencial)
  if (!posthogKey) return
  visible.value = true
})
```

### Porque este desenho é correcto

**O código de terceiros só é descarregado depois do "Aceitar".** A linha decisiva é `await import('posthog-js')` **dentro** de `loadPosthog`, que só é chamada em `accept()` ou quando já existe consentimento gravado. Não é o PostHog "carregado mas inactivo": o Vite empacota `posthog-js` num ficheiro separado dentro de `frontend-web/dist/assets/`, e o navegador nunca o pede se ninguém aceitar. Zero pedidos a servidores do PostHog, zero identificadores, para quem recusa ou ignora.

**Recusar é uma escolha registada, não um adiamento.** `localStorage.setItem(CONSENT_KEY, 'rejected')` e a faixa nunca volta. Um sítio que repete a pergunta a cada visita está a pressionar até obter o "sim" — prática que os reguladores europeus consideram consentimento inválido.

**Sem faixa quando não há nada a consentir.** Se `VITE_POSTHOG_KEY` não estiver definida, não há analítica, logo não há pergunta. Interromper o visitante com um pedido de consentimento para algo que não existe seria, além de inútil, contraproducente: ensina as pessoas a clicar "Aceitar" sem ler.

**A faixa é acessível.** `role="dialog"` e `aria-label="Consentimento de cookies"` para leitores de ecrã; dois botões reais, "Recusar" e "Aceitar", com pesos visuais próximos — não um "Aceitar" enorme e um "Recusar" escondido em letra cinzenta.

**Há informação a mais de um clique.** A faixa liga para `/privacidade` (`frontend-web/src/views/PrivacyView.vue`), onde a explicação é completa. E o sistema tem uma contrapartida real do lado do servidor: `backend-api/routes/privacy.py` expõe `/admin/privacy/erase` para apagar dados pessoais associados a um email, e há uma limpeza automática por retenção em `backend-api/core/retention.py`. Direitos que existem em código, não só em texto.

**Nota técnica:** `persistence: 'localStorage'` usa armazenamento local em vez de *cookies* clássicos. Não altera a obrigação legal — é armazenamento no dispositivo do utilizador da mesma forma — mas evita enviar identificadores em cada pedido HTTP.

---

## III.6 `functions/_middleware.js` — bloqueio de sondagens

### O problema concreto

Como explicado em III.2, uma SPA exige que o servidor devolva `index.html` para caminhos desconhecidos. Isso significa que, sem intervenção:

```
GET /.env            → 200 OK  + index.html
GET /.git/config     → 200 OK  + index.html
GET /package.json    → 200 OK  + index.html
```

Nenhum destes pedidos obtém informação sensível — o conteúdo devolvido é a página da loja. Mas o **código de estado** `200 OK` é o problema. Ferramentas automáticas de reconhecimento classificam alvos por códigos de resposta; um `200` em `/.env` marca o sítio como "promissor" e desencadeia varrimentos mais agressivos. É ruído, consome quota e, ocasionalmente, atrai atenção humana.

### A solução

As **Pages Functions** são código que corre na rede da Cloudflare (não no navegador, não na nossa máquina) antes de a resposta ser servida. Um ficheiro chamado `_middleware.js` intercepta *todos* os pedidos.

`frontend-web/functions/_middleware.js` na íntegra:

```javascript
const BLOCK = [
  /^\/\.env(?:$|\.)/i,
  /^\/\.git(?:$|\/)/i,
  /^\/package(?:-lock)?\.json$/i,
  /^\/vite\.config\./i,
  /^\/src(?:$|\/)/i,
  /^\/backend-api(?:$|\/)/i,
  /^\/\.github(?:$|\/)/i,
  /^\/node_modules(?:$|\/)/i,
];

export async function onRequest(context) {
  const path = new URL(context.request.url).pathname;
  if (BLOCK.some((re) => re.test(path))) {
    return new Response("Not Found", {
      status: 404,
      headers: {
        "content-type": "text/plain; charset=utf-8",
        "cache-control": "no-store",
        "x-content-type-options": "nosniff",
      },
    });
  }
  return context.next();
}
```

### Leitura detalhada

Os padrões são **expressões regulares** — uma notação para descrever formas de texto. Descodificando o primeiro, `/^\/\.env(?:$|\.)/i`: começa (`^`) com uma barra (`\/`), seguida de um ponto literal (`\.`), seguida de `env`, e a seguir ou termina (`$`) ou vem outro ponto (`\.`). O `i` no fim significa indiferente a maiúsculas. Isto apanha `/.env`, `/.env.local`, `/.ENV.production`.

Os alvos escolhidos correspondem aos caminhos mais procurados por ferramentas automáticas: ficheiros de configuração com segredos (`.env`), repositórios expostos (`.git`, que se descarregado permite reconstituir todo o histórico de código), manifestos de dependências (`package.json`, útil para procurar versões vulneráveis), código-fonte (`/src`, `/backend-api`), configuração de integração contínua (`.github`) e dependências instaladas (`node_modules`).

A resposta é deliberadamente pobre: texto simples `"Not Found"`, sem HTML, sem pistas. `cache-control: no-store` evita que a Cloudflare guarde a resposta (não se quer poluir a cache com respostas negativas). `x-content-type-options: nosniff` impede o navegador de tentar adivinhar o tipo do conteúdo — hábito de segurança aplicado até aqui.

`return context.next()` é a linha que faz tudo o resto funcionar: para pedidos que não correspondem a nenhum padrão, deixa continuar o processamento normal. Um *middleware* que se esquecesse desta linha derrubaria o sítio inteiro.

### O que isto é e o que não é

**Não é** uma medida de segurança essencial: esses ficheiros nunca estiveram em `dist/`, porque o processo de construção só copia `public/` e os artefactos compilados. Nada havia para roubar.

**É** redução de ruído e de sinal para o atacante — e uma segunda camada, caso um dia alguém copie inadvertidamente algo para `public/`. Segurança em profundidade significa exactamente isto: proteger contra o erro que ainda não foi cometido.

---

## III.7 `_headers` e CSP em linguagem simples

O ficheiro `frontend-web/public/_headers` (copiado para `frontend-web/dist/_headers` no *build*) instrui a Cloudflare Pages a acrescentar cabeçalhos HTTP às respostas. A sintaxe é simples: uma linha com um padrão de caminho, e a seguir linhas indentadas com cabeçalhos.

### Os cabeçalhos simples

```
/*
  X-Frame-Options: DENY
  X-Content-Type-Options: nosniff
  Referrer-Policy: strict-origin-when-cross-origin
  Permissions-Policy: camera=(), microphone=(), geolocation=()
  Strict-Transport-Security: max-age=31536000; includeSubDomains; preload
```

- **`X-Frame-Options: DENY`** — ninguém pode incorporar a nossa loja dentro de um quadro (*iframe*) noutro sítio. Isto derrota o *clickjacking*: colocar a nossa página invisível sobre outra e fazer o visitante clicar em botões nossos sem saber.
- **`X-Content-Type-Options: nosniff`** — "acredita no tipo que eu declaro; não tentes adivinhar". Sem isto, um navegador pode decidir que um ficheiro declarado como texto é na verdade JavaScript e executá-lo.
- **`Referrer-Policy: strict-origin-when-cross-origin`** — quando o visitante sai da nossa loja para outro sítio, esse sítio recebe apenas `https://www.diomika.com`, não o endereço completo da página onde estava. Evita fugas de informação através de endereços com parâmetros.
- **`Permissions-Policy: camera=(), microphone=(), geolocation=()`** — a página renuncia explicitamente ao acesso a câmara, microfone e localização. Uma loja não precisa; declará-lo significa que nem um componente comprometido conseguiria pedi-los.
- **`Strict-Transport-Security`** (**HSTS** — HTTP Strict Transport Security) — "durante um ano (31 536 000 segundos), fala comigo **só** por HTTPS, e o mesmo para todos os subdomínios". Depois da primeira visita, o navegador nem tenta HTTP, mesmo que o visitante escreva `http://`. `preload` significa que o domínio pode ser incluído numa lista distribuída com os próprios navegadores, protegendo até a primeira visita. **Cuidado:** HSTS é uma promessa difícil de revogar — durante um ano, um domínio sem HTTPS funcional fica inacessível. É uma decisão consciente.

### Cache por tipo de ficheiro

```
/assets/*
  Cache-Control: public, max-age=31536000, immutable
```

"Guarda estes ficheiros um ano e nunca voltes a perguntar." Isto seria temerário — como se publicaria uma correcção? — se não fosse pelas impressões digitais nos nomes (III.1). Como `index-D846eMr6.js` muda de nome ao mudar de conteúdo, o `index.html` novo aponta para um nome novo, e o navegador pede o ficheiro novo. O antigo pode ficar em cache para sempre, sem consequências. Ficheiro pequeno e sempre fresco: apenas o `index.html`.

### O CSP, directiva por directiva

**CSP** significa Content Security Policy — Política de Segurança de Conteúdo. É, provavelmente, o cabeçalho de segurança mais poderoso da web.

A ideia: o navegador não sabe distinguir código legítimo nosso de código injectado por um atacante — para ele, tudo o que estiver na página é da página. O CSP resolve isto invertendo o modelo: declaramos antecipadamente **de onde** é legítimo carregar cada tipo de recurso, e o navegador **bloqueia tudo o resto**. Passa-se de "permitido por omissão" para "proibido por omissão".

O nosso CSP (do ficheiro `_headers`), decomposto:

| Directiva | Valor | Em português |
|---|---|---|
| `default-src` | `'self'` | Regra base: só o nosso próprio domínio. As directivas seguintes abrem excepções. |
| `script-src` | `'self' https://challenges.cloudflare.com` | Só executa código nosso e da Cloudflare (Turnstile). **Nada mais.** |
| `script-src-elem` | idem | O mesmo, especificamente para elementos `<script>`. |
| `connect-src` | `'self' https://*.supabase.co https://challenges.cloudflare.com https://api.diomika.com https://*.i.posthog.com https://eu.i.posthog.com` | Os únicos destinos a que a página pode fazer pedidos de dados. |
| `img-src` | `'self' data: blob: https://*.supabase.co https://*.r2.dev` | Imagens: nossas, embutidas, geradas em memória, do Supabase Storage, da Cloudflare R2. |
| `style-src` | `'self'` | Estilos só de ficheiros nossos — nem estilos inline. |
| `frame-src` | `https://challenges.cloudflare.com` | O único quadro permitido é o widget Turnstile. |
| `font-src` | `'self' data:` | Tipos de letra próprios (`@fontsource/arimo`, empacotado localmente) ou embutidos. |
| `base-uri` | `'self'` | Impede um atacante de reescrever a base dos endereços relativos da página. |
| `form-action` | `'self'` | Formulários só podem submeter para nós — não para o servidor de um atacante. |
| `object-src` | `'none'` | Nada de Flash, Java, ou objectos embutidos legados. |
| `frame-ancestors` | `'none'` | Ninguém nos pode incorporar (reforça `X-Frame-Options`). |
| `upgrade-insecure-requests` | — | Qualquer endereço `http://` esquecido é automaticamente convertido para `https://`. |

**Porque isto importa tanto.** O ataque mais comum contra sítios web chama-se **XSS** (Cross-Site Scripting — execução de código de terceiros no contexto do nosso sítio): um atacante consegue inserir JavaScript na página e passa a poder ler tudo o que o visitante vê, incluindo sessões. Com este CSP, mesmo que uma injecção aconteça, o código injectado não se executa se vier de outro domínio, não pode enviar dados para fora (`connect-src` restrito) e não pode redireccionar submissões (`form-action 'self'`). Não é imunidade; é reduzir uma catástrofe a um incidente.

**A relação de causa e efeito com o resto do sistema** é directa e vale a pena interiorizar: `challenges.cloudflare.com` está em `script-src` e `frame-src` **porque** o Turnstile precisa (III.4); `*.supabase.co` está em `connect-src` **porque** o navegador fala directamente com o Supabase (III.3); `api.diomika.com` está lá **porque** é a nossa API; `*.i.posthog.com` **porque** existe analítica consentida (III.5); `*.r2.dev` **porque** as imagens podem migrar para a Cloudflare R2. Cada entrada tem um dono identificável. Nenhuma está lá "por precaução" — e essa disciplina é o que mantém um CSP útil ao longo do tempo.

**Erro típico:** adicionar uma biblioteca externa nova (um mapa, um widget de chat) e ver "nada acontecer", sem erro visível na interface. A causa está quase sempre na consola do navegador, com uma mensagem de violação de CSP. A correcção certa é acrescentar a origem à directiva adequada — nunca relaxar para `'unsafe-inline'` ou `*`, que destroem a protecção. Existe um verificador automático: `deploy/verify_csp.py`.

**Nota:** a API tem o seu próprio CSP, muito mais estrito, em `backend-api/core/middleware.py`: `default-src 'none'; frame-ancestors 'none'`. Faz sentido — a API devolve JSON, nunca páginas, e portanto não deve carregar absolutamente nada.

---

## III.8 Variáveis `VITE_*` — o que significa "embutido no pacote"

### O mecanismo

Numa aplicação de servidor, a configuração é lida em tempo de execução: o programa arranca, consulta o ambiente, obtém o valor. Mudar a configuração é reiniciar.

No navegador isso é impossível. Não existe "ambiente" no navegador do visitante. Então o Vite faz outra coisa: durante o *build*, procura no código todas as ocorrências de `import.meta.env.VITE_ALGO` e **substitui-as pelo texto literal do valor**.

Antes (`frontend-web/src/lib/supabase.js`):

```javascript
const supabaseUrl = import.meta.env.VITE_SUPABASE_URL || ''
```

Depois, dentro de `dist/assets/index-D846eMr6.js` (esquematicamente):

```javascript
const supabaseUrl = "https://abcdefgh.supabase.co" || ''
```

O valor deixou de ser configuração e passou a ser **código**. Está literalmente escrito no ficheiro que qualquer pessoa no mundo pode descarregar.

O prefixo `VITE_` não é decorativo: é uma barreira de segurança. O Vite só expõe variáveis com esse prefixo. Se o ficheiro `.env` contiver `SUPABASE_KEY` (a chave de serviço) e `VITE_SUPABASE_ANON_KEY` (a anónima), **só a segunda entra no pacote**. A primeira é ignorada, mesmo estando no mesmo ficheiro. E o `.env` é o da raiz do projecto, por causa de `envDir` (III.1).

### As três consequências

**1. Tudo o que é `VITE_*` é público. Sem excepção.** Não é "difícil de encontrar" nem "obscuro": está em texto no ficheiro. A lista do que é legítimo ter lá está em `deploy/env.free.example`, na secção dedicada ao painel da Cloudflare Pages:

| Variável | Porque pode ser pública |
|---|---|
| `VITE_API_BASE_URL` | É um endereço público — `https://api.diomika.com`. |
| `VITE_SUPABASE_URL` | Idem, endereço do projecto. |
| `VITE_SUPABASE_ANON_KEY` | Desenhada para ser pública; a protecção é o RLS. |
| `VITE_TURNSTILE_SITE_KEY` | A metade pública do par; o segredo fica no servidor. |
| `VITE_POSTHOG_KEY` | Chave de ingestão, apenas escreve eventos; não permite ler dados. |
| `VITE_POSTHOG_HOST` | Endereço público. |
| `VITE_SUPABASE_STORAGE_BUCKET` | Nome de um contentor de ficheiros. |
| `VITE_STORAGE_PRIVATE` | Uma bandeira de comportamento. |
| `VITE_BETA_MODE` | Idem. |

E o que **nunca** pode ter prefixo `VITE_`: `SUPABASE_KEY` (chave de serviço), `API_SECRET_KEY`, `TURNSTILE_SECRET_KEY`, `MAIL_PASSWORD`, `SUPABASE_DB_PASSWORD`, `CLOUDFLARE_TUNNEL_TOKEN`, `DIOMIKA_DESKTOP_GATE`, `SENTRY_DSN`, `AXIOM_TOKEN`, chaves da R2. Se alguma destas aparecesse com prefixo `VITE_`, ficaria publicada no primeiro *build*. Não haveria aviso. Existe por isso um verificador dedicado, `deploy/verify_bundle_secrets.py`, que procura padrões de segredo dentro de `frontend-web/dist/` e falha a publicação se encontrar algo.

**2. Mudar uma variável exige reconstruir e republicar.** Não é reiniciar nada: o valor está compilado. Alterar `VITE_API_BASE_URL` no painel da Cloudflare Pages sem accionar novo *build* não tem efeito nenhum — a loja continua a apontar para o endereço antigo. Esta é uma das confusões mais frequentes de quem chega, e vale a pena repetir: **as variáveis `VITE_*` são consumidas no momento do *build*, não no momento da visita.**

**3. A ausência é detectada cedo.** Em `frontend-web/src/lib/api.js`:

```javascript
if (!import.meta.env.DEV && !prodBase) {
  throw new Error('VITE_API_BASE_URL em falta — configure antes do build de produção.')
}
```

Melhor falhar de forma ruidosa na publicação do que descobrir, com visitantes no sítio, que todos os formulários apontam para o vazio. O mesmo princípio, do lado do servidor, é `validate_startup()` (IV.2). É uma filosofia consistente em todo o projecto: **falhar cedo, falhar alto, com mensagem que diz o que fazer.**

---

# Parte IV — A API (`backend-api`)

## IV.1 FastAPI, uvicorn e ASGI explicados

### As três camadas

Um pedido HTTP que chega à nossa aplicação atravessa três peças com responsabilidades distintas. Confundi-las é fonte de mal-entendidos, por isso vale a pena separá-las com clareza.

**uvicorn — o servidor.** É o programa que abre uma porta TCP, aceita ligações, lê os bytes que chegam, reconhece que são um pedido HTTP e o interpreta (método, caminho, cabeçalhos, corpo). Não sabe nada sobre a Diomika. É um tradutor entre a rede e o Python.

**ASGI — o contrato.** Asynchronous Server Gateway Interface — Interface de Porta de Entrada de Servidor Assíncrona. Não é um programa: é uma **convenção** que define como um servidor entrega um pedido a uma aplicação Python. Qualquer servidor ASGI funciona com qualquer aplicação ASGI. É por isso que se pode trocar `uvicorn` por outro servidor sem alterar uma linha da aplicação.

Historicamente existia o **WSGI** (Web Server Gateway Interface, a versão síncrona), onde cada pedido ocupava um processo ou *thread* do início ao fim. O ASGI nasceu para permitir **concorrência assíncrona**, e essa diferença é decisiva num sistema como este.

**FastAPI — a aplicação.** A biblioteca onde escrevemos a lógica: rotas, validação, respostas. Construída sobre Starlette (que trata dos aspectos ASGI) e Pydantic (que trata da validação de dados).

### Porque o "assíncrono" é o que salva a e2-micro

Imagine-se um restaurante. No modelo síncrono, cada empregado acompanha um cliente do princípio ao fim: fica **parado** junto à mesa enquanto a cozinha prepara o prato. Com cinco empregados, cinco clientes.

No modelo assíncrono, o empregado tira o pedido, entrega-o na cozinha e **vai atender outra mesa**. Quando a cozinha avisa que está pronto, ele serve. O mesmo empregado atende dez mesas, porque o tempo de espera não é tempo de trabalho.

Na nossa API, a "cozinha" são as esperas por rede: o Supabase a responder, a Cloudflare a validar um testemunho Turnstile, o servidor de correio a aceitar um email. Todas medidas em dezenas ou centenas de milissegundos — uma eternidade em tempo de processador.

Escrever `async def` e usar `await` é dizer: "aqui vou esperar; usa este tempo para outra coisa". Exemplo real, em `backend-api/routes/contact.py`:

```python
await verify_turnstile_async(msg.cf_turnstile_response, get_client_ip(request))
```

Enquanto este pedido espera pela Cloudflare, o mesmo processo serve páginas de catálogo a outros visitantes.

**A armadilha correspondente.** Se, dentro de uma função `async`, se fizer uma operação bloqueante — leitura de rede síncrona, cálculo pesado — **todo** o processo pára. Não é este pedido que fica lento: são todos. É o empregado que decide lavar a louça no meio da sala.

Por isso o projecto usa sistematicamente `asyncio.to_thread`, que despacha o trabalho bloqueante para uma *thread* separada. Em `backend-api/utils/turnstile.py`:

```python
async def verify_turnstile_async(token: str | None, remote_ip: str | None = None) -> None:
    """Não bloqueia o event loop — usa thread para HTTP sync."""
    await asyncio.to_thread(verify_turnstile, token, remote_ip)
```

E em `backend-api/routes/catalog_generic.py`, onde a biblioteca do Supabase é síncrona:

```python
return await asyncio.to_thread(get_or_set, cache_key, float(ttl), load)
```

Também em `backend-api/core/health.py`, onde qualquer consulta à base de dados passa por um `ThreadPoolExecutor` com tempo limite de dois segundos — porque uma verificação de saúde que fica pendurada é pior do que não existir.

### O que o FastAPI dá de graça

**Validação declarativa.** Descreve-se a forma esperada dos dados e a validação acontece antes de o nosso código correr. De `backend-api/routes/contact.py`:

```python
class ContactRequest(BaseModel):
    nome: str = Field(..., min_length=2, max_length=120)
    email: EmailStr
    contacto: str = Field(..., min_length=6, max_length=20)
    assunto: str = Field(..., min_length=3, max_length=200)
    mensagem: str = Field(..., min_length=10, max_length=5000)
```

Um pedido com nome de uma letra, ou email malformado, ou mensagem de 50 000 caracteres, é rejeitado com `422` e uma descrição do problema — sem escrever um único `if`. O `...` indica campo obrigatório. Os limites máximos não são cosméticos: sem eles, um atacante poderia enviar megabytes num campo de texto.

Há ainda normalização preventiva:

```python
@field_validator("nome", "contacto", "assunto", "mensagem", mode="before")
@classmethod
def _nfc(cls, v: object) -> object:
    if isinstance(v, str):
        return normalize_text(v)
    return v
```

O mesmo carácter pode ter várias representações em Unicode (por exemplo "ã" como um carácter ou como "a" mais um til combinado). Normalizar evita duplicados invisíveis e uma classe de ataques baseada em representações alternativas.

**Injecção de dependências.** Requisitos declarados na assinatura da rota:

```python
@router.get("", dependencies=[Depends(admin_must_be_local), Depends(require_mensagens)])
def get_messages(limit: int = 100, offset: int = 0):
```

Lê-se: "para chegar a esta função, é necessário estar em ambiente local **e** ter permissão de mensagens". A verificação corre antes; se falhar, a função nunca é chamada. A segurança fica **visível na declaração da rota**, e não escondida no meio do corpo — o que a torna auditável por leitura, e verificável por ferramentas (`deploy/verify_route_guards.py`).

**Documentação automática.** O FastAPI gera a especificação OpenAPI e uma interface para explorar a API. Útil em desenvolvimento, **perigosa em produção** — é um mapa completo dos *endpoints*. Daí a lógica em `backend-api/core/config.py`:

```python
@property
def docs_enabled(self) -> bool:
    """Swagger/OpenAPI: nunca em produção; nunca com API_BASE_URL https (túnel público)."""
    if self.is_production:
        return False
    if self.api_base_url.startswith("https://"):
        return False
```

Duas condições independentes, e a segunda é a mais interessante: mesmo que alguém se esqueça de definir o ambiente como produção, o simples facto de a API ter um endereço público em HTTPS desliga a documentação. Proteger contra a distracção humana, não apenas contra a configuração errada.

---

## IV.2 `backend-api/main.py` como porta de entrada

Este ficheiro tem menos de 200 linhas e a **ordem** dessas linhas é significativa. Vamos percorrê-la.

### 1. Carregar o ambiente, antes de tudo

```python
from core.env_loader import load_project_env
load_project_env()

from core.auth import require_ops
from core.local_only import admin_must_be_local
...
```

Repare-se que `load_project_env()` é chamado **entre** importações — o que normalmente seria considerado má prática. É deliberado: vários módulos leem variáveis de ambiente no momento em que são importados. Se o `.env` não estiver carregado antes, esses módulos veriam valores vazios e tomariam decisões erradas de forma silenciosa.

### 2. Registo estruturado e ocultação de segredos

```python
if not (os.getenv("LOG_FORMAT") or "").strip():
    if (os.getenv("DIOMIKA_ENV") or "").strip().lower() == "production":
        os.environ["LOG_FORMAT"] = "json"
configure_structured_logging()
...
install_log_redaction()
_error_mode = init_error_tracking()
```

Em produção, os registos saem em JSON — feios para humanos, perfeitos para máquinas (podem ser filtrados e pesquisados por ferramentas como o Axiom). Em desenvolvimento, texto legível.

`install_log_redaction()` (em `backend-api/core/log_safe.py`) instala um filtro que remove padrões parecidos com segredos das linhas de registo. **Porquê:** a fuga de segredos mais comum não é por invasão — é por um registo demasiado verboso enviado para um serviço externo. Assume-se que alguém, algum dia, vai registar um objecto que contém uma chave por descuido.

### 3. Validação de arranque — o portão

```python
settings = get_settings()
settings.validate_startup()
```

Se o ambiente for `production`, `backend-api/core/config.py` exige, sob pena de o processo **terminar imediatamente**: `API_SECRET_KEY` (com pelo menos 32 caracteres), `SUPABASE_URL`, `SUPABASE_KEY`, `TURNSTILE_SECRET_KEY`, `ALLOWED_HOSTS`, `CORS_ORIGINS` sem `localhost`, `REDIS_URL`, `SUPABASE_STORAGE_PRIVATE=1`, `API_BASE_URL` em `https://`, chaves Turnstile reais (não as de teste), ausência de `DIOMIKA_SSL_INSECURE`, ausência da variável obsoleta `ADMIN_ALLOW_REMOTE`, e `TRUSTED_PROXY_IPS` definida se `TRUST_PROXY=1`.

**Porquê tão severo.** A alternativa é uma API que arranca "quase bem": sem verificação anti-spam, ou com CORS aberto, ou com armazenamento público. Funcionaria, e ninguém notaria — até notar. Uma API que se recusa a arrancar com uma mensagem explícita é um problema de cinco minutos; uma API mal configurada em silêncio é um problema de meses. Note-se que cada mensagem de erro inclui a acção correctiva:

```
ERRO: REDIS_URL obrigatorio em producao final (rate limit + sessões partilhadas entre workers).
```

### 4. Ciclo de vida

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    from core.background_workers import start_background_workers, stop_background_workers
    from core.schema_engine import bootstrap_database_schema

    if (os.getenv("SCHEMA_BOOTSTRAP") or "1").strip().lower() not in ("0", "false", "no"):
        bootstrap_database_schema(logger)
    else:
        logger.info("SCHEMA_BOOTSTRAP=0 — skip bootstrap (replica ou init já feito)")
    start_background_workers()
    yield
    stop_background_workers()
```

Tudo o que está antes do `yield` corre no arranque; tudo o que está depois, no encerramento ordenado. Verificar o esquema da base de dados (IV.8), lançar os trabalhadores (IV.7), e no fim pará-los com elegância. O interruptor `SCHEMA_BOOTSTRAP=0` existe para o caso de vários processos arrancarem em paralelo — não faz sentido cinco processos verificarem o mesmo esquema simultaneamente.

### 5. Construção da aplicação

```python
app = FastAPI(
    title="Diomika API",
    version=VERSION,
    docs_url="/api/docs" if settings.docs_enabled else None,
    redoc_url="/api/redoc" if settings.docs_enabled else None,
    openapi_url="/openapi.json" if settings.docs_enabled else None,
    lifespan=lifespan,
)
```

Em produção, os três endereços de documentação passam a `None` — não existem, devolvem `404`. Não é uma protecção por permissão: é ausência.

### 6. Middlewares e fronteiras de rede

Tratado em detalhe em IV.4. Nota importante sobre a produção:

```python
if settings.is_production:
    allowed_hosts = [h.strip() for h in (os.getenv("ALLOWED_HOSTS") or "").split(",") if h.strip()]
    # Fail-closed: sem hosts → middleware com lista vazia rejeita tudo (validate_startup já exige)
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=allowed_hosts or ["invalid.invalid"])
```

`TrustedHostMiddleware` rejeita pedidos cujo cabeçalho `Host` não conste da lista, protegendo contra ataques de confusão de domínio. E o `or ["invalid.invalid"]` é uma pequena obra de arte defensiva: se a lista viesse vazia, a alternativa preguiçosa seria "aceitar tudo"; aqui, coloca-se um valor que nunca corresponde a nada, e a API rejeita todos os pedidos. Falhar fechado, mesmo num caso que `validate_startup()` já deveria ter impedido.

### 7. Rotas e tratamento global de erros

```python
app.include_router(admin_auth.router)
app.include_router(privacy.router)
app.include_router(catalog_generic.router)
...
```

E depois:

```python
@app.exception_handler(Exception)
async def _unhandled_exception(request, exc):
    """Em produção não devolve stack traces ao cliente."""
    ...
    if settings.is_production:
        return JSONResponse(status_code=500, content={"detail": "Erro interno"})
    return JSONResponse(status_code=500, content={"detail": str(exc)})
```

Um erro inesperado em desenvolvimento mostra a mensagem completa (útil). Em produção mostra `"Erro interno"` (seguro) — mas o detalhe completo vai para os registos e para o rastreio de erros, junto com o caminho e o identificador do pedido. O cliente recebe a referência; o operador tem tudo. Um *stack trace* devolvido ao cliente revela caminhos de ficheiros, versões de bibliotecas e estrutura interna — material de reconhecimento gratuito para um atacante.

---

## IV.3 Os routers

Um **router** é um agrupamento de *endpoints* relacionados, com um prefixo comum. Serve organização e, sobretudo, permite aplicar guardas a um conjunto inteiro numa só linha.

| Router | Ficheiro | Prefixo | Papel | Quem pode |
|---|---|---|---|---|
| Categorias | `backend-api/routes/categories.py` | `/categorias` | Lista e detalhe de categorias | Público (leitura) |
| Catálogo | `backend-api/routes/catalog_generic.py` | `/catalogo` | Metadados, listagem por categoria, detalhe de modelo | Público (leitura); `/catalogo/admin/*` restrito |
| Contacto | `backend-api/routes/contact.py` | `/contacto` | Submissão pública; leitura, marcação e resposta | `POST` público; resto restrito |
| Orçamentos | `backend-api/routes/orcamentos.py` | `/orcamentos` | Submissão pública; PDF do pedido | `POST` público; PDF restrito |
| Encomendas internas | `backend-api/routes/encomendas.py` | `/encomendas-internas` | Criação de encomendas e PDF | Restrito |
| Admin CRUD | `backend-api/routes/admin_crud.py` | `/admin/crud` | Criar, ler, actualizar, apagar registos genéricos | Restrito |
| Admin | `backend-api/routes/admin.py` | `/admin` | Exportar e importar CSV | Restrito |
| Autenticação admin | `backend-api/routes/admin_auth.py` | `/admin/auth` | Sessão, MFA, gestão de utilizadores | Restrito |
| Privacidade | `backend-api/routes/privacy.py` | `/admin/privacy` | Apagar dados pessoais por email | Restrito (papel `admin`) |
| Sistema | `backend-api/routes/system.py` | `/system` | Configuração do backoffice, esquemas, categorias | Restrito |
| Saúde | `backend-api/main.py` | `/health` | Diagnóstico | `/health` e `/health/ready` públicos; `/health/detail` restrito |

**CRUD** significa Create, Read, Update, Delete — Criar, Ler, Actualizar, Apagar: as quatro operações básicas sobre dados.

Alguns pontos que merecem destaque.

**O catálogo é dirigido por configuração, não por código repetido.** Em `backend-api/routes/catalog_generic.py`, uma única rota serve todos os tipos de catálogo:

```python
@router.get("/{tipo}/modelos-catalogo/{id_categoria}")
async def list_storefront_catalog(tipo: str, id_categoria: str, filter_tipo: str | None = None):
```

O `{tipo}` é validado contra um registo central:

```python
def _require_tipo(tipo: str) -> dict:
    if not is_valid_tipo(tipo):
        raise HTTPException(status_code=404, detail=f"Tipo «{tipo}» não registado.")
    return CATALOG_TYPES[tipo]
```

Acrescentar uma nova família de produtos não exige escrever rotas novas: registá-la em `backend-api/models/catalog_registry.py` é suficiente. Esta é a filosofia de IV.8 aplicada ao encaminhamento.

**Leituras públicas são guardadas em cache duas vezes.** Primeiro em memória no servidor:

```python
ttl = catalog_cache_ttl()
return await asyncio.to_thread(get_or_set, "catalog:meta", float(ttl), catalog_metadata)
```

E depois no *edge* da Cloudflare, através do cabeçalho posto pelo middleware (IV.4). Numa máquina com processamento partilhado, a diferença entre calcular uma resposta a cada pedido e calculá-la uma vez por minuto é a diferença entre sobreviver e não sobreviver a um pico de visitas.

**Paginação com limites impostos pelo servidor.** Em vários sítios, o mesmo padrão:

```python
limit = min(max(limit, 1), 200)
offset = max(offset, 0)
```

Nunca se confia no valor que o cliente pediu. Sem este limite, `?limit=1000000` seria um pedido de negação de serviço escrito num navegador.

**O mesmo caminho serve público e privado, com guardas diferentes.** Em `backend-api/routes/contact.py`, `POST /contacto` é público (com Turnstile, limite de ritmo, idempotência e armadilha de mel), enquanto `GET /contacto` exige `admin_must_be_local` e `require_mensagens`. Mesma raiz, mundos diferentes.

**A resposta a uma mensagem é mais elaborada do que parece.** `POST /contacto/responder/{message_id}` reconstrói o assunto preservando uma referência estável:

```python
ref_id = f"[Ref: #{message_id[:8]}]"
clean_subject = re.sub(r"\[Ref: #\w+\]", "", original_subject).strip()
```

Assim uma conversa por email mantém o fio, sem acumular `Re: Re: Re:` nem duplicar a referência. E o histórico é classificado por autor comparando o remetente com `MAIL_FROM`, para o backoffice mostrar a conversa em forma de diálogo.

---

## IV.4 Middleware: o que é, e a ordem mental

### O conceito

Certas tarefas têm de acontecer em **todos** os pedidos: verificar limites, atribuir identificador, acrescentar cabeçalhos de segurança, medir duração. Escrever isso em cada função seria repetição garantida a esquecer num sítio qualquer.

**Middleware** é código que envolve o tratamento do pedido. A imagem correcta é uma cebola: o pedido atravessa as camadas de fora para dentro, a função executa no centro, e a resposta atravessa as mesmas camadas de dentro para fora. Cada camada pode inspeccionar, alterar, ou **interromper** — devolvendo resposta sem deixar o pedido prosseguir.

### A ordem — e a inversão que confunde todos

Em `backend-api/main.py`:

```python
# Ordem: path guard primeiro (outermost = last add) — Starlette inverte
app.add_middleware(GlobalRateLimitMiddleware)
app.add_middleware(BodySizeLimitMiddleware)
app.add_middleware(LatencyAlertMiddleware)
app.add_middleware(CatalogCacheHeadersMiddleware)
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(RequestIdMiddleware)
app.add_middleware(PrivilegedPathMiddleware)
```

O comentário avisa: **no Starlette, o último a ser adicionado é o primeiro a ver o pedido.** Cada `add_middleware` envolve tudo o que já existe. Ignorar isto leva a ordens de execução surpreendentes.

A ordem real de travessia de um pedido em produção (incluindo CORS e TrustedHost, adicionados depois no bloco de produção):

```
Pedido
  │
  ▼ 1. CORSMiddleware .................. origem permitida? responde a OPTIONS
  ▼ 2. TrustedHostMiddleware ........... cabeçalho Host é dos nossos?
  ▼ 3. PrivilegedPathMiddleware ........ é /admin, /system ou /health/detail? lockdown activo?
  ▼ 4. RequestIdMiddleware ............. atribui identificador único
  ▼ 5. SecurityHeadersMiddleware ....... (na resposta) cabeçalhos de segurança
  ▼ 6. CatalogCacheHeadersMiddleware ... (na resposta) Cache-Control em catálogo
  ▼ 7. LatencyAlertMiddleware .......... arranca cronómetro
  ▼ 8. BodySizeLimitMiddleware ......... Content-Length aceitável?
  ▼ 9. GlobalRateLimitMiddleware ....... este IP excedeu a quota?
  ▼
Router → dependências (Depends) → função
  │
  ▲ resposta sobe pelas mesmas camadas, em sentido inverso
```

**Porque esta ordem é a correcta.** As verificações mais baratas e mais decisivas vêm primeiro. Rejeitar por origem inválida custa quase nada. Rejeitar um caminho privilegiado antes de tocar na base de dados evita trabalho inútil. O identificador de pedido é atribuído cedo para que tudo o que aconteça depois possa ser correlacionado. E o cronómetro de latência arranca depois das rejeições rápidas, para medir o que interessa — o trabalho real — e não o tempo de dizer "não".

### Camada por camada

**`PrivilegedPathMiddleware`** (`backend-api/core/path_guard.py`) — a fronteira. Duas funções:

*Estado de emergência.* Se `SECURITY_LOCKDOWN=1`, tudo o que seja privilegiado ou mutação pública é suspenso, sobrando apenas as verificações de saúde:

```python
if lockdown_active():
    if path in ("/health", "/health/ready") and request.method == "GET":
        return await call_next(request)
    if path.startswith(_PRIVILEGED_PREFIXES) or any(path.startswith(p) for p in _PUBLIC_MUTATE_PREFIXES):
        return JSONResponse(status_code=503, content={"detail": "SECURITY_LOCKDOWN activo — operações suspensas."})
```

Um interruptor de emergência que se acciona por variável de ambiente e um reinício, sem publicar código. Durante um incidente, isto vale ouro.

*Fronteira permanente.* Em produção final, `/admin`, `/system` e `/health/detail` exigem `privileged_access_ok()` — loopback verdadeiro ou aplicação de secretária com o cabeçalho de porta válido. E note-se: esta verificação existe **também** ao nível de cada rota, via `Depends(admin_must_be_local)`. Duas camadas independentes a proteger a mesma coisa, porque uma rota nova pode nascer sem a dependência, mas nenhuma rota escapa ao middleware.

**`RequestIdMiddleware`** — respeita o identificador enviado pelo cliente ou gera um novo, guarda-o no estado do pedido (para que o tratador de erros e os alertas o possam usar) e devolve-o na resposta. Simples e desproporcionadamente útil.

**`SecurityHeadersMiddleware`** — acrescenta a todas as respostas: `X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`, `Permissions-Policy`, `Cross-Origin-Opener-Policy`, `Cross-Origin-Resource-Policy`; e, só em produção, HSTS e o CSP mínimo `default-src 'none'; frame-ancestors 'none'`. Que uma API JSON declare que não carrega absolutamente nada é a expressão mais pura do princípio do menor privilégio.

**`CatalogCacheHeadersMiddleware`** — acrescenta cache apenas onde é seguro:

```python
if request.method != "GET" or response.status_code != 200:
    return response
...
response.headers.setdefault("Cache-Control", "public, max-age=60, stale-while-revalidate=120")
```

Só `GET`, só `200`, e só em caminhos de catálogo. `stale-while-revalidate=120` é uma jóia pouco conhecida: durante dois minutos após a expiração, a Cloudflare pode servir a versão antiga **imediatamente** enquanto busca a nova em segundo plano. O visitante nunca espera. Note-se `setdefault` e não atribuição: se a rota já tiver decidido a sua política de cache, o middleware não a atropela.

**`LatencyAlertMiddleware`** — cronómetro com alerta:

```python
self.threshold_ms = max(0, int(os.getenv("ALERT_LATENCY_MS") or "2000"))
...
if elapsed_ms >= self.threshold_ms and not request.url.path.startswith("/health"):
    send_alert("Latência elevada", severity="warning", detail={...})
```

Dois cuidados: exclui `/health` (as verificações de saúde são frequentes e, por desenho, tolerantes; alertar sobre elas seria ruído) e envolve o envio do alerta em `try/except`, porque **um sistema de alertas avariado nunca deve derrubar a aplicação**. O detalhe do alerta inclui o identificador do pedido, permitindo saltar directamente para os registos.

**`BodySizeLimitMiddleware`** — assunto da secção seguinte.

**`GlobalRateLimitMiddleware`** — a camada final, delegando em `backend-api/core/rate_limit.py`, que tem três compartimentos:

| Compartimento | Caminhos | Limite por omissão | Variável |
|---|---|---|---|
| `catalog` | Leituras `GET` de `/categorias` e `/catalogo` | 600/min | `RATE_LIMIT_CATALOG_PER_MIN` |
| `admin` | `/admin`, `/system` | 300/min | `RATE_LIMIT_ADMIN_PER_MIN` |
| `global` | Tudo o resto | 120/min | `RATE_LIMIT_GLOBAL_PER_MIN` |

**Porquê compartimentos separados.** Uma pessoa a percorrer o catálogo faz muitos pedidos de leitura em pouco tempo — comportamento normal. Uma pessoa a submeter formulários faz poucos. Um limite único teria de ser generoso o suficiente para o catálogo, tornando-se inútil para os formulários. O comentário no código regista uma lição aprendida:

```python
if path.startswith("/admin") or path.startswith("/system"):
    # Backoffice faz muitas leituras/escritas; 30/min partia o uso normal.
    return "admin", int(os.getenv("RATE_LIMIT_ADMIN_PER_MIN", "300"))
```

**Ponto a vigiar:** `deploy/env.free.example` traz ainda `RATE_LIMIT_ADMIN_PER_MIN=30`, valor anterior a essa lição. Se o backoffice começar a devolver `429 Demasiados pedidos` em uso normal, é este o parâmetro a corrigir no `.env` da máquina.

O armazenamento dos contadores tem degradação graciosa: tenta Redis (partilhado entre processos, correcto) e, se falhar, usa memória local:

```python
def _record_and_check(key: str, max_calls: int, window_seconds: int) -> bool:
    redis_result = _record_and_check_redis(key, max_calls, window_seconds)
    if redis_result is not None:
        return redis_result
    return _record_and_check_memory(key, max_calls, window_seconds)
```

Com quatro processos e memória local, o limite efectivo torna-se quatro vezes maior — imperfeito, mas infinitamente melhor do que deixar de limitar ou falhar todos os pedidos. E `/health/detail` reporta qual dos dois está activo (`"rate_limit": "redis" | "memory"`), para o operador saber em que regime está.

Há ainda dois refinamentos: caminhos isentos (`/health`, `/health/ready`, documentação) e isenção de loopback para `/admin` e `/system`, porque o backoffice a correr na própria máquina não deve ser limitado.

---

## IV.5 O bug histórico do `BodySizeLimitMiddleware`

Esta secção conta um erro real, porque o erro ensina mais do que o código correcto.

### O objectivo legítimo

Um pedido com corpo enorme é um ataque trivial: enviar 500 MB para um formulário e ver o servidor consumir memória até morrer. É uma forma de **DoS** (Denial of Service — Negação de Serviço). Um limite de tamanho é obrigatório.

### A implementação intuitiva — e errada

A primeira versão fazia o que qualquer pessoa faria: ler o corpo e medi-lo. Algo equivalente a:

```python
# VERSÃO ERRADA — não usar
async def dispatch(self, request: Request, call_next):
    body = b""
    async for chunk in request.stream():
        body += chunk
        if len(body) > self.MAX_BYTES:
            return Response("Payload demasiado grande", status_code=413)
    # ... reinjectar o body para o handler poder lê-lo
    return await call_next(request)
```

Parece correcto. Estava a partir o sistema.

### O sintoma

Autenticação no backoffice a falhar com `422 Unprocessable Entity` e uma queixa de que o corpo estava em falta. Sintoma desconcertante por três razões: o pedido tinha corpo (visível nas ferramentas do navegador); o corpo era pequeno (uns 100 bytes de utilizador e password, muito longe do limite); e o `422` vinha da validação do FastAPI, um sítio onde ninguém suspeitaria de um middleware de tamanho.

### A causa

No modelo ASGI, o corpo do pedido não é uma variável — é um **fluxo** entregue por um canal chamado `receive`, em pedaços, e esse canal é de **consumo único**. Como uma fita de máquina de escrever: passa uma vez.

Quando o middleware percorre `request.stream()`, esgota esse canal. Quando, mais tarde, o FastAPI pede o corpo para o validar, o canal já não tem nada. Resultado: o FastAPI conclui que o pedido não trazia corpo e responde `422`.

A reinjecção do corpo é tecnicamente possível, mas com o `BaseHTTPMiddleware` do Starlette — que executa o resto da aplicação numa tarefa separada, comunicando por filas de mensagens — é frágil. Consegue-se fazer funcionar em casos simples e falhar de formas obscuras noutros, e essa fragilidade é precisamente o pior resultado possível: um bug intermitente e difícil de reproduzir.

### A correcção

O ficheiro `backend-api/core/middleware.py` guarda hoje a lição na própria documentação da classe:

```python
class BodySizeLimitMiddleware(BaseHTTPMiddleware):
    """Rejeita bodies demasiado grandes (DoS) via Content-Length.

    Não consumir request.stream() aqui: BaseHTTPMiddleware + re-inject
    do body parte o parsing JSON (login/admin POST → 422 body missing).
    """

    MAX_BYTES = int(__import__("os").getenv("MAX_REQUEST_BODY_BYTES") or str(2 * 1024 * 1024))

    async def dispatch(self, request: Request, call_next):
        cl = request.headers.get("content-length")
        if cl:
            try:
                if int(cl) > self.MAX_BYTES:
                    return Response("Payload demasiado grande", status_code=413)
            except ValueError:
                return Response("Content-Length inválido", status_code=400)
        return await call_next(request)
```

A mudança de perspectiva é elegante: em vez de **medir** o corpo, **ler a declaração** do seu tamanho. O cabeçalho `Content-Length` é metadado — está nos cabeçalhos, já lidos, e consultá-lo não toca no fluxo. Custo: praticamente zero. Efeito colateral: nenhum.

Detalhes que valem a pena:

- Limite por omissão de 2 MiB (`2 * 1024 * 1024`), configurável por `MAX_REQUEST_BODY_BYTES`.
- `413 Payload Too Large` para corpo grande — o código de estado correcto e informativo.
- Um `Content-Length` não numérico gera `400`, não uma excepção. Um atacante que envie `Content-Length: abc` recebe uma rejeição limpa.
- O middleware é **neutro em relação ao fluxo**: não o lê, não o modifica.

### As limitações honestas da correcção

Um pedido enviado em modo *chunked* (transferência em pedaços, sem `Content-Length`) não é verificado por esta camada. Na prática, o uvicorn e a Cloudflare normalizam quase todo o tráfego com `Content-Length`, e o uvicorn tem os seus próprios limites; mas a protecção completa exigiria um middleware ASGI puro que contasse bytes à medida que passam, sem os acumular. É uma melhoria conhecida e registada, não um esquecimento.

### As três lições transferíveis

1. **Middleware não deve consumir o corpo do pedido.** Se precisar de o inspeccionar, deve ser escrito como middleware ASGI puro, envolvendo o canal `receive` de forma transparente, e não com `BaseHTTPMiddleware`.
2. **Ler metadados é preferível a ler dados.** Muitas verificações que parecem exigir o conteúdo bastam-se com cabeçalhos: tamanho, tipo, codificação.
3. **Um sintoma pode estar muito longe da causa.** `422` numa autenticação apontava para validação de campos; o culpado era um middleware de tamanho, três camadas acima. Por isso o comentário ficou no código: para que a próxima pessoa a "optimizar" esta classe leia primeiro o aviso. Um comentário que descreve *o que já falhou* é um comentário que se paga.

---

## IV.6 Endpoints de saúde: `/health`, `/health/ready`, `/health/detail`

Três endereços com três públicos, três níveis de detalhe e três níveis de protecção. A distinção é subtil e frequentemente ignorada, com consequências.

### `/health` — "estás vivo?"

```python
@app.get("/health")
def health_check():
    return build_health(detailed=False)
```

Resposta:

```json
{"status": "online", "version": "..."}
```

Não toca na base de dados. Não faz trabalho. Responde em microssegundos.

**Quem usa.** A verificação de saúde do Docker (`curl -f http://127.0.0.1:8000/health` a cada 30 segundos), os monitores externos (`deploy/uptime_check.py`) e o `curl` de confirmação no fim da publicação.

**Porque é tão pobre de propósito.** É chamado a toda a hora. Se consultasse a base de dados, seríamos nós próprios a gerar carga permanente contra o Supabase — e um Supabase momentaneamente lento faria o Docker concluir que a API está morta e reiniciá-la, transformando uma lentidão passageira numa avaria real. Está isento de limitação de ritmo (`_EXEMPT_PATHS`) e é um dos dois caminhos permitidos durante `SECURITY_LOCKDOWN`.

### `/health/ready` — "estás pronto a trabalhar?"

```python
@app.get("/health/ready")
def health_ready():
    body = build_health(ready=True)
    if not body.get("database"):
        raise HTTPException(status_code=503, detail=body)
    return body
```

Aqui a base de dados **é** testada, e o teste é cuidadosamente defensivo (`backend-api/core/health.py`):

```python
def _db_ping() -> bool:
    try:
        with ThreadPoolExecutor(max_workers=1) as pool:
            fut = pool.submit(lambda: get_db().table("outbox_events").select("id").limit(1).execute())
            fut.result(timeout=_DB_TIMEOUT_SEC)
        return True
    except (FuturesTimeout, Exception):
        try:
            with ThreadPoolExecutor(max_workers=1) as pool:
                fut = pool.submit(_pg_ping)
                return bool(fut.result(timeout=8))
        except (FuturesTimeout, Exception):
            return False
```

Três características notáveis: consulta mínima (`select id limit 1` — não conta linhas, não varre tabelas); tempo limite de dois segundos (uma verificação que fica pendurada é pior do que uma que falha); e um caminho alternativo. O comentário desse caminho alternativo documenta um problema real observado:

```python
def _pg_ping() -> bool:
    """Fallback quando o REST Supabase falha (ex.: CA partida no host) mas o Postgres responde."""
```

Se a camada REST do Supabase falhar por um problema de certificados na máquina, mas o PostgreSQL responder directamente, a API não se declara morta. Distinguir "a base de dados está inacessível" de "um dos caminhos para a base de dados está inacessível" evita uma classe inteira de alarmes falsos.

**A diferença entre `/health` e `/health/ready`** é a distinção clássica entre *liveness* e *readiness*. "Vivo" significa que o processo não está bloqueado — se não estiver, reiniciar resolve. "Pronto" significa que consegue efectivamente servir pedidos — se não estiver, reiniciar não resolve nada (a base de dados continuará em baixo) e o que se deve fazer é parar de lhe enviar tráfego. Confundir os dois produz o pior comportamento possível: reiniciar em ciclo uma aplicação sã porque uma dependência externa está indisponível.

### `/health/detail` — o painel do operador

```python
@app.get(
    "/health/detail",
    dependencies=[Depends(admin_must_be_local), Depends(require_ops)],
)
def health_detail():
    """Detalhe ops — só localhost em produção final (público: /health e /health/ready)."""
    return build_health(detailed=True)
```

Devolve o estado completo do sistema:

| Campo | Significado |
|---|---|
| `env` | Ambiente configurado |
| `database` | Base de dados alcançável |
| `storage` | `private` ou `public` — modo do armazenamento de imagens |
| `rate_limit` | `redis` ou `memory` — que motor de contagem está activo |
| `api_key_required` | Se as chaves são exigidas |
| `contact_email_notify` | Se há destinatário de notificações configurado |
| `smtp_circuit` | `open` ou `closed` — estado do disjuntor de correio |
| `email_worker` | Se o trabalhador está vivo e quando foi o último ciclo |
| `outbox_pending` | Quantos eventos aguardam processamento |
| `feature_flags` | Estado dos interruptores de funcionalidade |
| `sentry`, `axiom` | **Booleanos** — se estão configurados, nunca os valores |

O `smtp_circuit` merece explicação: um **disjuntor** (*circuit breaker*) é um padrão que, após várias falhas consecutivas de um serviço externo, deixa de tentar durante um período. Em vez de cada email ficar 30 segundos à espera de um servidor de correio morto, falha imediatamente e volta a tentar mais tarde. `open` significa "a proteger-se"; `closed` significa "a funcionar normalmente".

Duas notas de engenharia. Primeiro, `outbox_pending` é guardado em cache por 30 segundos, porque contar linhas é caro:

```python
_OUTBOX_CACHE_SEC = 30
```

Segundo, e mais importante: **este endereço é triplamente protegido** — pelo middleware de caminho privilegiado, por `admin_must_be_local`, e por `require_ops` (que exige uma chave de operações). **Porquê:** a lista acima é um manual de reconhecimento para um atacante. Saber que o armazenamento está público, ou que o limite de ritmo caiu para memória, ou que o disjuntor de correio está aberto, é saber exactamente onde bater. Repare-se também que `sentry` e `axiom` são booleanos e não os valores das credenciais — o operador precisa de saber *se* a observabilidade está ligada, nunca *com que chave*.

---

## IV.7 Trabalhadores (email, outbox) e `RUN_EMBEDDED_WORKERS`

### O problema

Certas operações são lentas e não fiáveis: enviar um email pode demorar segundos ou falhar. Se o formulário de contacto esperasse pelo envio, o visitante ficaria a olhar para uma roda a girar; e se o servidor de correio estivesse em baixo, uma mensagem legítima seria perdida com um erro.

### A solução: o padrão outbox

A ideia é separar "registar a intenção" de "executar a acção":

1. O pedido guarda a mensagem na base de dados **e** insere um evento numa tabela `outbox_events` com estado `pending`. Ambas as escritas na mesma transacção.
2. Responde imediatamente ao visitante: recebido.
3. Um processo separado lê os eventos pendentes, executa-os e marca-os como concluídos.

Vantagens: a resposta é rápida; se o correio estiver em baixo, o evento permanece pendente e será tentado mais tarde; e não existe o cenário desastroso de "a mensagem foi gravada mas o email não saiu, e ninguém sabe" — porque o registo da intenção está na base de dados, contável (é o `outbox_pending` de IV.6).

Na Diomika isto é coordenado por *sagas* (`backend-api/core/saga/contact_saga.py`, `orcamento_saga.py`), que sequenciam os passos e sabem compensar quando um falha.

### Os três laços de execução

Em `backend-api/core/background_workers.py`:

**Trabalhador de email** — consulta o correio por **IMAP** (Internet Message Access Protocol — protocolo de acesso a caixas de correio) para detectar respostas de clientes e associá-las ao histórico da mensagem original:

```python
def _email_loop() -> None:
    from workers.email_worker import process_inbox
    poll = int(os.getenv("EMAIL_POLL_SECONDS", "30"))
    while not _stop.is_set():
        try:
            process_inbox()
        except Exception as exc:
            logger.error("Email worker: %s", exc)
        _stop.wait(poll)
```

**Trabalhador de outbox** — processa os eventos pendentes:

```python
n = asyncio.run(run_once())
if n:
    logger.info("Outbox: %s evento(s) processado(s)", n)
```

**Laço de manutenção** — três tarefas de limpeza em cadências diferentes:

```python
poll = int(os.getenv("SAGA_SWEEP_SECONDS", "300"))
retention_every = max(1, int(os.getenv("RETENTION_SWEEP_CYCLES", "12")))  # ~1h se poll=300
```

A cada 5 minutos: recuperar *sagas* interrompidas a meio (uma *saga* "zombie" é uma que começou e nunca terminou, tipicamente por reinício no momento errado) e apagar chaves de idempotência expiradas. A cada 12 ciclos, aproximadamente uma hora: `purge_expired_pii()`, que apaga dados pessoais fora do prazo de retenção — **PII** significa Personally Identifiable Information, Informação Pessoalmente Identificável. Cumprimento do RGPD implementado como rotina automática, não como promessa.

Três padrões repetem-se nos três laços, e todos são deliberados: cada iteração está envolvida em `try/except`, porque uma falha isolada não deve matar o laço; a espera usa `_stop.wait(poll)` em vez de `time.sleep(poll)`, para que o encerramento seja imediato em vez de esperar até 5 minutos; e o registo só acontece quando há trabalho feito (`if n:`), para não encher os registos com "nada a fazer" a cada 30 segundos.

### `RUN_EMBEDDED_WORKERS`

```python
def should_run_embedded() -> bool:
    explicit = (os.getenv("RUN_EMBEDDED_WORKERS") or "").strip().lower()
    if explicit in ("0", "false", "no"):
        return False
    if explicit in ("1", "true", "yes"):
        return True
    from core.config import get_settings
    return get_settings().is_production
```

Três estados: explicitamente desligado, explicitamente ligado, ou — se nada for dito — ligado em produção e desligado em desenvolvimento. Este último ponto é uma cortesia importante: ninguém quer que a máquina de desenvolvimento comece a consultar caixas de correio reais só porque se lançou a API para testar uma rota.

Quando activo, os laços correm como *threads* dentro do processo da API:

```python
t = threading.Thread(target=target, name=f"diomika-{name}", daemon=True)
t.start()
```

`daemon=True` significa que estas *threads* não impedem o processo de terminar. Os nomes (`diomika-email`, `diomika-outbox`, `diomika-saga-maint`) aparecem nos diagnósticos e facilitam a vida a quem investiga.

**Porquê embutido na e2-micro.** Cada contentor separado carregaria o seu interpretador Python, as suas bibliotecas, a sua ligação à base de dados — facilmente 150 a 250 MB cada. Com 1 GB total, três contentores extra não caberiam. Como *threads* dentro do processo existente, o custo marginal é de alguns megabytes.

**Custo desta escolha, dito com clareza.** Perde-se isolamento: um erro grave num trabalhador pode afectar a API. Perde-se a possibilidade de escalar um trabalhador independentemente. E há um ponto operacional a vigiar: o `Dockerfile` lança `uvicorn --workers 4`, o que significa quatro processos; com `RUN_EMBEDDED_WORKERS=true`, **cada** um deles lança o seu conjunto de laços, resultando em quatro consultas de correio em paralelo. Na prática, as transições de estado dos eventos na base de dados e as chaves de idempotência impedem o processamento duplicado, mas há trabalho desperdiçado e é uma razão adicional para preferir trabalhadores dedicados quando o sistema crescer. É precisamente essa a forma do `docker-compose.yml` da raiz (II.8), e é o que `deploy/env.free.example` sinaliza:

```
RUN_EMBEDDED_WORKERS=true
# Com docker-compose.scale.yml usar false + workers dedicados
```

### Como se sabe que estão vivos

Cada trabalhador escreve um ficheiro de pulsação, lido depois por `/health/detail` (`backend-api/core/health.py`):

```python
def _worker_status() -> dict:
    state_file = BACKEND_ROOT / ".email_worker_state.json"
    worker_file = BACKEND_ROOT / ".email_worker_heartbeat.json"
    ...
    if last:
        last_dt = datetime.fromisoformat(last.replace("Z", "+00:00"))
        age = (datetime.now(timezone.utc) - last_dt).total_seconds()
        status["running"] = age < 120
```

Regra simples e robusta: se a última pulsação tem menos de 120 segundos e o intervalo é de 30, está a correr. Se tem mais, algo está preso. Um trabalhador silenciosamente morto é uma das avarias mais perniciosas que existem — tudo parece bem, mas os emails deixaram de sair — e esta verificação existe exactamente para a tornar visível.

---

## IV.8 Schema-driven (Pydantic → SQL/UI) em linguagem simples

### O problema

Acrescentar um campo a um formulário de gestão implica, num sistema convencional, tocar em quatro lugares:

1. Criar a coluna na base de dados (SQL).
2. Acrescentar o campo ao modelo de validação da API.
3. Acrescentar o campo ao formulário do backoffice, com etiqueta, tipo de controlo e obrigatoriedade.
4. Actualizar a documentação.

Quatro lugares significa quatro oportunidades de esquecer um. E o modo de falha é subtil: o formulário mostra o campo, o utilizador preenche, a API aceita, e o valor perde-se porque a coluna não existe. Ou existe a coluna e a API rejeita o campo. Erros que aparecem semanas depois, difíceis de diagnosticar.

### A abordagem: uma fonte única de verdade

A Diomika inverte isto. Define-se a estrutura **uma vez**, em Python, com Pydantic, no ficheiro `backend-api/models/schemas.py`, num registo chamado `TABLE_MAP`. Todo o resto é **derivado**.

```
backend-api/models/schemas.py  (TABLE_MAP — fonte única)
        │
        ├──► validação da API .......... automática (Pydantic)
        ├──► colunas SQL ............... backend-api/core/schema_engine.py
        ├──► formulários do backoffice .. backend-api/models/ui_schema.py
        └──► documentação OpenAPI ....... automática (FastAPI)
```

### Ramo 1 — de tipo Python para tipo PostgreSQL

Em `backend-api/core/schema_engine.py`:

```python
def _pytype_to_sql(field_name: str, annotation) -> str:
    if field_name == "id":
        return "uuid"
    origin = get_origin(annotation)
    if origin is list or origin is dict:
        return "jsonb"
    ...
    mapping = {
        "str": "text",
        "int": "integer",
        "bool": "boolean",
        "UUID": "uuid",
        "float": "double precision",
    }
    return mapping.get(name, "text")
```

E a geração da instrução de criação:

```python
if fname == "id":
    lines.append(f"{fname} {sql_type} PRIMARY KEY DEFAULT gen_random_uuid()")
```

Convenções embutidas: um campo chamado `id` é sempre chave primária do tipo **UUID** (Universally Unique Identifier — Identificador Único Universal, um número de 128 bits gerado de forma a não colidir com nenhum outro no mundo, sem coordenação central); listas e dicionários viram `jsonb`, o tipo do PostgreSQL para dados estruturados com capacidade de indexação; tipos desconhecidos degradam para `text` em vez de falhar.

**Porque UUID e não um número sequencial.** Um identificador `1, 2, 3...` diz ao mundo quantos registos existem e permite adivinhar endereços de registos vizinhos — a base dos ataques chamados **IDOR** (Insecure Direct Object Reference — Referência Directa Insegura a Objecto). Existe até um teste dedicado, `backend-api/tests/test_idor.py`.

### Ramo 2 — do mesmo modelo para o formulário

Em `backend-api/models/ui_schema.py`, o mesmo modelo Pydantic é interrogado para decidir como desenhar cada campo:

```python
def field_widget(field: FieldInfo, field_name: str) -> str:
    extra = field_extra(field)
    if extra.get("ui_widget"):
        return extra["ui_widget"]
    if field_name in ("imagem", "imagem_capa"):
        return "image"
    if field_name == "galeria":
        return "multi_image"
    if field_name == "dimensoes":
        return "dimensions"
    if field_name == "mensagem":
        return "textarea"
    if field_name.startswith("id_"):
        return "relation"
    ...
```

Um campo chamado `imagem` recebe um carregador de imagens; `galeria` recebe um carregador múltiplo; qualquer campo que comece por `id_` é tratado como referência a outra tabela e recebe um selector com as opções correspondentes; um campo `mensagem` recebe uma área de texto grande.

E há esconderijos por omissão:

```python
hidden_defaults = {"id", "slug", "barcode_url", "created_at", "updated_at", "last_sender"}
```

Campos gerados pelo sistema não aparecem no formulário — ninguém deve escrever à mão um `created_at`. Quando a convenção não serve, sobrepõe-se explicitamente com `ui_widget`, `ui_label`, `ui_hidden`, `ui_readonly`, `ui_required`.

O backoffice consome isto por HTTP, em `backend-api/routes/system.py`:

```python
@router.get("/schema/form/{table_name}")
def form_schema(request: Request, table_name: str, role=Depends(require_admin)):
    if table_name not in TABLE_MAP or table_name in CRUD_INFRA_BLOCKED:
```

O que significa que **o backoffice não sabe** que campos existem — pergunta. Acrescentar um campo em `schemas.py` fá-lo aparecer no formulário sem tocar numa linha do código do backoffice. E `CRUD_INFRA_BLOCKED` garante que tabelas de infra-estrutura (chaves de idempotência, eventos de outbox, registos de auditoria) nunca são editáveis pela interface genérica.

### Ramo 3 — detecção de divergência

Não basta gerar; é preciso saber quando o código e a base de dados divergiram. Daí a fotografia do esquema:

```python
SNAPSHOT_PATH = Path(__file__).resolve().parent.parent / ".schema_snapshot.json"
```

E as funções `build_schema_snapshot` e `snapshot_hash`. Um **hash** é um resumo curto de conteúdo: se uma única letra mudar, o resumo muda. Comparar resumos é a forma mais rápida de responder a "isto mudou?".

Isto alimenta três operações em `backend-api/routes/system.py`:

- `GET /system/schema/status` — "há divergências?" sem alterar nada.
- `POST /system/schema/sync?dry_run=true` — "o que farias?" — mostra o SQL sem executar.
- `POST /system/schema/sync` — aplica.

E no arranque da API, `bootstrap_database_schema(logger)` verifica automaticamente (com o interruptor `SCHEMA_BOOTSTRAP=0` para o desligar).

**Porquê `dry_run` primeiro.** Migrações automáticas de esquema são poderosas e perigosas. Poder ver exactamente o SQL que vai ser executado, antes de o executar, é a diferença entre uma ferramenta útil e uma ferramenta assustadora.

### O balanço honesto

**O que se ganha.** Um único lugar para mudar. Coerência garantida entre validação, base de dados e interface. Formulários que aparecem sozinhos. Divergências detectadas em vez de descobertas. Menos código no total — e código que não existe não tem defeitos.

**O que se perde.** A camada de derivação é ela própria código não trivial, que exige compreensão: quem chegar e procurar o formulário da tabela X não o encontra, porque não existe. É preciso saber que o formulário é derivado. As convenções (`imagem` → carregador de imagens, `id_` → relação) são poderosas mas implícitas, e uma convenção que se ignora é uma surpresa. E a geração automática cobre os casos comuns; o incomum precisa de intervenção manual — daí `deploy/generated_catalog_infra.sql` e `deploy/supabase_pre_deploy.sql`, onde vivem índices, políticas RLS e restrições que não se derivam de tipos Python.

É um compromisso consciente: mais abstracção em troca de menos repetição, com a abstracção documentada — nesta secção, e nas docstrings dos ficheiros envolvidos.

---

# Encerramento das Partes II a IV

## Os dez princípios que atravessam tudo

Se houvesse que resumir estes três capítulos em princípios de engenharia, seriam estes — e cada um pode ser verificado no código:

1. **Falhar fechado.** Em dúvida, negar. `validate_startup()` não deixa arrancar mal configurado; `TrustedHostMiddleware` recebe `["invalid.invalid"]` em vez de aceitar tudo; o Turnstile recusa em produção se não tiver segredo.
2. **Falhar cedo e alto.** Erros de configuração aparecem no arranque ou no *build*, com mensagem que diz o que corrigir — não em produção, com clientes a ver.
3. **Defesa em camadas.** A porta 8000 está fechada pela *firewall*, pelo Docker e pela ausência de túnel para ela. Os caminhos administrativos estão protegidos pelo middleware e pelas dependências de rota.
4. **Menor privilégio.** A loja tem apenas chaves públicas. A API tem CSP `default-src 'none'`. A página renuncia a câmara, microfone e localização.
5. **Confiar em metadados para contar, nunca para autorizar.** `X-Forwarded-For` serve para limites de ritmo; para autorização, só o endereço TCP real.
6. **Cache em todas as camadas seguras.** Memória do servidor, cabeçalhos para o *edge*, nomes com impressão digital para o navegador.
7. **Degradação graciosa.** Redis em baixo? Contadores em memória. REST do Supabase em baixo? PostgreSQL directo. API em baixo? A loja continua a ler catálogo.
8. **Observabilidade proporcional ao risco.** `/health` é público e pobre; `/health/detail` é rico e triplamente protegido. Segredos aparecem sempre como booleanos.
9. **Uma fonte de verdade.** O esquema define base de dados, validação e interface. O catálogo define rotas, vitrine e formulários.
10. **Documentar o que já falhou.** O comentário em `BodySizeLimitMiddleware` e o comentário sobre `X-Forwarded-For` valem mais do que qualquer descrição do funcionamento normal.

## Para onde ir a seguir

| Tema | Onde |
|---|---|
| Autenticação, papéis, MFA, RLS, auditoria, gestão de segredos | Parte V — `deploy/relatorio_parts/part_03_seguranca_dados.md` |
| Modelo de dados, sagas, idempotência, retenção, armazenamento | Parte VI — mesmo ficheiro |
| Observabilidade, backoffice de secretária, publicação, decisões, perguntas frequentes | Partes VII a XII — `deploy/relatorio_parts/part_04_ops_decisoes.md` |
| Fundamentos da web e glossário A–Z | Parte I — `deploy/relatorio_parts/part_01_fundamentos.md` |
| Escalar para além da e2-micro | `deploy/SCALE.md` |
| Rotina de operação e incidentes | `deploy/OPS.md` |
| A pilha de custo zero em resumo | `deploy/FREE_STACK.md` |

**Recordatório final de segurança:** nada neste documento é um segredo. Todos os nomes de variáveis aqui citados — `API_SECRET_KEY`, `SUPABASE_KEY`, `TURNSTILE_SECRET_KEY`, `CLOUDFLARE_TUNNEL_TOKEN`, `DIOMIKA_DESKTOP_GATE`, `MAIL_PASSWORD` — aparecem sem valor, e devem continuar assim. Os valores vivem no ficheiro `.env` da máquina e no painel da Cloudflare Pages, nunca no repositório, nunca num relatório, nunca numa mensagem.
