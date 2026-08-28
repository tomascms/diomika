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
TIPO_ALMOFADA_LABELS = {"decorativa": "Decorativa", "dormir": "Dormir"}

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
    "guarda-chuvas": {
        "nome": "Guarda-chuvas",
        "tipo_catalogo": "guarda_chuva",
        "carrinho_step": 6,
        "carrinho_min": 6,
    },
    "oculos": {
        "nome": "Óculos",
        "tipo_catalogo": "oculo",
        "carrinho_step": 6,
        "carrinho_min": 6,
    },
    "toalhas-mesa": {
        "nome": "Toalhas de mesa",
        "tipo_catalogo": "toalha_mesa",
        "carrinho_step": 6,
        "carrinho_min": 6,
    },
    "material-cozinha": {
        "nome": "Material de cozinha",
        "tipo_catalogo": "material_cozinha",
        "aggregated_tipos": ["avental", "luva", "pega", "pano_cozinha"],
        "carrinho_step": 6,
        "carrinho_min": 6,
    },
    "regional": {
        "nome": "Regional",
        "tipo_catalogo": "regional",
        "carrinho_step": 6,
        "carrinho_min": 6,
    },
}


def category_definition_for_slug(slug: str | None) -> dict | None:
    if not slug:
        return None
    return CATEGORY_DEFINITIONS.get(slug)


def aggregated_tipos_for_tipo(tipo: str | None) -> list[str] | None:
    if not tipo:
        return None
    for definition in CATEGORY_DEFINITIONS.values():
        if definition.get("tipo_catalogo") == tipo and definition.get("aggregated_tipos"):
            return list(definition["aggregated_tipos"])
    return None


def is_registered_tipo(tipo: str | None) -> bool:
    if not tipo:
        return False
    if tipo in CATALOG_TYPES:
        return True
    return aggregated_tipos_for_tipo(tipo) is not None


def _validate_composicao_pct(v: Dict[str, int]) -> Dict[str, int]:
    if sum(v.values()) != 100:
        raise ValueError(f"Soma da composição deve ser 100% (Atual: {sum(v.values())}%)")
    return v


def _validate_string_list(v: List[str], label: str = "valores") -> List[str]:
    cleaned = [str(a).strip() for a in v if a and str(a).strip()]
    if not cleaned:
        raise ValueError(f"Indique pelo menos um(a) {label}.")
    return cleaned


def _validate_ean(v: str) -> str:
    digits = [int(d) for d in v]
    check = (10 - (sum(d * (3 if i % 2 else 1) for i, d in enumerate(digits[:-1])) % 10)) % 10
    if digits[-1] != check:
        raise ValueError(f"EAN inválido. Check-digit esperado: {check}")
    return v


def _composicao_field(*, required: bool = True):
    meta = {"ui_widget": "composition"}
    desc = "Composição (%) — igual para todas as cores"
    if required:
        return Field(..., description=desc, json_schema_extra=meta)
    return Field(default=None, description=desc, json_schema_extra=meta)


class ModeloCorBase(BaseModel):
    id: UUID = Field(default_factory=uuid4, json_schema_extra={"ui_hidden": True})
    id_modelo: UUID = Field(..., json_schema_extra={"ui_hidden": True})
    numero: int = Field(..., ge=1)
    nome: str = Field(default="")
    imagem: str = Field(...)
    visibilidade: bool = Field(default=False)


class ModeloBase(BaseModel):
    id: UUID = Field(default_factory=uuid4, json_schema_extra={"ui_hidden": True})
    id_categoria: UUID = Field(..., json_schema_extra={"ui_relation": "categories"})
    nome: str = Field(...)
    slug: str = Field(default="", json_schema_extra={"ui_readonly": True})
    descricao: str = Field(default="")
    visibilidade: bool = Field(default=False)

    @model_validator(mode="after")
    def _set_slug(self):
        if not self.slug:
            self.slug = generate_slug(self.nome)
        return self


class ProdutoEanBase(BaseModel):
    id: UUID = Field(default_factory=uuid4, json_schema_extra={"ui_hidden": True})
    ean: str = Field(..., pattern=r"^\d{13}$")
    barcode_url: Optional[str] = Field(None, json_schema_extra={"ui_readonly": True})
    visibilidade: bool = Field(default=False)

    @field_validator("ean")
    @classmethod
    def validate_ean(cls, v: str) -> str:
        return _validate_ean(v)


