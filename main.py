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
    if table_name not in db.table_names():
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
            payload = data.get("payload", {})
            
            title = payload.get("title", "")
            comment = payload.get("comment", "")
            user = payload.get("user", "")
            bot = payload.get("bot", False)
            
            if not title or bot:
                await msg.ack()
                return

            text_content = f"L'utente {user} ha modificato la pagina '{title}'. Commento: {comment}"
            vector = model.compute_source_embeddings(text_content)[0]

            record = NephtysEvent(
                source_id=source_id,
                timestamp=timestamp,
                text=text_content,
                vector=vector,
            )
            
            table.add([record])
            
            logger.info(f"[{source_id}] {text_content[:60]}...")
            
            await msg.ack()
            
        except Exception as e:
            logger.error(e)

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