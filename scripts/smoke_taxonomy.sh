#!/usr/bin/env bash
# scripts/smoke_taxonomy.sh
# Smoke-test taxonomy CLI contracts added in v1.12.0.
# Runs each command and validates JSON output shape.
# Exits non-zero on first failure.

set -euo pipefail

PASS=0
FAIL=0

check_json() {
	local label="$1"
	shift
	local output
	if output=$("$@" 2>&1); then
		if echo "$output" | python3 -c "import json,sys; json.load(sys.stdin)" 2>/dev/null; then
			echo "PASS  $label"
			PASS=$((PASS + 1))
		else
			echo "FAIL  $label  (exit 0 but invalid JSON)"
			FAIL=$((FAIL + 1))
		fi
	else
		echo "FAIL  $label  (exit non-zero: $?)"
		FAIL=$((FAIL + 1))
	fi
}

check_help() {
	local label="$1"
	shift
	if "$@" >/dev/null 2>&1; then
		echo "PASS  $label"
		PASS=$((PASS + 1))
	else
		echo "FAIL  $label  (non-zero exit)"
		FAIL=$((FAIL + 1))
	fi
}

echo "=== WorkFlow taxonomy smoke tests ==="
echo ""

check_json  "workflow topic list --json"       workflow topic list --json
check_json  "workflow content list --json"     workflow content list --json
check_json  "workflow concept list --json"     workflow concept list --json
check_json  "workflow graph stats --json"      workflow graph stats --json
check_json  "workflow graph orphans --json"    workflow graph orphans --json
check_help  "workflow lectures scan --help"    workflow lectures scan --help
check_help  "workflow lectures link --help"    workflow lectures link --help

echo ""
echo "=== Results: $PASS passed, $FAIL failed ==="

if [ "$FAIL" -gt 0 ]; then
	exit 1
fi
exit 0
