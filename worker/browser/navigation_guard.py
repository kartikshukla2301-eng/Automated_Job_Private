"""Security-first navigation guard strictly enforcing approved provider origins and anti-SSRF protections.

AUTHORITY:
- docs/AI_Job_Application_Agent_Architecture_v1.0_LOCKED.docx (Sections 11, 12)
- docs/BUILD_RULES.md
"""

import ipaddress
import logging
from pathlib import Path
from typing import List, Optional, Set
import urllib.parse
import urllib.request

from worker.browser.exceptions import (
    NavigationError,
    PrivateNetworkTargetError,
    UnsupportedDestinationError,
)

logger = logging.getLogger("worker.browser.navigation_guard")

DEFAULT_ALLOWED_DOMAINS: Set[str] = {
    "boards.greenhouse.io",
    "job-boards.greenhouse.io",
    "jobs.lever.co",
    "naukri.com",
    "www.naukri.com",
    "wellfound.com",
    "www.wellfound.com",
    "angel.co",
    "ashbyhq.com",
    "jobs.ashbyhq.com",
}

DISALLOWED_SCHEMES: Set[str] = {
    "http",
    "ftp",
    "javascript",
    "data",
    "ws",
    "wss",
    "vbscript",
}


class NavigationGuard:
    """Validates destination and redirect URLs before and during browser navigation."""

    def __init__(
        self,
        allowed_domains: Optional[Set[str]] = None,
        fixtures_dir: Optional[Path] = None,
    ) -> None:
        self.allowed_domains = allowed_domains or DEFAULT_ALLOWED_DOMAINS
        self.fixtures_dir = (fixtures_dir or Path("fixtures")).resolve()

    def is_private_or_loopback_host(self, host: str) -> bool:
        """Check if hostname or IP address resolves to private, loopback, or link-local range."""
        clean_host = host.strip().lower()

        # Direct string matches
        if clean_host in ("localhost", "127.0.0.1", "::1", "0.0.0.0", "[::1]"):
            return True

        if clean_host.endswith(".local") or clean_host.endswith(".internal"):
            return True

        # Check if the host string is an IP address
        try:
            # Strip brackets if IPv6
            ip_str = clean_host.strip("[]")
            ip = ipaddress.ip_address(ip_str)
            return (
                ip.is_private
                or ip.is_loopback
                or ip.is_link_local
                or ip.is_reserved
                or ip.is_multicast
            )
        except ValueError:
            # Not an IP address literal, hostname like 'boards.greenhouse.io'
            return False

    def validate_url(self, target: str) -> str:
        """Validate destination URL against approved provider domains or local fixtures.

        Returns:
            The normalized valid URL or file:// URI string.

        Raises:
            UnsupportedDestinationError: When scheme or domain is not approved.
            PrivateNetworkTargetError: When destination targets private/loopback network.
            NavigationError: When URL is malformed or invalid.
        """
        clean_target = target.strip()
        if not clean_target:
            raise NavigationError("Navigation target cannot be empty.")

        parsed = urllib.parse.urlparse(clean_target)

        # Check if Windows local path without scheme (e.g. C:\... or fixtures\...)
        is_windows_path = (
            len(parsed.scheme) == 1 and parsed.scheme.isalpha()
        ) or (not parsed.scheme and (clean_target.startswith(("/", "\\", ".")) or Path(clean_target).exists()))

        if is_windows_path or parsed.scheme == "file":
            return self._validate_local_fixture(clean_target, parsed)

        # External URL validation
        scheme = parsed.scheme.lower()

        if scheme in DISALLOWED_SCHEMES:
            raise UnsupportedDestinationError(
                target_url=clean_target,
                reason=f"Prohibited URL scheme '{scheme}'. Only secure 'https' or local 'file://' URIs are permitted.",
            )

        if scheme != "https":
            raise UnsupportedDestinationError(
                target_url=clean_target,
                reason=f"Unsupported scheme '{scheme}'. Only 'https' is permitted for external navigation.",
            )

        hostname = (parsed.hostname or "").lower()
        if not hostname:
            raise NavigationError(f"Malformed URL without hostname: '{clean_target}'")

        # Anti-SSRF check: block private, loopback, and internal addresses
        if self.is_private_or_loopback_host(hostname):
            raise PrivateNetworkTargetError(
                target_url=clean_target,
                hostname_or_ip=hostname,
            )

        # Verify domain is strictly within approved provider list
        if hostname not in self.allowed_domains:
            raise UnsupportedDestinationError(
                target_url=clean_target,
                reason=f"Domain '{hostname}' is not in approved provider origins {sorted(self.allowed_domains)}.",
            )

        # Path traversal guard in URL path
        if ".." in parsed.path:
            raise NavigationError(f"Directory traversal sequences forbidden in URL path: '{clean_target}'")

        return clean_target

    def _validate_local_fixture(self, raw_target: str, parsed: urllib.parse.ParseResult) -> str:
        """Validate and resolve local HTML test fixture path within approved fixtures directory."""
        if parsed.scheme == "file":
            local_path_str = urllib.request.url2pathname(parsed.path)
            # Normalize leading slash on Windows /C:/path -> C:/path
            if len(local_path_str) > 2 and local_path_str[0] == "/" and local_path_str[2] == ":":
                local_path_str = local_path_str[1:]
            resolved_path = Path(local_path_str).resolve()
        else:
            resolved_path = Path(raw_target).resolve()

        # Boundary enforcement: path must be strictly within self.fixtures_dir
        try:
            resolved_path.relative_to(self.fixtures_dir)
        except ValueError:
            raise UnsupportedDestinationError(
                target_url=raw_target,
                reason=f"Path traversal detected: '{resolved_path}' is outside approved fixtures directory '{self.fixtures_dir}'.",
            )

        if not resolved_path.exists():
            raise NavigationError(f"Local fixture file does not exist: '{resolved_path}'")

        if not resolved_path.is_file():
            raise NavigationError(f"Local fixture target is not a file: '{resolved_path}'")

        return resolved_path.as_uri()

    def validate_redirect(self, current_url: str, new_url: str) -> None:
        """Validate redirect destination during navigation lifecycle."""
        try:
            self.validate_url(new_url)
        except UnsupportedDestinationError as err:
            logger.warning(
                "Blocked prohibited redirect from '%s' to '%s': %s",
                current_url,
                new_url,
                err,
            )
            raise
