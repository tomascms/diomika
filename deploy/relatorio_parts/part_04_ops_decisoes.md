# Relatório técnico Diomika — Parte 04
## Observabilidade, Backoffice Electron, Deploy, Decisões e Limitações

> **Como ler este capítulo.** Este documento foi escrito para ser compreensível por alguém que **não** é engenheiro de software. Sempre que aparece uma sigla, ela é expandida e explicada na primeira vez que surge. Sempre que aparece um nome de ficheiro, ele existe realmente no repositório da Diomika e pode ser aberto e lido. Não existe neste documento **nenhuma credencial, chave, token ou password real** — apenas nomes de variáveis e descrições de comportamento. Onde um valor secreto seria necessário para ilustrar algo, aparece um marcador como `<valor-secreto>`.
>
> **Escopo.** Descreve-se o que está **implementado** no código, não intenções futuras. Quando algo está implementado mas desligado, isso é dito explicitamente (ver Parte IX.6 e Parte XI).

---

# Parte VII — Observabilidade (ver o que se passa)

## VII.1 Porquê monitorizar

### O problema em linguagem simples

Um sistema informático em produção é uma **caixa fechada**. Depois de instalado num servidor a milhares de quilómetros, ninguém está lá a ver o que acontece. Se um cliente preenche o formulário de contacto às 23h47 e a mensagem se perde, ninguém sabe — nem o cliente (que assume que recebemos), nem a Diomika (que nunca vê nada), nem o programador (que está a dormir). O erro existiu, aconteceu, e desapareceu sem deixar rasto.

**Observabilidade** é o nome técnico para o conjunto de mecanismos que fazem com que o sistema **conte o que lhe aconteceu**. A palavra vem da teoria de controlo: um sistema é "observável" se, olhando apenas para os seus sinais de saída, se consegue reconstruir o que se passou lá dentro. Aplicado a software, significa: se algo falhar, existe informação gravada em algum lado que permite responder a três perguntas.

1. **Aconteceu?** — alguém ou algo tem de dar o alarme. Se ninguém der o alarme, o problema pode durar dias.
2. **O que aconteceu exactamente?** — a mensagem de erro, a linha de código, o pedido específico, a hora.
3. **Porque aconteceu?** — o contexto: que pedido veio antes, que utilizador, que dados, que latência, que estado da base de dados.

Um sistema sem observabilidade só se descobre avariado quando um humano se queixa. Isso é intolerável num produto B2B (business-to-business, ou seja, empresa-para-empresa), onde o cliente da Diomika é uma empresa que depende do catálogo para trabalhar.

### As quatro categorias de sinal

A indústria organiza a observabilidade em quatro tipos de sinal. A Diomika usa todos os quatro, cada um com uma ferramenta dedicada:

| Sinal | O que é | Pergunta que responde | Ferramenta na Diomika |
|---|---|---|---|
| **Erros / excepções** | Momentos em que o código rebentou | "O que se partiu, e em que linha?" | Sentry |
| **Logs** | Registo cronológico de eventos, em texto estruturado | "O que aconteceu antes e depois?" | Axiom |
| **Métricas de produto** | Contagens de comportamento humano | "As pessoas conseguem usar isto?" | PostHog |
| **Disponibilidade (uptime)** | O serviço responde, sim ou não? | "Está de pé?" | UptimeRobot + GitHub Actions |

Acresce um quinto elemento que não é um "sinal" mas um **canal de entrega**: os alertas. Ter um erro gravado no Sentry não serve de nada se ninguém abre o Sentry. Por isso existe o `ntfy` / webhook (ver VII.5): um mecanismo de **notificação activa** que vai bater à porta do responsável.

### O princípio de desenho que atravessa tudo: a observabilidade nunca pode derrubar o serviço

Esta é a decisão mais importante desta parte inteira e vale a pena entendê-la antes de ver o código.

Imagine-se que o serviço de logs (o Axiom) fica em baixo, ou fica lento, ou a rede da máquina virtual não consegue chegar lá. Se o código da Diomika esperasse indefinidamente pela resposta do Axiom antes de responder ao cliente, então **uma avaria no fornecedor de logs tornar-se-ia uma avaria da loja**. Um sistema secundário (ver o que se passa) tinha derrubado o sistema primário (vender). Isso chama-se um acoplamento perigoso.

A Diomika resolve isto de forma consistente e deliberada em todos os pontos de integração: **todo o envio para o exterior é envolvido num `try/except` que engole a falha**. Vê-se literalmente no código do Axiom (`backend-api/core/structured_logging.py`):

```python
try:
    ...
    urllib.request.urlopen(req, timeout=5).read()
except Exception:
    pass
```

Aquele `except Exception: pass` parece, a olhos de um programador purista, um erro de principiante — "estás a esconder erros!". Aqui é o oposto: é uma decisão explícita de que **um log perdido é infinitamente preferível a um pedido de cliente perdido**. O mesmo padrão aparece em `core/alerts.py`, onde a função `send_alert` devolve `True` mesmo quando o webhook falha, e em `core/error_tracking.py`, onde a escrita no ficheiro local é protegida da mesma maneira. Existe ainda um `timeout=5` (cinco segundos) para o Axiom e `timeout=8` (oito segundos) para os alertas: mesmo que o servidor remoto aceite a ligação e depois nunca responda, o código desiste sozinho.

### Segundo princípio: gratuito por omissão, ligado por variável de ambiente

Nenhuma peça de observabilidade da Diomika é obrigatória para o sistema arrancar. Cada uma verifica se tem a sua credencial e, se não tiver, desliga-se silenciosamente:

- Sentry só arranca se existir `SENTRY_DSN` (`core/sentry_init.py`, primeira linha da função).
- O envio para o Axiom só acontece se existir `AXIOM_TOKEN` (`AxiomHandler.emit` sai imediatamente se o token estiver vazio).
- O PostHog só carrega se existir `VITE_POSTHOG_KEY` **e** o visitante tiver consentido.
- O webhook de alertas só é usado se existir `ALERT_WEBHOOK_URL` (ou o alias `SLACK_WEBHOOK_URL`).

Isto tem três consequências práticas muito úteis. Primeira: um programador pode correr o sistema no seu computador sem contas em serviço nenhum. Segunda: os testes automáticos correm sem enviar lixo para as contas de produção. Terceira: se um serviço se tornar pago ou desagradável, remove-se a variável de ambiente e o sistema continua a funcionar exactamente igual, apenas mais cego.

---

## VII.2 Sentry — erros e excepções

### O que é uma excepção, e o que é o Sentry

Em Python (a linguagem da interface de programação de aplicações — API, *Application Programming Interface* — da Diomika), quando o código encontra uma situação que não sabe tratar, ele "levanta uma excepção". Uma excepção é um objecto que contém o tipo de problema (por exemplo `KeyError`, `ConnectionError`) e o **stack trace**: a lista das chamadas de função que levaram até ali, como um rasto de migalhas de pão da linha exacta que falhou até ao ponto de entrada do pedido.

Se ninguém apanhar essa excepção, o programa normalmente morre. Numa API isso é mitigado pelo enquadramento (o FastAPI apanha e devolve erro 500), mas o stack trace evapora-se no ecrã do servidor.

O **Sentry** é um serviço que recebe esses stack traces, agrupa os que são iguais, conta quantas vezes cada um aconteceu, e mostra tudo num painel web. Em vez de "houve erros no servidor", passa-se a ter "o erro `KeyError: 'id_modelo'` em `catalog_generic.py` linha 214 aconteceu 47 vezes nas últimas 3 horas, todas no mesmo endpoint".

### DSN — o que é e porque é sensível

**DSN** significa *Data Source Name* — literalmente "nome da fonte de dados". É o endereço para onde o programa envia os erros, e tem um formato como `https://<chave-publica>@<id-organizacao>.ingest.<regiao>.sentry.io/<id-projecto>`.

O DSN é a única configuração necessária. Contém a chave de ingestão embutida no próprio endereço. Por isso, na Diomika, **o DSN é tratado como um segredo**: vive no ficheiro `.env` da máquina virtual, que está no `.gitignore` (a lista de ficheiros que o Git — o sistema de controlo de versões — nunca deve guardar). Não está no repositório, não está no instalador do backoffice, não está no código da loja.

Vale a pena entender **porquê** é sensível, mesmo sendo tecnicamente uma chave "pública" (do lado do cliente, o Sentry até é usado em browsers com DSN visível). Quem tiver o DSN pode **enviar erros falsos** para o projecto. O ataque não é roubar dados — é poluição: milhares de erros inventados que consomem a quota mensal do plano gratuito e escondem os erros verdadeiros no meio do ruído. Como a Diomika corre em plano gratuito com quota limitada, isso seria um ataque de negação de serviço (DoS, *Denial of Service*) ao próprio sistema de observabilidade. Daí a decisão de manter o DSN apenas no servidor.

### A questão da região e onde ficam os dados

Repare-se no segmento `<regiao>` no formato do DSN. A região não é uma opção de configuração do nosso lado: é decidida **quando a organização é criada** no Sentry, e fica embutida no endereço de ingestão. Não se muda depois com uma variável de ambiente — mudar exigiria criar uma organização nova e substituir o DSN.

Isto importa porque a Diomika trata a localização de dados como um critério consistente, e não caso a caso. Nos dois serviços onde a decisão está explicitamente registada no repositório, ela é europeia: o Axiom é uma organização **EU Central**, com ingestão em `eu-central-1.aws.edge.axiom.co` (`.env.example`, `deploy/env.free.example`, `deploy/OPS.md`), e o PostHog usa a instância `eu.i.posthog.com` (`CookieBanner.vue`). O raciocínio é o mesmo nos dois casos: manter os dados dentro do Espaço Económico Europeu evita toda a discussão sobre transferência internacional de dados pessoais ao abrigo do RGPD, e é a escolha coerente para os erros da API pela mesma razão.

Dito isto, para o Sentry especificamente há um controlo que faz mais trabalho do que a região: o `send_default_pii=False` descrito abaixo. A região determina **onde** os dados ficam alojados; a minimização determina **que** dados chegam a sair do servidor. Um erro sem informação pessoal anexada é pouco sensível independentemente do continente onde é armazenado, e é por isso que a desactivação de PII é a decisão mais consequente das duas.

### Como está implementado

O ficheiro é `backend-api/core/sentry_init.py`, e é curto de propósito. A sequência é:

1. Lê `SENTRY_DSN`. Se estiver vazio, devolve `False` e nada acontece.
2. Tenta importar o `sentry-sdk` (o **SDK**, *Software Development Kit*, é a biblioteca oficial do Sentry para Python). Se a biblioteca não estiver instalada, escreve um aviso no log — `"SENTRY_DSN definido mas sentry-sdk não instalado"` — e devolve `False`. Repare-se na atenção ao detalhe: uma configuração presente com biblioteca ausente é uma situação silenciosamente enganadora, e o código grita em vez de fingir.
3. Lê o ambiente de `DIOMIKA_ENV` (por omissão `development`), para que os erros no painel apareçam etiquetados como sendo de produção ou de desenvolvimento e não se misturem.
4. Calcula a **taxa de amostragem de traces** (`traces_sample_rate`): por omissão `0.05` em produção e `0.0` fora dela, configurável por `SENTRY_TRACES_SAMPLE_RATE`, e sempre limitada ao intervalo de 0 a 1.
5. Inicializa o SDK com `send_default_pii=False` e duas integrações: `StarletteIntegration` e `FastApiIntegration`, ambas com `transaction_style="endpoint"`.

Três destes pontos merecem explicação para leitor não técnico.

**A amostragem de 5%.** Um "trace" não é um erro: é a gravação detalhada do percurso de um pedido bem-sucedido, com tempos de cada etapa. É útil para perceber lentidão, mas é caro em volume. `0.05` significa "grava um em cada vinte pedidos". Isto é suficiente para ver tendências estatísticas de desempenho e consome vinte vezes menos quota do plano gratuito do que gravar tudo. Os **erros**, ao contrário dos traces, são enviados a 100% — nunca se descarta um erro.

**`send_default_pii=False`.** **PII** significa *Personally Identifiable Information* — informação pessoalmente identificável: nomes, endereços de correio electrónico, endereços de protocolo de internet (IP), cabeçalhos de autenticação. Por omissão, muitos SDK de monitorização anexam este contexto aos erros porque ajuda a depurar. A Diomika desliga-o explicitamente. A razão é dupla: obrigação legal ao abrigo do Regulamento Geral sobre a Protecção de Dados (RGPD), e redução de risco — dados pessoais que nunca saem do servidor não podem ser expostos numa fuga de um fornecedor terceiro. É um exemplo directo do princípio da **minimização de dados**.

**`transaction_style="endpoint"`.** Sem isto, o Sentry agruparia os erros pelo caminho literal do pedido: `/catalogo/produtos/8f3a-...`, `/catalogo/produtos/91bc-...`, e assim por diante — mil erros "diferentes" que são o mesmo erro. Com `endpoint`, agrupa pela **rota declarada** no código, e os mil tornam-se uma entrada com contador 1000.

### A rede de segurança: Sentry local quando não há Sentry na nuvem

Existe uma camada acima do Sentry, em `backend-api/core/error_tracking.py`, cuja docstring diz literalmente *"Sink local de erros — Sentry €0 (sempre activo)"*.

A função `init_error_tracking()` tenta arrancar o Sentry. Se conseguir, devolve a palavra `"sentry"`. Se não conseguir (sem DSN, ou sem biblioteca), cria a pasta `backend-api/logs/` e devolve `"local"`. O modo escolhido é escrito no arranque em `main.py`: `logger.info("Error tracking mode=%s", _error_mode)`.

No modo local, a função `capture_exception` grava cada erro numa linha de um ficheiro **JSONL** (*JSON Lines* — um formato onde cada linha do ficheiro é um objecto JSON independente, muito prático para ler linha a linha sem carregar tudo para memória). O caminho por omissão é `backend-api/logs/errors.jsonl`, configurável por `ERROR_LOG_FILE`. Cada linha contém o instante em tempo universal coordenado (UTC), o tipo da excepção, a mensagem truncada a 500 caracteres, o caminho do pedido e o identificador do pedido. A escrita é protegida por um `threading.Lock` para que dois pedidos simultâneos não escrevam a mesma linha em cima um do outro.

A ligação final está no manipulador global de excepções em `backend-api/main.py`. Quando algo rebenta e nenhuma rota apanhou:

- escreve-se `logger.exception(...)` — que vai para os logs e, portanto, para o Axiom;
- chama-se `capture_exception(...)` com o caminho e o identificador do pedido — que vai para o Sentry ou para o ficheiro local;
- **em produção devolve-se ao cliente apenas `{"detail": "Erro interno"}`**, com código 500 e nada mais.

Esse último ponto é segurança elementar e é frequentemente esquecido: um stack trace devolvido ao browser revela caminhos de ficheiros no servidor, nomes de bibliotecas e respectivas versões, e estrutura interna — tudo material de reconhecimento para um atacante. Em desenvolvimento a mensagem completa aparece (porque ajuda a trabalhar); em produção, nunca.

---

## VII.3 Axiom — logs estruturados

### Logs: de texto para dados

Um **log** é um registo cronológico. Historicamente eram linhas de texto livre:

```
2026-08-14 17:03:11 ERROR falhou o envio para joana@exemplo.pt depois de 3 tentativas
```

Isto lê-se bem com olhos humanos e é péssimo para máquinas. Para responder à pergunta "quantos erros de envio houve ontem entre as 14h e as 16h?" é preciso escrever expressões regulares frágeis que se partem no dia em que alguém muda a redacção da mensagem.

**Logging estruturado** resolve isto ao gravar cada evento como um objecto com campos nomeados, em JSON (*JavaScript Object Notation*, um formato de texto para dados estruturados, universalmente legível por máquinas):

```json
{"ts":"2026-08-14T17:03:11.482913+00:00","level":"ERROR","logger":"diomika-api","msg":"..."}
```

Agora "quantos erros ontem entre as 14h e as 16h" é uma consulta trivial, porque `level` e `ts` são campos e não pedaços de frase.

### O formatador de JSON

Na Diomika isto está em `backend-api/core/structured_logging.py`, na classe `JsonFormatter`. Cada registo produz sempre quatro campos base:

- `ts` — o instante em UTC no formato ISO 8601 (norma internacional para datas, do tipo `2026-08-14T17:03:11+00:00`). Usar UTC e não hora local é deliberado: evita a ambiguidade das mudanças de hora de verão e permite correlacionar com logs de outros sistemas sem aritmética de fusos.
- `level` — a gravidade: `INFO`, `WARNING`, `ERROR`.
- `logger` — que subsistema falou (por exemplo `diomika-api`, `diomika-alerts`, `diomika-anomaly`).
- `msg` — a mensagem.

Se o registo trouxer uma excepção, é acrescentado `exc` com o stack trace formatado. E há um detalhe importante: o formatador procura cinco campos opcionais e, se estiverem presentes, copia-os para o JSON de saída:

```python
for key in ("request_id", "path", "method", "status", "ms"):
    if hasattr(record, key):
        payload[key] = getattr(record, key)
```

O `request_id` é a peça que transforma logs numa ferramenta de investigação real. O `RequestIdMiddleware` (em `core/middleware.py`) atribui a cada pedido um identificador único universal (**UUID**, *Universally Unique Identifier*) — ou reutiliza o que vier no cabeçalho `X-Request-Id` — e devolve-o ao cliente no mesmo cabeçalho da resposta. Ou seja: quando alguém se queixa de um erro, se tiver o identificador do pedido, filtra-se por esse valor no Axiom e obtêm-se **exactamente as linhas daquele pedido específico**, entre milhares de outros do mesmo minuto.

### Quando é que o JSON está ligado

Em `main.py`, antes de qualquer configuração de logging:

```python
if not (os.getenv("LOG_FORMAT") or "").strip():
    if (os.getenv("DIOMIKA_ENV") or "").strip().lower() == "production":
        os.environ["LOG_FORMAT"] = "json"
```

Traduzindo: se ninguém disse nada sobre o formato, e estamos em produção, então JSON. Em desenvolvimento fica texto simples, que é mais confortável de ler num terminal. A decisão pode ser forçada nas duas direcções com `LOG_FORMAT=json`. Este padrão — **um valor por omissão inteligente que depende do ambiente, com possibilidade de sobreposição explícita** — repete-se em toda a base de código e é o que evita ter dois conjuntos de configuração a manter.

### O `AxiomHandler` e o envio em lote

O **Axiom** é o serviço onde os logs são armazenados e pesquisados. Um **dataset** é o contentor lógico onde eles caem — na Diomika chama-se `diomika` (variável `AXIOM_DATASET`, com esse mesmo valor por omissão no código).

O `AxiomHandler` é um *handler* do sistema de logging do Python: um objecto que recebe cada registo e decide o que fazer com ele. A lógica é:

1. Lê `AXIOM_TOKEN`. Vazio, sai imediatamente — não faz nada, não custa nada.
2. Constrói o corpo do evento com `ts`, `level`, `logger`, `msg`.
3. Adiciona-o a uma fila em memória (`_axiom_queue`), protegida por `threading.Lock`.
4. **Só quando a fila tem 5 ou mais eventos** os retira todos de uma vez e os envia num único pedido.

O ponto 4 chama-se **batching** (agrupamento em lote) e é uma optimização importante. Cada pedido de rede tem um custo fixo: estabelecer a ligação, negociar a segurança da camada de transporte (**TLS**, *Transport Layer Security*, a tecnologia que faz o "s" de HTTPS), enviar cabeçalhos. Fazer isso cinco vezes para cinco linhas de log é desperdiçar cinco vezes esse custo fixo. Enviar cinco linhas num pedido é uma ligação em vez de cinco — num servidor pequeno (ver Parte IX e a máquina `e2-micro`) esta diferença é significativa. O compromisso é a **latência de visibilidade**: se o sistema estiver muito calmo e só houver 3 linhas de log, elas ficam na fila até chegar a quinta. Para um catálogo B2B, esperar por mais duas linhas de log é um custo irrelevante.

Note-se também que a fila vive **em memória do processo**. Se o processo for reiniciado com eventos pendentes, esses eventos perdem-se. Isto é aceitável pela mesma razão de antes: os logs são um sinal secundário, não uma fonte de verdade de negócio. Os dados de negócio estão no PostgreSQL e nas sagas transaccionais, não aqui.

### O detalhe que causou uma falha real: edge da União Europeia contra o caminho antigo dos Estados Unidos

Este é um dos pormenores mais instrutivos de todo o sistema, porque é o tipo de coisa que custa uma tarde de depuração e é invisível em qualquer diagrama de arquitectura.

O Axiom tem **dois formatos de endereço de ingestão**, historicamente sobrepostos:

| Geração | Endereço base | Caminho |
|---|---|---|
| Antiga (Estados Unidos) | `https://api.axiom.co` | `/v1/datasets/{dataset}/ingest` |
| Actual (edge regional) | `https://eu-central-1.aws.edge.axiom.co` | `/v1/ingest/{dataset}` |

Repare-se: não é só o domínio que muda. **A estrutura do caminho é diferente** — na antiga o nome do dataset está no meio, na nova está no fim, e o segmento `datasets` desaparece. Se se enviar o caminho antigo para a máquina nova, o pedido é rejeitado. O erro que se recebe é genérico e não diz "usaste o caminho da geração anterior".

A conta da Diomika é uma organização **EU Central**, ou seja, alojada na União Europeia. Isso não é uma preferência estética: é uma decisão de conformidade com o RGPD. Logs contêm caminhos de pedidos, mensagens de erro e ocasionalmente fragmentos de contexto — mantê-los dentro do Espaço Económico Europeu evita toda a discussão sobre transferência internacional de dados pessoais. Foi a mesma lógica que ditou a escolha da região EU no PostHog (ver VII.4).

A solução no código é uma bifurcação de três linhas baseada no nome do domínio:

```python
base = (os.getenv("AXIOM_API_URL") or "https://api.axiom.co").rstrip("/")
if "edge.axiom.co" in base:
    url = f"{base}/v1/ingest/{dataset}"
else:
    url = f"{base}/v1/datasets/{dataset}/ingest"
```

E os comentários imediatamente acima documentam ambos os formatos, para que ninguém volte a perder a mesma tarde:

```python
# EU org: edge ingest (https://eu-central-1.aws.edge.axiom.co/v1/ingest/{dataset})
# US legacy: https://api.axiom.co/v1/datasets/{dataset}/ingest
```

A configuração em produção é `AXIOM_API_URL=https://eu-central-1.aws.edge.axiom.co`, como se vê em `.env.example`, `deploy/env.free.example` e `deploy/OPS.md`. A decisão de detectar por *substring* do domínio em vez de exigir uma variável extra do género `AXIOM_MODE=edge` é intencional: reduz a configuração que um operador tem de acertar. Quem cola o endereço da edge no `.env` obtém o comportamento correcto sem saber que existe uma bifurcação.

### Protecção contra falsificação de pedidos do lado do servidor

Antes de qualquer envio, o código chama `assert_safe_outbound_url(url)`, de `backend-api/core/ssrf_guard.py`.

**SSRF** significa *Server-Side Request Forgery* — falsificação de pedidos do lado do servidor. É uma classe de ataque onde o atacante não ataca o servidor directamente: convence o servidor a fazer um pedido em nome dele. Como o servidor está dentro da rede privada, consegue alcançar endereços que o atacante não alcança — por exemplo, na Google Cloud Platform, o endereço `169.254.169.254`, que é o serviço de metadados da instância e onde vivem credenciais da máquina virtual. Se um atacante conseguisse manipular a variável de destino dos logs para apontar para lá, o servidor iria buscar as suas próprias credenciais e enviá-las para fora.

O guarda impõe quatro regras: só o esquema `https` é aceite (nunca `http`, nunca `file://`, nunca `gopher://`); o domínio tem de existir; o domínio tem de constar de uma **lista de permissões** explícita; e se o domínio for um endereço IP literal, é comparado contra uma lista de redes bloqueadas — `127.0.0.0/8` (a própria máquina), `10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16` (redes privadas conforme o documento normativo RFC 1918), `169.254.0.0/16` (link-local, onde vivem os metadados de nuvem), e os equivalentes em IPv6.

A lista de permissões por omissão contém exactamente os destinos que o sistema realmente precisa: `api.cloudflare.com`, `challenges.cloudflare.com`, `hooks.slack.com`, `discord.com`, `discordapp.com`, `api.axiom.co`, `eu-central-1.aws.edge.axiom.co`, `us-east-1.aws.edge.axiom.co` e `ntfy.sh`. Pode ser estendida com `SSRF_ALLOW_HOSTS`. A filosofia é **negar por omissão**: um destino novo não funciona até alguém o autorizar deliberadamente. É o oposto de bloquear os maus conhecidos, abordagem que falha sempre porque a lista de maus é infinita.

---

## VII.4 PostHog — analítica de produto com consentimento

### Analítica de produto não é a mesma coisa que monitorização técnica

Sentry e Axiom respondem a "o sistema está a funcionar?". O **PostHog** responde a uma pergunta completamente diferente: "**as pessoas conseguem usar isto?**".

São perguntas independentes. Uma página pode responder com código 200, sem um único erro no Sentry, e ainda assim ser um fracasso: os visitantes chegam, não encontram o botão de orçamento, e vão-se embora. Tecnicamente perfeito, comercialmente inútil. A analítica de produto mede comportamento: que páginas se visitam, em que ordem, onde as pessoas desistem — o que se chama um **funil** (a metáfora do funil: entram cem no topo, chegam três ao fundo, e a questão é onde se perderam os noventa e sete).

### Região EU e a escolha da ferramenta

A configuração está em `frontend-web/src/components/CookieBanner.vue`, e o endereço por omissão é explícito no código:

```javascript
const posthogHost = import.meta.env.VITE_POSTHOG_HOST || 'https://eu.i.posthog.com'
```

`eu.i.posthog.com` é a instância europeia. A escolha da região não é configuração acidental — é a mesma decisão de RGPD do Axiom, aplicada a dados mais sensíveis, porque analítica de comportamento envolve identificadores de visitante e é matéria de tratamento de dados pessoais.

Vale registar que houve uma escolha entre alternativas, documentada em `deploy/APRESENTACAO_CLIENTE.md`. O Plausible foi considerado e **rejeitado**, e o mesmo documento lista o que foi "removido de propósito (era pior/duplicado): Plausible, pageviews first-party `/metrics/hit`, Grafana na VM". O Plausible é mais simples e mais leve, e por isso mesmo insuficiente: não faz funis nem análise de percursos. Havia também uma implementação caseira de contagem de visitas num endpoint próprio, que foi eliminada — manter código próprio para resolver um problema que um plano gratuito resolve melhor é custo permanente de manutenção sem benefício.

### Consentimento: a parte legal e a parte técnica, feitas a sério

Aqui é preciso ser preciso, porque a maioria dos sítios web faz isto mal.

A lei europeia sobre cookies e tecnologias equivalentes exige **consentimento prévio, informado e específico** antes de colocar no dispositivo do utilizador qualquer coisa que não seja estritamente necessária ao funcionamento do serviço. Analítica **não** é estritamente necessária. Portanto o consentimento tem de vir **antes**.

