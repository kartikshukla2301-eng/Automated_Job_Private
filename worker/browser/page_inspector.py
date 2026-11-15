"""Deterministic form element inspection and metadata extraction.

AUTHORITY:
- docs/AI_Job_Application_Agent_Architecture_v1.0_LOCKED.docx (Sections 11, 12)
- docs/BUILD_RULES.md
"""

from html.parser import HTMLParser
import logging
import re
from typing import Any, Dict, List, Optional

from worker.browser.exceptions import FormInspectionError
from worker.browser.field_detector import DetectedField, is_sensitive_field
from worker.browser.locator_resolver import LocatorResolver

logger = logging.getLogger("worker.browser.page_inspector")


class PageInspector:
    """Inspects live Playwright pages or offline HTML fixtures to discover form fields."""

    JS_INSPECTION_SCRIPT = """
    () => {
      const elements = Array.from(document.querySelectorAll('input, textarea, select'));
      const items = [];

      for (const el of elements) {
        const tag = el.tagName.toLowerCase();
        let type = (el.getAttribute('type') || (tag === 'textarea' ? 'textarea' : tag === 'select' ? 'select' : 'text')).toLowerCase();
        
        let label = '';
        if (el.id) {
          const lEl = document.querySelector(`label[for="${CSS.escape(el.id)}"]`);
          if (lEl) label = lEl.innerText.trim();
        }
        if (!label) {
          const parentLabel = el.closest('label');
          if (parentLabel) label = parentLabel.innerText.trim();
        }
        if (!label && el.getAttribute('aria-label')) {
          label = el.getAttribute('aria-label').trim();
        }
        if (!label) {
          const fieldContainer = el.closest('.field, .form-group, .application-field, [data-qa]');
          if (fieldContainer) {
            const containerLabel = fieldContainer.querySelector('label, .label, legend');
            if (containerLabel) label = containerLabel.innerText.trim();
          }
        }
        if (!label && el.placeholder) {
          label = el.placeholder.trim();
        }
        if (!label && el.name) {
          label = el.name;
        }

        let options = [];
        if (tag === 'select') {
          options = Array.from(el.querySelectorAll('option'))
            .map(o => o.innerText.trim())
            .filter(t => t.length > 0 && !t.startsWith('Select') && !t.startsWith('Choose'));
        }

        const required = el.hasAttribute('required') || el.getAttribute('aria-required') === 'true' || label.includes('*');
        const disabled = el.disabled || el.hasAttribute('disabled');
        const readonly = el.readOnly || el.hasAttribute('readonly');

        items.push({
          tag_name: tag,
          input_type: type,
          name: el.name || null,
          html_id: el.id || null,
          label: label || 'Unlabeled field',
          placeholder: el.placeholder || null,
          required: required,
          disabled: disabled,
          readonly: readonly,
          options: options,
        });
      }
      return items;
    }
    """

    async def inspect_page(self, page: Any) -> List[DetectedField]:
        """Inspect a live Playwright page instance and extract all form fields."""
        try:
            raw_items = await page.evaluate(self.JS_INSPECTION_SCRIPT)
            return self._normalize_raw_items(raw_items)
        except Exception as exc:
            raise FormInspectionError(f"Failed to inspect DOM on current page: {exc}") from exc

    def inspect_html(self, html_content: str) -> List[DetectedField]:
        """Inspect an offline HTML string and extract all form fields."""
        parser = _HTMLFormInspectorParser()
        parser.feed(html_content)
        return self._normalize_raw_items(parser.raw_items)

    def _normalize_raw_items(self, raw_items: List[Dict[str, Any]]) -> List[DetectedField]:
        """Group radios, deduplicate labels, resolve semantic selectors, and build DetectedField models."""
        grouped_radios: Dict[str, Dict[str, Any]] = {}
        processed: List[DetectedField] = []
        seen_field_ids: Dict[str, int] = {}
        seen_selectors: Dict[str, int] = {}

        for item in raw_items:
            tag_name = item.get("tag_name", "input")
            input_type = item.get("input_type", "text")
            name = item.get("name")
            html_id = item.get("html_id")
            label = item.get("label", "Unlabeled field")
            required = item.get("required", False)
            disabled = item.get("disabled", False)
            readonly = item.get("readonly", False)
            placeholder = item.get("placeholder")
            options = item.get("options", [])

            # Aggregate radio buttons sharing the same name
            if input_type == "radio" and name:
                opt_val = label if (label and label != "Unlabeled field") else (item.get("value") or "Option")
                if name not in grouped_radios:
                    grouped_radios[name] = {
                        "tag_name": "input",
                        "input_type": "radio",
                        "name": name,
                        "html_id": html_id,
                        "label": label,
                        "required": required,
                        "disabled": disabled,
                        "readonly": readonly,
                        "placeholder": None,
                        "options": [opt_val],
                    }
                else:
                    if opt_val not in grouped_radios[name]["options"]:
                        grouped_radios[name]["options"].append(opt_val)
                continue

            # Base field ID
            base_id = html_id or name or self._slugify(label) or "field"
            count = seen_field_ids.get(base_id, 0)
            seen_field_ids[base_id] = count + 1
            field_id = base_id if count == 0 else f"{base_id}_{count}"

            # Semantic selector
            base_selector = LocatorResolver.resolve_selector(
                tag_name=tag_name,
                label=label,
                name=name,
                html_id=html_id,
                input_type=input_type,
            )
            sel_count = seen_selectors.get(base_selector, 0)
            seen_selectors[base_selector] = sel_count + 1
            selector = LocatorResolver.disambiguate_selector(base_selector, sel_count)

            is_sensitive = is_sensitive_field(
                label=label,
                name=name,
                html_id=html_id,
                input_type=input_type,
            )

            detected = DetectedField(
                field_id=field_id,
                label=label,
                name=name,
                html_id=html_id,
                tag_name=tag_name,
                input_type=input_type,
                required=required,
                placeholder=placeholder,
                options=options,
                disabled=disabled,
                readonly=readonly,
                semantic_selector=selector,
                confidence=1.0 if (html_id or name) else 0.85,
                is_sensitive=is_sensitive,
            )
            processed.append(detected)

        # Process grouped radio groups
        for r_name, r_data in grouped_radios.items():
            base_id = r_name
            count = seen_field_ids.get(base_id, 0)
            seen_field_ids[base_id] = count + 1
            field_id = base_id if count == 0 else f"{base_id}_{count}"

            base_selector = f'input[type="radio"][name="{r_name}"]'
            is_sensitive = is_sensitive_field(
                label=r_data["label"],
                name=r_name,
                html_id=r_data["html_id"],
                input_type="radio",
            )
            processed.append(
                DetectedField(
                    field_id=field_id,
                    label=r_data["label"],
                    name=r_name,
                    html_id=r_data["html_id"],
                    tag_name="input",
                    input_type="radio",
                    required=r_data["required"],
                    placeholder=None,
                    options=r_data["options"],
                    disabled=r_data["disabled"],
                    readonly=r_data["readonly"],
                    semantic_selector=base_selector,
                    confidence=0.95,
                    is_sensitive=is_sensitive,
                )
            )

        return processed

    @staticmethod
    def _slugify(text: str) -> str:
        clean = re.sub(r"[^a-zA-Z0-9_]+", "_", text.strip().lower())
        return clean.strip("_")[:50]


