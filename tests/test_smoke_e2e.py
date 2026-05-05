from __future__ import annotations

import json
import os
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(
    os.getenv("RUN_BRIDGE_E2E_SMOKE") == "1", "Set RUN_BRIDGE_E2E_SMOKE=1 to run"
)
class BridgeSmokeE2ETests(unittest.TestCase):
    def test_wiki_sidecar_script_returns_non_empty_query_output(self) -> None:
        env = os.environ.copy()
        env.setdefault("TIMEOUT_SECONDS", "180")
        env.setdefault("RUN_ID", "smoke-e2e")

        completed = subprocess.run(
            ["bash", "scripts/e2e_wiki_sidecar.sh"],
            cwd=ROOT,
            env=env,
            capture_output=True,
            text=True,
            timeout=360,
            check=False,
        )

        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        self.assertIn("E2E session completed successfully.", completed.stdout)

        json_line = next(
            (
                line
                for line in completed.stdout.splitlines()
                if line.strip().startswith("[{")
            ),
            "[]",
        )
        payload = json.loads(json_line)
        self.assertTrue(payload)


if __name__ == "__main__":
    unittest.main()
