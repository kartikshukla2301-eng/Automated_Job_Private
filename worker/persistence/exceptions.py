"""Typed exceptions for Supabase persistence and storage operations (Phase 2.2)."""

from typing import Optional


class DatabaseError(Exception):
    """Base exception for all database persistence errors."""

    def __init__(self, message: str, code: Optional[str] = None, details: Optional[str] = None) -> None:
        super().__init__(message)
        self.message = message
        self.code = code
        self.details = details


class DatabaseConnectionError(DatabaseError):
    """Raised when connection to Supabase PostgREST or PostgreSQL fails."""
    pass


class DuplicateRecordError(DatabaseError):
    """Raised when an operation violates a unique constraint."""
    pass


class RecordNotFoundError(DatabaseError):
    """Raised when expected record is not found."""
    pass


class AuthorizationError(DatabaseError):
    """Raised when an operation violates Row Level Security or JWT ownership."""
    pass


class OptimisticConcurrencyError(DatabaseError):
    """Raised when concurrent update collision occurs."""
    pass


class StorageError(Exception):
    """Base exception for Supabase storage errors."""

    def __init__(self, message: str, bucket: Optional[str] = None, path: Optional[str] = None) -> None:
        super().__init__(message)
        self.bucket = bucket
        self.path = path
