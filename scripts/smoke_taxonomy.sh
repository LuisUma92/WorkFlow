#!/usr/bin/env bash
# scripts/smoke_taxonomy.sh
# Smoke-test taxonomy CLI contracts added in v1.12.0.
# Runs each command and validates JSON output shape.
# Exits non-zero on first failure.

set -euo pipefail

export WORKFLOW_DATA_DIR=$(mktemp -d)
trap 'rm -rf "$WORKFLOW_DATA_DIR"' EXIT

PASS=0
FAIL=0

check_json() {
	local label="$1"; shift
	local out err rc
	err=$(mktemp); out=$("$@" 2>"$err"); rc=$?
	if [ "$rc" -ne 0 ]; then
		echo "FAIL  $label  (exit $rc: $(cat "$err"))"
		rm -f "$err"; FAIL=$((FAIL+1)); return
	fi
	if echo "$out" | python3 -c "import json,sys; json.load(sys.stdin)" 2>/dev/null; then
		echo "PASS  $label"; PASS=$((PASS+1))
	else
		echo "FAIL  $label  (exit 0 but invalid JSON)"; FAIL=$((FAIL+1))
	fi
	rm -f "$err"
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

# Initialise schema in the isolated temp DB before running checks
workflow db migrate --quiet 2>/dev/null || workflow db migrate

check_json  "workflow topic list --json"       workflow topic list --json
check_json  "workflow content list --json"     workflow content list --json
check_json  "workflow concept list --json"     workflow concept list --json
check_json  "workflow graph stats --json"      workflow graph stats --json
check_json  "workflow graph orphans --json"    workflow graph orphans --json
check_help  "workflow graph neighbors --help"  workflow graph neighbors --help
check_help  "workflow lectures scan --help"    workflow lectures scan --help
check_help  "workflow lectures link --help"    workflow lectures link --help
check_help  "workflow content link-bib --help"   workflow content link-bib --help
check_help  "workflow content bib-links --help"  workflow content bib-links --help
check_help  "workflow content unlink-bib --help" workflow content unlink-bib --help

echo ""
echo "=== Results: $PASS passed, $FAIL failed ==="

if [ "$FAIL" -gt 0 ]; then
	exit 1
fi
exit 0