MIN_ORCAMENTO_TEXTO = "Mínimo de encomenda: 500€ + IVA (sem preços no site — orçamento sob consulta)."


def generate_slug(text: str) -> str:
    import unicodedata

    normalized = unicodedata.normalize("NFD", str(text or "").lower().strip())
    ascii_text = "".join(ch for ch in normalized if unicodedata.category(ch) != "Mn")
    return re.sub(r"[-\s]+", "-", re.sub(r"[^\w\s-]", "", ascii_text)).strip("-")


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
    visibilidade: bool = Field(default=False)
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
            elif not is_registered_tipo(self.tipo_catalogo):
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
    composicao: Dict[str, int] = _composicao_field()
    dimensoes: List[str] = Field(
        ...,
        min_length=1,
        description="Dimensões disponíveis (ex: 40x40, 50x50 cm)",
        json_schema_extra={"ui_widget": "string_list", "ui_label": "Dimensões"},
    )
    visibilidade: bool = Field(default=False)

    @model_validator(mode="after")
    def set_slug(self) -> "ModeloAlmofada":
        if not self.slug:
            self.slug = generate_slug(self.nome)
        return self

    @field_validator("composicao")
    @classmethod
    def validate_composicao(cls, v: Dict[str, int]) -> Dict[str, int]:
        return _validate_composicao_pct(v)

    @field_validator("dimensoes")
    @classmethod
    def validate_dimensoes(cls, v: List[str]) -> List[str]:
        return _validate_string_list(v, "dimensão")


class ModeloAlmofadaCor(BaseModel):
    """Cor de um modelo de almofada."""
    id: UUID = Field(default_factory=uuid4, json_schema_extra={"ui_hidden": True})
    id_modelo: UUID = Field(
        ...,
        description="Modelo dono",
        json_schema_extra={"ui_hidden": True},
    )
    numero: int = Field(..., ge=1, description="Número da cor")
    nome: str = Field(default="", description="Nome da cor (opcional)")
    imagem: str = Field(..., description="URL da imagem desta cor")
    visibilidade: bool = Field(default=False)


class ModeloAssentoCor(BaseModel):
    """Cor de um modelo de assento."""
    id: UUID = Field(default_factory=uuid4, json_schema_extra={"ui_hidden": True})
    id_modelo: UUID = Field(
        ...,
        description="Modelo dono",
        json_schema_extra={"ui_hidden": True},
    )
    numero: int = Field(..., ge=1, description="Número da cor")
    nome: str = Field(default="", description="Nome da cor (opcional)")
    imagem: str = Field(..., description="URL da imagem desta cor")
    visibilidade: bool = Field(default=False)


class Almofada(BaseModel):
    """Variante por tamanho/EAN — cor fica em modelo_cores. Categoria via modelo."""
    id: UUID = Field(default_factory=uuid4, json_schema_extra={"ui_hidden": True})
    id_modelo: UUID = Field(..., description="Modelo", json_schema_extra={"ui_relation": "modelos_almofadas"})
    ean: str = Field(..., pattern=r"^\d{13}$", description="EAN-13")
    barcode_url: Optional[str] = Field(None, json_schema_extra={"ui_readonly": True})
    dimensoes: str = Field(
        ...,
        pattern=r"^\d+x\d+$",
        description="Medidas (LxA cm)",
        json_schema_extra={
            "ui_widget": "dimensao_modelo",
            "ui_label": "Dimensão",
            "ui_lock_on_edit": True,
        },
    )
    visibilidade: bool = Field(default=False)

    @field_validator("ean")
    @classmethod
    def validate_ean(cls, v: str) -> str:
        return _validate_ean(v)


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
    visibilidade: bool = Field(default=False)

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
    """Um EAN/código de barras por altura do modelo."""
    id: UUID = Field(default_factory=uuid4, json_schema_extra={"ui_hidden": True})
    id_modelo: UUID = Field(..., description="Modelo", json_schema_extra={"ui_relation": "modelos_assentos"})
    altura: str = Field(
        ...,
        min_length=1,
        max_length=32,
        description="Altura desta variante (ex: 32mm)",
        json_schema_extra={
            "ui_widget": "altura_modelo",
            "ui_label": "Altura",
            "ui_lock_on_edit": True,
        },
    )
    ean: str = Field(..., pattern=r"^\d{13}$", description="EAN-13")
    barcode_url: Optional[str] = Field(None, json_schema_extra={"ui_readonly": True})
    visibilidade: bool = Field(default=False)

    @field_validator("ean")
    @classmethod
    def validate_ean(cls, v: str) -> str:
        digits = [int(d) for d in v]
        check = (10 - (sum(d * (3 if i % 2 else 1) for i, d in enumerate(digits[:-1])) % 10)) % 10
        if digits[-1] != check:
            raise ValueError(f"EAN inválido. Check-digit esperado: {check}")
        return v


