#!/usr/bin/env python
"""Seed database with test data for development."""
from __future__ import annotations

import os
import sys
from datetime import datetime
from decimal import Decimal
from uuid import uuid4

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.database import get_db


def seed_categories():
    """Seed product categories."""
    db = get_db()

    categories = [
        {
            "id": str(uuid4()),
            "name": "Almofadas",
            "slug": "almofadas",
            "tipo_catalogo": "almofada",
            "descricao": "Almofadas decorativas e funcionais",
            "visibilidade": True,
        },
        {
            "id": str(uuid4()),
            "name": "Mantas",
            "slug": "mantas",
            "tipo_catalogo": "manta",
            "descricao": "Mantas aconchegantes",
            "visibilidade": True,
        },
        {
            "id": str(uuid4()),
            "name": "Tapetes",
            "slug": "tapetes",
            "tipo_catalogo": "tapete",
            "descricao": "Tapetes para qualquer espaço",
            "visibilidade": True,
        },
    ]

    for cat in categories:
        try:
            db.table("categories").insert(cat).execute()
            print(f"✓ Category created: {cat['name']}")
        except Exception as e:
            print(f"✗ Category creation failed: {e}")

    return categories


def seed_products(categories):
    """Seed product models."""
    db = get_db()

    products = [
        {
            "id": str(uuid4()),
            "tipo_catalogo": "almofada",
            "id_categoria": categories[0]["id"],
            "nome": "Almofada Confort Básica",
            "descricao": "Almofada confortável para qualquer sofá",
            "preco_base": Decimal("29.99"),
            "sku": "ALM-001",
            "attributes": {
                "dimensoes": ["30x30", "40x40", "50x50"],
                "materiais": ["Algodão", "Lã"],
                "cores_disponiveis": ["Branco", "Cinzento", "Preto"],
            },
            "visibilidade": True,
            "criado_em": datetime.utcnow().isoformat(),
        },
        {
            "id": str(uuid4()),
            "tipo_catalogo": "almofada",
            "id_categoria": categories[0]["id"],
            "nome": "Almofada Premium Decorativa",
            "descricao": "Almofada de luxo com padrões especiais",
            "preco_base": Decimal("49.99"),
            "sku": "ALM-002",
            "attributes": {
                "dimensoes": ["40x40", "50x50"],
                "materiais": ["Veludo", "Seda"],
                "cores_disponiveis": ["Ouro", "Prata", "Bronze"],
            },
            "visibilidade": True,
            "criado_em": datetime.utcnow().isoformat(),
        },
        {
            "id": str(uuid4()),
            "tipo_catalogo": "manta",
            "id_categoria": categories[1]["id"],
            "nome": "Manta Quentinha Inverno",
            "descricao": "Manta perfeita para os dias frios",
            "preco_base": Decimal("59.99"),
            "sku": "MNT-001",
            "attributes": {
                "dimensoes": ["100x150", "150x200"],
                "materiais": ["Lã merino", "Algodão"],
                "cores_disponiveis": ["Vermelho", "Azul", "Verde"],
            },
            "visibilidade": True,
            "criado_em": datetime.utcnow().isoformat(),
        },
    ]

    for prod in products:
        try:
            db.table("product_models").insert(prod).execute()
            print(f"✓ Product created: {prod['nome']}")
        except Exception as e:
            print(f"✗ Product creation failed: {e}")

    return products


def seed_colors(products):
    """Seed product colors."""
    db = get_db()

    colors = [
        {
            "id": str(uuid4()),
            "id_modelo": products[0]["id"],
            "tipo_catalogo": "almofada",
            "cor": "Branco",
            "codigo_cor": "#FFFFFF",
            "disponibilidade": 50,
            "preco_margem": Decimal("0.00"),
        },
        {
            "id": str(uuid4()),
            "id_modelo": products[0]["id"],
            "tipo_catalogo": "almofada",
            "cor": "Cinzento",
            "codigo_cor": "#808080",
            "disponibilidade": 30,
            "preco_margem": Decimal("5.00"),
        },
        {
            "id": str(uuid4()),
            "id_modelo": products[1]["id"],
            "tipo_catalogo": "almofada",
            "cor": "Ouro",
            "codigo_cor": "#FFD700",
            "disponibilidade": 20,
            "preco_margem": Decimal("10.00"),
        },
    ]

    for color in colors:
        try:
            db.table("product_model_colors").insert(color).execute()
            print(f"✓ Color created: {color['cor']}")
        except Exception as e:
            print(f"✗ Color creation failed: {e}")


def seed_test_users():
    """Seed test users for local development."""
    db = get_db()

    users = [
        {
            "id": "test-admin-001",
            "email": "admin@diomika-test.pt",
            "name": "Test Admin",
            "role": "admin",
            "is_active": True,
            "mfa_enabled": False,
        },
        {
            "id": "test-user-001",
            "email": "user@diomika-test.pt",
            "name": "Test User",
            "role": "customer",
            "is_active": True,
            "mfa_enabled": False,
        },
    ]

    for user in users:
        try:
            db.table("users").insert(user).execute()
            print(f"✓ User created: {user['name']}")
        except Exception as e:
            print(f"✗ User creation failed: {e}")


def main():
    """Run all seeding functions."""
    print("🌱 Starting database seeding...\n")

    try:
        print("📦 Seeding categories...")
        categories = seed_categories()
        print()

        print("📦 Seeding products...")
        products = seed_products(categories)
        print()

        print("📦 Seeding colors...")
        seed_colors(products)
        print()

        print("👤 Seeding test users...")
        seed_test_users()
        print()

        print("✅ Database seeding completed successfully!")
        print("\nTest credentials:")
        print("  Admin: admin@diomika-test.pt")
        print("  User: user@diomika-test.pt")

    except Exception as e:
        print(f"\n❌ Seeding failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
