"""Deterministic normalization and deduplication utilities for job discovery.

Following Section 10 of Architecture v1.0 LOCKED:
- Key 1: (platform, external_id)
- Key 2: canonical_key = normalised company + title + location bucket
- Key 3: content_hash for content change detection
- Canonical URL normalization stripping tracking parameters
- Company name legal entity stripping and cleaning
"""

import hashlib
import re
from typing import Optional, Set, Tuple
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

# Tracking and analytical query parameters stripped during URL normalization
TRACKING_QUERY_PARAMS: Set[str] = {
    "utm_source",
    "utm_medium",
    "utm_campaign",
    "utm_term",
    "utm_content",
    "gh_src",
    "gh_jid",
    "lever-source",
    "lever-origin",
    "ref",
    "source",
    "fbclid",
    "gclid",
    "mc_cid",
    "mc_eid",
    "trk",
    "trackingId",
}

# Regex to strip common corporate/legal suffixes
COMPANY_LEGAL_SUFFIXES_RE = re.compile(
    r"\b(inc\.?|incorporated|llc\.?|l\.l\.c\.?|ltd\.?|limited|corp\.?|corporation|co\.?|company|pvt\.?\s*ltd\.?|private\s+limited|gmbh|s\.?a\.?|ag)\b",
    re.IGNORECASE,
)


def normalize_company(name: str) -> str:
    """Normalize company name by stripping legal suffixes, punctuation, and whitespace."""
    if not name:
        return ""
    # Strip and lower
    cleaned = name.strip().lower()
    # Replace common punctuation with space
    cleaned = re.sub(r"[,._\-/&]", " ", cleaned)
    # Strip legal entity suffixes
    cleaned = COMPANY_LEGAL_SUFFIXES_RE.sub("", cleaned)
    # Collapse multiple whitespace
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned or name.strip().lower()


def normalize_title(title: str) -> str:
    """Normalize job title by lowercasing and standardizing whitespace."""
    if not title:
        return ""
    cleaned = title.strip().lower()
    # Normalize special dashes and symbols
    cleaned = re.sub(r"[\u2013\u2014]", "-", cleaned)
    # Collapse multiple whitespace
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


def normalize_location(location: Optional[str]) -> Tuple[Optional[str], str]:
    """Normalize location string and categorize into a location bucket.

    Returns:
        (clean_location_string, location_bucket)
        where location_bucket is 'remote', 'hybrid', 'onsite', or 'unspecified'.
    """
    if not location or not location.strip():
        return None, "unspecified"

    clean_loc = re.sub(r"\s+", " ", location.strip())
    loc_lower = clean_loc.lower()

    if any(k in loc_lower for k in ("remote", "anywhere", "virtual", "telecommute", "work from home", "wfh")):
        bucket = "remote"
    elif "hybrid" in loc_lower:
        bucket = "hybrid"
    else:
        bucket = "onsite"

    return clean_loc, bucket


def normalize_url(url: str) -> str:
    """Normalize job posting URL into canonical format.

    - Normalizes scheme to lowercase (https/http)
    - Normalizes host to lowercase (strips default ports)
    - Strips trailing slash on paths
    - Strips tracking / analytics query parameters (utm_*, gh_src, lever-source, etc.)
    - Drops URL fragments (#...)
    """
    if not url or not url.strip():
        return ""

    parts = urlsplit(url.strip())
    scheme = parts.scheme.lower() or "https"
    netloc = parts.netloc.lower()

    # Strip default ports if explicitly present
    if netloc.endswith(":443") and scheme == "https":
        netloc = netloc[:-4]
    elif netloc.endswith(":80") and scheme == "http":
        netloc = netloc[:-3]

    # Normalize path: collapse slashes, strip trailing slash unless root
    path = re.sub(r"/+", "/", parts.path)
    if len(path) > 1 and path.endswith("/"):
        path = path[:-1]

    # Clean query parameters
    query_params = []
    if parts.query:
        for k, v in parse_qsl(parts.query, keep_blank_values=True):
            if k.lower() not in TRACKING_QUERY_PARAMS:
                query_params.append((k, v))
        # Sort query parameters for determinism
        query_params.sort(key=lambda x: x[0])

    new_query = urlencode(query_params)
    # Fragment is strictly dropped for canonical URLs
    return urlunsplit((scheme, netloc, path, new_query, ""))


def compute_content_hash(description: Optional[str], fallback_title: str = "") -> str:
    """Compute SHA-256 content hash of normalized job description text.

    If description is missing, falls back to normalized title.
    """
    text_to_hash = (description or "").strip().lower()
    if not text_to_hash:
        text_to_hash = (fallback_title or "").strip().lower()

    # Collapse all whitespace and newlines for deterministic hashing
    normalized_text = re.sub(r"\s+", " ", text_to_hash)
    return hashlib.sha256(normalized_text.encode("utf-8")).hexdigest()


def compute_canonical_key(company: str, title: str, location_bucket: Optional[str]) -> str:
    """Compute canonical deduplication key (Key 2 from Architecture Section 10).

    canonical_key = normalised company + ":" + normalised title + ":" + location bucket
    Truncated to 255 characters to stay strictly within database column limits.
    """
    norm_comp = normalize_company(company)
    norm_titl = normalize_title(title)
    bucket = (location_bucket or "unspecified").strip().lower()

    full_key = f"{norm_comp}:{norm_titl}:{bucket}"
    return full_key[:255]
