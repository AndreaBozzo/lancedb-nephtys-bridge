from __future__ import annotations

import json
import unittest
from unittest.mock import patch

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

    @patch("query.time.time", return_value=1_700_000_100)
    def test_filter_results_applies_source_event_and_recency_filters(self, _time_mock) -> None:
        results = _filter_results(
            [
                {
                    "text": "exchange hack",
                    "timestamp": 1_700_000_050_000,
                    "source_id": "rss_news",
                    "event_type": "article",
                    "symbol": "BTCUSDT",
                    "_distance": 0.1,
                },
                {
                    "text": "user edit",
                    "timestamp": 1_700_000_080_000,
                    "source_id": "wiki",
                    "event_type": "recent_changes_batch",
                    "_distance": 0.2,
                },
            ],
            limit=5,
            content_only=False,
            source_filters=["rss_news"],
            event_type_filters=["article"],
            max_age_seconds=60,
        )

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["source_id"], "rss_news")

    def test_filter_results_applies_symbol_filter(self) -> None:
        results = _filter_results(
            [
                {
                    "text": "exchange hack",
                    "timestamp": 1_700_000_050_000,
                    "source_id": "rss_news",
                    "event_type": "article",
                    "symbol": "BTCUSDT",
                    "_distance": 0.1,
                },
                {
                    "text": "altcoin headline",
                    "timestamp": 1_700_000_080_000,
                    "source_id": "rss_news",
                    "event_type": "article",
                    "symbol": "ETHUSDT",
                    "_distance": 0.2,
                },
            ],
            limit=5,
            content_only=False,
            symbol_filters=["BTCUSDT"],
        )

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["symbol"], "BTCUSDT")

    def test_print_results_json_output_is_machine_readable(self) -> None:
        rows = [
            {
                "text": "exchange hack",
                "timestamp": 1_700_000_000_000,
                "source_id": "rss_news",
                "event_type": "article",
                "symbol": "BTCUSDT",
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
        self.assertEqual(payload[0]["symbol"], "BTCUSDT")

    def test_print_results_json_output_includes_event_type(self) -> None:
        rows = [
            {
                "text": "source=rss_news | type=article | exchange hack",
                "timestamp": 1_700_000_000_000,
                "source_id": "rss_news",
                "event_type": "article",
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
        self.assertEqual(payload[0]["event_type"], "article")


if __name__ == "__main__":
    unittest.main()