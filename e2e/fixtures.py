"""E2E test fixtures and utilities for data seeding and test setup."""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from decimal import Decimal
from typing import Optional, AsyncGenerator
from uuid import uuid4

import pytest
from playwright.async_api import async_playwright, Browser, Page

logger = logging.getLogger("e2e-fixtures")


class TestDataFactory:
    """Factory for creating test data across API and database."""

    def __init__(self, api_base_url: str):
        self.api_base_url = api_base_url
        self.created_resources = []

    async def create_test_customer(
        self,
        email: Optional[str] = None,
        name: str = "Test Customer",
    ) -> dict:
        """Create a test customer account."""
        test_email = email or f"test-{uuid4().hex[:8]}@example.com"

        payload = {
            "email": test_email,
            "name": name,
            "password": "TestPassword123!",
        }

        # Would call API endpoint to create customer
        logger.info(f"Created test customer: {test_email}")

        self.created_resources.append(("customer", test_email))

        return {
            "email": test_email,
            "name": name,
        }

    async def create_test_product(
        self,
        name: str = "Test Product",
        price: Decimal = Decimal("99.99"),
        sku: Optional[str] = None,
    ) -> dict:
        """Create a test product."""
        test_sku = sku or f"TEST-{uuid4().hex[:8]}"

        payload = {
            "name": name,
            "sku": test_sku,
            "price": float(price),
            "category": "test",
            "stock": 100,
        }

        logger.info(f"Created test product: {test_sku}")

        self.created_resources.append(("product", test_sku))

        return {
            "sku": test_sku,
            "name": name,
            "price": price,
        }

    async def create_test_order(
        self,
        customer_email: str,
        items: list[dict],
        total_amount: Decimal = Decimal("199.99"),
    ) -> dict:
        """Create a test order."""
        order_id = f"TEST-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}-{uuid4().hex[:4]}"

        payload = {
            "customer_email": customer_email,
            "items": items,
            "total_amount": float(total_amount),
        }

        logger.info(f"Created test order: {order_id}")

        self.created_resources.append(("order", order_id))

        return {
            "order_id": order_id,
            "customer_email": customer_email,
            "total_amount": total_amount,
        }

    async def cleanup(self) -> None:
        """Clean up all created test resources."""
        logger.info(f"Cleaning up {len(self.created_resources)} test resources")

        for resource_type, resource_id in reversed(self.created_resources):
            try:
                # Would call API endpoint to delete resource
                logger.info(f"Deleted {resource_type}: {resource_id}")
            except Exception as e:
                logger.error(f"Failed to delete {resource_type} {resource_id}: {e}")

        self.created_resources.clear()


@pytest.fixture
async def test_data_factory(api_base_url: str = "http://localhost:8000") -> AsyncGenerator:
    """Fixture providing test data factory."""
    factory = TestDataFactory(api_base_url)
    yield factory
    await factory.cleanup()


@pytest.fixture
async def browser() -> AsyncGenerator:
    """Fixture providing Playwright browser instance."""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        yield browser
        await browser.close()


@pytest.fixture
async def page(browser: Browser) -> AsyncGenerator:
    """Fixture providing Playwright page instance."""
    page = await browser.new_page()
    yield page
    await page.close()


@pytest.fixture
def api_base_url() -> str:
    """API base URL fixture."""
    return "http://localhost:8000"
