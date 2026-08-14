# Relatório Técnico Diomika — Parte 03

## Segurança (camada a camada) e Dados (Supabase / PostgreSQL / Storage)

> **Como ler este capítulo.** Está escrito para quem não vive dentro de siglas. Cada sigla é
> expandida na primeira vez que aparece (e muitas vezes repetida, de propósito). Cada afirmação
> técnica aponta para o ficheiro real do repositório onde o comportamento está implementado, para
> que qualquer pessoa possa confirmar. **Nenhum valor secreto real aparece neste documento** — nem
> passwords, nem chaves de interface de programação de aplicações (API, *Application Programming
> Interface*), nem tokens. Onde faria sentido mostrar um segredo, mostra-se apenas o *nome* da
> variável de ambiente e um marcador do tipo `<valor-secreto>`.

---

# Parte V — Segurança (camada a camada)

## V.1 Modelo de ameaça (o que queremos impedir)

Antes de falar de firewalls, *hashes* ou políticas de base de dados, é preciso responder a três
perguntas simples. Um "modelo de ameaça" (*threat model*) é exactamente isso: uma lista honesta de
respostas a estas perguntas.

1. **O que temos de valioso?** (activos)
2. **Quem pode querer atacá-lo, e com que capacidades?** (adversários)
3. **O que estamos explicitamente a decidir *não* defender?** (limites do âmbito)

### V.1.1 Activos a proteger

| Activo | Onde vive | Porque é sensível |
|---|---|---|
| Catálogo (categorias, modelos, cores, referências) | PostgreSQL no Supabase, tabelas `categories`, `modelos_almofadas`, `modelos_assentos`, `almofada`, `assento`, `modelo_cores`, `paletas_cores` | É o produto comercial visível. Uma alteração maliciosa (preços, imagens, texto) é um problema de reputação imediato. |
| Pedidos de orçamento | Tabela `pedidos_orcamento` | Contém **dados pessoais**: nome, email, contacto telefónico, empresa, observações. Cai no Regulamento Geral sobre a Protecção de Dados (RGPD). |
| Mensagens de contacto | Tabela `contact_messages` e histórico `message_history` | Idem: dados pessoais e conteúdo de comunicação privada. |
| Encomendas internas | Tabela `encomendas_internas` | Informação comercial interna (o que se produz, para quem, em que quantidades). |
| Credenciais do backoffice | Ficheiro local `backend-api/data/admin_users.json` | Quem as tiver controla o backoffice inteiro. |
| Chave de serviço do Supabase | Variável de ambiente `SUPABASE_KEY`, apenas no servidor | **Ignora todas as políticas de segurança da base de dados** (ver VI.3). É o activo mais perigoso do sistema. |
| Segredo da API | Variável `API_SECRET_KEY` | Serve de chave de máquina *e* de raiz criptográfica das sessões do backoffice (ver V.7). |
| Gate da aplicação de secretária | Variável `DIOMIKA_DESKTOP_GATE` | Filtro de fronteira para `/admin` e `/system` (ver V.4). |
| Imagens de produto e códigos de barras | Supabase Storage (*buckets* `product-images` e `barcodes`) ou Cloudflare R2 | Propriedade intelectual; e escrita não autorizada permitiria injectar conteúdo. |

### V.1.2 Adversários considerados

* **Robôs de varrimento automático (*scanners*).** Percorrem a internet a testar `/admin`,
  `/wp-login.php`, `/.env`, `/actuator/health`. Não sabem nada sobre a Diomika; testam padrões.
  São a maior fatia do tráfego hostil de qualquer sítio público.
* **Spammers de formulários.** Enviam milhares de submissões automáticas para o formulário de
  contacto e de orçamento, seja para publicidade, seja para envenenar a caixa de correio.
* **Atacante oportunista com alguma competência.** Encontra o domínio da API, tenta enumerar
  endpoints, tenta força bruta no login, tenta ler pedidos de outra pessoa mudando um identificador
  no endereço (ataque conhecido como IDOR, *Insecure Direct Object Reference* — referência directa
  insegura a objectos).
* **Concorrente interessado no catálogo e nos clientes.** Objectivo: extrair a lista de modelos, de
  preços de referência e, sobretudo, a lista de contactos que pediram orçamento.
* **Insider com credenciais válidas mas âmbito limitado.** Alguém que legitimamente gere o catálogo
  não deve poder ler mensagens de clientes nem apagar registos definitivamente.
* **Rede não confiável entre cliente e servidor.** Wi-Fi de café, operador móvel, resolvedor de
  nomes (DNS, *Domain Name System*) manipulado. Daí a insistência em Transport Layer Security (TLS,
  a camada de cifra que está por baixo do `https://`) e em HTTP Strict Transport Security (ver V.17).

### V.1.3 O que queremos impedir, concretamente

1. **Leitura não autorizada de dados pessoais** — ninguém sem sessão válida lê `pedidos_orcamento`
   nem `contact_messages`, nem directamente na base de dados (políticas RLS, ver VI.4), nem através
   da API (verificações de papel/role, ver V.11), nem adivinhando identificadores
   (testes em `backend-api/tests/test_idor.py`).
2. **Escrita não autorizada no catálogo** — qualquer mutação exige autenticação e um papel com
   permissão para aquela tabela.
3. **Acesso à superfície administrativa a partir da internet aberta** — `/admin`, `/system` e
   `/health/detail` só respondem a partir de `localhost` na própria máquina ou da aplicação de
   secretária autorizada (ver V.4 e V.5), com a mesma regra espelhada na *firewall* da Cloudflare
   (ver V.3).
4. **Força bruta de password** — limitação de ritmo por endereço IP *e* por nome de utilizador,
   bloqueio temporário de conta, alertas (ver V.9).
5. **Roubo de sessão de longa duração** — as sessões duram minutos, não dias, e são revogáveis do
   lado do servidor (ver V.7).
6. **Spam automatizado nos formulários públicos** — Turnstile, campo-armadilha (*honeypot*),
   limitação de ritmo e chave de idempotência (ver V.15).
7. **Exfiltração através da chave de serviço** — a chave que ignora as políticas da base de dados
   nunca sai do servidor; o *frontend* recebe apenas a chave anónima (ver VI.3).
8. **Falsificação de pedidos do lado do servidor (SSRF)** — o servidor nunca busca uma URL
   arbitrária escolhida por terceiros (ver V.12).
9. **Ataques clássicos de navegador** — *clickjacking*, adivinhação de tipo de conteúdo (*MIME
   sniffing*), fuga de *referrer*, execução de scripts de terceiros (ver V.17).
10. **Negação de serviço barata** — corpos de pedido gigantes e rajadas de pedidos são cortados
    antes de chegarem à lógica de negócio (ver V.14).

### V.1.4 O que está fora do âmbito (dito às claras)

Um modelo de ameaça que promete tudo não vale nada. A Diomika **não** está desenhada para resistir a:

* um **actor estatal** com capacidade de interceptar tráfego cifrado ou comprometer a Cloudflare;
* **acesso físico** à máquina do operador (se alguém se senta ao computador desbloqueado com o
  backoffice aberto, está dentro);
* um **ataque à cadeia de fornecimento** de dependências (um pacote de Python ou Node comprometido);
* **engenharia social** contra o operador (se a password for entregue ao telefone, nenhuma camada
  técnica ajuda).

O que se faz em relação a estes é *reduzir o dano*: sessões curtas, registo de auditoria
(`admin_audit_log`), alertas em acções sensíveis e um interruptor de emergência global (ver V.16).

---

## V.2 Defense in depth (defesa em profundidade) — conceito

"Defesa em profundidade" é a ideia de que **nenhuma camada tem de estar certa para o sistema estar
seguro** — todas têm de estar erradas ao mesmo tempo para o sistema cair. A metáfora clássica é o
castelo: fosso, muralha exterior, muralha interior, portas com guardas, e a sala do tesouro
trancada. Um invasor que salte o fosso ainda não tem nada.

O oposto — e o erro mais comum em projectos pequenos — é a "casca de ovo": uma única verificação
forte à entrada e, depois dela, confiança total. Basta uma falha e tudo está exposto.

### V.2.1 As camadas concretas do Diomika, de fora para dentro

```
Internet
   │
   ├─ 1. Cloudflare: DNS, TLS estrito, HTTPS obrigatório, TLS mínimo 1.2,
   │     nível de segurança "high", verificação de navegador, regras de firewall
   │     (deploy/cloudflare/waf_rules.json)
   │
   ├─ 2. Cloudflare Tunnel: a máquina virtual não tem portas de entrada abertas.
   │     O túnel é estabelecido de dentro para fora — não há porta 8000 exposta ao mundo.
   │
   ├─ 3. TrustedHostMiddleware: rejeita pedidos cujo cabeçalho Host não esteja
   │     em ALLOWED_HOSTS (backend-api/main.py, linhas 101-104; "fail-closed":
   │     sem lista, a lista passa a ["invalid.invalid"] e rejeita tudo)
   │
   ├─ 4. PrivilegedPathMiddleware: /admin, /system, /health/detail só passam com
   │     acesso privilegiado válido; e o interruptor SECURITY_LOCKDOWN
   │     (backend-api/core/path_guard.py)
   │
   ├─ 5. GlobalRateLimitMiddleware + BodySizeLimitMiddleware: ritmo e tamanho
   │     (backend-api/core/rate_limit.py, backend-api/core/middleware.py)
   │
   ├─ 6. Autenticação: sessão Bearer (dms1.…) ou chave de máquina X-API-Key
   │     (backend-api/core/auth.py)
   │
   ├─ 7. Autorização por papel × tabela × acção (mesmo ficheiro: assert_table_action,
   │     role_can_access_table, CRUD_INFRA_BLOCKED, SENSITIVE_BUSINESS_TABLES)
   │
   ├─ 8. Validação de entrada com Pydantic (limites de comprimento, tipos, email,
   │     normalização de texto em backend-api/core/text_safe.py)
   │
   ├─ 9. PostgreSQL com Row Level Security activo e políticas explícitas
   │     (deploy/supabase_pre_deploy.sql)
   │
   └─ 10. Storage privado: leitura só por URL assinada com validade curta
         (backend-api/utils/storage.py)
```

### V.2.2 Dois princípios que atravessam todas as camadas

**Falhar fechado (*fail-closed*).** Quando algo está em falta ou avariado, a resposta é *negar*, não
*permitir*. Exemplos reais no código:

* sem `ALLOWED_HOSTS` configurado em produção, a lista de anfitriões aceitáveis torna-se
  `["invalid.invalid"]` — ou seja, ninguém entra (`backend-api/main.py`);
* sem nenhuma chave de API configurada, os endpoints protegidos respondem `503` em vez de abrir
  (`backend-api/core/auth.py`, `require_api_key`);
* com *storage* privado em produção final, se não for possível gerar uma URL assinada, o código
  **levanta erro** em vez de cair para uma URL pública
  (`backend-api/utils/storage.py`, `resolve_delivery_url`);
* se o Redis for obrigatório e não existir, as sessões de administração recusam-se a funcionar
  (`backend-api/core/session_tokens.py`, `_redis_required`).

**Ordem dos middlewares (detalhe subtil mas importante).** No Starlette/FastAPI, o middleware
adicionado **por último** é o **mais exterior**, ou seja, o primeiro a ver o pedido. Em
`backend-api/main.py` (linhas 93-100) a ordem de adição é:

```python
app.add_middleware(GlobalRateLimitMiddleware)
app.add_middleware(BodySizeLimitMiddleware)
app.add_middleware(LatencyAlertMiddleware)
app.add_middleware(CatalogCacheHeadersMiddleware)
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(RequestIdMiddleware)
app.add_middleware(PrivilegedPathMiddleware)   # último a adicionar = primeiro a executar
```

Portanto `PrivilegedPathMiddleware` é a **primeira** barreira aplicacional: um pedido bloqueado ali
nunca chega ao *router*, nunca toca na base de dados e quase não consome recursos. O comentário no
próprio ficheiro documenta esta inversão, precisamente porque é o tipo de detalhe que se esquece
seis meses depois.

---

## V.3 Cloudflare WAF (Web Application Firewall) — o que é; regra `/admin` sem header

### V.3.1 O que é um WAF

WAF quer dizer *Web Application Firewall* — "firewall de aplicação web". Uma firewall clássica de
rede decide com base em endereços e portas: "deixa passar tráfego para a porta 443, bloqueia a
porta 22". Um WAF trabalha uma camada acima: **percebe HTTP** e decide com base no *conteúdo* do
pedido — caminho da URL, cabeçalhos, método, país de origem, reputação do endereço IP, corpo do
pedido.

A vantagem prática é que o filtro corre **na rede da Cloudflare**, em centenas de localizações, e
não na máquina virtual da Diomika. Um pedido bloqueado no WAF nunca atravessa o túnel, nunca chega
ao Python, não consome memória nem processador do servidor, e não aparece nos registos da aplicação.
É a camada mais "barata" de todas.

### V.3.2 Configuração de zona declarada em `deploy/cloudflare/waf_rules.json`

```json
"zone_settings": {
  "ssl": "strict",
  "always_use_https": "on",
  "min_tls_version": "1.2",
  "security_level": "high",
  "browser_check": "on"
}
```

Tradução, item por item:

* **`ssl: strict`** — a ligação entre a Cloudflare e a origem (a máquina virtual) também é cifrada
  *e* o certificado é validado. O modo "flexible", muito comum e muito perigoso, cifraria apenas
  entre o visitante e a Cloudflare, deixando o resto do caminho em texto simples.
* **`always_use_https: on`** — qualquer pedido em `http://` recebe um redireccionamento para
  `https://`. É o complemento do cabeçalho HSTS descrito em V.17.
* **`min_tls_version: 1.2`** — versões antigas de TLS (1.0 e 1.1) têm fragilidades conhecidas e
  são recusadas.
* **`security_level: high`** — a Cloudflare aplica desafios mais agressivos a endereços IP com má
  reputação.
* **`browser_check: on`** — heurísticas que detectam clientes que se fazem passar por navegadores
  sem o ser.

### V.3.3 Regra 1 — bloquear pedidos sem *User-Agent*

```json
{
  "name": "block-empty-ua",
  "expression": "(http.user_agent eq \"\")",
  "action": "block"
}
```

O cabeçalho `User-Agent` é a "assinatura" que qualquer navegador envia a dizer o que é. Navegadores
reais enviam-no sempre. Ferramentas automáticas mal configuradas enviam-no vazio. Esta regra não
para um atacante competente (basta-lhe inventar um `User-Agent`), mas elimina de graça uma fatia
enorme de ruído automatizado. É exactamente o tipo de regra que se aceita por ter custo zero.

### V.3.4 Regra 2 — `/admin` e `/system` só com o cabeçalho do backoffice

```json
{
  "name": "block-admin-system-except-desktop",
  "expression": "(http.request.uri.path contains \"/admin\" or http.request.uri.path contains \"/system\") and not any(http.request.headers[\"x-diomika-desktop\"][*] eq \"REPLACE_WITH_DIOMIKA_DESKTOP_GATE\")",
  "action": "block"
}
```

Leitura da expressão em português corrido: *"se o caminho do pedido contiver `/admin` ou `/system`,
**e** nenhum dos valores do cabeçalho `x-diomika-desktop` for igual ao segredo esperado, então
bloqueia."*

Três notas de leitura:

* `http.request.headers["x-diomika-desktop"][*]` é uma **lista**, porque em HTTP o mesmo cabeçalho
  pode aparecer repetido. `any(... eq ...)` significa "algum dos valores é igual a". O `not any(...)`
  cobre também o caso em que o cabeçalho simplesmente não existe (lista vazia → nenhum valor
  corresponde → `any` é falso → `not any` é verdadeiro → bloqueia). Isto é *fail-closed* na
  linguagem de expressões da Cloudflare.
* `REPLACE_WITH_DIOMIKA_DESKTOP_GATE` é um **marcador**, não um segredo. O ficheiro versionado no
  repositório nunca contém o valor real: quem aplica as regras substitui o marcador pelo conteúdo de
  `DIOMIKA_DESKTOP_GATE` no momento de configurar a zona. É por isso que este ficheiro pode viver no
  Git sem risco.
* A regra usa `contains` e não `starts_with`. É deliberadamente generosa: apanha `/admin`,
  `/admin/auth/login`, `/api/admin/...`, `/x/system/y`. Em segurança, um filtro largo demais que
  bloqueia é melhor do que um filtro exacto que deixa passar uma variante.

### V.3.5 Porque é que isto **não** dispensa a verificação na API

O WAF é um filtro de rede: só vê o que passa pela Cloudflare. Se algum dia a origem ficasse
acessível por outro caminho (um endereço IP directo, um túnel de teste, uma configuração temporária
mal fechada), o WAF simplesmente não estaria no caminho. Por isso **a mesma regra é reimplementada
na aplicação**, em `backend-api/core/local_only.py` e `backend-api/core/path_guard.py`. A Cloudflare
é a conveniência; a API é a garantia. Este espelhamento intencional é o exemplo mais puro de
V.2 neste projecto.

---

## V.4 O *gate* de secretária `X-Diomika-Desktop`

### V.4.1 O que é, afinal, um cabeçalho HTTP

O Hypertext Transfer Protocol (HTTP) é o protocolo que os navegadores usam para falar com
servidores. Um pedido HTTP tem três partes:

```
POST /admin/auth/login HTTP/1.1          ← linha de pedido: método, caminho, versão
Host: api.diomika.com                     ┐
Content-Type: application/json            │ cabeçalhos (headers): pares nome: valor
Authorization: Bearer dms1.<...>          │
X-Diomika-Desktop: <valor-secreto>        ┘
                                          ← linha vazia separa cabeçalhos do corpo
{"username": "...", "password": "..."}    ← corpo (body)
```

Os cabeçalhos são **metadados**: não são o conteúdo do pedido, são informação *sobre* o pedido.
Alguns são padronizados (`Host`, `Content-Type`, `Authorization`); qualquer aplicação pode inventar
os seus, e a convenção histórica é começá-los por `X-` (de "extensão"). `X-Diomika-Desktop` é um
cabeçalho inventado para este projecto, e o seu único significado é: *"este pedido vem da aplicação
de secretária oficial da Diomika"*.

Detalhe prático: em HTTP os nomes de cabeçalhos **não distinguem maiúsculas de minúsculas**. É por
isso que o código Python procura `x-diomika-desktop` em minúsculas
(`backend-api/core/local_only.py`, constante `_DESKTOP_HEADER`) e o Electron escreve
`headers['x-diomika-desktop']`, enquanto a documentação e o WAF podem escrever
`X-Diomika-Desktop`. É o mesmo cabeçalho.

### V.4.2 `DIOMIKA_DESKTOP_GATE`

É a variável de ambiente que guarda o segredo partilhado. Documentada em `.env.example`:

```
# DIOMIKA_DESKTOP_GATE=  # >=24 chars; igual no WAF + build Electron (GitHub secret)
```

Ou seja, o **mesmo valor** tem de estar em três lugares:

1. no ficheiro `.env` do servidor da API (para a API saber o que esperar);
2. na regra do WAF da Cloudflare (para o filtro de rede saber o que deixar passar);
3. no processo de compilação (*build*) da aplicação Electron (para o instalador o levar consigo).

O comprimento mínimo de 24 caracteres é validado no *script* de compilação — um segredo curto seria
adivinhável por força bruta.

### V.4.3 `write-gate.cjs` → `desktop-gate.cjs` (ignorado pelo Git)

O ficheiro `backoffice-desktop/scripts/write-gate.cjs` é um pequeno programa de Node.js que corre
antes de empacotar a aplicação. Faz três coisas:

```js
const fromEnv  = (process.env.DIOMIKA_DESKTOP_GATE || '').trim()
const fromFile = readEnvFile(path.join(repoRoot, '.env')).DIOMIKA_DESKTOP_GATE || ''
const gate = (fromEnv || fromFile || '').trim()
if (!gate || gate.length < 24) {
  console.error('ERRO: defina DIOMIKA_DESKTOP_GATE (>=24 chars) no .env ou no ambiente de CI.')
  process.exit(1)
}
fs.writeFileSync(out, `module.exports = ${JSON.stringify(gate)}\n`, 'utf8')
```

