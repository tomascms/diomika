"""
Modelos de dados Diomika — FONTE DE VERDADE do catálogo.

Para adicionar um tipo de produto novo (ex.: mantas), edita SÓ este ficheiro:
  1. Classes Pydantic (ModeloX + ProdutoX)
  2. Entrada em CATALOG_TYPES dentro de _register_catalog_types()
  3. Entrada em CATEGORY_DEFINITIONS

Depois: reiniciar API (sync automático) + criar categoria no backoffice.

TABLE_MAP, sidebar, loja e validações são gerados automaticamente.
"""
from pydantic import BaseModel, Field, field_validator, model_validator
from typing import List, Optional, Dict, Literal
from uuid import UUID, uuid4
import re

TIPO_ALMOFADA = Literal["decorativa", "dormir"]
TIPO_ALMOFADA_LABELS = {"decorativa": "decorativa", "dormir": "dormir"}

TIPO_CATALOGO = str  # valores válidos = chaves de CATALOG_TYPES (validado em Categoria)

CATEGORY_DEFINITIONS = {
    "almofadas": {
        "nome": "Almofadas",
        "tipo_catalogo": "almofada",
        "carrinho_step": 6,
        "carrinho_min": 6,
    },
    "assentos": {
        "nome": "Assentos",
        "tipo_catalogo": "assento",
        "carrinho_step": 12,
        "carrinho_min": 12,
    },
}


def category_definition_for_slug(slug: str | None) -> dict | None:
    if not slug:
        return None
    return CATEGORY_DEFINITIONS.get(slug)


MIN_ORCAMENTO_TEXTO = "Mínimo de encomenda: 500€ + IVA (sem preços no site — orçamento sob consulta)."


def generate_slug(text: str) -> str:
    return re.sub(r"[-\s]+", "-", re.sub(r"[^\w\s-]", "", text.lower().strip()))


class Categoria(BaseModel):
    id: UUID = Field(default_factory=uuid4, json_schema_extra={"ui_hidden": True})
    tipo_catalogo: Optional[TIPO_CATALOGO] = Field(
        default=None,
        description="Tipo de catálogo (obrigatório — define modelos e produtos)",
        json_schema_extra={
            "ui_hidden": True,
        },
    )
    nome: str = Field(..., min_length=2)
    slug: str = Field(default="", json_schema_extra={"ui_readonly": True})
    imagem: str = Field(..., description="URL da imagem")
    visibilidade: bool = Field(default=True)
    carrinho_step: Optional[int] = Field(
        default=None,
        description="Passo quantidade (ex: 6 ou 12). Predefinido pelo tipo.",
    )
    carrinho_min: Optional[int] = Field(
        default=None,
        description="Quantidade mínima por linha no carrinho",
    )

    @model_validator(mode="after")
    def set_slug_and_cart_rules(self) -> "Categoria":
        if not self.slug:
            self.slug = generate_slug(self.nome)

        definition = category_definition_for_slug(self.slug)
        if definition:
            inferred_tipo = definition["tipo_catalogo"]
            if self.tipo_catalogo and self.tipo_catalogo != inferred_tipo:
                raise ValueError("Tipo de catálogo inválido para esta categoria.")
            self.tipo_catalogo = inferred_tipo
            if self.carrinho_step is None:
                self.carrinho_step = int(definition.get("carrinho_step") or 6)
            if self.carrinho_min is None:
                self.carrinho_min = int(definition.get("carrinho_min") or self.carrinho_step)
        else:
            if self.tipo_catalogo is None:
                self.tipo_catalogo = next(iter(CATALOG_TYPES.keys()), "almofada")
            elif self.tipo_catalogo not in CATALOG_TYPES:
                raise ValueError(f"tipo_catalogo «{self.tipo_catalogo}» não está registado em CATALOG_TYPES.")
            if self.carrinho_step is None:
                self.carrinho_step = 6
            if self.carrinho_min is None:
                self.carrinho_min = self.carrinho_step
        return self


class ModeloAlmofada(BaseModel):
    id: UUID = Field(default_factory=uuid4, json_schema_extra={"ui_hidden": True})
    id_categoria: UUID = Field(..., description="Categoria", json_schema_extra={"ui_relation": "categories"})
    nome: str = Field(..., description="Nome do Modelo")
    slug: str = Field(default="", json_schema_extra={"ui_readonly": True})
    descricao: str = Field(..., description="Descrição")
    tipo: TIPO_ALMOFADA = Field(
        ...,
        description="Tipo de Almofada",
        json_schema_extra={
            "ui_widget": "enum",
            "ui_options": ["decorativa", "dormir"],
            "ui_labels": TIPO_ALMOFADA_LABELS,
        },
    )
    composicao: Dict[str, int] = Field(
        ...,
        description="Composição (%) — igual para todas as cores",
        json_schema_extra={"ui_widget": "composition"},
    )
    visibilidade: bool = Field(default=True)

    @model_validator(mode="after")
    def set_slug(self) -> "ModeloAlmofada":
        if not self.slug:
            self.slug = generate_slug(self.nome)
        return self

    @field_validator("composicao")
    @classmethod
    def validate_composicao(cls, v: Dict[str, int]) -> Dict[str, int]:
        if sum(v.values()) != 100:
            raise ValueError(f"Soma da composição deve ser 100% (Atual: {sum(v.values())}%)")
        return v


