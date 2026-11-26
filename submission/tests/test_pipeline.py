import base64
import csv
from datetime import date
import io
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from rakshak.detection import SourceUnit, detect
from rakshak.formats import Rewrite, UnsafeInput, transform
from rakshak.release import publish_release


class DetectionTest(unittest.TestCase):
    def test_positions_are_original(self):
        source = "🩺 ९१२३\u200b४५६७८९; 650 mg"
        finding, = detect(SourceUnit(source)).findings
        self.assertEqual(source[finding.start:finding.end], "९१२३\u200b४५६७८९")
        self.assertEqual(finding.kind, "PHONE")

    def test_name_roles_and_ambiguous_care_of(self):
        source = "Dr. Mira spoke. S/o Mira"
        finding, = detect(SourceUnit(source)).findings
        self.assertEqual(finding.start, source.rindex("Mira"))
        self.assertFalse(detect(SourceUnit("C/O fever")).findings)
        self.assertTrue(detect(SourceUnit("C/O uncertain")).review)

    def test_multilingual_roles_and_hidden_channels(self):
        source = ("मरीज़: काव्या सेन\nरिश्तेदार: मीरा सेन\nफ़ोन: ०००००-०००००\n"
                  "Jaya Sen ji aaye, W/o Mira Sen. Phone +91 00000-00000. C/O chakkar.")
        regions = {source[item.start:item.end]: item.kind for item in detect(SourceUnit(source)).findings}
        self.assertEqual(regions["काव्या सेन"], "NAME")
        self.assertEqual(regions["मीरा सेन"], "RELATIVE")
        self.assertEqual(regions["Jaya Sen"], "NAME")
        self.assertEqual(regions["Mira Sen"], "RELATIVE")
        self.assertEqual(regions["+91 00000-00000"], "PHONE")
        self.assertNotIn("chakkar", regions)
        self.assertTrue(detect(SourceUnit("NovaPerson10101010.txt", channel="filename")).findings)
        self.assertFalse(detect(SourceUnit("note_1234.txt", channel="filename")).findings)

    def test_clinical_patient_heading_is_not_a_name(self):
        source = "Patient - received aspirin 75 mg daily"
        self.assertEqual(transform(source, ".txt", Rewrite())[0], source)


class FormatTest(unittest.TestCase):
    def test_delimiter_and_original_label_roles(self):
        output, locations = transform('नाम\tDose\n"ईशा राव"\t650 mg\n', ".tsv", Rewrite())
        self.assertEqual(list(csv.reader(io.StringIO(output), delimiter="\t")),
                         [["नाम", "Dose"], ["[NAME]", "650 mg"]])
        self.assertEqual(locations, ["row:0"])

    def test_transliterated_birth_date_field(self):
        output, _ = transform("Janm Tithi\tBP\tDose\n1991-02-03\t120/80\t650 mg\n",
                              ".tsv", Rewrite())
        self.assertEqual(list(csv.reader(io.StringIO(output), delimiter="\t")),
                         [["Janm Tithi", "BP", "Dose"], ["[DOB]", "120/80", "650 mg"]])

    def test_json_types_precision_and_duplicate_key(self):
        output, _ = transform('{"mobile":9123456789,"measurement":2.00,"flag":true}', ".json", Rewrite())
        self.assertEqual(json.loads(output), {"mobile": 0, "measurement": 2.0, "flag": True})
        self.assertIn('"measurement":2.00', output)
        with self.assertRaisesRegex(UnsafeInput, "duplicate_json_key"):
            transform('{"key":"x","key":"y"}', ".json", Rewrite())

    def test_fhir_references_narrative_and_attachment(self):
        anchor = "urn:uuid:91234567-1234-1234-1234-912345678912"
        attachment = base64.b64encode(b"Phone: 9123456789").decode("ascii")
        bundle = {
            "resourceType": "Bundle", "type": "collection", "entry": [
                {"fullUrl": anchor, "resource": {"resourceType": "Patient", "name": [
                    {"given": ["Mira"], "family": "Sen"}], "text": {"status": "generated",
                    "div": '<div xmlns="http://www.w3.org/1999/xhtml">Mira Sen, 27 yrs</div>'}}},
                {"resource": {"resourceType": "Observation", "subject": {"reference": anchor},
                              "valueQuantity": {"value": 9123456789, "unit": "mg/dL"}}},
                {"resource": {"resourceType": "DocumentReference",
                              "content": [{"attachment": {"contentType": "text/plain", "data": attachment}}]}},
            ],
        }
        result, locators = transform(json.dumps(bundle), ".json", Rewrite())
        self.assertNotIn("Mira", result)
        self.assertEqual(locators, ["doc"])
        entries = json.loads(result)["entry"]
        self.assertEqual(entries[0]["fullUrl"], entries[1]["resource"]["subject"]["reference"])
        self.assertEqual(entries[1]["resource"]["valueQuantity"]["value"], 9123456789)
        value = entries[2]["resource"]["content"][0]["attachment"]["data"]
        self.assertNotIn(b"9123456789", base64.b64decode(value))
        bundle["entry"][0].pop("fullUrl")
        with self.assertRaisesRegex(UnsafeInput, "unresolved_fhir_reference"):
            transform(json.dumps(bundle), ".json", Rewrite())

    def test_fhir_birth_date_never_becomes_an_invalid_placeholder(self):
        bundle = {"resourceType": "Bundle", "type": "document", "entry": [
            {"fullUrl": "urn:uuid:22222222-2222-4222-8222-222222222222",
             "resource": {"resourceType": "Patient", "id": "22222222-2222-4222-8222-222222222222",
                          "birthDate": "1991-02-03"}}]}
        try:
            output, _ = transform(json.dumps(bundle), ".json", Rewrite())
        except UnsafeInput as exc:
            self.assertEqual(exc.args[0], "unsupported_fhir_date_transform")
        else:
            released = json.loads(output)["entry"][0]["resource"]["birthDate"]
            date.fromisoformat(released)
            self.assertNotEqual(released, "[DOB]")


