"""Exercise the real release for linked tables, quarantine and structured roles."""
import csv
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from rakshak.formats import Rewrite, transform
from rakshak.release import publish_release


class ReleaseFixesTest(unittest.TestCase):
    def test_nested_patient_roles_do_not_redact_provider_or_clinical_fields(self):
        source = {"patients": [{"name": {"first": "Mira", "last": "Sen", "local": "मीरा"},
                                "guardian": {"name": "Asha Sen"},
                                "address": {"line": "House 123", "district": "Example District"},
                                "provider": {"name": "Dr. Nova"},
                                "diagnosis": {"name": "Asthma"}}]}
        rendered, locators = transform(json.dumps(source), ".json", Rewrite())
        patient = json.loads(rendered)["patients"][0]
        self.assertEqual(locators, ["/patients/0"])
        self.assertEqual(patient["name"], {"first": "[NAME]", "last": "[NAME]", "local": "[NAME]"})
        self.assertEqual(patient["guardian"]["name"], "[RELATIVE]")
        self.assertEqual(patient["address"]["line"], "[ADDRESS]")
        self.assertEqual(patient["address"]["district"], "Example District")
        self.assertEqual(patient["provider"]["name"], "Dr. Nova")

    def test_identifying_column_headers_are_disambiguated_without_raw_data(self):
        source = "Time,JJH-124567 Mira,JJH-124568 Asha\n09:30,120/80,130/85\n"
        rendered, _ = transform(source, ".csv", Rewrite())
        header, row = list(csv.reader(rendered.splitlines()))
        self.assertEqual(len(set(header)), 3)
        self.assertTrue(header[1].endswith("__col2"))
        self.assertTrue(header[2].endswith("__col3"))
        self.assertNotIn("Mira", rendered)
        self.assertNotIn("Asha", rendered)
        self.assertEqual(row, ["09:30", "120/80", "130/85"])

    def test_linked_id_is_present_in_table_and_index_and_rotates(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "input"
            source.mkdir()
            header = "Patient Name,Aadhaar,Age,Dose\n"
            (source / "first.csv").write_text(header + "Mira Sen,243512345678,47,5 mg\n")
            (source / "second.csv").write_text(header + "Mira Sen,243512345678,47,10 mg\n")
            # Invalid input with the same anchor must not generate an index entry.
            (source / "broken.csv").write_text(header + "Mira Sen,243512345678,47\n")
            pseudos = []
            for run, key in (("one", b"secret-one"), ("two", b"secret-two")):
                out = root / run
                counts = publish_release(source, out, key)
                entries = [json.loads(line) for line in (out / "records.jsonl").read_text().splitlines()]
                self.assertEqual(counts["files_quarantined"], 1)
                self.assertEqual(counts["records_linked"], 2)
                self.assertEqual(len(entries), 2)
                self.assertEqual(entries[0]["patient"], entries[1]["patient"])
                self.assertIsNotNone(entries[0]["patient"])
                self.assertEqual(counts["records_generalized"], 2)
                for entry in entries:
                    with (out / entry["file"]).open(newline="") as stream:
                        row = list(csv.reader(stream))[1]
                    self.assertEqual(row[1], entry["patient"])
                    self.assertEqual(row[2], "45-49")
                    self.assertIn(row[3], {"5 mg", "10 mg"})
                    self.assertNotIn("243512345678", (out / entry["file"]).read_text())
                pseudos.append(entries[0]["patient"])
            self.assertNotEqual(*pseudos)


if __name__ == "__main__":
    unittest.main()
