from __future__ import annotations

import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from nephtys_bridge.maintenance import optimize_table_storage, prune_e2e_runs


class MaintenanceTests(unittest.TestCase):
    def test_prune_e2e_runs_keeps_newest_and_deletes_overflow(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            keep = root / "keep"
            delete = root / "delete"
            keep.mkdir()
            delete.mkdir()
            now = time.time()
            keep.touch()
            delete.touch()
            keep_mtime = now
            delete_mtime = now - 60
            os.utime(keep, (keep_mtime, keep_mtime))
            os.utime(delete, (delete_mtime, delete_mtime))

            deleted = prune_e2e_runs(root, keep_runs=1, max_age_days=None)

            self.assertEqual(deleted, [str(delete)])
            self.assertTrue(keep.exists())
            self.assertFalse(delete.exists())

    @patch("nephtys_bridge.maintenance.open_table_if_exists")
    def test_optimize_table_storage_calls_compaction_and_cleanup(
        self, open_table_mock
    ) -> None:
        class FakeTable:
            def compact_files(self):
                return "compacted"

            def cleanup_old_versions(self, older_than):
                self.older_than = older_than
                return "cleaned"

        table = FakeTable()
        open_table_mock.return_value = table

        result = optimize_table_storage(
            "/tmp/db", "live_streams", cleanup_older_than_days=2
        )

        self.assertTrue(result["table_exists"])
        self.assertEqual(result["compaction"], "compacted")
        self.assertEqual(result["cleanup"], "cleaned")


if __name__ == "__main__":
    unittest.main()