# --- Guarda-chuvas ---

class ModeloGuardaChuvaCor(BaseModel):
    id: UUID = Field(default_factory=uuid4, json_schema_extra={"ui_hidden": True})
    id_modelo: UUID = Field(..., json_schema_extra={"ui_hidden": True})
    numero: int = Field(..., ge=1)
    nome: str = Field(default="")
    imagem: str = Field(...)
    visibilidade: bool = Field(default=False)


class ModeloGuardaChuva(BaseModel):
    id: UUID = Field(default_factory=uuid4, json_schema_extra={"ui_hidden": True})
    id_categoria: UUID = Field(..., json_schema_extra={"ui_relation": "categories"})
    nome: str = Field(...)
    slug: str = Field(default="", json_schema_extra={"ui_readonly": True})
    descricao: str = Field(default="")
    visibilidade: bool = Field(default=False)

    @model_validator(mode="after")
    def set_slug(self) -> "ModeloGuardaChuva":
        if not self.slug:
            self.slug = generate_slug(self.nome)
        return self


class GuardaChuva(BaseModel):
    id: UUID = Field(default_factory=uuid4, json_schema_extra={"ui_hidden": True})
    id_modelo: UUID = Field(..., json_schema_extra={"ui_relation": "modelos_guarda_chuvas"})
    ean: str = Field(..., pattern=r"^\d{13}$")
    barcode_url: Optional[str] = Field(None, json_schema_extra={"ui_readonly": True})
    visibilidade: bool = Field(default=False)

    @field_validator("ean")
    @classmethod
    def validate_ean(cls, v: str) -> str:
        return _validate_ean(v)


# --- Óculos ---

TIPO_OCULO = Literal["sol", "leitura"]
TIPO_OCULO_LABELS = {"sol": "Óculos de sol", "leitura": "Óculos de leitura"}
SEGMENTO_OCULO = Literal["homem", "mulher", "crianca"]
SEGMENTO_OCULO_LABELS = {"homem": "Homem", "mulher": "Mulher", "crianca": "Criança"}


class ModeloOculoCor(BaseModel):
    id: UUID = Field(default_factory=uuid4, json_schema_extra={"ui_hidden": True})
    id_modelo: UUID = Field(..., json_schema_extra={"ui_hidden": True})
    numero: int = Field(..., ge=1)
    nome: str = Field(default="")
    imagem: str = Field(...)
    visibilidade: bool = Field(default=False)


class ModeloOculo(BaseModel):
    id: UUID = Field(default_factory=uuid4, json_schema_extra={"ui_hidden": True})
    id_categoria: UUID = Field(..., json_schema_extra={"ui_relation": "categories"})
    nome: str = Field(...)
    slug: str = Field(default="", json_schema_extra={"ui_readonly": True})
    descricao: str = Field(default="")
    tipo_oculo: TIPO_OCULO = Field(
        ...,
        json_schema_extra={
            "ui_widget": "enum",
            "ui_options": ["sol", "leitura"],
            "ui_labels": TIPO_OCULO_LABELS,
        },
    )
    visibilidade: bool = Field(default=False)

    @model_validator(mode="after")
    def set_slug(self) -> "ModeloOculo":
        if not self.slug:
            self.slug = generate_slug(self.nome)
        return self


