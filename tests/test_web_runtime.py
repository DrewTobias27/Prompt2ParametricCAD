"""Tests for production web-service safeguards."""

import os

import pytest

from prompt2cad.web_runtime import cleanup_step_files
from prompt2cad.web_runtime import environment_int
from prompt2cad.web_runtime import SlidingWindowRateLimiter


def test_rate_limiter_enforces_sliding_window():
    limiter = SlidingWindowRateLimiter(limit=2, window_seconds=10)

    assert limiter.check("client", now=0) == (True, 1, 0)
    assert limiter.check("client", now=1) == (True, 0, 0)
    assert limiter.check("client", now=2) == (False, 0, 8)
    assert limiter.check("client", now=11) == (True, 1, 0)


def test_rate_limiter_can_be_disabled():
    limiter = SlidingWindowRateLimiter(limit=0, window_seconds=10)

    assert limiter.check("client", now=0) == (True, 0, 0)


def test_cleanup_step_files_removes_expired_and_excess_files(tmp_path):
    oldest = tmp_path / "oldest.step"
    middle = tmp_path / "middle.step"
    newest = tmp_path / "newest.step"
    ignored = tmp_path / "keep.json"
    for path in (oldest, middle, newest, ignored):
        path.write_text("test", encoding="utf-8")

    os.utime(oldest, (10, 10))
    os.utime(middle, (80, 80))
    os.utime(newest, (90, 90))

    removed = cleanup_step_files(
        tmp_path,
        max_age_seconds=50,
        max_files=1,
        now=100,
    )

    assert set(removed) == {oldest, middle}
    assert newest.exists()
    assert ignored.exists()


def test_environment_int_rejects_invalid_configuration(monkeypatch):
    monkeypatch.setenv("PROMPT2CAD_TEST_LIMIT", "not-a-number")

    with pytest.raises(ValueError, match="must be an integer"):
        environment_int("PROMPT2CAD_TEST_LIMIT", 5)