1. **Lê** o segredo do ambiente (caso de integração contínua, onde vem de um *GitHub secret*) ou,
   em alternativa, do ficheiro `.env` na raiz do repositório (caso de compilação local).
2. **Valida** que existe e tem pelo menos 24 caracteres — se não, aborta a compilação com código de
   saída 1. Isto impede silenciosamente produzir um instalador inútil.
3. **Escreve** `backoffice-desktop/electron/desktop-gate.cjs`, um módulo de uma linha que exporta o
   valor como *string*.

O ficheiro gerado está explicitamente ignorado pelo Git (`.gitignore`, linha 69:
`backoffice-desktop/electron/desktop-gate.cjs`). A distinção é importante: o *script que gera* está
versionado; o *ficheiro com o segredo* nunca. Assim qualquer pessoa pode reproduzir a compilação sem
que o repositório contenha o segredo.

### V.4.4 O *proxy* do Electron injecta o cabeçalho

A aplicação de secretária é Electron (Chromium + Node.js empacotados num programa nativo). Em
`backoffice-desktop/electron/main.cjs` acontece algo mais interessante do que "abrir um site":

1. **Carrega o gate** com tolerância a falhas (função `loadDesktopGate`): tenta `require`
   do `desktop-gate.cjs` gerado e, se não existir — cenário de desenvolvimento —, recorre à
   variável de ambiente.
2. **Levanta um servidor HTTP local** em `127.0.0.1` numa porta aleatória (`server.listen(0, ...)`)
   e carrega a interface a partir dele. A interface nunca corre em `file://`, o que evita uma classe
   inteira de problemas de segurança de origem.
3. **Faz *proxy* de tudo o que começa por `/api`** para a API real (`proxyToApi`), e é aqui que o
   cabeçalho entra:

```js
const headers = { ...req.headers, host: target.host }
delete headers.origin
delete headers.referer
delete headers['accept-encoding']
headers['user-agent'] = 'DiomikaBackoffice/1.0'
if (DESKTOP_GATE) headers['x-diomika-desktop'] = DESKTOP_GATE
```

Cada linha tem uma razão:

* `host: target.host` — o pedido tem de dizer o domínio da API, não `127.0.0.1`, senão o
  `TrustedHostMiddleware` rejeita-o (camada 3 de V.2.1).
* `delete headers.origin` / `delete headers.referer` — o navegador interno enviaria
  `Origin: http://127.0.0.1:<porta>`, que não consta da lista de origens permitidas de CORS
  (ver V.13). Como este pedido não é feito *por* uma página web num contexto de origem cruzada — é
  feito por um processo Node.js —, remover estes cabeçalhos é correcto e evita rejeições.
* `delete headers['accept-encoding']` — impede compressão na resposta, o que simplifica o
  encaminhamento por *pipe* sem descompressão intermédia.
* `user-agent: 'DiomikaBackoffice/1.0'` — identificação honesta do cliente que, de passagem,
  satisfaz a regra `block-empty-ua` do WAF (V.3.3).
* `x-diomika-desktop: DESKTOP_GATE` — o *gate*. Só é injectado se existir; se não existir, a
  aplicação avisa o utilizador com uma caixa de diálogo *"Build incompleto — Falta
  DIOMIKA_DESKTOP_GATE neste instalador. Peça um build novo à Diomika."*

O ponto arquitectónico decisivo: **o segredo vive no processo principal do Electron, nunca na
página**. O código da interface (Vue) não conhece o valor e não lhe consegue acessar — a janela é
criada com `contextIsolation: true`, `nodeIntegration: false` e `sandbox: true`. Mesmo que a
interface tivesse uma vulnerabilidade de *cross-site scripting*, o script injectado não conseguiria
ler o *gate*; conseguiria, no máximo, fazer pedidos através do *proxy* local — que é uma superfície
muito menor.

### V.4.5 A API compara com `hmac.compare_digest`

Do lado do servidor, em `backend-api/core/local_only.py`:

```python
_DESKTOP_HEADER = "x-diomika-desktop"

def desktop_gate_secret() -> str:
    return (os.getenv("DIOMIKA_DESKTOP_GATE") or "").strip()

def desktop_gate_ok(request: Request) -> bool:
    expected = desktop_gate_secret()
    if not expected:
        return False          # sem segredo configurado → nega (fail-closed)
    got = (request.headers.get(_DESKTOP_HEADER) or "").strip()
    if not got:
        return False
    return hmac.compare_digest(got, expected)
```

**O que é HMAC.** HMAC significa *Hash-based Message Authentication Code* — "código de autenticação
de mensagem baseado em função de dispersão". É uma construção criptográfica que combina uma chave
secreta com uma mensagem e produz uma etiqueta curta. Quem tem a chave consegue verificar que a
mensagem não foi alterada e que veio de alguém que também tem a chave; quem não tem a chave não
consegue produzir uma etiqueta válida. No Diomika, HMAC é usado a sério nos *tokens* de sessão
(V.7).

**Nota de honestidade técnica:** neste caso concreto, `hmac.compare_digest` **não** está a calcular
um HMAC. É apenas a função de comparação que o módulo `hmac` da biblioteca padrão de Python
disponibiliza — está ali por ser *timing-safe*. Vale a pena separar bem os dois conceitos, porque é
uma confusão frequente.

**O que é uma comparação resistente a análise temporal (*timing-safe*).** A comparação normal de
strings (`a == b`) está optimizada para ser rápida: compara byte a byte e **para no primeiro byte
diferente**. Isso significa que o tempo de execução revela informação. Suponha-se um segredo que
começa por `Q`:

* o atacante envia `A...` → falha no 1.º byte → resposta em, digamos, 1000 nanossegundos;
* envia `Q...` → o 1.º byte coincide, falha no 2.º → resposta em 1100 nanossegundos.

Essa diferença de 100 nanossegundos, medida milhares de vezes para filtrar o ruído da rede, permite
descobrir o segredo **um byte de cada vez**. Um segredo de 24 caracteres deixa de exigir 24
tentativas ao acaso sobre um espaço astronómico e passa a exigir umas centenas de tentativas por
posição — perfeitamente viável.

`hmac.compare_digest` compara **sempre todos os bytes**, independentemente de onde está a primeira
diferença, e devolve o resultado agregado no fim. O tempo de execução deixa de depender do conteúdo.
Existe um teste dedicado a este princípio: `test_compare_digest_timing_safe`, em
`backend-api/tests/test_security.py`.

A mesma disciplina aplica-se às chaves de máquina, onde o código usa a função equivalente do módulo
`secrets` (`backend-api/core/auth.py`, `resolve_role` → `secrets.compare_digest`), e à verificação
de password, que compara os *hashes* derivados com `hmac.compare_digest`
(`backend-api/core/admin_users.py`, `verify_password`).

### V.4.6 O WAF espelha a regra

Resumo do caminho de um pedido legítimo do backoffice a `/admin/catalogo/...`:

```
Backoffice Electron
  └─ proxy local injecta X-Diomika-Desktop
       └─ Cloudflare: regra block-admin-system-except-desktop compara o cabeçalho → passa
            └─ Cloudflare Tunnel → máquina virtual
                 └─ TrustedHostMiddleware: Host == api.diomika.com → passa
                      └─ PrivilegedPathMiddleware → privileged_access_ok() → desktop_gate_ok()
                         → hmac.compare_digest → passa
                           └─ dependência do router: Depends(admin_must_be_local) → passa
                                └─ require_api_key: sessão Bearer dms1.… válida?
                                     └─ assert_table_action(tabela, acção, papel)
                                          └─ PostgreSQL (a API usa a chave de serviço)
```

Duas verificações de *gate* independentes (Cloudflare e Python) e, dentro do Python, duas
verificações independentes do mesmo predicado: no middleware, que cobre *todos* os caminhos
privilegiados, e na dependência de cada *router* administrativo. Se alguém, ao acrescentar um
*router* novo, se esquecer da dependência, o middleware continua a proteger. Se alguém mexer no
middleware, as dependências continuam a proteger.

### V.4.7 O compromisso: o segredo está dentro do binário

Isto tem de ser dito sem rodeios: **o `DIOMIKA_DESKTOP_GATE` está dentro do instalador**. Quem
tiver o instalador e alguma paciência (descompactar o pacote `app.asar`, procurar a *string*)
consegue extraí-lo. Não é criptografia; é ofuscação com um propósito muito concreto.

Porque é que continua a valer a pena:

* **Elimina 100% do tráfego automatizado** contra `/admin`. Os *scanners* de V.1.2 nunca terão o
  cabeçalho, e são a esmagadora maioria dos pedidos hostis.
* **Não é a autenticação.** Passar o *gate* apenas dá direito a *ver o formulário de login*. Depois
  ainda é preciso nome de utilizador e password (V.6), sujeitos a limitação de ritmo (V.9), com
  sessão curta e revogável (V.7), e com autorização por papel a seguir (V.11). O *gate* é um
  filtro de fronteira, não um mecanismo de identidade.
* **Reduz a superfície exposta** de forma dramática: sem *gate* válido, um atacante não consegue nem
  descobrir *quais* endpoints administrativos existem, porque todos respondem `403` de forma
  uniforme.

O que se perde:

* **Um instalador comprometido "queima" o segredo para todos**, porque é partilhado.
* **A rotação é uma operação coordenada**: mudar `DIOMIKA_DESKTOP_GATE` no `.env` do servidor,
  actualizar a regra do WAF, recompilar o instalador e distribuí-lo. Se a ordem falhar, os clientes
  ficam bloqueados até actualizarem.
* **Não há revogação individual.** Não se consegue invalidar o *gate* de um só computador; para
  isso existem as contas de utilizador, que se podem desactivar uma a uma
  (`POST /admin/auth/users/disable`, em `backend-api/routes/admin_auth.py`).

Aceitar este compromisso é uma decisão consciente e proporcional: o objectivo do *gate* é *reduzir
ruído e superfície*, e nesse papel é excelente. Confundi-lo com autenticação é que seria o erro.

---

## V.5 `path_guard` e `local_only` / `privileged_access_ok`

Dois módulos pequenos que, juntos, definem "quem pode falar com a parte administrativa".

### V.5.1 `backend-api/core/local_only.py` — a decisão

```python
_LOOPBACK = frozenset({"127.0.0.1", "::1", "localhost", "testclient"})

def peer_is_loopback(request: Request) -> bool:
    """IP do peer TCP — não usar X-Forwarded-For (fácil de forjar)."""
    if request.client and request.client.host:
        peer = request.client.host.strip().lower()
        return peer in _LOOPBACK or peer.startswith("127.")
    return False

def privileged_access_ok(request: Request) -> bool:
    settings = get_settings()
    if not settings.is_production or settings.is_beta:
        return True            # desenvolvimento e beta: aberto (ver nota abaixo)
    if peer_is_loopback(request):
        return True            # operações na própria máquina virtual
    return desktop_gate_ok(request)
```

Pontos a sublinhar:

* **"Loopback"** é o nome do endereço de rede que uma máquina usa para falar consigo mesma:
  `127.0.0.1` em IPv4, `::1` em IPv6. Tráfego de loopback nunca atravessa uma rede física — se o
  pedido vem de `127.0.0.1`, vem de um processo na própria máquina virtual, o que só acontece se
  alguém já tiver acesso por SSH (*Secure Shell*, o protocolo de administração remota). Nesse
  cenário, quem lá está tem legitimamente as chaves do reino.
* **`"testclient"`** está na lista porque é o nome que o cliente de testes do Starlette usa. Permite
  que a bateria de testes exercite os caminhos administrativos sem simular rede.
* **O comentário sobre `X-Forwarded-For` é a parte mais importante do ficheiro.** `X-Forwarded-For`
  é um cabeçalho que os *proxies* acrescentam a dizer "o cliente original era este IP". Qualquer
  pessoa pode escrever `X-Forwarded-For: 127.0.0.1` num pedido. Se a verificação de loopback
  confiasse nesse cabeçalho, o controlo de acesso inteiro seria trivialmente contornável com uma
  linha de `curl`. Por isso usa-se `request.client.host` — o endereço real da ligação TCP
  (*Transmission Control Protocol*), que o atacante não controla.
* **Em desenvolvimento e em beta, devolve `True`.** Isto é deliberado (ergonomia durante o
  desenvolvimento) e explica porque é que `validate_startup`, em `backend-api/core/config.py`, é tão
  rígido: quase todas as garantias fortes estão condicionadas a `is_production and not is_beta`, e a
  configuração de arranque recusa-se a subir em produção sem os pré-requisitos.

E o ponto de entrada usado pelos *routers*:

```python
def admin_must_be_local(request: Request) -> None:
    if privileged_access_ok(request):
        return
    raise HTTPException(
        status_code=403,
        detail="Admin/system só via backoffice Diomika ou localhost.",
    )
```

Usa-se como dependência do FastAPI, por exemplo em `backend-api/routes/admin_auth.py`:

```python
router = APIRouter(
    prefix="/admin/auth",
    tags=["Admin Auth"],
    dependencies=[Depends(admin_must_be_local)],   # aplica-se a TODAS as rotas do router
)
```

### V.5.2 `backend-api/core/path_guard.py` — a fronteira

```python
_PRIVILEGED_PREFIXES = ("/admin", "/system", "/health/detail")
_PUBLIC_MUTATE_PREFIXES = ("/contacto", "/orcamentos")

class PrivilegedPathMiddleware(BaseHTTPMiddleware):
    """Fail-closed para caminhos privilegiados + lockdown global."""
```

Este middleware garante que **nenhum caminho privilegiado fica aberto por esquecimento**. Repare-se
que `/health/detail` está na lista: o `/health` simples devolve apenas "estou vivo" e pode ser
público (é o que a Cloudflare e a própria aplicação de secretária consultam), mas o `/health/detail`
revela estado interno — versões, ligações, contadores — e isso é informação de reconhecimento útil
para um atacante. Distinguir os dois é uma decisão de maturidade.

O nome do módulo, "path guard" (guarda de caminhos), descreve bem a função: uma sentinela colocada
no ponto mais exterior da aplicação que olha apenas para o caminho da URL e para o estado global do
sistema, antes de qualquer outra lógica.

Testes que fixam este comportamento, em `backend-api/tests/test_local_only.py`:

* `test_admin_local_allows_loopback_in_production` — loopback passa em produção;
* `test_admin_local_blocks_remote_without_gate` — remoto sem *gate* é bloqueado;
* `test_admin_allows_remote_with_desktop_gate` — remoto com *gate* válido passa;
* `test_admin_local_allows_remote_in_beta` — em beta, o *gate* não é exigido.

Estes quatro testes são a especificação executável de V.4 e V.5. Se alguém alterar a lógica de
acesso privilegiado sem perceber, a bateria de testes queixa-se antes de o código chegar a produção.

---

## V.6 Autenticação de administração: `scrypt`

### V.6.1 Porque não se guarda a password em claro

Se a base de dados (ou, aqui, o ficheiro local) guardasse `password: "Verao2026!"`, então:

* qualquer pessoa com acesso de leitura ao ficheiro — cópia de segurança extraviada, disco antigo,
  erro de configuração, atacante que já entrou por outra via — fica com a password;
* como as pessoas reutilizam passwords, essa fuga compromete também o email e a banca do operador;
* e o administrador do sistema *consegue ver* a password dos utilizadores, o que é um problema legal
  e de confiança, além de técnico.

A solução padrão desde os anos 70 é guardar uma **função de dispersão (*hash*)** da password.

### V.6.2 O que é uma função de dispersão criptográfica

É uma função que transforma qualquer entrada num valor de tamanho fixo, com três propriedades:

1. **Determinista** — a mesma entrada produz sempre a mesma saída (essencial: é assim que se
   verifica a password).
2. **Unidireccional** — dada a saída, não existe forma prática de recuperar a entrada. Não há função
   inversa; a única via é tentar candidatos.
3. **Resistente a colisões** — é impraticável encontrar duas entradas diferentes com a mesma saída.

Verificar uma password passa então a ser: aplicar a mesma função à password apresentada e comparar o
resultado com o valor guardado. Se coincidirem, a password está certa — **e o servidor nunca teve de
guardar a password**.

### V.6.3 O que é o *salt* e porque é indispensável

Só *hash* não basta. Considere-se um sistema onde três pessoas escolheram `Verao2026!`. Com um
*hash* simples, as três teriam exactamente o mesmo valor guardado, o que revela imediatamente que
partilham a password. Pior: um atacante pode pré-calcular uma tabela gigantesca de
`password → hash` (uma "*rainbow table*") e consultá-la instantaneamente.

O **salt** é um valor aleatório, diferente para cada utilizador, misturado com a password antes do
*hash*. Não é secreto — é guardado ao lado do *hash* — e resolve os dois problemas:

* passwords iguais produzem *hashes* diferentes, porque os *salts* diferem;
* tabelas pré-calculadas tornam-se inúteis, porque teria de existir uma tabela por *salt*, e o
  espaço de *salts* é astronómico.

No Diomika o *salt* tem 16 bytes de aleatoriedade criptográfica: `secrets.token_bytes(16)`.

### V.6.4 Porque `scrypt` e não SHA-256

SHA-256 é excelente como função de dispersão, mas tem uma característica que aqui é um defeito: é
**rápida**. Uma placa gráfica moderna calcula milhares de milhões de SHA-256 por segundo. Um
atacante com o ficheiro de *hashes* testaria todo um dicionário de passwords comuns em minutos.

Para passwords quer-se o contrário: uma função **deliberadamente lenta e caríssima em memória**.
`scrypt` (Colin Percival, 2009) foi desenhada exactamente para isso: é *memory-hard*, ou seja, exige
uma grande quantidade de memória de acesso aleatório, o que anula a vantagem de hardware
especializado (as placas gráficas e os circuitos dedicados têm muitos núcleos mas pouca memória por
núcleo).

Em `backend-api/core/admin_users.py`:

```python
def hash_password(password: str, *, salt: bytes | None = None) -> str:
    salt = salt or secrets.token_bytes(16)
    dk = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=2**14, r=8, p=1, dklen=32)
    return "scrypt$" + base64.b64encode(salt).decode() + "$" + base64.b64encode(dk).decode()
```

Os parâmetros, um a um:

| Parâmetro | Valor | Significado |
|---|---|---|
| `n` | `2**14` = 16 384 | **Custo de CPU e memória.** É o número de iterações da mistura interna. Cada duplicação de `n` duplica o trabalho *e* a memória necessária. |
| `r` | `8` | **Tamanho do bloco.** Controla quanta memória é tocada por iteração; 8 é o valor recomendado clássico. |
| `p` | `1` | **Paralelismo.** Quantos fluxos independentes correm. Com `p=1`, não há ganho em paralelizar num só cálculo. |
| `dklen` | `32` | **Comprimento da chave derivada**, em bytes (256 bits). |

A memória aproximada é `128 × n × r` bytes ≈ `128 × 16384 × 8` ≈ **16 MiB por verificação**. Isto
tem uma consequência dupla: para o operador legítimo, o login demora umas dezenas de milissegundos
(imperceptível); para um atacante que queira testar mil milhões de candidatos, exige mil milhões ×
16 MiB de trabalho de memória — economicamente inviável.

O formato guardado é `scrypt$<salt-em-base64>$<hash-em-base64>`. O prefixo do algoritmo está lá de
propósito: permite, no futuro, migrar para outro algoritmo (por exemplo Argon2id) mantendo a
capacidade de verificar *hashes* antigos, porque `verify_password` começa por ler o prefixo:

```python
algo, salt_b64, hash_b64 = encoded.split("$", 2)
if algo != "scrypt":
    return False
```

E a comparação final volta a ser resistente a análise temporal:
`return hmac.compare_digest(dk, expected)`.

### V.6.5 Política de força da password

Não basta guardar bem uma password fraca. `validate_password_strength` exige:

* **12 caracteres** no mínimo (configurável por `ADMIN_PASSWORD_MIN_LEN`);
* pelo menos uma **maiúscula**;
* pelo menos uma **minúscula**;
* pelo menos um **dígito**;
* pelo menos um **símbolo** (qualquer caractere não alfanumérico);
* e não constar de uma pequena lista de passwords óbvias (`password`, `admin123456`, variantes de
  `diomika…`), verificada em minúsculas.