class Oculo(BaseModel):
    id: UUID = Field(default_factory=uuid4, json_schema_extra={"ui_hidden": True})
    id_modelo: UUID = Field(..., json_schema_extra={"ui_relation": "modelos_oculos"})
    segmento: Optional[SEGMENTO_OCULO] = Field(
        None,
        description="Segmento (legado — oculto no backoffice)",
        json_schema_extra={"ui_hidden": True},
    )
    ean: str = Field(..., pattern=r"^\d{13}$")
    barcode_url: Optional[str] = Field(None, json_schema_extra={"ui_readonly": True})
    visibilidade: bool = Field(default=False)

    @field_validator("ean")
    @classmethod
    def validate_ean(cls, v: str) -> str:
        return _validate_ean(v)


# --- Toalhas de mesa ---

TIPO_TOALHA_MESA = Literal["toalha", "protetor"]
TIPO_TOALHA_MESA_LABELS = {"toalha": "Toalha de mesa", "protetor": "Protetor de mesa"}
MATERIAL_TOALHA = Literal["pvc", "poliester"]
MATERIAL_TOALHA_LABELS = {"pvc": "PVC", "poliester": "Poliéster"}


class ModeloToalhaMesaCor(BaseModel):
    id: UUID = Field(default_factory=uuid4, json_schema_extra={"ui_hidden": True})
    id_modelo: UUID = Field(..., json_schema_extra={"ui_hidden": True})
    numero: int = Field(..., ge=1)
    nome: str = Field(default="")
    imagem: str = Field(...)
    visibilidade: bool = Field(default=False)


class ModeloToalhaMesa(BaseModel):
    id: UUID = Field(default_factory=uuid4, json_schema_extra={"ui_hidden": True})
    id_categoria: UUID = Field(..., json_schema_extra={"ui_relation": "categories"})
    nome: str = Field(...)
    slug: str = Field(default="", json_schema_extra={"ui_readonly": True})
    descricao: str = Field(default="")
    tipo_produto: TIPO_TOALHA_MESA = Field(
        ...,
        json_schema_extra={
            "ui_widget": "enum",
            "ui_options": ["toalha", "protetor"],
            "ui_labels": TIPO_TOALHA_MESA_LABELS,
        },
    )
    material: MATERIAL_TOALHA = Field(
        ...,
        json_schema_extra={
            "ui_widget": "enum",
            "ui_options": ["pvc", "poliester"],
            "ui_labels": MATERIAL_TOALHA_LABELS,
        },
    )
    composicao: Dict[str, int] = _composicao_field()
    dimensoes: List[str] = Field(
        ...,
        min_length=1,
        json_schema_extra={"ui_widget": "string_list", "ui_label": "Dimensões"},
    )
    visibilidade: bool = Field(default=False)

    @model_validator(mode="after")
    def set_slug(self) -> "ModeloToalhaMesa":
        if not self.slug:
            self.slug = generate_slug(self.nome)
        return self

    @field_validator("composicao")
    @classmethod
    def validate_composicao(cls, v: Dict[str, int]) -> Dict[str, int]:
        return _validate_composicao_pct(v)

    @field_validator("dimensoes")
    @classmethod
    def validate_dimensoes(cls, v: List[str]) -> List[str]:
        return _validate_string_list(v, "dimensão")


class ToalhaMesa(BaseModel):
    id: UUID = Field(default_factory=uuid4, json_schema_extra={"ui_hidden": True})
    id_modelo: UUID = Field(..., json_schema_extra={"ui_relation": "modelos_toalhas_mesa"})
    dimensoes: str = Field(
        ...,
        pattern=r"^\d+x\d+$",
        json_schema_extra={"ui_widget": "dimensao_modelo", "ui_lock_on_edit": True},
    )
    ean: str = Field(..., pattern=r"^\d{13}$")
    barcode_url: Optional[str] = Field(None, json_schema_extra={"ui_readonly": True})
    visibilidade: bool = Field(default=False)

    @field_validator("ean")
    @classmethod
    def validate_ean(cls, v: str) -> str:
        return _validate_ean(v)


# --- Material de cozinha (famílias) ---

class ModeloAventalCor(BaseModel):
    id: UUID = Field(default_factory=uuid4, json_schema_extra={"ui_hidden": True})
    id_modelo: UUID = Field(..., json_schema_extra={"ui_hidden": True})
    numero: int = Field(..., ge=1)
    nome: str = Field(default="")
    imagem: str = Field(...)
    visibilidade: bool = Field(default=False)