class ReleaseTest(unittest.TestCase):
    def test_all_output_path_components_are_keyed(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "input"
            (source / "patient_synthetic").mkdir(parents=True)
            (source / "patient_synthetic" / "unlabeled-person.txt").write_text("BP: 120/80")
            first, second = root / "first", root / "second"
            publish_release(source, first, b"key-a")
            publish_release(source, second, b"key-b")
            paths = [next((out / "sanitized").rglob("*.txt")).relative_to(out / "sanitized")
                     for out in (first, second)]
            self.assertNotEqual(paths[0], paths[1])
            self.assertTrue(all(part.startswith(("directory_", "file_"))
                                for path in paths for part in path.parts))
            self.assertEqual(next((first / "sanitized").rglob("*.txt")).read_text(), "BP: 120/80")

    def test_repeatable_and_quarantine_does_not_publish_raw(self):
        with TemporaryDirectory() as temporary:
            directory = Path(temporary)
            source = directory / "input"
            source.mkdir()
            sample = b"Name: Mira Sen"
            (source / "9123456789.txt").write_bytes(sample)
            (source / "duplicate.txt").write_bytes(sample)
            (source / "unreadable.pdf").write_bytes(b"raw synthetic marker")
            (source / "review.txt").write_text("C/O uncertain")
            out, repeat, rotated = (directory / label for label in ("a", "b", "c"))
            for path, key in ((out, b"key-a"), (repeat, b"key-a"), (rotated, b"key-b")):
                publish_release(source, path, key)
            def artifacts(path):
                return {file.relative_to(path): file.read_bytes() for file in path.rglob("*")
                        if file.is_file() and file.name != "report.json"}
            self.assertEqual(artifacts(out), artifacts(repeat))
            self.assertNotEqual(artifacts(out), artifacts(rotated))
            self.assertNotIn(b"Mira", b"".join(artifacts(out).values()))
            report = json.loads((out / "report.json").read_text())
            self.assertEqual(report["counts"]["files_sanitized"], 2)
            self.assertEqual(report["counts"]["files_quarantined"], 2)
            self.assertEqual(report["files"][0]["input_sha256"], report["files"][1]["input_sha256"])
            self.assertEqual((source / "9123456789.txt").read_bytes(), sample)


if __name__ == "__main__":
    unittest.main()
