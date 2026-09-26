#!/usr/bin/env bash
set -euo pipefail

CLIENT_ID="outage-$(date +%s)"

echo "Stopping Redis..."
docker compose stop redis

echo "Sending requests while Redis is down..."
for i in {1..5}; do
  curl -s -X POST http://localhost:8000/check \
    -H 'Content-Type: application/json' \
    -d "{\"client_id\":\"$CLIENT_ID\"}"
  echo
done

echo "Starting Redis..."
docker compose start redis

sleep 2

echo "Sending request after Redis recovery..."
curl -s -X POST http://localhost:8000/check \
  -H 'Content-Type: application/json' \
  -d "{\"client_id\":\"$CLIENT_ID\"}"

echo
echo "Done."
echo "If RATE_LIMIT_FAIL_OPEN=true, requests during outage were allowed."
echo "If RATE_LIMIT_FAIL_OPEN=false, requests during outage were denied."