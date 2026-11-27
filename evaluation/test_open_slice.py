import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest

from docs.datasets.robustness_v2.build_open_slice import build
from docs.datasets.robustness_v2.verify_open_slice import validate_lineage, verify
from evaluation.evaluate import open_slice_audit


class OpenSliceTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = TemporaryDirectory()
        cls.original = Path(cls.temporary.name) / "generated"
        build(cls.original)

    @classmethod
    def tearDownClass(cls):
        cls.temporary.cleanup()

    def copy_slice(self):
        temporary = TemporaryDirectory()
        root = Path(temporary.name) / "slice"
        shutil.copytree(self.original, root)
        self.addCleanup(temporary.cleanup)
        return root

    def test_generated_slice_has_matching_manifest_and_source_spans(self):
        result = verify(self.original)
        self.assertEqual((result["files"], result["records"], result["units"]), (5, 5, 11))
        self.assertEqual((result["split"], result["status"]), ("development", "verified"))

    def test_release_audit_counts_clinical_facts_over_all_input(self):
        with TemporaryDirectory() as temporary:
            release = Path(temporary) / "release"
            root = Path(__file__).resolve().parents[1]
            subprocess.run([sys.executable, str(root / "submission/main.py"),
                            "--input", str(self.original / "input"), "--output", str(release)],
                           env={**os.environ, "RAKSHA_SECRET": "practice"},
                           check=True, capture_output=True, text=True)
            result = open_slice_audit(self.original, release)
            self.assertEqual((result["input_files"], result["sanitized_files"],
                              result["input_clinical_facts"], result["preserved_clinical_facts"]),
                             (5, 4, 7, 6))
            self.assertEqual(result["linkage_diagnostic"]["false_merged_clusters"], 0)
            manifest = json.loads((self.original / "manifest.json").read_bytes())
            report_path = release / "report.json"
            report = json.loads(report_path.read_bytes())
            duplicate = json.loads(report_path.read_bytes())
            sanitized_entries = [item for item in duplicate["files"]
                                 if item["status"] == "sanitized"]
            sanitized_entries[1]["output"] = sanitized_entries[0]["output"]
            report_path.write_text(json.dumps(duplicate))
            with self.assertRaisesRegex(ValueError, "invalid_release_ledger"):
                open_slice_audit(self.original, release)
            report_path.write_text(json.dumps(report))
            fingerprint = manifest["files"]["registration/row-0002.csv"]
            output = next(item["output"] for item in report["files"]
                          if item["input_sha256"] == fingerprint)
            target = release / output
            target.write_text(target.read_text().replace("BP 118/76, pulse 72", "BP 118/76"))
            self.assertEqual(open_slice_audit(self.original, release)["preserved_clinical_facts"], 5)
            (release / "sanitized" / "unreported.txt").write_text("synthetic", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "invalid_release_ledger"):
                open_slice_audit(self.original, release)

    def test_release_audit_requires_safe_paths_and_complete_record_index(self):
        with TemporaryDirectory() as temporary:
            release = Path(temporary) / "release"
            root = Path(__file__).resolve().parents[1]
            subprocess.run([sys.executable, str(root / "submission/main.py"),
                            "--input", str(self.original / "input"), "--output", str(release)],
                           env={**os.environ, "RAKSHA_SECRET": "practice"},
                           check=True, capture_output=True, text=True)
            report_path = release / "report.json"
            original_report = report_path.read_bytes()
            report = json.loads(original_report)
            entry = next(item for item in report["files"] if item["status"] == "sanitized")
            entry["output"] = "sanitized/../renamed.txt"
            report_path.write_text(json.dumps(report), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "invalid_release_path"):
                open_slice_audit(self.original, release)
            report_path.write_bytes(original_report)
            index_path = release / "records.jsonl"
            index_path.write_text("\n".join(index_path.read_text().splitlines()[1:]) + "\n",
                                  encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "invalid_record_index"):
                open_slice_audit(self.original, release)

    def test_release_audit_flags_cross_patient_pseudonym_cluster(self):
        with TemporaryDirectory() as temporary:
            release = Path(temporary) / "release"
            root = Path(__file__).resolve().parents[1]
            subprocess.run([sys.executable, str(root / "submission/main.py"),
                            "--input", str(self.original / "input"), "--output", str(release)],
                           env={**os.environ, "RAKSHA_SECRET": "practice"},
                           check=True, capture_output=True, text=True)
            token = "PSN-SYNTHETIC-COLLISION"
            manifest = json.loads((self.original / "manifest.json").read_bytes())
            report = json.loads((release / "report.json").read_bytes())
            by_hash = {item["input_sha256"]: item["output"] for item in report["files"]}
            def published(original):
                return release / by_hash[manifest["files"][original]]
            note = published("notes/note-0001.txt")
            note.write_text(note.read_text(encoding="utf-8").rstrip("\n") +
                            " " + token + "\n", encoding="utf-8")
            table = published("registration/row-0002.csv")
            table.write_text(table.read_text(encoding="utf-8").replace(
                "pulse 72", "pulse 72 " + token), encoding="utf-8")
            index_path = release / "records.jsonl"
            entries = [json.loads(line) for line in index_path.read_text(encoding="utf-8").splitlines()]
            for entry in entries:
                if entry["file"] in {str(note.relative_to(release)), str(table.relative_to(release))}:
                    entry["patient"] = token
            index_path.write_text("".join(json.dumps(item) + "\n" for item in entries),
                                  encoding="utf-8")
            self.assertEqual(open_slice_audit(self.original, release)
                             ["linkage_diagnostic"]["false_merged_clusters"], 1)

    def test_file_hash_tampering_is_rejected(self):
        root = self.copy_slice()
        path = root / "input/notes/note-0001.txt"
        path.write_bytes(path.read_bytes() + b"x")
        with self.assertRaisesRegex(ValueError, "input_digest_mismatch"):
            verify(root)

    def test_invalid_code_point_span_is_rejected_after_hash_update(self):
        root = self.copy_slice()
        truth_path = root / "truth/annotations.json"
        truth = json.loads(truth_path.read_bytes())
        truth[0]["gold"][0][1] = 1000
        data = (json.dumps(truth, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode()
        truth_path.write_bytes(data)
        manifest_path = root / "manifest.json"
        manifest = json.loads(manifest_path.read_bytes())
        manifest["truth_sha256"] = hashlib.sha256(data).hexdigest()
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "invalid_span"):
            verify(root)

    def test_source_unit_must_equal_parsed_file_value(self):
        root = self.copy_slice()
        units_path = root / "source_units.json"
        units = json.loads(units_path.read_bytes())
        units[1]["text"] += "x"
        units_data = json.dumps(units, ensure_ascii=False).encode()
        units_path.write_bytes(units_data)
        truth_path = root / "truth/annotations.json"
        truth = json.loads(truth_path.read_bytes())
        for annotation in truth:
            annotation["input_sha256"] = hashlib.sha256(units_data).hexdigest()
        truth_data = json.dumps(truth, ensure_ascii=False).encode()
        truth_path.write_bytes(truth_data)
        manifest_path = root / "manifest.json"
        manifest = json.loads(manifest_path.read_bytes())
        manifest["source_units_sha256"] = hashlib.sha256(units_data).hexdigest()
        manifest["truth_sha256"] = hashlib.sha256(truth_data).hexdigest()
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "source_value_mismatch"):
            verify(root)

    def test_wrong_occurrence_surface_is_rejected(self):
        root = self.copy_slice()
        truth_path = root / "truth/annotations.json"
        truth = json.loads(truth_path.read_bytes())
        truth[0]["occurrences"][0]["surface"] = "wrong surface"
        truth_data = json.dumps(truth, ensure_ascii=False).encode()
        truth_path.write_bytes(truth_data)
        manifest_path = root / "manifest.json"
        manifest = json.loads(manifest_path.read_bytes())
        manifest["truth_sha256"] = hashlib.sha256(truth_data).hexdigest()
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "occurrence_surface_mismatch"):
            verify(root)

    def test_extra_gold_span_requires_its_own_occurrence(self):
        root = self.copy_slice()
        truth_path = root / "truth/annotations.json"
        truth = json.loads(truth_path.read_bytes())
        truth[0]["gold"].append([7, 17, "NAME"])
        truth_data = json.dumps(truth, ensure_ascii=False).encode()
        truth_path.write_bytes(truth_data)
        manifest_path = root / "manifest.json"
        manifest = json.loads(manifest_path.read_bytes())
        manifest["truth_sha256"] = hashlib.sha256(truth_data).hexdigest()
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "gold_occurrence_mismatch"):
            verify(root)

    def test_lineage_collision_across_assigned_splits_is_rejected(self):
        records = json.loads((self.original / "manifest.json").read_bytes())["records"]
        collision = dict(records[0], id="record-collision", split="validation")
        with self.assertRaisesRegex(ValueError, "split_collision"):
            validate_lineage(records + [collision])

    def test_open_slice_rejects_sealed_split(self):
        root = self.copy_slice()
        manifest_path = root / "manifest.json"
        manifest = json.loads(manifest_path.read_bytes())
        manifest["split"] = "sealed"
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "invalid_manifest"):
            verify(root)


if __name__ == "__main__":
    unittest.main()
