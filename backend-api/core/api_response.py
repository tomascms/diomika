"""Standardized API response formatting."""
from __future__ import annotations

import logging
from enum import Enum
from typing import Optional, Any, Generic, TypeVar, List
from dataclasses import dataclass, field, asdict
from datetime import datetime

logger = logging.getLogger("diomika-api")

T = TypeVar("T")


class ResponseStatus(Enum):
    """API response status."""
    SUCCESS = "success"
    ERROR = "error"
    PARTIAL = "partial"
    ACCEPTED = "accepted"


@dataclass
class PaginationInfo:
    """Pagination information for list responses."""
    page: int = 1
    page_size: int = 20
    total_items: int = 0
    total_pages: int = 0
    has_next: bool = False
    has_previous: bool = False

    @property
    def offset(self) -> int:
        """Calculate offset from page and page_size."""
        return (self.page - 1) * self.page_size

    def from_results(self, total_items: int) -> PaginationInfo:
        """Update pagination from total items."""
        self.total_items = total_items
        self.total_pages = (total_items + self.page_size - 1) // self.page_size
        self.has_next = self.page < self.total_pages
        self.has_previous = self.page > 1
        return self


@dataclass
class ApiResponse(Generic[T]):
    """Standardized API response."""
    status: ResponseStatus
    data: Optional[T] = None
    message: Optional[str] = None
    error: Optional[str] = None
    errors: Optional[List[dict]] = None
    meta: dict = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.utcnow)
    request_id: Optional[str] = None
    pagination: Optional[PaginationInfo] = None

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        response = {
            "status": self.status.value,
            "timestamp": self.timestamp.isoformat(),
        }

        if self.request_id:
            response["request_id"] = self.request_id

        if self.data is not None:
            if hasattr(self.data, "__dict__"):
                response["data"] = asdict(self.data)
            else:
                response["data"] = self.data

        if self.message:
            response["message"] = self.message

        if self.error:
            response["error"] = self.error

        if self.errors:
            response["errors"] = self.errors

        if self.pagination:
            response["pagination"] = asdict(self.pagination)

        if self.meta:
            response["meta"] = self.meta

        return response

    def to_json(self) -> str:
        """Convert to JSON."""
        import json
        return json.dumps(self.to_dict(), default=str)


@dataclass
class ListResponse:
    """Response for list endpoints."""
    items: List[Any] = field(default_factory=list)
    pagination: PaginationInfo = field(default_factory=PaginationInfo)
    filters_applied: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "items": self.items,
            "pagination": asdict(self.pagination),
            "filters_applied": self.filters_applied,
        }


class ApiResponseBuilder:
    """Builder for constructing API responses."""

    def __init__(self, status: ResponseStatus = ResponseStatus.SUCCESS):
        self.response = ApiResponse(status=status)

    def with_data(self, data: Any) -> ApiResponseBuilder:
        """Add data to response."""
        self.response.data = data
        return self

    def with_message(self, message: str) -> ApiResponseBuilder:
        """Add success message."""
        self.response.message = message
        return self

    def with_error(self, error: str) -> ApiResponseBuilder:
        """Add error message."""
        self.response.error = error
        self.response.status = ResponseStatus.ERROR
        return self

    def with_errors(self, errors: List[dict]) -> ApiResponseBuilder:
        """Add validation errors."""
        self.response.errors = errors
        return self

    def with_pagination(self, page: int, page_size: int, total: int) -> ApiResponseBuilder:
        """Add pagination info."""
        pagination = PaginationInfo(page=page, page_size=page_size)
        pagination.from_results(total)
        self.response.pagination = pagination
        return self

    def with_metadata(self, key: str, value: Any) -> ApiResponseBuilder:
        """Add metadata."""
        self.response.meta[key] = value
        return self

    def with_request_id(self, request_id: str) -> ApiResponseBuilder:
        """Add request ID."""
        self.response.request_id = request_id
        return self

    def build(self) -> ApiResponse:
        """Build and return response."""
        return self.response


