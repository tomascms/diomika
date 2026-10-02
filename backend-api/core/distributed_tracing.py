"""Distributed tracing with OpenTelemetry."""
import logging
from typing import Optional, Dict, Any
from datetime import datetime
import time

logger = logging.getLogger("diomika-api")


class Span:
    """Represents a tracing span."""

    def __init__(self, name: str, span_id: str, parent_span_id: Optional[str] = None):
        self.name = name
        self.span_id = span_id
        self.parent_span_id = parent_span_id
        self.attributes: Dict[str, Any] = {}
        self.events: list = []
        self.start_time = time.time()
        self.end_time: Optional[float] = None
        self.status = "UNSET"
        self.error: Optional[str] = None

    def set_attribute(self, key: str, value: Any):
        """Set span attribute."""
        self.attributes[key] = value

    def add_event(self, name: str, attributes: Optional[Dict[str, Any]] = None):
        """Add event to span."""
        event = {
            "name": name,
            "timestamp": datetime.utcnow().isoformat(),
            "attributes": attributes or {},
        }
        self.events.append(event)

    def set_status(self, status: str, error: Optional[str] = None):
        """Set span status."""
        self.status = status
        if error:
            self.error = error

    def end(self):
        """End the span."""
        self.end_time = time.time()

    def duration_ms(self) -> float:
        """Get span duration in milliseconds."""
        if not self.end_time:
            return 0
        return (self.end_time - self.start_time) * 1000

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "span_id": self.span_id,
            "parent_span_id": self.parent_span_id,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "duration_ms": self.duration_ms(),
            "attributes": self.attributes,
            "events": self.events,
            "status": self.status,
            "error": self.error,
        }


class Trace:
    """Represents a distributed trace."""

    def __init__(self, trace_id: str, root_span_name: str):
        self.trace_id = trace_id
        self.spans: Dict[str, Span] = {}
        self.root_span_id: Optional[str] = None

    def create_span(
        self,
        name: str,
        span_id: str,
        parent_span_id: Optional[str] = None
    ) -> Span:
        """Create a span in this trace."""
        span = Span(name, span_id, parent_span_id)
        self.spans[span_id] = span

        if parent_span_id is None:
            self.root_span_id = span_id

        logger.debug(f"Created span {span_id} ({name})")
        return span

    def get_span(self, span_id: str) -> Optional[Span]:
        """Get a span by ID."""
        return self.spans.get(span_id)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "trace_id": self.trace_id,
            "root_span_id": self.root_span_id,
            "spans": {span_id: span.to_dict() for span_id, span in self.spans.items()},
        }


class TracingContext:
    """Context for tracing."""

    def __init__(self, trace_id: str, span_id: str):
        self.trace_id = trace_id
        self.span_id = span_id
        self.parent_span_id: Optional[str] = None

    def to_headers(self) -> Dict[str, str]:
        """Convert to HTTP headers for propagation."""
        return {
            "X-Trace-ID": self.trace_id,
            "X-Span-ID": self.span_id,
            "X-Parent-Span-ID": self.parent_span_id or "",
        }

    @classmethod
    def from_headers(cls, headers: Dict[str, str]) -> "TracingContext":
        """Create from HTTP headers."""
        import uuid
        trace_id = headers.get("X-Trace-ID", str(uuid.uuid4()))
        span_id = headers.get("X-Span-ID", str(uuid.uuid4()))
        parent_span_id = headers.get("X-Parent-Span-ID") or None

        context = cls(trace_id, span_id)
        context.parent_span_id = parent_span_id
        return context


class Tracer:
    """Main tracer for distributed tracing."""

    def __init__(self):
        self.traces: Dict[str, Trace] = {}
        self.active_spans: Dict[str, Span] = {}

    def create_trace(self, trace_id: str, root_span_name: str = "root") -> Trace:
        """Create a new trace."""
        trace = Trace(trace_id, root_span_name)
        self.traces[trace_id] = trace
        logger.debug(f"Created trace {trace_id}")
        return trace

    def get_trace(self, trace_id: str) -> Optional[Trace]:
        """Get a trace by ID."""
        return self.traces.get(trace_id)

    def start_span(
        self,
        trace_id: str,
        span_name: str,
        span_id: Optional[str] = None,
        parent_span_id: Optional[str] = None
    ) -> Span:
        """Start a new span."""
        import uuid
        span_id = span_id or str(uuid.uuid4())

        trace = self.get_trace(trace_id)
        if not trace:
            trace = self.create_trace(trace_id)

        span = trace.create_span(span_name, span_id, parent_span_id)
        self.active_spans[span_id] = span

        return span

    def end_span(self, span_id: str, status: str = "OK", error: Optional[str] = None):
        """End a span."""
        span = self.active_spans.get(span_id)
        if span:
            span.set_status(status, error)
            span.end()
            logger.debug(f"Ended span {span_id} ({span.name}) - duration: {span.duration_ms():.2f}ms")
            del self.active_spans[span_id]

    def export_trace(self, trace_id: str) -> Optional[Dict[str, Any]]:
        """Export a complete trace."""
        trace = self.get_trace(trace_id)
        if not trace:
            return None
        return trace.to_dict()


class SpanContextManager:
    """Manages span context for async operations."""

    def __init__(self, tracer: Tracer):
        self.tracer = tracer
        self.context_stack: list = []

    def push_context(self, trace_id: str, span_id: str, parent_span_id: Optional[str] = None):
        """Push a new context."""
        context = {
            "trace_id": trace_id,
            "span_id": span_id,
            "parent_span_id": parent_span_id,
        }
        self.context_stack.append(context)

    def pop_context(self) -> Optional[Dict[str, str]]:
        """Pop the current context."""
        if self.context_stack:
            return self.context_stack.pop()
        return None

    def current_context(self) -> Optional[Dict[str, str]]:
        """Get the current context."""
        if self.context_stack:
            return self.context_stack[-1]
        return None


class TracingMiddleware:
    """Middleware for automatic tracing."""

    def __init__(self, tracer: Tracer):
        self.tracer = tracer

    async def __call__(self, scope, receive, send):
        """ASGI middleware for tracing."""
        from starlette.requests import Request

        if scope["type"] != "http":
            await send(scope)
            return

        request = Request(scope)

        # Extract tracing context from headers
        trace_id = request.headers.get("X-Trace-ID") or str(__import__("uuid").uuid4())
        parent_span_id = request.headers.get("X-Parent-Span-ID")

        # Create span for request
        span = self.tracer.start_span(
            trace_id=trace_id,
            span_name=f"{request.method} {request.url.path}",
            parent_span_id=parent_span_id,
        )

        # Add request attributes
        span.set_attribute("http.method", request.method)
        span.set_attribute("http.url", str(request.url))
        span.set_attribute("http.target", request.url.path)

        try:
            # Call next middleware
            await send(scope)
            span.set_status("OK")

        except Exception as e:
            span.set_status("ERROR", str(e))
            raise

        finally:
            self.tracer.end_span(span.span_id)

        # Add tracing headers to response
        scope["trace_id"] = trace_id
        scope["span_id"] = span.span_id


# Global tracer
_tracer: Optional[Tracer] = None


def get_tracer() -> Tracer:
    """Get global tracer."""
    global _tracer
    if _tracer is None:
        _tracer = Tracer()
    return _tracer


def get_span_context_manager() -> SpanContextManager:
    """Get span context manager."""
    return SpanContextManager(get_tracer())
