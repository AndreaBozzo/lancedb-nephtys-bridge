#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
NEPHTYS_REPO="${NEPHTYS_REPO:-/home/andrea/Nephtys}"
BRIDGE_PYTHON="${BRIDGE_PYTHON:-$ROOT_DIR/.venv/bin/python}"
CONFIG_FILE="${CONFIG_FILE:-$ROOT_DIR/wikipedia-stream-example.json}"
NEPHTYS_ADMIN_TOKEN="${NEPHTYS_ADMIN_TOKEN:-bridge-local-admin}"
NEPHTYS_PORT="${NEPHTYS_PORT:-3002}"
NATS_URL="${NATS_URL:-nats://127.0.0.1:4222}"
RUN_ID="${RUN_ID:-$(date +%Y%m%d%H%M%S)}"
BRIDGE_DB_PATH="${BRIDGE_DB_PATH:-$ROOT_DIR/data/e2e_runs/$RUN_ID}"
BRIDGE_TABLE_NAME="${BRIDGE_TABLE_NAME:-live_streams}"
BRIDGE_STREAM_TOPIC="${BRIDGE_STREAM_TOPIC:-nephtys.stream.wiki}"
QUERY_TEXT="${QUERY_TEXT:-modificato pagina commento utente}"
TIMEOUT_SECONDS="${TIMEOUT_SECONDS:-120}"

NATS_PID=""
NEPHTYS_PID=""
BRIDGE_PID=""
STREAM_ID="wiki_live_edits"
TMP_DIR="$(mktemp -d)"
NATS_LOG="$TMP_DIR/nats.log"
NEPHTYS_LOG="$TMP_DIR/nephtys.log"
BRIDGE_LOG="$TMP_DIR/bridge.log"

cleanup() {
	set +e
	if command -v curl >/dev/null 2>&1; then
		curl -fsS -X DELETE \
			-H "Authorization: Bearer $NEPHTYS_ADMIN_TOKEN" \
			"http://127.0.0.1:${NEPHTYS_PORT}/v1/streams/${STREAM_ID}" >/dev/null 2>&1 || true
	fi
	if [[ -n "$BRIDGE_PID" ]]; then
		stop_process "$BRIDGE_PID" 5
	fi
	if [[ -n "$NEPHTYS_PID" ]]; then
		stop_process "$NEPHTYS_PID" 5
	fi
	if [[ -n "$NATS_PID" ]]; then
		stop_process "$NATS_PID" 5
	fi
	rm -rf "$TMP_DIR"
}
trap cleanup EXIT

wait_for_http() {
	local url="$1"
	local timeout="$2"
	local start
	start="$(date +%s)"
	while true; do
		if curl -fsS "$url" >/dev/null 2>&1; then
			return 0
		fi
		if (( $(date +%s) - start >= timeout )); then
			echo "Timed out waiting for $url" >&2
			return 1
		fi
		sleep 1
	done
}

stop_process() {
	local pid="$1"
	local timeout="${2:-20}"
	local start
	if [[ -z "$pid" ]]; then
		return 0
	fi
	if ! kill -0 "$pid" >/dev/null 2>&1; then
		wait "$pid" 2>/dev/null || true
		return 0
	fi
	kill -INT "$pid" >/dev/null 2>&1 || true
	start="$(date +%s)"
	while kill -0 "$pid" >/dev/null 2>&1; do
		if (( $(date +%s) - start >= timeout )); then
			kill "$pid" >/dev/null 2>&1 || true
			break
		fi
		sleep 1
	done
	if kill -0 "$pid" >/dev/null 2>&1; then
		kill -KILL "$pid" >/dev/null 2>&1 || true
	fi
	wait "$pid" 2>/dev/null || true
}

if ! ss -ltn '( sport = :4222 )' | tail -n +2 | grep -q 4222; then
	echo "Starting local nats-server..."
	nats-server -js -m 8222 >"$NATS_LOG" 2>&1 &
	NATS_PID="$!"
	for _ in $(seq 1 15); do
		if ss -ltn '( sport = :4222 )' | tail -n +2 | grep -q 4222; then
			break
		fi
		sleep 1
	done
fi

if curl -fsS "http://127.0.0.1:${NEPHTYS_PORT}/health" >/dev/null 2>&1; then
	echo "Reusing existing Nephtys on :${NEPHTYS_PORT}..."
else
	echo "Starting Nephtys..."
	(
		cd "$NEPHTYS_REPO"
		NEPHTYS_ADMIN_TOKEN="$NEPHTYS_ADMIN_TOKEN" NATS_URL="$NATS_URL" make run >"$NEPHTYS_LOG" 2>&1
	) &
	NEPHTYS_PID="$!"
	wait_for_http "http://127.0.0.1:${NEPHTYS_PORT}/health" 30
fi

