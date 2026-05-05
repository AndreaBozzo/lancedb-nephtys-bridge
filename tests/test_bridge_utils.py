from __future__ import annotations

import unittest

from nephtys_bridge.utils import extract_text_content, iter_event_rows


class BridgeUtilsTests(unittest.TestCase):
    def test_iter_event_rows_supports_wikipedia_batch_payloads(self) -> None:
        rows = iter_event_rows(
            {
                "source": "wiki",
                "type": "recent_changes_batch",
                "timestamp": 1_700_000_000,
                "payload": [
                    {
                        "title": "Bitcoin",
                        "comment": "Added regulation update",
                        "user": "alice",
                        "bot": False,
                    }
                ],
            }
        )

        self.assertEqual(len(rows), 1)
        self.assertIn("Bitcoin", rows[0]["text"])
        self.assertIn("source=wiki", rows[0]["text"])
        self.assertIn("type=recent_changes_batch", rows[0]["text"])
        self.assertEqual(rows[0]["event_type"], "recent_changes_batch")
        self.assertIsNone(rows[0]["symbol"])

    def test_extract_text_content_supports_generic_news_payloads(self) -> None:
        text = extract_text_content(
            "rss_news",
            "article",
            {
                "headline": "Exchange hack sparks solvency concerns",
                "summary": "Large withdrawals resume after the incident.",
                "symbol": "BTCUSDT",
            },
        )

        self.assertIsNotNone(text)
        assert text is not None
        self.assertIn("Exchange hack", text)
        self.assertIn("symbol=BTCUSDT", text)

    def test_extract_text_content_falls_back_to_market_summary(self) -> None:
        text = extract_text_content(
            "binance_btc_trade",
            "trade",
            {
                "symbol": "BTCUSDT",
                "price": "68000",
                "volume": "2.0",
                "imbalance": "0.4",
            },
        )

        self.assertEqual(
            text,
            "source=binance_btc_trade | type=trade | symbol=BTCUSDT | price=68000 volume=2.0 imbalance=0.4",
        )

    def test_upgrade_legacy_row_extracts_inline_metadata(self) -> None:
        from nephtys_bridge.utils import upgrade_legacy_row

        upgraded = upgrade_legacy_row(
            {
                "source_id": "",
                "timestamp": 1_700_000_000_000,
                "text": "source=wiki_live_edits | type=message_batch | symbol=BTCUSDT | headline",
                "vector": [0.0, 1.0],
            }
        )

        assert upgraded is not None
        self.assertEqual(upgraded["source_id"], "wiki_live_edits")
        self.assertEqual(upgraded["event_type"], "message_batch")
        self.assertEqual(upgraded["symbol"], "BTCUSDT")


if __name__ == "__main__":
    unittest.main()
