# lancedb-nephtys-bridge

Real-time semantic search over NATS event streams, powered by LanceDB.

Consumes JSON events from a NATS JetStream topic, extracts reusable text summaries from generic Nephtys payloads, generates sentence embeddings with `all-MiniLM-L6-v2`, and stores them in a local LanceDB table. Query the table semantically from the CLI in either human or JSON form.

The bridge now persists `source_id`, `event_type`, and `symbol` as first-class Lance columns, exposes a small long-running HTTP query service, and includes maintenance tooling for e2e run retention plus Lance file compaction.

Scaffold overview:
- `nephtys_bridge/`: internal package with the actual runtime modules
- `nephtys_bridge/config.py`: central environment-driven settings
- `nephtys_bridge/db.py`: lazy LanceDB and embedding runtime helpers
- `nephtys_bridge/ingest.py`: ingestion runtime
- `nephtys_bridge/query.py`: query/filter/serialization logic
- `nephtys_bridge/service.py`: resident HTTP query service
- `nephtys_bridge/maintenance.py`: retention and compaction tasks
- top-level `main.py`, `query.py`, `service.py`, and `maintenance.py`: thin entrypoints for local CLI compatibility

## Requirements

- Python >= 3.11
- [uv](https://docs.astral.sh/uv/)
- A running NATS server with JetStream enabled

## Setup

```bash
uv sync
```

## Usage

### Ingest events

```bash
make run
```

Connects to `nats://localhost:4222`, subscribes to `nephtys.stream.>`, and writes incoming events to `./data/nephtys_lancedb`.

The bridge runtime is configurable with:
- `BRIDGE_DB_PATH`
- `BRIDGE_TABLE_NAME`
- `BRIDGE_NATS_URL`
- `BRIDGE_STREAM_TOPIC`

The bridge now supports:
- Wikipedia-style batched payloads.
- Generic news/article payloads with fields like `headline`, `title`, `summary`, `description`, `text`, or `message`.
- Fallback summaries for market events that at least carry `symbol` plus fields like `price`, `volume`, `spread`, or `imbalance`.

### Query

```bash
make query QUERY="search terms"
./.venv/bin/python query.py "search terms" --limit 20
./.venv/bin/python query.py "search terms" --all-namespaces
./.venv/bin/python query.py "exchange hack insolvency" --json
./.venv/bin/python query.py "bitcoin hack" --source rss_news --event-type article --max-age-seconds 86400 --json
./.venv/bin/python query.py "btc liquidation" --symbol BTCUSDT --json
```

If the `live_streams` table does not exist yet, query returns no results instead of failing. This makes it safe for other tools, such as Mercury's news-risk agent, to poll the bridge before the ingester has populated it.

Supported query filters:
- `--source`: repeatable source filter, matched against `source_id`
- `--event-type`: repeatable event-type filter, matched against the `event_type` column
- `--symbol`: repeatable symbol filter, matched against the `symbol` column
- `--max-age-seconds`: only keep recent rows inside the specified recency window

### Query Service

Run the bridge as a long-lived query service so consumers like Mercury do not pay Python and model cold-start cost on every poll.

```bash
make service
curl 'http://127.0.0.1:8787/health'
curl 'http://127.0.0.1:8787/query?q=bitcoin%20hack&limit=5&all_namespaces=true&source=rss_news'
```

Supported endpoints:
- `GET /health`
- `GET /query`

`/query` accepts:
- `q` or `query`
- `limit`
- `all_namespaces`
- `content_only`
- repeated `source`
- repeated `event_type`
- repeated `symbol`
- `max_age_seconds`
- optional `db_path` and `table`

### Bridge as a sidecar for Mercury

Mercury's `executor/news_risk_agent.py` can use this bridge as an out-of-band semantic news source. The intended workflow is:

1. Run `make run` here, or supervise the same entrypoint, to populate `./data/nephtys_lancedb`.
2. Prefer running `make service` here and point Mercury at `NEWS_RISK_BRIDGE_SERVICE_URL=http://127.0.0.1:8787`.
3. Mercury can still fall back to `query.py` directly when no service URL is configured.
4. Use the returned texts to lower risk limits without putting an LLM in the trade execution path.

The current architecture decision is:
- Keep the CLI tools for local debugging and backfills.
- Treat the bridge as a Nephtys-adjacent supervised service for operational Mercury usage.

### Local E2E Session

This repo now includes a small operational runner that starts Nephtys, registers the sample Wikimedia SSE stream, starts the bridge, and waits until the Lance table has real rows.

```bash
make e2e-wiki-sidecar
```

Important defaults:
- `NEPHTYS_REPO=/home/andrea/Nephtys`
- `NEPHTYS_ADMIN_TOKEN=bridge-local-admin`
- `BRIDGE_DB_PATH=./data/e2e_runs/$RUN_ID`

Operational behavior:
- Reuses an already-running Nephtys on `:3002` when present.
- Starts the bridge with the repo virtualenv Python instead of `uv run` to avoid orphan wrapper processes.
- Uses a run-scoped LanceDB path by default so repeated e2e sessions do not corrupt each other.
- Stops the bridge before the final semantic query so verification happens against a stable on-disk table.

Override them with environment variables if your local paths or ports differ.

See [E2E_FINDINGS.md](E2E_FINDINGS.md) for the latest live-session findings and the next recommended evolution steps.

### Maintenance

Apply retention and compaction policies:

```bash
make maintain
./.venv/bin/python maintenance.py --json
```

Current defaults:
- Keep the newest `5` e2e run directories.
- Delete older e2e runs after `7` days.
- Compact Lance data files and clean old table versions older than `7` days.

### Smoke Coverage

A gated smoke test is included for the full Nephtys -> bridge -> LanceDB -> query path:

```bash
make smoke-e2e
```

It is skipped by default unless `RUN_BRIDGE_E2E_SMOKE=1` is set.

### Stream configuration

See `wikipedia-stream-example.json` for an example SSE source config targeting the Wikimedia recent-changes stream.

## Related

- [Blog post: Lance Format and LanceDB](https://andreabozzo.pages.dev/posts/lancearticle-blog.en/)
- [lance-format/lance](https://github.com/lance-format/lance)
