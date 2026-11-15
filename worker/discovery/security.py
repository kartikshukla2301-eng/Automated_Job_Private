"""Security and sanitization guards for untrusted job listings and external endpoints.

Following Architecture v1.0 LOCKED Section 18 and Phase 1.1 Requirements:
- Job descriptions and provider responses are treated as untrusted data.
- Strips executable code, scripts, hidden Unicode tags, and injection attempts.
- Strict network boundary enforcement restricting HTTP endpoints to approved providers.
"""

import html
import re
from typing import Optional, Set
from urllib.parse import urlsplit

# Approved hostnames for external public job discovery API calls and canonical job URLs
ALLOWED_DISCOVERY_HOSTS: Set[str] = {
    "boards-api.greenhouse.io",
    "api.greenhouse.io",
    "boards.greenhouse.io",
    "job-boards.greenhouse.io",
    "api.lever.co",
    "jobs.lever.co",
    "naukri.com",
    "www.naukri.com",
    "wellfound.com",
    "www.wellfound.com",
    "angel.co",
    "ashbyhq.com",
    "jobs.ashbyhq.com",
    "api.ashbyhq.com",
    "linkedin.com",
    "www.linkedin.com",
}

# Regex to strip HTML script, style, and iframe blocks along with their contents
DANGEROUS_BLOCKS_RE = re.compile(
    r"<(script|style|iframe|object|embed|svg|form|noscript)[\s>].*?</\1>",
    re.IGNORECASE | re.DOTALL,
)

# Regex to strip all remaining HTML tags
HTML_TAG_RE = re.compile(r"<[^>]+>")

# Regex to detect and strip invisible control characters, zero-width chars, and bidi overrides
INVISIBLE_CHARS_RE = re.compile(
    r"[\u200B-\u200D\uFEFF\u202A-\u202E\u2066-\u2069\x00-\x08\x0B\x0C\x0E-\x1F\x7F]"
)

# Literal delimiter neutralization to prevent prompt injection boundary breakout
DELIMITER_TAGS_RE = re.compile(
    r"<\s*/?\s*(system|instruction|user|assistant|context|document|tool|function|sandbox)\s*>",
    re.IGNORECASE,
)


def sanitize_job_description(raw_content: Optional[str], max_length: int = 50000) -> str:
    """Sanitize untrusted job description text from external HTML or text responses.

    1. Neutralizes dangerous HTML blocks (<script>, <style>, <iframe>).
    2. Converts line-break and paragraph tags to standard newlines.
    3. Strips all HTML tags.
    4. Unescapes HTML entities (&amp;, &lt;, etc.).
    5. Strips invisible zero-width chars and bidirectional overrides.
    6. Neutralizes XML/prompt delimiter tags to prevent prompt injection.
    7. Bounds content length to prevent denial-of-service.
    """
    if not raw_content:
        return ""

    text = str(raw_content)

    # 1. Strip dangerous blocks with content
    text = DANGEROUS_BLOCKS_RE.sub(" ", text)

    # 2. Convert common block breaks to newlines before stripping tags
    text = re.sub(r"<(?:p|br|div|li|tr|h[1-6])[\s/>]", "\n", text, flags=re.IGNORECASE)

    # 3. Neutralize potential prompt injection delimiter tags
    text = DELIMITER_TAGS_RE.sub(lambda m: f"[SANITIZED_TAG:{m.group(1)}]", text)

    # 4. Strip remaining HTML tags
    text = HTML_TAG_RE.sub(" ", text)

    # 5. Unescape HTML entities
    text = html.unescape(text)

    # 6. Strip invisible and bidi override characters
    text = INVISIBLE_CHARS_RE.sub("", text)

    # 7. Normalize whitespace while preserving readable paragraphs
    lines = [re.sub(r"[ \t]+", " ", line).strip() for line in text.split("\n")]
    cleaned_lines = [l for l in lines if l]
    result = "\n".join(cleaned_lines)

    # 8. Bounds check
    if len(result) > max_length:
        result = result[:max_length] + "\n[TRUNCATED_AT_MAX_LENGTH]"

    return result


def is_safe_discovery_url(url: str, allowed_hosts: Optional[Set[str]] = None) -> bool:
    """Validate that an external discovery endpoint URL is strictly restricted to approved hosts.

    Rejects:
    - Non-HTTP/HTTPS schemes
    - Hosts outside allowed_hosts
    - Credentials in URL (user:pass@host)
    - IP addresses (IPv4 / IPv6)
    - Localhost or loopback addresses
    """
    if not url or not url.strip():
        return False

    allowed = allowed_hosts or ALLOWED_DISCOVERY_HOSTS

    try:
        parts = urlsplit(url.strip())
        # Enforce https (or http if explicitly present)
        if parts.scheme.lower() not in ("https", "http"):
            return False

        # Reject embedded credentials
        if parts.username or parts.password:
            return False

        hostname = (parts.hostname or "").lower()
        if not hostname:
            return False

        # Reject IP addresses or localhost
        if hostname == "localhost" or hostname.startswith("127.") or hostname == "::1":
            return False

        # Exact or subdomain check against allowed hosts
        return hostname in allowed
    except Exception:
        return False
