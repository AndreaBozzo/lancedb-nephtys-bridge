import argparse
from datetime import datetime

import lancedb

MIN_VALID_TS_MS = 946684800000  # 2000-01-01 UTC


def _is_content_row(text: str) -> bool:
    blocked_prefixes = (
        "User talk:",
        "Talk:",
        "Category:",
        "File:",
        "Wikipedia:",
        "Template:",
        "Portal:",
    )
    return not any(prefix in text for prefix in blocked_prefixes)


def query_stream(query_text: str, limit: int, content_only: bool):
    db = lancedb.connect("./data/nephtys_lancedb")
    table = db.open_table("live_streams")

    print(f"Ricerca per: '{query_text}'")
    print(f"Modalita content_only: {content_only}\n")

    raw_results = table.search(query_text).limit(max(limit * 60, 500)).to_list()

    seen_texts: set[str] = set()
    filtered_results = []

    for row in raw_results:
        text = row.get("text", "")
        timestamp_ms = int(row.get("timestamp", 0) or 0)

        if timestamp_ms < MIN_VALID_TS_MS:
            continue
        if not text or text in seen_texts:
            continue
        if content_only and not _is_content_row(text):
            continue

        seen_texts.add(text)
        filtered_results.append(row)

        if len(filtered_results) >= limit:
            break

    if not filtered_results:
        print("Nessun risultato dopo i filtri applicati.")
        return

    for row in filtered_results:
        timestamp_ms = int(row.get("timestamp", 0) or 0)
        ts = datetime.fromtimestamp(timestamp_ms / 1000).strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{ts}] (Score: {row['_distance']:.4f})")
        print(f"Testo: {row['text']}")
        print("-" * 40)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Query semantic search results from LanceDB")
    parser.add_argument("query", nargs="?", default="notizie su data engineering")
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--all-namespaces", action="store_true")

    args = parser.parse_args()
    query_stream(args.query, limit=args.limit, content_only=not args.all_namespaces)
