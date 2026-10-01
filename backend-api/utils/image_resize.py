"""Redimensiona/comprime imagens de catálogo no upload (servidor) — sem
depender do Supabase Image Transformation (feature paga, Plano Pro+).

O projecto corre em infraestrutura de custo zero (ver deploy/docker-compose.free.yml),
por isso a optimização tem de acontecer uma vez, no upload, e não por-pedido
numa API de transformação. Gifs animados e imagens já pequenas ficam
intocados; PNG/JPEG/WebP grandes são redimensionados e recomprimidos.
"""
from __future__ import annotations

import io
from pathlib import Path

MAX_DIMENSION = 1600  # suficiente para a maior imagem usada na loja (hero/detalhe)
JPEG_QUALITY = 82
WEBP_QUALITY = 82
PNG_COMPRESS_LEVEL = 9


def optimize_for_web(data: bytes, filename: str, *, max_dimension: int = MAX_DIMENSION) -> bytes:
    """Redimensiona (se maior que max_dimension) e recomprime. Nunca falha
    "a mais" — se o Pillow não conseguir processar, devolve os bytes originais."""
    ext = Path(filename or "").suffix.lower()
    if ext == ".gif":
        return data  # animações — não mexer

    try:
        from PIL import Image, ImageOps
    except ImportError:
        return data

    try:
        img = Image.open(io.BytesIO(data))
        img = ImageOps.exif_transpose(img)  # corrige rotação de fotos de telemóvel

        if max(img.width, img.height) > max_dimension:
            img.thumbnail((max_dimension, max_dimension), Image.LANCZOS)

        out = io.BytesIO()
        if ext in (".jpg", ".jpeg"):
            if img.mode in ("RGBA", "P"):
                img = img.convert("RGB")
            img.save(out, format="JPEG", quality=JPEG_QUALITY, optimize=True, progressive=True)
        elif ext == ".webp":
            img.save(out, format="WEBP", quality=WEBP_QUALITY, method=6)
        elif ext == ".png":
            img.save(out, format="PNG", optimize=True, compress_level=PNG_COMPRESS_LEVEL)
        else:
            return data

        optimized = out.getvalue()
        # Só usa o resultado se for mesmo mais pequeno — nunca piorar.
        return optimized if len(optimized) < len(data) else data
    except Exception:
        return data
