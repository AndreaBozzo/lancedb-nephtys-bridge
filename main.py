import asyncio
import json
import logging
from datetime import datetime

import nats
import lancedb
from lancedb.pydantic import LanceModel, Vector
from lancedb.embeddings import get_registry

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("nephtys-bridge")

# 1. Define the LanceDB model with automatic embedding
# We use a lightweight and fast HuggingFace model
model = get_registry().get("sentence-transformers").create(name="all-MiniLM-L6-v2")

class NephtysEvent(LanceModel):
    # The ID of the Nephtys source (e.g., "hackernews_poller")
    source_id: str 
    # The original timestamp assigned by Nephtys at ingestion
    timestamp: int 
    # The text extracted from the payload
    text: str = model.SourceField() 
    # The vector automatically calculated by LanceDB
    vector: Vector = model.VectorField()

async def main():
    # 2. Connect to LanceDB(local file-based for simplicity)
    db = lancedb.connect("./data/nephtys_lancedb")
    
    # Create table if it doesn't exist, otherwise open it
    table_name = "live_streams"
    if table_name not in db.table_names():
        table = db.create_table(table_name, schema=NephtysEvent)
        logger.info(f"LanceDB table '{table_name}' created.")
    else:
        table = db.open_table(table_name)
        logger.info(f"LanceDB table '{table_name}' opened.")

    # 3. Connect to NATS (where Nephtys publishes)
    nc = await nats.connect("nats://localhost:4222")
    js = nc.jetstream()
    
    stream_topic = "nephtys.stream.>" 

    async def message_handler(msg):
        try:
            data = json.loads(msg.data.decode())
            
            source_id = data.get("source", "unknown")
            timestamp = data.get("timestamp", 0)
            payload = data.get("payload", {})
            
            # Assume the payload contains a 'text' field or extract it
            # (In a real-world scenario, you would adapt this based on the API Nephtys is querying)
            text_content = payload.get("text", "")
            
            if not text_content:
                await msg.ack()
                return

            # 4. APPEND TO LANCEDB
            # Create the Pydantic object. LanceDB will handle calling
            # the local model and generating the embedding in the background!
            record = NephtysEvent(
                source_id=source_id,
                timestamp=timestamp,
                text=text_content
            )
            
            # LanceDB shines here: fast columnar appends
            table.add([record])
            
            logger.info(f"Saved to LanceDB: [{source_id}] {text_content[:30]}...")
            
            # Confirm to JetStream that the message has been processed
            await msg.ack()
            
        except Exception as e:
            logger.error(f"Error processing message: {e}")

    # Push subscription to JetStream
    sub = await js.subscribe(stream_topic, cb=message_handler)
    logger.info(f"Listening on {stream_topic}...")

    try:
        # Keep the loop alive
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        await sub.unsubscribe()
        await nc.drain()

if __name__ == '__main__':
    # Run the consumer with uvicorn or directly with asyncio
    asyncio.run(main())