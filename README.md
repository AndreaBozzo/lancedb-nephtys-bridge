# lancedb-nephtys-bridge

Real-time semantic search over NATS event streams, powered by LanceDB.

Consumes JSON event batches from a NATS JetStream topic, generates sentence embeddings with `all-MiniLM-L6-v2`, and stores them in a local LanceDB table. Query the table semantically from the CLI.

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

### Query

```bash
uv run query.py "search terms"
uv run query.py "search terms" --limit 20
uv run query.py "search terms" --all-namespaces
```

### Stream configuration

See `wikipedia-stream-example.json` for an example SSE source config targeting the Wikimedia recent-changes stream.

## Related

- [Blog post: Lance Format and LanceDB](https://andreabozzo.pages.dev/posts/lancearticle-blog.en/)
- [lance-format/lance](https://github.com/lance-format/lance)