O erro comum é mostrar o aviso de cookies e, ao mesmo tempo, já ter carregado e inicializado a biblioteca de analítica por trás. Nesse caso o aviso é teatro: os dados já foram recolhidos, e o botão "Recusar" apenas esconde a janela.

A Diomika implementa a versão correcta, e o mecanismo que garante isso é a **importação dinâmica**:

```javascript
const loadPosthog = async () => {
  if (!posthogKey || window.__diomikaPosthog) return
  try {
    const { default: posthog } = await import('posthog-js')
    posthog.init(posthogKey, { ... })
    window.__diomikaPosthog = true
  } catch { /* ignore */ }
}
```

`await import('posthog-js')` é uma importação que só acontece **no momento em que a linha corre**. Como essa função só é chamada por `accept()` (o botão "Aceitar") ou quando já existe consentimento gravado de uma visita anterior, o código do PostHog **nunca é descarregado do servidor** para o browser de quem recusa. Não é apenas "não é inicializado": o ficheiro JavaScript não chega a ser transferido. Isto é verificável por qualquer pessoa: abre-se o painel de ferramentas de desenvolvimento do browser, separador de rede, recusa-se, e não existe pedido nenhum para `posthog`.

O fluxo completo, na função `onMounted` (que corre quando o componente aparece):

1. Lê a chave `diomika_cookie_consent` do armazenamento local (`localStorage`, uma pequena base de dados que o browser mantém por domínio, persistente entre visitas).
2. Se o valor for `'accepted'` — carrega o PostHog e **não mostra o aviso**. Quem já disse sim não é incomodado outra vez.
3. Se for `'rejected'` — não carrega nada e não mostra o aviso. Quem disse não também não é incomodado outra vez. Isto é uma decisão de respeito pelo utilizador que muitos sítios violam propositadamente, voltando a perguntar a cada visita até a pessoa ceder por cansaço.
4. Se não houver valor gravado **e não existir chave do PostHog configurada**, também não mostra o aviso. O comentário no código explica: `// Sem key PostHog: não mostrar banner (nada a consentir além do essencial)`. Não faz sentido pedir consentimento para uma recolha que não vai acontecer — e um aviso de cookies desnecessário é apenas atrito imposto ao visitante.
5. Só no caso restante — sem decisão anterior e com analítica configurada — o aviso aparece.

O aviso em si é acessível: um elemento `<aside>` com `role="dialog"` e `aria-label="Consentimento de cookies"`, para que leitores de ecrã o anunciem correctamente. Os dois botões — "Recusar" e "Aceitar" — têm igual proeminência visual, o que é o oposto do padrão manipulador de tornar a recusa cinzenta e minúscula. Há uma ligação para `/privacidade` com o texto "Saiba mais", que é o requisito de consentimento **informado**.

As opções de inicialização são `persistence: 'localStorage'`, `autocapture: true` e `capture_pageview: true`. `autocapture` significa que o PostHog registra automaticamente cliques e interacções sem ser necessário instrumentar cada botão à mão — uma escolha pragmática para um sítio pequeno, onde o custo de instrumentação manual não se justifica.

### Onde vive a chave do PostHog

Ao contrário do `SENTRY_DSN`, a chave do PostHog **é embutida no código que corre no browser**. O prefixo `VITE_` no nome (`VITE_POSTHOG_KEY`) indica isso mesmo: no Vite (a ferramenta que constrói a loja), só variáveis com esse prefixo são incluídas no resultado final, precisamente para tornar essa fronteira explícita e evitar que alguém injecte um segredo de servidor por distracção.

Consequência operacional relevante: como a chave é embutida na **construção** (*build*), mudá-la exige **reconstruir e voltar a publicar** a loja no Cloudflare Pages. Não é uma variável de ambiente do servidor que se altera e reinicia — é uma constante compilada no ficheiro JavaScript. Está documentado como tal em `deploy/OPS.md`, sob "analytics loja (Pages)".

Essa fronteira é activamente verificada. O programa `deploy/verify_bundle_secrets.py` mantém uma lista `ALLOWED_PUBLIC` onde `VITE_POSTHOG_KEY` e `VITE_POSTHOG_HOST` constam como aceitáveis no resultado da construção, e uma lista `FORBIDDEN_PATTERNS` com o que nunca pode aparecer — `service_role`, `SUPABASE_KEY`, `API_SECRET_KEY`, `MAIL_PASSWORD`, `TURNSTILE_SECRET`, `SUPABASE_DB_PASSWORD` e senhas de IMAP (*Internet Message Access Protocol*, o protocolo de leitura de correio electrónico). Ver Parte IX.4.

---

## VII.5 ntfy — alertas push baratos

### O problema: dados gravados que ninguém lê

Sentry, Axiom e PostHog são todos **passivos**. A informação está lá, correctamente organizada, à espera que um humano abra o browser. Se o sistema começar a falhar às 3h da manhã de domingo, os três painéis registam tudo com fidelidade impecável — e ninguém sabe até segunda-feira.

Para o subconjunto de eventos que **exigem acção humana imediata**, é preciso um canal activo: algo que faça o telefone vibrar.

### O que é o ntfy

O **ntfy** (pronuncia-se "notify") é um serviço de notificações push extremamente simples. O modelo é: escolhe-se um nome de **tópico** (*topic*), faz-se um pedido HTTP POST para `https://ntfy.sh/<nome-do-topico>` com um corpo, e quem estiver subscrito a esse tópico na aplicação móvel recebe uma notificação. Não há registo de conta, não há chaves de interface de programação, não há configuração de projecto.

Essa simplicidade é ao mesmo tempo a virtude e a limitação, e é importante ser honesto sobre a limitação: **o nome do tópico é a única credencial**. Quem descobrir o nome do tópico pode enviar notificações para lá (poluição) e, na configuração pública, pode subscrever e ler o que passa. Por isso o nome do tópico é tratado como segredo na Diomika — e é por isso que consta explicitamente da lista de coisas que **não** vão para o cliente, em `RELATORIO_TECNICO.md` §8: *"Topic ntfy"*.

O domínio `ntfy.sh` está na lista de permissões do guarda de SSRF, ao lado de `hooks.slack.com`, `discord.com` e `discordapp.com` — a implementação de alertas é agnóstica quanto ao destino, e o mesmo código serve os quatro.

### Como está implementado

O ficheiro é `backend-api/core/alerts.py`. A função principal chama-se `send_alert(title, *, severity="warning", detail=None)` e faz quatro coisas por esta ordem exacta:

**1. Monta a carga útil.** Um objecto com `text` (no formato `[Diomika/<severidade>] <título>`, pensado para ser legível numa notificação de telefone com pouco espaço), mais os campos separados `severity`, `title`, `detail` e `ts`.

**2. Escreve no log da aplicação.** `logger.warning("ALERT %s: %s %s", ...)` — o que significa que **todo o alerta também vai para o Axiom**, sem código adicional, porque o `AxiomHandler` está ligado ao logger raiz. Duas ferramentas, um ponto de instrumentação.

**3. Grava sempre num ficheiro local.** Em `deploy/alerts.log` por omissão, configurável por `ALERT_LOG_FILE`. Esta é a peça mais subestimada do desenho: mesmo que não haja webhook configurado, mesmo que a rede esteja em baixo, mesmo que o ntfy tenha desaparecido do mundo, **existe um registo dos alertas na máquina virtual**. É o histórico de último recurso para uma investigação forense — e o ficheiro está no `.gitignore`, porque contém detalhes operacionais (nomes de utilizador, endereços IP de tentativas de login) que não pertencem a um repositório.

**4. Envia para o webhook, se houver.** Lê `ALERT_WEBHOOK_URL` ou, em alternativa, `SLACK_WEBHOOK_URL`. Se estiver vazio, devolve `True` e termina. Se estiver preenchido, valida o endereço com `assert_safe_outbound_url` — e se o guarda o rejeitar, escreve `logger.error("ALERT webhook URL rejeitada pelo SSRF guard: %s", exc)` e **ainda assim devolve `True`**. O envio é feito com `timeout=8`.

Aquele detalhe de devolver `True` mesmo em caso de falha merece explicação, porque parece errado. `send_alert` é chamada de dentro de caminhos de negócio — por exemplo, no meio de uma tentativa de login. Se ela lançasse uma excepção quando o webhook falhasse, uma avaria no serviço de notificações passaria a produzir erros 500 no login. O valor devolvido significa portanto "o alerta foi registado de forma durável", não "a notificação chegou ao telefone". A garantia real é o ficheiro local do ponto 3; o webhook é entrega em melhor esforço.

### O que gera alertas hoje

Não é qualquer coisa — é uma lista curta e deliberada, porque um canal de alertas que grita por tudo é um canal que se aprende a ignorar (o fenómeno conhecido como *alert fatigue*, fadiga de alertas):

| Evento | Onde | Severidade |
|---|---|---|
| Pedido acima do limiar de latência | `middleware.py`, `LatencyAlertMiddleware` | `warning` |
| Login de administrador falhado | `routes/admin_auth.py` | `warning` |
| Password de administrador alterada | `routes/admin_auth.py` | `warning` |
| Padrão de força bruta detectado | `core/anomaly.py` | `critical` |

Existe ainda o auxiliar `alert_if(condition, title, **detail)`, que só dispara se a condição for verdadeira e usa sempre severidade `critical` — açúcar sintáctico para verificações do género "se a fila de saída passou de N, grita".

O caso da anomalia (`core/anomaly.py`) ilustra bem a preocupação com fadiga de alertas. A função `note_login_failure` não alerta a cada falha. Mantém, por combinação de utilizador e endereço IP, a lista dos instantes das falhas recentes, e só alerta quando há **8 ou mais falhas numa janela de 600 segundos** (dez minutos) — valores configuráveis por `ANOMALY_LOGIN_FAIL_THRESHOLD` e `ANOMALY_LOGIN_FAIL_WINDOW_SEC`. Depois de alertar, aplica um **período de silêncio** de 900 segundos (quinze minutos, `ANOMALY_ALERT_COOLDOWN_SEC`) para aquela combinação. Sem esse silêncio, um ataque de força bruta sustentado geraria uma notificação por tentativa — milhares de vibrações que tornariam o telefone inútil precisamente no momento em que era mais preciso prestar atenção.

---

## VII.6 UptimeRobot — verificações externas a cada 5 minutos

### Porque é que os testes de dentro não bastam

Todas as ferramentas anteriores têm uma característica em comum: **correm dentro do sistema**. O Sentry recebe erros do processo da API; o Axiom recebe logs desse processo; os alertas são enviados por esse processo.

Isto tem um ponto cego enorme e obvio quando se enuncia: **se o processo estiver morto, não envia nada**. Um servidor que arde não envia um alerta a dizer que ardeu. E o silêncio é ambíguo — silêncio pode significar "está tudo bem, nada a reportar" ou "está tudo destruído". Não se consegue distinguir uma coisa da outra de dentro.

Um **monitor de uptime** resolve o problema por inversão: vive **fora** do sistema, num terceiro independente, e pergunta periodicamente "estás vivo?". Se não houver resposta, é ele que alerta. A propriedade fundamental é a independência do destino do que está a ser observado.

### A configuração na Diomika

Estão configurados dois monitores no **UptimeRobot** (serviço externo, plano gratuito), com intervalo de **5 minutos**:

| Monitor | Endereço | O que confirma |
|---|---|---|
| API | `https://api.diomika.com/health` | Cloudflare, Tunnel, contentor Docker e processo Python estão todos vivos |
| Loja | `https://www.diomika.com` | O Cloudflare Pages serve a loja |

O caminho `/health` foi escolhido de propósito, e há razão para isso. Poderia usar-se a raiz da API, mas `/health` é o único endereço público desenhado para ser barato: `build_health(detailed=False)` devolve apenas `{"status": "online", "version": ...}` — **sem tocar na base de dados**, sem consultar o Redis, sem verificar coisa nenhuma. Isto importa porque 5 minutos de intervalo, indefinidamente, são cerca de 8 640 pedidos por mês. Se cada um deles fizesse uma consulta ao PostgreSQL, o monitor consumiria quota da base de dados só para perguntar se está de pé. Além disso, `/health` está explicitamente excluído do alerta de latência (`if elapsed_ms >= self.threshold_ms and not request.url.path.startswith("/health")`), para que verificações de saúde não gerem notificações.

Há uma cadeia importante embutida naquela verificação de uma linha. Quando o UptimeRobot obtém 200 de `https://api.diomika.com/health`, isso prova **todas** estas coisas ao mesmo tempo: a resolução do nome no sistema de nomes de domínio (**DNS**) funciona; o Cloudflare está a servir a zona; o certificado TLS é válido; o **Tunnel** do Cloudflare está ligado (ver Parte X.2); o processo `cloudflared` na máquina virtual está vivo; o contentor Docker da API está de pé; e o processo Python está a responder. Um único pedido HTTP valida sete camadas. É a definição de uma verificação de alto valor por custo baixo.

As notificações são por correio electrónico, em **ambas as direcções**: quando o serviço cai (*down*) e quando volta (*up*). A segunda metade é frequentemente esquecida e é essencial. Sem a notificação de recuperação, quem recebe o alerta de queda não sabe se ainda está em baixo — e vai investigar um problema que se resolveu sozinho há vinte minutos.

### O segundo monitor, gratuito e independente

Existe uma verificação redundante em `.github/workflows/uptime.yml`, que corre na infra-estrutura do GitHub Actions:

```yaml
on:
  schedule:
    - cron: "*/15 * * * *"
  workflow_dispatch:
```

A expressão `*/15 * * * *` é sintaxe **cron** (o agendador clássico do Unix): os cinco campos são minuto, hora, dia do mês, mês e dia da semana, e `*/15` no primeiro campo significa "a cada 15 minutos". `workflow_dispatch` acrescenta a possibilidade de o disparar à mão a partir da interface web.

O trabalho instala Python 3.12 e corre `deploy/uptime_check.py --url "$API_URL"`, onde o endereço vem do segredo `API_HEALTH_URL` do repositório. Se o segredo não estiver definido, o passo **não falha** — imprime `"Skip: define secret API_HEALTH_URL"` e termina com sucesso. Esta escolha evita que um repositório clonado sem segredos configurados tenha a integração contínua permanentemente vermelha por uma razão que não é um defeito.

O programa `deploy/uptime_check.py` é usado tanto aqui como manualmente. Aceita `--url`, `--ready` e `--timeout` (por omissão 15 segundos), e é tolerante quanto ao endereço que recebe: se já terminar em `/health`, usa-o tal como está; se não, acrescenta `/health`. A validação não é apenas o código de estado — exige 200 **e** que o corpo contenha `online`, `ready` ou `ok`:

```python
ok = st == 200 and ("online" in body or "ready" in body or "ok" in body.lower())
```

A razão é defensiva: existem situações em que uma camada intermédia (uma página de erro de um serviço de rede, um portal cativo, uma página de manutenção do Cloudflare) devolve 200 com conteúdo que não é a nossa aplicação. Verificar o conteúdo distingue "a minha API respondeu" de "algo respondeu por ela".

Com `--ready`, verifica também `/health/ready`, que é uma sonda mais profunda: chama `_db_ping()` e devolve 503 se a base de dados não responder. A distinção entre as duas sondas é a distinção clássica entre **liveness** (o processo está vivo?) e **readiness** (o processo está em condições de servir tráfego?). Um processo pode estar vivo e não conseguir chegar à base de dados — nesse caso deve continuar de pé (para não entrar num ciclo de reinícios) mas anunciar que não está pronto.

Há ainda um detalhe curioso e revelador: todos estes programas enviam um cabeçalho `User-Agent` (agente do utilizador — a etiqueta que identifica quem faz o pedido) explícito, como `"Mozilla/5.0 (compatible; DiomikaUptime/1.0)"`. Isto existe porque uma das regras de firewall de aplicação web em `deploy/cloudflare/waf_rules.json` bloqueia pedidos sem agente do utilizador:

```json
{ "name": "block-empty-ua", "expression": "(http.user_agent eq \"\")", "action": "block" }
```

A regra é boa (a maioria dos programas automáticos maliciosos não se identifica), mas afecta também as nossas próprias ferramentas — que passam a ter de se identificar. É um bom exemplo de como uma decisão de segurança tem consequências que se propagam para sítios inesperados, e de como isso está resolvido em vez de esquecido.

---

## VII.7 Verificações de saúde e alertas de latência

### As três sondas de saúde

A API expõe três endereços de saúde, com finalidades e níveis de protecção diferentes. Estão declarados em `backend-api/main.py` e a lógica está em `backend-api/core/health.py`.

**`GET /health` — público, barato.**

```json
{"status": "online", "version": "..."}
```

Nada mais. É deliberadamente pobre em informação: qualquer pessoa na internet pode chamá-lo, e quanto menos revelar, melhor. É o alvo do UptimeRobot e da verificação prévia do backoffice Electron.

**`GET /health/ready` — público, toca na base de dados.**

Chama `_db_ping()` e devolve `{"status": "ready"|"degraded", "database": true|false}`; se a base de dados falhar, a rota levanta 503.

O `_db_ping()` é mais sofisticado do que parece e conta uma história. A primeira tentativa é uma consulta minúscula pela interface REST do Supabase (`select("id").limit(1)` na tabela `outbox_events`), executada num `ThreadPoolExecutor` com **timeout de 2 segundos**. O padrão do executor com prazo existe porque a biblioteca cliente é síncrona e uma chamada de rede pendurada bloquearia o processo — o executor permite desistir.

Se essa tentativa falhar, há um **segundo caminho**: `_pg_ping()`, que se liga directamente ao PostgreSQL com `psycopg2`, força `sslmode=require` se não estiver no endereço, e executa `SELECT 1`. O comentário no código explica exactamente porquê: *"Fallback quando o REST Supabase falha (ex.: CA partida no host) mas o Postgres responde."* Traduzindo: já aconteceu que o conjunto de certificados de autoridade certificadora (**CA**, *Certificate Authority*) da máquina estava corrompido, o que fazia a camada REST em HTTPS falhar na validação do certificado enquanto a ligação directa em PostgreSQL continuava a funcionar. Sem o segundo caminho, o sistema declarar-se-ia doente estando são. Este é conhecimento operacional adquirido a partir de uma avaria real, cristalizado em código.

**`GET /health/detail` — protegido, informação completa.**

Esta rota tem **duas** dependências de segurança:

```python
@app.get("/health/detail", dependencies=[Depends(admin_must_be_local), Depends(require_ops)])
```

`admin_must_be_local` exige origem em loopback (a própria máquina) ou o cabeçalho válido do backoffice desktop (ver Parte VIII.7 e X.3). `require_ops` exige o papel de operações. Além disso, `/health/detail` consta da lista `_PRIVILEGED_PREFIXES` do `PrivilegedPathMiddleware` (`core/path_guard.py`), a par de `/admin` e `/system` — ou seja, é bloqueado numa camada anterior à própria rota, e a regra de firewall no Cloudflare bloqueia-o antes de o pedido chegar à máquina virtual. Três camadas independentes para a mesma restrição.

O que devolve inclui: ambiente, se a base de dados responde, se o armazenamento é privado ou público, se o limitador de taxa está a usar Redis ou memória, se é exigida chave de interface, se a notificação de contacto por correio electrónico está configurada, o estado do disjuntor de SMTP (aberto ou fechado), o estado do trabalhador de correio electrónico, o número de eventos pendentes na fila de saída, o retrato das *feature flags*, e dois booleanos: `sentry` e `axiom`.

Aqueles dois últimos são notáveis pela sua modéstia:

```python
"sentry": bool((os.getenv("SENTRY_DSN") or "").strip()),
"axiom": bool((os.getenv("AXIOM_TOKEN") or "").strip()),
```

Devolvem **se a variável existe**, não o seu valor. É a maneira certa de responder à pergunta operacional "a monitorização está ligada nesta máquina?" sem transformar a rota de diagnóstico numa fuga de credenciais. Se um dia a protecção da rota falhasse, o pior que se revelava era a existência de configuração, não o seu conteúdo.

Detalhe de eficiência: a contagem de pendentes na fila de saída usa `_outbox_pending_cached()`, com cache de 30 segundos e prazo de 2 segundos, e em caso de falha devolve o último valor conhecido em vez de rebentar. Uma rota de diagnóstico que fica lenta ou falha quando o sistema está sob stress é uma rota que não serve para nada precisamente quando é mais necessária.

### O alerta de latência

Está em `core/middleware.py`, na classe `LatencyAlertMiddleware`, e a docstring resume-o: *"Alerta se request demorar mais que ALERT_LATENCY_MS (default 2000 — sempre on)"*.

O funcionamento é simples e a implementação tem cuidados que vale a pena notar. No construtor, o limiar é lido de `ALERT_LATENCY_MS` com **duas** protecções: `max(0, int(...))` impede valores negativos, e um `except ValueError` trata o caso de alguém escrever texto na variável, voltando a 2000. Configuração inválida não deve derrubar o arranque do serviço.

A medição usa `time.perf_counter()`, e não `time.time()`. A diferença é técnica mas relevante: `time.time()` devolve a hora do relógio de parede, que pode saltar para trás ou para a frente quando o sistema sincroniza com um servidor de tempo; `perf_counter()` é um contador monotónico, feito para medir intervalos, e nunca anda para trás. Medir durações com o relógio de parede pode produzir durações negativas.

Se o pedido igualar ou exceder o limiar, e não for um caminho `/health`, dispara `send_alert` com severidade `warning` e um detalhe rico: caminho, método, milissegundos decorridos, limiar configurado e o **identificador do pedido**. Esse último campo é o que fecha o ciclo entre ferramentas: recebe-se a notificação no telefone com um identificador, cola-se esse identificador na pesquisa do Axiom, e obtêm-se todas as linhas de log daquele pedido lento em particular.

O limiar de 2 segundos é um julgamento calibrado para este sistema específico. A API corre numa máquina virtual `e2-micro` (a categoria gratuita da Google Cloud Platform, com recursos muito modestos) e fala com o Supabase e com o serviço de correio electrónico pela rede. Duzentos milissegundos seria irrealista e produziria ruído contínuo; dez segundos deixaria passar problemas reais. Dois segundos é o ponto onde "isto está anormalmente lento" começa a ser verdade neste contexto — e é ajustável sem alterar código.

Todo o mecanismo está envolto em `try/except Exception: pass`, pela razão de sempre: um pedido lento não deve tornar-se um pedido falhado por causa do alerta sobre a lentidão.

### A ordem dos middlewares

Uma nota sobre um pormenor que já causou confusão e está documentado no código. Em `main.py`:

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

Um **middleware** é uma camada que envolve o tratamento do pedido: vê-o à entrada, delega, e vê a resposta à saída. Como cebolas, uma dentro da outra.

O detalhe contra-intuitivo é que o Starlette (a base do FastAPI) **inverte** a ordem de adição: o último adicionado fica a camada mais exterior. Portanto o `PrivilegedPathMiddleware` — o guarda que bloqueia `/admin` e `/system` — é o primeiro a ver qualquer pedido, o que é exactamente o que se quer de um guarda. E o `RequestIdMiddleware` está imediatamente por dentro dele, para que o identificador exista antes das camadas seguintes o poderem usar.

---

## VII.8 Feature flags `FEATURE_*`

### O conceito

Uma **feature flag** (bandeira de funcionalidade, também chamada *feature toggle*) é um interruptor que liga ou desliga uma parte do comportamento do sistema **sem alterar o código**.

O valor disto percebe-se com um cenário concreto. Suponha-se que o formulário de contacto começa a ser alvo de abuso automatizado, ou que o serviço de correio electrónico do fornecedor está em baixo e cada submissão gera um erro. As opções sem feature flags são: publicar uma versão nova com o formulário removido (minutos ou horas de trabalho, mais risco de introduzir outro defeito no meio de uma crise), ou deixar o problema a acontecer. Com uma feature flag, a operação é: mudar `FEATURE_CONTACT_FORM=0` no `.env`, reiniciar o contentor, e em segundos o formulário responde com uma mensagem educada de indisponibilidade em vez de falhar. Depois de resolvido o problema, inverte-se.

### A implementação

O ficheiro é `backend-api/core/feature_flags.py` e tem 29 linhas. A função central:

```python
def flag(name: str, default: bool = False) -> bool:
    key = f"FEATURE_{(name or '').strip().upper()}"
    raw = os.getenv(key)
    if raw is None or not str(raw).strip():
        return default
    return str(raw).strip().lower() in ("1", "true", "yes", "on")
```

Quatro decisões de desenho merecem nota.

**A convenção de nome é automática.** Pede-se `flag("CONTACT_FORM")` e a função procura `FEATURE_CONTACT_FORM`. O prefixo nunca é escrito à mão em nenhum ponto de chamada, o que impede a divergência clássica em que metade do código usa um prefixo e a outra metade outro.

**Ausência e vazio são a mesma coisa.** Tanto uma variável inexistente como uma variável definida com espaços em branco recuperam o valor por omissão. Isto é importante em ficheiros `.env` reais, onde `FEATURE_CONTACT_FORM=` (definida, mas vazia) acontece por acidente.

**A aceitação de valores é generosa.** `1`, `true`, `yes` e `on` — em qualquer combinação de maiúsculas e minúsculas — significam ligado. Um operador humano a editar um `.env` às pressas não deve ser punido por escrever `TRUE` em vez de `1`.

**O valor por omissão é do lado de quem chama.** A assinatura tem `default=False`, mas cada ponto de chamada decide. Em `routes/contact.py` é `flag("CONTACT_FORM", True)`: o formulário está **ligado** salvo indicação contrária. Isto é a escolha correcta para a funcionalidade principal do produto — uma variável esquecida não deve desligar o negócio. Uma bandeira nova e experimental usaria `False` e teria de ser ligada explicitamente.

A segunda função dá um retrato para operações:

```python
def flags_snapshot() -> dict[str, bool]:
    known = ("CONTACT_FORM", "ORCAMENTO_FORM", "MAINTENANCE_BANNER", "CATALOG_WRITE")
    return {k: flag(k, default=True) for k in known}
```

As quatro bandeiras conhecidas são: o formulário de contacto, o formulário de pedido de orçamento, a faixa de aviso de manutenção na loja, e a escrita no catálogo. Esta função é chamada por `build_health(detailed=True)`, de modo que `/health/detail` mostra o estado real de todas as bandeiras na máquina — o que responde à pergunta operacional "porque é que o formulário está a devolver 503?" sem entrar na máquina por SSH a ler ficheiros de configuração.

### O uso real

Em `backend-api/routes/contact.py`, primeira coisa que a rota faz:

```python
from core.feature_flags import flag

if not flag("CONTACT_FORM", True):
    raise HTTPException(status_code=503, detail="Formulário temporariamente indisponível.")
```

A verificação está **antes** do limitador de taxa, antes da idempotência, antes do favo de mel anti-robô, antes do Turnstile e antes da saga. Se a funcionalidade está desligada, o pedido é recusado com o mínimo de trabalho — não vale a pena gastar uma consulta de idempotência para depois recusar.

O código de estado escolhido é 503 (*Service Unavailable*, serviço indisponível) e não 404 nem 403. Isto é semanticamente correcto e tem efeitos práticos: 503 comunica "isto existe e voltará", o que é a verdade; e os clientes HTTP e os motores de busca tratam 503 como condição temporária, não removendo o endereço dos seus índices. A mensagem devolvida está em português e é dirigida a um humano, porque quem a vai ler é um visitante da loja e não um programador.

