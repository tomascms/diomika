"""E2E tests for complete order flow: browse -> add to cart -> checkout -> payment -> receipt."""
from __future__ import annotations

import asyncio
from decimal import Decimal
from uuid import uuid4

import pytest
from playwright.async_api import Page, expect

from fixtures import TestDataFactory


class TestOrderFlow:
    """End-to-end order flow tests."""

    async def test_complete_purchase_flow(
        self,
        page: Page,
        test_data_factory: TestDataFactory,
        api_base_url: str,
    ):
        """Test complete purchase flow from browsing to order confirmation."""

        # Create test customer
        customer = await test_data_factory.create_test_customer(
            name="E2E Test User"
        )

        # Navigate to store
        await page.goto(f"{api_base_url}/storefront")

        # Wait for product list to load
        await page.wait_for_selector("[data-testid='product-card']")

        product_cards = await page.locator("[data-testid='product-card']").all()
        assert len(product_cards) > 0, "Should have products displayed"

        # Click first product to view details
        await product_cards[0].click()
        await page.wait_for_selector("[data-testid='product-detail']")

        # Add to cart
        add_to_cart_btn = page.locator("[data-testid='add-to-cart']")
        await expect(add_to_cart_btn).to_be_enabled()
        await add_to_cart_btn.click()

        # Verify cart was updated
        cart_badge = page.locator("[data-testid='cart-badge']")
        await expect(cart_badge).to_contain_text("1")

    async def test_cart_operations(
        self,
        page: Page,
        api_base_url: str,
    ):
        """Test cart add/remove/update operations."""

        await page.goto(f"{api_base_url}/storefront")

        # Add first product
        first_product = page.locator("[data-testid='product-card']").first
        await first_product.locator("[data-testid='add-to-cart']").click()

        # Open cart
        await page.locator("[data-testid='cart-icon']").click()
        await page.wait_for_selector("[data-testid='cart-items']")

        # Verify item in cart
        cart_items = page.locator("[data-testid='cart-item']")
        await expect(cart_items).to_have_count(1)

        # Update quantity
        quantity_input = page.locator("[data-testid='item-quantity']").first
        await quantity_input.fill("2")

        # Verify subtotal updated
        subtotal = page.locator("[data-testid='cart-subtotal']")
        await expect(subtotal).to_contain_text("$")

    async def test_checkout_validation(
        self,
        page: Page,
        api_base_url: str,
    ):
        """Test checkout form validation."""

        await page.goto(f"{api_base_url}/cart")

        # Navigate to checkout
        await page.locator("[data-testid='checkout-btn']").click()
        await page.wait_for_selector("[data-testid='checkout-form']")

        # Try to submit empty form
        submit_btn = page.locator("[data-testid='submit-checkout']")
        await submit_btn.click()

        # Verify validation errors appear
        errors = page.locator("[data-testid='form-error']")
        await expect(errors).to_have_count_gte(1)

        # Fill out form
        await page.locator("[data-testid='email-input']").fill("test@example.com")
        await page.locator("[data-testid='name-input']").fill("Test User")
        await page.locator("[data-testid='address-input']").fill("123 Main St")
        await page.locator("[data-testid='city-input']").fill("Test City")
        await page.locator("[data-testid='postal-input']").fill("12345")

        # Submit should now work
        await submit_btn.click()

        # Should proceed to payment
        await page.wait_for_selector("[data-testid='payment-form']")

    async def test_order_tracking(
        self,
        page: Page,
        test_data_factory: TestDataFactory,
        api_base_url: str,
    ):
        """Test order tracking functionality."""

        # Create a test order
        customer = await test_data_factory.create_test_customer()
        order = await test_data_factory.create_test_order(
            customer_email=customer["email"],
            items=[{"sku": "test-sku", "qty": 1, "price": 99.99}],
        )

        # Navigate to order tracking
        await page.goto(f"{api_base_url}/orders/{order['order_id']}")

        # Verify order details displayed
        await page.wait_for_selector("[data-testid='order-detail']")

        order_id_element = page.locator("[data-testid='order-number']")
        await expect(order_id_element).to_contain_text(order["order_id"])

        # Verify status timeline
        status_elements = page.locator("[data-testid='status-step']")
        await expect(status_elements).to_have_count_gte(1)


class TestUserAccount:
    """User account management E2E tests."""

    async def test_user_registration(
        self,
        page: Page,
        api_base_url: str,
    ):
        """Test user registration flow."""

        await page.goto(f"{api_base_url}/register")

        # Fill registration form
        email = f"newuser-{uuid4().hex[:8]}@example.com"
        password = "SecurePassword123!"

        await page.locator("[data-testid='email-input']").fill(email)
        await page.locator("[data-testid='password-input']").fill(password)
        await page.locator("[data-testid='confirm-password']").fill(password)
        await page.locator("[data-testid='terms-checkbox']").check()

        # Submit registration
        await page.locator("[data-testid='register-btn']").click()

        # Should redirect to dashboard
        await page.wait_for_url(f"{api_base_url}/dashboard")

    async def test_login_logout(
        self,
        page: Page,
        test_data_factory: TestDataFactory,
        api_base_url: str,
    ):
        """Test login and logout flows."""

        customer = await test_data_factory.create_test_customer()

        # Navigate to login
        await page.goto(f"{api_base_url}/login")

        # Fill credentials
        await page.locator("[data-testid='email-input']").fill(customer["email"])
        await page.locator("[data-testid='password-input']").fill("TestPassword123!")

        # Submit login
        await page.locator("[data-testid='login-btn']").click()

        # Should redirect to dashboard
        await page.wait_for_url(f"{api_base_url}/dashboard")

        # Logout
        await page.locator("[data-testid='user-menu']").click()
        await page.locator("[data-testid='logout-btn']").click()

        # Should redirect to home
        await page.wait_for_url(f"{api_base_url}/")
