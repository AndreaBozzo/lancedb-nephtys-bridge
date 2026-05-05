# pyright: reportMissingImports=false, reportMissingModuleSource=false

from __future__ import annotations

import argparse
import json
import shutil
import time
from datetime import timedelta
from pathlib import Path
from typing import Any

from bridge_config import bridge_maintenance_settings, bridge_settings
from bridge_db import open_table_if_exists

_bridge = bridge_settings()
_maintenance = bridge_maintenance_settings()
DB_PATH = _bridge.db_path
TABLE_NAME = _bridge.table_name
E2E_RUNS_ROOT = _maintenance.e2e_runs_root
RETENTION_KEEP_RUNS = _maintenance.keep_runs
RETENTION_MAX_AGE_DAYS = _maintenance.max_age_days
RETENTION_VERSION_AGE_DAYS = _maintenance.version_age_days


def prune_e2e_runs(
    root_path: str | Path = E2E_RUNS_ROOT,
    keep_runs: int = RETENTION_KEEP_RUNS,
    max_age_days: float | None = RETENTION_MAX_AGE_DAYS,
) -> list[str]:
    root = Path(root_path)
    if not root.exists():
        return []

    now = time.time()
    run_dirs = sorted(
        [path for path in root.iterdir() if path.is_dir()],
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    deleted: list[str] = []

    for index, path in enumerate(run_dirs):
        age_days = (now - path.stat().st_mtime) / 86400
        expired = max_age_days is not None and age_days > max_age_days
        overflow = index >= keep_runs
        if not (expired or overflow):
            continue
        shutil.rmtree(path, ignore_errors=True)
        deleted.append(str(path))

    return deleted


def optimize_table_storage(
    db_path: str = DB_PATH,
    table_name: str = TABLE_NAME,
    cleanup_older_than_days: float | None = RETENTION_VERSION_AGE_DAYS,
) -> dict[str, Any]:
    table = open_table_if_exists(db_path, table_name)
    if table is None:
        return {"table_exists": False, "table": table_name, "db_path": db_path}

    result: dict[str, Any] = {
        "table_exists": True,
        "table": table_name,
        "db_path": db_path,
        "compaction": str(table.compact_files()),
    }
    if cleanup_older_than_days is not None:
        result["cleanup"] = str(
            table.cleanup_old_versions(older_than=timedelta(days=cleanup_older_than_days))
        )
    return result


def run_maintenance(
    db_path: str = DB_PATH,
    table_name: str = TABLE_NAME,
    e2e_root: str = E2E_RUNS_ROOT,
    keep_runs: int = RETENTION_KEEP_RUNS,
    max_age_days: float | None = RETENTION_MAX_AGE_DAYS,
    cleanup_older_than_days: float | None = RETENTION_VERSION_AGE_DAYS,
) -> dict[str, Any]:
    return {
        "deleted_runs": prune_e2e_runs(e2e_root, keep_runs=keep_runs, max_age_days=max_age_days),
        "table_maintenance": optimize_table_storage(
            db_path=db_path,
            table_name=table_name,
            cleanup_older_than_days=cleanup_older_than_days,
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Apply retention and compaction policies")
    parser.add_argument("--db-path", default=DB_PATH)
    parser.add_argument("--table", default=TABLE_NAME)
    parser.add_argument("--e2e-root", default=E2E_RUNS_ROOT)
    parser.add_argument("--keep-runs", type=int, default=RETENTION_KEEP_RUNS)
    parser.add_argument("--max-age-days", type=float, default=RETENTION_MAX_AGE_DAYS)
    parser.add_argument("--cleanup-older-than-days", type=float, default=RETENTION_VERSION_AGE_DAYS)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    result = run_maintenance(
        db_path=args.db_path,
        table_name=args.table,
        e2e_root=args.e2e_root,
        keep_runs=args.keep_runs,
        max_age_days=args.max_age_days,
        cleanup_older_than_days=args.cleanup_older_than_days,
    )

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return

    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()