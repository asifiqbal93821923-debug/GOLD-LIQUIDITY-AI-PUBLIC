import unittest

from scripts.download_xauusd_same_feed import aggregate


class DukascopyAggregateTests(unittest.TestCase):
    @staticmethod
    def minute_rows(start, count, omit=()):
        omitted = set(omit)
        rows = []
        for offset in range(count):
            if offset in omitted:
                continue
            price = 2000.0 + offset
            rows.append({
                "time": start + offset * 60,
                "open": price,
                "high": price + 0.5,
                "low": price - 0.5,
                "close": price + 0.1,
                "volume": 1.0,
            })
        return rows

    def test_emits_only_complete_contiguous_bucket(self):
        start = 1_700_000_000 - (1_700_000_000 % 900)
        rows = self.minute_rows(start, 15)
        bars, report = aggregate(rows, 900, now=start + 1_000)
        self.assertEqual(len(bars), 1)
        self.assertEqual(report["source_m1_rows"], 15)
        self.assertEqual(report["partial_or_gapped_buckets_excluded"], 0)

    def test_excludes_bucket_when_one_source_minute_is_missing(self):
        start = 1_700_000_000 - (1_700_000_000 % 900)
        rows = self.minute_rows(start, 15, omit=(7,))
        bars, report = aggregate(rows, 900, now=start + 1_000)
        self.assertEqual(bars, [])
        self.assertEqual(report["candidate_buckets"], 1)
        self.assertEqual(report["partial_or_gapped_buckets_excluded"], 1)
        self.assertEqual(report["source_m1_rows"], 0)

    def test_excludes_unclosed_aggregation_window(self):
        start = 1_700_000_000 - (1_700_000_000 % 900)
        rows = self.minute_rows(start, 15)
        bars, report = aggregate(rows, 900, now=start + 899)
        self.assertEqual(bars, [])
        self.assertEqual(report["bars"], 0)


if __name__ == "__main__":
    unittest.main()