class _HTMLFormInspectorParser(HTMLParser):
    """Offline HTML parser for test environments."""

    def __init__(self) -> None:
        super().__init__()
        self.raw_items: List[Dict[str, Any]] = []
        self._labels_by_for: Dict[str, str] = {}
        self._current_label_for: Optional[str] = None
        self._current_label_text: Optional[List[str]] = None
        self._enclosing_label_input: Optional[Dict[str, Any]] = None
        self._current_select: Optional[Dict[str, Any]] = None
        self._in_option: bool = False
        self._current_option_text: List[str] = []

    def handle_starttag(self, tag: str, attrs: List[tuple]) -> None:
        attrs_dict = {k.lower(): v for k, v in attrs if k}

        if tag == "label":
            self._current_label_for = attrs_dict.get("for")
            self._current_label_text = []
            self._enclosing_label_input = None

        elif tag in ("input", "textarea"):
            input_type = attrs_dict.get("type", "textarea" if tag == "textarea" else "text").lower()
            html_id = attrs_dict.get("id")
            name = attrs_dict.get("name")
            required = "required" in attrs_dict or attrs_dict.get("aria-required") == "true"
            disabled = "disabled" in attrs_dict
            readonly = "readonly" in attrs_dict
            placeholder = attrs_dict.get("placeholder")
            aria_label = attrs_dict.get("aria-label")
            value = attrs_dict.get("value")

            label = self._labels_by_for.get(html_id, "") if html_id else ""
            if not label and aria_label:
                label = aria_label
            if not label and placeholder:
                label = placeholder

            item = {
                "tag_name": tag,
                "input_type": input_type,
                "name": name,
                "html_id": html_id,
                "label": label or "Unlabeled field",
                "placeholder": placeholder,
                "required": required,
                "disabled": disabled,
                "readonly": readonly,
                "options": [],
                "value": value,
            }
            self.raw_items.append(item)
            if self._current_label_text is not None and not self._current_label_for:
                self._enclosing_label_input = item

        elif tag == "select":
            html_id = attrs_dict.get("id")
            name = attrs_dict.get("name")
            required = "required" in attrs_dict or attrs_dict.get("aria-required") == "true"
            disabled = "disabled" in attrs_dict
            readonly = "readonly" in attrs_dict
            label = self._labels_by_for.get(html_id, "") if html_id else ""

            self._current_select = {
                "tag_name": "select",
                "input_type": "select",
                "name": name,
                "html_id": html_id,
                "label": label or "Unlabeled select",
                "placeholder": None,
                "required": required,
                "disabled": disabled,
                "readonly": readonly,
                "options": [],
            }
            self.raw_items.append(self._current_select)

        elif tag == "option" and self._current_select is not None:
            self._in_option = True
            self._current_option_text = []

    def handle_endtag(self, tag: str) -> None:
        if tag == "label":
            if self._current_label_text is not None:
                label_str = "".join(self._current_label_text).strip()
                if self._current_label_for:
                    self._labels_by_for[self._current_label_for] = label_str
                    # Update previously parsed inputs if they shared this id
                    for item in self.raw_items:
                        if item.get("html_id") == self._current_label_for and item.get("label") == "Unlabeled field":
                            item["label"] = label_str
                elif self._enclosing_label_input:
                    self._enclosing_label_input["label"] = label_str
            self._current_label_for = None
            self._current_label_text = None
            self._enclosing_label_input = None

        elif tag == "select":
            self._current_select = None

        elif tag == "option" and self._in_option:
            self._in_option = False
            opt_str = "".join(self._current_option_text).strip()
            if self._current_select is not None and opt_str:
                self._current_select["options"].append(opt_str)
            self._current_option_text = []

    def handle_data(self, data: str) -> None:
        if self._current_label_text is not None:
            self._current_label_text.append(data)
        if self._in_option:
            self._current_option_text.append(data)
