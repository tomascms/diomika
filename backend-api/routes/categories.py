import asyncio
import logging

from uuid import UUID

from fastapi import APIRouter, HTTPException

from core.cache import catalog_cache_ttl, get_or_set
from core.cqrs.queries.catalog import ListCategoriesQuery, list_categories
from core.database import get_db
from core.public_api import PUBLIC_CATEGORY_FIELDS, public_category
from core.visibility import require_visible

logger = logging.getLogger("diomika-api")

router = APIRouter(prefix="/categorias", tags=["Categorias"])


@router.get("")
async def get_categories():
    ttl = catalog_cache_ttl()

    def load():
        return list_categories(ListCategoriesQuery())

    try:
        return await asyncio.to_thread(get_or_set, "categories:all", float(ttl), load)
    except Exception as e:
        logger.error("Erro ao listar categorias: %s", e)
        raise HTTPException(status_code=500, detail="Erro ao carregar categorias") from e


@router.get("/slug/{slug}")
async def get_category_by_slug(slug: str):
    ttl = catalog_cache_ttl()
    cache_key = f"categories:slug:{slug}"

    def load():
        res = (
            get_db()
            .table("categories")
            .select(PUBLIC_CATEGORY_FIELDS)
            .eq("slug", slug.strip())
            .execute()
        )
        if not res.data:
            raise HTTPException(status_code=404, detail="Categoria não encontrada")
        return public_category(require_visible(res.data[0]))

    try:
        return await asyncio.to_thread(get_or_set, cache_key, float(ttl), load)
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Erro ao buscar categoria slug %s: %s", slug, e)
        raise HTTPException(status_code=500, detail="Erro ao carregar categoria") from e


@router.get("/{id_categoria}")
async def get_category(id_categoria: UUID):
    ttl = catalog_cache_ttl()
    cache_key = f"categories:{id_categoria}"

    def load():
        res = get_db().table("categories").select(PUBLIC_CATEGORY_FIELDS).eq("id", str(id_categoria)).execute()
        if not res.data:
            raise HTTPException(status_code=404, detail="ID não encontrado")
        return public_category(require_visible(res.data[0]))

    try:
        return await asyncio.to_thread(get_or_set, cache_key, float(ttl), load)
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Erro ao buscar categoria %s: %s", id_categoria, e)
        raise HTTPException(status_code=500, detail="Erro ao carregar categoria") from e