class ModeloCor(BaseModel):
    """Cor de um modelo (almofada ou assento). Sem paletas partilhadas."""
    id: UUID = Field(default_factory=uuid4, json_schema_extra={"ui_hidden": True})
    id_modelo: UUID = Field(
        ...,
        description="Modelo dono (almofada ou assento)",
        json_schema_extra={"ui_relation": "modelos_almofadas"},
    )
    numero: int = Field(..., ge=1, description="Número da cor")
    nome: str = Field(default="", description="Nome da cor (opcional)")
    imagem: str = Field(..., description="URL da imagem desta cor")
    visibilidade: bool = Field(default=True)


class Almofada(BaseModel):
    """Variante por tamanho/EAN — cor fica em modelo_cores. Categoria via modelo."""
    id: UUID = Field(default_factory=uuid4, json_schema_extra={"ui_hidden": True})
    id_modelo: UUID = Field(..., description="Modelo", json_schema_extra={"ui_relation": "modelos_almofadas"})
    ean: str = Field(..., pattern=r"^\d{13}$", description="EAN-13")
    barcode_url: Optional[str] = Field(None, json_schema_extra={"ui_readonly": True})
    dimensoes: str = Field(..., pattern=r"^\d+x\d+$", description="Medidas (LxA cm)")
    visibilidade: bool = Field(default=True)

    @field_validator("ean")
    @classmethod
    def validate_ean(cls, v: str) -> str:
        digits = [int(d) for d in v]
        check = (10 - (sum(d * (3 if i % 2 else 1) for i, d in enumerate(digits[:-1])) % 10)) % 10
        if digits[-1] != check:
            raise ValueError(f"EAN inválido. Check-digit esperado: {check}")
        return v


class PedidoOrcamentoLinha(BaseModel):
    ean: str = Field(..., pattern=r"^\d{13}$")
    numero_cor: int = Field(..., ge=1)
    quantidade: int = Field(..., ge=1)
    altura: Optional[str] = Field(None, max_length=32, description="Altura (assentos, ex: 32mm)")


class PedidoOrcamento(BaseModel):
    id: UUID = Field(default_factory=uuid4, json_schema_extra={"ui_hidden": True})
    nome: str = Field(..., json_schema_extra={"ui_readonly": True})
    email: str = Field(..., json_schema_extra={"ui_readonly": True})
    contacto: Optional[str] = Field(None, json_schema_extra={"ui_readonly": True})
    empresa: Optional[str] = Field(None, json_schema_extra={"ui_readonly": True})
    observacoes: Optional[str] = Field(None, json_schema_extra={"ui_readonly": True})
    linhas: List[Dict] = Field(default_factory=list, json_schema_extra={"ui_hidden": True})
    lida: bool = Field(default=False)
    visibilidade: bool = Field(default=True)
    status: str = Field(default="Nova", json_schema_extra={"ui_readonly": True})


class EncomendaInternaLinha(BaseModel):
    ean: str = Field(..., pattern=r"^\d{13}$")
    numero_cor: int = Field(..., ge=1)
    quantidade: int = Field(..., ge=1)
    altura: Optional[str] = Field(None, max_length=32)


class EncomendaInterna(BaseModel):
    id: UUID = Field(default_factory=uuid4, json_schema_extra={"ui_hidden": True})
    referencia_cliente: str = Field(..., description="Cliente")
    observacoes: Optional[str] = Field(None, json_schema_extra={"ui_hidden": True})
    linhas: List[Dict] = Field(default_factory=list, json_schema_extra={"ui_hidden": True})
    visibilidade: bool = Field(default=True)


class ContactMessage(BaseModel):
    id: UUID = Field(default_factory=uuid4, json_schema_extra={"ui_hidden": True})
    nome: str = Field(..., json_schema_extra={"ui_readonly": True})
    email: str = Field(..., json_schema_extra={"ui_readonly": True})
    contacto: Optional[str] = Field(None, json_schema_extra={"ui_readonly": True})
    assunto: str = Field(..., json_schema_extra={"ui_readonly": True})
    mensagem: str = Field(..., json_schema_extra={"ui_readonly": True})
    lida: bool = Field(default=False)
    visibilidade: bool = Field(default=True)
    status: Optional[str] = Field(None, json_schema_extra={"ui_readonly": True})
    last_sender: Optional[str] = Field(None, json_schema_extra={"ui_hidden": True})


class IdempotencyKey(BaseModel):
    key: str = Field(..., json_schema_extra={"ui_hidden": True})
    operation: str = Field(...)
    response: Dict = Field(default_factory=dict)
    expires_at: Optional[str] = Field(None, json_schema_extra={"ui_hidden": True})