Existem testes automáticos para isto em `backend-api/tests/test_observability_flags.py`, cobrindo os quatro casos que importam: variável ausente com valor por omissão verdadeiro devolve verdadeiro; ausente com valor por omissão falso devolve falso; `"0"` sobrepõe um por omissão verdadeiro; `"1"` sobrepõe um por omissão falso.

---

# Parte VIII — Backoffice Electron (o programa do administrador)

## VIII.1 O que é o Electron

### A ideia

O **Electron** é uma tecnologia que permite construir aplicações de secretária — programas que se instalam e abrem com duplo clique, como o Word ou o Excel — usando as mesmas ferramentas com que se constroem páginas web.

O truque é embalar duas coisas dentro do executável:

1. **Chromium** — o motor de renderização que está por baixo do Google Chrome e do Microsoft Edge. É ele que desenha a interface: interpreta HTML, aplica CSS, executa JavaScript.
2. **Node.js** — um ambiente de execução de JavaScript **fora** do browser, com acesso ao sistema operativo: ler e escrever ficheiros, abrir portas de rede, lançar processos.

O resultado é uma aplicação que **parece** um programa nativo (ícone, janela própria, aparece na barra de tarefas) e **é**, por dentro, uma página web servida e consumida por si mesma. Aplicações muito conhecidas usam esta abordagem: Visual Studio Code, Slack, Discord, Figma.

O custo é o tamanho. Como cada aplicação Electron transporta a sua própria cópia do Chromium, o executável ronda as dezenas ou centenas de megabytes, contra os poucos megabytes de um programa nativo equivalente. Para a Diomika esse custo é irrelevante: o ficheiro é transferido uma vez, e a alternativa (escrever uma aplicação nativa distinta para Windows, macOS e Linux) custaria três vezes mais desenvolvimento e três vezes mais manutenção permanente.

### Porque é que a Diomika escolheu isto

A razão fundamental é a **reutilização da interface**. A loja em `frontend-web/` é feita em Vue 3 (uma biblioteca de interfaces). O backoffice em `backoffice-desktop/` é feito **na mesma tecnologia**: `vue` e `vue-router` nas dependências, `vite` e `@vitejs/plugin-vue` no desenvolvimento. Consequências: um único conjunto de competências para manter os dois lados, um único vocabulário de componentes, e a possibilidade de correr o backoffice num browser normal durante o desenvolvimento (`npm run dev:browser`), o que acelera muito o trabalho.

A alternativa realista era um painel de administração web, acessível por browser em algo como `admin.diomika.com`. Essa alternativa foi rejeitada, e a Parte X.1 desenvolve o raciocínio completo. O resumo é: uma aplicação instalada permite um controlo que uma página web não permite — o cabeçalho de portão embutido no binário — e permite bloquear o acesso administrativo a **todos** os browsers do mundo na firewall de aplicação web.

### A configuração de segurança da janela

Em `backoffice-desktop/electron/main.cjs`, a criação da janela inclui:

```javascript
webPreferences: {
  contextIsolation: true,
  nodeIntegration: false,
  sandbox: true,
}
```

Estas três linhas são a diferença entre um Electron seguro e um Electron perigoso, e valem explicação.

`nodeIntegration: false` significa que o código da interface **não tem acesso ao Node.js**. Não pode ler ficheiros, não pode executar comandos, não pode abrir ligações arbitrárias. Sem isto, qualquer defeito que permitisse injectar JavaScript na interface passaria a permitir executar comandos no computador do cliente — uma vulnerabilidade de execução remota de código, a categoria mais grave que existe.

`contextIsolation: true` mantém o mundo JavaScript da aplicação separado do mundo JavaScript interno do Electron, para que um não possa manipular os objectos do outro.

`sandbox: true` coloca o processo de renderização na caixa de areia do sistema operativo — o mesmo mecanismo de isolamento que o Chrome usa para separar abas.

O resultado é uma inversão útil: a interface do backoffice tem **menos** privilégios do que uma página web normal teria, e comunica com o mundo exterior apenas por HTTP, através do servidor local descrito a seguir. Acrescenta-se ainda um controlo sobre a abertura de janelas:

```javascript
win.webContents.setWindowOpenHandler(({ url }) => {
  if (url.startsWith('http://127.0.0.1') || url.startsWith('http://localhost')) {
    return { action: 'deny' }
  }
  shell.openExternal(url)
  return { action: 'deny' }
})
```

Nenhuma janela nova é aberta **dentro** da aplicação, nunca. Ligações externas abrem no browser predefinido do sistema; ligações para o próprio servidor local são simplesmente negadas. Isto impede a criação de janelas Electron sem as protecções acima.

---

## VIII.2 O proxy local `/api` → `api.diomika.com`

### O problema que resolve

A interface do backoffice precisa de falar com a API em `https://api.diomika.com`. Se o fizesse directamente, surgiriam três problemas distintos.

**Primeiro: a partilha de recursos entre origens.** **CORS** (*Cross-Origin Resource Sharing*) é o mecanismo de segurança dos browsers que impede que uma página numa origem faça pedidos arbitrários a outra origem. Como o Chromium está embutido no Electron, esta regra aplica-se na mesma. Falar directamente exigiria configurar CORS no servidor para aceitar a origem da aplicação, com pedidos de pré-verificação (*preflight*) e uma lista de origens permitidas a manter.

**Segundo: o segredo de portão.** Todo o pedido administrativo tem de levar o cabeçalho `X-Diomika-Desktop` com um valor secreto. Se esse valor tivesse de ser adicionado pelo código da interface, teria de estar acessível ao JavaScript da interface — e portanto visível a quem abrisse as ferramentas de desenvolvimento. Isso destruiria o propósito.

**Terceiro: o endereço da API espalhado pelo código.** Cada chamada teria de saber o endereço absoluto, ou haveria uma configuração a passar por todos os módulos.

### A solução

O processo principal do Electron levanta um **servidor HTTP local** e faz-se passar pela origem de tudo. Em `createLocalServer()`:

```javascript
server.listen(0, '127.0.0.1', () => {
  const addr = server.address()
  resolve({ server, port: addr.port })
})
```

Duas escolhas importantes nesta linha. `'127.0.0.1'` limita o servidor à interface de loopback: **só processos no próprio computador conseguem ligar-se**, nunca outra máquina da rede local. E `0` como porta significa "pede ao sistema operativo uma porta livre qualquer" — uma **porta efémera**. Isso evita colisões com outros programas (uma porta fixa como 3000 estaria ocupada em metade dos computadores de desenvolvedores) e torna o alvo imprevisível.

Depois de arrancar o servidor, a janela carrega `http://127.0.0.1:<porta>/`. A partir daí, toda a interface vive nessa origem, e o encaminhamento é:

- Caminho começa por `/api` → **proxy** para a API na nuvem.
- Qualquer outro caminho, com método GET ou HEAD → ficheiro estático da interface construída.
- Outro método em caminho não-`/api` → 405 *Method Not Allowed*.

A configuração da interface reflecte isto de forma absoluta. Em `backoffice-desktop/src/lib/settings.js`:

```javascript
const LOCAL_API_BASE = '/api'
```

E `loadSettings()` termina sempre com `apiBaseUrl: LOCAL_API_BASE`, **sobrepondo qualquer valor guardado**. Até `saveSettings` força o mesmo valor. Isto é deliberado: não existe forma de a interface ser apontada para outro servidor, nem por acidente nem por manipulação do armazenamento local do browser. Os três problemas desaparecem de uma vez — não há CORS porque tudo é a mesma origem; o segredo nunca toca no JavaScript da interface; e nenhum módulo conhece o endereço da API.

### A função `proxyToApi` em detalhe

```javascript
const incoming = new URL(req.url || '/', 'http://127.0.0.1')
const targetPath = (incoming.pathname.replace(/^\/api/, '') || '/') + incoming.search
const target = new URL(targetPath, API_ORIGIN + '/')
```

O prefixo `/api` é retirado: um pedido a `/api/admin/auth/login` torna-se `https://api.diomika.com/admin/auth/login`. A cadeia de consulta (`?limit=200`) é preservada.

A manipulação de cabeçalhos é onde está a substância:

```javascript
const headers = { ...req.headers, host: target.host }
delete headers.origin
delete headers.referer
delete headers['accept-encoding']
headers['user-agent'] = 'DiomikaBackoffice/1.0'
if (DESKTOP_GATE) headers['x-diomika-desktop'] = DESKTOP_GATE
```

Linha por linha, e a razão de cada uma:

- **`host` reescrito** — obrigatório. Chegaria `127.0.0.1:<porta>`, e o Cloudflare precisa de `api.diomika.com` para saber que zona serve. Além disso, a API em produção tem `TrustedHostMiddleware` com `ALLOWED_HOSTS=api.diomika.com`, e rejeitaria o resto.
- **`origin` e `referer` removidos** — apontariam para `http://127.0.0.1:<porta>`, um endereço que não significa nada para o servidor e que poderia disparar lógica de CORS ou de verificação de origem indesejada. Remover é mais limpo do que forjar.
- **`accept-encoding` removido** — impede que a resposta venha comprimida (por exemplo em gzip). Sem isto, seria necessário descomprimir para reencaminhar corretamente, ou arriscar entregar dados comprimidos com cabeçalhos inconsistentes. Sacrifica-se alguma largura de banda numa ligação que é sempre curta, e ganha-se simplicidade e correcção.
- **`user-agent` fixado** — a aplicação identifica-se como `DiomikaBackoffice/1.0`, o que satisfaz a regra da firewall contra agentes vazios e torna o tráfego do backoffice identificável nos logs.
- **`x-diomika-desktop` injectado** — o portão, adicionado aqui e **só aqui**. O valor vem de `desktop-gate.cjs`, um ficheiro que o processo principal do Electron lê e que o mundo da interface nunca vê.

No caminho da resposta há um detalhe subtil e revelador:

```javascript
const outHeaders = { ...upRes.headers }
delete outHeaders['cross-origin-resource-policy']
delete outHeaders['cross-origin-opener-policy']
```

A API define `Cross-Origin-Resource-Policy: same-site` e `Cross-Origin-Opener-Policy: same-origin` no `SecurityHeadersMiddleware`. São cabeçalhos de isolamento excelentes para um browser a consumir a API pela internet. Mas neste caminho, o "site" é `127.0.0.1` e a resposta vem de `api.diomika.com` — o Chromium embutido veria uma violação de política e **bloquearia a resposta**. Removê-los na fronteira do proxy é correcto porque a fronteira de confiança aqui é diferente: o consumidor é a nossa própria aplicação, numa origem local, não uma página web arbitrária. Este é o tipo de pormenor que só se descobre a depurar um ecrã em branco inexplicável.

Por fim, o tratamento de falha traduz erros técnicos em português para humanos:

```javascript
detail: `API inacessível (${API_ORIGIN}). Verifique a internet. (${err.message})`
```

Devolvido com código 502. O utilizador do backoffice é um administrativo, não um engenheiro de redes — "verifique a internet" é accionável, `ECONNREFUSED` não é. A mensagem técnica original vai entre parênteses, para o caso de haver suporte a acompanhar.

### A verificação prévia de saúde

Antes de abrir a janela, em produção:

```javascript
const ok = await apiHealthOk()
if (!ok) {
  dialog.showErrorBox('Sem ligação à API',
    `Não foi possível contactar ${API_ORIGIN}.\nConfirme a internet e tente de novo.`)
}
```

`apiHealthOk()` faz um GET a `${API_ORIGIN}/health` com prazo de 8 segundos e considera bom qualquer código entre 200 e 499. O intervalo é intencionalmente largo: 401 ou 403 significam "o servidor está lá e a responder" — o que é precisamente o que se quer saber nesta fase. Só 5xx e ausência de resposta contam como avaria.

O valor desta verificação é de experiência de utilização. Sem ela, o cliente abriria a aplicação, veria o ecrã de login, escreveria as credenciais, esperaria, e receberia um erro obscuro. Com ela, sabe imediatamente que o problema é de ligação e não das suas credenciais. Note-se que a caixa de diálogo é informativa e **não** impede o arranque: a janela abre de seguida, porque a rede pode voltar entretanto e não faz sentido recusar-se a arrancar.

---

## VIII.3 Builds: EXE Windows, DMG macOS, AppImage Linux

### Os três formatos

O `package.json` do `backoffice-desktop` define a construção para os três sistemas operativos através do `electron-builder`:

| Sistema | Formato | Nome do artefacto | O que é |
|---|---|---|---|
| Windows | `portable` (.exe) | `Diomika-Backoffice-<versão>-windows.exe` | Executável único, sem instalação |
| macOS | `dmg` (universal) | `Diomika-Backoffice-<versão>-mac.dmg` | Imagem de disco montável |
| Linux | `AppImage` (x64) | `Diomika-Backoffice-<versão>-linux.AppImage` | Ficheiro único executável |

**Windows portable** é uma escolha deliberada em vez de um instalador tradicional. Um instalador escreve no registo do sistema, cria entradas no menu Iniciar, precisa de privilégios de administrador e tem de ser desinstalado. Um portável é **um ficheiro**: copia-se, executa-se, apaga-se. Para um cliente que precisa de um programa e não de um projecto de instalação informática, esta é a via de menor atrito — e elimina a possibilidade de a instalação falhar por falta de permissões numa máquina gerida por outra pessoa.

**macOS universal** significa um único binário que corre nativamente tanto em Mac com processador Intel como em Mac com processador Apple Silicon (as gerações M1 e seguintes). A alternativa seria distribuir dois ficheiros e explicar ao cliente qual deles descarregar — uma pergunta que nem todos os utilizadores sabem responder sobre o seu próprio computador.

**AppImage** é o formato de distribuição Linux que evita o problema das distribuições. Um pacote `.deb` funciona em Debian e Ubuntu; um `.rpm` em Fedora e derivados; um AppImage funciona em praticamente todas, porque transporta as suas dependências. Dá-se permissão de execução ao ficheiro e corre.

### A configuração relevante

```json
"appId": "pt.diomika.backoffice",
"productName": "Diomika Backoffice",
"directories": { "output": "release", "buildResources": "build" },
"files": ["dist/**/*", "electron/**/*", "package.json"]
```

O `appId` segue a convenção de nome de domínio invertido, usada pelos sistemas operativos para identificar aplicações de forma única. A lista `files` é a mais interessante: só três coisas entram no pacote — a interface construída (`dist/`), o código do processo principal (`electron/`) e o `package.json`. Nada de código-fonte, nada de dependências de desenvolvimento, nada de ficheiros do repositório. É esta lista que garante que o binário entregue ao cliente contém o mínimo necessário, e é também por aqui que o ficheiro `electron/desktop-gate.cjs` entra (por ser dentro de `electron/`).

### Os comandos de construção

```json
"dist:win": "node scripts/write-gate.cjs && vite build && electron-builder --win portable --x64",
"dist:mac": "node scripts/write-gate.cjs && vite build && electron-builder --mac dmg --universal",
"dist:linux": "node scripts/write-gate.cjs && vite build && electron-builder --linux AppImage --x64"
```

Todos começam por `node scripts/write-gate.cjs`, e o operador `&&` garante que, se esse passo falhar, **nada mais corre**. Isto é uma protecção deliberada, e a razão vê-se no próprio script:

```javascript
const gate = (fromEnv || fromFile || '').trim()
if (!gate || gate.length < 24) {
  console.error('ERRO: defina DIOMIKA_DESKTOP_GATE (>=24 chars) no .env ou no ambiente de CI.')
  process.exit(1)
}
fs.writeFileSync(out, `module.exports = ${JSON.stringify(gate)}\n`, 'utf8')
```

O script procura o segredo primeiro no ambiente (`process.env.DIOMIKA_DESKTOP_GATE`) e depois no `.env` da raiz do repositório, exige pelo menos 24 caracteres, e **termina com erro se não encontrar**. Sem isto, seria possível produzir e distribuir um instalador sem portão, que falharia no computador do cliente com um erro de permissões incompreensível. É melhor a construção falhar em casa, com uma mensagem clara, do que o produto falhar no cliente.

O ficheiro gerado, `electron/desktop-gate.cjs`, contém uma única linha (`module.exports = "<valor-secreto>"`) e está no `.gitignore`. É por isso que a Parte VIII.6 insiste que ele nunca aparece no repositório: é gerado no momento da construção, a partir de um segredo que vive noutro sítio, e desaparece com a pasta de trabalho.

---

## VIII.4 Integração contínua com matriz no GitHub Actions

### Porque é necessária uma matriz

Existe uma limitação incontornável na construção de aplicações de secretária: **cada sistema operativo tem de ser construído no próprio sistema operativo**. Não se pode produzir um `.dmg` assinável e válido a partir de Windows, nem um `.exe` a partir de macOS de forma fiável, porque as ferramentas de empacotamento invocam utilitários nativos da plataforma.

Sem automação, isto obrigaria a Diomika a ter fisicamente três máquinas — uma Windows, um Mac e uma Linux — e a repetir manualmente o mesmo procedimento em cada uma, com o risco associado de as três produzirem versões ligeiramente diferentes.

Uma **matriz** de integração contínua resolve isto: descreve-se o conjunto de combinações, e a plataforma dá máquinas virtuais efémeras de cada tipo, em paralelo.

### O workflow

`.github/workflows/backoffice-release.yml`:

```yaml
on:
  workflow_dispatch:
  push:
    tags:
      - "backoffice-v*"
```

Dois gatilhos. `workflow_dispatch` permite premir um botão na interface web do GitHub. O gatilho por **etiqueta** (*tag*) dispara quando alguém marca um ponto do histórico com um nome como `backoffice-v1.0.0`. Isto liga o versionamento à distribuição: cada versão publicada tem uma etiqueta correspondente no histórico de código, e há sempre resposta para "que código exacto está no executável do cliente?".

```yaml
strategy:
  fail-fast: false
  matrix:
    include:
      - os: windows-latest
        dist: dist:win
      - os: macos-latest
        dist: dist:mac
      - os: ubuntu-latest
        dist: dist:linux
runs-on: ${{ matrix.os }}
```

`fail-fast: false` é uma escolha importante. O comportamento por omissão do GitHub Actions é cancelar todos os trabalhos da matriz assim que um falhe. Aqui isso é indesejável: se a construção do macOS falhar por uma razão específica dessa plataforma, ainda se quer o executável de Windows e o AppImage de Linux, que estão bem. Cancelar tudo por causa de um transformaria um problema parcial num bloqueio total.

Os passos são cinco: obter o código; instalar Node.js 20 com cache das dependências (apontando a `backoffice-desktop/package-lock.json`); `npm ci`; construir; carregar os artefactos.

O `npm ci` (*clean install*, instalação limpa) merece uma nota. Difere de `npm install` num aspecto crucial: instala **exactamente** as versões registadas no `package-lock.json`, sem actualizar nada, e falha se o ficheiro de bloqueio estiver inconsistente com o `package.json`. Isto é o que torna a construção **reproduzível**: a mesma etiqueta produz o mesmo resultado hoje e em Janeiro, e não se descobre uma incompatibilidade nova porque uma dependência lançou uma versão menor entretanto.

### O segredo `DIOMIKA_DESKTOP_GATE`

```yaml
- name: Build installer
  run: npm run ${{ matrix.dist }}
  env:
    CSC_IDENTITY_AUTO_DISCOVERY: "false"
    DIOMIKA_DESKTOP_GATE: ${{ secrets.DIOMIKA_DESKTOP_GATE }}
```

`secrets.DIOMIKA_DESKTOP_GATE` é um **segredo de repositório** do GitHub. O modelo é: guarda-se o valor uma vez na configuração do repositório, e a partir daí é encriptado e injectado apenas como variável de ambiente durante a execução. Não é legível na interface web depois de guardado (nem pelo próprio dono), não está no código, e o GitHub faz mascaramento automático nos registos de execução — se o valor aparecer numa linha de saída, é substituído por asteriscos.

O `write-gate.cjs` lê essa variável e escreve o ficheiro do portão. É por isso que o script aceita **duas** fontes: o ambiente (usado pela integração contínua) e o `.env` local (usado por quem constrói no seu computador). Um script, dois contextos, sem ramificação de código.

Esta variável é o exemplo mais claro de um segredo que tem de existir **em quatro lugares simultaneamente e com o mesmo valor**:

1. No segredo do repositório GitHub — para construir os instaladores.
2. No `.env` da máquina virtual — para a API validar o cabeçalho.
3. Na regra de firewall no Cloudflare — para o bloqueio na fronteira.
4. Embutido em cada instalador já distribuído.

A consequência operacional é séria e está registada em `RELATORIO_TECNICO.md` §4.3: **rodar este segredo é um procedimento coordenado**, não uma alteração de configuração. Trocá-lo implica nova construção, actualização da regra de firewall, actualização do `.env` do servidor, actualização do segredo do GitHub, e **redistribuição do instalador a todos os clientes** — porque os instaladores antigos deixam de funcionar no instante em que o servidor passa a esperar o valor novo. A Parte X.3 discute este compromisso em profundidade.

`CSC_IDENTITY_AUTO_DISCOVERY: "false"` desliga a busca automática de certificados de assinatura de código, e leva à secção seguinte.

---

## VIII.5 Gatekeeper (macOS) e SmartScreen (Windows) — binários não assinados

### O que é a assinatura de código

**Assinatura de código** (*code signing*) é o processo de anexar a um executável uma assinatura criptográfica emitida com um certificado de identidade validada. Serve dois propósitos: prova **quem** produziu o ficheiro, e prova que o ficheiro **não foi alterado** desde então.

Os sistemas operativos modernos usam essa assinatura para decidir como tratar um programa novo. Um programa assinado por uma entidade conhecida abre em silêncio. Um programa não assinado é tratado com desconfiança.

A Diomika **não assina** os seus binários. A configuração diz isso explicitamente:

```json
"win": { "signAndEditExecutable": false, ... },
"mac": { "hardenedRuntime": false, "gatekeeperAssess": false, "identity": null, ... }
```

`identity: null` no macOS significa "não tentes assinar". E na integração contínua, `CSC_IDENTITY_AUTO_DISCOVERY: "false"` impede que o `electron-builder` procure certificados na máquina de construção e falhe por não encontrar nenhum. A ausência de assinatura é uma decisão registada, não um esquecimento — consta do checklist de estado em `RELATORIO_TECNICO.md` §11 como *"Assinatura código (Authenticode / notarize): Não (unsigned; SmartScreen/Gatekeeper)"*.

### Porque não

Puramente económico e processual. Um certificado de assinatura de código para Windows (**Authenticode**) custa tipicamente entre uma e várias centenas de euros por ano, e as variantes com validação estendida exigem armazenamento em dispositivo físico de segurança. Para macOS, é necessária uma conta no programa de desenvolvedores da Apple (99 dólares por ano) e um processo de **notarização**: enviar cada binário à Apple, esperar pela análise automática, e anexar o resultado ao ficheiro.

Somando, seriam algumas centenas de euros por ano de custo recorrente, mais complexidade permanente na cadeia de construção. Isto colide de frente com o objectivo de arquitectura declarado do projecto: infra-estrutura recorrente de **zero euros** (ver Parte X.9). Para um sistema com um número muito reduzido de instalações conhecidas, entregues por canal privado a pessoas identificadas, o valor da assinatura é baixo — a confiança é estabelecida pela relação comercial, não pelo certificado.

### O que o cliente vê, concretamente

Isto é a consequência real e tem de ser comunicado com honestidade, porque acontece na primeira abertura e é assustador para quem não está à espera.

**No Windows — SmartScreen.** O Microsoft Defender SmartScreen mostra uma janela azul: *"O Windows protegeu o seu PC"*, com um botão "Não executar" bem visível. O botão que permite prosseguir está escondido atrás de **"Mais informações"**, e só depois aparece **"Executar mesmo assim"**. É preciso dizer isto ao cliente por palavras, porque a janela é desenhada para o dissuadir e o caminho para continuar não é óbvio. Nota adicional: o SmartScreen usa reputação além de assinatura — um ficheiro descarregado poucas vezes é tratado com mais suspeita, e como cada nova versão é um ficheiro novo, o aviso pode reaparecer a cada actualização.

**No macOS — Gatekeeper.** O Gatekeeper é mais severo. Ao abrir a aplicação com duplo clique, o macOS diz que *não pode ser aberta porque é de um desenvolvedor não identificado* — e não oferece nenhum botão para continuar. O caminho existe mas é escondido: **clique com o botão direito** (ou Control+clique) sobre a aplicação, escolher **"Abrir"** no menu de contexto, e depois confirmar "Abrir" na janela que aparece. Só é preciso na primeira vez; depois o sistema memoriza. Nas versões mais recentes do macOS pode ser necessário ir a Definições do Sistema, Privacidade e Segurança, e autorizar explicitamente a aplicação que foi bloqueada.

**No Linux — nada.** O modelo de segurança do Linux não tem equivalente: dá-se permissão de execução ao ficheiro (`chmod +x`) e corre. Nem aviso, nem bloqueio.

### O que mitiga o risco

A assinatura resolveria dois problemas: garantir a autoria e garantir a integridade. Na ausência dela, existem outras garantias:

1. **Canal de entrega privado.** O executável não está publicado numa página de descarregamentos aberta. É entregue directamente ao cliente identificado, conforme descrito na Parte VIII.6.
2. **Origem verificável.** Os artefactos são produzidos pelo GitHub Actions a partir de uma etiqueta do repositório, e ficam retidos 90 dias (`retention-days: 90`). Há registo de que construção produziu que ficheiro.
3. **O portão funciona como autenticação de facto.** Um executável falsificado não teria o valor do portão e seria rejeitado pela API e pela firewall. Isto não protege o cliente de instalar software malicioso (que poderia fazer outras coisas), mas protege o **sistema Diomika** de um binário forjado.
4. **Verificação prévia.** A aplicação testa `/health` e avisa se não conseguir contactar a API, o que dá um sinal precoce de que algo está errado.

É uma limitação honesta, não uma questão resolvida — e está registada como tal na Parte XI.

---

## VIII.6 O que enviar ao cliente e o que **não** enviar

Esta secção é a mais operacionalmente crítica de toda a Parte VIII, porque um erro aqui é uma fuga de credenciais para fora do perímetro.

### A pasta que não existe no repositório

A entrega ao cliente é preparada numa pasta local chamada `cliente-backoffice/`, e essa pasta está no `.gitignore`:

```
backoffice-desktop/release/
backoffice-desktop/electron/desktop-gate.cjs
cliente-backoffice/
```

Três entradas relacionadas, três razões distintas:

- `backoffice-desktop/release/` — a pasta onde o `electron-builder` deixa os binários. Ficheiros de dezenas de megabytes, gerados, que nunca devem ir para controlo de versões (inflam o repositório permanentemente e não são código).
- `electron/desktop-gate.cjs` — **contém o segredo do portão em texto simples**. Se isto entrasse no repositório, o segredo ficaria no histórico do Git para sempre, e removê-lo exigiria reescrever o histórico.
- `cliente-backoffice/` — a área de preparação da entrega, onde se juntam binários e instruções, e onde é fácil colocar um ficheiro de credenciais por descuido.

### O que **vai** para o cliente

Três coisas, e nada mais:

