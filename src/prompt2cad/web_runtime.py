"""Small runtime safeguards for the public Prompt2CAD web service."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from math import ceil
import os
from pathlib import Path
from threading import Lock
from time import monotonic, time


def environment_int(name: str, default: int, *, minimum: int = 0) -> int:
    """Read a bounded integer setting and fail clearly on bad configuration."""
    raw_value = os.getenv(name)
    if raw_value is None or not raw_value.strip():
        return default

    try:
        value = int(raw_value)
    except ValueError as error:
        raise ValueError(f"{name} must be an integer") from error

    if value < minimum:
        raise ValueError(f"{name} must be at least {minimum}")
    return value


@dataclass
class SlidingWindowRateLimiter:
    """Bound requests per client without requiring an external datastore."""

    limit: int
    window_seconds: int
    _requests: dict[str, deque[float]] = field(default_factory=dict)
    _lock: Lock = field(default_factory=Lock)

    def check(
        self,
        client_key: str,
        *,
        now: float | None = None,
    ) -> tuple[bool, int, int]:
        """Return allowed, remaining requests, and retry-after seconds."""
        if self.limit == 0:
            return True, 0, 0

        checked_at = monotonic() if now is None else now
        cutoff = checked_at - self.window_seconds

        with self._lock:
            requests = self._requests.setdefault(client_key, deque())
            while requests and requests[0] <= cutoff:
                requests.popleft()

            if len(requests) >= self.limit:
                retry_after = max(1, ceil(requests[0] + self.window_seconds - checked_at))
                return False, 0, retry_after

            requests.append(checked_at)
            return True, self.limit - len(requests), 0


def cleanup_step_files(
    directory: Path,
    *,
    max_age_seconds: int,
    max_files: int,
    now: float | None = None,
) -> list[Path]:
    """Remove expired STEP downloads and cap retained files by recency."""
    if not directory.exists():
        return []

    checked_at = time() if now is None else now
    step_files = [path for path in directory.glob("*.step") if path.is_file()]
    removed: list[Path] = []
    retained: list[Path] = []

    for path in step_files:
        try:
            is_expired = (
                max_age_seconds > 0
                and checked_at - path.stat().st_mtime > max_age_seconds
            )
            if is_expired:
                path.unlink()
                removed.append(path)
            else:
                retained.append(path)
        except FileNotFoundError:
            continue

    if max_files > 0 and len(retained) > max_files:
        retained.sort(key=lambda path: path.stat().st_mtime, reverse=True)
        for path in retained[max_files:]:
            try:
                path.unlink()
                removed.append(path)
            except FileNotFoundError:
                continue

    return removed
