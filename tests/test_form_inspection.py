"""Tests for PageInspector and FieldDetector form discovery.

AUTHORITY:
- docs/AI_Job_Application_Agent_Architecture_v1.0_LOCKED.docx (Sections 11, 12)
- docs/BUILD_RULES.md
"""

from pathlib import Path
import pytest

from worker.browser.field_detector import DetectedField
from worker.browser.page_inspector import PageInspector


@pytest.fixture
def inspector() -> PageInspector:
    return PageInspector()


@pytest.fixture
def greenhouse_html() -> str:
    return Path("fixtures/forms/greenhouse_job.html").read_text(encoding="utf-8")


@pytest.fixture
def lever_html() -> str:
    return Path("fixtures/forms/lever_job.html").read_text(encoding="utf-8")


def test_inspect_greenhouse_form(inspector: PageInspector, greenhouse_html: str):
    """Verify Greenhouse form fixture fields are detected and classified accurately."""
    fields = inspector.inspect_html(greenhouse_html)
    assert len(fields) >= 8

    labels = [f.label for f in fields]
    assert any("First Name" in lbl for lbl in labels)
    assert any("Last Name" in lbl for lbl in labels)
    assert any("Email" in lbl for lbl in labels)
    assert any("Phone" in lbl for lbl in labels)
    assert any("LinkedIn" in lbl for lbl in labels)
    assert any("Website" in lbl for lbl in labels)

    # Required fields check
    fn_field = next(f for f in fields if "First Name" in f.label)
    assert fn_field.required is True
    assert fn_field.input_type == "text"
    assert fn_field.is_sensitive is False

    # Sensitive fields check: password, otp, file upload must be flagged is_sensitive=True
    password_field = next(f for f in fields if f.name == "password" or "password" in f.label.lower())
    assert password_field.is_sensitive is True

    otp_field = next(f for f in fields if "otp" in (f.name or "").lower() or "otp" in f.label.lower())
    assert otp_field.is_sensitive is True

    resume_field = next(f for f in fields if f.name == "resume" or "resume" in f.label.lower())
    assert resume_field.is_sensitive is True
    assert resume_field.input_type == "file"


def test_inspect_lever_form(inspector: PageInspector, lever_html: str):
    """Verify Lever form fixture fields (select, radio group, checkbox, textarea) are parsed."""
    fields = inspector.inspect_html(lever_html)
    assert len(fields) >= 8

    # Text inputs
    name_field = next(f for f in fields if f.name == "name")
    assert "Full Name" in name_field.label
    assert name_field.required is True

    # Dropdown select
    work_auth_field = next(f for f in fields if f.name == "work_authorization")
    assert work_auth_field.input_type == "select"
    assert "Yes" in work_auth_field.options
    assert "No" in work_auth_field.options

    # Radio group aggregation
    radio_group = next(f for f in fields if f.input_type == "radio")
    assert radio_group.name == "relocation"
    assert len(radio_group.options) == 2
    assert any("Yes" in opt for opt in radio_group.options)
    assert any("No" in opt for opt in radio_group.options)

    # Checkbox
    consent_field = next(f for f in fields if f.name == "consent")
    assert consent_field.input_type == "checkbox"

    # Textarea
    comments_field = next(f for f in fields if f.name == "comments")
    assert comments_field.input_type == "textarea"


def test_inspect_duplicate_labels_disambiguation(inspector: PageInspector):
    """Verify duplicate labels on the same form are disambiguated without collisions."""
    html_with_duplicates = """
    <form>
      <div>
        <label for="phone_home">Phone Number</label>
        <input type="tel" id="phone_home" name="phone_home">
      </div>
      <div>
        <label for="phone_work">Phone Number</label>
        <input type="tel" id="phone_work" name="phone_work">
      </div>
    </form>
    """
    fields = inspector.inspect_html(html_with_duplicates)
    assert len(fields) == 2
    assert fields[0].label == "Phone Number"
    assert fields[1].label == "Phone Number"
    # Ensure distinct field IDs
    assert fields[0].field_id != fields[1].field_id


def test_inspect_no_fragile_absolute_xpath(inspector: PageInspector, greenhouse_html: str):
    """Verify selectors are semantic and never absolute XPaths like /html/body/..."""
    fields = inspector.inspect_html(greenhouse_html)
    for f in fields:
        assert not f.semantic_selector.startswith("/html/")
        assert not f.semantic_selector.startswith("/body/")
        # Selectors should start with #, tag, internal:label, or [attr
        assert (
            f.semantic_selector.startswith("#")
            or f.semantic_selector.startswith("input")
            or f.semantic_selector.startswith("textarea")
            or f.semantic_selector.startswith("select")
            or f.semantic_selector.startswith("internal:")
        )
