# pyright: reportMissingImports=false, reportMissingModuleSource=false

import argparse
import json
import time
from datetime import datetime

from bridge_config import bridge_settings
from bridge_db import open_table_if_exists
from bridge_utils import extract_inline_field

MIN_VALID_TS_MS = 946684800000  # 2000-01-01 UTC
DB_PATH = bridge_settings().db_path
TABLE_NAME = bridge_settings().table_name


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
    source_filters: list[str] | None = None,
    event_type_filters: list[str] | None = None,
    symbol_filters: list[str] | None = None,
    max_age_seconds: int | None = None,
) -> list[dict]:
    table = open_table_if_exists(db_path, table_name)
    if table is None:
        return []

    raw_results = table.search(query_text).limit(max(limit * 60, 500)).to_list()
    return _filter_results(
        raw_results,
        limit=limit,
        content_only=content_only,
        source_filters=source_filters,
        event_type_filters=event_type_filters,
        symbol_filters=symbol_filters,
        max_age_seconds=max_age_seconds,
    )


def _filter_results(
    raw_results: list[dict],
    limit: int,
    content_only: bool,
    source_filters: list[str] | None = None,
    event_type_filters: list[str] | None = None,
    symbol_filters: list[str] | None = None,
    max_age_seconds: int | None = None,
) -> list[dict]:
    filtered_results = []

    seen_texts: set[str] = set()
    allowed_sources = {source.strip() for source in source_filters or [] if source.strip()}
    allowed_event_types = {
        event_type.strip() for event_type in event_type_filters or [] if event_type.strip()
    }
    allowed_symbols = {symbol.strip() for symbol in symbol_filters or [] if symbol.strip()}
    min_timestamp_ms = None
    if max_age_seconds is not None and max_age_seconds >= 0:
        min_timestamp_ms = int(time.time() * 1000) - max_age_seconds * 1000

    for row in raw_results:
        text = row.get("text", "")
        timestamp_ms = int(row.get("timestamp", 0) or 0)
        source_id = str(row.get("source_id", "") or "")
        event_type = str(row.get("event_type") or extract_inline_field(text, "type") or "")
        symbol = str(row.get("symbol") or extract_inline_field(text, "symbol") or "")

        if timestamp_ms < MIN_VALID_TS_MS:
            continue
        if min_timestamp_ms is not None and timestamp_ms < min_timestamp_ms:
            continue
        if not text or text in seen_texts:
            continue
        if allowed_sources and source_id not in allowed_sources:
            continue
        if allowed_event_types and event_type not in allowed_event_types:
            continue
        if allowed_symbols and symbol not in allowed_symbols:
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
    text = row.get("text", "")
    return {
        "timestamp": timestamp_ms,
        "datetime": datetime.fromtimestamp(timestamp_ms / 1000).strftime("%Y-%m-%d %H:%M:%S"),
        "score": row.get("_distance"),
        "source_id": row.get("source_id", "unknown"),
        "event_type": row.get("event_type") or extract_inline_field(text, "type"),
        "symbol": row.get("symbol") or extract_inline_field(text, "symbol"),
        "text": text,
    }


def serialize_results(results: list[dict]) -> list[dict]:
    return [_serialize_result(row) for row in results]


def print_results(results: list[dict], query_text: str, content_only: bool, json_output: bool) -> None:
    if json_output:
        print(json.dumps(serialize_results(results), ensure_ascii=False))
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
        if serialized["event_type"]:
            print(f"Tipo: {serialized['event_type']}")
        if serialized["symbol"]:
            print(f"Simbolo: {serialized['symbol']}")
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
    parser.add_argument("--source", action="append", default=[])
    parser.add_argument("--event-type", action="append", default=[])
    parser.add_argument("--symbol", action="append", default=[])
    parser.add_argument("--max-age-seconds", type=int)

    args = parser.parse_args()
    results = query_stream(
        args.query,
        limit=args.limit,
        content_only=not args.all_namespaces,
        db_path=args.db_path,
        table_name=args.table,
        source_filters=args.source,
        event_type_filters=args.event_type,
        symbol_filters=args.symbol,
        max_age_seconds=args.max_age_seconds,
    )
    print_results(results, args.query, content_only=not args.all_namespaces, json_output=args.json)
