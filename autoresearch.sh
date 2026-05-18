#!/usr/bin/env bash
set -euo pipefail

export PYTHONHASHSEED=0
export LIBRARY_PORTAL_ENVIRONMENT=production
export LIBRARY_PORTAL_API_KEY=autoresearch-key
export LIBRARY_PORTAL_LOG_LEVEL=ERROR
export LIBRARY_PORTAL_METRICS_ENABLED=false

python scripts/benchmarks/benchmark_architecture.py