class SuccessResponse:
    """Helper for creating success responses."""

    @staticmethod
    def created(data: Any = None, message: str = "Resource created") -> ApiResponse:
        """Create response for resource creation."""
        return ApiResponseBuilder(ResponseStatus.SUCCESS).with_data(
            data
        ).with_message(message).build()

    @staticmethod
    def updated(data: Any = None, message: str = "Resource updated") -> ApiResponse:
        """Create response for resource update."""
        return ApiResponseBuilder(ResponseStatus.SUCCESS).with_data(
            data
        ).with_message(message).build()

    @staticmethod
    def deleted(message: str = "Resource deleted") -> ApiResponse:
        """Create response for resource deletion."""
        return ApiResponseBuilder(ResponseStatus.SUCCESS).with_message(
            message
        ).build()

    @staticmethod
    def listed(
        items: List[Any],
        page: int = 1,
        page_size: int = 20,
        total: int = 0,
    ) -> ApiResponse:
        """Create response for list."""
        return ApiResponseBuilder(ResponseStatus.SUCCESS).with_data(
            items
        ).with_pagination(page, page_size, total).build()

    @staticmethod
    def ok(data: Any = None, message: str = "Success") -> ApiResponse:
        """Create generic success response."""
        return ApiResponseBuilder(ResponseStatus.SUCCESS).with_data(
            data
        ).with_message(message).build()


class ErrorResponse:
    """Helper for creating error responses."""

    @staticmethod
    def validation_error(errors: List[dict], message: str = "Validation failed") -> ApiResponse:
        """Create response for validation error."""
        return ApiResponseBuilder(ResponseStatus.ERROR).with_message(
            message
        ).with_errors(errors).build()

    @staticmethod
    def not_found(message: str = "Resource not found") -> ApiResponse:
        """Create response for not found."""
        return ApiResponseBuilder(ResponseStatus.ERROR).with_error(
            message
        ).build()

    @staticmethod
    def unauthorized(message: str = "Unauthorized") -> ApiResponse:
        """Create response for unauthorized."""
        return ApiResponseBuilder(ResponseStatus.ERROR).with_error(
            message
        ).build()

    @staticmethod
    def forbidden(message: str = "Forbidden") -> ApiResponse:
        """Create response for forbidden."""
        return ApiResponseBuilder(ResponseStatus.ERROR).with_error(
            message
        ).build()

    @staticmethod
    def conflict(message: str = "Resource conflict") -> ApiResponse:
        """Create response for conflict."""
        return ApiResponseBuilder(ResponseStatus.ERROR).with_error(
            message
        ).build()

    @staticmethod
    def server_error(message: str = "Internal server error") -> ApiResponse:
        """Create response for server error."""
        return ApiResponseBuilder(ResponseStatus.ERROR).with_error(
            message
        ).build()


class ResponseFormatter:
    """Format responses for FastAPI endpoints."""

    @staticmethod
    def format_list(
        items: List[Any],
        page: int = 1,
        page_size: int = 20,
        total: int = 0,
        request_id: Optional[str] = None,
    ) -> dict:
        """Format list response."""
        response = SuccessResponse.listed(items, page, page_size, total)
        if request_id:
            response.request_id = request_id
        return response.to_dict()

    @staticmethod
    def format_create(data: Any, request_id: Optional[str] = None) -> dict:
        """Format create response."""
        response = SuccessResponse.created(data)
        if request_id:
            response.request_id = request_id
        return response.to_dict()

    @staticmethod
    def format_update(data: Any, request_id: Optional[str] = None) -> dict:
        """Format update response."""
        response = SuccessResponse.updated(data)
        if request_id:
            response.request_id = request_id
        return response.to_dict()

    @staticmethod
    def format_delete(request_id: Optional[str] = None) -> dict:
        """Format delete response."""
        response = SuccessResponse.deleted()
        if request_id:
            response.request_id = request_id
        return response.to_dict()

    @staticmethod
    def format_error(message: str, request_id: Optional[str] = None) -> dict:
        """Format error response."""
        response = ErrorResponse.server_error(message)
        if request_id:
            response.request_id = request_id
        return response.to_dict()

    @staticmethod
    def format_validation_error(
        errors: List[dict],
        request_id: Optional[str] = None,
    ) -> dict:
        """Format validation error response."""
        response = ErrorResponse.validation_error(errors)
        if request_id:
            response.request_id = request_id
        return response.to_dict()