| Item | Conteúdo | Canal |
|---|---|---|
| Instalador do sistema operativo | O `.exe`, `.dmg` ou `.AppImage` correspondente | Transferência de ficheiro |
| `LEIA-ME.txt` | Instruções de abertura, incluindo como passar o SmartScreen ou o Gatekeeper | Junto com o instalador |
| Utilizador e password de administrador | As credenciais de login | **Canal privado, separado** |

A separação de canais no terceiro item é uma prática de segurança elementar chamada **separação de canal**: o ficheiro e a credencial não viajam pelo mesmo meio. Se a caixa de correio electrónico for comprometida, o atacante tem o programa mas não a password, ou vice-versa. Enviar as duas coisas na mesma mensagem anula esta protecção.

### O que **não** vai para o cliente, e porquê

| Item | Porque nunca |
|---|---|
| `CHAVES_MONITORIZACAO.env.txt` e os tokens de Sentry, Axiom e PostHog | São credenciais de **operação**, não do cliente. Dão acesso aos logs e erros de todo o sistema, e permitem consumir a quota dos planos gratuitos. |
| Nome do tópico `ntfy` | É a única credencial do canal de alertas. Quem o tiver pode ler e poluir as notificações operacionais. |
| Valor bruto do portão desktop | **Já vai embutido no instalador.** Fornecê-lo separadamente permitiria fazer pedidos administrativos com uma simples ferramenta de linha de comandos, sem a aplicação — o que desfaria todo o modelo de "admin só pela app". |
| Acesso SSH à máquina virtual e o `.env` do servidor | O `.env` contém a chave de papel de serviço do Supabase, a chave secreta da API, a password de correio electrónico, o segredo do Turnstile. É o conjunto completo de credenciais do sistema. |

O terceiro item é o mais subtil e merece ser sublinhado. Existe uma diferença fundamental entre **o segredo estar dentro de um binário** e **o segredo estar num pedaço de texto**. Ambos podem ser extraídos por alguém com competência técnica e motivação — mas o esforço é radicalmente diferente, e o esforço é uma parte legítima de qualquer modelo de segurança. Entregar o valor em texto é oferecer o acesso administrativo à API a qualquer pessoa com um cliente HTTP. Embutido no binário, é preciso pelo menos inspeccionar o executável.

### Higiene automatizada, não apenas disciplina

Confiar em memória humana para não vazar segredos é uma estratégia que falha. O projecto tem por isso três verificações automáticas:

1. **`.gitignore`** — impede que os ficheiros perigosos sejam sequer propostos para commit.
2. **`gitleaks`** — corre no `pre-commit` (antes de cada commit local) e na integração contínua, procurando padrões que parecem credenciais em todo o repositório e no histórico.
3. **`deploy/verify_bundle_secrets.py`** — analisa a construção da loja à procura de segredos de servidor.

Estas três camadas estão descritas em detalhe nas Partes IX.4 e IX.5.

---

## VIII.7 O fluxo completo de login, passo a passo

Esta é a jornada integral de um clique no botão "Entrar" até uma sessão activa. Envolve seis sistemas distintos. Vale a pena seguir com atenção, porque é aqui que quase todos os conceitos das partes anteriores se cruzam.

### Passo 0 — Arranque da aplicação

O cliente executa o ficheiro. O Electron arranca e, antes de mostrar qualquer coisa, faz duas verificações em `app.whenReady()`:

```javascript
if (!isDev && !DESKTOP_GATE) {
  dialog.showErrorBox('Build incompleto',
    'Falta DIOMIKA_DESKTOP_GATE neste instalador. Peça um build novo à Diomika.')
}
```

Se o portão não existir no binário, aparece uma mensagem que diz **exactamente o que fazer**: pedir uma construção nova. Não é um erro técnico — é uma instrução. Depois corre `apiHealthOk()` (Passo descrito em VIII.2). Só então o servidor local arranca numa porta efémera e a janela carrega `http://127.0.0.1:<porta>/`.

### Passo 1 — A interface pergunta se há login configurado

O componente `LoginView.vue`, ao aparecer (`onMounted`), chama `api.authStatus()`, que faz `GET /admin/auth/status`. Esta chamada acontece **antes** de qualquer credencial, e serve para a interface se adaptar: descobrir se o servidor tem utilizadores criados, qual o tempo de vida da sessão, e se é exigido segundo factor.

A resposta vem de `routes/admin_auth.py`:

```python
return {
    "login_required": has_users(),
    "session_ttl_seconds": SESSION_TTL_SECONDS,
    "admin_local_only": False,
    "desktop_gate_required": True,
    "mfa_required": mfa_required_globally(),
}
```

Se já existir uma sessão guardada, a interface tenta `api.me()` para a validar; se falhar, limpa a sessão e mostra o formulário. Isto evita o caso irritante de a aplicação parecer autenticada com um token expirado e falhar no primeiro clique real.

### Passo 2 — O pedido sai da interface

O utilizador escreve nome e password e submete. A função `submit()` chama `api.login(user, pass)`, que em `src/lib/api.js` se traduz em:

```javascript
login: (username, password, totp_code) =>
  request('POST', '/admin/auth/login', {
    body: totp_code ? { username, password, totp_code } : { username, password },
  }),
```

O caminho é relativo. `baseUrl()` devolve `/api` (forçado, como visto em VIII.2), portanto o destino real é `http://127.0.0.1:<porta>/api/admin/auth/login`. Há um `AbortController` com 30 segundos: um pedido que não responda é cancelado do lado do cliente, em vez de deixar a interface pendurada indefinidamente.

**Ponto essencial:** neste momento o pedido **não tem** o cabeçalho do portão. O código da interface não conhece o segredo, não tem acesso a ele, e não poderia adicioná-lo mesmo que quisesse.

### Passo 3 — O proxy do Electron acrescenta o portão

O servidor local recebe o pedido, vê que o caminho começa por `/api`, e chama `proxyToApi`. Aí acontece a transformação descrita em VIII.2: `/api` é retirado do caminho, o cabeçalho `host` passa a `api.diomika.com`, `origin` e `referer` e `accept-encoding` são removidos, o agente do utilizador passa a `DiomikaBackoffice/1.0`, e é adicionado:

```javascript
if (DESKTOP_GATE) headers['x-diomika-desktop'] = DESKTOP_GATE
```

Este é o momento exacto em que o pedido adquire o privilégio de poder falar com `/admin`. Antes desta linha era um pedido comum; depois dela é um pedido reconhecido como vindo da aplicação oficial.

### Passo 4 — A fronteira Cloudflare: TLS e firewall de aplicação web

O pedido viaja pela internet até ao nó Cloudflare mais próximo. Ali:

- O **TLS** é terminado — a ligação é cifrada de ponta a ponta até este ponto, com um mínimo de TLS 1.2 forçado pela configuração da zona (`min_tls_version: "1.2"` em `waf_rules.json`), modo de segurança `strict`, e HTTPS sempre obrigatório.
- A **firewall de aplicação web** (**WAF**, *Web Application Firewall*) avalia as regras. Duas são relevantes:

```json
{ "name": "block-empty-ua", "expression": "(http.user_agent eq \"\")", "action": "block" },
{ "name": "block-admin-system-except-desktop",
  "expression": "(http.request.uri.path contains \"/admin\" or http.request.uri.path contains \"/system\") and not any(http.request.headers[\"x-diomika-desktop\"][*] eq \"<valor-secreto>\")",
  "action": "block" }
```

A segunda regra é a peça central. Traduzida para português: *se o caminho contém `/admin` ou `/system` e o cabeçalho `x-diomika-desktop` não é exactamente igual ao valor esperado, bloqueia*.

O efeito prático merece ser saboreado: **um pedido de um browser normal para `https://api.diomika.com/admin/auth/login` nunca chega à máquina virtual**. É rejeitado na fronteira, na rede global do Cloudflare, a centenas ou milhares de quilómetros da nossa infra-estrutura. O nosso servidor não gasta um único ciclo de processador a tratá-lo. Um varrimento automatizado à procura de painéis de administração — que é uma constante na internet — bate numa parede que nem sabe que existimos.

Repare-se também que esta regra é **redundante** face ao que a API já faz. Essa redundância é o princípio de **defesa em profundidade**: se um dia alguém alterar a configuração da API por erro, a firewall ainda protege; se a firewall for mal configurada, a API ainda protege.

### Passo 5 — O Tunnel: entrada sem portas abertas

Passada a firewall, o pedido tem de chegar à máquina virtual. Não vai por uma porta aberta na internet, porque não existe nenhuma. Vai por um **Cloudflare Tunnel**.

O modelo é o inverso do habitual e é a ideia mais elegante de toda a arquitectura. Um processo chamado `cloudflared` corre **na máquina virtual** e estabelece uma ligação **de saída** para a rede Cloudflare. Essa ligação fica persistente, e o tráfego que chega ao Cloudflare desce por ela.

Consequência: **a máquina virtual não tem nenhuma porta de escuta exposta à internet**. Não há porta 8000 aberta, não há porta 443, não há porta 80. Um varrimento de portas ao endereço IP da máquina não encontra serviço nenhum. A configuração em `deploy/docker-compose.free.yml` confirma-o:

```yaml
api:
  ports:
    - "127.0.0.1:8000:8000"
```

O prefixo `127.0.0.1:` antes da porta é decisivo. Sem ele, o Docker abriria a porta 8000 em **todas** as interfaces de rede, incluindo a pública — um erro de configuração extremamente comum e que expõe serviços internos ao mundo. Com ele, só processos na própria máquina alcançam a API. O mesmo padrão é usado no Redis (`127.0.0.1:6379:6379`).

O serviço `cloudflared` corre com `network_mode: host`, o que lhe permite alcançar `127.0.0.1:8000` como se fosse um processo local — e o comentário no ficheiro explica que essa é a razão da escolha. A Parte X.2 desenvolve o raciocínio completo.

### Passo 6 — Os middlewares da API, em ordem

O pedido chega finalmente ao FastAPI. Atravessa as camadas de fora para dentro:

**`PrivilegedPathMiddleware`** (`core/path_guard.py`) — o guarda mais exterior. Primeiro verifica o bloqueio global:

```python
def lockdown_active() -> bool:
    return (os.getenv("SECURITY_LOCKDOWN") or "").strip().lower() in ("1", "true", "yes")
```

Se `SECURITY_LOCKDOWN` estiver activo, todos os caminhos privilegiados e os formulários públicos (`/contacto`, `/orcamentos`) respondem 503, e apenas `/health` e `/health/ready` continuam a funcionar. É o interruptor de emergência: um incidente em curso pode ser contido com uma variável de ambiente, mantendo o sistema observável.

Depois, em produção não-beta, se o caminho começar por `/admin`, `/system` ou `/health/detail`, chama `privileged_access_ok(request)` e responde 403 se falhar.

**`RequestIdMiddleware`** — atribui o identificador único que vai correlacionar tudo.

**`SecurityHeadersMiddleware`** — acrescenta os cabeçalhos de segurança na resposta, incluindo, em produção, HSTS (`Strict-Transport-Security: max-age=31536000; includeSubDomains; preload`, que instrui o browser a nunca mais tentar HTTP neste domínio) e uma política de segurança de conteúdo restritiva (`default-src 'none'; frame-ancestors 'none'`), apropriada para uma API que não serve páginas.

**`LatencyAlertMiddleware`** — arranca o cronómetro.

**`BodySizeLimitMiddleware`** — e aqui há uma história que vale por si. O código actual verifica **apenas** o cabeçalho `Content-Length`:

```python
class BodySizeLimitMiddleware(BaseHTTPMiddleware):
    """Rejeita bodies demasiado grandes (DoS) via Content-Length.

    Não consumir request.stream() aqui: BaseHTTPMiddleware + re-inject
    do body parte o parsing JSON (login/admin POST → 422 body missing).
    """
```

A versão anterior tentava ler o corpo do pedido para o medir. O problema é que o corpo de um pedido HTTP é um **fluxo que só pode ser lido uma vez**. O middleware lia-o, media-o, e quando o FastAPI chegava para o interpretar, já não havia nada — resultado: o login devolvia 422 com "campo obrigatório em falta", um erro que aponta para o formulário estando o defeito no middleware. Foram horas de depuração a olhar para o lugar errado. A correcção foi eliminar a leitura e confiar no cabeçalho declarado. É menos exaustivo (um cliente malicioso pode mentir no `Content-Length`), mas o servidor web subjacente também impõe limites, e a simplicidade correcta vale mais do que a exaustividade quebrada.

**`GlobalRateLimitMiddleware`** — o limitador por camadas, com Redis em produção e memória como alternativa, isentando o loopback. Os limites configurados em `deploy/env.free.example` são `RATE_LIMIT_CATALOG_PER_MIN=600`, `RATE_LIMIT_GLOBAL_PER_MIN=120` e `RATE_LIMIT_ADMIN_PER_MIN=30`.

### Passo 7 — A dependência do router: `admin_must_be_local`

O router de autenticação declara a verificação a nível de router, aplicando-a a todas as suas rotas:

```python
router = APIRouter(
    prefix="/admin/auth",
    tags=["Admin Auth"],
    dependencies=[Depends(admin_must_be_local)],
)
```

Em `core/local_only.py`:

```python
def privileged_access_ok(request: Request) -> bool:
    settings = get_settings()
    if not settings.is_production or settings.is_beta:
        return True
    if peer_is_loopback(request):
        return True
    return desktop_gate_ok(request)
```

Dois detalhes de segurança importantes.

**`peer_is_loopback` ignora deliberadamente o `X-Forwarded-For`.** O comentário é explícito: *"IP do peer TCP — não usar X-Forwarded-For (fácil de forjar)"*. O `X-Forwarded-For` é um cabeçalho HTTP que os intermediários acrescentam para indicar o cliente original — e, sendo um cabeçalho, qualquer pessoa pode escrever nele o que quiser. Um atacante que enviasse `X-Forwarded-For: 127.0.0.1` obteria acesso administrativo se o código confiasse nele. O código usa `request.client.host`, o endereço real da ligação TCP, que não é forjável pelo cliente.

**A comparação do portão usa tempo constante.**

```python
def desktop_gate_ok(request: Request) -> bool:
    expected = desktop_gate_secret()
    if not expected:
        return False
    got = (request.headers.get(_DESKTOP_HEADER) or "").strip()
    if not got:
        return False
    return hmac.compare_digest(got, expected)
```

`hmac.compare_digest` compara duas cadeias em tempo constante, ou seja, o tempo que demora não depende de quantos caracteres coincidem. O operador normal `==` pára no primeiro caractere diferente, e essa diferença de tempo — microssegundos — é mensurável na rede com estatística suficiente. Um atacante poderia descobrir o segredo caractere a caractere, medindo qual tentativa demora infinitesimalmente mais: um **ataque de temporização**. Reparar que `expected` vazio devolve `False`: sem portão configurado, ninguém entra por esta via, e não há o comportamento perigoso de "sem configuração, permite tudo".

### Passo 8 — Limitação de taxa dupla no login

```python
rate_limit(request, "admin_login", max_calls=20, window_seconds=300)
user_key = (body.username or "").strip().lower()[:64] or "unknown"
rate_limit_absolute(f"admin_login_user:{user_key}", max_calls=10, window_seconds=300)
```

Dois limites de eixos diferentes, e a razão está no comentário: *"limitar por IP + por username (anti brute-force multi-IP)"*.

O primeiro limite é por endereço IP: 20 tentativas em 5 minutos. Trava o atacante simples de uma única origem. Mas um atacante com uma rede de máquinas distribuídas contorna-o trivialmente, fazendo poucas tentativas de muitos endereços.

O segundo limite é por **nome de utilizador**, independentemente da origem: 10 tentativas em 5 minutos para a conta `admin`, vindas de onde vierem. É o limite que efectivamente protege a conta contra ataque distribuído. Note-se o corte a 64 caracteres e a normalização para minúsculas — para que não se possa multiplicar o orçamento de tentativas escrevendo `Admin`, `ADMIN` e `admin` como se fossem contas distintas, nem esgotar memória com nomes gigantes.

### Passo 9 — Verificação da password com scrypt

`authenticate()` em `core/admin_users.py` executa uma sequência ordenada:

1. Carrega o ficheiro de utilizadores, `backend-api/data/admin_users.json` (que está no `.gitignore`).
2. Procura o utilizador, comparando em minúsculas.
3. Se a conta estiver `disabled`, recusa.
4. Se houver `locked_until` no futuro, recusa com o tempo restante.
5. Verifica a password.

A verificação é `verify_password`:

```python
algo, salt_b64, hash_b64 = encoded.split("$", 2)
if algo != "scrypt":
    return False
salt = base64.b64decode(salt_b64)
expected = base64.b64decode(hash_b64)
dk = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=2**14, r=8, p=1, dklen=32)
return hmac.compare_digest(dk, expected)
```

O formato armazenado é `scrypt$<sal>$<derivada>`, com o nome do algoritmo lá dentro — o que permitirá no futuro migrar para outro algoritmo sem ambiguidade sobre como interpretar registos antigos.

**scrypt** é uma função de derivação de chave desenhada para ser **lenta e cara em memória** de propósito. Os parâmetros: `n=2**14` (16384 iterações), `r=8` (tamanho do bloco), `p=1` (sem paralelismo), `dklen=32` (32 bytes de saída). O `sal` (*salt*) são 16 bytes aleatórios por utilizador, gerados com `secrets.token_bytes(16)`. A Parte X.4 explica em detalhe porque isto é essencial e o que aconteceria com uma função de dispersão rápida.

Se a password estiver errada, incrementa-se o contador de falhas; ao atingir `MAX_FAILED` (5, configurável), a conta é bloqueada por `LOCKOUT_MINUTES` (15) e o contador é reposto.

### Passo 10 — Resposta genérica, registo detalhado

Se a autenticação falhar por qualquer razão, o cliente recebe **sempre** a mesma coisa:

```python
raise HTTPException(status_code=401, detail="Credenciais inválidas")
```

O comentário no código explica: *"Resposta genérica ao cliente — sem enumeração (lockout/disabled/tentativas)."*

Isto chama-se prevenção de **enumeração de utilizadores**. Se a API respondesse "utilizador não existe" para nomes inválidos e "password errada" para nomes válidos, um atacante poderia descobrir quais as contas existentes antes de tentar passwords — reduzindo drasticamente o espaço de busca. Se respondesse "conta bloqueada", confirmaria que aquela conta existe e está a ser atacada com sucesso suficiente para disparar o bloqueio. Uma única mensagem para todos os casos não revela nada.

Isto está protegido por um teste automático em `test_observability_flags.py`, cujo nome e docstring são explícitos: `test_login_error_is_generic` — *"Cliente nunca vê lockout/disabled/tentativas — só Credenciais inválidas."* Um teste que verifica que uma mensagem **não** melhora é exactamente o tipo de teste que evita que alguém, com boa intenção, torne o erro "mais útil" e reabra a vulnerabilidade.

Do lado interno, ao contrário, registra-se tudo: `log_admin_action` com a razão real, `send_alert` com nome, endereço IP e motivo, e `note_login_failure` para a detecção de anomalia.

### Passo 11 — Emissão do token de sessão

Autenticação bem-sucedida, `issue_session()` em `core/session_tokens.py`:

```python
payload = {"u": username, "r": role, "iat": now, "exp": now + SESSION_TTL_SECONDS, "jti": jti}
body = _b64url(json.dumps(payload, separators=(",", ":")).encode())
sig = _b64url(hmac.new(_secret(), body.encode(), hashlib.sha256).digest())
return f"{_PREFIX}{body}.{sig}", SESSION_TTL_SECONDS
```

O resultado é uma cadeia com o prefixo `dms1.`, seguida do conteúdo codificado em base64 seguro para endereços, seguida de uma assinatura. Os campos: utilizador, papel, instante de emissão, instante de expiração, e `jti` (*JWT ID*, identificador único do token) de 8 bytes aleatórios.

A assinatura é **HMAC-SHA256** (*Hash-based Message Authentication Code*) com uma chave derivada de `API_SECRET_KEY`:

```python
raw = (os.getenv("API_SECRET_KEY") or "").strip()
if not raw or len(raw) < 32:
    raise RuntimeError("API_SECRET_KEY (>=32 chars) obrigatório para sessões admin")
return hashlib.sha256(raw.encode("utf-8")).digest()
```

Sem chave, ou com chave curta, o sistema **recusa-se a emitir sessões**. Falha ruidosamente em vez de operar de forma insegura.

Três propriedades da sessão:

**Tempo de vida curto.** `SESSION_TTL_SECONDS` são 15 minutos por omissão (`ADMIN_SESSION_TTL_MINUTES`), com inactividade de 10 minutos (`ADMIN_SESSION_IDLE_MINUTES`). Dois relógios: um absoluto, que expira independentemente da actividade, e um de inactividade, que expira se ninguém tocar na aplicação.

**Uma sessão activa por utilizador.** Ao emitir uma nova, a anterior do mesmo utilizador é revogada. Se alguém entrar noutro computador, a primeira sessão morre — o que dá visibilidade imediata a um acesso não autorizado.

**Revogável.** Existe `_revoked` em memória e, com Redis, chaves `diomika:sess:revoked:<jti>`. A capacidade de revogar é a diferença central face a um token JWT clássico, e a Parte X.5 explora-a.

### Passo 12 — A interface guarda o token

A resposta viaja de volta pelo caminho inverso — API, Tunnel, Cloudflare, proxy Electron (que remove os cabeçalhos de política de origem) — e chega à interface, que executa:

```javascript
saveSettings({ accessToken: res.access_token })
writeSessionUser({ username: res.username, role: res.role })
await router.replace({ name: 'workspace', params: { table: 'categories' } })
```

O token vai para `sessionStorage`, não para `localStorage`. A distinção importa: `localStorage` persiste indefinidamente entre sessões; `sessionStorage` é apagado quando a janela fecha. Como o token vive 15 minutos, guardá-lo de forma persistente só criaria um valor obsoleto no disco. Fechar a aplicação limpa a sessão.

A partir daqui, cada pedido inclui automaticamente:

```javascript
if (s.accessToken) {
  h.Authorization = `Bearer ${s.accessToken}`
}
```

E do lado da API, `require_api_key` em `core/auth.py` reconhece o prefixo `dms1.` como token de sessão, valida a assinatura, verifica revogação e inactividade, e anexa o papel e o actor ao estado do pedido — que é o que permite o controlo de acessos por papel e por tabela descrito no mesmo ficheiro.

### O caminho do segundo factor

Se `ADMIN_MFA_REQUIRED` estiver ligado (hoje está a `0`), há dois desvios. Se o utilizador já tem segredo TOTP configurado, o login devolve `{"mfa_required": True}` e a interface mostra o campo de código. Se ainda não tem, devolve `{"mfa_setup_required": True}` e a interface chama `POST /admin/auth/mfa/setup`, obtendo um segredo e um endereço `otpauth://` para configurar numa aplicação autenticadora, seguido de `mfa/confirm` para validar o primeiro código. **TOTP** significa *Time-based One-Time Password* — password de uso único baseada no tempo: a aplicação no telefone e o servidor partilham um segredo e calculam ambos um código a partir da hora actual, mudando a cada 30 segundos. A verificação usa `valid_window=1`, tolerando um intervalo adjacente para compensar relógios ligeiramente desalinhados.

---

# Parte IX — Deploy e operações

## IX.1 `deploy_vm.py` — publicar a API na máquina virtual

### O contexto

A API corre numa máquina virtual `e2-micro` na Google Cloud Platform, dentro da categoria **Always Free** (permanentemente gratuita). É uma máquina modesta. `deploy/deploy_vm.py` é o programa que leva o código do computador de desenvolvimento até lá e o põe a correr.

O programa exige duas variáveis no `.env` local: `REMOTE_VM_SSH` (no formato `utilizador@endereço-ip`) e `CLOUDFLARE_TUNNEL_TOKEN`. Se faltar alguma, para com uma mensagem que inclui a sugestão de onde procurar. **SSH** significa *Secure Shell* — o protocolo padrão para obter uma linha de comandos cifrada numa máquina remota. **SCP** (*Secure Copy Protocol*) é o seu companheiro para copiar ficheiros.

Antes de agir, o programa garante que cinco linhas existem no `.env` que vai enviar, acrescentando-as se faltarem:

```python
required = [
    "DIOMIKA_ENV=production",
    "TRUST_PROXY=1",
    "SUPABASE_STORAGE_PRIVATE=1",
    "API_BASE_URL=https://api.diomika.com",
    "ALLOWED_HOSTS=api.diomika.com",
]
```

Isto elimina uma classe inteira de incidentes: a máquina de produção a correr com configuração de desenvolvimento porque alguém se esqueceu de uma linha.

### Os seis passos

**1) Preparação da máquina.** Por SSH, um comando com `set -euo pipefail` (que faz o script abortar ao primeiro erro, tratar variáveis não definidas como erro, e propagar falhas em cadeias de comandos) que: cria um ficheiro de **swap** de 2 gigabytes se não existir, e o registra em `/etc/fstab` para sobreviver a reinícios; instala o Docker se não estiver presente; cria a pasta de trabalho.

O swap merece explicação. É espaço em disco usado como extensão da memória: quando a memória física esgota, páginas menos usadas são movidas para disco. Numa `e2-micro`, com memória muito limitada, construir uma imagem Docker pode esgotar a memória e o núcleo do sistema mata o processo — uma falha confusa que aparece como "morreu sem explicação". Dois gigabytes de swap tornam a construção lenta em vez de impossível. É uma troca deliberada de velocidade por viabilidade.

**2) Envio do código.** Aqui está uma decisão de segurança interessante, anunciada no próprio texto impresso: *"Enviar codigo local (repo privado — sem git clone)"*.

A alternativa óbvia seria a máquina fazer `git clone` do repositório. Isso exigiria que a máquina tivesse **credenciais de acesso ao repositório privado** — uma chave de implantação ou um token. Se a máquina fosse comprometida, o atacante teria acesso ao histórico completo do código.

Em vez disso, cria-se um arquivo `tar` localmente, exclui-se o que não deve viajar, envia-se por SCP para `/tmp`, extrai-se, e apaga-se. A máquina **nunca tem credenciais do Git**. As exclusões:

```python
excludes = [
    "--exclude=.git", "--exclude=node_modules",
    "--exclude=frontend-web/node_modules", "--exclude=backoffice-desktop/node_modules",
    "--exclude=backoffice-desktop/release", "--exclude=__pycache__",
    "--exclude=.venv", "--exclude=*.pyc", "--exclude=.env",
]
```

`--exclude=.git` remove o histórico. `--exclude=.env` é crucial: o ficheiro de ambiente é enviado separadamente no passo 3, depois de ser processado. Enviá-lo aqui seria enviar a versão local, possivelmente de desenvolvimento.

O ficheiro temporário local é apagado num bloco `finally`, garantindo limpeza mesmo em caso de erro.

**3) Envio do `.env` de produção.** O texto processado (com as linhas obrigatórias garantidas) é escrito num ficheiro temporário, copiado para `~/diomika/.env`, e o temporário é apagado imediatamente.

**4) Actualização da origem do Tunnel.** Via interface de programação do Cloudflare, lista os túneis da conta, encontra o chamado `diomika-api`, e substitui a sua configuração de encaminhamento:

```python
"ingress": [
    {"hostname": "api.diomika.com", "service": origin, "originRequest": {}},
    {"service": "http_status:404"},
]
```