Esta validação corre em **todos** os caminhos que definem uma password: criação inicial
(`ensure_bootstrap`), alteração pelo próprio (`change_password`) e escrita administrativa
(`upsert_user`). Teste correspondente: `test_password_strength_rejects_weak`, em
`backend-api/tests/test_admin_session.py`.

### V.6.6 Como o ficheiro é escrito (detalhe que evita perder o acesso)

A função `_save`, no mesmo ficheiro, é mais cuidadosa do que parece:

1. **Cópia de segurança rotativa** — antes de escrever, copia o ficheiro actual para
   `admin_users.json.bak`. Se a escrita corromper algo, existe o estado anterior.
2. **Escrita atómica** — escreve primeiro num ficheiro temporário e só depois faz
   `tmp.replace(_STORE)`. Em sistemas de ficheiros comuns, `replace` é atómico, portanto nunca
   existe um momento em que `admin_users.json` esteja meio escrito. Uma falha de energia a meio de
   uma escrita não trancaria o operador fora do backoffice.
3. **Permissões restritivas** — `os.chmod(_STORE, 0o600)`, isto é, leitura e escrita **apenas** para
   o dono do ficheiro. Nem o grupo nem os outros utilizadores da máquina conseguem ler.
4. **Serialização com bloqueio** — todas as operações passam por um `threading.Lock`, o que evita
   que dois pedidos concorrentes escrevam em cima um do outro.

*Nota de melhoria identificada:* o `.gitignore` (linhas 24-25) exclui `admin_users.json` e
`admin_users.tmp`, mas não `admin_users.json.bak`. Não é uma fuga real — o ficheiro só existe na
máquina que corre a API, e o directório não é publicado —, mas acrescentar
`backend-api/data/admin_users.json.bak` à lista fecharia a possibilidade de alguém o versionar por
distracção.

---

## V.7 Sessões: *tokens* HMAC `dms1.…` (não é um JWT de biblioteca)

### V.7.1 O problema que uma sessão resolve

HTTP não tem memória: cada pedido é independente. Se o backoffice tivesse de enviar a password em
todos os pedidos, a password circularia dezenas de vezes por minuto e teria de ficar guardada em
memória na aplicação. A solução universal é: autenticar **uma vez** e receber um *token* que prova
"eu já me autentiquei", com validade limitada.

### V.7.2 O formato do *token*

Em `backend-api/core/session_tokens.py`:

```python
_PREFIX = "dms1."

payload = {
    "u": username,                        # quem
    "r": role,                            # com que papel
    "iat": now,                           # issued at — emitido em
    "exp": now + SESSION_TTL_SECONDS,     # expiration — expira em
    "jti": jti,                           # JWT ID — identificador único da sessão
}
body = _b64url(json.dumps(payload, separators=(",", ":")).encode())
sig  = _b64url(hmac.new(_secret(), body.encode(), hashlib.sha256).digest())
return f"{_PREFIX}{body}.{sig}", SESSION_TTL_SECONDS
```

Ou seja, o *token* é `dms1.<corpo-em-base64url>.<assinatura-em-base64url>`. O prefixo `dms1` é uma
etiqueta de versão ("Diomika session, versão 1") que permite introduzir um formato `dms2` mais tarde
sem ambiguidade, e permite à função `is_session_token` distinguir num instante um *token* de sessão
de uma chave de API.

**Sobre a palavra "opaco".** Vale a pena ser preciso: o corpo está em Base64URL, que é uma
*codificação*, não uma *cifra*. Qualquer pessoa com o *token* pode descodificar o corpo e ler o nome
de utilizador, o papel e as datas. Isto é seguro **porque o corpo não contém segredos** — só
identificadores. O que a assinatura garante não é confidencialidade, é **integridade e
autenticidade**: sem `API_SECRET_KEY`, ninguém consegue produzir um corpo diferente com assinatura
válida. Trocar `"r":"mensagens"` por `"r":"admin"` invalida a assinatura e o *token* é rejeitado em
`parse_session`.

A chave de assinatura é derivada, não usada em cru:

```python
def _secret() -> bytes:
    raw = (os.getenv("API_SECRET_KEY") or "").strip()
    if not raw or len(raw) < 32:
        raise RuntimeError("API_SECRET_KEY (>=32 chars) obrigatório para sessões admin")
    return hashlib.sha256(raw.encode("utf-8")).digest()
```

`sha256` converte um segredo de comprimento variável em exactamente 32 bytes, que é o tamanho de
bloco ideal para HMAC-SHA256. O mínimo de 32 caracteres é exigido em tempo de execução — e, em
produção, também no arranque (`backend-api/core/config.py`). O comentário no código sublinha uma
decisão deliberada: *"Fonte única: API_SECRET_KEY (sem alias ADMIN_SESSION_SECRET — menos
superfície)"*. Menos variáveis de ambiente equivalentes significa menos formas de configurar mal.
Teste: `test_session_secret_only_api_secret_key`, em
`backend-api/tests/test_path_guard_hardening.py`.

### V.7.3 Porque não uma biblioteca de JWT

JWT significa *JSON Web Token* — um padrão muito difundido para *tokens* assinados. O formato aqui
usado é *inspirado* nele (a nomenclatura `iat`, `exp`, `jti` vem de lá), mas a implementação é
própria e minimalista. As razões:

1. **A família de vulnerabilidades do campo `alg`.** O JWT inclui um cabeçalho onde o *token* diz
   qual o algoritmo com que foi assinado. Bibliotecas mal usadas confiaram nesse campo, o que
   permitiu ataques como `alg: none` (token sem assinatura aceite como válido) ou confusão entre
   algoritmos simétricos e assimétricos. Neste formato **não existe** campo de algoritmo negociável:
   é sempre HMAC-SHA256, decidido pelo servidor. A classe de ataque desaparece por construção.
2. **Menos dependências.** Tudo o que é usado (`hmac`, `hashlib`, `base64`, `json`, `secrets`) vem
   da biblioteca padrão de Python. Menos código de terceiros é menos superfície de cadeia de
   fornecimento e menos actualizações de segurança a acompanhar.
3. **JWT é, por filosofia, sem estado — e aqui quer-se estado.** A promessa do JWT é que o servidor
   valida o *token* sem consultar nada, o que também significa que **não o consegue revogar**. O
   Diomika quer o contrário: quer poder terminar uma sessão imediatamente (ao mudar a password, ao
   desactivar um utilizador, ao fazer logout). Daí o `jti` e o registo de sessões activas e
   revogadas.

### V.7.4 Tempos de vida: absoluto e por inactividade

```python
SESSION_TTL_SECONDS  = int(os.getenv("ADMIN_SESSION_TTL_MINUTES") or "15") * 60
SESSION_IDLE_SECONDS = int(os.getenv("ADMIN_SESSION_IDLE_MINUTES") or "10") * 60
```

TTL quer dizer *Time To Live* — tempo de vida. Existem dois limites, com propósitos diferentes:

* **TTL absoluto (15 minutos por omissão)** — passados 15 minutos desde a emissão, o *token* morre,
  **mesmo que esteja em uso constante**. Limita a janela de utilidade de um *token* roubado.
* **Inactividade (10 minutos por omissão)** — se não houver pedidos durante 10 minutos, a sessão
  expira antes do TTL. É a protecção para o operador que se afasta do computador.

Cada pedido validado "toca" a sessão (parâmetro `touch=True` em `parse_session`), actualizando o
carimbo de última utilização. Teste: `test_idle_timeout_expires_session`.

Quinze minutos são um valor agressivo para um backoffice. É uma escolha justificada: o backoffice
gere dados pessoais de clientes e corre numa aplicação de secretária que reautentica sem atrito.

### V.7.5 Como o *token* viaja: `Authorization: Bearer`

O cliente envia o *token* no cabeçalho padrão de autorização:

```
Authorization: Bearer dms1.<corpo>.<assinatura>
```

"Bearer" significa "portador": *quem apresentar este token é tratado como autorizado*. É simples e é
por isso que o *token* tem de ser tratado como um segredo em trânsito — daí TLS obrigatório e vida
curta.

Do lado do servidor, `backend-api/core/auth.py` aceita **dois** mecanismos no mesmo ponto de entrada:

```python
def require_api_key(request, x_api_key=Security(api_key_header), bearer=Security(bearer_scheme)):
    token = (bearer.credentials if bearer else None) or ""
    if token and is_session_token(token):
        sess = parse_session(token)
        if not sess:
            raise HTTPException(status_code=401, detail="Sessão inválida ou expirada")
        role = str(sess["role"])
        if role not in BUSINESS_ROLES:
            raise HTTPException(status_code=401, detail="Sessão com role inválido")
        return _attach(request, role=role, actor=str(sess["username"]))
    ...
```

Note-se o `_attach`: guarda o papel e o **actor** (o nome de utilizador, ou `"api-key"`) em
`request.state`. É esse actor que aparece depois na tabela `admin_audit_log` — o que permite
responder à pergunta "quem fez isto?" e não apenas "que papel fez isto?".

### V.7.6 Redis em produção, memória em desenvolvimento

Redis é uma base de dados em memória, extremamente rápida, usada para estado partilhado. É
necessária aqui por uma razão prática: em produção a API corre com **vários processos de trabalho**
(*workers*) para aproveitar os núcleos do processador. Se o registo de sessões vivesse na memória de
cada processo, o comportamento seria absurdo — o utilizador faria login (processo A), o pedido
seguinte iria para o processo B, que não conheceria a sessão, e o login "cairia" de forma aleatória.

Chaves usadas em Redis (todas com prefixo de namespace e expiração automática):

| Chave | Conteúdo | Para que serve |
|---|---|---|
| `diomika:sess:user:<username>` | o `jti` da sessão activa | Impor **uma única sessão activa por utilizador**. Um login novo revoga o anterior. |
| `diomika:sess:revoked:<jti>` | `"1"` | Lista de revogação, com expiração `TTL + 60s` (mais do que isso é desnecessário: o *token* já expirou por si). |
| `diomika:sess:seen:<jti>` | carimbo Unix da última utilização | Cálculo do tempo de inactividade. |

A obrigatoriedade é explícita em produção final:

```python
def _redis_required() -> bool:
    s = get_settings()
    return bool(s.is_production and not s.is_beta)
```

E em `validate_startup` a API recusa-se a arrancar sem `REDIS_URL` em produção final, com a
justificação escrita no próprio erro: *"rate limit + sessões partilhadas entre workers"*.

Em desenvolvimento, há um substituto em memória (`_active_jti`, `_revoked`, `_last_seen`, protegidos
por `threading.Lock`), com um limite de 5000 entradas revogadas para não crescer indefinidamente.
Toda a lógica está escrita para que o Redis, quando presente, tenha a última palavra, e a memória
seja apenas recurso de reserva — o padrão está na função `_redis_session_ok`, que devolve
`True`/`False` quando o Redis responde e `None` quando não está disponível, sinalizando "usa a
memória".

### V.7.7 Revogação: os quatro caminhos

1. **Logout explícito** — `POST /admin/auth/logout` chama `revoke_session(token)`.
2. **Login novo** — `issue_session` revoga automaticamente o `jti` anterior do mesmo utilizador
   (teste `test_new_login_invalidates_previous_session`).
3. **Alteração de password ou de papel** — `upsert_user` chama `revoke_all_for_user`. Faz sentido
   absoluto: se a password mudou porque se suspeita de compromisso, deixar sessões antigas vivas
   anularia a medida.
4. **Desactivação de conta** — `set_user_disabled(username, True)` também revoga (teste
   `test_disable_user_revokes_sessions`). Há ainda uma protecção contra o erro clássico de
   auto-exclusão: *"Não pode desactivar a própria conta activa"*.

---

## V.8 MFA / TOTP — o que é; `ADMIN_MFA_REQUIRED=0` por agora

### V.8.1 Os três factores

MFA significa *Multi-Factor Authentication* — autenticação com múltiplos factores. Um "factor" é uma
categoria de prova de identidade:

1. **Algo que se sabe** — password, código pessoal.
2. **Algo que se tem** — telefone, chave física de segurança, cartão.
3. **Algo que se é** — impressão digital, reconhecimento facial.

Multifactor significa combinar **categorias diferentes**. Password + pergunta de segurança não é
MFA (são duas coisas que se sabem). Password + código no telemóvel é MFA. O valor é claro: uma
password roubada por *phishing* ou fuga de dados deixa de ser suficiente, porque o atacante teria de
ter também o telefone.

### V.8.2 O que é TOTP

TOTP significa *Time-based One-Time Password* — password de utilização única baseada no tempo,
padronizada no RFC 6238. É o mecanismo por trás do Google Authenticator, Authy, 1Password, Aegis e
afins. Funciona assim:

1. No momento da configuração, servidor e aplicação partilham um **segredo aleatório** (normalmente
   transmitido por código QR).
2. Ambos calculam `HMAC-SHA1(segredo, número-do-intervalo-de-30-segundos)` e reduzem o resultado a
   6 dígitos.
3. Como ambos conhecem o segredo e ambos sabem que horas são, ambos chegam ao mesmo número, que muda
   a cada 30 segundos.

Não é preciso rede: o telefone pode estar em modo de avião. E o código é inútil passados segundos,
o que torna a interceptação pouco valiosa.

### V.8.3 A implementação no Diomika

Em `backend-api/core/admin_users.py`, usando a biblioteca `pyotp`:

```python
def _totp_ok(secret: str, code: str) -> bool:
    totp = pyotp.TOTP(secret)
    return bool(totp.verify(code.strip(), valid_window=1))
```

`valid_window=1` aceita o código do intervalo actual, do anterior e do seguinte — uma tolerância de
±30 segundos que resolve o problema real dos relógios ligeiramente desalinhados e do utilizador que
escreve o código no último segundo.

O enrolamento é feito em **dois passos**, o que é a forma correcta de o fazer:

* `begin_mfa_setup(username)` gera um segredo e guarda-o em `totp_secret_pending` — **ainda não
  activo** —, devolvendo também o URI de aprovisionamento
  (`otpauth://totp/<utilizador>?issuer=Diomika%20Admin&secret=…`), que a aplicação transforma em
  código QR;
* `confirm_mfa_setup(username, code)` só promove `totp_secret_pending` para `totp_secret` **depois**
  de o utilizador provar que consegue gerar um código válido.

Sem esta separação, um erro na leitura do QR trancaria o operador fora da própria conta. Os
endpoints correspondentes são `POST /admin/auth/mfa/setup` e `POST /admin/auth/mfa/confirm`, ambos
exigindo password correcta e ambos com limitação de ritmo.

### V.8.4 Porque está desligado por omissão

```python
def mfa_required_globally() -> bool:
    """MFA opcional — activo só com ADMIN_MFA_REQUIRED=1."""
    return (os.getenv("ADMIN_MFA_REQUIRED") or "").strip().lower() in ("1", "true", "yes")
```

E em `.env.example`: `# ADMIN_MFA_REQUIRED=0`.

A justificação é de proporcionalidade e de risco operacional:

* o backoffice já está atrás de **duas** barreiras que o utilizador comum da internet não transpõe
  (o *gate* de secretária e a restrição a loopback);
* há hoje **um operador principal**; se perder o telefone com o segredo TOTP e não houver
  procedimento de recuperação testado, fica sem acesso ao seu próprio sistema — e um sistema que se
  tranca sozinho é um problema de disponibilidade, que também é segurança;
* a força bruta já está coberta por limitação de ritmo e bloqueio de conta (V.9).

Quando activar (recomendação): assim que houver mais do que um utilizador com papel `admin`, ou
assim que o backoffice passe a ser usado a partir de mais do que um computador. O caminho de
activação é suave, porque o fluxo de login já devolve estados intermédios:
`{"mfa_setup_required": true}` quando `ADMIN_MFA_REQUIRED=1` mas a conta ainda não tem TOTP, e
`{"mfa_required": true}` quando tem. A interface pode, portanto, guiar o enrolamento sem qualquer
alteração no servidor. Teste: `test_mfa_optional_via_env`.

**Limitação honesta:** o segredo TOTP é guardado em claro no mesmo `admin_users.json` que contém os
*hashes* das passwords. Quem conseguir ler esse ficheiro contorna o MFA. Isto não é um defeito
específico do Diomika (é o compromisso normal do TOTP: o servidor *precisa* do segredo para
verificar), mas reforça a importância das permissões `0600` descritas em V.6.6 — e explica porque a
melhoria natural do futuro é cifrar esse campo com uma chave que não viva no mesmo ficheiro.

---

## V.9 Bloqueio por falhas; alertas em login falhado

A defesa contra adivinhação de passwords tem quatro camadas independentes que actuam no mesmo
endpoint (`POST /admin/auth/login`, em `backend-api/routes/admin_auth.py`).

### V.9.1 Camada 1 — limitação de ritmo dupla

```python
rate_limit(request, "admin_login", max_calls=20, window_seconds=300)
user_key = (body.username or "").strip().lower()[:64] or "unknown"
rate_limit_absolute(f"admin_login_user:{user_key}", max_calls=10, window_seconds=300)
```

* **Por endereço IP:** 20 tentativas em 5 minutos. Trava um atacante único.
* **Por nome de utilizador, independentemente do IP:** 10 tentativas em 5 minutos. Esta é a parte
  inteligente. Um ataque distribuído (*password spraying*) com mil endereços IP diferentes, um
  pedido cada, passaria completamente pelo limite por IP. O limite absoluto por nome de utilizador
  fecha essa porta — o comentário no código di-lo em duas palavras: *"anti brute-force multi-IP"*.

O nome de utilizador é normalizado (minúsculas, truncado a 64 caracteres) antes de servir de chave,
para que variações de escrita não criem contentores separados.

### V.9.2 Camada 2 — bloqueio da conta

Em `backend-api/core/admin_users.py`:

```python
MAX_FAILED      = int(os.getenv("ADMIN_LOGIN_MAX_FAILED") or "5")
LOCKOUT_MINUTES = int(os.getenv("ADMIN_LOGIN_LOCKOUT_MINUTES") or "15")
```

Cinco falhas consecutivas escrevem `locked_until` no registo do utilizador, 15 minutos no futuro, e
reiniciam o contador. Enquanto estiver bloqueada, a conta recusa mesmo a password correcta. Um login
bem-sucedido limpa `failed_attempts` e `locked_until`.

Este estado é **persistente** (fica no ficheiro), ao contrário da limitação de ritmo em memória.
Reiniciar a API não apaga o bloqueio. Teste: `test_login_lockout`.

### V.9.3 Camada 3 — respostas genéricas (sem enumeração)

Internamente, `authenticate` distingue e devolve mensagens ricas: `"Conta desactivada"`,
`"Conta bloqueada. Tente dentro de ~N min."`,
`"Credenciais inválidas (N tentativas restantes)"`. Mas a rota **não** as reenvia ao cliente:

```python
if err or not user:
    # Resposta genérica ao cliente — sem enumeração (lockout/disabled/tentativas).
    log_admin_action(action="login_failed", ...)
    send_alert("Admin login falhou", severity="warning", ...)
    raise HTTPException(status_code=401, detail="Credenciais inválidas")
```

Isto chama-se prevenção de **enumeração de utilizadores**. Se a resposta distinguisse "utilizador
não existe" de "password errada", um atacante descobriria nomes de utilizador válidos sem nunca
acertar numa password — e metade do trabalho estaria feito. As mensagens detalhadas vão para os
registos do servidor, onde são úteis para o operador e invisíveis para o atacante. Teste:
`test_login_error_is_generic`, em `backend-api/tests/test_observability_flags.py`.

### V.9.4 Camada 4 — auditoria, alertas e detecção de anomalias

Cada falha desencadeia três acções:

1. **Auditoria** — `log_admin_action(action="login_failed", ...)` escreve na tabela
   `admin_audit_log` com actor, endereço IP, identificador de pedido e motivo. Esta tabela está
   fechada a `anon` por política RLS e excluída do CRUD genérico
   (`CRUD_INFRA_BLOCKED`, ver V.11): nem através da API se consegue apagar o rasto.
2. **Alerta imediato** — `send_alert("Admin login falhou", severity="warning", ...)`. Em
   `backend-api/core/alerts.py`, todo o alerta é **sempre** escrito em `deploy/alerts.log` (uma linha
   JSON por evento) e, se `ALERT_WEBHOOK_URL` estiver configurado, enviado também por HTTP POST.
