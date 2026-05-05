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
- The query contract Mercury needs is stable enough to consume as JSON with source, event-type, and recency filtering.
- Cold-start cost is noticeable because both ingest and query load the embedding model at process start.
- Earlier `uv run main.py` e2e attempts leaked wrapper processes; the runner now avoids that by using the venv Python directly.
- Querying a table while it is actively being appended to was unstable in this environment; offline verification after bridge shutdown was reliable.

## Recommended Next Steps

1. Persist `event_type`, `source_id`, and any important market keys such as `symbol` as first-class Lance columns instead of relying on inline metadata parsing.
2. Add a small long-running query service or HTTP wrapper so Mercury does not pay model cold-start cost on every poll.
3. Add retention and compaction policies for `data/e2e_runs` and any long-lived bridge databases.
4. Decide whether the bridge should remain a CLI sidecar or become a proper Nephtys-adjacent service with supervised lifecycle and health checks.
5. If Mercury starts depending on this path operationally, add a dedicated smoke test that spins up Nephtys, ingests one known event source, and asserts non-empty JSON query output.