A primeira regra encaminha `api.diomika.com` para `http://127.0.0.1:8000`. A segunda é um apanha-tudo que devolve 404 — importante, porque sem ela um pedido a um nome não configurado teria comportamento indefinido. Se as credenciais do Cloudflare não estiverem presentes, o programa avisa em vez de falhar: *"Sem CLOUDFLARE_API_TOKEN/ACCOUNT_ID — actualiza o origin no Zero Trust manualmente"*. Automação opcional, com caminho manual documentado.

**5) Arranque dos contentores.**

```bash
sudo docker compose --env-file .env -f deploy/docker-compose.free.yml --profile tunnel up -d --build
sleep 8; curl -sf http://127.0.0.1:8000/health
```

O `--profile tunnel` activa o serviço `cloudflared`, que está marcado com `profiles: ["tunnel"]` e portanto não arranca por omissão. Isto permite usar o mesmo ficheiro de composição para uma máquina sem túnel. A verificação local com `curl -sf` (silencioso, e falha em código de erro HTTP) confirma que a API responde **de dentro** da máquina.

**6) Verificação pública.** Um pedido a `https://api.diomika.com/health` com agente do utilizador explícito (para não bater na regra da firewall contra agentes vazios). Se falhar, a mensagem não é alarmista: *"Tunnel pode estar a propagar — retesta"*, com código de saída 2 (distinto do 1 de falha real). A propagação de configuração de rede leva segundos, e reportar isso como avaria produziria falsos alarmes.

### O ficheiro de composição

`deploy/docker-compose.free.yml` define três serviços.

**redis** — imagem `redis:7-alpine`, com `--save "" --appendonly no`, ou seja, **sem persistência em disco**. É deliberado: o Redis aqui serve limitação de taxa, idempotência e estado de sessões, tudo dados efémeros que podem ser reconstruídos. Sem persistência, não há escrita em disco (importante numa máquina pequena) e não há ficheiro de dados a gerir. Ligado apenas a `127.0.0.1:6379`. Tem verificação de saúde com `redis-cli ping`.

**api** — construída a partir do `Dockerfile` na raiz, ligada a `127.0.0.1:8000`, lê o `.env` e sobrepõe as variáveis críticas de produção. Depende do Redis estar **saudável** (`condition: service_healthy`), não apenas arrancado — uma distinção que evita a corrida clássica em que a aplicação tenta ligar-se antes de a base de dados estar pronta. A sua própria verificação de saúde tem `start_period: 40s`, dando à aplicação tempo para arrancar antes de começar a ser avaliada.

**cloudflared** — imagem fixada em `cloudflare/cloudflared:2024.12.2`, com `profiles: ["tunnel"]` e `network_mode: host`. Depende de a API estar saudável, o que evita o túnel encaminhar tráfego para um serviço que ainda não responde. A fixação de versão exacta (em vez de `latest`) é deliberada: um deploy amanhã usa o mesmo software de hoje, e uma actualização é uma decisão consciente.

---

## IX.2 `deploy_beta.py` — construir e publicar a loja

### O que faz

`deploy/deploy_beta.py` trata da loja: constrói os ficheiros estáticos e publica-os no **Cloudflare Pages**, um serviço de alojamento de sítios estáticos com rede de distribuição de conteúdo (**CDN**, *Content Delivery Network*) incluída e gratuito.

O comando de produção documentado no `README.md` é:

```powershell
python deploy/deploy_beta.py --pages-deploy --api-url https://api.diomika.com
```

### A construção

A loja é uma **aplicação de página única** (**SPA**, *Single-Page Application*): um ficheiro HTML e pacotes de JavaScript que desenham tudo no browser. A ferramenta `vite` transforma o código-fonte numa pasta `dist/` de ficheiros optimizados.

A função `build_frontend` injecta o endereço da API na construção:

```python
build_env = {**env, "VITE_API_BASE_URL": api_url.rstrip("/")}
```

Como o prefixo `VITE_` indica, este valor é **embutido nos ficheiros JavaScript**. A loja não descobre o endereço da API em tempo de execução — ele é uma constante compilada. Trocá-lo exige reconstruir.

Antes de construir, valida as variáveis obrigatórias: `VITE_SUPABASE_URL` e `VITE_SUPABASE_ANON_KEY` são sempre exigidas; fora do modo beta, `VITE_TURNSTILE_SITE_KEY` também. Falhar na validação é muito melhor do que produzir uma construção silenciosamente inútil.

### O modo beta

Quando `beta=True`, acontecem quatro coisas para garantir que uma versão de pré-produção **não é indexada** pelos motores de busca:

1. `VITE_BETA_MODE=1` é definido.
2. `public/robots-beta.txt` é copiado sobre `dist/robots.txt`.
3. Uma etiqueta `<meta name="robots" content="noindex, nofollow">` é injectada no `index.html`, se ainda não existir.
4. Os cabeçalhos apropriados são escolhidos: `_headers` para beta, `_headers.production` para produção.

A redundância entre `robots.txt` e a etiqueta `meta` é intencional: são mecanismos diferentes, respeitados por rastreadores diferentes, e o custo da duplicação é nulo. Uma loja de testes indexada no Google é um problema de reputação difícil de desfazer.

### A verificação obrigatória de segredos

O último passo da construção não é opcional:

```python
verify = subprocess.run([sys.executable, str(ROOT / "deploy" / "verify_bundle_secrets.py")], cwd=ROOT)
if verify.returncode != 0:
    return False
```

Se o analisador encontrar um segredo de servidor no resultado da construção, `build_frontend` devolve falso e **a publicação não acontece**. Não é um aviso que se possa ignorar por distracção — é um bloqueio.

### A publicação

```python
cmd = ["npx", "--yes", "wrangler@3", "pages", "deploy", dist_arg,
       f"--project-name={project}", f"--branch={branch}", "--commit-dirty=true"]
```

O `wrangler` é a ferramenta oficial de linha de comandos do Cloudflare, com versão fixada em 3 para evitar surpresas. O nome do projecto por omissão é `diomika-loja`, o ramo por omissão é `production`.

Há um comentário que documenta um pormenor não óbvio: *"Deploy from frontend-web so sibling `functions/` (path probes 404) is included."* A publicação é executada com o directório de trabalho em `frontend-web/`, porque o Cloudflare Pages procura uma pasta `functions/` **irmã** da pasta publicada. É lá que vive `frontend-web/functions/_middleware.js`, que bloqueia sondagens automáticas a caminhos como `.env`, `.git` e `/src`. Publicar do lugar errado silenciosamente deixaria essa protecção de fora.

No fim, o endereço é extraído da saída por expressão regular e o estado é gravado em `deploy/beta.state.json` — que está no `.gitignore`, por conter endereços operacionais.

---

## IX.3 Variáveis de ambiente — o conceito

### O problema

Um programa precisa de valores que mudam conforme onde corre: o endereço da base de dados, as credenciais, se está em produção. Estes valores têm duas propriedades incómodas: **mudam por ambiente** e **alguns são secretos**.

Escrevê-los no código tem duas consequências, ambas graves. Primeira: o mesmo código não serve para dois ambientes, e passa a haver ficheiros diferentes a manter em paralelo, que divergem. Segunda: os segredos entram no controlo de versões, e o Git **guarda o histórico para sempre** — apagar a linha num commit posterior não remove o segredo, que continua acessível no histórico. A única remediação verdadeira é rodar a credencial e reescrever o histórico.

### A solução

**Variáveis de ambiente** são pares nome-valor que o sistema operativo fornece ao processo quando ele arranca. O código lê-as por nome:

```python
token = (os.getenv("AXIOM_TOKEN") or "").strip()
```

O código sabe **que** valor precisa; não sabe **qual** é. O valor vem de fora, e varia por máquina sem que uma linha de código mude. Este princípio é o segundo dos "doze factores", um conjunto de práticas amplamente adoptado para aplicações modernas.

### `.env` e `.env.example`

Definir variáveis à mão em cada arranque é impraticável. A convenção é um ficheiro chamado `.env`, com uma linha por variável:

```
DIOMIKA_ENV=production
AXIOM_DATASET=diomika
```

**Este ficheiro nunca entra no Git.** Está no topo do `.gitignore`, com um comentário que não deixa dúvidas:

```
# Secrets — nunca versionar .env (fica só na VM / PC local)
.env
.env.local
.env.*.local
!.env.example
```

A última linha é a chave da solução. `!` é uma negação: "ignora tudo o que corresponde aos padrões acima, **excepto** `.env.example`".

O `.env.example` é o **modelo**: tem exactamente os mesmos nomes de variáveis, com valores que são marcadores inofensivos:

```
SUPABASE_URL=https://YOUR_PROJECT.supabase.co
SUPABASE_KEY=your-service-role-key
API_SECRET_KEY=generate-a-long-random-string
```

Isto resolve um problema real de colaboração: quem chega ao projecto precisa de saber **que** variáveis existem, e essa informação não é secreta — apenas os valores são. O modelo é versionado (é documentação executável), os valores não. Copia-se `.env.example` para `.env`, preenche-se, e o `.gitignore` protege o resultado.

A Diomika tem dois modelos, para dois públicos:

- **`.env.example`** — orientado a desenvolvimento, com a secção de produção comentada.
- **`deploy/env.free.example`** — orientado a produção, com valores reais de configuração (`UVICORN_WORKERS=4`, `RATE_LIMIT_CATALOG_PER_MIN=600`) e apenas os segredos como marcadores. Inclui comentários operacionais valiosos, como a forma de gerar o portão: `python -c "import secrets; print(secrets.token_urlsafe(32))"`.

Vale notar duas linhas deste segundo ficheiro que funcionam como memória institucional:

```
# ADMIN_ALLOW_REMOTE — removido; use DIOMIKA_DESKTOP_GATE + app oficial
```

Documentar o que foi **removido** e o que o substituiu evita que alguém, ao encontrar uma referência antiga, tente reintroduzir um mecanismo mais fraco.

### O prefixo `VITE_`

Existe uma fronteira que atravessa toda a lista de variáveis e que é a mais importante de compreender: **variáveis de servidor contra variáveis de cliente**.

O Vite só inclui na construção as variáveis cujo nome começa por `VITE_`. Isto não é um detalhe de ergonomia: é um mecanismo de segurança. Sem ele, seria fácil incluir por acidente uma chave de servidor no JavaScript entregue a todos os visitantes.

| Onde vive | Exemplos | Visível a quem? |
|---|---|---|
| Servidor | `SUPABASE_KEY`, `API_SECRET_KEY`, `MAIL_PASSWORD`, `TURNSTILE_SECRET_KEY`, `AXIOM_TOKEN`, `SENTRY_DSN`, `DIOMIKA_DESKTOP_GATE` | Só ao processo na máquina virtual |
| Cliente (`VITE_`) | `VITE_SUPABASE_ANON_KEY`, `VITE_API_BASE_URL`, `VITE_TURNSTILE_SITE_KEY`, `VITE_POSTHOG_KEY` | A qualquer visitante que abra as ferramentas do browser |

A distinção entre `SUPABASE_KEY` e `VITE_SUPABASE_ANON_KEY` é o exemplo mais consequente. A primeira é a chave de **papel de serviço**, que ignora todas as regras de segurança a nível de linha (**RLS**, *Row Level Security*) e pode ler e escrever tudo na base de dados. A segunda é a chave **anónima**, que está sujeita a essas regras. Confundi-las — colocar a chave de serviço numa variável `VITE_` — exporia a base de dados inteira a qualquer visitante da loja. É precisamente por isso que `verify_bundle_secrets.py` tem uma verificação dedicada a essa confusão específica:

```python
if anon and service and anon == service:
    failures.append("VITE_SUPABASE_ANON_KEY = SUPABASE_KEY (service role exposto como anon!)")
```

---

## IX.4 Integração contínua: pytest, Playwright, gitleaks, pip-audit, verify_bundle_secrets

### O conceito

**Integração contínua** (**CI**, *Continuous Integration*) é a prática de correr automaticamente um conjunto de verificações a cada alteração de código. A alternativa é confiar que cada pessoa se lembra de correr tudo à mão, o que falha exactamente nos dias em que há pressa.

O ficheiro é `.github/workflows/ci.yml`, disparado por envios e pedidos de integração nos ramos `master` e `main`. Tem dois trabalhos, e o segundo depende do primeiro (`needs: security-gate`).

### Trabalho 1: `security-gate`

Corre antes de tudo o resto. A escolha de ordem é intencional: se houver um segredo exposto ou uma dependência vulnerável, não vale a pena gastar minutos de computação a correr testes.

**`pip-audit`** compara as versões em `requirements.txt` com bases de dados públicas de vulnerabilidades conhecidas e falha se encontrar alguma. A maioria das falhas de segurança em produção não vem de código próprio mal escrito — vem de uma biblioteca desactualizada com uma vulnerabilidade publicada e um exploit disponível.

**`deploy/security_gate.py`** corre com variáveis de ambiente que são visivelmente marcadores:

```yaml
API_SECRET_KEY: test-key-with-enough-length-32ch
SUPABASE_URL: https://example.supabase.co
SUPABASE_KEY: test-service-key
```

Note-se `test-key-with-enough-length-32ch`: tem exactamente o comprimento mínimo exigido por `_secret()` em `session_tokens.py`. É um valor escolhido para satisfazer a validação sem ser um segredo. Isto permite que a integração contínua corra em qualquer clone do repositório, sem acesso a credenciais reais.

**`gitleaks`** analisa o repositório à procura de padrões que parecem credenciais — chaves privadas, tokens de fornecedores conhecidos, cadeias de alta entropia. Usa `.gitleaks.toml` para configuração, o que permite marcar falsos positivos (os marcadores nos ficheiros de exemplo, por exemplo).

### Trabalho 2: `test`

**`pytest`** corre `python -m pytest backend-api/tests -q`. O ficheiro `pytest.ini` na raiz configura o essencial:

```ini
[pytest]
pythonpath = backend-api
testpaths = backend-api/tests
```

`pythonpath = backend-api` é o que permite que os testes escrevam `from core.admin_users import ...` em vez de caminhos relativos frágeis.

O conjunto de testes cobre as áreas onde um erro é caro: guarda de caminhos (`test_path_guard_hardening.py`), acesso apenas local (`test_local_only.py`), sessões (`test_admin_session.py`), referências directas a objectos inseguras (`test_idor.py`), endurecimento geral (`test_hardening.py`), apagamento por privacidade (`test_privacy_erase.py`), e observabilidade (`test_observability_flags.py`). São, na sua maioria, **testes de segurança** — verificam que coisas continuam bloqueadas.

**Verificação de RLS**, condicional:

```bash
if [ -n "$SUPABASE_URL" ] && [ -n "$VITE_SUPABASE_ANON_KEY" ]; then
  python deploy/verify_rls.py
else
  echo "Skip RLS verify — secrets em falta"
fi
```

Corre só se os segredos existirem. Um clone sem credenciais salta o passo com uma mensagem clara, em vez de ficar permanentemente vermelho.

**Construção do frontend**, com quatro passos e uma verificação sagaz no fim:

```bash
npm ci --ignore-scripts
npm audit --audit-level=high
npm run build
test ! -f dist/assets/*.map
```

`--ignore-scripts` impede a execução de scripts de instalação das dependências — um vector de ataque real na cadeia de fornecimento, em que um pacote comprometido executa código arbitrário no momento da instalação. `npm audit --audit-level=high` é o equivalente do `pip-audit` para JavaScript. E `test ! -f dist/assets/*.map` verifica que **não** existem ficheiros de mapa de origem (*source maps*) na construção: esses ficheiros permitem reconstruir o código-fonte original a partir do JavaScript minificado, e publicá-los entrega a estrutura interna da aplicação a qualquer pessoa.

**`verify_bundle_secrets.py`** — descrito abaixo.

**Código morto (suave)** — `vulture` via `deploy/check_dead_code.py`, marcado como suave: reporta mas não bloqueia. Detecção de código não utilizado tem falsos positivos suficientes para não justificar travar uma integração.

**Playwright contra produção real:**

```yaml
env:
  E2E_SITE_URL: https://www.diomika.com
  E2E_API_URL: https://api.diomika.com
```

O Playwright é uma ferramenta de automação de browsers. Os testes em `frontend-web/e2e/critical.spec.js` correm **contra o sistema em produção**, não contra uma cópia local. São quatro:

1. `/health` e `/health/ready` respondem.
2. A página inicial da loja carrega e os elementos `body` e `#app` estão visíveis.
3. A página de privacidade tem um cabeçalho de nível 1 visível — o que é simultaneamente um teste de conformidade (a página tem de existir) e de acessibilidade.
4. **`admin público bloqueado`** — o mais interessante:

```javascript
const r = await request.get(`${api}/admin/auth/status`, {
  headers: { 'User-Agent': 'Mozilla/5.0 DiomikaE2E' },
})
expect([401, 403, 404, 405]).toContain(r.status())
```

Este teste verifica activamente, a cada integração, que um pedido sem o cabeçalho do portão **não** consegue chegar ao endereço administrativo. Aceita quatro códigos, porque o bloqueio pode ocorrer em camadas diferentes (firewall, guarda de caminho, dependência da rota) e cada uma responde de forma ligeiramente diferente — o que importa é que **não** seja 200. Um teste automático que confirma continuamente que a porta está fechada é a melhor defesa contra uma regressão silenciosa de configuração.

### `verify_bundle_secrets.py` em detalhe

Analisa `frontend-web/dist/` a três níveis.

**Padrões proibidos** — expressões regulares para `service_role`, `SUPABASE_KEY`, `API_SECRET_KEY`, `MAIL_PASSWORD`, `TURNSTILE_SECRET`, `SUPABASE_DB_PASSWORD` e senhas de IMAP. Detecta o **nome** da variável, o que apanha o erro de alguém referenciar acidentalmente uma variável de servidor no código do cliente.

**Valores literais** — lê o `.env` local e procura os valores reais dos segredos no conteúdo da construção:

```python
for name, value in server_secrets:
    if value and len(value) >= 8 and value in combined:
        failures.append(f"Valor literal de {name} encontrado no bundle")
```

Esta é a verificação mais poderosa, porque apanha o caso em que o segredo foi embutido sem o seu nome aparecer — por exemplo, colado directamente numa constante.

**Confusão anon/serviço** — a comparação directa já descrita.

O programa termina com uma mensagem que também **educa**:

```
[OK] Chaves publicas esperadas (anon, API URL, Turnstile site) podem aparecer — protegidas por RLS
```

Isto previne um pânico legítimo: alguém abre as ferramentas do browser, vê uma chave do Supabase, e conclui que há uma fuga. A mensagem explica antecipadamente que aquela chave é a anónima, que é pública por desenho, e que a protecção real está nas políticas de segurança a nível de linha na base de dados.

### Dependabot

`.github/dependabot.yml` configura actualizações automáticas de dependências: semanais para `npm` em `frontend-web` e em `backoffice-desktop`, semanais para `pip` na raiz, e mensais para as próprias acções do GitHub. Cada actualização chega como um pedido de integração que passa pela integração contínua completa — o que significa que uma actualização que quebre algo é detectada antes de ser aceite. O limite de 5 pedidos abertos por ecossistema evita afogar o repositório.

---

## IX.5 `pre-commit`

### O conceito

**`pre-commit`** é uma ferramenta que instala **ganchos** (*hooks*) no Git: pequenos programas que correm automaticamente em momentos definidos. O gancho de pre-commit corre **antes** de cada registo de alterações, e se falhar, o registo não acontece.

A relação com a integração contínua é de camadas, e a diferença essencial é **quando** o problema é detectado:

| Camada | Quando | Consequência de falhar |
|---|---|---|
| `pre-commit` | Antes do commit, no computador | O commit não se faz. Nada saiu da máquina. |
| CI | Depois do envio, no servidor | O commit existe no histórico e no remoto. |

Para segredos, esta diferença é qualitativa, não quantitativa. Se um segredo entra num commit e esse commit é enviado, o segredo está no histórico do repositório remoto. Mesmo que se remova num commit seguinte, continua acessível. A única remediação séria é **rodar a credencial** — assumir que foi comprometida e substituí-la em todos os sistemas. Se o `pre-commit` travar o commit, nada disto é necessário.

### A configuração

`.pre-commit-config.yaml`:

```yaml
repos:
  - repo: https://github.com/gitleaks/gitleaks
    rev: v8.24.2
    hooks:
      - id: gitleaks
        args: [--config, .gitleaks.toml]

  - repo: local
    hooks:
      - id: verify-bundle-secrets
        name: verify bundle secrets
        entry: python deploy/verify_bundle_secrets.py
        language: system
        pass_filenames: false
        stages: [pre-commit]
```

Dois ganchos, e ambos são sobre segredos — o que revela a prioridade: não são regras de formatação nem de estilo, é contenção de credenciais.

O `gitleaks` está com versão fixada (`rev: v8.24.2`) e usa a mesma configuração da integração contínua, o que garante que o resultado local e o remoto coincidem. Não há nada mais frustrante do que um gancho local que passa e uma integração que falha pela mesma regra.

O segundo gancho corre `verify_bundle_secrets.py`. `language: system` significa que usa o Python já instalado, sem criar um ambiente isolado — apropriado para um script que faz parte do próprio projecto. `pass_filenames: false` é necessário porque o programa analisa uma pasta inteira e não aceitaria uma lista de ficheiros alterados como argumento.

Vale notar que o `pre-commit` é uma protecção **cooperativa**: pode ser contornado com `git commit --no-verify`, e alguém que não o instale não o tem. Por isso as mesmas verificações estão também na integração contínua, que não pode ser saltada. Camadas, outra vez.

---

## IX.6 Checklist operacional actual

Estado verificado, com o que está ligado e o que está pendente, e a razão de cada pendência.

### Ligado e em produção

| Item | Estado | Evidência |
|---|---|---|
| Loja no Cloudflare Pages, em `www.diomika.com` | Produção | Testes Playwright na integração contínua |
| API na máquina virtual com Tunnel, em `api.diomika.com` | Produção | `/health` público responde |
| Portão desktop e regra de firewall administrativa | Activo | Teste `admin público bloqueado` na integração contínua |
| Login de administrador alinhado com as credenciais | Corrigido | Ver nota abaixo |
| Sentry | Ligado | `sentry: true` em `/health/detail` |
| Axiom na edge da União Europeia | Ligado | `axiom: true` em `/health/detail` |
| PostHog na região EU, com consentimento | Ligado | `VITE_POSTHOG_KEY` na construção do Pages |
| UptimeRobot para API e loja | Criados | Dois monitores, 5 minutos |
| Alertas `ntfy` | Ligado | `ALERT_WEBHOOK_URL` configurado |
| Armazenamento privado com endereços assinados | Activo | `SUPABASE_STORAGE_PRIVATE=1` |
| Redis para limitação de taxa e sessões | Activo | `rate_limit: "redis"` em `/health/detail` |

Sobre o login: houve um incidente real, documentado em `RELATORIO_TECNICO.md` §4.4, que vale a pena registar porque a causa é contra-intuitiva. **Alterar `ADMIN_BOOTSTRAP_PASSWORD` no `.env` não altera uma password já existente.** A função `ensure_bootstrap()` começa com:

```python
def ensure_bootstrap() -> None:
    if has_users():
        return
```

Ou seja: se já existe pelo menos um utilizador, a função não faz absolutamente nada. Isto é o comportamento **correcto** — caso contrário, um reinício do contentor reporia a password para o valor do ficheiro de configuração, desfazendo qualquer alteração feita através da aplicação, e o `.env` tornar-se-ia um mecanismo permanente de reposição de credenciais. Mas é surpreendente para quem espera que mudar a configuração mude o comportamento. A resolução correcta é usar `upsert_user`, ou a rota `/admin/auth/change-password`, ou apagar o ficheiro de utilizadores para forçar novo arranque inicial.

### Implementado mas desligado, por decisão

**Segundo factor de autenticação (MFA) — `ADMIN_MFA_REQUIRED=0`.**

O código está completo e funcional: geração de segredo TOTP com `pyotp`, endereço `otpauth://` para configurar na aplicação autenticadora, confirmação do primeiro código, verificação em cada login com tolerância de um intervalo, e interface preparada em `LoginView.vue` com os dois desvios (código exigido e configuração inicial).

Está desligado porque impõe um requisito ao utilizador final: instalar uma aplicação autenticadora no telefone, configurar a conta, e ter o telefone à mão a cada login numa sessão que expira em 15 minutos. Para um cliente que ainda está a adoptar a ferramenta, isso é atrito significativo. A protecção actual — portão no binário, firewall, password forte com política de 12 caracteres e complexidade, limitação de taxa dupla, bloqueio após 5 falhas, detecção de anomalia — é considerada proporcional ao risco. **Ligar é uma alteração de uma variável de ambiente**, sem qualquer desenvolvimento, no dia em que o cliente estiver pronto.

**Cloudflare R2 — código pronto, conta não activada.**

`backend-api/utils/storage_r2.py` implementa o carregamento e a geração de endereços assinados contra o R2, o serviço de armazenamento de objectos do Cloudflare compatível com a interface S3. Activa-se com `STORAGE_BACKEND=r2` e as variáveis `R2_*`. Usa `boto3` com assinatura `s3v4` contra `https://<conta>.r2.cloudflarestorage.com`.

Está desactivado porque o armazenamento do Supabase é suficiente para o volume actual, e o R2 acrescentaria uma conta e um conjunto de credenciais para gerir. O ganho seria distribuição de imagens por rede de conteúdo — relevante com muito tráfego, irrelevante hoje. `deploy/OPS.md` documenta-o como *"opcional; se preenchido + keys → imagens em R2"*, e `deploy/SCALE.md` como *"Storage auto-R2 se `R2_*` existirem"*.

**Assinatura de código — não feita.**

Discutida em detalhe na Parte VIII.5. Decisão económica, com consequência conhecida: avisos do SmartScreen e do Gatekeeper na primeira abertura.

### O comando único de verificação

`deploy/OPS.md` resume a operação a uma linha:

```powershell
python deploy/verify_production.py
```

Esse programa corre, em sequência: `uptime_check.py --ready` (saúde e prontidão), `smoke_test.py` (verificações funcionais na API e na loja), `security_test.py` (verificações de segurança), `load_test.py` com 8 pedidos concorrentes e 40 pedidos totais em modo **suave** (reporta mas não falha), e os testes Playwright, também em modo suave — porque os browsers do Playwright podem não estar instalados localmente e isso não é uma avaria de produção.

O `load_test.py` merece nota: distribui pedidos por `/health`, `/categorias` e `/catalogo/meta`, mede a mediana (p50) e o percentil 95 (p95) das latências, e falha se a taxa de falha exceder 5%. O percentil 95 é uma métrica mais honesta do que a média: significa "95% dos pedidos foram mais rápidos do que isto", e é o número que corresponde à experiência dos utilizadores azarados. Uma média baixa pode esconder que um em cada vinte pedidos demora dez segundos.

Existe ainda `deploy/critical_flow_check.py`, que é apenas um alias:

```python
"""Alias — usa verify_production.py (entrypoint único)."""
```

Manter um único ponto de entrada verdadeiro e aliases para nomes que as pessoas se lembram é melhor do que ter dois programas parecidos a divergir com o tempo.

---

# Parte X — Decisões e compromissos (porque assim)