3. **Detecção de anomalia** — `note_login_failure(username, ip)`, em `backend-api/core/anomaly.py`,
   mantém uma janela deslizante:

```python
threshold = int(os.getenv("ANOMALY_LOGIN_FAIL_THRESHOLD") or "8")      # 8 falhas
window    = int(os.getenv("ANOMALY_LOGIN_FAIL_WINDOW_SEC") or "600")   # em 10 minutos
cooldown  = int(os.getenv("ANOMALY_ALERT_COOLDOWN_SEC") or "900")      # 1 alerta / 15 min
```

Oito falhas no mesmo par (utilizador, IP) em dez minutos produzem um alerta de severidade
**crítica** — *"Anomalia: brute-force login admin"* —, com um período de silêncio de 15 minutos para
que um ataque prolongado não gere mil notificações. A diferença entre `warning` (cada falha) e
`critical` (padrão de ataque) é o que separa um sistema de alertas útil de um que se aprende a
ignorar.

### V.9.5 Notificações no telefone (ntfy) e o destino dos alertas

`ALERT_WEBHOOK_URL` aceita qualquer serviço que receba um POST com JSON. Duas opções práticas:

* **Slack / Discord** — URLs de *webhook* de canal; os anfitriões `hooks.slack.com`, `discord.com` e
  `discordapp.com` constam da lista de permissões de saída.
* **ntfy** — um serviço minimalista de notificações *push* baseado em tópicos: escolhe-se um nome de
  tópico, faz-se POST para `https://ntfy.sh/<tópico>` e a aplicação de telemóvel subscrita recebe a
  notificação em segundos, sem contas nem configuração. O anfitrião `ntfy.sh` está na lista de
  permissões de `backend-api/core/ssrf_guard.py`, precisamente para permitir este caminho.

O detalhe que interessa em segurança: a URL configurada é **validada pelo guarda de SSRF antes de
qualquer envio** (ver V.12):

```python
try:
    from core.ssrf_guard import assert_safe_outbound_url
    assert_safe_outbound_url(url)
except Exception as exc:
    logger.error("ALERT webhook URL rejeitada pelo SSRF guard: %s", exc)
    return True
```

Assim, uma variável de ambiente mal preenchida — ou maliciosamente alterada — não transforma o
sistema de alertas num instrumento para o servidor atacar a sua própria rede interna. E note-se que
a falha de envio devolve `True`: **um alerta que não consegue sair não derruba o pedido do
utilizador**. O registo local em `deploy/alerts.log` garante que nada se perde.

Em produção final, a ausência de `ALERT_WEBHOOK_URL` é tratada como erro de arranque por omissão
(`ALERT_WEBHOOK_REQUIRED` assume `1`), com a possibilidade de a baixar para aviso definindo
`ALERT_WEBHOOK_REQUIRED=0`. A filosofia: um sistema de produção sem caminho de alerta é um sistema
onde os problemas se descobrem pelo cliente.

---

## V.10 A armadilha do *bootstrap*

Esta secção existe porque é o erro operacional mais provável de todo o projecto, e vale a pena
gravá-lo.

### V.10.1 O que `ensure_bootstrap` faz

```python
def ensure_bootstrap() -> None:
    """Cria utilizador inicial a partir de ADMIN_BOOTSTRAP_* se ainda não houver users."""
    if has_users():
        return                      # ← A LINHA CRÍTICA
    user     = (os.getenv("ADMIN_BOOTSTRAP_USER") or "").strip()
    password = (os.getenv("ADMIN_BOOTSTRAP_PASSWORD") or "").strip()
    role     = (os.getenv("ADMIN_BOOTSTRAP_ROLE") or "admin").strip().lower()
    if not user or not password:
        logger.warning("Sem utilizadores admin locais. Defina ADMIN_BOOTSTRAP_USER + ...")
        return
    upsert_user(user, password, role=role if role in VALID_ROLES else "admin")
```

Traduzindo: **se `backend-api/data/admin_users.json` já tiver pelo menos um utilizador, a função
devolve imediatamente e ignora completamente as variáveis `ADMIN_BOOTSTRAP_*`.**

### V.10.2 A armadilha

> Mudar `ADMIN_BOOTSTRAP_PASSWORD` no `.env` e reiniciar a API **não altera** a password de um
> utilizador que já exista. O login continuará a exigir a password antiga, e a nova aparecerá
> "ignorada". Não é uma avaria — é o comportamento pretendido.

Porque é que isto é o desenho correcto:

* se as variáveis de ambiente sobrepusessem sempre a password, o `.env` passaria a ser a fonte de
  verdade das credenciais — um ficheiro de texto simples, com cópias em `.bak`, editado por vezes
  por SSH;
* uma password alterada em condições de emergência através do endpoint próprio seria silenciosamente
  revertida no reinício seguinte, o que é um problema de segurança sério;
* e o comportamento actual respeita o princípio de que o *bootstrap* é **semeadura**, não
  **configuração contínua**. O `.env.example` já o documenta: *"so cria user se admin_users.json
  vazio"*.

### V.10.3 Como mudar a password de facto

**Via preferencial — o endpoint dedicado:**

```
POST /admin/auth/change-password
Authorization: Bearer dms1.<sessão-actual>
{"current_password": "<actual>", "new_password": "<nova, 12+ caracteres, forte>"}
```

Exige sessão de utilizador real (rejeita actores `api-key` e `dev-open`), verifica a password
actual, valida a força da nova, **revoga todas as sessões** e emite um alerta *"Admin password
alterada"*. A resposta inclui `{"relogin_required": true}`.

**Via de recuperação — quando ninguém consegue entrar:**

1. parar a API;
2. mover (não apagar) `backend-api/data/admin_users.json` para fora do directório — e **lembrar que
   existe `admin_users.json.bak`**, pelo que também esse deve ser movido, senão a recuperação pode
   ficar confusa;
3. garantir que `ADMIN_BOOTSTRAP_USER` e `ADMIN_BOOTSTRAP_PASSWORD` estão definidos, com password
   que passe a política de V.6.5;
4. arrancar a API — `ensure_bootstrap` encontra o depósito vazio e cria o utilizador;
5. confirmar nos registos a linha `"Utilizador bootstrap criado: <nome> (role=<papel>)"`;
6. **remover `ADMIN_BOOTSTRAP_PASSWORD` do `.env`** — cumprida a função, é apenas um segredo a mais
   guardado em texto simples.

Duas armadilhas menores no mesmo caminho:

* Se a password de *bootstrap* **falhar a política de força**, `upsert_user` levanta `ValueError`, o
  código regista `"Bootstrap admin falhou: <motivo>"` e **nenhum utilizador é criado**. O sintoma
  seguinte é `GET /admin/auth/status` a devolver `login_required: false` e o login a responder `503`
  com *"Login não configurado"*. Quem não ler os registos passa muito tempo à procura.
* `ADMIN_BOOTSTRAP_ROLE` é validado contra `VALID_ROLES` e, se for inválido, recai silenciosamente
  em `admin`. Convém verificar o papel efectivo em `GET /admin/auth/me` depois do primeiro login.

---

## V.11 Chaves de API (`X-API-Key`) e âmbitos (*scopes*)

### V.11.1 Duas formas de autenticar, para dois tipos de cliente

* **Sessão (`Authorization: Bearer dms1.…`)** — para **pessoas**. Curta, revogável, ligada a um nome
  de utilizador que aparece na auditoria.
* **Chave de API (`X-API-Key: <valor>`)** — para **máquinas**: *scripts* de manutenção, verificações
  de implantação, trabalhos automáticos. Não expira, não tem interface de login, e na auditoria
  aparece como actor `"api-key"`.

### V.11.2 O mapa de chaves para papéis

Em `backend-api/core/auth.py`:

```python
mapping: list[tuple[str, Role]] = [
    ("API_SECRET_KEY",          "admin"),
    ("API_SECRET_KEY_PREVIOUS", "admin"),
    ("API_OPS_KEY",             "ops"),
    ("API_CATALOG_KEY",         "catalog"),
    ("API_PEDIDOS_KEY",         "pedidos"),
    ("API_MENSAGENS_KEY",       "mensagens"),
]
```

Só as variáveis efectivamente definidas entram na lista, e a comparação é feita com
`secrets.compare_digest` (V.4.5). Duas observações de desenho:

* **`API_SECRET_KEY_PREVIOUS` existe para permitir rotação sem indisponibilidade.** Rodar uma chave
  compartilhada é normalmente traumático: no instante em que o servidor muda, todos os clientes
  antigos param. Com duas chaves aceites em simultâneo, o procedimento fica: (1) mover o valor
  actual para `API_SECRET_KEY_PREVIOUS`, (2) gerar um novo `API_SECRET_KEY`, (3) reiniciar, (4)
  actualizar os clientes ao seu ritmo, (5) apagar `API_SECRET_KEY_PREVIOUS`. Atenção a um detalhe
  importante: a chave *antiga* continua a autenticar como `admin`, mas **as sessões são assinadas
  sempre com o `API_SECRET_KEY` actual** (V.7.2) — mudar a chave principal invalida todos os
  *tokens* de sessão emitidos, o que obriga a novo login. Isso é desejável, mas convém saber antes.
* **Chaves por âmbito seguem o princípio do menor privilégio.** Um *script* que só publica catálogo
  recebe `API_CATALOG_KEY` e, se essa chave for exposta, o dano fica confinado ao catálogo: não lê
  mensagens de clientes nem pedidos de orçamento.

### V.11.3 A matriz de autorização

O papel é apenas o começo; a decisão real combina **papel × tabela × acção**.

Conjuntos definidos em `backend-api/core/auth.py`:

```python
CRUD_INFRA_BLOCKED = frozenset({
    "admin_audit_log", "outbox_events", "saga_instances",
    "idempotency_keys", "message_history",
})

SENSITIVE_BUSINESS_TABLES = frozenset({
    "contact_messages", "pedidos_orcamento", "encomendas_internas",
})
```

* **`CRUD_INFRA_BLOCKED`** — tabelas de infra-estrutura e auditoria **fora do CRUD genérico, para
  todos os papéis, incluindo `admin`**. A razão é a integridade da prova: se o papel `admin`
  pudesse editar `admin_audit_log` pelo endpoint genérico, o registo de auditoria deixaria de valer
  como registo. Só os caminhos internos da aplicação lá escrevem.
* **`SENSITIVE_BUSINESS_TABLES`** — dados pessoais e comerciais. Não basta ser "administrador de
  alguma coisa"; é preciso o papel dedicado (ou `admin`).

Comportamentos derivados:

| Papel | Catálogo | Pedidos/encomendas | Mensagens | Infra/auditoria | *Hard delete* |
|---|---|---|---|---|---|
| `admin` | sim | sim | sim | **não** | só fora das tabelas sensíveis |
| `catalog` | sim (`categories`, `modelos*`, `produtos*`, `modelo_cores`) | não | não | não | não |
| `pedidos` | não | sim | não | não | não |
| `mensagens` | não | não | sim (`contact_messages`) | não | não |
| `ops` | **não** | não | não | não | não |

O papel `ops` merece explicação: existe para **operações de sistema** (`/system`, saúde, manutenção)
e está explicitamente excluído de qualquer CRUD (`if role == "ops": return False` em
`role_can_access_table`). Há mesmo uma separação de funções nos dois sentidos: com `API_OPS_KEY`
definida, `require_ops` recusa `admin` e `require_admin` recusa `ops`. Quem opera a máquina não lê
os dados dos clientes; quem gere os dados não mexe na máquina. Testes:
`test_require_ops_blocks_admin_when_ops_configured` e `test_require_admin_blocks_ops_when_ops_configured`.

E a eliminação definitiva tem regras próprias:

```python
if action == "hard_delete":
    if role != "admin":
        raise HTTPException(status_code=403, detail="Hard delete só para admin.")
    if table in SENSITIVE_BUSINESS_TABLES:
        raise HTTPException(status_code=403, detail="Hard delete bloqueado em tabelas sensíveis.")
```

Ou seja: em `contact_messages`, `pedidos_orcamento` e `encomendas_internas`, **ninguém** apaga
fisicamente pelo CRUD genérico. Usa-se ocultação lógica (`visibilidade = false`), e a eliminação
verdadeira, quando é obrigação legal (direito ao apagamento do RGPD), passa pelo fluxo dedicado de
privacidade (`backend-api/routes/privacy.py`, com testes em
`backend-api/tests/test_privacy_erase.py`), que exige papel `admin` e deixa rasto.

### V.11.4 Coerência na interface

`filter_sidebar_for_role` filtra o menu lateral do backoffice conforme o papel. Não é uma medida de
segurança — a segurança é do lado do servidor, e um utilizador `catalog` que forjasse um pedido a
`/admin/contacto` receberia `403` de qualquer forma. É uma medida de **usabilidade honesta**: não
mostrar portas que se sabe estarem trancadas evita frustração e reduz erros.

### V.11.5 Quando não há chave nenhuma

```python
if not settings.api_key_required:
    return _attach(request, role="admin", actor="dev-open")

pairs = _key_roles()
if not pairs:
    raise HTTPException(status_code=503, detail="API key não configurada no servidor")
```

Em desenvolvimento sem `API_SECRET_KEY`, a API abre com o actor `dev-open` (e o arranque avisa:
*"API_SECRET_KEY não definido — endpoints admin abertos apenas em dev local"*). Em produção ou beta,
`api_key_required` é sempre verdadeiro, e sem chaves configuradas a resposta é `503` — indisponível,
nunca aberto. É outra vez *fail-closed*. Testes: `test_api_key_required_in_production`,
`test_api_key_required_in_beta`, `test_api_key_scopes_resolve`.

---

## V.12 SSRF (Server-Side Request Forgery) — o ataque; lista de permissões; `ssrf_guard.py`

### V.12.1 O ataque, explicado do zero

SSRF significa *Server-Side Request Forgery* — falsificação de pedido do lado do servidor. A ideia é
subtil e é por isso que aparece no top 10 da OWASP (*Open Web Application Security Project*, a
organização de referência em segurança de aplicações web).

Imagine-se uma funcionalidade inocente: "cole aqui o endereço de uma imagem e nós importamo-la".
O servidor recebe a URL e vai buscá-la. O atacante, em vez de uma imagem, escreve:

* `http://169.254.169.254/latest/meta-data/iam/security-credentials/` — em máquinas virtuais na
  nuvem, este endereço especial (só acessível *de dentro* da máquina) devolve credenciais da conta
  de serviço. Foi assim que aconteceu a fuga da Capital One em 2019, com dados de mais de 100
  milhões de pessoas.
* `http://127.0.0.1:6379/` — o Redis local, muitas vezes sem password porque "só é acessível
  localmente".
* `http://192.168.1.1/admin` — o router da rede interna.
* `http://localhost:8000/admin/...` — **a própria API**, e a partir de loopback, onde
  `peer_is_loopback` devolve `True` e o *gate* de secretária deixa de ser exigido (V.5.1).

O ponto essencial: o atacante não precisa de acesso à rede interna. Usa o servidor como
**intermediário confiável** — o servidor está dentro, e faz o pedido por ele. Firewalls de perímetro
não ajudam, porque o pedido origina-se legitimamente de dentro.

### V.12.2 A defesa: lista de permissões, não lista de proibições

Em `backend-api/core/ssrf_guard.py`:

```python
def assert_safe_outbound_url(url: str) -> str:
    """Rejeita URLs para loopback/RFC1918/metadata e hosts fora da allow-list."""
    parsed = urlparse((url or "").strip())
    if parsed.scheme not in ("https",):
        raise UnsafeUrlError("Apenas https permitido")
    host = (parsed.hostname or "").lower()
    if not host:
        raise UnsafeUrlError("Host em falta")
    if host not in allowed_fetch_hosts():
        raise UnsafeUrlError(f"Host não permitido: {host}")
    try:
        ip = ipaddress.ip_address(host)
        for net in _blocked_networks():
            if ip in net:
                raise UnsafeUrlError("IP privado/bloqueado")
    except ValueError:
        pass  # hostname não é IP literal — OK se na allow-list
    return url
```

Quatro decisões, todas defensáveis:

1. **Só `https`.** Elimina `http://`, e com ele esquemas exóticos que causam estragos noutras
   linguagens: `file:///etc/passwd`, `gopher://` (usado para falar com Redis), `dict://`, `ftp://`.
2. **Lista de permissões (*allow-list*) e não de proibições (*deny-list*).** É a decisão mais
   importante. Uma lista de proibições ("bloqueia 127.0.0.1, bloqueia 169.254.169.254…") perde
   sempre, porque existem infinitas formas de escrever o mesmo endereço: `127.1`, `0177.0.0.1`
   (octal), `2130706433` (decimal), `[::ffff:127.0.0.1]` (IPv6 mapeado), ou um domínio público que
   *resolve* para `127.0.0.1`. Uma lista de permissões inverte o ónus: se não está na lista, é não.
3. **Redes privadas bloqueadas** — para o caso de a URL usar um endereço IP literal:
   `0.0.0.0/8`, `10.0.0.0/8`, `127.0.0.0/8`, `169.254.0.0/16` (onde vivem os serviços de metadados
   das nuvens), `172.16.0.0/12`, `192.168.0.0/16`, `::1/128`, `fc00::/7`, `fe80::/10`.
4. **Lista com valores por omissão sensatos, ampliável por ambiente.** `SSRF_ALLOW_HOSTS` aceita uma
   lista separada por vírgulas, e a esta juntam-se sempre os anfitriões de que o *stack* precisa:
   `api.cloudflare.com`, `challenges.cloudflare.com` (Turnstile), `hooks.slack.com`, `discord.com`,
   `discordapp.com`, `api.axiom.co` e os pontos de entrada regionais do Axiom, e `ntfy.sh`.

### V.12.3 Onde é usado hoje, e porque é uma defesa preventiva

Actualmente o único consumidor é o envio de alertas (`backend-api/core/alerts.py`, V.9.5). Não há,
neste momento, nenhuma funcionalidade em que um utilizador forneça uma URL para o servidor buscar —
e é *precisamente* por isso que o guarda existe agora: quando essa funcionalidade aparecer (importar
imagens por URL, integrar um serviço de transportes, chamar um *webhook* configurado pelo cliente),
a defesa já está escrita, testada e disponível numa linha. Escrever o guarda **antes** de haver a
vulnerabilidade é a diferença entre segurança por desenho e segurança por remendo.

Teste: `test_ssrf_blocks_private_and_unknown_hosts`, em
`backend-api/tests/test_path_guard_hardening.py`.

### V.12.4 Limitação conhecida

O guarda valida o **nome** do anfitrião, não o endereço IP para que esse nome resolve. Em teoria, um
domínio que constasse da lista de permissões e resolvesse para `127.0.0.1` (ataque de *DNS
rebinding*) passaria. Na prática o risco é remoto, porque a lista só contém domínios de fornecedores
conhecidos que não controlamos nem o atacante controla. A mitigação completa exigiria resolver o
nome, validar o endereço obtido e ligar directamente a esse endereço — algo a considerar se algum dia
existir uma funcionalidade em que o utilizador final define URLs.

---

## V.13 CORS — o que é e o que o Diomika configura

### V.13.1 A política de mesma origem

Os navegadores impõem, desde os anos 90, a *same-origin policy* (política de mesma origem): código
JavaScript de uma página em `https://a.com` não pode ler respostas de `https://b.com`. Uma "origem"
é a combinação **esquema + domínio + porta** — `https://diomika.com` e `http://diomika.com` são
origens diferentes, tal como `https://diomika.com` e `https://api.diomika.com`.

Sem esta regra, qualquer sítio malicioso que se visitasse poderia, em silêncio, fazer pedidos ao
*homebanking* aproveitando os *cookies* de sessão já presentes no navegador, e ler as respostas.

### V.13.2 O que é CORS

CORS significa *Cross-Origin Resource Sharing* — partilha de recursos entre origens. É o mecanismo
que permite **relaxar deliberadamente** a política de mesma origem. Funciona por cabeçalhos de
resposta: o servidor B declara "aceito que a origem A leia as minhas respostas", através de
`Access-Control-Allow-Origin`.

