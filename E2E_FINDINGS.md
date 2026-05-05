# E2E Findings

## Live Session Summary

Date: 2026-05-05

Validated flow:
- Reused an already-running Nephtys admin/API instance on `:3002`.
- Registered the sample Wikimedia SSE stream from `wikipedia-stream-example.json`.
- Started the bridge and observed repeated `Saved 20 records to LanceDB` log lines.
- Verified semantic query output after stopping the bridge cleanly.

Successful verification output came from a run-scoped database path similar to:

```text
/home/andrea/Documenti/lancedb-nephtys-bridge/data/e2e_runs/20260505201439
```

Sample verified query shape:

```json
[
  {
    "timestamp": 1778002991981,
    "datetime": "2026-05-05 19:43:11",
    "score": 0.8049065470695496,
    "source_id": "wiki_live_edits",
    "event_type": "message_batch",
    "text": "source=wiki_live_edits | type=message_batch | ..."
  }
]
```

## Findings

- The Nephtys -> NATS -> bridge -> LanceDB path is working with live Wikimedia SSE traffic.
- The bridge can now be operated as a practical sidecar instead of a Wikipedia-only demo.
- The query contract Mercury needs is stable enough to consume as JSON with source, event-type, symbol, and recency filtering.
- Cold-start cost is noticeable because both ingest and query load the embedding model at process start.
- Earlier `uv run main.py` e2e attempts leaked wrapper processes; the runner now avoids that by using the venv Python directly.
- Querying a table while it is actively being appended to was unstable in this environment; offline verification after bridge shutdown was reliable.

## Completed Follow-ups

- `source_id`, `event_type`, and `symbol` are now persisted as first-class Lance columns.
- The bridge now includes a resident HTTP query service so Mercury can avoid repeated CLI cold starts.
- Retention and compaction policies are implemented in `maintenance.py`.
- A gated smoke test exists for the full e2e sidecar path.

## Architecture Decision

Decision:
Treat the bridge as a Nephtys-adjacent supervised service for operational use, while keeping the CLI tools for local debugging, ad hoc queries, and backfills.

Reasoning:
- Mercury benefits directly from a resident query service because the repeated CLI/model startup cost is otherwise paid on every polling cycle.
- The live e2e work showed that operational lifecycle matters: process supervision, bounded shutdown, and stable DB paths are part of the real contract.
- The CLI remains useful, but it is not the right primary interface once another system depends on the bridge continuously.

## Recommended Next Steps

1. Add first-class columns for any additional trading-specific filters Mercury will want, such as venue, market, or normalized asset identifiers.
2. Add service supervision and health-check wiring in the actual deployment environment, such as Docker Compose or systemd.
3. Consider pre-warming or sharing embedding/query state further if query latency becomes material under load.
4. Add a migration/backup policy for long-lived production tables if schema changes continue.
5. Extend the smoke test to cover the HTTP service path explicitly, not only the CLI verification path.