Esta parte é a mais importante do documento para quem quiser **compreender** o sistema em vez de apenas operá-lo. Cada secção segue a mesma estrutura: qual era o problema, que alternativas existiam, o que foi decidido, o que se perdeu ao decidir assim, e o que faria mudar a decisão.

## X.1 Backoffice na nuvem em vez de Python local

### O problema

A Diomika precisa de uma ferramenta de administração: criar categorias, editar modelos, carregar imagens, ler mensagens de contacto, gerar orçamentos e encomendas em PDF. Quem a usa é pessoal administrativo de uma empresa de almofadas — pessoas competentes no seu trabalho e sem qualquer razão para saber o que é um ambiente virtual de Python.

### As alternativas consideradas

**Alternativa A: correr tudo localmente.** A API e o backoffice no computador do cliente, ligados directamente à base de dados. Vantagem: a superfície de ataque é mínima, porque nada administrativo existe na internet. Desvantagem que a inviabiliza: exige instalar Python, gerir dependências, configurar variáveis de ambiente, e ter as credenciais de serviço da base de dados **no computador do cliente**. Cada actualização seria um procedimento técnico assistido. E o suporte remoto seria quase impossível — "que versão do Python tem instalada?" é uma pergunta que não se faz a um cliente.

**Alternativa B: painel de administração web.** Uma página em `admin.diomika.com`, acessível por browser. Vantagem: zero instalação, actualizações instantâneas, funciona em qualquer dispositivo. Desvantagem decisiva: **o painel administrativo passa a ser acessível a todos os browsers do mundo**. A protecção reduz-se ao nome de utilizador e à password, porque não há nada que distinga o browser do cliente do browser de um atacante. Painéis administrativos web são um dos alvos mais assediados da internet, e existem ferramentas automatizadas que varrem endereços à procura deles continuamente.

**Alternativa C: aplicação de secretária que fala com a API na nuvem.** Um binário por sistema operativo, ligado a `https://api.diomika.com`.

### A decisão e o raciocínio

Escolheu-se C, e a razão fundamental é uma propriedade que só uma aplicação instalada tem: **pode transportar um segredo que um browser não pode**.

Este é o ponto central e vale a pena isolá-lo. Uma página web entrega todo o seu código ao browser do visitante. Qualquer segredo nesse código é legível por quem abrir as ferramentas de desenvolvimento. Não há forma de contornar isto — é uma propriedade fundamental da plataforma, não uma limitação de implementação.

Um binário instalado é diferente. O segredo pode viver no processo principal do Electron, **fora** do alcance do código da interface. Extraí-lo exige inspeccionar o executável, o que é possível mas requer competência e intenção deliberada.

Esta única diferença permite a regra da firewall que é a peça central de toda a segurança administrativa: *bloqueia `/admin` e `/system` a menos que o cabeçalho `x-diomika-desktop` corresponda*. Com essa regra, **todos os browsers do mundo são bloqueados na fronteira do Cloudflare**, e apenas a aplicação oficial passa. Com a alternativa B, uma regra dessas seria impossível, porque o cliente legítimo seria também um browser.

Além disso, a aplicação não precisa de credenciais da base de dados. A chave de papel de serviço do Supabase vive **apenas** no `.env` da máquina virtual. A aplicação fala com a API; a API fala com a base de dados. Se o computador do cliente for comprometido, o atacante obtém o portão e talvez a sessão de 15 minutos — não obtém acesso directo à base de dados.

### O que se perdeu

**O portão é um segredo partilhado num binário distribuído.** Quem tiver o instalador oficial **e** as credenciais de login tem acesso administrativo à API. Isto está registado como limitação em `RELATORIO_TECNICO.md` §5.1 e na Parte XI. As mitigações são: password forte com política aplicada, limitação de taxa dupla, bloqueio após falhas, alerta em cada login falhado, detecção de força bruta, e sessões de 15 minutos. O portão não é autenticação — é uma **restrição de canal**. A autenticação é o login.

**Actualizar exige redistribuir.** Uma correcção na interface do backoffice não chega ao cliente até ele receber e abrir um binário novo. Um painel web actualizava-se instantaneamente para todos.

**Três construções em vez de uma.** Resolvido pela matriz de integração contínua (Parte VIII.4), mas é complexidade permanente: três sistemas operativos que podem falhar de formas diferentes.

**Avisos do sistema operativo.** Consequência da não assinatura (Parte VIII.5).

### O que faria mudar

Se o número de utilizadores administrativos crescesse para dezenas em organizações diferentes, o custo de distribuir binários superaria o benefício, e a resposta seria provavelmente um painel web com autenticação multifactor obrigatória e restrição por endereço IP — trocando o portão no binário por controlos que escalam melhor.

## X.2 Cloudflare Tunnel em vez de portas abertas

### O problema

A API tem de ser alcançável em `https://api.diomika.com`. O caminho convencional é: um endereço IP público na máquina, portas 80 e 443 abertas na firewall, um servidor de proxy inverso à frente, certificados TLS obtidos e renovados automaticamente, e um registo de DNS a apontar para o IP.

Este caminho funciona, é bem compreendido, e tem cinco problemas concretos numa operação pequena.

**Superfície de ataque permanente.** Uma porta aberta é um convite permanente. Todo o endereço IP público na internet recebe varrimentos automatizados continuamente — em minutos após ficar acessível. Cada porta aberta é uma via a defender.

**Certificados para gerir.** Obter, renovar, e não deixar expirar. Um certificado expirado torna o serviço inacessível com um erro alarmante no browser, e acontece tipicamente num fim de semana.

**Configuração de proxy inverso.** Mais um componente para instalar, configurar e manter actualizado.

**IP exposto.** O endereço da máquina fica publicamente conhecido, e passa a ser alvo directo de ataques de negação de serviço que ignoram qualquer camada de protecção.

**IP fixo necessário.** Mudar de máquina exige actualizar DNS e esperar propagação.

### A decisão

Usa-se um **Cloudflare Tunnel**, e a inversão de sentido é a ideia toda: em vez de o mundo se ligar à nossa máquina, a **nossa máquina liga-se ao mundo** e mantém essa ligação aberta.

O processo `cloudflared` corre na máquina virtual e estabelece uma ligação de saída persistente para a rede Cloudflare. O tráfego que chega a `api.diomika.com` desce por essa ligação.

O resultado é que **a máquina virtual não tem nenhuma porta de escuta exposta à internet**. Zero. Um varrimento de portas ao IP não encontra nada. Isto não é uma porta bem protegida — é a ausência de porta.

E os cinco problemas resolvem-se de uma vez:

- Nenhuma porta aberta a defender.
- TLS terminado no Cloudflare, com certificados gerados e renovados automaticamente. Nada a gerir.
- Nenhum proxy inverso a instalar. O `cloudflared` faz o encaminhamento.
- O IP da máquina não é o endereço público. Protecção contra negação de serviço incluída na rede Cloudflare.
- Mudar de máquina é actualizar a configuração de encaminhamento do túnel — que `deploy_vm.py` faz automaticamente por interface de programação. Sem propagação de DNS.

A implementação é a configuração vista em IX.1: `network_mode: host` no serviço `cloudflared` para alcançar `127.0.0.1:8000`, e `ports: "127.0.0.1:8000:8000"` na API para não expor nada.

### O que se perdeu

**Dependência de um único fornecedor.** Se o Cloudflare tiver uma interrupção global, a API fica inacessível — mesmo estando perfeitamente saudável. Esta é a troca central: aceita-se uma dependência crítica em troca de eliminar cinco categorias de trabalho operacional.

**Menos controlo.** Não se vê o tráfego antes de ele chegar ao túnel, e as ferramentas de diagnóstico de rede tradicionais não se aplicam da mesma forma.

**Mais uma peça a correr.** O `cloudflared` é um processo que pode falhar, e se falhar a API fica inacessível. Mitigado por `restart: unless-stopped` e pela verificação externa do UptimeRobot, que detecta o problema em 5 minutos.

**O tráfego passa por terceiros.** O Cloudflare termina o TLS, e portanto vê o tráfego em claro. Isto é verdade para qualquer rede de distribuição de conteúdo, e é a razão pela qual a Diomika não trata dados de cartões nem categorias especiais de dados pessoais nesta via.

### O que faria mudar

Requisitos regulatórios que proibissem terminação de TLS por terceiros, ou volume que tornasse o plano gratuito insuficiente. Nenhum dos dois se aplica hoje.

## X.3 O portão desktop — um segredo partilhado, não JWT

### O problema

Existe uma tensão que parece irresolúvel. O modelo mental do produto é *"administração só no computador do cliente"*. Mas a API está na nuvem, e as rotas `/admin` e `/system` estão nela. Como se restringe uma rota pública a uma aplicação específica?

### As alternativas consideradas

**Autenticação mútua com certificados de cliente (mTLS).** Cada instalação teria o seu certificado, e o Cloudflare validaria na fronteira. É criptograficamente a solução mais forte. É também substancialmente mais complexa: emitir, distribuir, renovar e revogar certificados por instalação, configurar a validação, e tratar os erros com mensagens compreensíveis para um utilizador não técnico. Para o número de instalações em causa, o custo de operação é desproporcionado.

**Restrição por endereço IP.** Só o endereço do escritório do cliente acede. Simples e forte — e frágil na prática: endereços residenciais e de pequenas empresas mudam, e o cliente perde o acesso sem saber porquê, tipicamente na pior altura.

**Um token JWT por instalação.** JWT (*JSON Web Token*) é um formato padrão de token assinado. Mas um JWT resolve o problema de **transportar afirmações verificáveis**, e o problema aqui não é esse: é distinguir a aplicação oficial de qualquer outro cliente. Um JWT de longa duração embutido no binário tem exactamente as mesmas propriedades de segurança de um segredo simples — e acrescenta uma biblioteca, um formato, e uma gestão de expiração que não trazem benefício.

**Nada — apenas o login.** Depender só de utilizador e password. Deixaria `/admin` acessível a todos os browsers, o que é precisamente o que se quer evitar.

### A decisão

Um **segredo partilhado de instalação** num cabeçalho HTTP com nome próprio: `X-Diomika-Desktop`.

O mecanismo completo tem cinco pontos:

1. Um segredo de pelo menos 24 caracteres, gerado com `secrets.token_urlsafe(32)` (criptograficamente seguro).
2. O Electron injecta-o em todos os pedidos, no processo principal, fora do alcance da interface.
3. A API compara com `hmac.compare_digest` (tempo constante, imune a ataques de temporização).
4. Em produção, `/admin`, `/system` e `/health/detail` exigem loopback **ou** portão válido, verificado em duas camadas independentes (`PrivilegedPathMiddleware` e a dependência `admin_must_be_local`).
5. Uma regra de firewall no Cloudflare aplica a mesma restrição **antes** de o pedido chegar à máquina.

O ponto 5 é o que gera o maior benefício prático. Varrimentos automatizados à procura de painéis administrativos — que são constantes — são absorvidos pela rede global do Cloudflare. O nosso servidor nunca os vê.

### O que se perdeu, com honestidade

**Não é autenticação, e não deve ser confundido com autenticação.** É uma restrição de canal: responde a "que software é este?", não a "quem é esta pessoa?". Quem tiver o instalador tem o portão. A identidade é estabelecida pelo login, com scrypt, política de password, bloqueio e alertas.

**A rotação é um procedimento coordenado.** Como descrito em VIII.4, o segredo vive em quatro lugares e trocá-lo exige nova construção, actualização da firewall, actualização do `.env` do servidor, actualização do segredo do GitHub, e redistribuição a todos os clientes. Não é uma operação de rotina — é uma operação planeada. Este é o custo real desta decisão, e é o argumento mais forte contra ela.

**Extraível de um binário.** Alguém com competência e o instalador consegue obter o valor. A mitigação é que isso apenas lhe dá o **canal**; ainda precisa de credenciais válidas, e cada tentativa falhada gera alerta e conta para o bloqueio.

### O que faria mudar

Um incidente em que o portão fosse comprovadamente extraído e usado, ou um número de instalações que tornasse a redistribuição impraticável. Nesse cenário, mTLS por instalação passaria a valer a complexidade, porque permitiria revogar uma instalação sem afectar as outras — que é precisamente a capacidade que o segredo partilhado não tem.

## X.4 scrypt para passwords

### O problema

Passwords não podem ser guardadas em texto. Se a base de dados for comprometida, o atacante teria todas as contas — e, pior, poderia tentar as mesmas passwords em correio electrónico e bancos, porque as pessoas reutilizam.

A solução clássica é guardar uma **dispersão** (*hash*): uma transformação de sentido único. Verifica-se dispersando a tentativa e comparando. A dispersão não permite recuperar a password.

Só que isto, por si, é insuficiente, e por uma razão que é preciso quantificar para se perceber.

### Porque uma dispersão rápida não serve

Funções como MD5, SHA-1 e SHA-256 foram desenhadas para serem **rápidas**, porque o seu propósito principal é verificar integridade de ficheiros grandes. Uma placa gráfica moderna calcula **milhares de milhões de SHA-256 por segundo**.

O que isso significa para um atacante que roubou uma tabela de dispersões: ele não precisa de inverter a função. Faz um ataque de dicionário — pega numa lista de passwords comuns e vazadas (existem listas públicas com centenas de milhões de entradas reais), dispersa cada uma, e compara. A milhares de milhões por segundo, uma lista de mil milhões de candidatos esgota-se em **segundos**.

Aqui está a inversão de intuição que é o coração desta decisão: **para armazenamento de passwords, lentidão é a propriedade desejada**.

### O que é o scrypt

O **scrypt** é uma função de derivação de chave desenhada explicitamente para ser custosa. Tem dois mecanismos de defesa.

**Custo computacional.** O parâmetro `n` controla quantas iterações são feitas. Com `n=2**14` (16384), calcular uma dispersão demora uma fracção de segundo perceptível. Para um utilizador legítimo que faz login, isso é imperceptível. Para um atacante que precisa de testar mil milhões de candidatos, a mesma fracção de segundo multiplicada por mil milhões transforma segundos em séculos.

**Custo de memória.** Esta é a característica que distingue o scrypt e a razão pela qual foi escolhido. O algoritmo exige uma quantidade significativa de memória de acesso aleatório para cada cálculo, controlada por `r` (aqui 8). As placas gráficas — a arma preferida para quebrar passwords — têm milhares de núcleos de cálculo mas memória limitada por núcleo. Uma função que exige memória **anula a vantagem do paralelismo massivo**: não se podem correr dez mil cálculos em paralelo se não há memória para dez mil cálculos. É por isso que o scrypt se diz *memory-hard* (duro em memória).

Os parâmetros na Diomika, em `core/admin_users.py`:

```python
dk = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=2**14, r=8, p=1, dklen=32)
```

`n=2**14` iterações, `r=8` de tamanho de bloco (o factor de memória), `p=1` sem paralelismo, `dklen=32` bytes de saída.

### O sal

```python
salt = salt or secrets.token_bytes(16)
```

Um **sal** (*salt*) são 16 bytes aleatórios, únicos por utilizador, guardados **em claro** ao lado da dispersão. Não é secreto — o seu propósito é outro.

Sem sal, dois utilizadores com a mesma password teriam a mesma dispersão. Isso permite duas coisas ao atacante: ver imediatamente quais contas partilham password, e usar **tabelas pré-calculadas** (*rainbow tables*) — dispersões de milhões de passwords calculadas antecipadamente, uma vez, e reutilizadas contra qualquer base de dados. Com sal único, a tabela pré-calculada é inútil, porque o cálculo teria de ser refeito para cada sal. O trabalho passa a ser por utilizador em vez de universal.

O formato armazenado é `scrypt$<sal-em-base64>$<derivada-em-base64>`. O nome do algoritmo à cabeça permite migrar no futuro sem ambiguidade.

### A comparação final

```python
return hmac.compare_digest(dk, expected)
```

Mesmo aqui, comparação em tempo constante. É uma superfície de ataque menor do que a do portão, mas o custo de fazer bem é zero e a consistência tem valor próprio.

### Porque não bcrypt ou Argon2

O **bcrypt** é excelente e amplamente usado, mas tem um limite de 72 bytes na entrada e não é duro em memória.

O **Argon2** é o vencedor da competição de dispersão de passwords de 2015 e é, tecnicamente, a melhor escolha disponível hoje.

A razão de não usar Argon2 é pragmática e alinhada com um princípio que atravessa todo o projecto: **o scrypt está na biblioteca padrão do Python**, através de `hashlib.scrypt`. O Argon2 exige uma dependência externa (`argon2-cffi`) com componentes compilados. Uma dependência externa é: uma coisa a instalar, uma coisa a actualizar, uma coisa que pode ter uma vulnerabilidade, uma coisa que pode falhar a compilar numa máquina pequena, uma coisa que pode ser abandonada. O scrypt correctamente parametrizado é forte, e não custa nada disso. A diferença de segurança entre scrypt bem configurado e Argon2 é pequena; a diferença de custo operacional não é.

### A política de password que acompanha

Uma função de derivação forte não compensa uma password fraca. `validate_password_strength` exige: pelo menos 12 caracteres (`ADMIN_PASSWORD_MIN_LEN`), uma maiúscula, uma minúscula, um dígito, um símbolo, e rejeita uma lista de passwords óbvias incluindo variantes com o nome da empresa — `"diomika12345"`, `"diomika12345!"`. Esta última inclusão é um detalhe revelador: as passwords que as pessoas realmente escolhem envolvem o nome da empresa, e uma lista genérica de passwords comuns não as apanharia.

## X.5 Não usar uma biblioteca de JWT para sessões

### O problema

Depois do login, cada pedido subsequente precisa de provar "sou o utilizador X, com o papel Y". Reenviar a password é inaceitável. Precisa-se de um token de sessão.

### O que é um JWT e onde brilha

Um **JWT** (*JSON Web Token*) é um formato padronizado: três partes codificadas e separadas por pontos — cabeçalho, carga útil, assinatura. O servidor assina; qualquer parte com a chave pode verificar sem consultar base de dados nenhuma.

Essa última propriedade é a razão de existir dos JWT e é genuinamente valiosa **num contexto específico**: arquitecturas distribuídas, com muitos serviços independentes, possivelmente de equipas diferentes, que precisam de validar identidade sem uma chamada central a cada pedido. O token é auto-suficiente. Escala horizontalmente sem estado partilhado.

### O problema dos JWT que raramente se menciona

A ausência de estado é a força **e** a fraqueza. Um token verdadeiramente sem estado **não pode ser revogado**.

Se um token é válido durante uma hora, e ao fim de dez minutos se descobre que foi roubado, não há nada a fazer: o token continua a validar-se durante os restantes cinquenta minutos, porque a validação é matemática (a assinatura confere, a expiração é futura) e não consulta nada. As respostas habituais da indústria são: tempos de vida muito curtos com um mecanismo de renovação, ou uma lista de revogação — que é **estado**, e portanto abandona a propriedade que justificava o JWT.

Para o backoffice da Diomika, o cenário de token roubado é real: o token é emitido no computador do cliente, guardado no armazenamento de sessão, e o computador pode ser comprometido. A capacidade de revogar imediatamente é mais valiosa do que a capacidade de validar sem estado.

### A decisão

Tokens HMAC próprios, com estado, em `core/session_tokens.py`. Formato:

```
dms1.<carga-em-base64url>.<assinatura-em-base64url>
```

A carga contém utilizador, papel, instante de emissão, expiração e `jti`. A assinatura é HMAC-SHA256 com chave derivada de `API_SECRET_KEY`.

Estruturalmente é semelhante a um JWT. A diferença está nas propriedades operacionais.

**Revogação imediata.** Existe `revoke_session(token)` e `revoke_all_for_user(username)`. Em produção com Redis, uma chave `diomika:sess:revoked:<jti>` invalida o token instantaneamente em todos os processos.

**Uma sessão activa por utilizador.**

```python
old = _active_jti.get(key)
if old and old != jti:
    _revoked.add(old)
```

Emitir uma sessão nova mata a anterior. Consequência de segurança útil: se alguém entrar noutro computador, a sessão em uso morre imediatamente, e o utilizador legítimo nota. É um detector de intrusão embutido no modelo de sessão.

**Expiração por inactividade além da absoluta.** Dois relógios: 15 minutos absolutos, 10 minutos de inactividade. O de inactividade é actualizado a cada pedido (`touch`), e é o que protege o computador deixado desbloqueado.

**Revogação em cascata a partir de mudanças de conta.** `upsert_user` chama `revoke_all_for_user`. Mudar a password, mudar o papel, ou desactivar a conta **invalida imediatamente todas as sessões**. Com JWT sem estado, uma password alterada não invalida nada — o token antigo continua válido até expirar, o que é exactamente o oposto do que um utilizador espera ao mudar a password por suspeita de compromisso.

**Menos superfície e menos dependências.** O ficheiro tem cerca de 250 linhas usando apenas a biblioteca padrão: `hmac`, `hashlib`, `base64`, `json`, `secrets`. Nenhuma biblioteca de JWT para actualizar, e nenhuma exposição às vulnerabilidades históricas dessa família — nomeadamente a classe de falhas de **confusão de algoritmo**, em que um atacante altera o cabeçalho para `alg: none` ou para um algoritmo diferente e a biblioteca aceita. Aqui não existe cabeçalho de algoritmo: só há um algoritmo, escrito no código, e não há nada para confundir.

**Prefixo com versão.** `dms1.` permite reconhecer o formato imediatamente (é o que `is_session_token` faz) e introduzir um `dms2.` no futuro sem ambiguidade.

### A degradação controlada com Redis

`_redis_session_ok` devolve três valores: `True`, `False`, ou `None` quando o Redis não está disponível — caso em que se usa o estado em memória. E em produção final o Redis é **obrigatório**:

```python
if client is None and _redis_required():
    raise RuntimeError("REDIS_URL obrigatório para sessões admin em produção final")
```

A razão é a correcção com múltiplos processos. Com vários trabalhadores (`UVICORN_WORKERS=4`), cada um teria o seu dicionário em memória, e uma sessão revogada num deles continuaria válida nos outros. Falhar no arranque é melhor do que ter revogação parcialmente funcional — um estado de segurança que parece bom e não é.

### O que se perdeu

**Código próprio em vez de biblioteca auditada.** Uma biblioteca de JWT madura foi revista por muita gente. Este código foi revisto por poucos. A mitigação é o tamanho reduzido e o uso exclusivo de primitivas da biblioteca padrão — não se implementou criptografia, apenas se compôs `hmac` e `hashlib`.

**Não interopera.** Um token `dms1.` não é reconhecido por nenhuma ferramenta externa. Irrelevante num sistema fechado; seria um problema se houvesse integrações de terceiros.

## X.6 Armazenamento privado com endereços assinados

### O problema

O catálogo tem imagens de produtos. Precisam de ser servidas à loja e ao backoffice. A opção simples é um contentor público: cada imagem tem um endereço permanente que qualquer pessoa pode abrir.

Para um catálogo de retalho aberto isso é adequado — as imagens são material de marketing.

Para um catálogo **B2B** é diferente, e por três razões concretas. Fotografias de produtos, especialmente de peças personalizadas, podem revelar informação comercial. Um endereço permanente e adivinhável permite enumerar o catálogo inteiro, incluindo produtos ainda não publicados. E um endereço público é indexado por motores de busca, o que pode expor imagens que não deveriam aparecer em resultados de pesquisa.

### A decisão

Armazenamento **privado** com **endereços assinados**, activado por `SUPABASE_STORAGE_PRIVATE=1` (definido em `docker-compose.free.yml`, em `env.free.example`, e garantido por `deploy_vm.py`).

Um endereço assinado é um endereço temporário que contém uma assinatura criptográfica e um prazo. O servidor gera-o quando alguém autorizado pede a imagem; funciona durante o prazo (`STORAGE_SIGNED_URL_TTL`, 3600 segundos por omissão) e depois deixa de funcionar.

Isto muda a natureza do controlo: em vez de "quem souber o endereço vê a imagem para sempre", passa a ser "quem for autorizado agora obtém acesso por uma hora". O contentor não é enumerável, os endereços não são partilháveis indefinidamente, e o controlo de acesso passa a ser da API — que sabe quem está a pedir.

O estado é observável em `/health/detail`, no campo `"storage": "private" | "public"`.

O suporte para R2 (`utils/storage_r2.py`) segue o mesmo modelo, com `generate_presigned_url` e `s3v4`, e com a alternativa de um endereço público de rede de conteúdo através de `R2_PUBLIC_BASE_URL` quando a distribuição rápida for mais importante que a privacidade.

### O que se perdeu

**Não são cacheáveis eficientemente.** Um endereço público pode ser guardado em cache pela rede de distribuição e pelo browser durante meses. Um endereço assinado muda a cada geração, e portanto a cache é muito menos eficaz. Custo: mais tráfego e imagens ligeiramente mais lentas.

**Mais trabalho no servidor.** Cada visualização exige gerar uma assinatura, e cada lista de produtos exige gerar várias.

**Endereços que expiram confundem.** Um utilizador que copie o endereço de uma imagem e o guarde vê-o falhar mais tarde. É correcto por desenho e surpreendente na prática.

### O que faria mudar

Se o catálogo se tornasse deliberadamente público como ferramenta de marketing, o armazenamento público com rede de distribuição seria a escolha certa, e a variável já existe para inverter a decisão sem alterar código.

## X.7 Observabilidade freemium: cinco ferramentas em vez de uma

### O problema

Precisa-se de erros, logs, analítica de produto, uptime e alertas. Há três formas de o obter.

**Uma plataforma comercial única.** Datadog, New Relic, Grafana Cloud. Tudo integrado, correlação automática entre sinais, uma factura. E dezenas a centenas de euros por mês, escalando com volume — o que colide com o objectivo de zero euros de infra-estrutura recorrente.

**Auto-alojamento.** Prometheus, Grafana, Loki e Sentry auto-alojado na própria máquina. Sem custo de licença. E impraticável aqui por duas razões independentes. A primeira é capacidade: uma `e2-micro` não tem recursos para a API e mais uma pilha de observabilidade — e a pilha competiria pela memória com o serviço que devia observar. A segunda é mais séria: **monitorização alojada na máquina monitorizada não serve para monitorizar essa máquina**. Se a máquina cai, os painéis caem com ela, e a informação sobre a queda desaparece exactamente quando é necessária.

**Vários serviços gratuitos, um por função.**

### A decisão

A terceira via, e a lista está registada em `deploy/APRESENTACAO_CLIENTE.md` com a justificação de cada escolha:

| Função | Ferramenta | Porque esta |
|---|---|---|
| Erros da API | Sentry | Stack traces completos, agrupamento, alertas |
| Logs e pesquisa | Axiom | Logs JSON pesquisáveis; substitui um "SIEM caseiro" |
| Analítica da loja | PostHog (EU) | Funis e percursos, não apenas contagens |
| Uptime | UptimeRobot | Verificação externa e independente |
| Alertas | Webhook e ficheiro local | Já no código, sem dependência |

O mesmo documento registra o que foi **removido de propósito**: Plausible, uma implementação própria de contagem de visitas num endpoint, e Grafana na máquina virtual. Documentar rejeições é tão valioso como documentar escolhas — impede que alguém reintroduza uma opção já avaliada e descartada.