Para pedidos que não sejam triviais (métodos como `PUT`, `DELETE`, ou cabeçalhos personalizados), o
navegador faz primeiro um **pedido preliminar** (*preflight*) com o método `OPTIONS`, a perguntar
"posso?". Só depois envia o pedido verdadeiro.

Dois mal-entendidos frequentes, que vale a pena desfazer:

* **CORS não protege o servidor.** É uma regra imposta pelo *navegador*. Um pedido feito com `curl`,
  Python ou Postman ignora CORS por completo. A protecção do servidor é a autenticação (V.7, V.11).
  CORS protege os *utilizadores* de outros sítios.
* **CORS permissivo não é "uma falha" por si só** — mas combinado com autenticação baseada em
  *cookies* torna-se perigoso. O Diomika usa `Authorization: Bearer`, que não é enviado
  automaticamente pelo navegador, o que reduz muito esta classe de risco.

### V.13.3 A configuração real

Em `backend-api/main.py`:

**Produção final:**

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,      # lista exacta de CORS_ORIGINS
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=ALLOWED_CORS_HEADERS,
)
```

**Beta privada** (endereços gerados dinamicamente pelos túneis e pelo Cloudflare Pages):

```python
allow_origin_regex=r"https://.*\.(trycloudflare\.com|pages\.dev)$"
```

**Desenvolvimento:**

```python
allow_origin_regex=r"http://(localhost|127\.0\.0\.1)(:\d+)?"
allow_methods=["*"], allow_headers=["*"]
```

A lista de cabeçalhos aceitos é explícita (`backend-api/core/middleware.py`):

```python
ALLOWED_CORS_HEADERS = [
    "Accept", "Accept-Language", "Content-Language", "Content-Type",
    "Authorization", "X-API-Key", "Idempotency-Key", "X-Request-Id",
]
```

Cada um justifica-se: `Authorization` para as sessões, `X-API-Key` para as chaves de máquina,
`Idempotency-Key` para evitar submissões duplicadas nos formulários públicos, `X-Request-Id` para
correlacionar registos entre cliente e servidor. Não se usou `["*"]` em produção porque uma lista
fechada torna visível qualquer cabeçalho novo que alguém queira introduzir.

Repare-se que `X-Diomika-Desktop` **não** está na lista, e é correcto: esse cabeçalho nunca é
enviado por uma página de navegador, é injectado pelo processo Node.js do Electron (V.4.4), que não
está sujeito a CORS.

### V.13.4 Validação no arranque

```python
if not self.is_beta and (
    not self.cors_origins
    or any("localhost" in origin or "127.0.0.1" in origin for origin in self.cors_origins)
):
    missing.append("CORS_ORIGINS (domínios de produção)")
```

Em produção final, a API **recusa-se a arrancar** se `CORS_ORIGINS` estiver vazia ou contiver
endereços locais. Isto fecha a porta ao erro mais comum de implantação: promover para produção um
`.env` de desenvolvimento e deixar `http://localhost:5173` na lista de origens aceites.

### V.13.5 O parente próximo: `ALLOWED_HOSTS`

CORS trata da origem de *quem chama*. O `TrustedHostMiddleware` trata do cabeçalho `Host`, isto é,
do domínio *pelo qual* o servidor foi chamado:

```python
allowed_hosts = [h.strip() for h in (os.getenv("ALLOWED_HOSTS") or "").split(",") if h.strip()]
app.add_middleware(TrustedHostMiddleware, allowed_hosts=allowed_hosts or ["invalid.invalid"])
```

Defende contra ataques de envenenamento de cabeçalho `Host` — em que um pedido chega com
`Host: atacante.com` e a aplicação, ao construir URLs absolutas (por exemplo num email de
notificação), acaba a apontar para o domínio do atacante. O comentário no código explicita o
princípio: *"Fail-closed: sem hosts → middleware com lista vazia rejeita tudo"*, e
`validate_startup` já exige a variável.

---

## V.14 Limitação de ritmo (*rate limiting*) e Redis

### V.14.1 O conceito e o algoritmo escolhido

Limitar o ritmo é impor "no máximo N pedidos por janela de tempo, por cliente". Serve três
propósitos distintos: travar força bruta (V.9), travar extracção massiva de dados (*scraping*) e
travar negação de serviço barata.

O Diomika usa uma **janela deslizante** (*sliding window*): guarda os carimbos temporais dos pedidos
recentes e conta quantos caem dentro da janela. É mais justo do que a "janela fixa", que sofre do
problema clássico de permitir o dobro dos pedidos na fronteira entre janelas (59 pedidos ao segundo
59 e outros 59 ao segundo 61).

### V.14.2 Limites por camada

Em `backend-api/core/rate_limit.py`:

```python
def _limits_for_path(method: str, path: str) -> tuple[str, int]:
    if path.startswith("/admin") or path.startswith("/system"):
        return "admin", int(os.getenv("RATE_LIMIT_ADMIN_PER_MIN", "300"))
    if _is_public_catalog_read(method, path):
        return "catalog", int(os.getenv("RATE_LIMIT_CATALOG_PER_MIN", "600"))
    return "global", int(os.getenv("RATE_LIMIT_GLOBAL_PER_MIN", "120"))
```

| Contentor | Limite por minuto | Racional |
|---|---|---|
| `catalog` (leituras públicas `GET`) | 600 | Uma pessoa a navegar na loja gera muitos pedidos legítimos em pouco tempo. Um limite apertado partiria a experiência. |
| `admin` | 300 | O backoffice faz muitas leituras e escritas por sessão de trabalho. O comentário no código conta a história: *"Backoffice faz muitas leituras/escritas; 30/min partia o uso normal."* |
| `global` (o resto: formulários, mutações) | 120 | Estes são os endpoints caros e sensíveis. |

Além disto:

* **Isenções**: `/health`, `/health/ready`, `/api/docs`, `/api/redoc`, `/openapi.json` — as
  verificações de saúde não devem ser bloqueadas, senão a monitorização provoca o incidente que
  devia detectar.
* **Loopback isento em `/admin` e `/system`**: o backoffice a correr na própria máquina não é
  limitado (*"Admin/system já é localhost-only em produção — não limitar o backoffice local"*).
* **Limites por endpoint**, mais apertados, aplicados na própria rota: o formulário de contacto usa
  `rate_limit(request, "contact_form", max_calls=5, window_seconds=60)`.
* **Janela configurável**: `RATE_LIMIT_WINDOW_SECONDS`, com mínimo forçado de 10 segundos.

Testes: `test_tiered_limits`, `test_catalog_rate_limit_higher_than_global`, `test_catalog_read_detection`.

### V.14.3 Identificar o cliente sem se deixar enganar

Toda a limitação de ritmo depende de saber *quem* está a pedir. Se o atacante controlar esse
identificador, o mecanismo é decorativo.

```python
def get_client_ip(request: Request) -> str:
    if trust_proxy_headers() and _peer_is_trusted_proxy(request):
        forwarded_for = request.headers.get("x-forwarded-for") or ...
        if forwarded_for:
            first_ip = forwarded_for.split(",")[0].strip()
            if first_ip:
                return first_ip
        ...
    return request.client.host if request.client else "unknown"
```

O cabeçalho `X-Forwarded-For` só é considerado se **duas** condições se verificarem: `TRUST_PROXY`
estar activo *e* a ligação vir realmente de um dos endereços em `TRUSTED_PROXY_IPS` (que aceita
notação CIDR, isto é, blocos de endereços como `10.0.0.0/8`). Sem isto, qualquer pessoa contornaria
todos os limites acrescentando `X-Forwarded-For: <ip-aleatório>` a cada pedido.

A configuração de arranque reforça: com `TRUST_PROXY=1` e sem `TRUSTED_PROXY_IPS`, a API não
arranca em produção final. Testes: `test_trusted_proxy_ignores_spoofed_xff_without_trusted_peer`,
`test_trusted_proxy_uses_xff_from_trusted_peer`, `test_trusted_proxy_cidr`,
`test_production_trusted_proxy_ips_required_when_trust_proxy`.

### V.14.4 Redis e o problema dos múltiplos processos

O mesmo problema de V.7.6: com quatro processos de trabalho e contadores em memória, o limite
efectivo passaria a ser quatro vezes o configurado, de forma imprevisível.

A implementação com Redis usa um **conjunto ordenado** (*sorted set*), onde a pontuação de cada
elemento é o carimbo temporal, e executa quatro comandos num só *pipeline* (uma ida e volta à rede):

```python
pipe.zremrangebyscore(rkey, 0, now - window_seconds)   # 1. esquecer os antigos
pipe.zcard(rkey)                                       # 2. contar os que restam
pipe.zadd(rkey, {f"{now}:{os.getpid()}": now})         # 3. registar este pedido
pipe.expire(rkey, window_seconds + 5)                  # 4. auto-limpeza da chave
_, count, _, _ = pipe.execute()
return int(count) < max_calls
```

Três detalhes que revelam cuidado: o identificador do processo entra no nome do elemento para que
dois processos no mesmo microssegundo não se sobreponham; o `expire` garante que chaves de clientes
que desapareceram não ficam a ocupar memória para sempre; e o `zremrangebyscore` faz a limpeza da
janela em cada passagem, sem necessidade de tarefa de manutenção.

A degradação é graciosa: `_record_and_check_redis` devolve `None` se o Redis falhar, e
`_record_and_check` recorre à contagem em memória. Um Redis em baixo torna os limites menos precisos,
mas não derruba a API nem abre a porta.

O cliente Redis é criado de forma tardia e tolerante (`_get_redis`), com `socket_connect_timeout=1.5`
e um `ping` de confirmação. Se `REDIS_URL` não estiver definida, nem se tenta.

### V.14.5 Tamanho do corpo do pedido

Complemento indispensável da limitação de ritmo — em `backend-api/core/middleware.py`:

```python
class BodySizeLimitMiddleware(BaseHTTPMiddleware):
    MAX_BYTES = int(os.getenv("MAX_REQUEST_BODY_BYTES") or str(2 * 1024 * 1024))  # 2 MiB
```

Sem isto, 120 pedidos por minuto continuariam a permitir enviar gigabytes. A verificação usa o
cabeçalho `Content-Length` e responde `413` ("payload demasiado grande"), ou `400` se o valor for
inválido.

O comentário do código documenta uma armadilha real que já custou tempo:

> *"Não consumir `request.stream()` aqui: `BaseHTTPMiddleware` + re-inject do body parte o parsing
> JSON (login/admin POST → 422 body missing)."*

É o tipo de nota que salva a próxima pessoa de reintroduzir uma avaria já resolvida. Existem também
limites de domínio na mesma linha de pensamento: `MAX_PUBLIC_BODY_LINES = 50` e
`MAX_LINE_QUANTITY = 50_000`, que impedem um pedido de orçamento com dez mil linhas.

---

## V.15 Turnstile vs CAPTCHA clássico

### V.15.1 O CAPTCHA clássico e os seus problemas

CAPTCHA significa *Completely Automated Public Turing test to tell Computers and Humans Apart* —
teste de Turing público e completamente automatizado para distinguir computadores de humanos. Na
prática: as letras distorcidas, e mais tarde as grelhas de "selecione todos os semáforos".

Os problemas acumularam-se:

* **Acessibilidade** — quem tem baixa visão, dislexia ou dificuldades motoras é penalizado. Áudio
  alternativo raramente funciona bem.
* **Fricção** — cada segundo gasto num CAPTCHA converte-se em formulários abandonados. Num
  formulário de orçamento, isso é receita perdida.
* **Eficácia decrescente** — a visão por computador resolve hoje muitos CAPTCHAs melhor do que
  pessoas, e existem serviços que resolvem CAPTCHAs por cêntimos usando trabalho humano.
* **Privacidade** — as soluções mais eficazes basearam-se em perfilar o comportamento do
  utilizador na web, com implicações sérias de protecção de dados.

### V.15.2 O que o Turnstile faz de diferente

O Cloudflare Turnstile substitui o desafio visual por um conjunto de **desafios não interactivos**
executados no navegador: verificações de coerência da plataforma, provas de trabalho leves, sinais
de comportamento, atestação de integridade quando disponível. Para a maioria dos visitantes não há
nada para clicar — o *widget* apenas confirma.

O fluxo tem duas metades, e a separação é o essencial:

1. **No navegador**, o *widget* usa a **chave de sítio** (`VITE_TURNSTILE_SITE_KEY`), que é
   **pública** por natureza (vai no código do *frontend*), e produz um *token* de uso único.
2. **No servidor**, a API envia esse *token* junto com a **chave secreta**
   (`TURNSTILE_SECRET_KEY`, que nunca sai do servidor) para
   `https://challenges.cloudflare.com/turnstile/v0/siteverify`, e só confia no resultado devolvido
   por essa chamada.

O passo 2 é o que torna o mecanismo útil. Um *widget* que se limitasse a validar no navegador seria
trivialmente contornável — bastaria não executar o JavaScript.

### V.15.3 A implementação

Em `backend-api/utils/turnstile.py`:

```python
def verify_turnstile(token: str | None, remote_ip: str | None = None) -> None:
    settings = get_settings()
    secret = _resolve_secret(settings)

    if not secret:
        if settings.is_production:
            raise ValueError("Verificação anti-spam indisponível")   # produção: fail-closed
        return                                                        # dev: passa
    if not token:
        raise ValueError("Verificação anti-spam em falta")
    ...
    resp = requests.post(
        "https://challenges.cloudflare.com/turnstile/v0/siteverify",
        data=payload, timeout=10, verify=_VERIFY,
    )
    data = resp.json()
    if not data.get("success"):
        raise ValueError("Verificação anti-spam inválida")
```

Notas de implementação:

* **`verify=_VERIFY` com `certifi`** — a validação do certificado TLS usa um conjunto de autoridades
  de certificação actualizado, em vez de depender do que o sistema operativo tiver.
* **Existe versão assíncrona** — `verify_turnstile_async` corre a chamada HTTP síncrona num *thread*
  (`asyncio.to_thread`) para não bloquear o *event loop* do servidor. Numa aplicação assíncrona, uma
  chamada de rede bloqueante trava *todos* os pedidos em curso; este detalhe é diferença entre um
  servidor responsivo e um servidor que congela sob carga.
* **O endereço IP do cliente é enviado** (`remoteip`), o que melhora a decisão da Cloudflare.

### V.15.4 Chaves de teste: úteis em desenvolvimento, proibidas em produção

A Cloudflare publica chaves de teste que sempre passam (ou sempre falham), ideais para
desenvolvimento e testes automáticos. O perigo óbvio é chegarem a produção. Por isso estão listadas
explicitamente em `backend-api/core/config.py`:

```python
TURNSTILE_TEST_KEYS = frozenset({...})   # valores públicos de teste da Cloudflare
```

e a validação de arranque é intransigente:

```python
if self._turnstile_is_test_key() and not self.is_beta:
    print("ERRO: Turnstile usa chaves de teste — producao exige chaves reais.", file=sys.stderr)
    sys.exit(1)
```

Além disso, `TURNSTILE_SECRET_KEY` consta da lista de variáveis obrigatórias em produção. Testes:
`test_production_rejects_turnstile_test_keys`, `test_production_startup_requires_turnstile`,
`test_turnstile_requires_secret_in_production`.

Em beta, `TURNSTILE_BETA_USE_TEST` permite usar deliberadamente a chave de teste (para que os testes
automáticos de ponta a ponta funcionem), e há um *token* fictício aceito nesse modo. Toda esta
flexibilidade está confinada a `is_beta`, e produção final não a tem.

### V.15.5 Turnstile não anda sozinho

O formulário de contacto (`backend-api/routes/contact.py`) empilha quatro defesas independentes:

1. **Limitação de ritmo** — `rate_limit(request, "contact_form", max_calls=5, window_seconds=60)`.
2. **Chave de idempotência** — em produção, `Idempotency-Key` é **obrigatória**. Evita que um duplo
   clique, ou uma repetição automática do cliente, crie duas mensagens iguais. Respostas já
   processadas são devolvidas da cache em vez de reexecutadas.
3. **Campo-armadilha (*honeypot*)** — o modelo tem um campo `website` que a interface esconde por
   CSS. Um humano nunca o preenche; muitos robôs preenchem todos os campos que encontram. Se vier
   preenchido, a resposta é `400 Pedido inválido` e o evento é registado. Custo zero,
   zero fricção para o utilizador, e apanha uma quantidade surpreendente de tráfego automático.
   Testes: `test_honeypot_empty_passes`, `test_honeypot_filled_blocks`.
4. **Turnstile**.

E, a montante de tudo, a validação com Pydantic impõe limites de comprimento (`nome` 2-100,
`mensagem` 10-5000, email validado sintacticamente) e normalização de texto Unicode
(`backend-api/core/text_safe.py`, `normalize_text`, com teste `test_normalize_text_nfc`) — o que
evita truques com caracteres visualmente idênticos mas com códigos diferentes.

---

## V.16 `SECURITY_LOCKDOWN`

### V.16.1 O interruptor de emergência

Há momentos em que a resposta correcta a um incidente não é analisar: é **parar**. Suspeita de fuga
de credenciais, ataque em curso, comportamento inexplicável, exposição acidental de um endpoint. Sem
um mecanismo preparado, a única alternativa é desligar o servidor — o que também derruba a loja
pública e destrói a visibilidade sobre o que está a acontecer.

`SECURITY_LOCKDOWN` é esse mecanismo. Em `backend-api/core/path_guard.py`:

```python
def lockdown_active() -> bool:
    return (os.getenv("SECURITY_LOCKDOWN") or "").strip().lower() in ("1", "true", "yes")
```

E o efeito, no ponto mais exterior da aplicação:

```python
if lockdown_active():
    if path in ("/health", "/health/ready") and request.method == "GET":
        return await call_next(request)
    if path.startswith(_PRIVILEGED_PREFIXES) or any(
        path.startswith(p) for p in _PUBLIC_MUTATE_PREFIXES
    ):
        return JSONResponse(
            status_code=503,
            content={"detail": "SECURITY_LOCKDOWN activo — operações suspensas."},
        )
```

### V.16.2 O que fica de pé e o que cai

| Caminho | Em lockdown |
|---|---|
| `GET /health`, `GET /health/ready` | **Funciona** — a monitorização continua a ver o sistema. |
| `/admin/*`, `/system/*`, `/health/detail` | `503` — toda a superfície administrativa fecha. |
| `/contacto`, `/orcamentos` | `503` — as mutações públicas fecham. |
| `GET /categorias`, `GET /catalogo/*` | **Funciona** — a loja continua visível. |

A escolha é cirúrgica e merece ser apreciada: **a loja não deixa de existir, mas o sistema deixa de
aceitar dados novos e deixa de expor a administração**. Um visitante que esteja a ver o catálogo não
percebe nada; um atacante perde acesso a tudo o que interessa. E, crucialmente, os endpoints de
saúde continuam a responder, pelo que a monitorização externa não dispara falsos alarmes de "sítio
em baixo" enquanto a equipa investiga.

Vale a pena notar que o lockdown é avaliado **antes** de qualquer verificação de acesso privilegiado
e independentemente do ambiente: funciona em desenvolvimento, em beta e em produção.

### V.16.3 Como se activa, e o aviso no arranque

```
# no .env do servidor
SECURITY_LOCKDOWN=1
```

e reiniciar a API. Desactiva-se removendo a linha (ou pondo `0`) e reiniciando.

Como o estado é lido do ambiente em cada pedido, é impossível "esquecer" que está activo sem que o
sistema o diga: `validate_startup` imprime um aviso explícito em produção final:

```
AVISO: SECURITY_LOCKDOWN=1 — API em modo incidente (só /health;/health/ready).
```

Este é um exemplo de bom desenho de estados perigosos: o modo excepcional é fácil de activar,
impossível de esquecer, e não requer alterações de código sob pressão. Teste:
`test_lockdown_blocks_admin`.

---

## V.17 Cabeçalhos de segurança: HSTS, `nosniff`, opções de *frame* e restantes

Cabeçalhos de resposta são instruções que o servidor dá ao navegador sobre como tratar o conteúdo.
Custam bytes e evitam classes inteiras de ataque. Existem dois conjuntos no Diomika: os da **API**
(`backend-api/core/middleware.py`) e os do **sítio público** (`frontend-web/public/_headers`, lido
pelo Cloudflare Pages).

