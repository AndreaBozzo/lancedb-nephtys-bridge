from __future__ import annotations

import json
import unittest

from query import _filter_results, print_results


class QueryTests(unittest.TestCase):
    def test_filter_results_deduplicates_and_applies_limit(self) -> None:
        results = _filter_results(
            [
                {"text": "hack headline", "timestamp": 1_700_000_000_000, "_distance": 0.1},
                {"text": "hack headline", "timestamp": 1_700_000_000_100, "_distance": 0.2},
                {"text": "second headline", "timestamp": 1_700_000_000_200, "_distance": 0.3},
            ],
            limit=2,
            content_only=False,
        )

        self.assertEqual([row["text"] for row in results], ["hack headline", "second headline"])

    def test_print_results_json_output_is_machine_readable(self) -> None:
        rows = [
            {
                "text": "exchange hack",
                "timestamp": 1_700_000_000_000,
                "source_id": "rss_news",
                "_distance": 0.12,
            }
        ]

        import io
        import sys

        buffer = io.StringIO()
        previous = sys.stdout
        sys.stdout = buffer
        try:
            print_results(rows, "hack", content_only=False, json_output=True)
        finally:
            sys.stdout = previous

        payload = json.loads(buffer.getvalue())
        self.assertEqual(payload[0]["text"], "exchange hack")
        self.assertEqual(payload[0]["source_id"], "rss_news")


if __name__ == "__main__":
    unittest.main()