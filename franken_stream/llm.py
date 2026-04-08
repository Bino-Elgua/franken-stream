import os
import re
from typing import Optional

import requests


class LLMClient:
    """Basic helper to adapt scraping selectors using an LLM endpoint."""

    def __init__(self, endpoint: Optional[str] = None):
        self.endpoint = endpoint or os.environ.get("FRANKEN_STREAM_LLM_ENDPOINT")

    @property
    def enabled(self) -> bool:
        return bool(self.endpoint)

    def adapt_selector(
        self,
        provider: str,
        failed_html: str,
        target: str = "video embed URL",
    ) -> Optional[str]:
        """Ask an LLM for a CSS selector when extraction fails."""
        if not self.enabled:
            return None

        prompt = (
            f"You are a scraping assistant. Given the following HTML fragment for {provider}, "
            f"provide a single CSS selector that extracts the {target}. "
            "Return only the selector string, no explanation."
            f"\n\nHTML:\n{failed_html[:2000]}"
        )

        try:
            response = requests.post(
                self.endpoint,
                json={"prompt": prompt, "max_tokens": 128},
                timeout=10,
            )
            response.raise_for_status()
            text = response.text.strip()
            selector = self._clean_selector(text)
            return selector
        except Exception:
            return None

    @staticmethod
    def _clean_selector(text: str) -> Optional[str]:
        selector = text.strip()
        selector = re.sub(r"^['\"]|['\"]$", "", selector)
        if selector and len(selector) < 256:
            return selector
        return None