### V.17.1 Os cabeçalhos que a API envia sempre

```python
response.headers["X-Content-Type-Options"] = "nosniff"
response.headers["X-Frame-Options"] = "DENY"
response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
response.headers["Cross-Origin-Opener-Policy"] = "same-origin"
response.headers["Cross-Origin-Resource-Policy"] = "same-site"
```

**`X-Content-Type-Options: nosniff`.** Historicamente, os navegadores tentavam "adivinhar" o tipo de
um ficheiro olhando para o seu conteúdo (*MIME sniffing*), ignorando o `Content-Type` declarado. Isso
criou um ataque elegante: enviar um ficheiro declarado como `text/plain` mas cujo conteúdo parece
HTML com JavaScript; o navegador adivinha "isto é HTML" e executa o script. `nosniff` desliga a
adivinhação — o `Content-Type` declarado é lei. MIME significa *Multipurpose Internet Mail
Extensions*, a norma que originalmente classificava anexos de email e que hoje classifica todo o
conteúdo na web.

**`X-Frame-Options: DENY`.** Impede que a resposta seja embutida num `<iframe>` noutro sítio. Sem
isto, um atacante embute a página real, sobrepõe-lhe elementos visuais transparentes, e as
"pancadas" do utilizador vão para a página escondida — é o **clickjacking**. `DENY` proíbe qualquer
enquadramento, mesmo do próprio domínio.

**`Referrer-Policy: strict-origin-when-cross-origin`.** O cabeçalho `Referer` (com a célebre falta
de ortografia na norma original) diz ao destino de onde vem o visitante. Se a URL de origem contiver
informação sensível — um identificador de pedido, um *token* —, ela fuga para terceiros. Esta
política envia a URL completa dentro do mesmo sítio, envia apenas a origem (domínio) para outros
sítios em HTTPS, e não envia nada quando se desce de HTTPS para HTTP.

**`Permissions-Policy: camera=(), microphone=(), geolocation=()`.** Declara que esta resposta não
precisa de câmara, microfone nem localização. As listas vazias significam "ninguém, nem esta página
nem nada nela embutido". É uma declaração de intenções verificável pelo navegador.

**`Cross-Origin-Opener-Policy: same-origin`.** Corta a ligação entre janelas de origens diferentes.
Sem isto, uma página que abra outra mantém uma referência (`window.opener`) que pode ser abusada.

**`Cross-Origin-Resource-Policy: same-site`.** Impede que outros sítios incluam estes recursos,
mitigando ataques de canal lateral do tipo Spectre. Curiosidade útil: o *proxy* do Electron
**remove** este cabeçalho e o COOP das respostas que reenvia (`delete outHeaders[...]` em
`main.cjs`), porque a interface é servida de `127.0.0.1` e os cabeçalhos, pensados para a web
pública, bloqueariam o funcionamento normal da aplicação de secretária.

### V.17.2 Só em produção: HSTS e CSP na API

```python
if get_settings().is_production:
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains; preload"
    response.headers["Content-Security-Policy"] = "default-src 'none'; frame-ancestors 'none'"
```

**HSTS — HTTP Strict Transport Security.** Resolve um problema concreto: um utilizador que escreve
`diomika.com` na barra de endereços faz, tipicamente, um primeiro pedido em `http://`, que é
redireccionado para `https://`. Esse primeiro pedido em texto simples é a janela para um ataque de
homem-no-meio (interceptar o redireccionamento e servir uma versão falsa do sítio — a ferramenta
clássica chama-se `sslstrip`).

HSTS diz ao navegador: *"durante os próximos 31 536 000 segundos (um ano), nunca me contactes em
`http://`; converte para `https://` antes de sair de casa."* A partir da primeira visita, a janela
fecha-se.

* **`includeSubDomains`** — aplica a regra a todos os subdomínios. Cuidado real: se algum
  subdomínio interno só funcionar em HTTP, deixa de estar acessível nos navegadores que já viram o
  cabeçalho.
* **`preload`** — sinaliza a intenção de entrar na lista que os navegadores trazem **embutida**, o
  que protege até a *primeiríssima* visita. Aviso importante: entrar nessa lista é fácil, sair é
  lento (meses, à velocidade das versões dos navegadores). Só se deve activar quando há certeza de
  que todo o domínio e subdomínios servem HTTPS para sempre.

Estar limitado a `is_production` é correcto: enviar HSTS em desenvolvimento faria o navegador
recusar-se a falar com `http://localhost`, um problema irritante e difícil de diagnosticar.

**CSP na API — `default-src 'none'; frame-ancestors 'none'`.** CSP significa *Content Security
Policy* — política de segurança de conteúdo. Numa API que devolve apenas JSON, a política pode ser a
mais restritiva possível: *nada* pode ser carregado (`default-src 'none'`) e a resposta não pode ser
enquadrada por ninguém (`frame-ancestors 'none'`, a versão moderna de `X-Frame-Options`). Se alguma
resposta da API for alguma vez interpretada como HTML por um navegador — por engano ou por ataque —,
não conseguirá carregar scripts, imagens, estilos ou tipos de letra.

### V.17.3 A CSP do sítio público

Em `frontend-web/public/_headers`, aplicada pelo Cloudflare Pages a todos os caminhos (`/*`), com os
mesmos cabeçalhos base mais uma CSP detalhada. Directiva por directiva:

| Directiva | Valor | Leitura |
|---|---|---|
| `default-src` | `'self'` | Por omissão, só recursos do próprio domínio. |
| `script-src` / `script-src-elem` | `'self' https://challenges.cloudflare.com` | Scripts próprios e o *widget* Turnstile. Sem `'unsafe-inline'` e sem `'unsafe-eval'` — o que significa que não há scripts embutidos no HTML, uma disciplina que elimina o vector principal de XSS (*cross-site scripting*). |
| `connect-src` | `'self'`, `https://*.supabase.co`, `challenges.cloudflare.com`, `https://api.diomika.com`, PostHog | Destinos permitidos para chamadas de rede do JavaScript. Reflecte exactamente a arquitectura: base de dados, verificação anti-spam, API própria, produto de análise. |
| `img-src` | `'self' data: blob: https://*.supabase.co https://*.r2.dev` | Imagens locais, embutidas, geradas no navegador, e dos dois *backends* de armazenamento (Supabase Storage e Cloudflare R2 — ver VI.6). |
| `style-src` | `'self'` | Folhas de estilo próprias apenas. |
| `frame-src` | `https://challenges.cloudflare.com` | O único enquadramento permitido é o do Turnstile. |
| `font-src` | `'self' data:` | Tipos de letra locais ou embutidos. |
| `base-uri` | `'self'` | Impede que um `<base>` injectado reescreva todos os caminhos relativos da página. |
| `form-action` | `'self'` | Impede que um formulário injectado submeta credenciais para outro domínio. |
| `object-src` | `'none'` | Sem Flash, Java ou `<embed>` — tecnologias obsoletas e historicamente vulneráveis. |
| `frame-ancestors` | `'none'` | Ninguém enquadra o sítio. |
| `upgrade-insecure-requests` | — | Qualquer referência a `http://` é automaticamente convertida para `https://`. |

O ficheiro define ainda `Cache-Control: public, max-age=31536000, immutable` para `/assets/*`. Isto é
seguro porque a ferramenta de compilação (Vite) gera nomes com *hash* do conteúdo: um ficheiro
alterado tem nome novo, logo nunca há risco de servir uma versão obsoleta durante um ano.

### V.17.4 `X-Request-Id`: observabilidade que ajuda a investigar

`RequestIdMiddleware` aceita um `X-Request-Id` do cliente ou gera um UUID (*Universally Unique
Identifier*), coloca-o em `request.state` e devolve-o na resposta. Esse identificador aparece nos
registos estruturados, nas entradas de `admin_audit_log` e nos alertas. Não é uma medida de
segurança em si, mas é o que transforma "houve um problema" em "houve este problema, neste pedido, a
esta hora, deste actor" — e a capacidade de investigar é parte inseparável de segurança.

---

# Parte VI — Dados (Supabase / PostgreSQL / Storage)

## VI.1 O que é uma base de dados relacional

### VI.1.1 O modelo

Uma base de dados relacional guarda informação em **tabelas**. Uma tabela é uma grelha:

* as **colunas** definem os campos e o seu tipo (`nome` é texto, `created_at` é data-hora, `linhas`
  é JSON);
* as **linhas** (ou registos) são as ocorrências concretas — um pedido de orçamento, uma categoria.

O modelo foi formalizado por Edgar Codd em 1970 e a palavra "relacional" não se refere às ligações
entre tabelas (erro comum), mas ao conceito matemático de *relação* — uma tabela *é* uma relação
entre valores.

### VI.1.2 Chaves

**Chave primária (*primary key*)** — a coluna que identifica univocamente cada linha. No Diomika é
sempre um UUID gerado pela base de dados:

```sql
id uuid PRIMARY KEY DEFAULT gen_random_uuid()
```

UUID significa *Universally Unique Identifier* — 128 bits de aleatoriedade, escritos como
`3f2a9c1e-…`. A alternativa clássica seria um número sequencial (1, 2, 3…), e há uma razão de
segurança forte para preferir UUID: identificadores sequenciais são **adivinháveis**. Com `id=41`,
qualquer pessoa tenta `40` e `42`. É precisamente o ataque IDOR de V.1.2. Com UUID, adivinhar é
impraticável. (Nota importante: isto **não substitui** o controlo de acesso — é uma camada
adicional, e os testes em `backend-api/tests/test_idor.py` verificam que o controlo existe mesmo.)

**Chave estrangeira (*foreign key*)** — uma coluna que aponta para a chave primária de outra tabela,
e cuja validade a base de dados garante:

```sql
id_modelo uuid NOT NULL REFERENCES modelos_almofadas(id) ON DELETE CASCADE
```

Isto diz duas coisas. Primeiro: é **impossível** inserir uma cor cujo modelo não exista — a base de
dados recusa. Segundo: `ON DELETE CASCADE` significa que apagar um modelo apaga automaticamente as
suas cores, evitando "linhas órfãs". Uma variante mais suave aparece noutro sítio:

```sql
id_paleta uuid REFERENCES paletas_cores(id) ON DELETE SET NULL
```

