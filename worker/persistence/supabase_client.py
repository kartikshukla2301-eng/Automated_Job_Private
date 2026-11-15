"""Supabase PostgREST async client wrapper with error translation (Phase 2.2).

AUTHORITY:
- docs/AI_Job_Application_Agent_Architecture_v1.0_LOCKED.docx (Section 14)
- docs/BUILD_RULES.md
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Union
import httpx

from worker.persistence.exceptions import (
    AuthorizationError,
    DatabaseConnectionError,
    DatabaseError,
    DuplicateRecordError,
    RecordNotFoundError,
)

logger = logging.getLogger("worker.persistence.supabase_client")


class SupabaseClient:
    """Async PostgREST client communicating with Supabase PostgreSQL API."""

    def __init__(
        self,
        base_url: str = "http://localhost:54321",
        api_key: str = "mock-key",
        client: Optional[httpx.AsyncClient] = None,
        timeout: float = 10.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.rest_url = f"{self.base_url}/rest/v1"
        self.api_key = api_key
        self._external_client = client
        self.timeout = timeout

    def _get_headers(
        self,
        jwt: Optional[str] = None,
        custom_headers: Optional[Dict[str, str]] = None,
    ) -> Dict[str, str]:
        auth_token = jwt or self.api_key
        headers = {
            "apikey": self.api_key,
            "Authorization": f"Bearer {auth_token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Prefer": "return=representation",
        }
        if custom_headers:
            headers.update(custom_headers)
        return headers

    def _handle_response(self, response: httpx.Response, action_desc: str) -> List[Dict[str, Any]]:
        if response.status_code in (200, 201):
            try:
                data = response.json()
                if isinstance(data, list):
                    return data
                elif isinstance(data, dict):
                    return [data]
                return []
            except Exception:
                return []

        # Error handling and mapping
        error_text = response.text
        code = None
        details = None
        try:
            err_json = response.json()
            if isinstance(err_json, dict):
                error_text = err_json.get("message") or err_json.get("error") or error_text
                code = err_json.get("code")
                details = err_json.get("details") or err_json.get("hint")
        except Exception:
            pass

        if response.status_code == 409 or (code and code.startswith("23505")):
            raise DuplicateRecordError(
                f"Duplicate record conflict during {action_desc}: {error_text}",
                code=code,
                details=details,
            )
        elif response.status_code in (401, 403):
            raise AuthorizationError(
                f"Unauthorized or RLS permission denied during {action_desc}: {error_text}",
                code=code,
                details=details,
            )
        elif response.status_code == 404:
            raise RecordNotFoundError(
                f"Resource not found during {action_desc}: {error_text}",
                code=code,
                details=details,
            )
        else:
            raise DatabaseError(
                f"Database error ({response.status_code}) during {action_desc}: {error_text}",
                code=code,
                details=details,
            )

    async def select(
        self,
        table: str,
        params: Optional[Dict[str, Any]] = None,
        jwt: Optional[str] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> List[Dict[str, Any]]:
        """Perform a SELECT query against a PostgREST table."""
        url = f"{self.rest_url}/{table}"
        req_headers = self._get_headers(jwt=jwt, custom_headers=headers)

        try:
            if self._external_client:
                resp = await self._external_client.get(
                    url, params=params, headers=req_headers, timeout=self.timeout
                )
            else:
                async with httpx.AsyncClient() as client:
                    resp = await client.get(
                        url, params=params, headers=req_headers, timeout=self.timeout
                    )
            return self._handle_response(resp, f"select from {table}")
        except (DuplicateRecordError, AuthorizationError, RecordNotFoundError, DatabaseError):
            raise
        except Exception as e:
            logger.error("Database connection error on select from %s: %s", table, e)
            raise DatabaseConnectionError(f"Connection failure communicating with Supabase: {e}")

    async def insert(
        self,
        table: str,
        data: Union[Dict[str, Any], List[Dict[str, Any]]],
        jwt: Optional[str] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> List[Dict[str, Any]]:
        """Perform an INSERT into a PostgREST table."""
        url = f"{self.rest_url}/{table}"
        req_headers = self._get_headers(jwt=jwt, custom_headers=headers)

        try:
            if self._external_client:
                resp = await self._external_client.post(
                    url, json=data, headers=req_headers, timeout=self.timeout
                )
            else:
                async with httpx.AsyncClient() as client:
                    resp = await client.post(
                        url, json=data, headers=req_headers, timeout=self.timeout
                    )
            return self._handle_response(resp, f"insert into {table}")
        except (DuplicateRecordError, AuthorizationError, RecordNotFoundError, DatabaseError):
            raise
        except Exception as e:
            logger.error("Database connection error on insert into %s: %s", table, e)
            raise DatabaseConnectionError(f"Connection failure communicating with Supabase: {e}")

    async def update(
        self,
        table: str,
        data: Dict[str, Any],
        params: Dict[str, Any],
        jwt: Optional[str] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> List[Dict[str, Any]]:
        """Perform a PATCH update on a PostgREST table."""
        url = f"{self.rest_url}/{table}"
        req_headers = self._get_headers(jwt=jwt, custom_headers=headers)

        try:
            if self._external_client:
                resp = await self._external_client.patch(
                    url, json=data, params=params, headers=req_headers, timeout=self.timeout
                )
            else:
                async with httpx.AsyncClient() as client:
                    resp = await client.patch(
                        url, json=data, params=params, headers=req_headers, timeout=self.timeout
                    )
            return self._handle_response(resp, f"update {table}")
        except (DuplicateRecordError, AuthorizationError, RecordNotFoundError, DatabaseError):
            raise
        except Exception as e:
            logger.error("Database connection error on update %s: %s", table, e)
            raise DatabaseConnectionError(f"Connection failure communicating with Supabase: {e}")

    async def delete(
        self,
        table: str,
        params: Dict[str, Any],
        jwt: Optional[str] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> List[Dict[str, Any]]:
        """Perform a DELETE on a PostgREST table."""
        url = f"{self.rest_url}/{table}"
        req_headers = self._get_headers(jwt=jwt, custom_headers=headers)

        try:
            if self._external_client:
                resp = await self._external_client.delete(
                    url, params=params, headers=req_headers, timeout=self.timeout
                )
            else:
                async with httpx.AsyncClient() as client:
                    resp = await client.delete(
                        url, params=params, headers=req_headers, timeout=self.timeout
                    )
            return self._handle_response(resp, f"delete from {table}")
        except (DuplicateRecordError, AuthorizationError, RecordNotFoundError, DatabaseError):
            raise
        except Exception as e:
            logger.error("Database connection error on delete from %s: %s", table, e)
            raise DatabaseConnectionError(f"Connection failure communicating with Supabase: {e}")
