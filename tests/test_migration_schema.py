"""Automated static validation suite for migrations/001_initial_schema.sql.

Note: These tests perform deterministic static text, regex pattern matching,
and constraint inspections. They do NOT represent real SQL AST parsing,
PostgreSQL migration execution, or live Supabase database validation.
"""

import re
from pathlib import Path
import pytest

SCHEMA_FILE = Path("migrations/001_initial_schema.sql")

EXPECTED_TABLES = [
    "profile_snapshots",
    "resume_versions",
    "jobs",
    "runs",
    "applications",
    "application_events",
    "form_snapshots",
    "answer_bank",
    "sessions",
    "llm_calls",
    "app_config",
    "company_rules",
    "notifications",
]


@pytest.fixture(scope="module")
def migration_sql() -> str:
    assert SCHEMA_FILE.exists(), f"Migration file '{SCHEMA_FILE}' must exist"
    content = SCHEMA_FILE.read_text(encoding="utf-8")
    assert len(content.strip()) > 0, "Migration file must not be empty"
    return content


def test_migration_file_exists_and_readable(migration_sql: str):
    """Verify migration file exists, is non-empty, and has UTF-8 encoding."""
    assert len(migration_sql) > 1000
    assert "AI Job Application Agent — Initial Database Schema Migration" in migration_sql


def test_no_auth_schema_or_table_stubs_created(migration_sql: str):
    """Verify migration does NOT create or alter Supabase-managed auth objects."""
    # Must not contain CREATE SCHEMA auth
    assert not re.search(r"CREATE\s+SCHEMA\s+.*?auth", migration_sql, re.IGNORECASE), (
        "Migration must not attempt to create or modify the Supabase 'auth' schema"
    )

    # Must not contain CREATE TABLE auth.users
    assert not re.search(r"CREATE\s+TABLE\s+.*?auth\.users", migration_sql, re.IGNORECASE), (
        "Migration must not create a stub 'auth.users' table; Supabase Auth manages it"
    )

    # Legitimate foreign key references to auth.users(id) must remain
    assert re.search(r"REFERENCES\s+auth\.users\s*\(\s*id\s*\)", migration_sql, re.IGNORECASE), (
        "Migration must retain legitimate foreign-key references to auth.users(id)"
    )


def test_all_thirteen_architecture_tables_defined(migration_sql: str):
    """Verify all 13 tables specified in Section 14 of the locked architecture are defined."""
    for table_name in EXPECTED_TABLES:
        pattern = rf"CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?{table_name}\s*\("
        match = re.search(pattern, migration_sql, re.IGNORECASE)
        assert match is not None, f"Expected table '{table_name}' was not found in migration"


def test_foreign_key_relationships_defined(migration_sql: str):
    """Verify critical relational foreign key constraints are established."""
    # applications -> jobs(id)
    assert re.search(r"REFERENCES\s+jobs\s*\(\s*id\s*\)", migration_sql, re.IGNORECASE)

    # applications -> runs(id)
    assert re.search(r"REFERENCES\s+runs\s*\(\s*id\s*\)", migration_sql, re.IGNORECASE)

    # application_events -> applications(id)
    assert re.search(r"REFERENCES\s+applications\s*\(\s*id\s*\)", migration_sql, re.IGNORECASE)

    # form_snapshots -> applications(id)
    assert re.search(r"REFERENCES\s+applications\s*\(\s*id\s*\)", migration_sql, re.IGNORECASE)

    # llm_calls -> runs(id)
    assert re.search(r"REFERENCES\s+runs\s*\(\s*id\s*\)", migration_sql, re.IGNORECASE)

    # user-scoped tables -> auth.users(id)
    assert re.search(r"REFERENCES\s+auth\.users\s*\(\s*id\s*\)", migration_sql, re.IGNORECASE)


def test_unique_deduplication_constraints(migration_sql: str):
    """Verify deduplication and idempotency constraints per Architecture Section 14."""
    # Deduplication across platform and external ID
    assert "uq_jobs_platform_external" in migration_sql
    assert "UNIQUE (platform, external_id)" in migration_sql

    # Application idempotency and single application per user-job
    assert "uq_applications_idempotency" in migration_sql
    assert "uq_applications_user_job" in migration_sql

    # Profile versioning
    assert "uq_profile_snapshots_user_version" in migration_sql

    # Answer bank scoping
    assert "uq_answer_bank_user_key_scope" in migration_sql


def test_company_rules_uniqueness_not_silently_introduced(migration_sql: str):
    """Verify company_rules does not silently introduce unapproved unique constraints."""
    # Must not contain an invented unique constraint on (user_id, company, rule_type)
    assert "uq_company_rules" not in migration_sql
    assert not re.search(r"UNIQUE\s*\(\s*user_id\s*,\s*company\s*,\s*rule_type\s*\)", migration_sql, re.IGNORECASE), (
        "Company rule uniqueness must not be silently invented without explicit decision"
    )


