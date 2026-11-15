"""Supabase persistence and storage module (Phase 2.2)."""

from worker.persistence.answer_bank_repository import SupabaseAnswerBankRepository
from worker.persistence.application_repository import SupabaseApplicationRepository
from worker.persistence.event_repository import SupabaseApplicationEventRepository
from worker.persistence.exceptions import (
    AuthorizationError,
    DatabaseConnectionError,
    DatabaseError,
    DuplicateRecordError,
    OptimisticConcurrencyError,
    RecordNotFoundError,
    StorageError,
)
from worker.persistence.job_repository import SupabaseJobRepository
from worker.persistence.storage import SupabaseStorageService
from worker.persistence.supabase_client import SupabaseClient

__all__ = [
    "AuthorizationError",
    "DatabaseConnectionError",
    "DatabaseError",
    "DuplicateRecordError",
    "OptimisticConcurrencyError",
    "RecordNotFoundError",
    "StorageError",
    "SupabaseAnswerBankRepository",
    "SupabaseApplicationEventRepository",
    "SupabaseApplicationRepository",
    "SupabaseClient",
    "SupabaseJobRepository",
    "SupabaseStorageService",
]
