#!/usr/bin/env python3
"""Focused regression gate for the next bounded autoresearch round.

These checks encode only review findings that are either still live on current
main or important enough to keep from regressing while the next round runs.
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from fastapi import FastAPI
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
DATA_DIR = ROOT / "data" / "classified" / "organized"
API_KEY = "autoresearch-key"


@dataclass
class CheckSuite:
    checks: int = 0
    failures: list[str] = field(default_factory=list)

    def require(self, condition: bool, message: str) -> None:
        self.checks += 1
        if not condition:
            self.failures.append(message)


def _last_error_line(stderr: str) -> str:
    for line in reversed(stderr.splitlines()):
        if line.strip():
            return line.strip()
    return "<no stderr>"


def check_metrics_enabled_reload(suite: CheckSuite) -> None:
    """app_v2.main must be reloadable when Prometheus metrics are enabled."""
    code = (
        "import importlib; "
        "import app_v2.main as main_module; "
        "importlib.reload(main_module); "
        "print('metrics reload ok')"
    )
    env = os.environ.copy()
    env.update(
        {
            "LIBRARY_PORTAL_ENVIRONMENT": "production",
            "LIBRARY_PORTAL_API_KEY": API_KEY,
            "LIBRARY_PORTAL_METRICS_ENABLED": "true",
            "LIBRARY_PORTAL_LOG_LEVEL": "ERROR",
        }
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    suite.require(
        result.returncode == 0,
        "metrics-enabled app_v2.main reload failed: " + _last_error_line(result.stderr),
    )


def check_public_path_bypass_stays_closed(suite: CheckSuite) -> None:
    """Traversal-like public paths must not reach protected handlers unauthenticated."""
    from app_v2.middleware.auth import APIKeyMiddleware

    app = FastAPI()
    app.add_middleware(APIKeyMiddleware, api_key=API_KEY, environment="production")

    @app.get("/health")
    def health() -> dict[str, bool]:
        return {"ok": True}

    @app.get("/api/secure")
    def secure() -> dict[str, bool]:
        return {"ok": True}

    client = TestClient(app)
    for path in (
        "/health/../api/secure",
        "/health/..%2fapi/secure",
        "/health/%2E%2E/api/secure",
        "//api/secure",
    ):
        status_code = client.get(path).status_code
        suite.require(
            status_code != 200, f"unauthenticated bypass succeeded for {path}"
        )


def check_invalid_keys_share_ip_rate_limit_bucket(suite: CheckSuite) -> None:
    """Rotating bogus API keys must not bypass failed-auth rate limiting."""
    from app_v2.middleware.auth import APIKeyMiddleware
    from app_v2.middleware.rate_limit import RateLimitMiddleware

    app = FastAPI()
    app.add_middleware(APIKeyMiddleware, api_key=API_KEY, environment="production")
    app.add_middleware(
        RateLimitMiddleware,
        max_requests=2,
        window_seconds=60,
        valid_api_keys=[API_KEY],
    )

    @app.get("/api/secure")
    def secure() -> dict[str, bool]:
        return {"ok": True}

    client = TestClient(app)
    suite.require(
        client.get("/api/secure", headers={"X-API-Key": "wrong-1"}).status_code == 403,
        "first invalid key request should fail auth, not rate limit",
    )
    suite.require(
        client.get("/api/secure", headers={"X-API-Key": "wrong-2"}).status_code == 403,
        "second invalid key request should fail auth, not rate limit",
    )
    suite.require(
        client.get("/api/secure", headers={"X-API-Key": "wrong-3"}).status_code == 429,
        "rotating invalid keys did not share the IP rate-limit bucket",
    )


def check_failed_reload_preserves_existing_index(suite: CheckSuite) -> None:
    """A failed reload must not replace the currently serving index."""
    from app_v2.data_loader import DataLoader
    from app_v2.services.indexing import PaperIndex

    index = PaperIndex()
    index._load_from_directory(DataLoader(DATA_DIR))
    before_count = index._paper_count
    before_urls = {paper["url"] for paper in index.papers if paper.get("url")}

    with tempfile.TemporaryDirectory(prefix="autoresearch-bad-data-") as tmp:
        Path(tmp, "broken.json").write_text("{not valid json", encoding="utf-8")
        try:
            index._reload_from_directory(DataLoader(Path(tmp)))
        except RuntimeError:
            pass
        else:
            suite.require(False, "corrupt data reload did not fail")

    after_urls = {paper["url"] for paper in index.papers if paper.get("url")}
    suite.require(
        index._paper_count == before_count, "failed reload changed paper count"
    )
    suite.require(after_urls == before_urls, "failed reload changed indexed URLs")


def main() -> int:
    suite = CheckSuite()
    check_failures: dict[str, int] = {}
    checks: tuple[tuple[str, Any], ...] = (
        ("metrics_enabled_reload", check_metrics_enabled_reload),
        ("public_path_bypass", check_public_path_bypass_stays_closed),
        (
            "invalid_key_rate_limit_bucket",
            check_invalid_keys_share_ip_rate_limit_bucket,
        ),
        ("failed_reload_preserves_index", check_failed_reload_preserves_existing_index),
    )

    for name, check in checks:
        before = len(suite.failures)
        check(suite)
        failures = len(suite.failures) - before
        check_failures[name] = failures
        status = "pass" if failures == 0 else "fail"
        print(f"CHECK {name}={status}")

    total_failures = len(suite.failures)
    print(f"NEXT_ROUND_CHECKS checks={suite.checks} failures={total_failures}")
    print(f"METRIC next_round_failures={total_failures}")
    print(f"METRIC next_round_checks={suite.checks}")
    for name, failures in check_failures.items():
        print(f"METRIC {name}_failures={failures}")

    if suite.failures:
        print("FAILURES:", file=sys.stderr)
        for failure in suite.failures:
            print(f"- {failure}", file=sys.stderr)
    return 1 if suite.failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