class ModeloAvental(BaseModel):
    id: UUID = Field(default_factory=uuid4, json_schema_extra={"ui_hidden": True})
    id_categoria: UUID = Field(..., json_schema_extra={"ui_relation": "categories"})
    nome: str = Field(...)
    slug: str = Field(default="", json_schema_extra={"ui_readonly": True})
    descricao: str = Field(default="")
    composicao: Dict[str, int] = _composicao_field()
    visibilidade: bool = Field(default=False)

    @model_validator(mode="after")
    def set_slug(self) -> "ModeloAvental":
        if not self.slug:
            self.slug = generate_slug(self.nome)
        return self

    @field_validator("composicao")
    @classmethod
    def validate_composicao(cls, v: Dict[str, int]) -> Dict[str, int]:
        return _validate_composicao_pct(v)


class Avental(BaseModel):
    id: UUID = Field(default_factory=uuid4, json_schema_extra={"ui_hidden": True})
    id_modelo: UUID = Field(..., json_schema_extra={"ui_relation": "modelos_aventais"})
    ean: str = Field(..., pattern=r"^\d{13}$")
    barcode_url: Optional[str] = Field(None, json_schema_extra={"ui_readonly": True})
    visibilidade: bool = Field(default=False)

    @field_validator("ean")
    @classmethod
    def validate_ean(cls, v: str) -> str:
        return _validate_ean(v)


class ModeloLuvaCor(BaseModel):
    id: UUID = Field(default_factory=uuid4, json_schema_extra={"ui_hidden": True})
    id_modelo: UUID = Field(..., json_schema_extra={"ui_hidden": True})
    numero: int = Field(..., ge=1)
    nome: str = Field(default="")
    imagem: str = Field(...)
    visibilidade: bool = Field(default=False)


class ModeloLuva(BaseModel):
    id: UUID = Field(default_factory=uuid4, json_schema_extra={"ui_hidden": True})
    id_categoria: UUID = Field(..., json_schema_extra={"ui_relation": "categories"})
    nome: str = Field(...)
    slug: str = Field(default="", json_schema_extra={"ui_readonly": True})
    descricao: str = Field(default="")
    composicao: Dict[str, int] = _composicao_field()
    visibilidade: bool = Field(default=False)

    @model_validator(mode="after")
    def set_slug(self) -> "ModeloLuva":
        if not self.slug:
            self.slug = generate_slug(self.nome)
        return self

    @field_validator("composicao")
    @classmethod
    def validate_composicao(cls, v: Dict[str, int]) -> Dict[str, int]:
        return _validate_composicao_pct(v)


class Luva(BaseModel):
    id: UUID = Field(default_factory=uuid4, json_schema_extra={"ui_hidden": True})
    id_modelo: UUID = Field(..., json_schema_extra={"ui_relation": "modelos_luvas"})
    ean: str = Field(..., pattern=r"^\d{13}$")
    barcode_url: Optional[str] = Field(None, json_schema_extra={"ui_readonly": True})
    visibilidade: bool = Field(default=False)

    @field_validator("ean")
    @classmethod
    def validate_ean(cls, v: str) -> str:
        return _validate_ean(v)


class ModeloPegaCor(BaseModel):
    id: UUID = Field(default_factory=uuid4, json_schema_extra={"ui_hidden": True})
    id_modelo: UUID = Field(..., json_schema_extra={"ui_hidden": True})
    numero: int = Field(..., ge=1)
    nome: str = Field(default="")
    imagem: str = Field(...)
    visibilidade: bool = Field(default=False)


class ModeloPega(BaseModel):
    id: UUID = Field(default_factory=uuid4, json_schema_extra={"ui_hidden": True})
    id_categoria: UUID = Field(..., json_schema_extra={"ui_relation": "categories"})
    nome: str = Field(...)
    slug: str = Field(default="", json_schema_extra={"ui_readonly": True})
    descricao: str = Field(default="")
    composicao: Dict[str, int] = _composicao_field()
    visibilidade: bool = Field(default=False)

    @model_validator(mode="after")
    def set_slug(self) -> "ModeloPega":
        if not self.slug:
            self.slug = generate_slug(self.nome)
        return self

    @field_validator("composicao")
    @classmethod
    def validate_composicao(cls, v: Dict[str, int]) -> Dict[str, int]:
        return _validate_composicao_pct(v)


