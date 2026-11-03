import unittest

from scripts.build_pine_candidate_metadata import build_candidate_metadata


def reference_meta():
    return {
        "script_title": "Alpha Signal Engine Pro",
        "pine_version": "6",
        "symbol": "OANDA:XAUUSD",
        "provider": "OANDA",
        "timezone": "UTC",
        "timeframe": "60",
        "bar_timestamp": "bar_open_unix_seconds",
        "bar_confirmation": "barstate.isconfirmed",
        "settings": {"ema_length": 20, "atr_length": 14},
    }


class PineCandidateMetadataTests(unittest.TestCase):
    def test_builds_candidate_only_for_exact_source_and_settings(self):
        meta = reference_meta()
        candidate = build_candidate_metadata(
            meta, dict(meta["settings"]), source="OANDA", symbol="OANDA:XAUUSD"
        )
        self.assertEqual(candidate["settings"], meta["settings"])
        self.assertEqual(candidate["script_title"], meta["script_title"])
        self.assertEqual(candidate["implementation"], "Python Alpha Signal Engine")

    def test_rejects_settings_mismatch(self):
        meta = reference_meta()
        with self.assertRaisesRegex(ValueError, "does not exactly match"):
            build_candidate_metadata(
                meta, {"ema_length": 21}, source="OANDA", symbol="OANDA:XAUUSD"
            )

    def test_rejects_provider_or_symbol_mismatch(self):
        meta = reference_meta()
        with self.assertRaisesRegex(ValueError, "provider"):
            build_candidate_metadata(
                meta, meta["settings"], source="TVC", symbol="OANDA:XAUUSD"
            )
        with self.assertRaisesRegex(ValueError, "symbol"):
            build_candidate_metadata(
                meta, meta["settings"], source="OANDA", symbol="TVC:GOLD"
            )

    def test_rejects_non_1h_or_unconfirmed_or_local_timestamp_metadata(self):
        cases = (
            ("timeframe", "15"),
            ("timezone", "Asia/Kolkata"),
            ("bar_timestamp", "bar_close_local"),
            ("bar_confirmation", "intrabar"),
        )
        for key, value in cases:
            with self.subTest(key=key):
                meta = reference_meta()
                meta[key] = value
                with self.assertRaises(ValueError):
                    build_candidate_metadata(
                        meta, meta["settings"], source="OANDA", symbol="OANDA:XAUUSD"
                    )

    def test_rejects_empty_or_incomplete_metadata(self):
        meta = reference_meta()
        meta["settings"] = {}
        with self.assertRaises(ValueError):
            build_candidate_metadata(
                meta, meta["settings"], source="OANDA", symbol="OANDA:XAUUSD"
            )
        meta = reference_meta()
        del meta["pine_version"]
        with self.assertRaisesRegex(ValueError, "pine_version"):
            build_candidate_metadata(
                meta, meta["settings"], source="OANDA", symbol="OANDA:XAUUSD"
            )


if __name__ == "__main__":
    unittest.main()
