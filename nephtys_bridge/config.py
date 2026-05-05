from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class BridgeSettings:
    db_path: str
    table_name: str
    nats_url: str
    stream_topic: str
    embedding_model: str


@dataclass(frozen=True)
class BridgeServiceSettings:
    host: str
    port: int
    default_limit: int


@dataclass(frozen=True)
class BridgeMaintenanceSettings:
    e2e_runs_root: str
    keep_runs: int
    max_age_days: float
    version_age_days: float


def bridge_settings() -> BridgeSettings:
    return BridgeSettings(
        db_path=os.getenv("BRIDGE_DB_PATH", "./data/nephtys_lancedb"),
        table_name=os.getenv("BRIDGE_TABLE_NAME", "live_streams"),
        nats_url=os.getenv("BRIDGE_NATS_URL", "nats://localhost:4222"),
        stream_topic=os.getenv("BRIDGE_STREAM_TOPIC", "nephtys.stream.>"),
        embedding_model=os.getenv("BRIDGE_EMBEDDING_MODEL", "all-MiniLM-L6-v2"),
    )


def bridge_service_settings() -> BridgeServiceSettings:
    return BridgeServiceSettings(
        host=os.getenv("BRIDGE_SERVICE_HOST", "127.0.0.1"),
        port=int(os.getenv("BRIDGE_SERVICE_PORT", "8787")),
        default_limit=int(os.getenv("BRIDGE_SERVICE_DEFAULT_LIMIT", "10")),
    )


def bridge_maintenance_settings() -> BridgeMaintenanceSettings:
    return BridgeMaintenanceSettings(
        e2e_runs_root=os.getenv("BRIDGE_E2E_RUNS_ROOT", "./data/e2e_runs"),
        keep_runs=int(os.getenv("BRIDGE_RETENTION_KEEP_RUNS", "5")),
        max_age_days=float(os.getenv("BRIDGE_RETENTION_MAX_AGE_DAYS", "7")),
        version_age_days=float(os.getenv("BRIDGE_RETENTION_VERSION_AGE_DAYS", "7")),
    )