class Pega(BaseModel):
    id: UUID = Field(default_factory=uuid4, json_schema_extra={"ui_hidden": True})
    id_modelo: UUID = Field(..., json_schema_extra={"ui_relation": "modelos_pegas"})
    ean: str = Field(..., pattern=r"^\d{13}$")
    barcode_url: Optional[str] = Field(None, json_schema_extra={"ui_readonly": True})
    visibilidade: bool = Field(default=False)

    @field_validator("ean")
    @classmethod
    def validate_ean(cls, v: str) -> str:
        return _validate_ean(v)


class ModeloPanoCozinhaCor(BaseModel):
    id: UUID = Field(default_factory=uuid4, json_schema_extra={"ui_hidden": True})
    id_modelo: UUID = Field(..., json_schema_extra={"ui_hidden": True})
    numero: int = Field(..., ge=1)
    nome: str = Field(default="")
    imagem: str = Field(...)
    visibilidade: bool = Field(default=False)


class ModeloPanoCozinha(BaseModel):
    id: UUID = Field(default_factory=uuid4, json_schema_extra={"ui_hidden": True})
    id_categoria: UUID = Field(..., json_schema_extra={"ui_relation": "categories"})
    nome: str = Field(...)
    slug: str = Field(default="", json_schema_extra={"ui_readonly": True})
    descricao: str = Field(default="")
    composicao: Dict[str, int] = _composicao_field()
    dimensoes: List[str] = Field(
        ...,
        min_length=1,
        json_schema_extra={"ui_widget": "string_list", "ui_label": "Dimensões"},
    )
    visibilidade: bool = Field(default=False)

    @model_validator(mode="after")
    def set_slug(self) -> "ModeloPanoCozinha":
        if not self.slug:
            self.slug = generate_slug(self.nome)
        return self

    @field_validator("dimensoes")
    @classmethod
    def validate_dimensoes(cls, v: List[str]) -> List[str]:
        return _validate_string_list(v, "dimensão")

    @field_validator("composicao")
    @classmethod
    def validate_composicao(cls, v: Dict[str, int]) -> Dict[str, int]:
        return _validate_composicao_pct(v)


class PanoCozinha(BaseModel):
    id: UUID = Field(default_factory=uuid4, json_schema_extra={"ui_hidden": True})
    id_modelo: UUID = Field(..., json_schema_extra={"ui_relation": "modelos_panos_cozinha"})
    dimensoes: str = Field(
        ...,
        pattern=r"^\d+x\d+$",
        json_schema_extra={"ui_widget": "dimensao_modelo", "ui_lock_on_edit": True},
    )
    ean: str = Field(..., pattern=r"^\d{13}$")
    barcode_url: Optional[str] = Field(None, json_schema_extra={"ui_readonly": True})
    visibilidade: bool = Field(default=False)

    @field_validator("ean")
    @classmethod
    def validate_ean(cls, v: str) -> str:
        return _validate_ean(v)


# --- Regional ---

SUBTIPO_REGIONAL = Literal["avental", "luva", "pega", "pano_cozinha", "toalha", "protetor"]
SUBTIPO_REGIONAL_LABELS = {
    "avental": "Avental",
    "luva": "Luva",
    "pega": "Pega",
    "pano_cozinha": "Pano de cozinha",
    "toalha": "Toalha de mesa",
    "protetor": "Protetor de mesa",
}


class ModeloRegionalCor(BaseModel):
    id: UUID = Field(default_factory=uuid4, json_schema_extra={"ui_hidden": True})
    id_modelo: UUID = Field(..., json_schema_extra={"ui_hidden": True})
    numero: int = Field(..., ge=1)
    nome: str = Field(default="", description="Nome da estampa/região")
    imagem: str = Field(...)
    visibilidade: bool = Field(default=False)


