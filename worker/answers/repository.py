"""Repository protocol and in-memory implementation for Answer Bank persistence."""

import re
import threading
from datetime import datetime, timezone
from typing import Dict, List, Optional, Protocol, Tuple

from worker.answers.exceptions import InvalidAnswerEntryError
from worker.answers.models import AnswerBankEntry


def normalize_query_text(text: str) -> str:
    """Normalize text for alias and variant matching: lowercase, strip, punctuation collapsed to space."""
    clean = text.strip().lower()
    clean = re.sub(r"[^\w\s]", " ", clean)
    clean = re.sub(r"\s+", " ", clean).strip()
    return clean


class AnswerBankRepository(Protocol):
    """Protocol defining the Answer Bank persistence interface."""

    def add(self, entry: AnswerBankEntry) -> None:
        """Add a new Answer Bank entry."""
        ...

    def update(self, entry: AnswerBankEntry) -> None:
        """Update an existing verified Answer Bank entry."""
        ...

    def get(self, key: str, scope: str = "global") -> Optional[AnswerBankEntry]:
        """Retrieve an entry by exact key and scope."""
        ...

    def search_by_alias(self, query: str, scope: Optional[str] = None) -> List[AnswerBankEntry]:
        """Search entries matching an alias or question variant."""
        ...

    def list_by_scope(self, scope: str) -> List[AnswerBankEntry]:
        """List all entries for a specific scope."""
        ...

    def mark_needs_review(self, key: str, scope: str = "global") -> None:
        """Mark an existing entry as needing review."""
        ...

    def list_all(self) -> List[AnswerBankEntry]:
        """List all entries across all scopes."""
        ...


class InMemoryAnswerBankRepository:
    """Deterministic in-memory implementation of AnswerBankRepository for offline tests and local execution."""

    def __init__(self, initial_entries: Optional[List[AnswerBankEntry]] = None) -> None:
        self._lock = threading.Lock()
        # Storage keyed by (normalized_key, normalized_scope)
        self._entries: Dict[Tuple[str, str], AnswerBankEntry] = {}

        if initial_entries:
            for entry in initial_entries:
                self.add(entry)

    def _make_key(self, key: str, scope: str) -> Tuple[str, str]:
        return (key.strip().lower(), scope.strip().lower())

    def add(self, entry: AnswerBankEntry) -> None:
        """Add a new entry. Overwrites if same (key, scope) already exists."""
        if not entry.key:
            raise InvalidAnswerEntryError("Cannot add AnswerBankEntry with empty key.")
        with self._lock:
            k = self._make_key(entry.key, entry.scope)
            self._entries[k] = entry

    def update(self, entry: AnswerBankEntry) -> None:
        """Update an existing entry."""
        k = self._make_key(entry.key, entry.scope)
        with self._lock:
            if k not in self._entries:
                raise KeyError(f"Entry with key '{entry.key}' and scope '{entry.scope}' does not exist.")
            self._entries[k] = entry

    def get(self, key: str, scope: str = "global") -> Optional[AnswerBankEntry]:
        """Retrieve an entry by key and scope."""
        k = self._make_key(key, scope)
        with self._lock:
            return self._entries.get(k)

    def search_by_alias(self, query: str, scope: Optional[str] = None) -> List[AnswerBankEntry]:
        """Search entries whose aliases or question variants match the normalized query."""
        norm_query = normalize_query_text(query)
        if not norm_query:
            return []

        matched: List[AnswerBankEntry] = []
        with self._lock:
            for (_, entry_scope), entry in self._entries.items():
                if scope is not None and entry_scope != scope.strip().lower():
                    continue

                # Check aliases
                for alias in entry.aliases:
                    if normalize_query_text(alias) == norm_query:
                        matched.append(entry)
                        break
                else:
                    # Check variants
                    for variant in entry.variants:
                        if normalize_query_text(variant) == norm_query:
                            matched.append(entry)
                            break

        return matched

    def list_by_scope(self, scope: str) -> List[AnswerBankEntry]:
        """List all entries belonging to the specified scope."""
        clean_scope = scope.strip().lower()
        with self._lock:
            return [e for (_, s), e in self._entries.items() if s == clean_scope]

    def mark_needs_review(self, key: str, scope: str = "global") -> None:
        """Mark an entry as needing review."""
        k = self._make_key(key, scope)
        with self._lock:
            if k in self._entries:
                existing = self._entries[k]
                updated = existing.model_copy(update={"needs_review": True})
                self._entries[k] = updated

    def list_all(self) -> List[AnswerBankEntry]:
        """List all entries stored in the repository."""
        with self._lock:
            return list(self._entries.values())
