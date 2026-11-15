"""Deterministic Playwright locator resolution adhering to semantic and accessibility best practices.

AUTHORITY:
- docs/AI_Job_Application_Agent_Architecture_v1.0_LOCKED.docx (Section 11)
- docs/BUILD_RULES.md
"""

from typing import Optional


class LocatorResolver:
    """Generates robust, semantic Playwright selectors avoiding fragile absolute XPaths."""

    @staticmethod
    def resolve_selector(
        tag_name: str,
        label: Optional[str] = None,
        name: Optional[str] = None,
        html_id: Optional[str] = None,
        input_type: Optional[str] = None,
    ) -> str:
        """Derive the most reliable semantic selector for an element."""
        clean_tag = tag_name.lower().strip()

        # Strategy 1: HTML id (if valid and not purely numeric or auto-generated hash)
        if html_id and not html_id.isdigit():
            # Escape CSS special characters if needed
            safe_id = html_id.replace(":", "\\:").replace(".", "\\.")
            return f"#{safe_id}"

        # Strategy 2: Distinct name attribute
        if name:
            safe_name = name.replace('"', '\\"')
            return f'{clean_tag}[name="{safe_name}"]'

        # Strategy 3: Accessible label fallback
        if label:
            clean_label = label.strip()
            # Remove trailing asterisks often present for required fields
            clean_label = clean_label.rstrip("* \t\r\n")
            if clean_label:
                safe_label = clean_label.replace('"', '\\"')
                return f'internal:label="{safe_label}"i'

        # Strategy 4: Input type fallback
        if input_type:
            return f'{clean_tag}[type="{input_type}"]'

        return clean_tag

    @staticmethod
    def disambiguate_selector(base_selector: str, index: int) -> str:
        """Disambiguate multiple matching elements via nth-index without absolute XPath."""
        if index <= 0:
            return base_selector
        return f"{base_selector} >> nth={index}"
