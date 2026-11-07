from __future__ import annotations

import json
import re
import time

import httpx

from ai_runtime import ClaudeCodeError, ClaudeCodeUnavailable, claude_code_complete

from .config import ReviewConfig


class OnlineError(RuntimeError):
    def __init__(self, message: str, *, status: int | None = None, raw: str = ""):
        self.status = status
        self.raw = raw
        super().__init__(message)


def extract_json(text: str) -> dict:
    cleaned = text.strip()
    fenced = re.search(r"```(?:json)?\s*(.*?)```", cleaned, re.S)
    if fenced:
        cleaned = fenced.group(1).strip()
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start < 0 or end <= start:
        raise OnlineError(f"response contains no JSON object: {text[:500]}", raw=text)
    try:
        data = json.loads(cleaned[start : end + 1])
    except json.JSONDecodeError as exc:
        raise OnlineError(f"invalid JSON from online model: {exc}", raw=text) from exc
    if not isinstance(data, dict):
        raise OnlineError("online model returned JSON that is not an object", raw=text)
    return data


class OnlineClient:
    """Minimal OpenAI-compatible chat client.

    Credentials come from the caller; this class never reads or stores config
    files. Requests use ``trust_env=False`` so a local proxy cannot intercept.
    """

    def __init__(self, config: ReviewConfig, api_key: str | None = None):
        self.config = config
        self.api_key = api_key
        self.last_raw = ""
        self._json_mode = True

    def chat_json(self, messages: list[dict], *, max_tokens: int | None = None) -> tuple[dict, dict]:
        if self.config.backend == "claude_code":
            return self._claude_json(messages)
        payload = {
            "model": self.config.model.model,
            "messages": messages,
            "max_tokens": max_tokens or self.config.model.max_tokens,
            "temperature": self.config.model.temperature,
        }
        attempts = 1 + self.config.model.retries
        last_error: Exception | None = None
        for attempt in range(attempts):
            try:
                return self._post(payload)
            except OnlineError as exc:
                last_error = exc
                if exc.status in (400, 422) and self._json_mode:
                    self._json_mode = False
                    payload = {k: v for k, v in payload.items() if k != "response_format"}
                    continue
                if exc.status is not None and exc.status < 500 and exc.status != 429:
                    raise
                if attempt + 1 < attempts:
                    time.sleep(2.0 * (attempt + 1))
        raise OnlineError(f"online model request failed after {attempts} attempt(s): {last_error}")

    def _claude_json(self, messages: list[dict]) -> tuple[dict, dict]:
        cc = self.config.claude_code
        if cc is None:
            raise OnlineError("claude-code backend is not configured")
        system = "\n\n".join(
            str(item.get("content", "")) for item in messages if item.get("role") == "system"
        )
        body = "\n\n".join(
            f"{str(item.get('role', 'user')).upper()}:\n{item.get('content', '')}"
            for item in messages
            if item.get("role") != "system"
        )
        body += "\n\nReturn only one JSON object. No markdown fences, no commentary."
        try:
            result = claude_code_complete(
                cc,
                body,
                system=system or None,
                timeout_s=self.config.model.timeout_s,
                tools=False,
            )
        except ClaudeCodeUnavailable as exc:
            raise OnlineError(str(exc)) from exc
        except ClaudeCodeError as exc:
            raise OnlineError(str(exc)) from exc
        self.last_raw = result.content
        return extract_json(result.content), dict(result.usage)

    def _post(self, payload: dict) -> tuple[dict, dict]:
        if self._json_mode:
            payload = {**payload, "response_format": {"type": "json_object"}}
        try:
            with httpx.Client(
                base_url=self.config.model.base_url,
                trust_env=False,
                timeout=self.config.model.timeout_s,
            ) as client:
                response = client.post(
                    "/chat/completions",
                    headers={"Authorization": f"Bearer {self.api_key}"},
                    json=payload,
                )
        except httpx.HTTPError as exc:
            raise OnlineError(f"online model unreachable: {exc}") from exc

        if response.status_code >= 400:
            raise OnlineError(
                f"online model returned {response.status_code}: {response.text[:500]}",
                status=response.status_code,
                raw=response.text,
            )
        try:
            data = response.json()
            choice = data["choices"][0]
            content = choice["message"]["content"] or ""
        except (ValueError, KeyError, IndexError, TypeError) as exc:
            raise OnlineError(f"unexpected completion payload: {response.text[:500]}", raw=response.text) from exc
        self.last_raw = content
        usage = dict(data.get("usage") or {})
        usage["finish_reason"] = choice.get("finish_reason")
        return extract_json(content), usage
