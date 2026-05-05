# lancedb-nephtys-bridge

Real-time semantic search over NATS event streams, powered by LanceDB.

Consumes JSON events from a NATS JetStream topic, extracts reusable text summaries from generic Nephtys payloads, generates sentence embeddings with `all-MiniLM-L6-v2`, and stores them in a local LanceDB table. Query the table semantically from the CLI in either human or JSON form.

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
uv run main.py
```

Connects to `nats://localhost:4222`, subscribes to `nephtys.stream.>`, and writes incoming events to `./data/nephtys_lancedb`.

The bridge now supports:
- Wikipedia-style batched payloads.
- Generic news/article payloads with fields like `headline`, `title`, `summary`, `description`, `text`, or `message`.
- Fallback summaries for market events that at least carry `symbol` plus fields like `price`, `volume`, `spread`, or `imbalance`.

### Query

```bash
uv run query.py "search terms"
uv run query.py "search terms" --limit 20
uv run query.py "search terms" --all-namespaces
uv run query.py "exchange hack insolvency" --json
uv run query.py "bitcoin hack" --source rss_news --event-type article --max-age-seconds 86400 --json
```

If the `live_streams` table does not exist yet, query returns no results instead of failing. This makes it safe for other tools, such as Mercury's news-risk agent, to poll the bridge before the ingester has populated it.

Supported query filters:
- `--source`: repeatable source filter, matched against `source_id`
- `--event-type`: repeatable event-type filter, matched from inline event metadata
- `--max-age-seconds`: only keep recent rows inside the specified recency window

### Bridge as a sidecar for Mercury

Mercury's `executor/news_risk_agent.py` can use this bridge as an out-of-band semantic news source. The intended workflow is:

1. Run `uv run main.py` here to populate `./data/nephtys_lancedb`.
2. Let Mercury call `uv run query.py ... --json` against this repo.
3. Use the returned texts to lower risk limits without putting an LLM in the trade execution path.

### Local E2E Session

This repo now includes a small operational runner that starts Nephtys, registers the sample Wikimedia SSE stream, starts the bridge, and waits until the Lance table has real rows.

```bash
make e2e-wiki-sidecar
```

Important defaults:
- `NEPHTYS_REPO=/home/andrea/Nephtys`
- `NEPHTYS_ADMIN_TOKEN=bridge-local-admin`
- `BRIDGE_DB_PATH=./data/e2e_nephtys_lancedb`

Override them with environment variables if your local paths or ports differ.

### Stream configuration

See `wikipedia-stream-example.json` for an example SSE source config targeting the Wikimedia recent-changes stream.

## Related

- [Blog post: Lance Format and LanceDB](https://andreabozzo.pages.dev/posts/lancearticle-blog.en/)
- [lance-format/lance](https://github.com/lance-format/lance)
