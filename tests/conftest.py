"""Pytest configuration and shared fixtures for all tests."""
import os
import asyncio
from datetime import datetime
from decimal import Decimal
import pytest
from unittest.mock import Mock, patch, MagicMock


@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def mock_db():
    """Mock database connection."""
    db = MagicMock()
    db.table = MagicMock(return_value=MagicMock())
    db.execute = MagicMock()
    return db


@pytest.fixture
def mock_s3_client():
    """Mock S3 client for invoice uploads."""
    client = MagicMock()
    client.put_object = MagicMock(return_value={"ETag": "fake-etag"})
    client.get_object = MagicMock()
    return client


@pytest.fixture
def sample_order_data():
    """Sample order data for testing."""
    return {
        "id": "order-001",
        "customer_name": "John Doe",
        "customer_email": "john@example.com",
        "customer_phone": "+351 910000000",
        "customer_address": "123 Main St, Lisbon, PT",
        "lines": [
            {
                "ean": "5901234123457",
                "quantity": 2,
                "price": 49.99,
                "color_code": "RED",
                "size": "M"
            }
        ],
        "status": "pending",
        "total_amount": 99.98,
        "created_by": "user-123",
        "created_at": datetime.utcnow().isoformat(),
        "visibilidade": True,
    }


@pytest.fixture
def sample_customer_data():
    """Sample customer data for saga testing."""
    return {
        "name": "Jane Smith",
        "email": "jane@example.com",
        "phone": "+351 920000000",
        "address": "456 Oak Ave, Porto, PT",
    }


@pytest.fixture
def sample_order_lines():
    """Sample order lines for saga testing."""
    from core.saga.order_saga import OrderLine
    return [
        OrderLine(
            ean="5901234123457",
            quantity=2,
            price=Decimal("49.99"),
            color_code="RED",
            size="M"
        ),
        OrderLine(
            ean="5901234123458",
            quantity=1,
            price=Decimal("29.99"),
            color_code="BLUE",
            size="L"
        ),
    ]


@pytest.fixture
def mock_invoice_generator():
    """Mock invoice generator."""
    generator = MagicMock()
    generator.generate_invoice_pdf = MagicMock(
        return_value=b"PDF_BYTES_PLACEHOLDER"
    )
    return generator


@pytest.fixture
def mock_email_sender():
    """Mock email sender utility."""
    sender = MagicMock()
    sender.send_email_async = MagicMock(return_value=True)
    return sender


@pytest.fixture
def audit_retention_stats():
    """Sample audit retention statistics."""
    return {
        "total_logs": 50000,
        "total_archived": 10000,
        "retention_days": 365,
        "action_distribution": {
            "CREATE": 15000,
            "UPDATE": 20000,
            "DELETE": 5000,
            "READ": 10000,
        },
        "result_distribution": {
            "SUCCESS": 45000,
            "FAILURE": 5000,
        },
        "age_distribution": {
            "today": 500,
            "last_7_days": 5000,
            "last_30_days": 20000,
            "last_90_days": 35000,
            "older": 15000,
        },
    }


@pytest.fixture(autouse=True)
def reset_mocks():
    """Reset mocks before each test."""
    yield
    Mock.reset_mock()


@pytest.fixture
def patched_get_db(mock_db):
    """Patch get_db function globally."""
    with patch("core.database.get_db", return_value=mock_db):
        yield mock_db


@pytest.fixture
def patched_get_invoice_generator(mock_invoice_generator):
    """Patch invoice generator globally."""
    with patch("core.invoice_generator.get_invoice_generator", return_value=mock_invoice_generator):
        yield mock_invoice_generator


@pytest.fixture
def patched_send_email_async(mock_email_sender):
    """Patch email sender globally."""
    with patch("utils.email_sender.send_email_async", return_value=True):
        yield True


@pytest.fixture
def patched_boto3_s3():
    """Patch boto3 S3 client."""
    mock_s3 = MagicMock()
    mock_s3.put_object = MagicMock()
    mock_s3.get_object = MagicMock()
    with patch("boto3.client", return_value=mock_s3):
        yield mock_s3


@pytest.fixture
def patched_outbox_enqueue():
    """Patch outbox event enqueue."""
    with patch("core.outbox.enqueue_event", return_value=None):
        yield


@pytest.fixture
def patched_saga_log():
    """Patch saga logging function."""
    with patch("core.saga.logging.saga_log"):
        yield


def pytest_configure(config):
    """Configure pytest with custom markers."""
    config.addinivalue_line(
        "markers", "unit: mark test as unit test"
    )
    config.addinivalue_line(
        "markers", "integration: mark test as integration test"
    )
    config.addinivalue_line(
        "markers", "e2e: mark test as end-to-end test"
    )
    config.addinivalue_line(
        "markers", "slow: mark test as slow running"
    )
    config.addinivalue_line(
        "markers", "security: mark test as security test"
    )
