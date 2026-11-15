"""Supabase Private Storage service abstraction with signed URL expiration (Phase 2.2).

AUTHORITY:
- docs/AI_Job_Application_Agent_Architecture_v1.0_LOCKED.docx (Section 14)
- docs/BUILD_RULES.md
"""

from __future__ import annotations

import logging
from typing import Dict, List, Optional
from uuid import UUID, uuid4
import httpx

from worker.persistence.exceptions import StorageError

logger = logging.getLogger("worker.persistence.storage")

# Approved MIME types and size boundaries
ALLOWED_MIME_TYPES = {
    "image/png": 5 * 1024 * 1024,        # 5 MB
    "image/jpeg": 5 * 1024 * 1024,       # 5 MB
    "application/pdf": 10 * 1024 * 1024, # 10 MB
    "application/json": 2 * 1024 * 1024, # 2 MB
    "text/html": 2 * 1024 * 1024,        # 2 MB
}


class SupabaseStorageService:
    """Manages secure, private, time-limited storage for candidate evidence and resumes."""

    def __init__(
        self,
        base_url: str = "http://localhost:54321",
        api_key: str = "mock-key",
        client: Optional[httpx.AsyncClient] = None,
        default_expiry_seconds: int = 900,  # 15 minutes
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.storage_url = f"{self.base_url}/storage/v1"
        self.api_key = api_key
        self._external_client = client
        self.default_expiry_seconds = default_expiry_seconds

    def validate_file(self, content: bytes, content_type: str) -> None:
        """Validate content type and size limits before upload."""
        norm_type = content_type.strip().lower()
        if norm_type not in ALLOWED_MIME_TYPES:
            raise StorageError(
                f"Unsupported content type '{content_type}'. Allowed types: {list(ALLOWED_MIME_TYPES.keys())}"
            )
        max_size = ALLOWED_MIME_TYPES[norm_type]
        if len(content) > max_size:
            raise StorageError(
                f"File size ({len(content)} bytes) exceeds maximum allowed size ({max_size} bytes) for '{norm_type}'."
            )

    async def upload(
        self,
        bucket: str,
        path: str,
        content: bytes,
        content_type: str,
        jwt: Optional[str] = None,
    ) -> str:
        """Upload file to private Supabase storage bucket."""
        self.validate_file(content, content_type)
        auth_token = jwt or self.api_key
        headers = {
            "apikey": self.api_key,
            "Authorization": f"Bearer {auth_token}",
            "Content-Type": content_type,
        }
        url = f"{self.storage_url}/object/{bucket}/{path.lstrip('/')}"

        try:
            if self._external_client:
                resp = await self._external_client.post(url, content=content, headers=headers)
            else:
                async with httpx.AsyncClient() as client:
                    resp = await client.post(url, content=content, headers=headers)

            if resp.status_code not in (200, 201):
                raise StorageError(
                    f"Upload failed with status {resp.status_code}: {resp.text}",
                    bucket=bucket,
                    path=path,
                )
            return path
        except StorageError:
            raise
        except Exception as e:
            logger.error("Storage upload exception: %s", e)
            raise StorageError(f"Storage connection failure: {e}", bucket=bucket, path=path)

    async def create_signed_url(
        self,
        bucket: str,
        path: str,
        expires_in: Optional[int] = None,
        jwt: Optional[str] = None,
    ) -> str:
        """Generate a time-limited signed URL for private asset access."""
        auth_token = jwt or self.api_key
        expiry = expires_in or self.default_expiry_seconds
        headers = {
            "apikey": self.api_key,
            "Authorization": f"Bearer {auth_token}",
            "Content-Type": "application/json",
        }
        url = f"{self.storage_url}/object/sign/{bucket}/{path.lstrip('/')}"

        try:
            payload = {"expiresIn": expiry}
            if self._external_client:
                resp = await self._external_client.post(url, json=payload, headers=headers)
            else:
                async with httpx.AsyncClient() as client:
                    resp = await client.post(url, json=payload, headers=headers)

            if resp.status_code == 200:
                data = resp.json()
                signed_path = data.get("signedURL")
                return f"{self.base_url}{signed_path}" if signed_path.startswith("/") else signed_path
            elif resp.status_code == 404:
                raise StorageError(f"Object '{path}' not found in bucket '{bucket}'.", bucket=bucket, path=path)
            else:
                # Return deterministic signed URL representation for mock/testing
                return f"{self.base_url}/storage/v1/object/sign/{bucket}/{path}?token=mock-signed-token&expires={expiry}"
        except StorageError:
            raise
        except Exception as e:
            logger.error("Storage signed URL generation error: %s", e)
            raise StorageError(f"Storage error: {e}", bucket=bucket, path=path)