class ModeloRegional(BaseModel):
    id: UUID = Field(default_factory=uuid4, json_schema_extra={"ui_hidden": True})
    id_categoria: UUID = Field(..., json_schema_extra={"ui_relation": "categories"})
    nome: str = Field(...)
    slug: str = Field(default="", json_schema_extra={"ui_readonly": True})
    descricao: str = Field(default="")
    subtipo: SUBTIPO_REGIONAL = Field(
        ...,
        json_schema_extra={
            "ui_widget": "enum",
            "ui_options": ["avental", "luva", "pega", "pano_cozinha", "toalha", "protetor"],
            "ui_labels": SUBTIPO_REGIONAL_LABELS,
        },
    )
    composicao: Dict[str, int] = _composicao_field()
    dimensoes: Optional[List[str]] = Field(
        None,
        json_schema_extra={"ui_widget": "string_list", "ui_label": "Dimensões"},
    )
    visibilidade: bool = Field(default=False)

    @model_validator(mode="after")
    def set_slug(self) -> "ModeloRegional":
        if not self.slug:
            self.slug = generate_slug(self.nome)
        return self

    @model_validator(mode="after")
    def validate_subtipo_fields(self) -> "ModeloRegional":
        needs_dim = self.subtipo in ("pano_cozinha", "toalha", "protetor")
        if needs_dim and not self.dimensoes:
            raise ValueError("Indique dimensões para este subtipo.")
        if not self.composicao:
            raise ValueError("Indique composição.")
        _validate_composicao_pct(self.composicao)
        return self

    @field_validator("composicao")
    @classmethod
    def validate_composicao(cls, v: Dict[str, int]) -> Dict[str, int]:
        return _validate_composicao_pct(v)


