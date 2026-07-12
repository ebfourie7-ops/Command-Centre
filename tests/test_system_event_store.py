import tempfile
import unittest
from pathlib import Path

from core.events import SystemEventStore


class SystemEventStoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / "private" / "events.db"
        self.store = SystemEventStore(self.path)

    def tearDown(self):
        self.store.close()
        self.temp.cleanup()

    def test_private_permissions_and_deduplication(self):
        self.assertEqual(self.path.parent.stat().st_mode & 0o777, 0o700)
        self.assertEqual(self.path.stat().st_mode & 0o777, 0o600)
        self.assertTrue(self.store.add("POWER", "GPU entered P8", dedupe_key="gpu-p8"))
        self.assertFalse(self.store.add("POWER", "GPU entered P8", dedupe_key="gpu-p8"))
        self.assertEqual(len(self.store.recent()), 1)

    def test_observed_state_round_trip(self):
        expected = {"vpn": True, "updates": 2, "profile": "power-saver"}
        self.store.save_observed_states(expected)
        decoded = self.store.decode_observed_states(self.store.observed_states())
        self.assertEqual(decoded, expected)

    def test_routine_startup_noise_is_removed(self):
        self.store.add("SYSTEM", "Telemetry connected", dedupe_key="old-noise")
        self.store.close()
        self.store = SystemEventStore(self.path)
        self.assertEqual(self.store.recent(), [])


if __name__ == "__main__":
    unittest.main()
