"""Tests for candidate profile models, ProfileSource interface, and LocalFileProfileSource."""

from pathlib import Path
import pytest
import yaml

from worker.profile.exceptions import (
    ProfileNotFoundError,
    ProfileParseError,
    ProfileValidationError,
)
from worker.profile.localfile import LocalFileProfileSource
from worker.profile.models import (
    CandidateDetails,
    EducationEntry,
    ExperienceEntry,
    ProfileSnapshot,
    SkillEntry,
    compute_profile_version,
)
from worker.profile.source import ProfileSource


def test_profile_source_protocol_compliance():
    """Verify LocalFileProfileSource implements ProfileSource protocol."""
    source = LocalFileProfileSource("fixtures/profile.yaml")
    assert isinstance(source, ProfileSource)


@pytest.mark.asyncio
async def test_load_valid_fixture_profile():
    """Verify loading the baseline template fixture successfully parses all models."""
    source = LocalFileProfileSource("fixtures/profile.yaml")
    snapshot = await source.get_snapshot()

    assert isinstance(snapshot, ProfileSnapshot)
    assert snapshot.schema_version == 1
    assert snapshot.profile_version == "template-v1.0.0"
    assert snapshot.candidate.name == "Candidate Name Placeholder"
    assert snapshot.candidate.email == "candidate.placeholder@example.com"
    assert len(snapshot.candidate.education) == 1
    assert snapshot.candidate.education[0].institution == "Example Institute of Technology"
    assert len(snapshot.candidate.experience) == 1
    assert snapshot.candidate.experience[0].company == "Example Software Labs"
    assert snapshot.candidate.experience[0].is_current is True
    assert len(snapshot.candidate.skills) == 5
    assert len(snapshot.candidate.projects) == 1
    assert snapshot.candidate.links["github"] == "https://github.com/example-candidate"
    assert "Software Engineer" in snapshot.preferences.roles


def test_skill_entry_string_and_dict_normalization():
    """Verify SkillEntry accepts both string and dictionary inputs."""
    s1 = SkillEntry.model_validate("Python")
    assert s1.name == "Python"
    assert s1.years is None

    s2 = SkillEntry.model_validate({"name": "FastAPI", "years": 2.5})
    assert s2.name == "FastAPI"
    assert s2.years == 2.5


def test_missing_profile_file_raises_error(tmp_path: Path):
    """Verify missing file raises ProfileNotFoundError without falling back to fake data."""
    non_existent = tmp_path / "does_not_exist.yaml"
    source = LocalFileProfileSource(non_existent)

    with pytest.raises(ProfileNotFoundError) as exc_info:
        source.load_snapshot()

    assert "not found" in str(exc_info.value).lower()


def test_malformed_yaml_raises_parse_error(tmp_path: Path):
    """Verify invalid YAML syntax raises ProfileParseError."""
    malformed_file = tmp_path / "bad.yaml"
    malformed_file.write_text("candidate: [unclosed_list: {foo", encoding="utf-8")

    source = LocalFileProfileSource(malformed_file)
    with pytest.raises(ProfileParseError) as exc_info:
        source.load_snapshot()

    assert "failed to parse yaml" in str(exc_info.value).lower()


def test_non_dict_yaml_root_raises_validation_error(tmp_path: Path):
    """Verify YAML that parses into a list or scalar raises ProfileValidationError."""
    list_file = tmp_path / "list.yaml"
    list_file.write_text("- item1\n- item2\n", encoding="utf-8")

    source = LocalFileProfileSource(list_file)
    with pytest.raises(ProfileValidationError) as exc_info:
        source.load_snapshot()

    assert "root must be a mapping" in str(exc_info.value).lower()


def test_invalid_email_format_raises_validation_error(tmp_path: Path):
    """Verify invalid email string raises ProfileValidationError."""
    profile_data = {
        "candidate": {
            "name": "Jane Doe",
            "email": "not-an-email",
        }
    }
    invalid_file = tmp_path / "invalid_email.yaml"
    invalid_file.write_text(yaml.safe_dump(profile_data), encoding="utf-8")

    source = LocalFileProfileSource(invalid_file)
    with pytest.raises(ProfileValidationError) as exc_info:
        source.load_snapshot()

    assert "email" in str(exc_info.value).lower()


def test_unknown_extra_fields_forbidden(tmp_path: Path):
    """Verify extra unexpected fields are strictly forbidden."""
    profile_data = {
        "candidate": {
            "name": "Jane Doe",
            "email": "jane@example.com",
            "unexpected_secret_field": "some_value",
        }
    }
    invalid_file = tmp_path / "extra_field.yaml"
    invalid_file.write_text(yaml.safe_dump(profile_data), encoding="utf-8")

    source = LocalFileProfileSource(invalid_file)
    with pytest.raises(ProfileValidationError) as exc_info:
        source.load_snapshot()

    assert "extra inputs are not permitted" in str(exc_info.value).lower()


def test_deterministic_profile_version():
    """Verify version hash calculation is deterministic for identical content."""
    payload_1 = {
        "schema_version": 1,
        "candidate": {
            "name": "Jane Doe",
            "email": "jane@example.com",
            "skills": [{"name": "Python", "years": 3}],
        },
        "preferences": {"roles": ["Engineer"]},
    }
    payload_2 = {
        "preferences": {"roles": ["Engineer"]},
        "schema_version": 1,
        "candidate": {
            "email": "jane@example.com",
            "name": "Jane Doe",
            "skills": [{"name": "Python", "years": 3}],
        },
    }

    version_1 = compute_profile_version(payload_1)
    version_2 = compute_profile_version(payload_2)

    assert version_1 == version_2
    assert len(version_1) == 16


def test_profile_version_changes_when_content_changes():
    """Verify version hash updates when candidate content is modified."""
    payload_base = {
        "schema_version": 1,
        "candidate": {
            "name": "Jane Doe",
            "email": "jane@example.com",
        },
        "preferences": {"roles": ["Engineer"]},
    }
    payload_changed = {
        "schema_version": 1,
        "candidate": {
            "name": "Jane Doe",
            "email": "jane@example.com",
            "location": "Bengaluru",
        },
        "preferences": {"roles": ["Engineer"]},
    }

    assert compute_profile_version(payload_base) != compute_profile_version(payload_changed)


def test_auto_compute_version_when_omitted(tmp_path: Path):
    """Verify auto-generation of profile_version when omitted from YAML."""
    profile_data = {
        "schema_version": 1,
        "candidate": {
            "name": "Jane Doe",
            "email": "jane@example.com",
        },
    }
    file_path = tmp_path / "no_version.yaml"
    file_path.write_text(yaml.safe_dump(profile_data), encoding="utf-8")

    source = LocalFileProfileSource(file_path, auto_compute_version=True)
    snapshot = source.load_snapshot()

    expected_hash = compute_profile_version(profile_data)
    assert snapshot.profile_version == expected_hash
