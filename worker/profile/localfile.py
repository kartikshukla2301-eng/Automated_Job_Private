"""Local YAML file implementation of ProfileSource."""

from pathlib import Path
from typing import Any, Dict, Optional, Union

import yaml
from pydantic import ValidationError

from worker.profile.exceptions import (
    ProfileNotFoundError,
    ProfileParseError,
    ProfileValidationError,
)
from worker.profile.models import ProfileSnapshot, compute_profile_version
from worker.profile.source import ProfileSource


class LocalFileProfileSource(ProfileSource):
    """ProfileSource backed by a local YAML configuration file.

    Serves as the bootstrap and local fallback mechanism for the Job Agent
    without introducing network or cloud dependencies.
    """

    def __init__(
        self,
        file_path: Union[str, Path],
        auto_compute_version: bool = True,
    ) -> None:
        """Initialize with path to candidate profile YAML.

        Args:
            file_path: Filesystem path to profile YAML.
            auto_compute_version: If True, computes a deterministic SHA256 version
                digest when profile_version is not explicitly specified in the file.
        """
        self.file_path = Path(file_path)
        self.auto_compute_version = auto_compute_version

    def _read_and_parse_yaml(self) -> Dict[str, Any]:
        """Read and parse the YAML file without exposing sensitive content on failure."""
        if not self.file_path.exists():
            raise ProfileNotFoundError(f"Profile file not found at: {self.file_path}")

        try:
            with open(self.file_path, "r", encoding="utf-8") as f:
                content = yaml.safe_load(f)
        except yaml.YAMLError as exc:
            raise ProfileParseError(f"Failed to parse YAML profile: {exc}") from exc
        except Exception as exc:
            raise ProfileParseError(f"Unexpected error reading profile file: {exc}") from exc

        if not isinstance(content, dict):
            raise ProfileValidationError("Profile YAML root must be a mapping/dictionary")

        return content

    def load_snapshot(self) -> ProfileSnapshot:
        """Synchronously load, validate, and construct a ProfileSnapshot.

        Returns:
            ProfileSnapshot: Validated candidate profile snapshot.

        Raises:
            ProfileNotFoundError: When the file does not exist.
            ProfileParseError: When YAML parsing fails.
            ProfileValidationError: When data fails Pydantic schema validation.
        """
        data = self._read_and_parse_yaml()

        # If profile_version is missing or empty and auto_compute_version is enabled,
        # calculate a deterministic SHA256 digest of normalized content
        version = data.get("profile_version")
        if version is not None:
            data["profile_version"] = str(version)
        elif self.auto_compute_version:
            data["profile_version"] = compute_profile_version(data)

        try:
            return ProfileSnapshot.model_validate(data)
        except ValidationError as exc:
            # Mask sensitive values; include field error paths and messages safely
            sanitized_errors = [
                f"{'.'.join(str(loc) for loc in err['loc'])}: {err['msg']}"
                for err in exc.errors()
            ]
            error_summary = "; ".join(sanitized_errors)
            raise ProfileValidationError(
                f"Candidate profile schema validation failed: {error_summary}"
            ) from exc

    async def get_snapshot(self) -> ProfileSnapshot:
        """Retrieve the profile snapshot asynchronously (implements ProfileSource protocol)."""
        return self.load_snapshot()
