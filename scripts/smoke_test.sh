#!/usr/bin/env sh
set -eu

api_base="${API_BASE_URL:-http://127.0.0.1:8100}"
curl --fail --silent "$api_base/health" | grep -q '"status":"ok"'
curl --fail --silent "$api_base/api/v1/dashboard/overview" | grep -q '"metrics"'
curl --fail --silent "$api_base/api/v1/form-schemas" | grep -q 'sales-weekly-v1'
printf 'Smoke tests passed.\n'