class Regional(BaseModel):
    id: UUID = Field(default_factory=uuid4, json_schema_extra={"ui_hidden": True})
    id_modelo: UUID = Field(..., json_schema_extra={"ui_relation": "modelos_regionais"})
    dimensoes: Optional[str] = Field(
        None,
        pattern=r"^\d+x\d+$",
        json_schema_extra={"ui_widget": "dimensao_modelo", "ui_lock_on_edit": True},
    )
    ean: str = Field(..., pattern=r"^\d{13}$")
    barcode_url: Optional[str] = Field(None, json_schema_extra={"ui_readonly": True})
    visibilidade: bool = Field(default=False)

    @field_validator("ean")
    @classmethod
    def validate_ean(cls, v: str) -> str:
        return _validate_ean(v)


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
                "colors_table": "modelo_almofada_cores",
                "colors_schema": ModeloAlmofadaCor,
                "model_schema": ModeloAlmofada,
                "product_schema": Almofada,
                "model_discriminator_field": "dimensoes",
                "product_readonly_on_edit": True,
                "apply_barcode_on_save": True,
                "storefront_mode": "variantes",
                "storefront_filters": [
                    {
                        "field": "tipo",
                        "label": "Tipo de Almofada",
                        "options": ["decorativa", "dormir"],
                        "labels": TIPO_ALMOFADA_LABELS,
                    },
                ],
                "storefront_picker": {
                    "source": "products",
                    "field": "dimensoes",
                    "label": "Tamanho",
                    "format": "dimensions",
                    "suffix": " cm",
                },
            },
            "assento": {
                "label": "Assentos",
                "model_table": "modelos_assentos",
                "product_table": "assento",
                "colors_table": "modelo_assento_cores",
                "colors_schema": ModeloAssentoCor,
                "model_schema": ModeloAssento,
                "product_schema": Assento,
                "model_discriminator_field": "alturas",
                "product_readonly_on_edit": True,
                "apply_barcode_on_save": True,
                "storefront_mode": "assento",
                "storefront_picker": {
                    "source": "products",
                    "field": "altura",
                    "label": "Altura",
                    "format": "plain",
                },
            },
            "guarda_chuva": {
                "label": "Guarda-chuvas",
                "model_table": "modelos_guarda_chuvas",
                "product_table": "guarda_chuva",
                "colors_table": "modelo_guarda_chuva_cores",
                "colors_schema": ModeloGuardaChuvaCor,
                "model_schema": ModeloGuardaChuva,
                "product_schema": GuardaChuva,
                "model_discriminator_field": None,
                "product_readonly_on_edit": True,
                "apply_barcode_on_save": True,
                "storefront_mode": "unico",
            },
            "oculo": {
                "label": "Óculos",
                "model_table": "modelos_oculos",
                "product_table": "oculo",
                "colors_table": "modelo_oculo_cores",
                "colors_schema": ModeloOculoCor,
                "model_schema": ModeloOculo,
                "product_schema": Oculo,
                "model_discriminator_field": None,
                "product_readonly_on_edit": True,
                "apply_barcode_on_save": True,
                "storefront_mode": "unico",
                "storefront_filters": [
                    {
                        "field": "tipo_oculo",
                        "label": "Tipo",
                        "options": ["sol", "leitura"],
                        "labels": TIPO_OCULO_LABELS,
                    },
                ],
            },
            "toalha_mesa": {
                "label": "Toalhas de mesa",
                "model_table": "modelos_toalhas_mesa",
                "product_table": "toalha_mesa",
                "colors_table": "modelo_toalha_mesa_cores",
                "colors_schema": ModeloToalhaMesaCor,
                "model_schema": ModeloToalhaMesa,
                "product_schema": ToalhaMesa,
                "model_discriminator_field": "dimensoes",
                "product_readonly_on_edit": True,
                "apply_barcode_on_save": True,
                "storefront_mode": "variantes",
                "storefront_filters": [
                    {
                        "field": "tipo_produto",
                        "label": "Tipo",
                        "options": ["toalha", "protetor"],
                        "labels": TIPO_TOALHA_MESA_LABELS,
                    },
                    {
                        "field": "material",
                        "label": "Material",
                        "options": ["pvc", "poliester"],
                        "labels": MATERIAL_TOALHA_LABELS,
                    },
                ],
                "storefront_picker": {
                    "source": "products",
                    "field": "dimensoes",
                    "label": "Dimensão",
                    "format": "dimensions",
                    "suffix": " cm",
                },
            },
            "avental": {
                "label": "Aventais",
                "model_table": "modelos_aventais",
                "product_table": "avental",
                "colors_table": "modelo_avental_cores",
                "colors_schema": ModeloAventalCor,
                "model_schema": ModeloAvental,
                "product_schema": Avental,
                "apply_barcode_on_save": True,
                "storefront_mode": "unico",
            },
            "luva": {
                "label": "Luvas",
                "model_table": "modelos_luvas",
                "product_table": "luva",
                "colors_table": "modelo_luva_cores",
                "colors_schema": ModeloLuvaCor,
                "model_schema": ModeloLuva,
                "product_schema": Luva,
                "apply_barcode_on_save": True,
                "storefront_mode": "unico",
            },
            "pega": {
                "label": "Pegas",
                "model_table": "modelos_pegas",
                "product_table": "pega",
                "colors_table": "modelo_pega_cores",
                "colors_schema": ModeloPegaCor,
                "model_schema": ModeloPega,
                "product_schema": Pega,
                "apply_barcode_on_save": True,
                "storefront_mode": "unico",
            },
            "pano_cozinha": {
                "label": "Panos de cozinha",
                "model_table": "modelos_panos_cozinha",
                "product_table": "pano_cozinha",
                "colors_table": "modelo_pano_cozinha_cores",
                "colors_schema": ModeloPanoCozinhaCor,
                "model_schema": ModeloPanoCozinha,
                "product_schema": PanoCozinha,
                "model_discriminator_field": "dimensoes",
                "product_readonly_on_edit": True,
                "apply_barcode_on_save": True,
                "storefront_mode": "variantes",
                "storefront_picker": {
                    "source": "products",
                    "field": "dimensoes",
                    "label": "Dimensão",
                    "format": "dimensions",
                    "suffix": " cm",
                },
            },
            "regional": {
                "label": "Regional",
                "model_table": "modelos_regionais",
                "product_table": "regional",
                "colors_table": "modelo_regional_cores",
                "colors_schema": ModeloRegionalCor,
                "model_schema": ModeloRegional,
                "product_schema": Regional,
                "model_discriminator_field": "dimensoes",
                "product_readonly_on_edit": True,
                "apply_barcode_on_save": True,
                "storefront_mode": "variantes",
                "storefront_filters": [
                    {
                        "field": "subtipo",
                        "label": "Tipo",
                        "options": ["avental", "luva", "pega", "pano_cozinha", "toalha", "protetor"],
                        "labels": SUBTIPO_REGIONAL_LABELS,
                    },
                ],
                "storefront_picker": {
                    "source": "products",
                    "field": "dimensoes",
                    "label": "Dimensão",
                    "format": "dimensions",
                    "suffix": " cm",
                },
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
