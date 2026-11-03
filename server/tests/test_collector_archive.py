import importlib.util
import unittest
from pathlib import Path

MODULE_PATH=Path(__file__).resolve().parents[2]/"scripts"/"collect_free_xau.py"
SPEC=importlib.util.spec_from_file_location("collect_free_xau",MODULE_PATH)
collector=importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(collector)


class RollingArchiveTests(unittest.TestCase):
    def test_archive_keeps_only_last_90_days_and_sorts(self):
        now=2_000_000_000
        cutoff=now-collector.RETENTION_SECONDS
        existing=[{"t":cutoff-1,"p":2300.0},{"t":now-20,"p":2301.0}]
        incoming=[{"t":now-10,"p":2302.0},{"t":now,"p":2303.0}]
        result=collector.merge_archive(existing,incoming,now)
        self.assertEqual([p["t"] for p in result],[now-20,now-10,now])

    def test_new_sample_replaces_same_timestamp(self):
        now=2_000_000_000
        result=collector.merge_archive(
            [{"t":now-1,"p":2300.0}],
            [{"t":now-1,"p":2305.0}],
            now,
        )
        self.assertEqual(len(result),1)
        self.assertEqual(result[0]["p"],2305.0)


if __name__=="__main__":
    unittest.main()
