"""FastAPI dependency providers and authentication verification."""

import secrets
from pathlib import Path
from typing import Optional

from fastapi import Depends, Header, HTTPException, status

from services.api.config import Settings, get_settings
from worker.core.caps import ApplicationLedger, CapsEnforcer, FileApplicationLedger
from worker.core.kill_switch import FileKillSwitch, KillSwitch
from worker.core.runner import JobApplicationRunner
from worker.core.safety import SafetyEngine
from worker.core.workflow import WalkingSkeletonWorkflow
from worker.profile.localfile import LocalFileProfileSource
from worker.profile.source import ProfileSource
from worker.providers.greenhouse import GreenhouseProvider


def verify_worker_token(
    x_worker_token: Optional[str] = Header(None, alias="X-Worker-Token"),
    auth_header: Optional[str] = Header(None, alias="Authorization"),
    app_settings: Settings = Depends(get_settings),
) -> None:
    """Verify scoped worker authentication token with fail-closed semantics.

    SECURITY RULES (Architecture v1.0 LOCKED line 224/617):
    1. If 'worker_token' is configured (non-empty), valid bearer or header token is mandatory.
    2. Production and staging environments MUST have 'worker_token' configured. Missing token fails closed.
    3. In development and test, tokenless access is permitted ONLY when explicitly enabled via
       'allow_tokenless_dev=True' AND bound strictly to local loopback interface (127.0.0.1, localhost, ::1).
    4. Unsafe or non-local configurations (e.g. 0.0.0.0, external interfaces) strictly forbid tokenless execution.
    5. Tokens are validated in constant time via secrets.compare_digest and are never logged or echoed.
    """
    if app_settings.worker_token:
        provided_token: Optional[str] = x_worker_token
        if not provided_token and auth_header and auth_header.startswith("Bearer "):
            provided_token = auth_header[7:].strip()

        if not provided_token or not secrets.compare_digest(provided_token, app_settings.worker_token):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or missing worker token",
                headers={"WWW-Authenticate": "Bearer"},
            )
        return

    # Fail closed in production and staging if token is not configured
    if app_settings.app_env in ("production", "staging"):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Worker authentication must be configured in production and staging environments.",
        )

    # In development and test, tokenless access requires explicit opt-in and local-only interface
    is_local_host = app_settings.api_host in ("127.0.0.1", "localhost", "::1")
    if app_settings.app_env in ("development", "test") and app_settings.allow_tokenless_dev and is_local_host:
        return

    if not is_local_host:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tokenless worker actions are strictly prohibited on non-local network interfaces.",
        )

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Worker authentication required: worker_token is unconfigured and allow_tokenless_dev is disabled.",
        headers={"WWW-Authenticate": "Bearer"},
    )


def get_profile_source(app_settings: Settings = Depends(get_settings)) -> ProfileSource:
    """Provide configured candidate ProfileSource."""
    return LocalFileProfileSource(app_settings.profile.local_file_path)


def get_kill_switch() -> KillSwitch:
    """Provide file-persisted KillSwitch (fail-closed if missing/corrupt)."""
    return FileKillSwitch(Path("worker/sessions/kill_switch.json"))


def get_application_ledger() -> ApplicationLedger:
    """Provide file-persisted durable application ledger."""
    return FileApplicationLedger(Path("worker/sessions/application_ledger.jsonl"))


def get_caps_enforcer(
    app_settings: Settings = Depends(get_settings),
    ledger: ApplicationLedger = Depends(get_application_ledger),
) -> CapsEnforcer:
    """Provide CapsEnforcer configured with application settings and ledger."""
    return CapsEnforcer(caps_config=app_settings.caps, ledger=ledger)


def get_safety_engine(
    kill_switch: KillSwitch = Depends(get_kill_switch),
    caps_enforcer: CapsEnforcer = Depends(get_caps_enforcer),
) -> SafetyEngine:
    """Provide central SafetyEngine with real submit gate strictly disabled."""
    return SafetyEngine(
        kill_switch=kill_switch,
        caps_enforcer=caps_enforcer,
        real_submit_gate_enabled=False,
    )


def get_runner(
    safety_engine: SafetyEngine = Depends(get_safety_engine),
    profile_source: ProfileSource = Depends(get_profile_source),
) -> JobApplicationRunner:
    """Provide central JobApplicationRunner configured with providers."""
    return JobApplicationRunner(
        safety_engine=safety_engine,
        profile_source=profile_source,
        providers={"greenhouse": GreenhouseProvider()},
    )


def get_walking_skeleton_workflow(
    runner: JobApplicationRunner = Depends(get_runner),
) -> WalkingSkeletonWorkflow:
    """Provide WalkingSkeletonWorkflow for approved local fixture dry-runs."""
    return WalkingSkeletonWorkflow(runner=runner)


