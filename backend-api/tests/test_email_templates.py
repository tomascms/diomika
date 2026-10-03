"""Unit tests for email template rendering."""
import pytest
from datetime import datetime
from decimal import Decimal

from core.email_templates import (
    render_order_confirmation,
    render_payment_confirmation,
    render_shipping_notification,
    render_refund_notification,
    render_2fa_verification,
)


class TestEmailTemplates:
    """Test email template rendering."""

    def test_order_confirmation_basic(self):
        """Test order confirmation email rendering."""
        html = render_order_confirmation(
            order_id="ORD-001",
            customer_name="John Doe",
            order_date=datetime(2024, 1, 15),
            items=[
                {"description": "Test Product", "quantity": 1, "unit_price": Decimal("99.99")}
            ],
            subtotal=Decimal("99.99"),
            tax=Decimal("22.99"),
            shipping=Decimal("10.00"),
            total=Decimal("132.98"),
            shipping_address="123 Main St\nTest City, 12345",
        )

        assert "<!DOCTYPE html>" in html
        assert "John Doe" in html
        assert "ORD-001" in html
        assert "Order Confirmed" in html or "Confirmed" in html
        assert "Test Product" in html
        assert "$99.99" in html or "99.99" in html

    def test_order_confirmation_with_tracking(self):
        """Test order confirmation with tracking URL."""
        html = render_order_confirmation(
            order_id="ORD-002",
            customer_name="Jane Smith",
            order_date=datetime(2024, 1, 15),
            items=[],
            subtotal=Decimal("0"),
            tax=Decimal("0"),
            shipping=Decimal("0"),
            total=Decimal("0"),
            shipping_address="Test",
            tracking_url="https://tracking.example.com/track/ORD-002",
        )

        assert "Track Your Order" in html
        assert "tracking.example.com" in html

    def test_payment_confirmation(self):
        """Test payment confirmation email."""
        html = render_payment_confirmation(
            order_id="ORD-003",
            customer_name="Bob Johnson",
            amount=Decimal("199.99"),
            payment_method="credit_card",
            transaction_id="TXN-12345",
        )

        assert "<!DOCTYPE html>" in html
        assert "Payment Confirmed" in html or "Confirmed" in html
        assert "Bob Johnson" in html
        assert "199.99" in html
        assert "TXN-12345" in html

    def test_shipping_notification(self):
        """Test shipping notification email."""
        html = render_shipping_notification(
            order_id="ORD-004",
            customer_name="Alice Brown",
            carrier="FedEx",
            tracking_number="1234567890",
            tracking_url="https://fedex.com/track/1234567890",
            estimated_delivery="January 20, 2024",
        )

        assert "On the Way" in html or "Way" in html
        assert "Alice Brown" in html
        assert "FedEx" in html
        assert "1234567890" in html
        assert "Track" in html

    def test_refund_notification(self):
        """Test refund notification email."""
        html = render_refund_notification(
            order_id="ORD-005",
            customer_name="Charlie Davis",
            refund_amount=Decimal("299.99"),
            reason="Customer requested refund",
            estimated_date="January 25, 2024",
        )

        assert "Refund Initiated" in html or "Refund" in html
        assert "Charlie Davis" in html
        assert "299.99" in html
        assert "Customer requested refund" in html

    def test_2fa_verification(self):
        """Test 2FA verification code email."""
        html = render_2fa_verification(
            customer_name="Eve Wilson", code="123456", valid_for_minutes=10
        )

        assert "Verification Code" in html or "Code" in html
        assert "Eve Wilson" in html
        assert "123456" in html
        assert "10 minutes" in html

    def test_email_html_valid_structure(self):
        """Test that rendered HTML has valid structure."""
        html = render_order_confirmation(
            order_id="TEST",
            customer_name="Test",
            order_date=datetime.now(),
            items=[],
            subtotal=Decimal("0"),
            tax=Decimal("0"),
            shipping=Decimal("0"),
            total=Decimal("0"),
            shipping_address="Test",
        )

        assert html.count("<html>") == 1 or html.count("<HTML>") == 1
        assert html.count("</html>") == 1 or html.count("</HTML>") == 1
        assert "<head>" in html.lower()
        assert "<body>" in html.lower()

    def test_email_responsive_design(self):
        """Test that emails have responsive design meta tags."""
        html = render_order_confirmation(
            order_id="TEST",
            customer_name="Test",
            order_date=datetime.now(),
            items=[],
            subtotal=Decimal("0"),
            tax=Decimal("0"),
            shipping=Decimal("0"),
            total=Decimal("0"),
            shipping_address="Test",
        )

        assert "viewport" in html.lower()
        assert "utf-8" in html.lower() or "utf8" in html.lower()

    def test_email_styling_included(self):
        """Test that emails have CSS styling."""
        html = render_order_confirmation(
            order_id="TEST",
            customer_name="Test",
            order_date=datetime.now(),
            items=[],
            subtotal=Decimal("0"),
            tax=Decimal("0"),
            shipping=Decimal("0"),
            total=Decimal("0"),
            shipping_address="Test",
        )

        assert "<style>" in html
        assert "font-family" in html

    def test_payment_confirmation_security(self):
        """Test that payment confirmation doesn't leak sensitive data."""
        html = render_payment_confirmation(
            order_id="TEST",
            customer_name="Test",
            amount=Decimal("100"),
            payment_method="credit_card",
            transaction_id="secret123",
        )

        # Should not contain full card details
        assert "4532" not in html  # No credit card numbers
        assert "Security Notice" in html or "security" in html.lower()

    def test_2fa_security_warning(self):
        """Test that 2FA email includes security warning."""
        html = render_2fa_verification(customer_name="Test", code="123456")

        assert "Security" in html or "security" in html.lower()
        assert "never share" in html.lower() or "never" in html.lower()
        assert "employee" in html.lower()