O que faz esta arquitectura funcionar é uma decisão de implementação: **cada integração é opcional e isolada**. Como visto na Parte VII.1, cada uma verifica a sua credencial e desliga-se se não a tiver, e todo o envio externo engole falhas. Isto significa que os cinco serviços não formam uma cadeia de dependências — são cinco caminhos paralelos, e a falha de qualquer um não afecta os outros nem o sistema principal.

Há também um efeito de composição interessante: os alertas escrevem no log da aplicação, e o log vai para o Axiom. Uma linha de código (`logger.warning`) alimenta duas ferramentas.

### O que se perdeu

**Correlação manual.** Uma plataforma única mostraria um erro, os logs adjacentes e a latência do mesmo pedido no mesmo ecrã. Aqui é preciso copiar o identificador do pedido de uma ferramenta para outra. É precisamente por isso que o `request_id` existe e é propagado com tanto cuidado — é a cola manual que substitui a correlação automática.

**Cinco contas para gerir.** Cinco credenciais, cinco painéis, cinco conjuntos de configuração de alertas.

**Quotas e instabilidade de planos gratuitos.** Registado em `RELATORIO_TECNICO.md` §12, com um exemplo concreto e revelador: a interface do UptimeRobot mudou o caminho de criação de monitores de `/create` para `/new/http`. Fornecedores gratuitos mudam interfaces sem aviso, e procedimentos documentados ficam obsoletos.

**Sem garantia de serviço.** Um plano gratuito pode degradar, mudar de condições, ou desaparecer.

### O que faria mudar

Crescimento que esgotasse as quotas gratuitas, ou uma operação com pessoas de plantão a exigir correlação rápida durante incidentes. `deploy/SCALE.md` já aponta o primeiro passo nessa direcção: um alerta de orçamento na Google Cloud entre 1 e 5 dólares, para detectar crescimento de custo antes de ele surpreender.

## X.8 Arquitectura orientada ao esquema

### O problema

Um catálogo tem muitas tabelas — categorias, modelos, almofadas, assentos, cores, pedidos de orçamento, encomendas internas, mensagens de contacto. Cada uma precisa de definição na base de dados, validação na API, e um formulário no backoffice.

Escrever estas três coisas à mão para cada tabela cria o problema clássico da **divergência** (*drift*): acrescenta-se um campo à base de dados, esquece-se de o acrescentar à validação, e ele nunca é gravado. Ou acrescenta-se à validação e não ao formulário, e o administrador não o consegue preencher. Com um campo, é um lapso; com dezenas de tabelas e centenas de campos, é uma fonte permanente de defeitos subtis e difíceis de localizar.

### A decisão

Uma **fonte única de verdade**: os modelos Pydantic em `backend-api/models/schemas.py`. Desses modelos derivam-se as outras três coisas:

- A **validação da API** — o Pydantic faz isso nativamente, é a sua função.
- Os **formulários do backoffice** — servidos por `GET /system/schema/form/{table}` e consumidos por `SchemaForm.vue`. O backoffice **não tem formulários escritos à mão**: pede a descrição do formulário à API e desenha-o.
- O **SQL da base de dados** — sincronizado pelo `schema_engine`, com os ficheiros gerados visíveis em `backend-api/sql/generated_*.sql` (todos no `.gitignore`, por serem derivados).

A consequência prática é que acrescentar um campo é **uma alteração num lugar**. O modelo muda; a validação muda automaticamente; o formulário do backoffice passa a mostrar o campo novo sem uma linha de código de interface; e o SQL de sincronização reflecte-o. A divergência torna-se estruturalmente difícil, em vez de evitada por disciplina.

Existe ainda `POST /system/schema/sync?dry_run=true`, que mostra o que seria alterado sem alterar nada. Um ensaio a seco antes de tocar na base de dados de produção é uma cortesia elementar que muitas ferramentas de migração não oferecem.

### O que se perdeu

**Uma camada de indirecção.** Compreender como um campo chega ao ecrã exige perceber o gerador, não apenas ler o formulário. A curva de aprendizagem inicial é mais íngreme.

**Casos especiais precisam de escape.** Campos com comportamento peculiar não se exprimem bem num gerador. É por isso que existem componentes dedicados — `CompositionField.vue`, `ImageField.vue`, `ModelColorsPanel.vue`, `OrderRecordPanel.vue`. A regra prática é: o gerador trata os 90% regulares, e o restante é explícito.

**Formulários genéricos são menos polidos.** Um formulário desenhado à mão pode ter agrupamentos, ajuda contextual e disposição pensada para a tarefa. Um gerado é correcto e uniforme.

**O gerador é código crítico.** Um defeito nele afecta todas as tabelas ao mesmo tempo. É um ponto único de falha em troca de eliminar uma classe inteira de defeitos distribuídos.

## X.9 A pilha de zero euros

### O objectivo

Está declarado em vários documentos, incluindo `deploy/FREE_STACK.md`: *"Único gasto: domínio `diomika.com`."* Infra-estrutura recorrente de zero euros por mês.

### Como se consegue

| Peça | Serviço | Plano |
|---|---|---|
| Loja | Cloudflare Pages | Gratuito |
| Rede, TLS, firewall, Tunnel | Cloudflare | Gratuito |
| Computação da API | Google Cloud `e2-micro` | Always Free |
| Base de dados e armazenamento | Supabase | Gratuito |
| Erros | Sentry | Gratuito |
| Logs | Axiom | Gratuito |
| Analítica | PostHog | Gratuito |
| Uptime | UptimeRobot | Gratuito |
| Alertas | ntfy | Gratuito |
| Integração contínua e construções | GitHub Actions | Gratuito para repositório privado, dentro da quota |
| Domínio | Cloudflare Registrar | Custo anual — o único |

### Porque isto não é só avareza

É tentador ver a restrição de custo como uma limitação imposta. Vale a pena o argumento oposto, porque é genuinamente verdadeiro neste caso: **a restrição melhorou a arquitectura**.

Três exemplos concretos.

O Tunnel foi escolhido por ser gratuito e por evitar gerir certificados. O resultado é uma máquina **sem portas expostas** — uma postura de segurança melhor do que a de uma máquina com portas abertas e bem configuradas. A opção mais barata era também a mais segura.

A `e2-micro` obrigou a atenção genuína a eficiência: cache do estado da fila de saída, prazos curtos, envio de logs em lote, sem persistência no Redis, ficheiro de swap. Uma máquina generosa teria permitido desleixo, e o desleixo custa em qualquer escala.

Cinco serviços gratuitos em vez de uma plataforma paga forçou a que cada integração fosse **opcional e isolada**. Uma plataforma única teria produzido, muito provavelmente, um acoplamento em que a indisponibilidade do fornecedor afectaria o serviço. A restrição impôs desacoplamento.

### O que se perdeu

**Nenhum acordo de nível de serviço.** Nenhum destes fornecedores garante nada para um plano gratuito. Não há a quem recorrer numa interrupção.

**Quotas que podem ser atingidas.** Especialmente na observabilidade. `deploy/SCALE.md` reconhece isto e prescreve o alerta de orçamento como primeiro sinal.

**Capacidade limitada.** Uma `e2-micro` tem um tecto real, registado em `RELATORIO_TECNICO.md` §12.

**Risco de mudança de condições.** Planos gratuitos mudam. Já mudaram no passado, noutros fornecedores, com pouco aviso.

### O caminho de saída, já documentado

`deploy/SCALE.md` é curto e útil precisamente por isso:

1. Alerta de orçamento na Google Cloud entre 1 e 5 dólares — detecção precoce.
2. Mais trabalhadores, ou upgrade do Supabase, se o processador da base de dados estiver alto.
3. Auto-alojar o PostgreSQL **só com um manual de operações escrito** — e explicitamente *"não é o próximo passo"*.

A última linha é a mais sensata do documento. Auto-alojar uma base de dados é a decisão que parece poupar dinheiro e custa mais em trabalho operacional, risco de perda de dados e responsabilidade de cópias de segurança. Escrever "não é o próximo passo" **antes** de a pressão existir é uma forma de proteger a decisão futura de um impulso.

---

# Parte XI — Limitações honestas

Esta secção existe porque um relatório técnico que só descreve o que funciona não é um relatório técnico — é material de marketing. Cada limitação está acompanhada do que a mitiga e do que faria mudar.

## XI.1 O portão está no binário

**A limitação.** Quem tiver o instalador oficial e credenciais de login válidas tem acesso administrativo à API. O portão é um segredo partilhado, extraível de um executável por alguém com competência e intenção.

**O que mitiga.** Não é a única barreira. É preciso, além do portão, uma password que cumpre a política (12 caracteres, quatro classes), e cada tentativa falhada gera um alerta, conta para o bloqueio após 5 falhas, e alimenta a detecção de força bruta. A sessão obtida dura 15 minutos e expira com 10 de inactividade. A firewall bloqueia na fronteira quem não tem o portão.

**O que faria mudar.** Um incidente comprovado de extracção e uso, ou a necessidade de revogar uma instalação individual — capacidade que um segredo partilhado não tem e que mTLS por instalação daria.

## XI.2 A password de arranque não roda o armazenamento de utilizadores

**A limitação.** Alterar `ADMIN_BOOTSTRAP_PASSWORD` no `.env` **não** altera uma password já existente, porque `ensure_bootstrap()` sai imediatamente se `has_users()` for verdadeiro.

**Porque é assim.** É intencional e correcto: caso contrário, cada reinício reporia a password para o valor do ficheiro de configuração, desfazendo alterações feitas pela aplicação.

**O que mitiga.** Está documentado em `RELATORIO_TECNICO.md` §4.4 e nesta secção. Existem três caminhos correctos: `upsert_user`, a rota `/admin/auth/change-password`, ou apagar o ficheiro de utilizadores para forçar novo arranque inicial.

**O que faria mudar.** Um comando de operações dedicado — algo como `python deploy/reset_admin.py` — reduziria o risco de alguém tentar o caminho errado durante um incidente. É trabalho pequeno e não feito.

## XI.3 Dependência de planos gratuitos

**A limitação.** Nove serviços em plano gratuito, sem acordo de nível de serviço, com quotas e interfaces que mudam sem aviso.

**Exemplo concreto e documentado.** A interface do UptimeRobot mudou o caminho de criação de monitores de `/create` para `/new/http`, invalidando um procedimento escrito.

**O que mitiga.** Cada integração é opcional: remover uma variável de ambiente desactiva a peça sem afectar o resto. Nenhum dado de negócio vive exclusivamente num serviço de observabilidade — a fonte de verdade é o PostgreSQL. `deploy/SCALE.md` prescreve o alerta de orçamento como detector precoce.

**O que faria mudar.** Esgotar quotas, ou uma mudança de condições que torne um serviço inviável. A resposta seria migrar essa peça, não a arquitectura.

## XI.4 Binários não assinados

**A limitação.** Avisos do SmartScreen no Windows e bloqueio do Gatekeeper no macOS na primeira abertura, com caminhos de contorno pouco óbvios (Parte VIII.5).

**O que mitiga.** Instruções explícitas no `LEIA-ME.txt`, entrega por canal privado a cliente identificado, artefactos rastreáveis a uma etiqueta do repositório com retenção de 90 dias.

**O que faria mudar.** Distribuição mais ampla, ou fricção reportada pelo cliente que justifique algumas centenas de euros por ano.

## XI.5 Capacidade da `e2-micro`

**A limitação.** A máquina é modesta. A API, o Redis e os trabalhadores embutidos partilham recursos escassos.

**O que mitiga.** Ficheiro de swap de 2 gigabytes criado pelo `deploy_vm.py`; Redis sem persistência; cache de 30 segundos na contagem de pendentes; prazos curtos em todas as chamadas externas; envio de logs em lote; alerta de latência a 2 segundos como sinal precoce; `load_test.py` para medir antes de doer.

**O que faria mudar.** Um percentil 95 consistentemente acima do limiar de latência, ou alertas de latência frequentes. `deploy/SCALE.md` tem o caminho.

## XI.6 Segundo factor implementado e desligado

**A limitação.** Existe apenas password para o acesso administrativo hoje.

**O que mitiga.** Política de password aplicada, limitação de taxa dupla, bloqueio, alertas, detecção de anomalia, portão, firewall, sessões curtas.

**O que faria mudar.** Uma alteração de `ADMIN_MFA_REQUIRED` para `1`. Sem desenvolvimento. A decisão é de prontidão do cliente, não técnica.

## XI.7 A fila de logs vive em memória

**A limitação.** O `AxiomHandler` acumula até 5 eventos antes de enviar; um reinício perde os pendentes. E o `except Exception: pass` significa que uma falha de envio é silenciosa.

**O que mitiga.** Os logs são um sinal secundário. Erros vão também para o Sentry ou para `errors.jsonl`; alertas vão sempre para `deploy/alerts.log`. Existem três destinos independentes, e a perda dos três simultaneamente é improvável.

**O que faria mudar.** Se a investigação de incidentes passasse a depender criticamente de completude nos logs, seria necessária uma fila persistente em disco.

## XI.8 O limite de tamanho do corpo confia no cabeçalho declarado

**A limitação.** O `BodySizeLimitMiddleware` verifica só o `Content-Length`, que um cliente pode declarar falsamente.

**Porque é assim.** Ler o fluxo do corpo no middleware esgotava-o e quebrava a interpretação do JSON nas rotas (Parte VIII.7, Passo 6). A correcção foi simplificar.

**O que mitiga.** O servidor web e a fronteira Cloudflare impõem os seus próprios limites. `MAX_REQUEST_BODY_BYTES` continua a apanhar o caso honesto, que é a maioria.

**O que faria mudar.** Abuso observado por declaração falsa de tamanho. A solução seria impor o limite numa camada ASGI mais baixa, que não sofre do mesmo problema.

## XI.9 Um único operador

**A limitação transversal.** Todos os procedimentos assumem uma pessoa com acesso ao `.env`, ao SSH da máquina, ao GitHub e às contas dos fornecedores. Não há rotação de plantão, nem revisão por segunda pessoa, nem separação de funções.

**O que mitiga.** Automação que reduz passos manuais (`deploy_vm.py`, `verify_production.py`, um comando por operação); documentação escrita (`OPS.md`, `FREE_STACK.md`, `SCALE.md`, este relatório); e verificações que não dependem de memória humana (integração contínua, `pre-commit`, gitleaks).

**O que faria mudar.** Uma segunda pessoa envolvida na operação exigiria gestão de segredos partilhados e registo de auditoria mais formal.

---

# Parte XII — Como estudar o código

## O mapa das pastas

```
diomika/
├── backend-api/              A API (Python + FastAPI)
│   ├── main.py               ── PONTO DE ENTRADA. Começar aqui.
│   ├── core/                 Infra-estrutura transversal
│   ├── routes/               Endpoints HTTP
│   ├── models/               Modelos Pydantic — a fonte de verdade do esquema
│   ├── utils/                Auxiliares (storage, email, imagens, Turnstile)
│   ├── sql/                  SQL, incluindo generated_*.sql (ignorados pelo Git)
│   ├── data/                 admin_users.json (ignorado pelo Git)
│   └── tests/                Testes pytest
│
├── frontend-web/             A loja pública (Vue 3 + Vite)
│   ├── src/views/            Uma página por rota
│   ├── src/components/       Componentes, incluindo CookieBanner.vue
│   ├── src/lib/              Cliente Supabase para o catálogo
│   ├── functions/            _middleware.js — bloqueio de sondagens no Pages
│   ├── public/               _headers, robots
│   └── e2e/                  Testes Playwright
│
├── backoffice-desktop/       A aplicação de administração (Electron + Vue)
│   ├── electron/main.cjs     ── O proxy e o servidor local. Ler cedo.
│   ├── scripts/              write-gate.cjs
│   └── src/                  Interface Vue
│
├── deploy/                   Automação e documentação de operações
└── .github/workflows/        Integração contínua
```

## A ordem de leitura recomendada

A tentação natural é abrir ficheiros ao acaso. Não funciona bem neste código, porque a lógica interessante está nas camadas transversais e não nas rotas. A ordem abaixo constrói entendimento em camadas.

**Nível 1 — Orientação (30 minutos).** `README.md` na raiz, `deploy/APRESENTACAO_CLIENTE.md` (a visão de negócio), `deploy/FREE_STACK.md` (a topologia num diagrama), e `deploy/RELATORIO_TECNICO.md` (o mapa completo). Nada de código ainda.

**Nível 2 — O ponto de entrada (1 hora).** `backend-api/main.py`, do princípio ao fim. É o índice de toda a API: a configuração de logging, o arranque do rastreio de erros, a ordem dos middlewares com o comentário sobre a inversão do Starlette, os routers incluídos, o manipulador global de excepções, e as três rotas de saúde. Depois `backend-api/core/config.py`, para ver como a configuração é lida e validada no arranque.

**Nível 3 — As camadas de segurança (2 a 3 horas).** Esta é a parte mais densa e a mais recompensadora. Nesta ordem exacta, porque cada ficheiro depende de conceitos do anterior:

1. `core/local_only.py` — 55 linhas. O portão e o loopback. É o coração do modelo de acesso.
2. `core/path_guard.py` — 49 linhas. O guarda de fronteira e o bloqueio de emergência.
3. `core/middleware.py` — todas as camadas transversais, incluindo o `BodySizeLimitMiddleware` com a sua docstring que documenta uma avaria real.
4. `core/auth.py` — os papéis, as chaves por escopo, e as listas de tabelas bloqueadas e sensíveis.
5. `core/admin_users.py` — scrypt, política de password, bloqueio, arranque inicial.
6. `core/session_tokens.py` — a emissão, a validação, a revogação, e a lógica de Redis.
7. `core/ssrf_guard.py` — 65 linhas. A lista de permissões de saída.

**Nível 4 — Observabilidade (1 hora).** `core/structured_logging.py` (o formatador e a bifurcação da edge do Axiom), `core/sentry_init.py`, `core/error_tracking.py`, `core/alerts.py`, `core/anomaly.py`, `core/feature_flags.py`, `core/health.py`.

**Nível 5 — O backoffice (2 horas).** `backoffice-desktop/electron/main.cjs` do princípio ao fim — é o ficheiro mais instrutivo de todo o projecto, porque contém o servidor local, o proxy, a injecção do portão, a limpeza de cabeçalhos nos dois sentidos, a protecção contra travessia de caminhos, e a configuração de segurança da janela. Depois `scripts/write-gate.cjs`, `src/lib/settings.js`, `src/lib/api.js`, e `src/views/LoginView.vue`.

**Nível 6 — O fluxo público (1 hora).** `routes/contact.py` como caso completo: bandeira de funcionalidade, limitação de taxa, idempotência, favo de mel, Turnstile, saga. Depois `frontend-web/src/components/CookieBanner.vue` e `frontend-web/functions/_middleware.js`.

**Nível 7 — Operações (1 a 2 horas).** `deploy/deploy_vm.py`, `deploy/docker-compose.free.yml`, `deploy/deploy_beta.py`, `deploy/verify_bundle_secrets.py`, `.github/workflows/ci.yml`, `.github/workflows/backoffice-release.yml`.

**Nível 8 — Os testes.** Deixados para o fim de propósito, e é a melhor parte. `backend-api/tests/` lê-se como uma **especificação executável** do modelo de segurança: cada teste é uma afirmação sobre o que o sistema deve recusar. `test_observability_flags.py` é um bom ponto de partida pela sua brevidade. `frontend-web/e2e/critical.spec.js` tem quatro testes que resumem o que significa "o sistema está bem".

## Três coisas a saber antes de começar

**O código está em português.** Nomes de tabelas (`pedidos_orcamento`, `encomendas_internas`, `modelo_cores`), campos (`visibilidade`, `lida`, `assunto`), comentários e mensagens de erro. Isto é deliberado: o domínio de negócio é português, e traduzir o vocabulário do negócio para inglês introduziria uma camada de tradução mental permanente e propensa a erro.

**Os ficheiros pequenos são os importantes.** `local_only.py` tem 55 linhas e é o pilar de todo o modelo de acesso administrativo. `path_guard.py` tem 49. `ssrf_guard.py` tem 65. `feature_flags.py` tem 29. Neste código, densidade de importância é inversamente proporcional ao número de linhas.

**Ler as docstrings e os comentários.** Não são decorativos. Vários documentam avarias reais e a razão de decisões contra-intuitivas: a advertência de não consumir o fluxo do corpo no `BodySizeLimitMiddleware`, os dois formatos de endereço do Axiom, a nota de que o `X-Forwarded-For` é forjável, a explicação da alternativa de ligação ao PostgreSQL quando os certificados falham, a razão de publicar o Pages a partir de `frontend-web`. Cada um desses comentários é uma tarde de depuração que não é preciso repetir.

---

# Apêndice A — Fluxos sequenciais

## A.1 Um visitante envia uma mensagem de contacto

```
 1. Visitante abre https://www.diomika.com/contacto
      └─ Cloudflare Pages serve a aplicação Vue
      └─ functions/_middleware.js já bloqueou sondagens a .env, .git, /src
      └─ public/_headers aplica a política de segurança de conteúdo

 2. CookieBanner.vue avalia o consentimento
      ├─ 'accepted'  → carrega o PostHog dinamicamente, sem aviso
      ├─ 'rejected'  → não carrega nada, sem aviso
      ├─ sem decisão e sem chave → não mostra aviso
      └─ sem decisão e com chave → mostra o aviso

 3. Visitante preenche o formulário
      └─ O campo 'website' fica invisível e vazio (favo de mel anti-robô)
      └─ useTurnstile.js resolve o desafio e obtém um sinal

 4. POST https://api.diomika.com/contacto
      Cabeçalhos: Content-Type, Idempotency-Key
      Corpo: nome, email, contacto, assunto, mensagem, website, sinal Turnstile

 5. Cloudflare: TLS, mínimo 1.2, verificação de agente do utilizador não vazio

 6. Tunnel → 127.0.0.1:8000 (nenhuma porta pública na máquina)

 7. Middlewares, de fora para dentro:
      PrivilegedPath   → /contacto bloqueado só se SECURITY_LOCKDOWN
      RequestId        → gera o UUID e devolve-o em X-Request-Id
      SecurityHeaders  → prepara os cabeçalhos da resposta
      LatencyAlert     → arranca o cronómetro
      BodySizeLimit    → verifica Content-Length contra o máximo
      GlobalRateLimit  → limite global por minuto

 8. routes/contact.py, em ordem:
      a) flag("CONTACT_FORM", True) → se falso, 503 com mensagem
      b) rate_limit "contact_form", 5 por 60 segundos
      c) Idempotency-Key obrigatória em produção (400 se ausente,
         409 se já em processamento, resposta em cache se repetida)
      d) msg.website preenchido → 400 e registo do favo de mel
      e) verify_turnstile_async → 400 se falhar
      f) run_contact_submission_saga(...)

 9. A saga (transacção com compensações):
      ├─ Grava em contact_messages
      ├─ Envia notificação por correio electrónico (disjuntor SMTP)
      └─ Enfileira em outbox_events para o trabalhador reprocessar

10. Resposta 200:
      { status, message, email_notified, message_status }
      + complete_idempotent_request grava a resposta em cache

11. LatencyAlert: se demorou ≥ ALERT_LATENCY_MS
      └─ send_alert → logger.warning (→ Axiom)
                    → deploy/alerts.log
                    → webhook ntfy (validado por SSRF)

12. Se algo rebentou sem ser apanhado:
      └─ manipulador global → logger.exception (→ Axiom)
                            → capture_exception (→ Sentry ou errors.jsonl)
                            → 500 { detail: "Erro interno" }, sem stack trace
```

## A.2 O administrador entra no backoffice

```
 1. Duplo clique no executável
      └─ Electron arranca
      └─ Sem portão no binário? Diálogo "Build incompleto"
      └─ apiHealthOk(): GET /health, 8s, aceita 200–499
      └─ Servidor local em 127.0.0.1:<porta efémera>
      └─ Janela carrega http://127.0.0.1:<porta>/
         (contextIsolation, sandbox, sem integração de Node)

 2. LoginView.vue → GET /api/admin/auth/status
      └─ Descobre login_required, TTL da sessão, se exige MFA
      └─ Sessão guardada? Valida com api.me() ou limpa

 3. Utilizador submete → POST /api/admin/auth/login
      Corpo: { username, password }
      SEM cabeçalho de portão — a interface não conhece o segredo

 4. proxyToApi no processo principal do Electron:
      ├─ Retira o prefixo /api
      ├─ host → api.diomika.com
      ├─ Remove origin, referer, accept-encoding
      ├─ user-agent → DiomikaBackoffice/1.0
      └─ ADICIONA x-diomika-desktop: <valor-secreto>   ◄── o momento decisivo

 5. Cloudflare:
      ├─ TLS (mínimo 1.2, modo strict)
      ├─ Regra: agente do utilizador não vazio → passa
      └─ Regra: /admin com x-diomika-desktop correcto → PASSA
         (um browser normal seria BLOQUEADO aqui, longe da máquina)

 6. Tunnel → 127.0.0.1:8000

 7. PrivilegedPathMiddleware:
      ├─ SECURITY_LOCKDOWN? → 503
      └─ Produção e /admin → privileged_access_ok()
           ├─ peer_is_loopback (IP TCP real, nunca X-Forwarded-For)
           └─ desktop_gate_ok (hmac.compare_digest, tempo constante)

 8. Dependência do router: admin_must_be_local → mesma verificação, 403 se falhar

 9. Limitação dupla:
      ├─ Por IP:       20 por 300 segundos
      └─ Por username: 10 por 300 segundos (anti força bruta distribuída)

10. authenticate():
      ├─ Lê data/admin_users.json
      ├─ Conta desactivada? → recusa
      ├─ locked_until no futuro? → recusa
      ├─ verify_password: scrypt n=2^14 r=8 p=1 dklen=32, sal de 16 bytes
      │                   comparação com hmac.compare_digest
      ├─ Falhou? → incrementa; 5 falhas → bloqueio de 15 minutos
      └─ MFA exigido? → devolve mfa_required ou mfa_setup_required

11. Se falhou:
      ├─ log_admin_action("login_failed") com a razão real
      ├─ send_alert (Axiom + alerts.log + ntfy)
      ├─ note_login_failure → 8 falhas em 600s = alerta crítico
      └─ 401 "Credenciais inválidas"  ◄── genérico, sem enumeração

12. Se passou — issue_session():
      ├─ payload { u, r, iat, exp, jti }
      ├─ HMAC-SHA256 com chave derivada de API_SECRET_KEY (≥32 chars)
      ├─ Token: dms1.<carga>.<assinatura>
      ├─ Revoga a sessão anterior do mesmo utilizador
      └─ Redis: diomika:sess:user:<utilizador> e :seen:<jti>

13. Resposta: { access_token, token_type, expires_in, username, role, mfa_enabled }
      └─ Proxy remove Cross-Origin-Resource-Policy e Cross-Origin-Opener-Policy
         (sem isto, o Chromium embutido bloquearia a resposta)

14. LoginView:
      ├─ saveSettings({ accessToken }) → sessionStorage (não localStorage)
      ├─ writeSessionUser({ username, role })
      └─ Navega para o espaço de trabalho

15. Pedidos seguintes:
      Authorization: Bearer dms1....
      └─ require_api_key reconhece o prefixo, valida assinatura,
         verifica revogação e inactividade, anexa papel e actor
      └─ 15 minutos absolutos, 10 de inactividade
```

