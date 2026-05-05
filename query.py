# pyright: reportMissingImports=false, reportMissingModuleSource=false

import argparse
import json
import os
from datetime import datetime

import lancedb  # type: ignore[import-untyped]

MIN_VALID_TS_MS = 946684800000  # 2000-01-01 UTC
DB_PATH = os.getenv("BRIDGE_DB_PATH", "./data/nephtys_lancedb")
TABLE_NAME = os.getenv("BRIDGE_TABLE_NAME", "live_streams")


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


def query_stream(
    query_text: str,
    limit: int,
    content_only: bool,
    db_path: str = DB_PATH,
    table_name: str = TABLE_NAME,
) -> list[dict]:
    table = _open_table_if_exists(db_path, table_name)
    if table is None:
        return []

    raw_results = table.search(query_text).limit(max(limit * 60, 500)).to_list()
    return _filter_results(raw_results, limit=limit, content_only=content_only)


def _open_table_if_exists(db_path: str, table_name: str):
    db = lancedb.connect(db_path)
    existing_tables = set(db.list_tables().tables)
    if table_name not in existing_tables:
        return None
    return db.open_table(table_name)


def _filter_results(raw_results: list[dict], limit: int, content_only: bool) -> list[dict]:
    filtered_results = []

    seen_texts: set[str] = set()

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

    return filtered_results


def _serialize_result(row: dict) -> dict:
    timestamp_ms = int(row.get("timestamp", 0) or 0)
    return {
        "timestamp": timestamp_ms,
        "datetime": datetime.fromtimestamp(timestamp_ms / 1000).strftime("%Y-%m-%d %H:%M:%S"),
        "score": row.get("_distance"),
        "source_id": row.get("source_id", "unknown"),
        "text": row.get("text", ""),
    }


def print_results(results: list[dict], query_text: str, content_only: bool, json_output: bool) -> None:
    if json_output:
        print(json.dumps([_serialize_result(row) for row in results], ensure_ascii=False))
        return

    print(f"Ricerca per: '{query_text}'")
    print(f"Modalita content_only: {content_only}\n")

    if not results:
        print("Nessun risultato dopo i filtri applicati.")
        return

    for row in results:
        serialized = _serialize_result(row)
        score = serialized["score"]
        score_label = f"{float(score):.4f}" if score is not None else "n/a"
        print(f"[{serialized['datetime']}] (Score: {score_label})")
        print(f"Fonte: {serialized['source_id']}")
        print(f"Testo: {serialized['text']}")
        print("-" * 40)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Query semantic search results from LanceDB")
    parser.add_argument("query", nargs="?", default="notizie su data engineering")
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--all-namespaces", action="store_true")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--db-path", default=DB_PATH)
    parser.add_argument("--table", default=TABLE_NAME)

    args = parser.parse_args()
    results = query_stream(
        args.query,
        limit=args.limit,
        content_only=not args.all_namespaces,
        db_path=args.db_path,
        table_name=args.table,
    )
    print_results(results, args.query, content_only=not args.all_namespaces, json_output=args.json)
