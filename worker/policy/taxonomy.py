"""Fixed field taxonomy and policy classifications for the AI Job Application Agent.

Following Section 8 of docs/AI_Job_Application_Agent_Architecture_v1.0_LOCKED.docx:
The policy engine is code, not prompt text. The taxonomy is fixed.
Unknown or unclassified fields default to always_ask.
Sensitive fields (government IDs, bank details, passwords, OTP, security credentials)
must never be automated (never_fill).
"""

from enum import Enum
from typing import Dict, FrozenSet, Tuple


class PolicyType(str, Enum):
    """Supported field-filling policies from the locked architecture."""

    AUTO = "auto"
    AUTO_LOG = "auto+log"
    ALWAYS_ASK = "always_ask"
    NEVER_FILL = "never_fill"


class FieldCategory(str, Enum):
    """Fixed 12-category field taxonomy per Section 8 of the locked architecture."""

    IDENTITY_AND_CONTACT = "identity_and_contact"
    EDUCATION_EXPERIENCE_SKILLS = "education_experience_skills"
    AVAILABILITY = "availability"
    COMPENSATION = "compensation"
    WORK_PREFERENCES = "work_preferences"
    WORK_AUTHORIZATION = "work_authorization"
    LEGAL_CONSENTS = "legal_consents"
    DEMOGRAPHICS_EEO = "demographics_eeo"
    CRIMINAL_AND_HEALTH = "criminal_and_health"
    SENSITIVE_SECURITY = "sensitive_security"
    MOTIVATION_COVER_LETTER = "motivation_cover_letter"
    UNKNOWN_UNCLASSIFIED = "unknown_unclassified"


# Canonical default policy mapping per field category
DEFAULT_CATEGORY_POLICIES: Dict[FieldCategory, PolicyType] = {
    FieldCategory.IDENTITY_AND_CONTACT: PolicyType.AUTO,
    FieldCategory.EDUCATION_EXPERIENCE_SKILLS: PolicyType.AUTO,
    FieldCategory.AVAILABILITY: PolicyType.AUTO_LOG,
    FieldCategory.COMPENSATION: PolicyType.ALWAYS_ASK,
    FieldCategory.WORK_PREFERENCES: PolicyType.AUTO_LOG,
    FieldCategory.WORK_AUTHORIZATION: PolicyType.AUTO_LOG,
    FieldCategory.LEGAL_CONSENTS: PolicyType.ALWAYS_ASK,
    FieldCategory.DEMOGRAPHICS_EEO: PolicyType.ALWAYS_ASK,
    FieldCategory.CRIMINAL_AND_HEALTH: PolicyType.ALWAYS_ASK,
    FieldCategory.SENSITIVE_SECURITY: PolicyType.NEVER_FILL,
    FieldCategory.MOTIVATION_COVER_LETTER: PolicyType.ALWAYS_ASK,
    FieldCategory.UNKNOWN_UNCLASSIFIED: PolicyType.ALWAYS_ASK,
}

# Substrings and keywords identifying sensitive security/credential/identity fields
# that MUST NEVER be automated under any circumstance (never_fill).
SENSITIVE_SECURITY_KEYWORDS: Tuple[str, ...] = (
    "password",
    "passwd",
    "secret",
    "ssn",
    "social_security",
    "social security",
    "national_id",
    "national id",
    "passport",
    "bank",
    "routing_number",
    "routing number",
    "account_number",
    "account number",
    "iban",
    "credit_card",
    "credit card",
    "cvv",
    "cvc",
    "pin",
    "otp",
    "one-time",
    "one time password",
    "verification_code",
    "verification code",
    "security_code",
    "security code",
    "mfa",
    "2fa",
    "captcha",
    "recaptcha",
    "hcaptcha",
    "turnstile",
    "driver_license",
    "drivers_license",
    "driver's license",
    "drivers license",
    "aadhaar",
    "pan_card",
    "tax_id",
)

# Common deterministic keywords mapping to specific taxonomy categories
CATEGORY_KEYWORD_RULES: Dict[FieldCategory, Tuple[str, ...]] = {
    FieldCategory.SENSITIVE_SECURITY: SENSITIVE_SECURITY_KEYWORDS,
    FieldCategory.IDENTITY_AND_CONTACT: (
        "first_name",
        "last_name",
        "full_name",
        "name",
        "email",
        "phone",
        "telephone",
        "mobile",
        "linkedin",
        "github",
        "portfolio",
        "website",
        "address",
        "city",
        "state",
        "zip",
        "postal_code",
        "country",
    ),
    FieldCategory.EDUCATION_EXPERIENCE_SKILLS: (
        "education",
        "school",
        "university",
        "college",
        "degree",
        "major",
        "gpa",
        "graduation_year",
        "experience",
        "company",
        "job_title",
        "skills",
        "technologies",
    ),
    FieldCategory.AVAILABILITY: (
        "notice_period",
        "notice period",
        "start_date",
        "start date",
        "earliest_start",
        "availability",
        "joining_date",
        "how soon can you join",
    ),
    FieldCategory.COMPENSATION: (
        "salary",
        "compensation",
        "current_ctc",
        "expected_ctc",
        "desired_salary",
        "hourly_rate",
        "base_pay",
        "remuneration",
    ),
    FieldCategory.WORK_PREFERENCES: (
        "relocation",
        "willing to relocate",
        "remote",
        "hybrid",
        "on-site",
        "work_mode",
        "office_location",
        "preferred_location",
    ),
    FieldCategory.WORK_AUTHORIZATION: (
        "work_authorization",
        "authorized to work",
        "sponsorship",
        "require sponsorship",
        "visa_status",
        "visa sponsorship",
        "legally authorized",
    ),
    FieldCategory.LEGAL_CONSENTS: (
        "consent",
        "background_check",
        "background check",
        "attestation",
        "terms_and_conditions",
        "privacy_policy",
        "certify that",
        "agree to",
        "disclaimer",
    ),
    FieldCategory.DEMOGRAPHICS_EEO: (
        "gender",
        "race",
        "ethnicity",
        "veteran",
        "disability",
        "eeo",
        "equal_opportunity",
        "sexual_orientation",
        "pronouns",
    ),
    FieldCategory.CRIMINAL_AND_HEALTH: (
        "criminal",
        "convicted",
        "felony",
        "misdemeanor",
        "medical",
        "health_condition",
        "immigration_history",
    ),
    FieldCategory.MOTIVATION_COVER_LETTER: (
        "cover_letter",
        "cover letter",
        "why do you want to work",
        "why us",
        "motivation",
        "tell us about yourself",
        "additional_information",
    ),
}
