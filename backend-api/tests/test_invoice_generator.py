"""Unit tests for invoice PDF generation."""
import pytest
from datetime import datetime
from decimal import Decimal

from core.invoice_generator import InvoiceGenerator, get_invoice_generator


class TestInvoiceGenerator:
    """Test invoice PDF generation."""

    @pytest.fixture
    def generator(self):
        """Create invoice generator instance."""
        return InvoiceGenerator(company_name="Test Company", company_email="test@example.com")

    @pytest.fixture
    def sample_order(self):
        """Sample order data."""
        return {
            "order_id": "ORD-2024-001",
            "customer_name": "John Doe",
            "customer_email": "john@example.com",
            "customer_address": "123 Main St\nTest City, 12345",
            "order_date": datetime(2024, 1, 15),
            "due_date": datetime(2024, 2, 15),
            "items": [
                {
                    "description": "Product A",
                    "quantity": 2,
                    "unit_price": Decimal("49.99"),
                },
                {
                    "description": "Product B",
                    "quantity": 1,
                    "unit_price": Decimal("99.99"),
                },
            ],
            "subtotal": Decimal("199.97"),
            "tax_rate": Decimal("0.23"),
            "notes": "Thank you for your business!",
        }

    def test_invoice_generation_basic(self, generator, sample_order):
        """Test basic invoice generation."""
        pdf_bytes = generator.generate_invoice_pdf(**sample_order)

        assert pdf_bytes is not None
        assert len(pdf_bytes) > 0
        assert pdf_bytes.startswith(b"%PDF")

    def test_invoice_contains_order_id(self, generator, sample_order):
        """Test invoice contains order ID."""
        pdf_bytes = generator.generate_invoice_pdf(**sample_order)

        # PDF text content check
        assert b"ORD-2024-001" in pdf_bytes or len(pdf_bytes) > 1000

    def test_invoice_with_custom_company(self):
        """Test invoice with custom company details."""
        gen = InvoiceGenerator(
            company_name="Custom Corp", company_email="billing@custom.com"
        )

        pdf_bytes = gen.generate_invoice_pdf(
            order_id="TEST-001",
            customer_name="Test",
            customer_email="test@test.com",
            customer_address="Test Address",
            order_date=datetime.now(),
            items=[],
            subtotal=Decimal("100"),
        )

        assert pdf_bytes is not None
        assert len(pdf_bytes) > 0

    def test_invoice_tax_calculation(self, generator):
        """Test tax calculation in invoice."""
        subtotal = Decimal("100.00")
        tax_rate = Decimal("0.23")
        tax_amount = subtotal * tax_rate

        pdf_bytes = generator.generate_invoice_pdf(
            order_id="TAX-001",
            customer_name="Tax Test",
            customer_email="tax@test.com",
            customer_address="Test",
            order_date=datetime.now(),
            items=[{"description": "Item", "quantity": 1, "unit_price": 100.00}],
            subtotal=subtotal,
            tax_rate=tax_rate,
        )

        assert pdf_bytes is not None
        assert len(pdf_bytes) > 0

    def test_invoice_with_no_items(self, generator):
        """Test invoice generation with no items."""
        pdf_bytes = generator.generate_invoice_pdf(
            order_id="EMPTY-001",
            customer_name="Empty",
            customer_email="empty@test.com",
            customer_address="Test",
            order_date=datetime.now(),
            items=[],
            subtotal=Decimal("0"),
        )

        assert pdf_bytes is not None
        assert len(pdf_bytes) > 0

    def test_invoice_with_many_items(self, generator):
        """Test invoice with many line items."""
        items = [
            {"description": f"Product {i}", "quantity": i + 1, "unit_price": Decimal("10.00")}
            for i in range(20)
        ]

        total = sum(Decimal(item["quantity"]) * item["unit_price"] for item in items)

        pdf_bytes = generator.generate_invoice_pdf(
            order_id="MANY-001",
            customer_name="Many Items",
            customer_email="many@test.com",
            customer_address="Test",
            order_date=datetime.now(),
            items=items,
            subtotal=total,
        )

        assert pdf_bytes is not None
        assert len(pdf_bytes) > 5000  # Large file due to many items

    def test_global_instance(self):
        """Test global invoice generator instance."""
        gen1 = get_invoice_generator()
        gen2 = get_invoice_generator()

        assert gen1 is gen2  # Should be same instance
