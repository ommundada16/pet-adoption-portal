#!/usr/bin/env bash
# Quick end-to-end check that a running deployment really works.
#   ./scripts/smoke_test.sh http://localhost
# The same script is used by the pipeline after docker compose, after Kubernetes, and after the AWS deploy.
set -u
BASE="${1:-http://localhost}"
FAILED=0

# check <description> <expected HTTP status> <curl args...>
check() {
  local desc="$1" expected="$2"; shift 2
  local status
  status=$(curl -s -o /dev/null -w '%{http_code}' --max-time 10 "$@")
  if [ "$status" = "$expected" ]; then
    echo "PASS  $desc ($status)"
  else
    echo "FAIL  $desc - expected $expected, got $status"
    FAILED=1
  fi
}

echo "Smoke testing $BASE"

# Wait up to 60s for the site to start answering (a fresh deploy may still be starting up)
for i in $(seq 1 30); do
  curl -s -o /dev/null --max-time 3 "$BASE/index.html" && break
  sleep 2
done
check "frontend page loads"                200 "$BASE/index.html"
check "API health (liveness)"              200 "$BASE/api/health"
check "API ready (database reachable)"     200 "$BASE/api/ready"
check "pet list is served through nginx"   200 "$BASE/api/pets"
check "unknown pet returns 404"            404 "$BASE/api/pets/999999"
check "protected route needs a token"      401 "$BASE/api/pets/my-pets"
check "/metrics is NOT public"             404 "$BASE/metrics"

# Seed data must exist (the schema inserts 3 demo pets)
if curl -s --max-time 10 "$BASE/api/pets" | grep -q '"name"'; then
  echo "PASS  demo pets are present"
else
  echo "FAIL  no pets returned"; FAILED=1
fi

# Real user journey: register -> login -> token
EMAIL="smoke$(date +%s)@example.com"
check "register a new user" 201 -X POST "$BASE/api/users/register" \
  -H 'Content-Type: application/json' -d "{\"name\":\"Smoke\",\"email\":\"$EMAIL\",\"password\":\"Smoke@1234\"}"
if curl -s --max-time 10 -X POST "$BASE/api/users/login" -H 'Content-Type: application/json' \
     -d "{\"email\":\"$EMAIL\",\"password\":\"Smoke@1234\"}" | grep -q '"token"'; then
  echo "PASS  login returns a token"
else
  echo "FAIL  login did not return a token"; FAILED=1
fi

if [ "$FAILED" -eq 0 ]; then echo "ALL CHECKS PASSED"; else echo "SMOKE TEST FAILED"; fi
exit "$FAILED"
