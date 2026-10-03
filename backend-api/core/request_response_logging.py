"""Request/Response logging middleware."""
import logging
import json
import time
from typing import Optional, Dict, Any, Callable
from datetime import datetime
from functools import wraps

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger("diomika-api")


class RequestResponseLog:
    """Represents a logged request/response."""

    def __init__(self, request_id: str):
        self.request_id = request_id
        self.timestamp = datetime.utcnow()

        # Request info
        self.method: Optional[str] = None
        self.path: Optional[str] = None
        self.query_params: Dict[str, Any] = {}
        self.headers: Dict[str, str] = {}
        self.body: Optional[str] = None
        self.user_id: Optional[str] = None

        # Response info
        self.status_code: Optional[int] = None
        self.response_headers: Dict[str, str] = {}
        self.response_body: Optional[str] = None
        self.duration_ms: Optional[float] = None

        # Additional
        self.error: Optional[str] = None
        self.client_ip: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "request_id": self.request_id,
            "timestamp": self.timestamp.isoformat(),
            "method": self.method,
            "path": self.path,
            "query_params": self.query_params,
            "status_code": self.status_code,
            "duration_ms": self.duration_ms,
            "client_ip": self.client_ip,
            "user_id": self.user_id,
            "error": self.error,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict())


class RequestResponseLogger:
    """Logger for request/response cycles."""

    def __init__(self, max_body_size: int = 10000):
        self.logs: Dict[str, RequestResponseLog] = {}
        self.max_body_size = max_body_size
        self.sensitive_headers = {
            "authorization", "x-api-key", "cookie", "set-cookie"
        }

    def _redact_headers(self, headers: Dict[str, str]) -> Dict[str, str]:
        """Redact sensitive headers."""
        redacted = {}
        for key, value in headers.items():
            if key.lower() in self.sensitive_headers:
                redacted[key] = "***REDACTED***"
            else:
                redacted[key] = value
        return redacted

    def _truncate_body(self, body: str) -> str:
        """Truncate body if too large."""
        if len(body) > self.max_body_size:
            return body[:self.max_body_size] + f"... (truncated {len(body) - self.max_body_size} bytes)"
        return body

    def create_request_log(self, request_id: str) -> RequestResponseLog:
        """Create a new request log."""
        log = RequestResponseLog(request_id)
        self.logs[request_id] = log
        return log

    def get_log(self, request_id: str) -> Optional[RequestResponseLog]:
        """Get a log by request ID."""
        return self.logs.get(request_id)

    async def log_request(self, request: Request, log: RequestResponseLog):
        """Log request details."""
        log.method = request.method
        log.path = request.url.path
        log.query_params = dict(request.query_params)
        log.client_ip = request.client.host if request.client else None

        # Log headers (redacted)
        headers_dict = dict(request.headers)
        log.headers = self._redact_headers(headers_dict)

        # Log user ID if available
        log.user_id = getattr(request.state, "user_id", None)

        # Try to log body
        try:
            body = await request.body()
            if body:
                try:
                    log.body = self._truncate_body(body.decode())
                except:
                    log.body = f"<binary data: {len(body)} bytes>"
        except Exception as e:
            logger.debug(f"Could not log request body: {e}")

        logger.info(f"[{log.request_id}] {log.method} {log.path} from {log.client_ip}")

    def log_response(
        self,
        request_id: str,
        status_code: int,
        response_headers: Dict[str, str],
        duration_ms: float,
        response_body: Optional[str] = None,
    ):
        """Log response details."""
        log = self.logs.get(request_id)
        if not log:
            return

        log.status_code = status_code
        log.response_headers = self._redact_headers(response_headers)
        log.duration_ms = duration_ms

        if response_body:
            log.response_body = self._truncate_body(response_body)

        logger.info(f"[{request_id}] {log.method} {log.path} -> {status_code} ({duration_ms:.2f}ms)")

    def log_error(self, request_id: str, error: str):
        """Log error."""
        log = self.logs.get(request_id)
        if log:
            log.error = error
            logger.error(f"[{request_id}] Error: {error}")

    def get_logs(self, limit: int = 100) -> list:
        """Get recent logs."""
        return list(self.logs.values())[-limit:]


class RequestResponseLoggingMiddleware(BaseHTTPMiddleware):
    """Middleware to log all requests and responses."""

    def __init__(self, app, logger_instance: Optional[RequestResponseLogger] = None):
        super().__init__(app)
        self.logger_instance = logger_instance or RequestResponseLogger()

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Intercept request/response and log."""
        request_id = getattr(request.state, "request_id", None) or str(__import__("uuid").uuid4())
        request.state.request_id = request_id

        # Create log
        log = self.logger_instance.create_request_log(request_id)

        start_time = time.time()

        try:
            # Log request
            await self.logger_instance.log_request(request, log)

            # Process request
            response = await call_next(request)

            # Log response
            duration_ms = (time.time() - start_time) * 1000
            response_headers = dict(response.headers)

            self.logger_instance.log_response(
                request_id,
                response.status_code,
                response_headers,
                duration_ms,
            )

            # Add request ID to response headers
            response.headers["X-Request-ID"] = request_id

            return response

        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            self.logger_instance.log_error(request_id, str(e))
            raise


class StructuredLoggingFormatter:
    """Formats logs as structured JSON."""

    @staticmethod
    def format_request_log(log: RequestResponseLog) -> str:
        """Format as JSON."""
        return json.dumps({
            "level": "INFO",
            "timestamp": log.timestamp.isoformat(),
            "type": "http_request",
            "request_id": log.request_id,
            "method": log.method,
            "path": log.path,
            "status_code": log.status_code,
            "duration_ms": log.duration_ms,
            "client_ip": log.client_ip,
            "user_id": log.user_id,
        })


def log_function_call(func: Callable) -> Callable:
    """Decorator to log function calls."""
    @wraps(func)
    async def wrapper(*args, **kwargs):
        func_name = func.__name__
        logger.debug(f"Calling {func_name} with args={args}, kwargs={kwargs}")

        start_time = time.time()
        try:
            result = await func(*args, **kwargs)
            duration_ms = (time.time() - start_time) * 1000
            logger.debug(f"{func_name} completed in {duration_ms:.2f}ms")
            return result
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            logger.error(f"{func_name} failed after {duration_ms:.2f}ms: {e}")
            raise

    return wrapper


# Global logger
_request_response_logger: Optional[RequestResponseLogger] = None


def get_request_response_logger() -> RequestResponseLogger:
    """Get global request/response logger."""
    global _request_response_logger
    if _request_response_logger is None:
        _request_response_logger = RequestResponseLogger()
    return _request_response_logger