echo "Registering SSE stream from $CONFIG_FILE..."
curl -fsS -X DELETE \
	-H "Authorization: Bearer $NEPHTYS_ADMIN_TOKEN" \
	"http://127.0.0.1:${NEPHTYS_PORT}/v1/streams/${STREAM_ID}" >/dev/null 2>&1 || true

curl -fsS -X POST "http://127.0.0.1:${NEPHTYS_PORT}/v1/streams" \
	-H "Content-Type: application/json" \
	-H "Authorization: Bearer $NEPHTYS_ADMIN_TOKEN" \
	--data-binary @"$CONFIG_FILE" >/dev/null

echo "Starting LanceDB bridge..."
rm -rf "$BRIDGE_DB_PATH"
mkdir -p "$(dirname "$BRIDGE_DB_PATH")"
(
	cd "$ROOT_DIR"
	BRIDGE_DB_PATH="$BRIDGE_DB_PATH" \
	BRIDGE_TABLE_NAME="$BRIDGE_TABLE_NAME" \
	BRIDGE_NATS_URL="$NATS_URL" \
	BRIDGE_STREAM_TOPIC="$BRIDGE_STREAM_TOPIC" \
	"$BRIDGE_PYTHON" main.py >"$BRIDGE_LOG" 2>&1
) &
BRIDGE_PID="$!"

echo "Waiting for Lance table population..."
START_TS="$(date +%s)"
while true; do
	ROW_COUNT="$(BRIDGE_DB_PATH="$BRIDGE_DB_PATH" BRIDGE_TABLE_NAME="$BRIDGE_TABLE_NAME" "$BRIDGE_PYTHON" - <<PY
import os
from pathlib import Path

db_path = os.environ["BRIDGE_DB_PATH"]
table_name = os.environ["BRIDGE_TABLE_NAME"]
table_path = Path(db_path) / f"{table_name}.lance"
data_path = table_path / "data"

try:
    if not table_path.exists() or not data_path.exists():
        print(0)
    else:
        print(sum(1 for path in data_path.iterdir() if path.is_file()))
except Exception:
    print(0)
PY
	)"
	if [[ "$ROW_COUNT" =~ ^[0-9]+$ ]] && (( ROW_COUNT > 0 )); then
		break
	fi
	if (( $(date +%s) - START_TS >= TIMEOUT_SECONDS )); then
		echo "Timed out waiting for populated Lance table" >&2
		if [[ -f "$NEPHTYS_LOG" ]]; then
			echo "Nephtys log:" >&2
			tail -n 50 "$NEPHTYS_LOG" >&2 || true
		fi
		echo "Bridge log:" >&2
		tail -n 50 "$BRIDGE_LOG" >&2 || true
		exit 1
	fi
	sleep 2
done

echo "Lance rows recorded: $ROW_COUNT"
echo "Waiting for bridge ingestion confirmation..."
START_TS="$(date +%s)"
while true; do
	if [[ -f "$BRIDGE_LOG" ]] && grep -q "Saved [0-9]\+ records to LanceDB" "$BRIDGE_LOG"; then
		break
	fi
	if (( $(date +%s) - START_TS >= TIMEOUT_SECONDS )); then
		echo "Timed out waiting for bridge ingestion logs" >&2
		tail -n 50 "$BRIDGE_LOG" >&2 || true
		exit 1
	fi
	sleep 2
done

echo "Stopping bridge for offline verification..."
stop_process "$BRIDGE_PID" 20
BRIDGE_PID=""

echo "Sample semantic query:"
QUERY_OUTPUT="[]"
QUERY_OUTPUT_FILE="$TMP_DIR/query_output.json"
START_TS="$(date +%s)"
while true; do
	QUERY_OUTPUT="[]"
	if (
		cd "$ROOT_DIR"
		BRIDGE_DB_PATH="$BRIDGE_DB_PATH" "$BRIDGE_PYTHON" query.py \
			"$QUERY_TEXT" \
			--limit 3 \
			--all-namespaces \
			--db-path "$BRIDGE_DB_PATH" \
			--table "$BRIDGE_TABLE_NAME" \
			--json >"$QUERY_OUTPUT_FILE" 2>/dev/null
	); then
		QUERY_OUTPUT="$(cat "$QUERY_OUTPUT_FILE")"
	fi
	if [[ "$QUERY_OUTPUT" != "[]" ]]; then
		break
	fi
	if (( $(date +%s) - START_TS >= TIMEOUT_SECONDS )); then
		echo "Timed out waiting for semantic query results" >&2
		echo "Bridge log:" >&2
		tail -n 50 "$BRIDGE_LOG" >&2 || true
		exit 1
	fi
	sleep 2
done
echo "Verified DB path: $BRIDGE_DB_PATH"
printf '%s\n' "$QUERY_OUTPUT"

echo "E2E session completed successfully."