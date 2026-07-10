import tempfile
import unittest
from pathlib import Path

import command_intel


class IntelStoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        command_intel.DATA_DIR = Path(self.temp.name)
        command_intel.DB_FILE = command_intel.DATA_DIR / "intel.db"
        command_intel.EVIDENCE_DIR = command_intel.DATA_DIR / "evidence"
        self.store = command_intel.IntelStore()

    def tearDown(self):
        self.store.db.close()
        self.temp.cleanup()

    def test_case_lifecycle_and_migration_fields(self):
        case_id = self.store.add_case("Authorized research")
        self.store.update_case(case_id, authorization="Written approval", scope="example.com")
        row = self.store.db.execute("SELECT * FROM cases WHERE id=?", (case_id,)).fetchone()
        self.assertEqual(row["authorization"], "Written approval")
        self.assertEqual(row["scope"], "example.com")
        self.store.update_case(case_id, status="archived")
        self.assertEqual(len(self.store.cases(include_archived=False)), 0)

    def test_evidence_entities_relations_and_backup(self):
        case_id = self.store.add_case("Case")
        evidence_id = self.store.add_evidence(case_id, "Source", "note", notes="Observed")
        self.store.add_entity(case_id, "Domain", "example.com", "manual", 90)
        self.store.add_entity(case_id, "IP Address", "192.0.2.1", "manual", 80)
        entities = self.store.entities(case_id)
        self.store.add_relation(case_id, entities[0]["id"], entities[1]["id"], "resolves to", evidence_id)
        self.assertEqual(len(self.store.evidence(case_id)), 1)
        self.assertEqual(len(self.store.relations(case_id)), 1)
        backup = Path(self.temp.name) / "backup.db"
        self.store.backup(backup)
        self.assertTrue(backup.exists())

    def test_file_hash_is_stable(self):
        path = Path(self.temp.name) / "sample.txt"
        path.write_text("command intel", encoding="utf-8")
        first = command_intel.AdvancedCommandIntelPage.hash_file(path)
        second = command_intel.AdvancedCommandIntelPage.hash_file(path)
        self.assertEqual(first, second)
        self.assertEqual(len(first), 64)


if __name__ == "__main__":
    unittest.main()
