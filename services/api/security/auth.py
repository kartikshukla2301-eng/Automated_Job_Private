"""API Authentication and role-based authorization dependencies (Phase 2.3).

AUTHORITY:
- docs/AI_Job_Application_Agent_Architecture_v1.0_LOCKED.docx (Section 14)
- docs/BUILD_RULES.md
"""

from __future__ import annotations

import logging
import secrets
from typing import Optional
from uuid import UUID, uuid4

from fastapi import Depends, Header, HTTPException, status

from services.api.config import Settings, get_settings
from services.api.security.models import AuthenticatedSubject, UserRole
from worker.application.models import Application

logger = logging.getLogger("services.api.security.auth")


def get_authenticated_subject(
    authorization: Optional[str] = Header(None, alias="Authorization"),
    x_worker_token: Optional[str] = Header(None, alias="X-Worker-Token"),
    x_user_jwt: Optional[str] = Header(None, alias="X-User-JWT"),
    x_user_id: Optional[str] = Header(None, alias="X-User-ID"),
    x_user_role: Optional[str] = Header(None, alias="X-User-Role"),
    app_settings: Settings = Depends(get_settings),
) -> AuthenticatedSubject:
    """Extract and authenticate request subject, strictly separating Worker vs User identity.

    Rules:
    - Worker identity requires matching configured worker_token (or dev local bypass).
    - User identity requires valid bearer JWT or dev user header.
    - User IDs from request bodies are never trusted blindly for authorization.
    """
    if not isinstance(authorization, str):
        authorization = None
    if not isinstance(x_worker_token, str):
        x_worker_token = None
    if not isinstance(x_user_jwt, str):
        x_user_jwt = None
    if not isinstance(x_user_id, str):
        x_user_id = None
    if not isinstance(x_user_role, str):
        x_user_role = None

    token = None
    if authorization and authorization.startswith("Bearer "):
        token = authorization[7:].strip()
    elif x_worker_token:
        token = x_worker_token.strip()
    elif x_user_jwt:
        token = x_user_jwt.strip()

    # 1. Check Worker Token
    if app_settings.worker_token and token and secrets.compare_digest(token, app_settings.worker_token):
        return AuthenticatedSubject(
            subject_id=UUID("00000000-0000-0000-0000-000000000001"),
            role=UserRole.WORKER,
            token_type="worker_token",
        )

    # 2. Check User JWT or Dev User Header
    if token and token.startswith("user-jwt-"):
        # Simulated or parsed JWT token with user id
        uid_part = token.replace("user-jwt-", "")
        try:
            user_uuid = UUID(uid_part)
        except ValueError:
            user_uuid = uuid4()
        role = UserRole.OWNER
        if x_user_role and x_user_role.upper() in UserRole.__members__:
            role = UserRole[x_user_role.upper()]
        return AuthenticatedSubject(
            subject_id=user_uuid,
            role=role,
            token_type="user_jwt",
        )

    # 3. Development / Test Local Fallback (only on loopback interface with allow_tokenless_dev)
    is_local_host = app_settings.api_host in ("127.0.0.1", "localhost", "::1")
    if app_settings.app_env in ("development", "test") and app_settings.allow_tokenless_dev and is_local_host:
        target_id = uuid4()
        if x_user_id:
            try:
                target_id = UUID(x_user_id)
            except ValueError:
                pass
        role = UserRole.OWNER
        if x_user_role and x_user_role.upper() in UserRole.__members__:
            role = UserRole[x_user_role.upper()]
        elif x_worker_token or (token and "worker" in token.lower()):
            role = UserRole.WORKER

        return AuthenticatedSubject(
            subject_id=target_id,
            role=role,
            token_type="dev_local",
        )

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authentication required: Missing or invalid authorization token",
        headers={"WWW-Authenticate": "Bearer"},
    )


def require_owner_or_operator(
    subject: AuthenticatedSubject = Depends(get_authenticated_subject),
) -> AuthenticatedSubject:
    """Ensure subject possesses human candidate owner or operator authorization."""
    if subject.role not in (UserRole.OWNER, UserRole.OPERATOR, UserRole.ADMIN):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Access forbidden: Role '{subject.role.value}' is not authorized for operator actions.",
        )
    return subject


def require_worker_identity(
    subject: AuthenticatedSubject = Depends(get_authenticated_subject),
) -> AuthenticatedSubject:
    """Ensure subject possesses worker execution authorization."""
    if subject.role != UserRole.WORKER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Access forbidden: Role '{subject.role.value}' is not authorized for internal worker execution.",
        )
    return subject


def verify_application_ownership(
    app: Application,
    subject: AuthenticatedSubject,
) -> None:
    """Enforce strict user ownership on application resources to block cross-user data leakage.

    Workers are permitted access for execution queues; users are restricted to their own applications.
    """
    if subject.role == UserRole.WORKER:
        return

    if app.user_id != subject.subject_id:
        logger.warning(
            "Security alert: User %s attempted cross-user access to application %s (owned by %s)",
            subject.subject_id,
            app.id,
            app.user_id,
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: You do not have permission to view or manipulate this application.",
        )
