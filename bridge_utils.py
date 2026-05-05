from __future__ import annotations

import time
from typing import Any

TEXT_FIELDS = (
    "headline",
    "title",
    "summary",
    "description",
    "text",
    "message",
    "content",
    "comment",
    "body",
)


def extract_inline_field(text: str, field: str) -> str | None:
    for segment in text.split("|"):
        token = segment.strip()
        prefix = f"{field}="
        if token.startswith(prefix):
            value = token[len(prefix) :].strip()
            return value or None
    return None


def inline_metadata(source_id: str, event_type: str, symbol: str | None = None) -> str:
    parts = []
    if source_id:
        parts.append(f"source={source_id}")
    if event_type:
        parts.append(f"type={event_type}")
    if symbol:
        parts.append(f"symbol={symbol}")
    return " | ".join(parts)


def normalize_timestamp_ms(ts_value: int | float | str | None) -> int:
    now_ms = int(time.time() * 1000)
    if ts_value is None:
        return now_ms

    try:
        ts_int = int(ts_value)
    except (TypeError, ValueError):
        return now_ms

    if ts_int <= 0:
        return now_ms
    if ts_int < 10_000_000_000:
        return ts_int * 1000
    return ts_int


def iter_event_rows(stream_event: dict[str, Any]) -> list[dict[str, Any]]:
    source_id = _clean_str(stream_event.get("source")) or "unknown"
    timestamp = normalize_timestamp_ms(stream_event.get("timestamp"))
    event_type = _clean_str(stream_event.get("type")) or "event"
    payload = stream_event.get("payload")

    if isinstance(payload, dict):
        payloads = [payload]
    elif isinstance(payload, list):
        payloads = [item for item in payload if isinstance(item, dict)]
    else:
        payloads = []

    rows: list[dict[str, Any]] = []
    for item in payloads:
        text = extract_text_content(source_id, event_type, item)
        if not text:
            continue
        symbol = extract_symbol(item)

        rows.append(
            {
                "source_id": source_id,
                "event_type": event_type,
                "symbol": symbol,
                "timestamp": normalize_timestamp_ms(item.get("timestamp", timestamp)),
                "text": text,
            }
        )

    return rows


def extract_text_content(source_id: str, event_type: str, item: dict[str, Any]) -> str | None:
    title = _clean_str(item.get("title"))
    comment = _clean_str(item.get("comment"))
    user = _clean_str(item.get("user")) or "unknown"
    bot = bool(item.get("bot", False))
    if title and not bot:
        prefix = inline_metadata(source_id, event_type)
        body = f"L'utente {user} ha modificato la pagina '{title}'. Commento: {comment or 'N/A'}"
        return f"{prefix} | {body}" if prefix else body

    text_fragments: list[str] = []
    for field in TEXT_FIELDS:
        value = _clean_str(item.get(field))
        if value and value not in text_fragments:
            text_fragments.append(value)

    symbol = extract_symbol(item)
    if text_fragments:
        prefix = inline_metadata(source_id, event_type, symbol or None)
        body = " ".join(text_fragments)
        return f"{prefix} | {body}" if prefix else body

    price = _clean_str(item.get("price")) or _clean_str(item.get("c"))
    volume = _clean_str(item.get("volume")) or _clean_str(item.get("qty")) or _clean_str(item.get("q"))
    imbalance = _clean_str(item.get("imbalance"))
    spread = _clean_str(item.get("spread"))
    if symbol and any((price, volume, imbalance, spread)):
        prefix = inline_metadata(source_id, event_type, symbol)
        fragments = []
        if price:
            fragments.append(f"price={price}")
        if volume:
            fragments.append(f"volume={volume}")
        if imbalance:
            fragments.append(f"imbalance={imbalance}")
        if spread:
            fragments.append(f"spread={spread}")
        suffix = " ".join(fragments)
        return f"{prefix} | {suffix}" if suffix else prefix

    return None


def extract_symbol(item: dict[str, Any]) -> str | None:
    symbol = _clean_str(item.get("symbol")) or _clean_str(item.get("s"))
    return symbol or None


def upgrade_legacy_row(row: dict[str, Any]) -> dict[str, Any] | None:
    text = _clean_str(row.get("text"))
    if not text:
        return None

    source_id = _clean_str(row.get("source_id")) or extract_inline_field(text, "source") or "unknown"
    event_type = _clean_str(row.get("event_type")) or extract_inline_field(text, "type") or "event"
    symbol = _clean_str(row.get("symbol")) or extract_inline_field(text, "symbol") or None
    timestamp = normalize_timestamp_ms(row.get("timestamp"))
    upgraded = {
        "source_id": source_id,
        "event_type": event_type,
        "symbol": symbol,
        "timestamp": timestamp,
        "text": text,
    }
    vector = row.get("vector")
    if vector is not None:
        upgraded["vector"] = vector
    return upgraded


def _clean_str(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    return text