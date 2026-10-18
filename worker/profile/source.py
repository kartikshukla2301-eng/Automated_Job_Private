"""Abstract ProfileSource interface for candidate profile retrieval."""

from typing import Protocol, runtime_checkable

from worker.profile.models import ProfileSnapshot


@runtime_checkable
class ProfileSource(Protocol):
    """Abstract interface for candidate profile retrieval.

    Defines the contract consumed by the worker engine, ensuring complete
    decoupling from the storage mechanism (e.g. LocalFileProfileSource,
    DevLevelerProfileSource).
    """

    async def get_snapshot(self) -> ProfileSnapshot:
        """Retrieve the current versioned profile snapshot.

        Returns:
            ProfileSnapshot: Strongly-typed snapshot containing candidate details,
                preferences, schema_version, and deterministic profile_version.
        """
        ...
