"""Privacy gate: decide whether this run may send content to the provider.

Code review may be sent to the configured provider.  Document review needs an
explicit file whitelist.  Course content is local to the user and is only sent
after a per-run ``--allow-external-content`` grant.  Tracked in Git never means
"safe to send".
"""

from __future__ import annotations

from dataclasses import dataclass, field
from urllib.parse import urlparse

from .schema import ReviewType

LOCAL_HOSTS = frozenset({"localhost", "127.0.0.1", "::1", "0.0.0.0", ""})


def endpoint_host(base_url: str | None) -> str | None:
    if not base_url:
        return None
    host = urlparse(base_url).hostname
    return host.lower() if host else None


def is_external(host: str | None) -> bool:
    return bool(host) and host not in LOCAL_HOSTS


@dataclass(frozen=True)
class PrivacyDecision:
    allowed: bool
    external_content: bool
    authorization: str | None
    reason: str | None = None
    notes: list[str] = field(default_factory=list)


def decide(
    review_type: ReviewType,
    *,
    allow_external_content: bool,
    host: str | None,
    explicit_files: tuple[str, ...] = (),
) -> PrivacyDecision:
    external = is_external(host)
    notes: list[str] = []
    if external:
        notes.append(f"content leaves this machine to {host}")
    else:
        notes.append("provider endpoint is local; content stays on this machine")

    if review_type is ReviewType.code:
        return PrivacyDecision(
            allowed=True,
            external_content=external,
            authorization="code_default",
            notes=notes,
        )

    if review_type is ReviewType.docs:
        if not explicit_files:
            return PrivacyDecision(
                allowed=False,
                external_content=external,
                authorization=None,
                reason="document review requires an explicit -Files whitelist; "
                "no automatic docs/ scan",
                notes=notes,
            )
        return PrivacyDecision(
            allowed=True,
            external_content=external,
            authorization="explicit_files",
            notes=notes,
        )

    if review_type is ReviewType.course:
        if external and not allow_external_content:
            return PrivacyDecision(
                allowed=False,
                external_content=external,
                authorization=None,
                reason="course content is user-owned; pass -AllowExternalContent "
                "for this run to send it to a remote provider",
                notes=notes,
            )
        authorization = (
            "explicit_external_content" if external else "local_provider"
        )
        return PrivacyDecision(
            allowed=True,
            external_content=external,
            authorization=authorization,
            notes=notes,
        )

    return PrivacyDecision(
        allowed=False,
        external_content=external,
        authorization=None,
        reason=f"unsupported review type: {review_type}",
        notes=notes,
    )


__all__ = [
    "LOCAL_HOSTS",
    "PrivacyDecision",
    "decide",
    "endpoint_host",
    "is_external",
]
