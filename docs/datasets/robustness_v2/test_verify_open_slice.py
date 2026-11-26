"""Fault injection for the open development slice verifier."""

import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from build_open_slice import build
from verify_open_slice import InvalidSlice, parsed_records, validate_lineage, verify


class VerifyOpenSliceTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name) / "open"
        build(self.root)

    def read(self, relative):
        return json.loads((self.root / relative).read_bytes())

    def write(self, relative, value):
        path = self.root / relative
        raw = json.dumps(value, ensure_ascii=False, sort_keys=True).encode("utf-8")
        path.write_bytes(raw)
        return hashlib.sha256(raw).hexdigest()

    def test_valid_slice_and_exact_input_set(self):
        self.assertEqual(verify(self.root)["status"], "verified")
        (self.root / "input" / "extra.txt").write_text("synthetic", encoding="utf-8")
        with self.assertRaisesRegex(InvalidSlice, "^input_file_set_mismatch$"):
            verify(self.root)

    def test_file_digest_detects_changed_input(self):
        path = self.root / "input" / "notes" / "note-0001.txt"
        path.write_bytes(path.read_bytes() + b" ")
        with self.assertRaisesRegex(InvalidSlice, "^input_digest_mismatch$"):
            verify(self.root)

    def test_nonfinite_json_is_rejected_after_rehash(self):
        path = self.root / "input" / "opd" / "visit-0003.json"
        value = json.loads(path.read_bytes())
        value["extra"] = float("nan")
        raw = json.dumps(value).encode("utf-8")
        path.write_bytes(raw)
        manifest = self.read("manifest.json")
        manifest["files"]["opd/visit-0003.json"] = hashlib.sha256(raw).hexdigest()
        self.write("manifest.json", manifest)
        with self.assertRaisesRegex(InvalidSlice, "^invalid_json$"):
            verify(self.root)

    def test_duplicate_manifest_key_is_rejected(self):
        manifest_path = self.root / "manifest.json"
        manifest = manifest_path.read_text(encoding="utf-8")
        manifest_path.write_text('{"schema":"robustness-v2-open-slice/1",' +
                                 manifest.lstrip()[1:], encoding="utf-8")
        with self.assertRaisesRegex(InvalidSlice, "^invalid_json$"):
            verify(self.root)

    def test_source_locator_checked_after_rehash(self):
        units = self.read("source_units.json")
        units[1]["locator"] = "row:0/observation"
        units[1]["label"] = "observation"
        digest = self.write("source_units.json", units)
        truth = self.read("truth/annotations.json")
        truth[1]["locator"] = units[1]["locator"]
        for item in truth:
            item["input_sha256"] = digest
        truth_digest = self.write("truth/annotations.json", truth)
        manifest = self.read("manifest.json")
        manifest["source_units_sha256"] = digest
        manifest["truth_sha256"] = truth_digest
        self.write("manifest.json", manifest)
        with self.assertRaisesRegex(InvalidSlice, "^source_value_mismatch$"):
            verify(self.root)

    def test_clinical_fact_original_coordinates_checked_after_rehash(self):
        truth = self.read("truth/annotations.json")
        truth[0]["clinical_facts"][0]["start"] += 1
        digest = self.write("truth/annotations.json", truth)
        manifest = self.read("manifest.json")
        manifest["truth_sha256"] = digest
        self.write("manifest.json", manifest)
        with self.assertRaisesRegex(InvalidSlice, "^invalid_clinical_fact$"):
            verify(self.root)

    def test_each_lineage_dimension_rejects_split_collision(self):
        original = self.read("manifest.json")["records"]
        fields = ("patient_group", "file_family", "template_family", "institution",
                  "near_duplicate_family", "renderer_family")
        for collision_field in fields:
            with self.subTest(field=collision_field):
                records = [dict(item) for item in original]
                records[2]["split"] = "validation"
                for field in fields:
                    records[2][field] = "independent-" + field
                records[2][collision_field] = records[0][collision_field]
                with self.assertRaisesRegex(InvalidSlice, "^split_collision$"):
                    validate_lineage(records)

    def test_duplicate_source_locator_is_rejected_after_rehash(self):
        units = self.read("source_units.json")
        units.append(dict(units[0], id="unit-duplicate"))
        input_digest = self.write("source_units.json", units)
        truth = self.read("truth/annotations.json")
        for annotation in truth:
            annotation["input_sha256"] = input_digest
        truth.append(dict(truth[0], id="unit-duplicate"))
        truth_digest = self.write("truth/annotations.json", truth)
        manifest = self.read("manifest.json")
        manifest["source_units_sha256"] = input_digest
        manifest["truth_sha256"] = truth_digest
        self.write("manifest.json", manifest)
        with self.assertRaisesRegex(InvalidSlice, "^duplicate_source_locator$"):
            verify(self.root)

    def test_structurally_invalid_csv_and_json_are_rejected(self):
        with self.assertRaisesRegex(InvalidSlice, "^invalid_csv$"):
            parsed_records(b'name,obs\nx,"y', "csv")
        with self.assertRaisesRegex(InvalidSlice, "^invalid_json$"):
            parsed_records(b'{"x": NaN}', "json")

    def test_fhir_bundle_cannot_be_mislabeled_plain_json(self):
        data = (self.root / "input/fhir/bundle-0005.json").read_bytes()
        self.assertIn("doc", parsed_records(data, "fhir"))
        with self.assertRaisesRegex(InvalidSlice, "^fhir_format_mismatch$"):
            parsed_records(data, "json")

    def test_tsv_rows_and_quoted_fields(self):
        rows = parsed_records(b'name\tobservation\nA\t"BP 120/80, pulse 72"\n'
                              b'B\t"dose\t500 mg"\n', "tsv")
        self.assertEqual(rows, {"row:0": {"name": "A", "observation": "BP 120/80, pulse 72"},
                                "row:1": {"name": "B", "observation": "dose\t500 mg"}})

    def test_invalid_tsv_structure(self):
        bad_tables = (b'name\tobs\nA\n', b'name\tname\nA\tB\n',
                      b'name\t\nA\tB\n', b'name\tobs\n',
                      b'name\tobs\nA\t"unterminated')
        for raw in bad_tables:
            with self.subTest(raw=raw), self.assertRaisesRegex(InvalidSlice, "^invalid_tsv$"):
                parsed_records(raw, "tsv")

    def test_tsv_file_mapping_and_field_source_label(self):
        csv_path = self.root / "input/registration/row-0002.csv"
        csv_path.unlink()
        tsv_path = self.root / "input/registration/row-0002.tsv"
        data = b'patient_name\tobservation\nLuvra Senq\tBP 118/76, pulse 72\n'
        tsv_path.write_bytes(data)
        manifest = self.read("manifest.json")
        del manifest["files"]["registration/row-0002.csv"]
        manifest["files"]["registration/row-0002.tsv"] = hashlib.sha256(data).hexdigest()
        manifest["records"][1]["file"] = "registration/row-0002.tsv"
        manifest["records"][1]["format"] = "tsv"
        self.write("manifest.json", manifest)
        self.assertEqual(verify(self.root)["status"], "verified")
        units = self.read("source_units.json")
        units[1]["label"] = "wrong_field"
        input_digest = self.write("source_units.json", units)
        truth = self.read("truth/annotations.json")
        for annotation in truth:
            annotation["input_sha256"] = input_digest
        truth_digest = self.write("truth/annotations.json", truth)
        manifest["source_units_sha256"] = input_digest
        manifest["truth_sha256"] = truth_digest
        self.write("manifest.json", manifest)
        with self.assertRaisesRegex(InvalidSlice, "^source_label_mismatch$"):
            verify(self.root)

    def test_source_label_must_match_parsed_field(self):
        units = self.read("source_units.json")
        units[1]["label"] = "patient_id"
        input_digest = self.write("source_units.json", units)
        truth = self.read("truth/annotations.json")
        for annotation in truth:
            annotation["input_sha256"] = input_digest
        truth_digest = self.write("truth/annotations.json", truth)
        manifest = self.read("manifest.json")
        manifest["source_units_sha256"] = input_digest
        manifest["truth_sha256"] = truth_digest
        self.write("manifest.json", manifest)
        with self.assertRaisesRegex(InvalidSlice, "^source_label_mismatch$"):
            verify(self.root)


if __name__ == "__main__":
    unittest.main()
