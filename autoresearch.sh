#!/usr/bin/env bash
set -euo pipefail

usage() {
  printf 'Usage: %s [--once|--loop]\n' "${0##*/}"
  printf '\n'
  printf 'Runs one deterministic benchmark round by default. Use --loop for continuous local runs.\n'
  printf '\n'
  printf 'Environment:\n'
  printf '  AUTORESEARCH_MAX_ROUNDS        Run this many rounds; implies --loop when set.\n'
  printf '  AUTORESEARCH_INTERVAL_SECONDS  Sleep between loop rounds; default 0.\n'
  printf '  AUTORESEARCH_STOP_ON_FAILURE   Exit loop on a failing round when true; default false.\n'
}

run_loop=false
case "${1:-}" in
  --once|-1)
    shift
    ;;
  --loop)
    run_loop=true
    shift
    ;;
  --help|-h)
    usage
    exit 0
    ;;
  "")
    ;;
  *)
    usage >&2
    exit 2
    ;;
esac

if (($# > 0)); then
  usage >&2
  exit 2
fi

export PYTHONHASHSEED="${PYTHONHASHSEED:-0}"
export LIBRARY_PORTAL_ENVIRONMENT="${LIBRARY_PORTAL_ENVIRONMENT:-production}"
export LIBRARY_PORTAL_API_KEY="${LIBRARY_PORTAL_API_KEY:-autoresearch-key}"
export LIBRARY_PORTAL_LOG_LEVEL="${LIBRARY_PORTAL_LOG_LEVEL:-ERROR}"
export LIBRARY_PORTAL_METRICS_ENABLED="${LIBRARY_PORTAL_METRICS_ENABLED:-false}"

: "${AUTORESEARCH_MAX_ROUNDS:=}"
: "${AUTORESEARCH_INTERVAL_SECONDS:=0}"
: "${AUTORESEARCH_STOP_ON_FAILURE:=false}"

case "$AUTORESEARCH_MAX_ROUNDS" in
  ""|*[!0-9]*)
    if [[ -n "$AUTORESEARCH_MAX_ROUNDS" ]]; then
      printf 'AUTORESEARCH_MAX_ROUNDS must be a positive integer.\n' >&2
      exit 2
    fi
    ;;
esac

if [[ "$AUTORESEARCH_MAX_ROUNDS" == "0" ]]; then
  printf 'AUTORESEARCH_MAX_ROUNDS must be a positive integer.\n' >&2
  exit 2
fi

if [[ -n "$AUTORESEARCH_MAX_ROUNDS" ]]; then
  run_loop=true
fi

case "$AUTORESEARCH_INTERVAL_SECONDS" in
  *[!0-9]*)
    printf 'AUTORESEARCH_INTERVAL_SECONDS must be a non-negative integer.\n' >&2
    exit 2
    ;;
esac

run_round() {
  local status=0

  python scripts/autoresearch/next_round_checks.py || status=$?
  python scripts/benchmarks/benchmark_architecture.py || status=$?

  return "$status"
}

round=1
while :; do
  printf 'AUTORESEARCH_ROUND round=%s\n' "$round"

  round_status=0
  run_round || round_status=$?

  printf 'AUTORESEARCH_ROUND_RESULT round=%s status=%s\n' "$round" "$round_status"

  if ! "$run_loop"; then
    exit "$round_status"
  fi

  if [[ "$round_status" -ne 0 && "$AUTORESEARCH_STOP_ON_FAILURE" == "true" ]]; then
    exit "$round_status"
  fi

  if [[ -n "$AUTORESEARCH_MAX_ROUNDS" && "$round" -ge "$AUTORESEARCH_MAX_ROUNDS" ]]; then
    exit "$round_status"
  fi

  round=$((round + 1))
  if [[ "$AUTORESEARCH_INTERVAL_SECONDS" -gt 0 ]]; then
    sleep "$AUTORESEARCH_INTERVAL_SECONDS"
  fi
done