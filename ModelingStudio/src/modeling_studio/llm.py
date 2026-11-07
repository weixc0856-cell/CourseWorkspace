from __future__ import annotations

import json
import re
import time
from typing import Any, TypeVar

import httpx
from ai_runtime import ContextBudget, ModelRoute
from pydantic import BaseModel, ValidationError

from .config import WorkflowConfig

T = TypeVar("T", bound=BaseModel)


class LLMError(RuntimeError):
    pass


def looks_like_schema(text: str) -> bool:
    head = text[:3000]
    return '"$defs"' in head or ('"properties"' in head and '"object_name"' not in head)


def extract_json(text: str) -> dict:
    cleaned = text.strip()
    fenced = re.search(r"```(?:json|python)?\s*(.*?)```", cleaned, re.S)
    if fenced:
        cleaned = fenced.group(1).strip()
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start < 0 or end <= start:
        raise LLMError(f"model response contains no JSON object: {text[:500]}")
    try:
        data = json.loads(cleaned[start : end + 1])
    except json.JSONDecodeError as exc:
        raise LLMError(f"invalid JSON from model: {exc}: {cleaned[:500]}") from exc
    if not isinstance(data, dict):
        raise LLMError("model returned JSON that is not an object")
    return data


class LLMClient:
    def __init__(
        self,
        config: WorkflowConfig,
        *,
        budget: ContextBudget | None = None,
        images: list[tuple[int, int]] | None = None,
    ):
        self.config = config
        self.budget = budget
        self.images = list(images or [])
        self._json_object_supported = True
        self.last_raw = ""
        self.last_error = ""

    def _post(self, payload: dict, route: ModelRoute | None = None) -> dict:
        base_url = route.base_url if route else self.config.llm.base_url
        api_key = route.api_key if route else self.config.llm.api_key
        trust_env = route.trust_env if route else False
        provider = route.provider if route else "local"
        last_error: Exception | None = None
        attempts = 1 + self.config.llm.max_retries
        for attempt in range(attempts):
            try:
                with httpx.Client(
                    base_url=base_url,
                    trust_env=trust_env,
                    timeout=self.config.llm.request_timeout_s,
                ) as client:
                    response = client.post(
                        "/chat/completions",
                        headers={"Authorization": f"Bearer {api_key}"},
                        json=payload,
                    )
                    if response.status_code in (400, 422) and payload.get("response_format"):
                        self._json_object_supported = False
                        payload = {k: v for k, v in payload.items() if k != "response_format"}
                        response = client.post(
                            "/chat/completions",
                            headers={"Authorization": f"Bearer {api_key}"},
                            json=payload,
                        )
                    if response.status_code >= 500:
                        raise httpx.HTTPStatusError(
                            f"server error {response.status_code}",
                            request=response.request,
                            response=response,
                        )
                    response.raise_for_status()
                    return response.json()
            except (httpx.HTTPError, ValueError) as exc:
                last_error = exc
                if attempt + 1 < attempts:
                    time.sleep(2.0 * (attempt + 1))
        raise LLMError(f"{provider} model request failed after {attempts} attempt(s): {last_error}")

    def chat(
        self,
        messages: list[dict[str, Any]],
        model_key: str,
        *,
        max_tokens: int = 2048,
        temperature: float = 0.1,
        json_object: bool = False,
        route: ModelRoute | None = None,
    ) -> tuple[str, dict]:
        if self.budget is not None:
            # Re-check on every attempt: retries append messages to the conversation.
            self.budget.check(messages, images=self.images)
        model = route.model if route else self.config.model(model_key).alias
        payload: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        if json_object and self._json_object_supported:
            payload["response_format"] = {"type": "json_object"}
        data = self._post(payload, route)
        try:
            choice = data["choices"][0]
            content = choice["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise LLMError(f"unexpected chat completion payload: {data}") from exc
        usage = data.get("usage", {})
        usage["finish_reason"] = choice.get("finish_reason")
        self.last_raw = content or ""
        return self.last_raw, usage

    def chat_json(
        self,
        messages: list[dict[str, Any]],
        model_key: str,
        contract: type[T],
        *,
        max_tokens: int = 2048,
        temperature: float = 0.1,
        attempts: int = 2,
        route: ModelRoute | None = None,
    ) -> tuple[T, dict]:
        conversation = list(messages)
        last_error = ""
        for attempt in range(attempts):
            content, usage = self.chat(
                conversation,
                model_key,
                max_tokens=max_tokens,
                temperature=temperature,
                json_object=True,
                route=route,
            )
            schema_echo = False
            try:
                if looks_like_schema(content):
                    schema_echo = True
                    raise LLMError(
                        "model returned the JSON Schema definition instead of a data instance"
                    )
                data = extract_json(content)
                return contract.model_validate(data), usage
            except (LLMError, ValidationError) as exc:
                last_error = str(exc)[:1500]
                hint = ""
                if schema_echo:
                    hint += (
                        " Do not output the schema. Output a data object with the required "
                        "top-level keys."
                    )
                if usage.get("finish_reason") == "length":
                    hint += (
                        " Your previous response hit the token limit. Return a shorter "
                        "object: only required fields, at most 8 parts."
                    )
                conversation = [
                    *messages,
                    {"role": "assistant", "content": content},
                    {
                        "role": "user",
                        "content": (
                            "The previous JSON failed validation. Fix only the reported "
                            "problems and return one complete JSON object, no prose."
                            f"{hint}\n{last_error}"
                        ),
                    },
                ]
        self.last_error = last_error
        raise LLMError(f"model did not produce a valid {contract.__name__}: {last_error}")