def get_llm_gateway(app_settings: Settings = Depends(get_settings)):
    """Provide the managed single-process LLM Gateway instance."""
    from worker.core.llm_gateway import get_managed_llm_gateway

    return get_managed_llm_gateway()


_application_repo = None
_event_repo = None


def get_application_repository():
    """Provide singleton in-memory ApplicationRepository."""
    global _application_repo
    if _application_repo is None:
        from worker.application.repository import InMemoryApplicationRepository

        _application_repo = InMemoryApplicationRepository()
    return _application_repo


def get_application_event_repository():
    """Provide singleton in-memory ApplicationEventRepository."""
    global _event_repo
    if _event_repo is None:
        from worker.application.repository import InMemoryApplicationEventRepository

        _event_repo = InMemoryApplicationEventRepository()
    return _event_repo


def get_matching_service():
    """Provide JobMatchingService configured with deterministic fallback embeddings."""
    from worker.matching.embedding import DeterministicFallbackEmbeddingProvider
    from worker.matching.service import JobMatchingService

    return JobMatchingService(
        embedding_provider=DeterministicFallbackEmbeddingProvider(),
        threshold=65.0,
    )


def get_application_orchestrator(
    application_repo=Depends(get_application_repository),
    event_repo=Depends(get_application_event_repository),
    matching_service=Depends(get_matching_service),
    safety_engine: SafetyEngine = Depends(get_safety_engine),
    runner: JobApplicationRunner = Depends(get_runner),
):
    """Provide configured central ApplicationOrchestrator."""
    from worker.application.orchestrator import ApplicationOrchestrator

    return ApplicationOrchestrator(
        application_repo=application_repo,
        event_repo=event_repo,
        matching_service=matching_service,
        safety_engine=safety_engine,
        runner=runner,
    )


_browser_manager = None
_navigation_guard = None


def get_navigation_guard():
    """Provide singleton NavigationGuard."""
    global _navigation_guard
    if _navigation_guard is None:
        from worker.browser.navigation_guard import NavigationGuard

        _navigation_guard = NavigationGuard()
    return _navigation_guard


def get_browser_manager():
    """Provide singleton BrowserManager (initialized on demand, not at import time)."""
    global _browser_manager
    if _browser_manager is None:
        from worker.browser.browser_manager import BrowserManager

        _browser_manager = BrowserManager()
    return _browser_manager


_provider_health_mgr = None
_heartbeat_mgr = None


def get_provider_health_manager():
    """Provide singleton ProviderHealthManager."""
    global _provider_health_mgr
    if _provider_health_mgr is None:
        from worker.ops.provider_health import ProviderHealthManager

        _provider_health_mgr = ProviderHealthManager()
    return _provider_health_mgr


def get_heartbeat_manager():
    """Provide singleton HeartbeatManager."""
    global _heartbeat_mgr
    if _heartbeat_mgr is None:
        from worker.ops.heartbeat import HeartbeatManager

        _heartbeat_mgr = HeartbeatManager()
    return _heartbeat_mgr


def get_approval_manager(
    orchestrator=Depends(get_application_orchestrator),
    app_repo=Depends(get_application_repository),
    event_repo=Depends(get_application_event_repository),
):
    """Provide configured ApprovalManager."""
    from worker.ops.approval import ApprovalManager

    return ApprovalManager(
        orchestrator=orchestrator,
        application_repo=app_repo,
        event_repo=event_repo,
    )


def get_canary_runner(health_mgr=Depends(get_provider_health_manager)):
    """Provide ProviderCanaryRunner."""
    from worker.ops.canary import ProviderCanaryRunner

    return ProviderCanaryRunner(health_mgr=health_mgr)


def get_metrics_aggregator(
    app_repo=Depends(get_application_repository),
    event_repo=Depends(get_application_event_repository),
    health_mgr=Depends(get_provider_health_manager),
):
    """Provide MetricsAggregator."""
    from worker.ops.metrics import MetricsAggregator

    return MetricsAggregator(
        application_repo=app_repo,
        event_repo=event_repo,
        health_mgr=health_mgr,
    )


def get_telegram_service(
    approval_manager=Depends(get_approval_manager),
    kill_switch=Depends(get_kill_switch),
    health_mgr=Depends(get_provider_health_manager),
    app_settings: Settings = Depends(get_settings),
):
    """Provide TelegramNotificationService configured with settings."""
    from worker.ops.telegram import TelegramNotificationService

    token = getattr(app_settings, "telegram_bot_token", None)
    chat_ids = getattr(app_settings, "telegram_allowed_chat_ids", None)
    return TelegramNotificationService(
        bot_token=token,
        allowed_chat_ids=chat_ids,
        approval_manager=approval_manager,
        kill_switch=kill_switch,
        provider_health_mgr=health_mgr,
    )


def get_readiness_evaluator():
    """Provide RealSubmitReadinessEvaluator."""
    from worker.ops.readiness import RealSubmitReadinessEvaluator

    return RealSubmitReadinessEvaluator()

