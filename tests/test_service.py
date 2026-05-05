from __future__ import annotations

import unittest
from unittest.mock import patch

from nephtys_bridge.service import query_response_from_params


class ServiceTests(unittest.TestCase):
    def test_query_response_requires_query_text(self) -> None:
        status, payload = query_response_from_params({})

        self.assertEqual(status, 400)
        self.assertEqual(payload["error"], "missing query parameter 'q'")

    @patch("nephtys_bridge.service.query_stream")
    def test_query_response_passes_filters_through(self, query_stream_mock) -> None:
        query_stream_mock.return_value = [
            {
                "timestamp": 1_700_000_000_000,
                "source_id": "rss_news",
                "event_type": "article",
                "symbol": "BTCUSDT",
                "text": "exchange hack",
                "_distance": 0.2,
            }
        ]

        status, payload = query_response_from_params(
            {
                "q": ["hack"],
                "limit": ["3"],
                "all_namespaces": ["true"],
                "source": ["rss_news"],
                "event_type": ["article"],
                "symbol": ["BTCUSDT"],
                "max_age_seconds": ["60"],
            }
        )

        self.assertEqual(status, 200)
        self.assertEqual(payload[0]["source_id"], "rss_news")
        self.assertEqual(payload[0]["symbol"], "BTCUSDT")
        query_stream_mock.assert_called_once_with(
            "hack",
            limit=3,
            content_only=False,
            db_path=unittest.mock.ANY,
            table_name=unittest.mock.ANY,
            source_filters=["rss_news"],
            event_type_filters=["article"],
            symbol_filters=["BTCUSDT"],
            max_age_seconds=60,
        )


if __name__ == "__main__":
    unittest.main()
