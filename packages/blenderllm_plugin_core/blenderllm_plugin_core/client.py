"""OpenAI Responses API client using only the Python standard library."""

from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from typing import Any

from .models import AssistantResult, parse_assistant_result, response_text
from .schema import RESPONSE_TEXT_FORMAT


API_URL = "https://api.openai.com/v1/responses"


class OpenAIResponsesClient:
    """Small dependency-free client that works inside Blender's Python."""

    def __init__(
        self,
        api_key: str,
        api_url: str = API_URL,
        timeout: int = 90,
        organization: str = "",
        project: str = "",
    ) -> None:
        self.api_key = normalize_api_key(api_key)
        self.api_url = api_url
        self.timeout = timeout
        self.organization = organization.strip()
        self.project = project.strip()

    def headers(self) -> dict[str, str]:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        if self.organization:
            headers["OpenAI-Organization"] = self.organization
        if self.project:
            headers["OpenAI-Project"] = self.project
        return headers

    def create_blender_response(self, *, model: str, instructions: str, user_input: str) -> AssistantResult:
        if not self.api_key:
            raise RuntimeError("Add your OpenAI API key in BlenderLLM-Plugin preferences or OPENAI_API_KEY.")

        body: dict[str, Any] = {
            "model": model.strip(),
            "instructions": instructions,
            "input": user_input,
            "text": {"format": RESPONSE_TEXT_FORMAT},
        }

        request = urllib.request.Request(
            self.api_url,
            data=json.dumps(body).encode("utf-8"),
            headers=self.headers(),
            method="POST",
        )

        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as handle:
                payload = json.loads(handle.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"OpenAI request failed: HTTP {exc.code}: {detail}") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"OpenAI request failed: {exc.reason}") from exc

        text = response_text(payload)
        if not text:
            raise RuntimeError("OpenAI returned no response text.")
        return parse_assistant_result(text)

    def test_authentication(self) -> dict[str, Any]:
        if not self.api_key:
            raise RuntimeError("Add your OpenAI API key in BlenderLLM-Plugin preferences or OPENAI_API_KEY.")

        request = urllib.request.Request(
            "https://api.openai.com/v1/models",
            headers=self.headers(),
            method="GET",
        )

        try:
            with urllib.request.urlopen(request, timeout=30) as handle:
                payload = json.loads(handle.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"OpenAI key test failed: HTTP {exc.code}: {detail}") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"OpenAI key test failed: {exc.reason}") from exc

        return payload


def normalize_api_key(value: str) -> str:
    """Accept raw keys or common pasted environment assignment forms."""

    cleaned = value.strip().strip("\"'")
    if "=" in cleaned and re.match(r"^[A-Za-z_][A-Za-z0-9_]*\s*=", cleaned):
        cleaned = cleaned.split("=", 1)[1].strip().strip("\"'")
    cleaned = re.sub(r"[\s\u200b\u200c\u200d\ufeff]+", "", cleaned)
    return cleaned


def api_key_fingerprint(value: str) -> str:
    key = normalize_api_key(value)
    if not key:
        return "empty"
    if len(key) <= 12:
        return f"{key[:4]}... ({len(key)} chars)"
    return f"{key[:12]}...{key[-10:]} ({len(key)} chars)"
