# pyright: reportMissingImports=false, reportMissingModuleSource=false

import asyncio
import json
import logging
import os

import nats

from bridge_config import bridge_settings
from bridge_db import add_event_rows, ensure_table
from bridge_utils import iter_event_rows  # type: ignore[import-not-found]

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("nephtys-bridge")


async def main():
    settings = bridge_settings()
    os.makedirs(os.path.dirname(settings.db_path) or ".", exist_ok=True)
    table = ensure_table(settings.db_path, settings.table_name)

    nc = await nats.connect(settings.nats_url)
    js = nc.jetstream()

    async def message_handler(msg):
        try:
            data = json.loads(msg.data.decode())
            event_rows = iter_event_rows(data)

            if event_rows:
                saved = add_event_rows(table, event_rows)
                logger.info("Saved %d records to LanceDB", saved)

            await msg.ack()

        except Exception as e:
            logger.exception("message_handler failed: %s", e)

    sub = await js.subscribe(settings.stream_topic, cb=message_handler)

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