Aqui, apagar a paleta não apaga o modelo: apenas lhe retira a paleta. A escolha entre `CASCADE` e
`SET NULL` é uma decisão de modelo de domínio ("as cores pertencem ao modelo; a paleta é uma
referência opcional") expressa em SQL.

### VI.1.3 Restrições (*constraints*)

Regras que a base de dados impõe, independentemente do código que lhe fala. É a diferença entre
"esperamos que os dados estejam correctos" e "os dados **estão** correctos".

```sql
-- Unicidade
ALTER TABLE categories ADD CONSTRAINT categories_slug_key UNIQUE (slug);
UNIQUE (id_modelo, numero)          -- unicidade combinada

-- Obrigatoriedade
ALTER TABLE categories ALTER COLUMN slug SET NOT NULL;

-- Validação de valores
ADD CONSTRAINT categories_carrinho_step_check
  CHECK (carrinho_step IS NULL OR carrinho_step > 0);

-- Regra de exclusividade: a cor pertence a um modelo OU a uma paleta, nunca aos dois
ADD CONSTRAINT modelo_cores_owner_check CHECK (
    (id_modelo IS NOT NULL AND id_paleta IS NULL) OR
    (id_modelo IS NULL AND id_paleta IS NOT NULL)
);
```

Esta última é particularmente elegante: uma regra de negócio real ("uma cor é de um modelo ou de uma
paleta") transformada numa garantia matemática. Nenhum caminho de código, presente ou futuro, com ou
sem erro, consegue criar uma linha inconsistente.

Há também uma decisão explícita **no sentido contrário**, documentada no SQL:

```sql
-- Validação de tipo_catalogo feita na API (CATALOG_TYPES) — sem CHECK estático na BD
ALTER TABLE categories DROP CONSTRAINT IF EXISTS categories_tipo_catalogo_check;
```

Porquê? Porque `tipo_catalogo` cresce com o produto (almofadas, assentos, e o que vier). Um `CHECK`
estático obrigaria a uma migração de base de dados para cada novo tipo. A validação vive em
`backend-api/models/catalog_registry.py`, onde o registo de tipos é a fonte única de verdade. É um
compromisso conscientemente assumido, e o comentário no SQL existe para que ninguém o "corrija" por
engano seis meses depois.

### VI.1.4 Índices

Um índice é uma estrutura auxiliar (tipicamente uma árvore B) que permite encontrar linhas sem ler a
tabela inteira. A analogia é o índice de um livro: procurar "segurança" no índice é instantâneo;
folhear 400 páginas não é.

```sql
CREATE INDEX IF NOT EXISTS idx_pedidos_orcamento_created ON pedidos_orcamento (created_at DESC);
CREATE INDEX IF NOT EXISTS idx_contact_messages_email    ON contact_messages (lower(email));
CREATE INDEX IF NOT EXISTS idx_categories_visible_tipo
  ON categories (tipo_catalogo) WHERE visibilidade = true;
```

Três variedades no mesmo excerto:

* **Índice simples descendente** — para "mostrar os pedidos mais recentes primeiro", a consulta mais
  frequente do backoffice.
* **Índice sobre expressão** — `lower(email)`. Só é usado se a consulta também escrever
  `WHERE lower(email) = ...`. É o que suporta pesquisa insensível a maiúsculas.
* **Índice parcial** — `WHERE visibilidade = true`. Indexa apenas as linhas visíveis. Como a loja
  pública nunca consulta as invisíveis, o índice fica menor, mais rápido e mais barato de manter.

O custo dos índices é real: cada escrita tem de os actualizar. Por isso não se indexa tudo — indexa-se
o que as consultas conhecidas pedem.

### VI.1.5 Transacções e ACID

Uma **transacção** agrupa várias operações num tudo-ou-nada. ACID é o acrónimo das quatro garantias:

* **Atomicidade** — ou todas as operações acontecem, ou nenhuma. Sem estados intermédios visíveis.
* **Consistência** — o resultado respeita todas as restrições definidas.
* **Isolamento** — transacções concorrentes não vêem os resultados parciais umas das outras.
* **Durabilidade** — depois de confirmada, sobrevive a uma falha de energia.

O Diomika complementa isto no plano aplicacional, porque algumas operações envolvem coisas que **não
são** a base de dados (enviar email, gerar PDF). Uma transacção SQL não consegue "desfazer" um email
enviado. Para esses casos existem o padrão **saga** (passos com compensação, em
`backend-api/core/saga/`) e o padrão **outbox** (a intenção de enviar é gravada na mesma transacção
que os dados, e um trabalhador em segundo plano entrega-a com repetições — tabela `outbox_events`,
com índices `idx_outbox_pending` e `idx_outbox_processing`).

### VI.1.6 `jsonb`: o híbrido pragmático

Várias colunas guardam JSON: `linhas` (as linhas de um orçamento), `alturas`, `composicao`,
`context`, `detail`, `payload`.

```sql
linhas jsonb NOT NULL DEFAULT '[]'::jsonb
```

O tipo `jsonb` (o `b` é de *binário*) guarda JSON já analisado e indexável, ao contrário do tipo
`json`, que guarda o texto original. É mais rápido a consultar e permite operadores próprios.

Porque não normalizar as linhas de orçamento numa tabela `pedido_linhas`? Porque a forma das linhas
varia por tipo de catálogo (uma almofada tem dimensões e cor; um assento tem alturas e paleta), e o
catálogo é dirigido por esquema (*schema-driven*). Guardar uma estrutura flexível em `jsonb` evita
uma migração de base de dados por cada evolução do produto. O compromisso é que a base de dados não
valida o interior do JSON — essa validação vive em
`backend-api/core/validators/order_lines.py` e nos modelos Pydantic.

### VI.1.7 Triggers e o detalhe do `search_path`

Um *trigger* é código que a base de dados executa automaticamente em resposta a um evento.

```sql
CREATE OR REPLACE FUNCTION diomika_set_updated_at()
RETURNS trigger
LANGUAGE plpgsql
SET search_path = ''
AS $$
BEGIN
  NEW.updated_at = now();
  RETURN NEW;
END;
$$;
```

Aplicado a `categories`, `modelos_almofadas`, `modelos_assentos`, `almofada`, `assento` e
`modelo_cores`, garante que `updated_at` está sempre certo — mesmo que alguém altere a linha
directamente pelo editor SQL do Supabase. O comentário no ficheiro explica a utilidade: *"detecção
de conflitos entre vários PCs com backoffice"* — se dois computadores editarem o mesmo modelo, o
carimbo permite detectar a divergência.

O `SET search_path = ''` merece destaque porque é uma prática de segurança pouco conhecida. O
`search_path` é a lista de esquemas onde o PostgreSQL procura nomes não qualificados. Se uma função
não o fixar, um atacante com permissão de criar objectos num esquema que apareça primeiro no
`search_path` pode criar uma função com o nome de uma função usada internamente e sequestrar a
execução. Fixar `search_path` a vazio força a qualificação explícita e fecha essa porta. É
exactamente o tipo de recomendação que os consultores de segurança do Supabase levantam, e está
aqui aplicada.

### VI.1.8 O inventário de tabelas do Diomika

| Tabela | Natureza | Papel |
|---|---|---|
| `categories` | Catálogo | Categorias, com `tipo_catalogo`, `carrinho_step`, `carrinho_min` |
| `modelos_almofadas`, `modelos_assentos` | Catálogo | Modelos por tipo de produto |
| `almofada`, `assento` | Catálogo | Referências concretas, com `ean` único e `barcode_url` |
| `modelo_cores` | Catálogo | Cores, pertencentes a um modelo **ou** a uma paleta |
| `paletas_cores` | Catálogo | Paletas reutilizáveis ("Fantasia", "Catálogo") |
| `pedidos_orcamento` | Negócio sensível | Pedidos do sítio público — **dados pessoais** |
| `encomendas_internas` | Negócio sensível | Encomendas criadas no backoffice |
| `contact_messages`, `message_history` | Negócio sensível | Formulário de contacto e histórico |
| `outbox_events` | Infra-estrutura | Entrega fiável de efeitos secundários |
| `saga_instances` | Infra-estrutura | Estado de transacções distribuídas |
| `idempotency_keys` | Infra-estrutura | Respostas em cache para evitar duplicação |
| `admin_audit_log` | Infra-estrutura | Registo de auditoria de acções administrativas |

Detalhe legado com valor pedagógico: a tabela de referências de almofada chama-se `almofada`, não
`products`. O topo de `deploy/supabase_pre_deploy.sql` di-lo explicitamente — *"BD actual: tabela
almofada (não products)"*. É a marca de um sistema que evoluiu com o negócio real, e a nota existe
para poupar tempo a quem procura a tabela "óbvia" que não existe.

---

## VI.2 PostgreSQL e Supabase (BaaS)

### VI.2.1 PostgreSQL

O PostgreSQL (frequentemente "Postgres") é um sistema de gestão de bases de dados relacionais de
código aberto, com mais de três décadas de desenvolvimento. É a escolha por omissão razoável para
quase tudo, e no contexto do Diomika interessam sobretudo:

* **Conformidade rigorosa com o padrão SQL** e tipos ricos: `uuid`, `jsonb`, `timestamptz` (data-hora
  **com fuso horário** — evita toda a categoria de erros de horário de verão), *arrays*.
* **Row Level Security** — segurança ao nível da linha, integrada no motor (ver VI.4). É o pilar do
  modelo de segurança de dados aqui.
* **Extensibilidade** — funções em PL/pgSQL, *triggers*, índices parciais e sobre expressões,
  extensões (`pgcrypto` fornece o `gen_random_uuid()` usado em todas as chaves primárias).

### VI.2.2 O que significa BaaS, e o que o Supabase é

BaaS significa *Backend as a Service* — "servidor como serviço". Em vez de instalar, configurar,
proteger, monitorizar, actualizar e fazer cópias de segurança de uma base de dados, contrata-se isso
como serviço gerido, e concentra-se o esforço na aplicação.

O Supabase é um BaaS construído **em torno de um PostgreSQL a sério** — e esta é a diferença
essencial em relação a alternativas como o Firebase, que impõem um modelo de dados proprietário. Com
o Supabase, o que existe por baixo é Postgres normal: pode-se migrar para qualquer alojamento de
Postgres levando o esquema e os dados, o que reduz drasticamente o risco de dependência de
fornecedor (*vendor lock-in*).

Componentes do Supabase e o que o Diomika usa:

| Componente | O que é | Uso no Diomika |
|---|---|---|
| **Database** | PostgreSQL gerido, com cópias de segurança e editor SQL | **Sim** — é a base de dados principal |
| **Storage** | Armazenamento de ficheiros com políticas e URLs assinadas | **Sim** — imagens de produto e códigos de barras |
| **PostgREST** | API REST gerada automaticamente a partir do esquema | Indirectamente, através da biblioteca cliente |
| **Auth** | Gestão de utilizadores, OAuth, JWT | **Não** — o backoffice tem autenticação própria (V.6, VI.8) |
| **Realtime** | Notificações de alterações por WebSocket | Não usado |
| **Edge Functions** | Funções serverless em Deno | Não usado |

A decisão de **não** usar o Supabase Auth é deliberada e vale a pena justificar. O Supabase Auth
resolve muito bem o problema de "milhares de utilizadores finais registam-se no meu produto". O
problema do Diomika é diferente: um punhado de operadores internos, num backoffice que já está atrás
de um *gate* de secretária e de restrições de rede. Uma implementação local (V.6, V.7) é mais simples,
não introduz dependência da disponibilidade do serviço de autenticação para entrar no backoffice, e
mantém as credenciais administrativas fora da base de dados na nuvem — o que, como se verá em VI.8, é
uma propriedade de segurança valiosa.

### VI.2.3 A ligação, em `backend-api/core/database.py`

```python
_http_limits  = httpx.Limits(max_connections=80, max_keepalive_connections=25, keepalive_expiry=30.0)
_http_timeout = httpx.Timeout(12.0, connect=3.0)

_ssl_ctx = ssl.create_default_context(cafile=certifi.where())
_http = httpx.Client(verify=_ssl_ctx, timeout=_http_timeout, limits=_http_limits)

_options = SyncClientOptions(httpx_client=_http)
supabase: Client = create_client(url or "", key or "", options=_options)
```

Cada parâmetro tem consequências operacionais:

* **`max_connections=80`** — limite superior de ligações simultâneas. Evita que um pico de tráfego
  esgote a quota de ligações do projecto Supabase.
* **`max_keepalive_connections=25`** e **`keepalive_expiry=30.0`** — reutilização de ligações
  (*connection pooling*). Estabelecer TLS de novo em cada pedido custa dezenas de milissegundos;
  reutilizar poupa esse custo repetidamente.
* **`Timeout(12.0, connect=3.0)`** — três segundos para estabelecer ligação, doze para a operação
  completa. Sem tempos-limite, uma dependência lenta propaga-se como bloqueio em toda a aplicação —
  o mecanismo pelo qual uma avaria pequena se transforma numa paragem total.
* **`verify=` com `certifi`** — validação de certificados TLS com um conjunto actualizado de
  autoridades, independente do sistema operativo.

E há uma protecção explícita contra o atalho perigoso:

```python
if _ssl_flag and _is_final_production:
    print("ERRO: DIOMIKA_SSL_INSECURE=1 em producao final — abortar.", file=sys.stderr)
    sys.exit(1)
```

`DIOMIKA_SSL_INSECURE=1` desliga a validação de certificados. É ocasionalmente necessário em
ambientes de teste com certificados auto-assinados, e é catastrófico em produção (abre a porta a
interceptação). O código **aborta o arranque** se a flag estiver activa em produção final, e emite
um aviso ruidoso em beta. Note-se o cuidado extra: nunca é activada implicitamente por estar em
beta, apenas por flag explícita. Os *scripts* de implantação usam uma variável **diferente**
(`DEPLOY_TLS_INSECURE`), para que relaxar TLS numa ferramenta de linha de comandos nunca possa
relaxar TLS na API. Testes: `test_production_rejects_ssl_insecure`,
`test_beta_allows_explicit_ssl_insecure_with_warning`.

---

## VI.3 Chave anónima vs chave de serviço (e o perigo de a segunda ir para o *frontend*)

### VI.3.1 As duas chaves

Cada projecto Supabase emite (pelo menos) duas chaves, ambas no formato JWT:

| Chave | Papel PostgreSQL | RLS aplica-se? | Onde pode viver |
|---|---|---|---|
| **`anon`** (anónima / publicável) | `anon` | **Sim** | Em qualquer sítio, incluindo código de navegador |
| **`service_role`** (chave de serviço) | `service_role` | **Não — ignora tudo** | **Apenas** no servidor |

A chave `anon` é *desenhada para ser pública*. Vai no pacote JavaScript do sítio, é visível a
qualquer visitante, e isso não é um problema, porque tudo o que ela consegue fazer está limitado
pelas políticas de RLS (VI.4). Sem políticas que permitam algo, a chave `anon` não faz nada.

A chave `service_role` é o oposto exacto: o PostgreSQL trata-a como **`BYPASSRLS`**. Todas as
políticas são ignoradas. Com essa chave é possível ler `pedidos_orcamento` inteira, ler todas as
mensagens de contacto, apagar tabelas, esvaziar o armazenamento.

### VI.3.2 A separação no Diomika

Em `.env.example` (nomes, com valores como marcadores):

```
SUPABASE_URL=https://YOUR_PROJECT.supabase.co
SUPABASE_KEY=your-service-role-key          ← SERVIDOR. Nunca no frontend.
VITE_SUPABASE_URL=https://YOUR_PROJECT.supabase.co
VITE_SUPABASE_ANON_KEY=your-anon-key        ← pode ir no bundle: é pública por natureza
```

**O prefixo `VITE_` é a parte que tem de ficar clara.** O Vite (a ferramenta que compila o
*frontend*) expõe ao código do navegador **apenas** as variáveis de ambiente cujo nome começa por
`VITE_`. É uma protecção de desenho: uma variável sem esse prefixo não pode ser lida por engano no
código do cliente. E a implicação inversa é igualmente importante: **qualquer coisa com prefixo `VITE_`
é pública**, porque fica literalmente escrita no ficheiro JavaScript que qualquer visitante
descarrega. Chamar-lhe "variável de ambiente" cria a ilusão de segredo; não é.

Por isso a regra é simples e absoluta: `SUPABASE_KEY` (a chave de serviço) nunca tem prefixo `VITE_`
e nunca aparece em nenhum ficheiro do `frontend-web/`.

Há verificação automatizada: `deploy/verify_bundle_secrets.py` inspecciona o pacote compilado à
procura de padrões de segredos antes da publicação — porque "temos cuidado" é uma intenção, e um
*script* que falha a construção é uma garantia.

### VI.3.3 O que aconteceria numa fuga da chave de serviço

Um cenário útil para calibrar a gravidade. Se a chave `service_role` fosse para o pacote do
*frontend*, qualquer visitante do sítio poderia, com o navegador aberto nas ferramentas de
desenvolvimento:

1. **ler todos os pedidos de orçamento** — nomes, emails, telefones, empresas (fuga de dados
   pessoais notificável ao regulador, ao abrigo do RGPD);
2. **ler todas as mensagens de contacto** e o histórico de correspondência;
3. **apagar ou alterar o catálogo** inteiro;
4. **escrever no armazenamento** — substituir imagens de produto por qualquer conteúdo;
5. **ler o registo de auditoria** e, com ele, o mapa de como o sistema é operado.

Não haveria mitigação parcial: a chave ignora RLS por definição. A única resposta seria rodar a
chave imediatamente no painel do Supabase (o que invalida a antiga), reimplantar a API e presumir
que tudo o que a chave alcançava foi comprometido.

É por isto que a arquitectura é *"anon lê o necessário; escrita via API"* (VI.4): mesmo que a
separação falhasse, as políticas de RLS limitariam o dano de uma fuga da chave `anon` a leituras que
já eram públicas de qualquer forma.

### VI.3.4 A validação de arranque, outra vez

```python
if not os.getenv("SUPABASE_URL"): missing.append("SUPABASE_URL")
if not os.getenv("SUPABASE_KEY"): missing.append("SUPABASE_KEY")
```

Em produção, ambas são obrigatórias e a ausência impede o arranque. É preferível que a API não suba
— falha visível, imediata, com mensagem clara — do que suba e falhe silenciosamente a cada pedido.

---

## VI.4 RLS — Row Level Security (segurança ao nível da linha)

### VI.4.1 O conceito

As permissões clássicas do SQL são por **tabela**: "este papel pode ler `categories`". A Row Level
Security desce ao nível da **linha**: "este papel pode ler as linhas de `categories` que satisfaçam
esta condição".

A mudança de paradigma é profunda: a regra de autorização deixa de estar no código da aplicação e
passa a estar **no motor da base de dados**. Qualquer caminho de acesso — a API, o editor SQL, uma
ferramenta de análise, um *script* — obedece à mesma regra. Não é possível esquecer um `WHERE`.

### VI.4.2 Activar é negar

```sql
ALTER TABLE categories ENABLE ROW LEVEL SECURITY;
```

O comportamento por omissão depois deste comando é **negar tudo**. Sem políticas, nem `SELECT`
funciona (para papéis sujeitos a RLS). Isto é *fail-closed* na sua forma mais pura: acrescentar uma
tabela nova e esquecer as políticas resulta em "ninguém acede", não em "todos acedem".

No `deploy/supabase_pre_deploy.sql`, a RLS é activada em **todas** as tabelas: catálogo, negócio,
infra-estrutura e auditoria. Não há excepções.

### VI.4.3 As políticas de leitura pública

```sql
CREATE POLICY "categories_public_read"       ON categories        FOR SELECT TO anon USING (visibilidade = true);
CREATE POLICY "modelos_public_read"          ON modelos_almofadas FOR SELECT TO anon USING (visibilidade = true);
CREATE POLICY "almofada_public_read"         ON almofada          FOR SELECT TO anon USING (visibilidade = true);
CREATE POLICY "modelo_cores_public_read"     ON modelo_cores      FOR SELECT TO anon USING (visibilidade = true);
CREATE POLICY "paletas_public_read"          ON paletas_cores     FOR SELECT TO anon USING (visibilidade = true);
CREATE POLICY "modelos_assentos_public_read" ON modelos_assentos  FOR SELECT TO anon USING (visibilidade = true);
CREATE POLICY "assento_public_read"          ON assento           FOR SELECT TO anon USING (visibilidade = true);
```

Anatomia de uma política:

* **`FOR SELECT`** — só leitura. Não há política de `INSERT`, `UPDATE` ou `DELETE` para `anon` nestas
  tabelas, logo a escrita é impossível para esse papel.
* **`TO anon`** — aplica-se ao papel usado pela chave anónima, isto é, ao *frontend*.
* **`USING (visibilidade = true)`** — a condição por linha. Um modelo com `visibilidade = false`
  **não existe** para o público. Não é filtrado pelo código, não é escondido pela interface: a base
  de dados não o devolve.

Isto tem uma consequência prática elegante: o interruptor de visibilidade no backoffice é uma
funcionalidade de negócio *e* um controlo de segurança ao mesmo tempo. Preparar um modelo novo sem o
publicar é seguro por construção. Teste: `test_hidden_category_returns_empty_catalog`, em
`backend-api/tests/test_idor.py`.

### VI.4.4 As políticas de negação

```sql
CREATE POLICY "pedidos_orcamento_deny_anon"   ON pedidos_orcamento   FOR ALL    TO anon USING (false);
CREATE POLICY "encomendas_internas_deny_anon" ON encomendas_internas FOR ALL    TO anon USING (false);
CREATE POLICY "contact_deny_anon_insert"      ON contact_messages    FOR INSERT TO anon WITH CHECK (false);
CREATE POLICY "contact_deny_anon_select"      ON contact_messages    FOR SELECT TO anon USING (false);
CREATE POLICY "history_deny_anon"             ON message_history     FOR ALL    TO anon USING (false);
CREATE POLICY "outbox_deny_anon"              ON outbox_events       FOR ALL    TO anon USING (false);
CREATE POLICY "saga_deny_anon"                ON saga_instances      FOR ALL    TO anon USING (false);
CREATE POLICY "idempotency_deny_anon"         ON idempotency_keys    FOR ALL    TO anon USING (false);
CREATE POLICY "admin_audit_deny_anon"         ON admin_audit_log     FOR ALL    TO anon USING (false);
```

Duas observações:

* **Políticas explícitas de negação, apesar de a omissão já negar.** É redundante, e a redundância é
  intencional: torna a intenção legível para quem inspecciona a base de dados ("aqui alguém decidiu
  que `anon` não toca nisto") e protege contra o acidente de alguém acrescentar uma política
  permissiva mais tarde sem perceber o contexto.
* **`USING` versus `WITH CHECK`.** `USING` filtra as linhas *existentes* (leitura, actualização,
  eliminação); `WITH CHECK` valida as linhas *novas* (inserção, actualização). Por isso a negação de
  inserção em `contact_messages` usa `WITH CHECK (false)` — não há linhas existentes para filtrar; o
  que se quer é recusar as novas.

### VI.4.5 O padrão: `anon` lê o necessário; escrita via API

O detalhe mais interessante de todo o modelo de dados está no comentário que precede a política de
contacto:

```sql
-- Contacto só via API (Turnstile + rate limit); bloquear INSERT anon directo
```

O *frontend* **poderia** inserir directamente em `contact_messages` com a chave anónima — é como
muitos projectos Supabase funcionam, e é mais simples. A decisão foi negar essa via e obrigar toda a
escrita a passar pela API. O que se ganha, camada a camada:

| Se o *frontend* escrevesse directamente | Escrevendo através da API |
|---|---|
| Sem verificação anti-spam possível | Turnstile verificado no servidor (V.15) |
| Sem limitação de ritmo real | 5 pedidos por minuto por IP (V.14) |
| Validação apenas no cliente (contornável) | Pydantic no servidor: comprimentos, email, normalização |
| Sem protecção contra duplicação | Chave de idempotência obrigatória em produção |
| Sem notificação por email | Saga + outbox garantem entrega com repetições |
| Sem registo nem alertas | Registos estruturados, auditoria e alertas |

Resumindo o modelo em três linhas:

* **Leitura pública** — directa do *frontend* para o PostgreSQL, com chave `anon`, filtrada por RLS.
  Rápida, sem carga na API, e segura porque só devolve o que é público.
* **Escrita pública** — obrigatoriamente pela API, que valida, limita, verifica e regista.
* **Leitura e escrita privilegiadas** — pela API com chave de serviço, depois de atravessar todas as
  camadas de V.2.

### VI.4.6 O papel `service_role` e a responsabilidade que herda

Como a API usa a chave de serviço, **as políticas de RLS não a limitam**. Isto não é um defeito do
desenho: é a razão de a API poder ler `pedidos_orcamento` para o backoffice. Mas tem uma implicação
que deve ser dita: **para os caminhos da API, a autorização é inteiramente responsabilidade do
código de V.11** (`assert_table_action`, `role_can_access_table`, `require_*`). A RLS é a rede de
segurança para o caminho do *frontend*; a matriz de papéis é a rede de segurança para o caminho da
API. Duas redes, para dois caminhos diferentes — e por isso a bateria de testes de IDOR
(`backend-api/tests/test_idor.py`) verifica explicitamente que um pedido sem autenticação não
consegue obter um PDF de orçamento, uma mensagem de contacto ou um pedido pelo identificador.

---

## VI.5 Armazenamento privado e URLs assinadas

### VI.5.1 *Buckets* e o modelo do Supabase Storage

Um *bucket* ("balde") é um contentor de ficheiros. O Diomika usa dois:

* **`product-images`** — imagens de categorias, modelos e cores;
* **`barcodes`** — imagens de código de barras geradas a partir dos códigos EAN
  (*European Article Number*).

O Supabase Storage é interessante porque os metadados dos ficheiros vivem numa tabela PostgreSQL
(`storage.objects`), o que significa que **as mesmas políticas de RLS se aplicam a ficheiros**:

```sql
CREATE POLICY "product_images_public_read" ON storage.objects
  FOR SELECT TO anon
  USING (
    bucket_id = 'product-images'
    AND coalesce(name, '') <> ''
    AND right(name, 1) <> '/'
  );

CREATE POLICY "product_images_no_anon_write"  ON storage.objects FOR INSERT TO anon WITH CHECK (false);
CREATE POLICY "product_images_no_anon_update" ON storage.objects FOR UPDATE TO anon USING (false);
CREATE POLICY "product_images_no_anon_delete" ON storage.objects FOR DELETE TO anon USING (false);
```

As condições `name <> ''` e `right(name, 1) <> '/'` excluem entradas de "pasta" (o Storage
representa directórios como objectos terminados em barra), para que a listagem não revele a
estrutura de directórios. As três políticas de negação garantem que `anon` **nunca** escreve: todos
os *uploads* passam pela API, com validação. O mesmo conjunto existe para `barcodes`.

### VI.5.2 Privado por omissão em produção

```python
def storage_is_private() -> bool:
    if storage_backend() == "r2":
        return not bool((os.getenv("R2_PUBLIC_BASE_URL") or "").strip())
    return (os.getenv("SUPABASE_STORAGE_PRIVATE") or "").strip().lower() in ("1", "true", "yes")
```

E a exigência no arranque:

```python
if not self.is_beta and (os.getenv("SUPABASE_STORAGE_PRIVATE") or "").strip().lower() not in ("1", "true", "yes"):
    print("ERRO: SUPABASE_STORAGE_PRIVATE=1 obrigatorio em producao final.", file=sys.stderr)
    sys.exit(1)
```

Porquê exigir armazenamento privado? Porque uma URL pública de armazenamento é **permanente,
adivinhável e não revogável**. Se um caminho for descoberto (por um *referrer*, por um cabeçalho, por
uma partilha), fica acessível para sempre a quem o tiver. Um catálogo inteiro pode ser copiado
enumerando caminhos.

### VI.5.3 URLs assinadas

Uma URL assinada é um endereço temporário que contém uma assinatura criptográfica e um prazo de
validade. Passado esse prazo, deixa de funcionar.

```python
def signed_url_ttl() -> int:
    return max(60, int(os.getenv("STORAGE_SIGNED_URL_TTL") or "3600"))
```

Por omissão, uma hora, com um mínimo forçado de 60 segundos (não faz sentido gerar URLs que expiram
antes de o navegador as usar). Configurável por `STORAGE_SIGNED_URL_TTL`.

E o comportamento é **fail-closed**, como o próprio *docstring* diz — *"falha fechada (nunca cai
para pública se storage privado)"*:

```python
def get_signed_url(storage_path: str, expires_in: int | None = None) -> str:
    ...
    if not url or not url.startswith("http"):
        raise RuntimeError("Falha ao gerar URL assinada do storage")
    return url
```

E na resolução da URL de entrega:

```python
def resolve_delivery_url(storage_path: str) -> str:
    ...
    # Produção final: nunca cair para URL pública
    if settings.is_production and not settings.is_beta:
        if not storage_is_private():
            raise RuntimeError("SUPABASE_STORAGE_PRIVATE=1 obrigatório — recusado URL pública")
        return get_signed_url(storage_path)
```

A tentação natural, ao programar isto, seria "se falhar a assinar, devolve a URL pública para o
utilizador ver a imagem". Seria uma degradação **silenciosa** de uma garantia de segurança — e essas
são as piores, porque ninguém repara. O código prefere falhar de forma visível. Teste:
`test_private_signed_url_fails_closed`, em `backend-api/tests/test_storage_private.py`.

O compromisso operacional é real e conhecido: URLs com validade não podem ser guardadas em cache
indefinidamente pelo navegador nem gravadas na base de dados como se fossem permanentes. É por isso
que existe `VITE_STORAGE_PRIVATE=1` do lado do *frontend* — para a interface saber que deve pedir
URLs actualizadas à API em vez de reutilizar as antigas.

### VI.5.4 Validação de *uploads*

Aceitar ficheiros de terceiros é uma das operações mais perigosas de qualquer aplicação. As defesas
em `backend-api/utils/storage.py`:

**1. Sanitização do caminho:**

```python
_SAFE_PATH = re.compile(r"[^a-zA-Z0-9._/\-]")

def sanitize_storage_path(dest_path: str) -> str:
    cleaned = dest_path.replace("\\", "/").lstrip("/")
    cleaned = _SAFE_PATH.sub("_", cleaned)
    parts = [p for p in cleaned.split("/") if p and p not in (".", "..")]
    if not parts:
        raise ValueError("Caminho de storage inválido")
    return "/".join(parts)
```

Isto defende contra **travessia de caminho** (*path traversal*): um nome como
`../../etc/passwd` ou `..\..\windows\system32\...` teria os segmentos `..` removidos, as barras
invertidas normalizadas e qualquer caractere fora do conjunto seguro substituído por `_`. E se, no
fim, não sobrar nada, levanta erro em vez de escrever num caminho inesperado. Teste:
`test_sanitize_storage_path`.

**2. Limite de tamanho:**

```python
max_bytes = int(os.getenv("STORAGE_MAX_UPLOAD_BYTES") or str(5 * 1024 * 1024))   # 5 MiB
```

**3. Validação do conteúdo, não da extensão:**

```python
validate_upload_bytes(data, dest_path)
```

Em `backend-api/utils/image_validation.py`. O ponto essencial: **verifica os bytes reais**, não
apenas o nome. Um ficheiro chamado `foto.png` que na verdade é um arquivo ZIP, ou um "polyglot" que é
simultaneamente imagem válida e arquivo, é rejeitado. Teste com um nome que diz tudo:
`test_upload_rejects_zip_polyglot`.

**4. Lista de tipos permitidos, com `Content-Type` derivado do servidor:**

```python
if lower.endswith((".jpg", ".jpeg")):  content_type = "image/jpeg"
elif lower.endswith(".png"):           content_type = "image/png"
elif lower.endswith(".webp"):          content_type = "image/webp"
elif lower.endswith(".gif"):           content_type = "image/gif"
else: raise ValueError("Extensão de imagem não permitida")
```

O `Content-Type` guardado é **determinado pelo servidor**, nunca aceito do cliente. Combinado com o
`X-Content-Type-Options: nosniff` de V.17, fecha a possibilidade de um ficheiro carregado ser
interpretado como HTML e executar script no domínio do sítio. Teste:
`test_upload_rejects_bad_extension`.

---

## VI.6 Cloudflare R2 — compatível com S3; `storage_r2.py`; opcional até haver `R2_*`

### VI.6.1 O que é o R2 e porque interessa

O Cloudflare R2 é armazenamento de objectos (ficheiros), equivalente funcional do Amazon S3
(*Simple Storage Service*), com uma diferença comercial decisiva: **não cobra tráfego de saída**
(*egress*). Nos fornecedores tradicionais, o custo dominante de servir imagens não é guardá-las, é
transmiti-las. Para um catálogo de produtos, que é essencialmente imagens servidas repetidamente,
essa diferença é estrutural.

"Compatível com S3" significa que fala o mesmo protocolo que o S3 da Amazon. A consequência prática:
usa-se a biblioteca padrão da indústria (`boto3`, em Python) apontando-a para um endereço diferente.
Nada de bibliotecas proprietárias, e a migração é uma questão de configuração.

### VI.6.2 Selecção automática do *backend*

Em `backend-api/utils/storage.py`:

```python
def storage_backend() -> str:
    """Auto: R2 se credenciais existirem; senão Supabase (ambos free-tier possíveis)."""
    forced = (os.getenv("STORAGE_BACKEND") or "").strip().lower()
    if forced in ("r2", "supabase"):
        return forced
    if all(
        (os.getenv(k) or "").strip()
        for k in ("R2_ACCOUNT_ID", "R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY")
    ):
        return "r2"
    return "supabase"
```

A lógica: `STORAGE_BACKEND` força explicitamente; se não estiver definida, o R2 é usado **se e só
se** as três credenciais existirem; caso contrário, Supabase Storage. Ou seja, **o R2 é totalmente
opcional e inerte até alguém preencher as variáveis `R2_*`** — não há nada a configurar, nada a
desactivar, nenhuma dependência a instalar para quem não o usa.

Este padrão merece destaque como decisão de arquitectura: a mudança de fornecedor de armazenamento é
uma alteração de configuração, não de código. Todo o resto da aplicação chama `upload_bytes`,
`get_signed_url` e `resolve_delivery_url` sem saber qual o *backend* — é o **padrão adaptador**
aplicado com disciplina.

### VI.6.3 A implementação, em `backend-api/utils/storage_r2.py`

```python
endpoint = f"https://{account}.r2.cloudflarestorage.com"
return boto3.client(
    "s3",
    endpoint_url=endpoint,
    aws_access_key_id=key,
    aws_secret_access_key=secret,
    region_name="auto",
    config=Config(signature_version="s3v4"),
)
```

Notas:

* **`region_name="auto"`** — o R2 é global, não tem regiões no sentido da Amazon, mas a biblioteca
  exige o campo.
* **`signature_version="s3v4"`** — a versão 4 do algoritmo de assinatura da AWS, exigida pelo R2.
* **`@lru_cache(maxsize=1)`** no construtor do cliente — o cliente é criado uma vez e reutilizado.
  Criar um cliente `boto3` por pedido seria desperdício mensurável.
* **`boto3` é dependência opcional** — o `import` está dentro da função e, se faltar, o erro é
  didáctico: `"STORAGE_BACKEND=r2 requer boto3 — pip install boto3"`. Quem não usa R2 não instala a
  biblioteca.
* **Nome do *bucket* com camadas de recurso** — `R2_BUCKET`, senão `SUPABASE_STORAGE_BUCKET`, senão
  `product-images`.

E a resolução de URLs, com duas estratégias:

```python
def resolve_url(dest_path: str) -> str:
    public = (os.getenv("R2_PUBLIC_BASE_URL") or "").rstrip("/")
    if public:
        return f"{public}/{dest_path.lstrip('/')}"
    # signed URL curta se sem CDN público
    client = _client()
    ttl = max(60, int(os.getenv("STORAGE_SIGNED_URL_TTL") or "3600"))
    return client.generate_presigned_url(
        "get_object", Params={"Bucket": _bucket(), "Key": dest_path}, ExpiresIn=ttl,
    )
```

* **Com `R2_PUBLIC_BASE_URL`** (por exemplo um domínio próprio de imagens ou um endereço `r2.dev`):
  URLs públicas, estáveis, com cache eficiente na rede da Cloudflare. É a configuração ideal para
  imagens de catálogo, que são *destinadas* a ser públicas.
* **Sem `R2_PUBLIC_BASE_URL`**: URLs pré-assinadas com validade, tal como no Supabase privado.

E é por isto que `storage_is_private()`, no caso do R2, é definido como *"não existe URL pública
configurada"* — a semântica de privacidade decorre da configuração, de forma coerente.

Detalhe de integração já resolvido: a CSP do sítio público (V.17.3) inclui `https://*.r2.dev` em
`img-src`, portanto activar o R2 não exige alterações no *frontend*.

---

## VI.7 SQL de implantação (`supabase_pre_deploy.sql`, `production_setup.sql`)

### VI.7.1 O princípio da idempotência

Idempotente significa: **executar duas vezes tem o mesmo efeito que executar uma vez**. É a
propriedade mais valiosa que um *script* de implantação pode ter, porque elimina a necessidade de
saber o estado actual antes de correr. Não é preciso perguntar "já foi aplicado?" — corre-se outra
vez e está.

Em `deploy/supabase_pre_deploy.sql` a idempotência é obtida com três técnicas, aplicadas de forma
consistente:

**1. `IF NOT EXISTS` na criação:**

```sql
CREATE TABLE IF NOT EXISTS modelo_cores (...);
ALTER TABLE categories ADD COLUMN IF NOT EXISTS carrinho_step integer DEFAULT 6;
CREATE INDEX IF NOT EXISTS idx_categories_tipo ON categories (tipo_catalogo);
```

**2. `DROP … IF EXISTS` seguido de `CREATE` para objectos que devem ficar num estado definido:**

```sql
DROP POLICY IF EXISTS "categories_public_read" ON categories;
CREATE POLICY "categories_public_read" ON categories FOR SELECT TO anon USING (visibilidade = true);
```

Este padrão é mais forte do que `IF NOT EXISTS` para políticas e restrições: garante que a
**definição** corresponde exactamente ao ficheiro, em vez de deixar em vigor uma versão antiga com o
mesmo nome. É a diferença entre "existe uma política chamada X" e "existe *esta* política".

**3. `INSERT … WHERE NOT EXISTS` para dados de semente:**

```sql
INSERT INTO paletas_cores (nome, slug, visibilidade)
SELECT 'Fantasia', 'fantasia', true
WHERE NOT EXISTS (SELECT 1 FROM paletas_cores WHERE slug = 'fantasia');
```

Cria a paleta só se não existir, sem depender de restrições de unicidade nem gerar erro.

### VI.7.2 O que o ficheiro contém, por ordem

`deploy/supabase_pre_deploy.sql` é um **pacote consolidado**: reúne o conteúdo de vários *scripts*
num único texto para colar no editor SQL do Supabase. Os cabeçalhos internos marcam a proveniência —
`-- === production_setup.sql (infra + RLS) ===`,
`-- === Assentos + paletas (migration_assentos.sql) ===` — o que permite ler o ficheiro como uma
história das decisões, e não como um bloco opaco.

A ordem:

1. **Evolução do catálogo** — colunas de carrinho (`carrinho_step`, `carrinho_min`),
   `tipo_catalogo`, unicidade de `slug`, restrições `CHECK`, `composicao` em `jsonb`.
2. **Normalização de dados existentes** — `UPDATE categories SET tipo_catalogo = 'assento' WHERE slug
   IN ('assentos', 'assento')`. Estas linhas são migração de dados, não de esquema: alinham o que já
   existe com o modelo novo.
3. **Tabelas de negócio** — `modelo_cores`, `pedidos_orcamento`, `encomendas_internas`.
4. **Infra-estrutura** — `outbox_events`, `saga_instances`, `idempotency_keys`, com os respectivos
   índices, incluindo o índice parcial `idx_outbox_processing … WHERE status = 'processing'`.
5. **Endurecimento de esquema** — `SET NOT NULL` em colunas que já não deviam admitir nulos,
   `SET DEFAULT true` em `visibilidade`.
6. **RLS** — activação em todas as tabelas e definição de todas as políticas (VI.4).
7. **Políticas de Storage** — para `product-images` e `barcodes` (VI.5.1).
8. **Assentos e paletas** — o segundo tipo de catálogo, incluindo a reformulação de `modelo_cores`
   para pertencer a um modelo *ou* a uma paleta, com índices únicos parciais e a restrição
   `modelo_cores_owner_check`.
9. **Limpeza de legado** — `DROP TABLE IF EXISTS paleta_cores CASCADE;` e
   `DROP TABLE IF EXISTS modelo_assento_cores CASCADE;`. São as **únicas** instruções destrutivas do
   ficheiro, dirigidas a tabelas nominalmente substituídas.
10. **Índices de desempenho** — para as consultas conhecidas da loja e do backoffice.
11. **`updated_at` e *triggers*** — o mecanismo de VI.1.7.
12. **Auditoria** — `admin_audit_log`, índices e política de negação.

### VI.7.3 Os outros ficheiros SQL do repositório

| Ficheiro | Papel |
|---|---|
| `backend-api/sql/production_setup.sql` | Base de infra-estrutura e RLS, incorporada no pacote consolidado |
| `backend-api/sql/migration_*.sql` | Migrações pontuais e datadas: `migration_assentos.sql`, `migration_admin_audit.sql`, `migration_outbox_claim.sql`, `migration_email_indexes.sql`, `migration_tipo_catalogo.sql`, `migration_v2_3_catalog.sql`, `migration_admin_users_audit_actor.sql` |
| `backend-api/sql/generated_*.sql` | **Gerados automaticamente** a partir do registo de esquema da aplicação (`backend-api/core/catalog_deploy_sql.py`). Estão no `.gitignore` (linha 33), porque o código é a fonte de verdade e o SQL é o produto |
| `deploy/generated_catalog_infra.sql` | Infra-estrutura de catálogo gerada da mesma forma |
| `backend-api/sql/create_messages_tables.sql` | Criação inicial das tabelas de mensagens |

A existência de `generated_*.sql` é uma consequência de o catálogo ser dirigido por esquema: as
tabelas de um tipo de catálogo novo são **derivadas** da definição em Python, não escritas à mão.
Elimina a divergência entre o que a aplicação espera e o que a base de dados tem.

### VI.7.4 Como se aplica

1. Abrir o editor SQL do projecto no painel do Supabase (o caminho está no cabeçalho do próprio
   ficheiro).
2. Colar o conteúdo de `deploy/supabase_pre_deploy.sql` na íntegra.
3. Executar. Como é idempotente, pode ser repetido sem receio.
4. Confirmar com as ferramentas de verificação do repositório — `deploy/verify_production.py` e
   `backend-api/core/db_verify.py` — que comparam o esquema real com o esperado.
5. Consultar os *advisors* de segurança e desempenho do Supabase, que sinalizam tabelas sem RLS,
   políticas permissivas e índices em falta.

Nota importante, presente no próprio SQL: *"Categorias são criadas apenas no backoffice — sem INSERT
automático."* O *script* prepara **estrutura**, não conteúdo de negócio. A única excepção são as duas
paletas de sistema ("Fantasia" e "Catálogo"), que a aplicação pressupõe existirem.

---

## VI.8 `admin_users.json` — ficheiro local na API, não é uma tabela do Supabase

### VI.8.1 Onde está e o que contém

```python
from paths import BACKEND_ROOT
_STORE = BACKEND_ROOT / "data" / "admin_users.json"
```

Ou seja: **`backend-api/data/admin_users.json`**, no disco da máquina que corre a API. `BACKEND_ROOT`
é resolvido a partir da localização do próprio módulo (`backend-api/paths.py`), pelo que não depende
do directório de trabalho de onde a API foi lançada.

Estrutura (com valores ilustrativos e **sem qualquer segredo real**):

```json
{
  "users": [
    {
      "username": "operador",
      "password_hash": "scrypt$<salt-base64>$<hash-base64>",
      "role": "admin",
      "failed_attempts": 0,
      "locked_until": null,
      "disabled": false,
      "totp_secret": "<presente apenas se MFA activo>",
      "totp_secret_pending": "<presente apenas durante o enrolamento>"
    }
  ]
}
```

Campo por campo: `username` (identificador, comparado sempre em minúsculas), `password_hash`
(V.6.4 — nunca a password), `role` (um de `admin`, `ops`, `catalog`, `pedidos`, `mensagens`),
`failed_attempts` e `locked_until` (V.9.2), `disabled` (desactivação sem eliminar histórico),
`totp_secret` e `totp_secret_pending` (V.8.3).

### VI.8.2 Porque não é uma tabela do Supabase

Esta é uma decisão de arquitectura deliberada, com quatro justificações:

**1. As credenciais administrativas não vivem na base de dados na nuvem.** Comprometer o projecto
Supabase — chave de serviço exposta, conta do painel invadida — não entrega o backoffice. São dois
domínios de compromisso separados, e essa separação é valiosa precisamente nos cenários piores.

**2. O login não depende da disponibilidade de um serviço externo.** Se a API do Supabase estiver
indisponível, o operador continua a poder autenticar-se e a usar a parte do backoffice que não
requer dados remotos. Um sistema de autenticação que depende da rede tem um modo de falha em que
ninguém entra para resolver o problema.

**3. É proporcional à escala real.** São poucos utilizadores, num único posto de trabalho. Uma
tabela, com migrações, políticas de RLS e ciclo de vida próprio, seria complexidade sem retorno.

**4. Reduz o alcance da chave `anon`.** Ainda que uma política de RLS fosse mal configurada por
acidente, não existe nenhuma tabela de credenciais para expor. A superfície simplesmente não existe.

### VI.8.3 Consequências operacionais (as que importam)

O compromisso tem custos concretos que devem ser conhecidos:

* **Não entra nas cópias de segurança do Supabase.** Este é o ponto mais importante desta secção. As
  cópias automáticas do Supabase cobrem a base de dados — **não cobrem este ficheiro**. Proteger o
  acesso ao backoffice exige incluir `backend-api/data/` no procedimento de cópia da máquina virtual
  (instantâneo de disco ou cópia explícita), guardada com o mesmo cuidado que um segredo.
* **É estado local, por instância.** Se algum dia a API correr em duas máquinas, cada uma teria o seu
  ficheiro e as contas divergiriam. É uma limitação reconhecida e documentada em `deploy/SCALE.md`; a
  evolução natural, nesse cenário, é migrar as credenciais para um armazenamento partilhado.
* **A recuperação é manual** — é o procedimento de V.10.3.
* **Nunca deve ser versionado** — o `.gitignore` (linhas 24-25) exclui `admin_users.json` e
  `admin_users.tmp`. Como observado em V.6.6, vale a pena acrescentar também
  `backend-api/data/admin_users.json.bak`.

Do lado positivo, todas as protecções de V.6.6 aplicam-se: permissões `0600`, escrita atómica,
cópia `.bak` antes de cada alteração e bloqueio de *thread* para serializar acessos concorrentes.

### VI.8.4 O que **está** no Supabase, e a distinção que fica

Para fechar sem ambiguidade:

| Vive no PostgreSQL/Supabase | Vive no disco da API |
|---|---|
| Catálogo (categorias, modelos, cores, paletas, referências) | `backend-api/data/admin_users.json` — contas do backoffice |
| Pedidos de orçamento, encomendas internas | `.env` — segredos de configuração |
| Mensagens de contacto e histórico | `deploy/alerts.log` — registo de alertas |
| Infra-estrutura: outbox, sagas, chaves de idempotência | Registos da aplicação (`backend-api/logs/`) |
| `admin_audit_log` — **o que** cada actor fez | — |
| Imagens (Supabase Storage ou Cloudflare R2) | — |

A assimetria é a mensagem: **a base de dados sabe *o que* foi feito e por *quem* (o campo `actor` em
`admin_audit_log`), mas não sabe *como provar* que alguém é essa pessoa.** A prova de identidade —
os *hashes* de password e os segredos TOTP — nunca sai da máquina que corre a API. Auditoria na
nuvem, autenticação em casa.

---

## Resumo das duas partes em vinte linhas

**Segurança.** Dez camadas independentes, todas configuradas para negar em caso de dúvida: a
Cloudflare filtra na rede antes de o tráfego chegar à máquina; o túnel elimina portas de entrada; o
`TrustedHostMiddleware` valida o domínio; o `PrivilegedPathMiddleware` fecha `/admin`, `/system` e
`/health/detail` a tudo o que não venha de `localhost` ou da aplicação de secretária autorizada; a
limitação de ritmo e o limite de tamanho de corpo travam o abuso; a autenticação aceita sessões
curtas assinadas com HMAC ou chaves de máquina por âmbito, comparadas em tempo constante; a
autorização decide por papel × tabela × acção, com auditoria a jusante; a validação com Pydantic
recusa entradas malformadas; o PostgreSQL aplica Row Level Security em todas as tabelas; e o
armazenamento só entrega ficheiros por URL assinada com validade curta. Onde há compromissos — o
*gate* dentro do binário, o MFA desligado por omissão — estão explicados, medidos e com caminho de
evolução definido.

**Dados.** O PostgreSQL gerido pelo Supabase é a fonte de verdade do negócio, com chaves UUID
não adivinháveis, restrições que garantem invariantes, índices dirigidos às consultas reais, e RLS a
distinguir com precisão o que é público (catálogo visível, leitura directa pela chave anónima) do
que é privado (dados pessoais, acessíveis só pela API com autorização). Toda a escrita pública
passa pela API, para poder ser verificada, limitada, validada e registada. As imagens vivem em
armazenamento privado com URLs assinadas, com um segundo *backend* — Cloudflare R2 — pronto e
inerte até alguém preencher três variáveis de ambiente. E as credenciais do backoffice ficam
deliberadamente fora da nuvem, num ficheiro local com permissões restritas, escrita atómica e cópia
de segurança rotativa: a nuvem guarda o registo do que foi feito, a máquina guarda a prova de quem o
fez.
