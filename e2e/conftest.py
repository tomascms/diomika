"""E2E test configuration with database fixtures."""
import os
import pytest
import asyncio
from datetime import datetime
from decimal import Decimal
from unittest.mock import patch, MagicMock


@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async E2E tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def db_connection():
    """Database connection fixture for E2E tests."""
    mock_db = MagicMock()

    # Simulate table operations
    mock_table = MagicMock()
    mock_db.table = MagicMock(return_value=mock_table)

    # Simulate insert response
    mock_table.insert = MagicMock(return_value=MagicMock(
        execute=MagicMock(return_value=MagicMock(
            data=[{"id": "order-123"}]
        ))
    ))

    # Simulate select response
    mock_table.select = MagicMock(return_value=MagicMock(
        eq=MagicMock(return_value=MagicMock(
            execute=MagicMock(return_value=MagicMock(
                data=[{"quantity": 100}]
            ))
        ))
    ))

    # Simulate update response
    mock_table.update = MagicMock(return_value=MagicMock(
        eq=MagicMock(return_value=MagicMock(
            execute=MagicMock(return_value=MagicMock(
                data=[{"id": "order-123"}]
            ))
        ))
    ))

    return mock_db


@pytest.fixture
def api_client():
    """API client for E2E tests."""
    from httpx import AsyncClient
    return AsyncClient(base_url="http://localhost:8000")


@pytest.fixture
def test_user_id():
    """Test user ID for E2E tests."""
    return "test-user-123"


@pytest.fixture
def test_customer_data():
    """Test customer data for E2E order flow."""
    return {
        "name": "E2E Test Customer",
        "email": "e2e-test@diomika.pt",
        "phone": "+351 912345678",
        "address": "Test Street 123, Test City, PT",
    }


@pytest.fixture
def test_order_lines():
    """Test order lines for E2E order flow."""
    from core.saga.order_saga import OrderLine
    return [
        OrderLine(
            ean="5901234123457",
            quantity=1,
            price=Decimal("99.99"),
            color_code="BLACK",
            size="M"
        ),
    ]


@pytest.fixture
def test_order_payload(test_customer_data, test_order_lines):
    """Complete order payload for E2E testing."""
    return {
        "customer": test_customer_data,
        "lines": [
            {
                "ean": line.ean,
                "quantity": line.quantity,
                "price": float(line.price),
                "color_code": line.color_code,
                "size": line.size,
            }
            for line in test_order_lines
        ],
    }


@pytest.fixture
def s3_bucket():
    """S3 bucket name for E2E tests."""
    return "diomika-invoices"


@pytest.fixture(autouse=True)
def mock_aws_credentials(monkeypatch):
    """Mock AWS credentials for E2E tests."""
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing")
    monkeypatch.setenv("AWS_SECURITY_TOKEN", "testing")
    monkeypatch.setenv("AWS_SESSION_TOKEN", "testing")
    monkeypatch.setenv("AWS_DEFAULT_REGION", "eu-west-1")


@pytest.fixture(autouse=True)
def mock_email_service():
    """Mock email service for E2E tests."""
    with patch("utils.email_sender.send_email_async", return_value=True):
        yield


@pytest.fixture(autouse=True)
def mock_s3_service():
    """Mock S3 service for E2E tests."""
    mock_s3 = MagicMock()
    mock_s3.put_object = MagicMock()
    mock_s3.get_object = MagicMock(return_value={
        "Body": MagicMock(read=MagicMock(return_value=b"PDF_CONTENT"))
    })

    with patch("boto3.client", return_value=mock_s3):
        yield mock_s3


@pytest.fixture
def audit_trail_data():
    """Sample audit trail data for verification."""
    return {
        "id": 1,
        "action": "CREATE",
        "result": "SUCCESS",
        "user_id": "test-user-123",
        "resource_type": "order",
        "resource_id": "order-123",
        "request_id": "req-123",
        "ip_address": "127.0.0.1",
        "error_message": None,
        "old_values": None,
        "new_values": {"status": "pending"},
        "details": {"order_lines": 1},
        "created_at": datetime.utcnow().isoformat(),
    }


@pytest.fixture
def invoice_data():
    """Sample invoice data for verification."""
    return {
        "order_id": "order-123",
        "invoice_url": "https://diomika-invoices.s3.amazonaws.com/invoices/order-123.pdf",
        "invoice_generated_at": datetime.utcnow().isoformat(),
    }


@pytest.fixture
def order_completion_event():
    """Sample order completion event for event verification."""
    return {
        "event_type": "order.completed",
        "payload": {
            "order_id": "order-123",
            "saga_id": "saga-123",
            "customer_email": "e2e-test@diomika.pt",
            "lines_count": 1,
            "inventory_reserved": True,
            "invoice_generated": True,
            "email_sent": True,
            "timestamp": datetime.utcnow().isoformat(),
        },
    }


def pytest_configure(config):
    """Configure E2E test markers."""
    config.addinivalue_line(
        "markers", "e2e: mark test as end-to-end test"
    )
    config.addinivalue_line(
        "markers", "order_flow: mark test as order flow test"
    )
    config.addinivalue_line(
        "markers", "payment_flow: mark test as payment flow test"
    )
    config.addinivalue_line(
        "markers", "invoice_generation: mark test as invoice generation test"
    )
    config.addinivalue_line(
        "markers", "notification: mark test as notification test"
    )
    config.addinivalue_line(
        "markers", "slow: mark test as slow running"
    )
