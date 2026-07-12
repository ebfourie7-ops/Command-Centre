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
        self.assertEqual(command_intel.DATA_DIR.stat().st_mode & 0o777, 0o700)
        self.assertEqual(command_intel.DB_FILE.stat().st_mode & 0o777, 0o600)
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

    def test_password_protected_case_encrypts_fields_and_evidence(self):
        case_id = self.store.add_case("Protected case", "Sensitive description")
        self.store.update_case(case_id, authorization="Secret authority", scope="example.test")
        source = Path(self.temp.name) / "evidence.txt"
        source.write_text("sensitive evidence content", encoding="utf-8")
        digest = command_intel.AdvancedCommandIntelPage.hash_file(source)
        self.store.add_evidence(case_id, "Secret evidence", "file", "private source", str(source), digest, "private notes")
        self.store.add_target(case_id, "Domain", "example.test", "confidential purpose")
        self.store.add_entity(case_id, "Domain", "example.test", "private source", 90)

        self.store.protect_case(case_id, "correct horse battery staple")
        raw_case = self.store.db.execute("SELECT authorization,scope,password_salt FROM cases WHERE id=?", (case_id,)).fetchone()
        raw_evidence = self.store.db.execute("SELECT title,local_path,notes FROM evidence WHERE case_id=?", (case_id,)).fetchone()
        self.assertTrue(raw_case["authorization"].startswith(command_intel.ENCRYPTED_PREFIX))
        self.assertTrue(raw_case["scope"].startswith(command_intel.ENCRYPTED_PREFIX))
        self.assertTrue(raw_case["password_salt"])
        self.assertTrue(raw_evidence["title"].startswith(command_intel.ENCRYPTED_PREFIX))
        self.assertTrue(raw_evidence["local_path"].startswith(command_intel.ENCRYPTED_PREFIX))

        evidence = self.store.evidence(case_id)[0]
        encrypted_path = Path(evidence["local_path"])
        self.assertTrue(encrypted_path.exists())
        self.assertEqual(encrypted_path.suffix, ".ccvault")
        self.assertEqual(self.store.evidence_digest(case_id, encrypted_path), digest)
        self.assertEqual(self.store.case_record(case_id)["authorization"], "Secret authority")

        self.store.lock_case(case_id)
        self.assertFalse(self.store.unlock_case(case_id, "wrong password"))
        self.assertTrue(self.store.unlock_case(case_id, "correct horse battery staple"))
        self.assertEqual(self.store.evidence(case_id)[0]["notes"], "private notes")


if __name__ == "__main__":
    unittest.main()
