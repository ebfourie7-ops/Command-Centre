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

    def test_review_gated_evidence_targets_findings_and_custody(self):
        case_id = self.store.add_case("Workflow case")
        self.store.add_target(case_id, "Domain", "example.com", "Authorized public research")
        inbox_id = self.store.add_inbox(case_id, "Capture", "web-page", "https://example.com", digest="abc")
        self.assertEqual(len(self.store.inbox(case_id)), 1)
        evidence_id = self.store.accept_inbox(inbox_id)
        finding_id = self.store.add_finding(case_id, "Related infrastructure", "Analyst-reviewed draft", "medium")
        self.store.db.execute("INSERT INTO finding_evidence(finding_id,evidence_id,role) VALUES(?,?,'supporting')", (finding_id, evidence_id))
        self.store.db.commit()
        custody = self.store.db.execute("SELECT * FROM custody_events WHERE evidence_id=?", (evidence_id,)).fetchall()
        self.assertEqual(len(self.store.targets(case_id)), 1)
        self.assertEqual(len(self.store.evidence(case_id)), 1)
        self.assertEqual(len(self.store.findings(case_id)), 1)
        self.assertEqual(len(custody), 1)
        self.assertEqual(len(custody[0]["event_hash"]), 64)


if __name__ == "__main__":
    unittest.main()
