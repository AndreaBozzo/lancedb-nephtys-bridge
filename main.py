# pyright: reportMissingImports=false, reportMissingModuleSource=false

import asyncio
import json
import logging
from typing import TYPE_CHECKING

import nats
import lancedb  # type: ignore[import-untyped]
from lancedb.embeddings import get_registry  # type: ignore[import-untyped]
from lancedb.pydantic import LanceModel, Vector  # type: ignore[import-untyped]

from bridge_utils import iter_event_rows  # type: ignore[import-not-found]

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("nephtys-bridge")

DB_PATH = "./data/nephtys_lancedb"
TABLE_NAME = "live_streams"
NATS_URL = "nats://localhost:4222"
STREAM_TOPIC = "nephtys.stream.>"

model = get_registry().get("sentence-transformers").create(name="all-MiniLM-L6-v2")

if TYPE_CHECKING:
    EmbeddingVector = list[float]
else:
    EmbeddingVector = Vector(model.ndims())

class NephtysEvent(LanceModel):
    source_id: str
    timestamp: int
    text: str = model.SourceField()
    vector: EmbeddingVector = model.VectorField()


async def main():
    db = lancedb.connect(DB_PATH)

    existing_tables = db.list_tables().tables
    if TABLE_NAME not in existing_tables:
        table = db.create_table(TABLE_NAME, schema=NephtysEvent)
    else:
        table = db.open_table(TABLE_NAME)

    nc = await nats.connect(NATS_URL)
    js = nc.jetstream()

    async def message_handler(msg):
        try:
            data = json.loads(msg.data.decode())
            event_rows = iter_event_rows(data)

            if event_rows:
                texts_to_embed = [row["text"] for row in event_rows]
                vectors = model.compute_source_embeddings(texts_to_embed)
                records_to_insert = []

                for row, vector in zip(event_rows, vectors):
                    records_to_insert.append(
                        NephtysEvent(
                            source_id=row["source_id"],
                            timestamp=row["timestamp"],
                            text=row["text"],
                            vector=vector,
                        )
                    )

                table.add(records_to_insert)
                logger.info("Saved %d records to LanceDB", len(records_to_insert))

            await msg.ack()

        except Exception as e:
            logger.exception("message_handler failed: %s", e)

    sub = await js.subscribe(STREAM_TOPIC, cb=message_handler)

    try:
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        await sub.unsubscribe()
        await nc.drain()

if __name__ == '__main__':
    asyncio.run(main())