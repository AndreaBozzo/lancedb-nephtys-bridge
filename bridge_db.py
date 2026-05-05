# pyright: reportMissingImports=false, reportMissingModuleSource=false

from __future__ import annotations

from functools import lru_cache
import logging
import os
from typing import TYPE_CHECKING, Any

import lancedb  # type: ignore[import-untyped]
from lancedb.embeddings import get_registry  # type: ignore[import-untyped]
from lancedb.pydantic import LanceModel, Vector  # type: ignore[import-untyped]

from bridge_config import bridge_settings
from bridge_utils import upgrade_legacy_row

logger = logging.getLogger("nephtys-bridge.db")

DB_PATH = bridge_settings().db_path
TABLE_NAME = bridge_settings().table_name

REQUIRED_COLUMNS = {"source_id", "event_type", "symbol", "timestamp", "text", "vector"}


@lru_cache(maxsize=1)
def get_embedding_model():
    settings = bridge_settings()
    return get_registry().get("sentence-transformers").create(name=settings.embedding_model)


@lru_cache(maxsize=1)
def get_event_model():
    model = get_embedding_model()
    vector_type = list[float] if TYPE_CHECKING else Vector(model.ndims())

    class NephtysEvent(LanceModel):
        source_id: str
        event_type: str
        symbol: str | None = None
        timestamp: int
        text: str = model.SourceField()
        vector: vector_type = model.VectorField()

    return NephtysEvent


def connect_db(db_path: str = DB_PATH):
    os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)
    return lancedb.connect(db_path)


def ensure_table(db_path: str = DB_PATH, table_name: str = TABLE_NAME):
    db = connect_db(db_path)
    existing_tables = set(db.list_tables().tables)
    if table_name not in existing_tables:
        return db.create_table(table_name, schema=get_event_model())

    table = db.open_table(table_name)
    if REQUIRED_COLUMNS.issubset(set(table.schema.names)):
        return table
    return migrate_table(db_path, table_name)


def open_table_if_exists(db_path: str = DB_PATH, table_name: str = TABLE_NAME):
    db = connect_db(db_path)
    existing_tables = set(db.list_tables().tables)
    if table_name not in existing_tables:
        return None

    table = db.open_table(table_name)
    if REQUIRED_COLUMNS.issubset(set(table.schema.names)):
        return table
    return migrate_table(db_path, table_name)


def migrate_table(db_path: str = DB_PATH, table_name: str = TABLE_NAME):
    db = connect_db(db_path)
    table = db.open_table(table_name)
    legacy_rows = table.to_arrow().to_pylist()
    upgraded_rows = []
    for row in legacy_rows:
        upgraded = upgrade_legacy_row(row)
        if upgraded is not None:
            upgraded_rows.append(upgraded)

    db.drop_table(table_name)
    upgraded_table = db.create_table(table_name, schema=get_event_model())
    if upgraded_rows:
        upgraded_table.add(upgraded_rows)
    logger.info("Migrated Lance table %s with %d upgraded rows", table_name, len(upgraded_rows))
    return upgraded_table


def add_event_rows(table, event_rows: list[dict[str, Any]]) -> int:
    if not event_rows:
        return 0

    model = get_embedding_model()
    event_model = get_event_model()
    texts_to_embed = [row["text"] for row in event_rows]
    vectors = model.compute_source_embeddings(texts_to_embed)
    records_to_insert = []

    for row, vector in zip(event_rows, vectors):
        records_to_insert.append(
            event_model(
                source_id=row["source_id"],
                event_type=row["event_type"],
                symbol=row.get("symbol") or None,
                timestamp=int(row["timestamp"]),
                text=row["text"],
                vector=vector,
            )
        )

    table.add(records_to_insert)
    return len(records_to_insert)