## A.3 Uma linha de log chega ao Axiom

```
 1. Em qualquer ponto do código:
      logger.info("Mensagem", extra={"request_id": rid, "path": p, "ms": 42})

 2. O logger raiz distribui por todos os handlers registados
      (configurados uma vez por configure_structured_logging)

 3. StreamHandler com JsonFormatter (se LOG_FORMAT=json):
      { ts, level, logger, msg }
      + exc se houver excepção
      + request_id, path, method, status, ms se presentes
      → saída padrão → registo do Docker → journal da máquina

 4. AxiomHandler.emit(record), em paralelo:
      a) AXIOM_TOKEN vazio? → sai. Custo zero.
      b) AXIOM_DATASET, por omissão "diomika"
      c) Constrói { ts, level, logger, msg }
      d) Com _axiom_lock: acrescenta à fila
      e) Fila com < 5 itens? → sai e espera
      f) Fila com ≥ 5? → retira todos e limpa

 5. Escolha do endereço (a bifurcação que custou uma tarde):
      base = AXIOM_API_URL, por omissão https://api.axiom.co

      "edge.axiom.co" em base?
        SIM → {base}/v1/ingest/{dataset}              ◄── edge EU, o actual
        NÃO → {base}/v1/datasets/{dataset}/ingest     ◄── legado dos EUA

      Produção: https://eu-central-1.aws.edge.axiom.co/v1/ingest/diomika

 6. assert_safe_outbound_url(url):
      ├─ Esquema https? Senão, rejeita
      ├─ Domínio na lista de permissões?
      │    eu-central-1.aws.edge.axiom.co ✓
      └─ Se for IP literal, verifica redes bloqueadas
         (127/8, 10/8, 172.16/12, 192.168/16, 169.254/16, ::1, fc00::/7, fe80::/10)

 7. POST com:
      Authorization: Bearer <token>
      Content-Type: application/json
      User-Agent: DiomikaAxiom/1.0
      Corpo: lote JSON de 5+ eventos
      Prazo: 5 segundos

 8. Falhou? → except Exception: pass
      └─ Log perdido. Pedido do cliente intacto.  ◄── a prioridade correcta

 9. No Axiom, os eventos ficam pesquisáveis:
      level == "ERROR"
      request_id == "<uuid>"        ◄── a cola entre ferramentas
      ms > 2000
```

---

# Apêndice B — Índice de ficheiros-chave

## API — infra-estrutura transversal (`backend-api/core/`)

| Ficheiro | Responsabilidade | Porque importa |
|---|---|---|
| `local_only.py` | Portão desktop e loopback | O pilar do modelo de acesso administrativo. 55 linhas. |
| `path_guard.py` | Fronteira de caminhos privilegiados e bloqueio global | Fecha `/admin` e `/system` antes das rotas. Tem o interruptor de emergência. |
| `middleware.py` | Cabeçalhos, identificador, taxa, tamanho, latência | Documenta a avaria do corpo esgotado. |
| `auth.py` | Papéis, chaves por escopo, controlo por tabela | Aceita sessão ou chave de máquina. Lista de tabelas bloqueadas. |
| `admin_users.py` | scrypt, política, bloqueio, arranque inicial | Onde vive a decisão de scrypt e o comportamento surpreendente do arranque. |
| `session_tokens.py` | Emissão, validação e revogação de sessões | A alternativa própria ao JWT, com estado e revogável. |
| `ssrf_guard.py` | Lista de permissões de saída | Nega por omissão. 65 linhas. |
| `structured_logging.py` | JSON e envio para o Axiom | A bifurcação da edge da União Europeia. |
| `sentry_init.py` | Sentry opcional | Amostragem de 5%, sem informação pessoal. |
| `error_tracking.py` | Sentry ou ficheiro local | A rede de segurança de custo zero. |
| `alerts.py` | Webhook e ficheiro local | Sempre grava localmente; nunca rebenta. |
| `anomaly.py` | Detecção de força bruta | Limiar e período de silêncio contra fadiga de alertas. |
| `feature_flags.py` | `FEATURE_*` | 29 linhas. Interruptores sem desenvolvimento. |
| `health.py` | As três sondas | Alternativa de PostgreSQL quando os certificados falham. |
| `config.py` | Configuração e validação no arranque | Falha ruidosamente em vez de operar mal configurado. |

## API — entrada e rotas

| Ficheiro | Responsabilidade |
|---|---|
| `backend-api/main.py` | Ponto de entrada: logging, erros, middlewares, routers, saúde |
| `routes/admin_auth.py` | Login, MFA, logout, alterar password, desactivar utilizador |
| `routes/contact.py` | Formulário público completo: bandeira, taxa, idempotência, favo de mel, Turnstile, saga |
| `models/schemas.py` | Modelos Pydantic — a fonte única de verdade do esquema |
| `utils/storage.py` / `utils/storage_r2.py` | Armazenamento privado; R2 opcional |
| `utils/turnstile.py` | Verificação anti-robô no servidor |

## Backoffice (`backoffice-desktop/`)

| Ficheiro | Responsabilidade | Porque importa |
|---|---|---|
| `electron/main.cjs` | Servidor local, proxy, injecção do portão, segurança da janela | O ficheiro mais instrutivo do projecto. |
| `electron/api-origin.cjs` | Origem embutida na construção | Uma linha: `https://api.diomika.com`. |
| `electron/desktop-gate.cjs` | O portão | **Gerado na construção. Ignorado pelo Git.** |
| `scripts/write-gate.cjs` | Escreve o portão a partir do ambiente ou do `.env` | Falha a construção se faltar ou for curto. |
| `src/lib/settings.js` | Sessão e endereço base forçado a `/api` | Impede apontar para outro servidor. |
| `src/lib/api.js` | Cliente HTTP com prazo e tradução de erros | Todos os endpoints num lugar. |
| `src/views/LoginView.vue` | Login com os dois desvios de MFA | |
| `package.json` | Construção para três sistemas operativos | Onde a não assinatura está declarada. |

## Loja (`frontend-web/`)

| Ficheiro | Responsabilidade |
|---|---|
| `src/components/CookieBanner.vue` | Consentimento e carregamento dinâmico do PostHog |
| `functions/_middleware.js` | Bloqueio de sondagens na fronteira do Pages |
| `public/_headers` | Cabeçalhos de segurança no Pages |
| `src/lib/catalogSupabase.js` | Catálogo público com chave anónima e RLS |
| `src/composables/useTurnstile.js` | Desafio anti-robô no cliente |
| `e2e/critical.spec.js` | Quatro testes de fumo contra produção |

## Operações (`deploy/`)

| Ficheiro | Responsabilidade |
|---|---|
| `deploy_vm.py` | Publicar a API: swap, Docker, tar, SCP, `.env`, túnel, compose, verificação |
| `deploy_beta.py` | Construir e publicar a loja no Pages |
| `docker-compose.free.yml` | Redis, API e cloudflared, todos ligados a loopback |
| `verify_production.py` | Comando único: uptime, fumo, segurança, carga, ponta a ponta |
| `verify_bundle_secrets.py` | Analisa a construção da loja à procura de segredos |
| `uptime_check.py` | Verificação de saúde e prontidão |
| `load_test.py` | Percentis 50 e 95, falha acima de 5% de erro |
| `cloudflare/waf_rules.json` | Modelo das regras de firewall |
| `env.free.example` | Modelo de produção com comentários operacionais |
| `OPS.md` / `FREE_STACK.md` / `SCALE.md` / `APRESENTACAO_CLIENTE.md` | Manuais e decisões |

## Automação (`.github/`)

| Ficheiro | Responsabilidade |
|---|---|
| `workflows/ci.yml` | Portão de segurança e testes: pip-audit, gitleaks, pytest, construção, Playwright |
| `workflows/backoffice-release.yml` | Matriz de três sistemas operativos com o segredo do portão |
| `workflows/uptime.yml` | Verificação secundária a cada 15 minutos |
| `dependabot.yml` | Actualizações de dependências |

## Configuração na raiz

| Ficheiro | Responsabilidade |
|---|---|
| `.gitignore` | O que nunca entra no Git: `.env`, portão, `cliente-backoffice/`, `release/`, utilizadores |
| `.env.example` | Modelo de desenvolvimento |
| `.pre-commit-config.yaml` | gitleaks e verificação da construção antes de cada commit |
| `.gitleaks.toml` | Configuração da procura de credenciais |
| `pytest.ini` | Caminho e localização dos testes |
| `requirements.txt` | Dependências Python |

---

# Apêndice C — Perguntas frequentes

**1. Onde está o sítio da Diomika, exactamente?**

Em dois lugares diferentes que trabalham juntos. A parte visível — as páginas que um visitante vê — está no Cloudflare Pages, uma rede de servidores espalhada pelo mundo que entrega ficheiros a partir do nó mais próximo de quem pede. Acede-se em `https://www.diomika.com`. A parte que pensa — a que grava mensagens, gera orçamentos, envia correio electrónico — corre numa máquina virtual na Google Cloud Platform e responde em `https://api.diomika.com`. São sistemas separados, com propriedades diferentes: um serve ficheiros estáticos e nunca precisa de mudar; o outro tem estado e lógica.

**2. Se o servidor não tem portas abertas, como é que os pedidos chegam lá?**

Esta é a pergunta certa a fazer, e a resposta é uma inversão. Normalmente, um servidor abre uma porta e espera que o mundo se ligue. Aqui, um programa na máquina — o `cloudflared` — liga-se **para fora**, para a rede Cloudflare, e mantém essa ligação aberta permanentemente. Quando um pedido chega ao Cloudflare para `api.diomika.com`, ele desce por essa ligação já estabelecida. A analogia é um túnel escavado de dentro para fora: a máquina não tem uma porta que se possa arrombar, tem uma ligação que ela própria iniciou. Um atacante que analise o endereço IP da máquina não encontra serviço nenhum a responder.

**3. Porque é que o administrador tem de instalar um programa em vez de usar o browser?**

Por causa de uma propriedade que só um programa instalado tem: pode guardar um segredo que o código de uma página web não pode. Toda a página web entrega o seu código ao browser do visitante — qualquer segredo lá dentro é legível por quem souber abrir as ferramentas de desenvolvimento. Um programa instalado pode manter o segredo na sua parte interna, fora do alcance da interface. Esse segredo é o que permite a regra na firewall do Cloudflare que bloqueia `/admin` para **todos os browsers do mundo** e deixa passar apenas a aplicação oficial. Com um painel web, essa regra seria impossível, porque o cliente legítimo seria também um browser.

**4. O que é exactamente o "portão desktop"?**

É uma palavra-passe secreta que a aplicação de administração envia em todos os pedidos, num campo especial do pedido HTTP chamado `X-Diomika-Desktop`. O servidor e a firewall sabem qual é o valor esperado; se não coincidir, o pedido é recusado. É importante entender o que ele **não** é: não é a autenticação da pessoa. Responde à pergunta "que programa é este?", não "quem é esta pessoa?". A identidade é estabelecida a seguir, pelo login com nome de utilizador e password.

**5. Se alguém roubar o executável, tem acesso a tudo?**

Não. Tem o **canal** — consegue fazer pedidos que a firewall não bloqueia. Continua a precisar de credenciais válidas. E cada tentativa falhada tem consequências: gera um alerta que chega ao telefone do responsável, conta para um bloqueio que trava a conta depois de cinco falhas, e alimenta um detector que grita quando vê oito falhas em dez minutos. Ainda assim, isto é uma limitação real e está registada como tal na Parte XI.1 — não é uma questão resolvida, é uma questão com mitigações.

**6. Porque é que a aplicação me avisa que é perigosa quando a abro?**

Porque não pagámos por um certificado de assinatura de código. O Windows e o macOS verificam se um programa novo foi assinado por uma entidade cuja identidade foi validada por uma autoridade certificadora. Não foi, e por isso o sistema avisa. Não significa que o programa seja malicioso — significa que o sistema não conseguiu verificar quem o fez. No Windows, clica-se em "Mais informações" e depois "Executar mesmo assim". No macOS, clica-se com o botão direito na aplicação e escolhe-se "Abrir" no menu, em vez de duplo clique. Só é preciso na primeira vez. A razão de não assinar é económica: os certificados custam algumas centenas de euros por ano, e o objectivo declarado do projecto é ter infra-estrutura recorrente de zero euros.

**7. O que é uma "variável de ambiente" e porque é que não estão simplesmente no código?**

É um valor que o sistema operativo entrega ao programa quando ele arranca. O programa sabe que precisa de um valor chamado `SUPABASE_KEY`, mas não sabe qual é — vai lê-lo de fora. Não estão no código por duas razões. A primeira é que mudam conforme o lugar: o endereço da base de dados no computador de desenvolvimento não é o mesmo que em produção, e não se quer manter duas versões do código. A segunda é mais grave: o sistema de controlo de versões guarda o histórico **para sempre**. Um segredo que entre no código continua acessível no histórico mesmo depois de ser apagado, e a única remediação real é considerar essa credencial comprometida e substituí-la em todos os sistemas.

**8. Se o `.env` não está no repositório, como é que alguém novo sabe o que preencher?**

Existe um ficheiro `.env.example` que **está** no repositório e tem exactamente os mesmos nomes de variáveis, com valores que são marcadores óbvios do género `your-service-role-key`. Copia-se, muda-se o nome para `.env`, e preenche-se com os valores reais. A lógica é que **os nomes não são secretos, só os valores são** — saber que existe uma variável chamada `SUPABASE_KEY` não dá acesso a nada. Há uma linha no `.gitignore` que faz precisamente esta distinção: `!.env.example`, onde o `!` significa "ignora tudo excepto este".

**9. Porque é que existem cinco ferramentas de monitorização em vez de uma?**

Porque respondem a perguntas diferentes e porque todas as cinco são gratuitas. O Sentry responde "o que se partiu e onde"; o Axiom responde "o que aconteceu antes e depois"; o PostHog responde "as pessoas conseguem usar isto"; o UptimeRobot responde "está de pé"; e o webhook de alertas responde "alguém precisa de saber disto agora". Uma plataforma comercial única faria as cinco coisas e correlacionaria automaticamente entre elas — por dezenas a centenas de euros por mês. A alternativa de alojar tudo na própria máquina tem um defeito fatal: se a máquina cai, os painéis caem com ela, e a informação sobre a queda desaparece exactamente quando é necessária.

**10. Um "log" é a mesma coisa que um "erro"?**

Não, e a distinção importa. Um erro é um momento em que o código rebentou. Um log é um registo cronológico de **tudo** o que aconteceu — a maioria das linhas descreve funcionamento perfeitamente normal. A relação entre os dois é de contexto: quando há um erro, os logs em volta contam a história de como se chegou lá. É por isso que existem duas ferramentas: o Sentry para agrupar e contar erros, o Axiom para pesquisar a narrativa completa. E há uma peça que as liga: cada pedido recebe um identificador único, que aparece nos dois lados, e permite passar de um erro no Sentry para as linhas exactas daquele pedido no Axiom.

**11. Porque é que o aviso de cookies só aparece às vezes?**

Porque só faz sentido perguntar quando há algo para consentir e quando não há resposta anterior. Se a pessoa já aceitou, não se volta a perguntar. Se já recusou, também não — insistir seria desrespeitoso, e muitos sítios fazem-no de propósito para cansar o visitante até ele ceder. E se a analítica não estiver configurada no sistema, não aparece aviso nenhum, porque não haveria recolha a autorizar. Pedir consentimento para algo que não vai acontecer é apenas atrito imposto sem razão.

**12. Se eu recusar os cookies, o que acontece realmente?**

O código da analítica **nunca é descarregado** para o browser. Não é apenas desactivado depois de carregado — o ficheiro não chega a ser pedido ao servidor. Isto consegue-se com uma técnica chamada importação dinâmica: a linha que carrega o PostHog só corre dentro da função que trata o botão "Aceitar". É verificável por qualquer pessoa: abre-se o separador de rede nas ferramentas do browser, recusa-se, e não existe pedido algum relacionado com analítica.

**13. O que é uma "feature flag" e para que serve na prática?**

É um interruptor que liga ou desliga uma parte do sistema sem alterar código. O exemplo concreto: se o formulário de contacto começar a ser abusado, ou se o serviço de correio electrónico do fornecedor estiver em baixo, muda-se `FEATURE_CONTACT_FORM=0` no ficheiro de configuração, reinicia-se, e em segundos o formulário passa a responder com uma mensagem educada de indisponibilidade em vez de falhar. Sem este mecanismo, a alternativa seria publicar uma versão nova do sistema no meio de uma crise — mais lento e mais arriscado.

**14. O que significa "scrypt" e porque é que interessa que seja lento?**

O scrypt é a forma como as passwords são transformadas antes de serem guardadas. É de sentido único: consegue-se verificar se uma password está certa, não se consegue recuperá-la. A parte contra-intuitiva é a lentidão deliberada. Se se usasse uma transformação rápida, um atacante que roubasse a base de dados poderia testar **milhares de milhões** de passwords por segundo numa placa gráfica, e esgotaria uma lista de mil milhões de passwords comuns em segundos. Sendo lento e exigente em memória, cada tentativa custa uma fracção de segundo — imperceptível para quem faz login uma vez, e a diferença entre segundos e séculos para quem tenta mil milhões.

**15. Porque é que a sessão do backoffice expira tão depressa?**

Quinze minutos no total, dez de inactividade. É curto de propósito, e a razão é o cenário mais provável de compromisso: um computador de escritório deixado desbloqueado. Uma sessão de oito horas significaria que qualquer pessoa que passasse pela secretária durante o dia teria acesso administrativo completo. Quinze minutos reduzem drasticamente essa janela. Existem também duas contas separadas: uma que expira independentemente do uso, e outra que expira se ninguém tocar na aplicação — a segunda é a que protege o computador abandonado.

**16. Se eu entrar noutro computador, o que acontece à minha sessão anterior?**

Morre imediatamente. Só existe uma sessão activa por utilizador, e emitir uma nova revoga a anterior. Isto é deliberado e tem um efeito de segurança útil: se alguém entrar com as suas credenciais noutro lugar, a sua sessão em uso cai, e a pessoa nota. É um detector de intrusão embutido no próprio modelo de sessão, em vez de um sistema de vigilância separado.

**17. Porque é que a mensagem de erro do login é sempre igual, mesmo quando o utilizador não existe?**

Para não confirmar informação a quem está a tentar entrar. Se a resposta fosse "utilizador não existe" para uns nomes e "password errada" para outros, um atacante saberia quais as contas que existem e concentraria o esforço nelas. Se dissesse "conta bloqueada", confirmaria que aquela conta existe e que o ataque está a ter efeito suficiente para disparar o bloqueio. Uma única mensagem para todos os casos não revela nada. Há até um teste automático dedicado a garantir que ninguém, com boa intenção de "tornar o erro mais útil", reabre esta brecha.

**18. Porque é que as imagens do catálogo têm endereços estranhos que deixam de funcionar?**

Porque o armazenamento é privado e os endereços são temporários. Cada endereço contém uma assinatura criptográfica e um prazo, tipicamente uma hora. Isto impede que alguém descubra um endereço, o partilhe, e ele funcione indefinidamente — e impede que se percorra o catálogo inteiro adivinhando endereços, incluindo produtos ainda não publicados. Num catálogo entre empresas, as imagens de produtos podem revelar informação comercial, e um endereço permanente é indexável por motores de busca. O efeito lateral é o que descreve: um endereço guardado deixa de funcionar mais tarde.

**19. O que é a "firewall de aplicação web" e o que faz aqui?**

É um filtro que corre na rede do Cloudflare, **antes** de o pedido chegar ao nosso servidor. Tem duas regras relevantes. A primeira bloqueia pedidos que não se identificam — a maioria dos programas automáticos maliciosos não envia identificação. A segunda é a mais importante: bloqueia qualquer pedido para `/admin` ou `/system` que não traga o segredo do backoffice. O efeito prático merece ser apreciado: um varrimento automatizado à procura de painéis de administração — que é uma constante na internet — bate numa parede a centenas de quilómetros da nossa máquina, que nem gasta um ciclo de processador a tratá-lo.

**20. Como é que se publica uma alteração?**

Depende do que mudou. Para a API: `python deploy/deploy_vm.py`, que envia o código, actualiza a configuração e reinicia os contentores. Para a loja: `python deploy/deploy_beta.py --pages-deploy --api-url https://api.diomika.com`, que constrói e publica. Para o backoffice: criar uma etiqueta no repositório com o formato `backoffice-v...`, e a automação do GitHub produz os três instaladores em paralelo. Depois de qualquer um destes, `python deploy/verify_production.py` confirma que o sistema está saudável.

**21. O que é "integração contínua" e porque é que interessa?**

É a prática de correr automaticamente um conjunto de verificações a cada alteração de código, sem depender de alguém se lembrar. Na Diomika verifica: se alguma dependência tem vulnerabilidade conhecida (Python e JavaScript); se há credenciais expostas em qualquer parte do repositório, incluindo o histórico; se todos os testes passam; se a loja constrói sem segredos de servidor no resultado; e se o sistema em produção responde correctamente. A razão de existir é simples: as verificações que dependem de memória humana falham exactamente nos dias em que há pressa, que são os dias em que mais importam.

**22. Porque é que existem verificações antes de cada commit **e** depois?**

Porque o momento em que um problema é detectado muda a natureza da resposta. As verificações antes do commit correm no computador e, se falharem, o commit não acontece — nada saiu da máquina. As verificações no servidor correm depois do envio, quando o commit já existe no histórico remoto. Para segredos, esta diferença é qualitativa: um segredo que entra no histórico remoto tem de ser considerado comprometido e substituído em todos os sistemas, mesmo que se apague a linha depois. Travar antes evita todo esse trabalho. Existem as duas camadas porque a primeira é cooperativa (pode ser saltada) e a segunda não pode.

**23. Porque é que os testes correm contra o sistema em produção real?**

Porque uma cópia local nunca é igual. Os quatro testes de fumo confirmam que a API responde, que a loja carrega, que a página de privacidade existe, e — o mais interessante — que um pedido sem o segredo do backoffice **não** consegue chegar ao endereço administrativo. Este último é uma verificação contínua de que a porta continua fechada. Um erro de configuração na firewall ou no servidor seria detectado na integração seguinte, em vez de ficar a descoberto até alguém reparar.

**24. Quanto custa manter isto a funcionar?**

Zero euros por mês de infra-estrutura recorrente. O único custo é o domínio `diomika.com`, uma vez por ano. Todos os serviços estão em planos gratuitos: Cloudflare para rede, TLS, firewall e alojamento da loja; Google Cloud para a máquina virtual, na categoria permanentemente gratuita; Supabase para base de dados e armazenamento; Sentry, Axiom, PostHog, UptimeRobot e ntfy para monitorização; GitHub Actions para automação. A restrição de custo, curiosamente, melhorou a arquitectura em vários pontos — está desenvolvido na Parte X.9.

**25. O que acontece se um destes serviços gratuitos desaparecer ou passar a ser pago?**

Depende de qual. Para as cinco ferramentas de monitorização, o impacto é limitado por desenho: cada uma está ligada a uma variável de ambiente e, se essa variável desaparecer, a integração desliga-se sozinha e o sistema continua a funcionar exactamente igual, apenas mais cego. Nenhum dado de negócio vive num serviço de observabilidade — a fonte de verdade é a base de dados. Para o Cloudflare ou o Supabase, o impacto seria estrutural e exigiria migração planeada. `deploy/SCALE.md` prescreve, como primeiro sinal de alerta, um limite de orçamento na Google Cloud entre 1 e 5 dólares — para detectar crescimento de custo antes de ele surpreender.

**26. O sistema aguenta muito tráfego?**

Tem um tecto conhecido e reconhecido. A máquina virtual é da categoria mais pequena disponível, e partilha recursos entre a API, o Redis e os trabalhadores de fundo. Há várias medidas para esticar essa capacidade: um ficheiro de troca de 2 gigabytes para a memória não esgotar durante construções, cache nas contagens mais caras, prazos curtos em todas as chamadas externas, envio de logs em lote, Redis sem escrita em disco, e um alerta que avisa quando um pedido demora mais de 2 segundos. Existe também um programa (`load_test.py`) que mede a latência sob carga e falha se mais de 5% dos pedidos falharem — para se saber o número antes de haver um problema. O caminho de crescimento está escrito em `deploy/SCALE.md`.

**27. Onde estão as passwords guardadas?**

Num ficheiro chamado `admin_users.json`, na máquina virtual, com permissões restritas a 600 (só o proprietário lê e escreve) e uma cópia de segurança rotativa antes de cada escrita. O ficheiro está na lista de exclusões do controlo de versões e nunca entra no repositório. E não contém passwords: contém o resultado da transformação scrypt, com um sal aleatório diferente por utilizador. Mesmo com o ficheiro em mãos, recuperar as passwords originais exigiria testar candidatos um a um, a uma fracção de segundo cada.

**28. Porque é que a autenticação não usa o Supabase Auth, se a base de dados é Supabase?**

Porque os utilizadores administrativos são poucos, conhecidos, e não se registam sozinhos. O Supabase Auth resolve problemas que aqui não existem: registo público, confirmação por correio electrónico, recuperação de password, autenticação através de terceiros, gestão de sessões em browsers. Nada disso é necessário para duas ou três contas geridas manualmente. Um ficheiro local com scrypt e sessões próprias é menos código, menos dependências, e mantém o controlo administrativo independente do fornecedor de base de dados — o que significa que uma alteração de política do Supabase não afecta o acesso ao backoffice.

**29. O que é o "modo de bloqueio" (`SECURITY_LOCKDOWN`)?**

É um interruptor de emergência. Quando activo, todas as operações administrativas e todos os formulários públicos passam a responder com indisponibilidade temporária, e apenas as verificações de saúde continuam a funcionar. Serve para conter um incidente em curso — suspeita de compromisso, abuso em escala, um defeito a corromper dados — sem desligar o sistema por completo. Manter as verificações de saúde a funcionar é deliberado: durante um incidente, perder a visibilidade é a última coisa que se quer.

**30. Como é que sei que o sistema está a funcionar bem, agora?**

Três formas, de diferentes profundidades. A mais rápida: abrir `https://api.diomika.com/health` num browser e ver `{"status": "online", ...}`. A mais completa: correr `python deploy/verify_production.py`, que testa disponibilidade, prontidão, funcionalidade, segurança, carga e os fluxos ponta a ponta, num comando. E a passiva: se algo estiver mal, o UptimeRobot envia um correio electrónico em até 5 minutos, e os alertas do sistema chegam por notificação — o que significa que a ausência de notícias é, ela própria, uma informação.

**31. Se eu quiser entender o código, por onde começo?**

A Parte XII tem uma ordem de leitura em oito níveis, mas o resumo é: começar pelos documentos (`README.md` e `deploy/APRESENTACAO_CLIENTE.md`), depois `backend-api/main.py`, que é o índice de toda a API, e depois os ficheiros de segurança pela ordem indicada — `local_only.py`, `path_guard.py`, `middleware.py`, `auth.py`. Duas notas úteis: os ficheiros mais curtos são os mais importantes (`local_only.py` tem 55 linhas e é o pilar de todo o modelo de acesso), e vale a pena ler os comentários, porque vários documentam avarias reais e a razão de decisões que parecem estranhas à primeira vista.
