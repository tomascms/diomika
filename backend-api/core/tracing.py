"""Distributed tracing with OpenTelemetry."""
from __future__ import annotations

import os
from typing import Optional

from opentelemetry import trace
from opentelemetry.exporter.jaeger.thrift import JaegerExporter
from opentelemetry.sdk.resources import SERVICE_NAME, Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
from opentelemetry.instrumentation.requests import RequestsInstrumentor
from opentelemetry.instrumentation.redis import RedisInstrumentor

_tracer: Optional[trace.Tracer] = None
_initialized = False


def initialize_tracing(service_name: str = "diomika-backend") -> None:
    """Initialize distributed tracing with OpenTelemetry.

    Configures:
    - Jaeger exporter (if JAEGER_ENDPOINT configured)
    - FastAPI instrumentation
    - SQLAlchemy instrumentation
    - Redis instrumentation
    - HTTP requests instrumentation
    """
    global _tracer, _initialized

    if _initialized:
        return

    # Skip if tracing disabled
    if os.getenv("ENABLE_TRACING", "false").lower() != "true":
        return

    # Create resource
    resource = Resource(attributes={
        SERVICE_NAME: service_name,
        "environment": os.getenv("ENVIRONMENT", "development"),
        "version": os.getenv("APP_VERSION", "0.0.1"),
    })

    # Create tracer provider
    jaeger_exporter = JaegerExporter(
        agent_host_name=os.getenv("JAEGER_HOST", "localhost"),
        agent_port=int(os.getenv("JAEGER_PORT", "6831")),
    )

    tracer_provider = TracerProvider(resource=resource)
    tracer_provider.add_span_processor(BatchSpanProcessor(jaeger_exporter))
    trace.set_tracer_provider(tracer_provider)

    # Get tracer
    _tracer = trace.get_tracer(__name__)

    # Instrument libraries
    FastAPIInstrumentor.instrument_app(app=None)  # Passed to app directly
    SQLAlchemyInstrumentor().instrument()
    RequestsInstrumentor().instrument()
    RedisInstrumentor().instrument()

    _initialized = True


def get_tracer() -> trace.Tracer:
    """Get the global tracer instance."""
    if _tracer is None:
        raise RuntimeError("Tracing not initialized. Call initialize_tracing() first.")
    return _tracer


def create_span(name: str, attributes: dict | None = None) -> trace.Span:
    """Create a new span with optional attributes.

    Usage:
        with create_span("operation_name", {"user_id": "123"}) as span:
            # Do work
            span.set_attribute("result", "success")
    """
    tracer = get_tracer()
    span = tracer.start_span(name)

    if attributes:
        for key, value in attributes.items():
            span.set_attribute(key, value)

    return span


def record_exception(span: trace.Span, exception: Exception) -> None:
    """Record exception in span."""
    span.record_exception(exception)
    span.set_attribute("error", True)


class TracingContext:
    """Context manager for distributed tracing."""

    def __init__(self, name: str, attributes: dict | None = None):
        self.name = name
        self.attributes = attributes or {}
        self.span = None

    def __enter__(self) -> trace.Span:
        tracer = get_tracer()
        self.span = tracer.start_span(self.name)

        for key, value in self.attributes.items():
            self.span.set_attribute(key, value)

        return self.span

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None:
            record_exception(self.span, exc_val)
        self.span.end()
