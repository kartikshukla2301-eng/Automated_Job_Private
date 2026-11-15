"""Unit tests for DevLeveler profile source integration and ETag caching (Phase 1.9).

AUTHORITY:
- docs/AI_Job_Application_Agent_Architecture_v1.0_LOCKED.docx (Sections 6, 8, 14)
- docs/BUILD_RULES.md
"""

from datetime import datetime, timezone, timedelta
import json
from pathlib import Path
import pytest
import httpx
from unittest.mock import AsyncMock, MagicMock

from worker.profile.devleveler import DevLevelerProfileSource
from worker.profile.exceptions import (
    DevLevelerAuthError,
    DevLevelerConnectionError,
)
from worker.profile.models import (
    CandidateDetails,
    CandidatePreferences,
    EducationEntry,
    ExperienceEntry,
    ProfileSnapshot,
    SkillEntry,
)


@pytest.fixture
def mock_profile_dict() -> dict:
    return {
        "schema_version": 1,
        "profile_version": "v1.0-devleveler-test",
        "candidate": {
            "name": "Dev Candidate",
            "email": "candidate@example.com",
            "phone": "+919876543210",
            "location": "Bangalore, India",
            "skills": [{"name": "Python", "years": 5.0}],
            "experience": [
                {
                    "title": "Senior Backend Engineer",
                    "company": "Acme Corp",
                    "location": "Bangalore",
                    "start_date": "2022-01",
                    "is_current": True,
                    "highlights": ["Scaled backend services"],
                }
            ],
            "education": [
                {
                    "institution": "National University",
                    "degree": "B.Tech",
                    "field_of_study": "Computer Science",
                    "start_date": "2016-08",
                    "end_date": "2020-05",
                }
            ],
        },
        "preferences": {
            "roles": ["Backend Engineer"],
            "locations": ["Bangalore"],
            "work_modes": ["remote"],
            "levels": ["Senior"],
        },
    }


@pytest.mark.asyncio
async def test_devleveler_successful_fetch_and_etag_cache(tmp_path: Path, mock_profile_dict: dict):
    cache_file = tmp_path / "devleveler_cache.json"

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = mock_profile_dict
    mock_response.headers = {"ETag": '"etag_abc_123"'}

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_response)
    mock_client.__aenter__.return_value = mock_client

    source = DevLevelerProfileSource(
        base_url="https://api.devleveler.com",
        api_token="valid_test_token",
        cache_path=cache_file,
        client=mock_client,
    )

    snapshot = await source.get_snapshot()

    assert snapshot.candidate.name == "Dev Candidate"
    assert snapshot.profile_version == "v1.0-devleveler-test"
    assert cache_file.exists()

    cache_data = json.loads(cache_file.read_text(encoding="utf-8"))
    assert cache_data["etag"] == '"etag_abc_123"'
    assert cache_data["profile"]["candidate"]["name"] == "Dev Candidate"


@pytest.mark.asyncio
async def test_devleveler_304_not_modified_returns_cache(tmp_path: Path, mock_profile_dict: dict):
    cache_file = tmp_path / "devleveler_cache.json"
    cache_payload = {
        "etag": '"etag_abc_123"',
        "cached_at": datetime.now(timezone.utc).isoformat(),
        "profile": mock_profile_dict,
    }
    cache_file.write_text(json.dumps(cache_payload), encoding="utf-8")

    mock_response = MagicMock()
    mock_response.status_code = 304
    mock_response.headers = {}

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_response)
    mock_client.__aenter__.return_value = mock_client

    source = DevLevelerProfileSource(
        base_url="https://api.devleveler.com",
        api_token="valid_test_token",
        cache_path=cache_file,
        client=mock_client,
    )

    snapshot = await source.get_snapshot()
    assert snapshot.candidate.name == "Dev Candidate"
    assert snapshot.profile_version == "v1.0-devleveler-test"


@pytest.mark.asyncio
async def test_devleveler_auth_failure_raises_devleveler_auth_error(tmp_path: Path):
    cache_file = tmp_path / "devleveler_cache.json"

    mock_response = MagicMock()
    mock_response.status_code = 401

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_response)
    mock_client.__aenter__.return_value = mock_client

    source = DevLevelerProfileSource(
        base_url="https://api.devleveler.com",
        api_token="invalid_token",
        cache_path=cache_file,
        client=mock_client,
    )

    with pytest.raises(DevLevelerAuthError, match="HTTP 401"):
        await source.get_snapshot()


@pytest.mark.asyncio
async def test_devleveler_network_error_falls_back_to_local_source(tmp_path: Path):
    cache_file = tmp_path / "empty_cache.json"

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(side_effect=httpx.ConnectError("Connection refused"))
    mock_client.__aenter__.return_value = mock_client

    mock_fallback = AsyncMock()
    mock_fallback.get_snapshot.return_value = ProfileSnapshot(
        schema_version=1,
        profile_version="v1.0-fallback",
        candidate=CandidateDetails(
            name="Fallback Candidate",
            email="fallback@example.com",
            phone="+919876543210",
            location="Remote",
        ),
        preferences=CandidatePreferences(
            roles=["Backend Engineer"],
            locations=["Remote"],
            work_modes=["remote"],
        ),
    )

    source = DevLevelerProfileSource(
        base_url="https://api.devleveler.com",
        api_token="token_123",
        cache_path=cache_file,
        fallback_source=mock_fallback,
        client=mock_client,
    )

    snapshot = await source.get_snapshot()
    assert snapshot.candidate.name == "Fallback Candidate"
    assert snapshot.profile_version == "v1.0-fallback"


def test_staleness_detection(tmp_path: Path, mock_profile_dict: dict):
    cache_file = tmp_path / "devleveler_cache.json"
    source = DevLevelerProfileSource(cache_path=cache_file)

    # Missing cache is stale
    assert source.check_staleness() is True

    # Fresh cache (<24 hours) is not stale
    fresh_payload = {
        "etag": '"fresh"',
        "cached_at": datetime.now(timezone.utc).isoformat(),
        "profile": mock_profile_dict,
    }
    cache_file.write_text(json.dumps(fresh_payload), encoding="utf-8")
    assert source.check_staleness() is False

    # Old cache (>24 hours) is stale
    old_time = datetime.now(timezone.utc) - timedelta(hours=30)
    old_payload = {
        "etag": '"old"',
        "cached_at": old_time.isoformat(),
        "profile": mock_profile_dict,
    }
    cache_file.write_text(json.dumps(old_payload), encoding="utf-8")
    assert source.check_staleness() is True
