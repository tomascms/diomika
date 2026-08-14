# Base de dados comercial — Diomika

Modelo de dados de **negócio** (catálogo + pedidos + contacto).  
Não inclui tabelas puramente técnicas (`outbox_events`, `saga_instances`, `idempotency_keys`) — essas são infraestrutura de fiabilidade da API.

Fonte de verdade no código: `backend-api/models/schemas.py` (`CATALOG_TYPES` + `TABLE_MAP`).

---

## Diagrama (entidade–relação)

```mermaid
erDiagram
    categories ||--o{ modelos_almofadas : "tem modelos"
    categories ||--o{ modelos_assentos : "tem modelos"
    categories ||--o{ almofada : "agrupa variantes"
    categories ||--o{ assento : "agrupa produtos"

    modelos_almofadas ||--o{ modelo_cores : "cores directas"
    modelos_almofadas ||--o{ almofada : "tamanhos/EAN"

    paletas_cores ||--o{ modelo_cores : "cores partilhadas"
    paletas_cores ||--o{ modelos_assentos : "paleta opcional"

    modelos_assentos ||--o{ assento : "um EAN por modelo"

    pedidos_orcamento ||--|{ pedido_linhas : "linhas JSON"
    encomendas_internas ||--|{ encomenda_linhas : "linhas JSON"

    categories {
        uuid id PK
        string nome
        string slug
        string tipo_catalogo
        string imagem
        bool visibilidade
        int carrinho_step
        int carrinho_min
    }

    modelos_almofadas {
        uuid id PK
        uuid id_categoria FK
        string nome
        string slug
        string descricao
        string tipo
        json composicao
        bool visibilidade
    }

    modelo_cores {
        uuid id PK
        uuid id_modelo FK
        uuid id_paleta FK
        int numero
        string nome
        string imagem
        bool visibilidade
    }

    almofada {
        uuid id PK
        uuid id_categoria FK
        uuid id_modelo FK
        string ean
        string dimensoes
        string barcode_url
        bool visibilidade
    }

    paletas_cores {
        uuid id PK
        string nome
        bool visibilidade
    }

    modelos_assentos {
        uuid id PK
        uuid id_categoria FK
        uuid id_paleta FK
        string nome
        string slug
        string material_forro
        string material_enchimento
        json alturas
        bool visibilidade
    }

    assento {
        uuid id PK
        uuid id_categoria FK
        uuid id_modelo FK
        string ean
        string barcode_url
        bool visibilidade
    }

    pedidos_orcamento {
        uuid id PK
        string nome
        string email
        string empresa
        json linhas
        string status
        bool lida
    }

    encomendas_internas {
        uuid id PK
        string referencia_cliente
        json linhas
        bool visibilidade
    }

    contact_messages {
        uuid id PK
        string nome
        string email
        string assunto
        string mensagem
        bool lida
        string status
    }
```

> Nota: `pedido_linhas` / `encomenda_linhas` no diagrama representam o conteúdo do campo JSON `linhas` (EAN + número de cor + quantidade [+ altura]), não tabelas físicas separadas.

---

## Leitura comercial (como se vende)

1. **Categoria** (`categories`) — “Almofadas” ou “Assentos”; define tipo de catálogo e regras de quantidade no carrinho (ex.: múltiplos de 6 ou 12).
2. **Modelo** — família de produto (`modelos_almofadas` / `modelos_assentos`): nome, descrição, composição ou materiais.
3. **Cor** (`modelo_cores`) — ou ligada a um modelo, ou a uma **paleta** partilhada (`paletas_cores`), útil nos assentos.
4. **Produto / variante** — `almofada` = tamanho + EAN-13; `assento` = um EAN por modelo (cor/altura escolhidas na encomenda).
5. **Pedido de orçamento** — o cliente pede preço (sem preços públicos); linhas referenciam EAN + cor (+ altura).
6. **Encomenda interna** — fluxo operacional interno com referência de cliente.
7. **Contacto** — mensagens do formulário da loja.

Regra de negócio visível na loja: mínimo de encomenda **500€ + IVA** (texto em `MIN_ORCAMENTO_TEXTO`); preços sob consulta.

---

## Famílias de catálogo

| tipo_catalogo | Tabela modelo | Tabela produto | Notas |
|---------------|---------------|----------------|-------|
| `almofada` | `modelos_almofadas` | `almofada` | Variantes por dimensões; cores em `modelo_cores` |
| `assento` | `modelos_assentos` | `assento` | Alturas no modelo; cores via paleta |

Para acrescentar uma família nova (ex.: mantas): editar só `backend-api/models/schemas.py` (`CATALOG_TYPES` + classes + `CATEGORY_DEFINITIONS`).