class OutboxEvent(BaseModel):
    id: UUID = Field(default_factory=uuid4, json_schema_extra={"ui_hidden": True})
    event_type: str = Field(...)
    payload: Dict = Field(default_factory=dict)
    status: str = Field(default="pending")
    attempts: int = Field(default=0)
    max_attempts: int = Field(default=5)
    next_retry_at: Optional[str] = None
    last_error: Optional[str] = None


class SagaInstance(BaseModel):
    id: UUID = Field(default_factory=uuid4, json_schema_extra={"ui_hidden": True})
    saga_type: str = Field(...)
    status: str = Field(default="running")
    current_step: Optional[str] = None
    context: Dict = Field(default_factory=dict)


class ModeloAssento(BaseModel):
    id: UUID = Field(default_factory=uuid4, json_schema_extra={"ui_hidden": True})
    id_categoria: UUID = Field(..., description="Categoria", json_schema_extra={"ui_relation": "categories"})
    nome: str = Field(..., description="Nome do modelo")
    slug: str = Field(default="", json_schema_extra={"ui_readonly": True})
    descricao: str = Field(default="", description="Descrição")
    material_forro: str = Field(..., description="Material do forro")
    material_enchimento: str = Field(..., description="Material do enchimento")
    alturas: List[str] = Field(
        ...,
        min_length=1,
        description="Alturas disponíveis (ex: 32mm, 45mm)",
        json_schema_extra={"ui_widget": "string_list", "ui_label": "Alturas"},
    )
    visibilidade: bool = Field(default=True)

    @model_validator(mode="after")
    def set_slug(self) -> "ModeloAssento":
        if not self.slug:
            self.slug = generate_slug(self.nome)
        return self

    @field_validator("alturas")
    @classmethod
    def validate_alturas(cls, v: List[str]) -> List[str]:
        cleaned = [a.strip() for a in v if a and str(a).strip()]
        if not cleaned:
            raise ValueError("Indique pelo menos uma altura.")
        return cleaned


class Assento(BaseModel):
    """Um EAN/código de barras por modelo — cor e altura escolhidas no pedido. Categoria via modelo."""
    id: UUID = Field(default_factory=uuid4, json_schema_extra={"ui_hidden": True})
    id_modelo: UUID = Field(..., description="Modelo", json_schema_extra={"ui_relation": "modelos_assentos"})
    ean: str = Field(..., pattern=r"^\d{13}$", description="EAN-13")
    barcode_url: Optional[str] = Field(None, json_schema_extra={"ui_readonly": True})
    visibilidade: bool = Field(default=True)

    @field_validator("ean")
    @classmethod
    def validate_ean(cls, v: str) -> str:
        digits = [int(d) for d in v]
        check = (10 - (sum(d * (3 if i % 2 else 1) for i, d in enumerate(digits[:-1])) % 10)) % 10
        if digits[-1] != check:
            raise ValueError(f"EAN inválido. Check-digit esperado: {check}")
        return v


# --- Registo de tipos de catálogo (modelo + produto por família) ---
# Único sítio onde defines a estrutura de um tipo novo.

CATALOG_TYPES: dict = {}


def _register_catalog_types() -> None:
    global CATALOG_TYPES
    CATALOG_TYPES.clear()
    CATALOG_TYPES.update(
        {
            "almofada": {
                "label": "Almofadas",
                "model_table": "modelos_almofadas",
                "product_table": "almofada",
                "model_schema": ModeloAlmofada,
                "product_schema": Almofada,
                "model_discriminator_field": None,
                "product_readonly_on_edit": False,
                "apply_barcode_on_save": True,
                "storefront_mode": "variantes",
            },
            "assento": {
                "label": "Assentos",
                "model_table": "modelos_assentos",
                "product_table": "assento",
                "model_schema": ModeloAssento,
                "product_schema": Assento,
                "model_discriminator_field": "alturas",
                "product_readonly_on_edit": True,
                "apply_barcode_on_save": True,
                "storefront_mode": "assento",
            },
        }
    )


_register_catalog_types()

TIPO_CATALOGO_LABELS = {k: v["label"] for k, v in CATALOG_TYPES.items()}


def _rebuild_table_map() -> None:
    from models.table_map_builder import merge_table_map, build_operations_table_map

    global TABLE_MAP
    ops = build_operations_table_map(
        categoria_schema=Categoria,
        modelo_cor_schema=ModeloCor,
        pedido_schema=PedidoOrcamento,
        encomenda_schema=EncomendaInterna,
        contact_schema=ContactMessage,
        infra_schemas={
            "idempotency_keys": IdempotencyKey,
            "outbox_events": OutboxEvent,
            "saga_instances": SagaInstance,
        },
    )
    TABLE_MAP.clear()
    TABLE_MAP.update(merge_table_map(CATALOG_TYPES, ops))


TABLE_MAP: dict = {}
_rebuild_table_map()


def sidebar_tables() -> dict:
    """Sidebar: Categorias, Modelos, Produtos + operações."""
    from models.catalog_views import sidebar_entries

    return sidebar_entries()
