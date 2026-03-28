import asyncio
import json
import logging
from typing import TYPE_CHECKING

import nats
import lancedb
from lancedb.pydantic import LanceModel, Vector
from lancedb.embeddings import get_registry

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("nephtys-bridge")

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
    db = lancedb.connect("./data/nephtys_lancedb")

    table_name = "live_streams"
    if table_name not in db.list_tables():
        table = db.create_table(table_name, schema=NephtysEvent)
    else:
        table = db.open_table(table_name)

    nc = await nats.connect("nats://localhost:4222")
    js = nc.jetstream()
    
    stream_topic = "nephtys.stream.>"

    async def message_handler(msg):
        try:
            data = json.loads(msg.data.decode())
            source_id = data.get("source", "unknown")
            timestamp = data.get("timestamp", 0)
            event_type = data.get("type", "")
            payload = data.get("payload", [])

            # Support both batched payloads and single events.
            if event_type.endswith("_batch") and isinstance(payload, list):
                payloads = payload
            elif isinstance(payload, dict):
                payloads = [payload]
            else:
                await msg.ack()
                return

            texts_to_embed = []
            event_rows = []

            for item in payloads:
                if not isinstance(item, dict):
                    continue

                bot = item.get("bot", False)
                title = item.get("title", "")
                comment = item.get("comment", "")
                user = item.get("user", "")

                if not title or bot:
                    continue

                text_content = f"L'utente {user} ha modificato la pagina '{title}'. Commento: {comment}"
                texts_to_embed.append(text_content)
                event_rows.append(
                    {
                        "source_id": source_id,
                        "timestamp": item.get("timestamp", timestamp),
                        "text": text_content,
                    }
                )

            if event_rows:
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

    sub = await js.subscribe(stream_topic, cb=message_handler)

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