def test_state_machine_check_constraints(migration_sql: str):
    """Verify application state machine check constraint includes all Section 13 states."""
    expected_states = [
        "DISCOVERED", "MATCHED", "ELIGIBLE", "READY", "AWAITING_APPROVAL",
        "FILLING", "NEEDS_USER_INPUT", "BLOCKED", "SUBMITTING",
        "UNCERTAIN", "VERIFYING", "APPLIED", "DRY_RUN_DONE",
        "SKIPPED", "REJECTED", "EXPIRED", "DUPLICATE", "FAILED"
    ]
    for state in expected_states:
        assert f"'{state}'" in migration_sql, f"State machine status '{state}' missing from check constraints"

    # Autonomy levels
    for level in ["L0", "L1", "L2", "L3"]:
        assert f"'{level}'" in migration_sql, f"Autonomy level '{level}' missing from check constraints"


def test_row_level_security_unconditionally_enabled_on_all_tables(migration_sql: str):
    """Verify Row-Level Security is explicitly enabled on all 13 tables."""
    for table_name in EXPECTED_TABLES:
        pattern = rf"ALTER\s+TABLE\s+{table_name}\s+ENABLE\s+ROW\s+LEVEL\s+SECURITY\s*;"
        assert re.search(pattern, migration_sql, re.IGNORECASE) is not None, (
            f"RLS is not explicitly enabled on '{table_name}'"
        )


def test_user_scoped_tables_restricted_to_owner(migration_sql: str):
    """Verify user-scoped tables restrict access to auth.uid() = user_id."""
    user_tables = [
        "profile_snapshots",
        "resume_versions",
        "applications",
        "answer_bank",
        "app_config",
        "company_rules",
        "notifications",
    ]
    for table_name in user_tables:
        pattern = rf"CREATE\s+POLICY\s+.*?ON\s+{table_name}\s+FOR\s+ALL\s+TO\s+authenticated"
        assert re.search(pattern, migration_sql, re.IGNORECASE | re.DOTALL) is not None, (
            f"Missing authenticated user policy on '{table_name}'"
        )
        assert "auth.uid() = user_id" in migration_sql


def test_application_events_is_strictly_read_only_for_authenticated(migration_sql: str):
    """Verify application_events has SELECT-only authenticated policy for audit immutability."""
    # Must have FOR SELECT policy
    select_policy = re.search(
        r"CREATE\s+POLICY\s+.*?ON\s+application_events\s+FOR\s+SELECT\s+TO\s+authenticated",
        migration_sql,
        re.IGNORECASE | re.DOTALL,
    )
    assert select_policy is not None, "application_events must have a FOR SELECT policy for authenticated users"

    # Must NOT have FOR ALL, INSERT, UPDATE, or DELETE policies for authenticated
    forbidden_policy = re.search(
        r"CREATE\s+POLICY\s+.*?ON\s+application_events\s+FOR\s+(?:ALL|INSERT|UPDATE|DELETE)\s+TO\s+authenticated",
        migration_sql,
        re.IGNORECASE | re.DOTALL,
    )
    assert forbidden_policy is None, "application_events must NOT allow mutations from authenticated users"


def test_form_snapshots_is_strictly_read_only_for_authenticated(migration_sql: str):
    """Verify form_snapshots has SELECT-only authenticated policy."""
    select_policy = re.search(
        r"CREATE\s+POLICY\s+.*?ON\s+form_snapshots\s+FOR\s+SELECT\s+TO\s+authenticated",
        migration_sql,
        re.IGNORECASE | re.DOTALL,
    )
    assert select_policy is not None, "form_snapshots must have a FOR SELECT policy for authenticated users"

    forbidden_policy = re.search(
        r"CREATE\s+POLICY\s+.*?ON\s+form_snapshots\s+FOR\s+(?:ALL|INSERT|UPDATE|DELETE)\s+TO\s+authenticated",
        migration_sql,
        re.IGNORECASE | re.DOTALL,
    )
    assert forbidden_policy is None, "form_snapshots must NOT allow mutations from authenticated users"


def test_fail_closed_tables_have_no_authenticated_policies(migration_sql: str):
    """Verify sensitive/unpartitioned tables have NO policies granted to authenticated users."""
    fail_closed_tables = ["sessions", "runs", "llm_calls"]
    for table_name in fail_closed_tables:
        policy = re.search(
            rf"CREATE\s+POLICY\s+.*?ON\s+{table_name}\s+FOR\s+.*?TO\s+authenticated",
            migration_sql,
            re.IGNORECASE | re.DOTALL,
        )
        assert policy is None, (
            f"Fail-closed table '{table_name}' must NOT expose any direct policies to authenticated users"
        )


def test_sql_syntax_cleanliness(migration_sql: str):
    """Verify SQL syntax basic formatting: statements end with semicolon and no unbalanced parentheses."""
    # Strip comments
    clean_lines = []
    for line in migration_sql.splitlines():
        stripped = line.strip()
        if stripped.startswith("--"):
            continue
        clean_lines.append(line)
    sql_text = "\n".join(clean_lines)

    open_parens = sql_text.count("(")
    close_parens = sql_text.count(")")
    assert open_parens == close_parens, f"Unbalanced parentheses: {open_parens} open vs {close_parens} close"

