"""Prometheus metrics collection and export."""
from __future__ import annotations

from prometheus_client import Counter, Gauge, Histogram, CollectorRegistry

# Create custom registry
registry = CollectorRegistry()

# Request metrics
request_count = Counter(
    "http_requests_total",
    "Total HTTP requests",
    ["method", "endpoint", "status"],
    registry=registry,
)

request_duration = Histogram(
    "http_request_duration_seconds",
    "HTTP request duration in seconds",
    ["method", "endpoint"],
    buckets=(0.01, 0.05, 0.1, 0.5, 1.0, 2.5, 5.0),
    registry=registry,
)

request_size = Histogram(
    "http_request_size_bytes",
    "HTTP request size in bytes",
    ["method", "endpoint"],
    buckets=(100, 1000, 10000, 100000, 1000000),
    registry=registry,
)

response_size = Histogram(
    "http_response_size_bytes",
    "HTTP response size in bytes",
    ["method", "endpoint"],
    buckets=(100, 1000, 10000, 100000, 1000000),
    registry=registry,
)

# Database metrics
db_connection_pool_size = Gauge(
    "db_connection_pool_size",
    "Database connection pool size",
    registry=registry,
)

db_query_duration = Histogram(
    "db_query_duration_seconds",
    "Database query duration in seconds",
    ["operation"],
    buckets=(0.001, 0.01, 0.1, 0.5, 1.0),
    registry=registry,
)

db_query_errors = Counter(
    "db_query_errors_total",
    "Total database query errors",
    ["operation"],
    registry=registry,
)

# Business metrics
orders_created = Counter(
    "orders_created_total",
    "Total orders created",
    ["status"],
    registry=registry,
)

orders_completed = Counter(
    "orders_completed_total",
    "Total orders completed successfully",
    registry=registry,
)

invoices_generated = Counter(
    "invoices_generated_total",
    "Total invoices generated",
    registry=registry,
)

emails_sent = Counter(
    "emails_sent_total",
    "Total emails sent",
    ["type"],
    registry=registry,
)

saga_execution_duration = Histogram(
    "saga_execution_duration_seconds",
    "Order saga execution duration in seconds",
    ["saga_type"],
    buckets=(0.1, 0.5, 1.0, 2.0, 5.0, 10.0),
    registry=registry,
)

saga_failures = Counter(
    "saga_failures_total",
    "Total saga failures",
    ["saga_type", "reason"],
    registry=registry,
)

# Cache metrics
cache_hits = Counter(
    "cache_hits_total",
    "Total cache hits",
    ["cache_name"],
    registry=registry,
)

cache_misses = Counter(
    "cache_misses_total",
    "Total cache misses",
    ["cache_name"],
    registry=registry,
)

cache_size = Gauge(
    "cache_size_bytes",
    "Cache size in bytes",
    ["cache_name"],
    registry=registry,
)

# Authentication metrics
auth_attempts = Counter(
    "auth_attempts_total",
    "Total authentication attempts",
    ["result"],
    registry=registry,
)

active_sessions = Gauge(
    "active_sessions_total",
    "Total active sessions",
    registry=registry,
)

# System metrics
processing_queue_length = Gauge(
    "processing_queue_length",
    "Length of background processing queue",
    registry=registry,
)

active_workers = Gauge(
    "active_workers_total",
    "Total active background workers",
    registry=registry,
)
