# pyright: reportMissingImports=false, reportMissingModuleSource=false

from __future__ import annotations

import asyncio
import json
import logging
import os

import nats

from .config import bridge_settings
from .db import add_event_rows, ensure_table
from .utils import iter_event_rows

logger = logging.getLogger("nephtys-bridge")


async def main() -> None:
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

        except Exception as exc:
            logger.exception("message_handler failed: %s", exc)

    sub = await js.subscribe(settings.stream_topic, cb=message_handler)

    try:
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        await sub.unsubscribe()
        await nc.drain()
