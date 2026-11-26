from hashlib import sha256
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

import robustness_v2 as benchmark
from generate import dump, generate, SEED


class OpenCorpusTest(unittest.TestCase):
    def test_reproducible_counts_and_split_collision(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            first, second = root / "first", root / "second"
            generate(first, SEED)
            generate(second, SEED)
            result = benchmark.validate(first)["open_splits"]
            self.assertEqual(result["development"]["records"], 1000)
            self.assertEqual(result["validation"]["records"], 400)
            self.assertEqual(result, benchmark.validate(second)["open_splits"])
            validation = second / "validation"
            development = benchmark.read_json(second / "development" / "truth.json")
            manifest, records = benchmark.load_split(validation)
            records[0]["patient_group"] = development[0]["patient_group"]
            dump(validation / "truth.json", records)
            manifest["truth_sha256"] = benchmark.digest(validation / "truth.json")
            dump(validation / "manifest.json", manifest)
            with self.assertRaisesRegex(ValueError, "split_collision"):
                benchmark.validate(second)

    def test_source_inventory_is_independent_of_truth_and_includes_background(self):
        with TemporaryDirectory() as directory:
            folder = Path(directory)
            source = folder / "input"
            source.mkdir()
            (source / "one.csv").write_text("Clerk Code,Dose\nnot a patient,5 mg\n")
            before = list(benchmark.source_units(folder))
            dump(folder / "truth.json", [{"file": "one.csv", "units": [{"label": "patient name"}]}])
            self.assertEqual(list(benchmark.source_units(folder)), before)
            self.assertTrue(any(unit["text"] == "5 mg" and unit["label"] == "Dose" for unit in before))
            self.assertTrue(any(unit["text"] == "Clerk Code" and unit["channel"] == "header" for unit in before))

    def test_release_audit_localizes_identical_surfaces_by_occurrence(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            dataset, release = root / "dataset", root / "release"
            (dataset / "input").mkdir(parents=True)
            (release / "sanitized").mkdir(parents=True)
            original = "Dr. Mira spoke. S/o Mira"
            (dataset / "input" / "note.txt").write_text(original)
            digest = sha256(original.encode()).hexdigest()
            dump(dataset / "manifest.json", {"files": {"note.txt": digest}})
            dump(dataset / "truth.json", [{"file": "note.txt", "loc": "doc", "format": "txt",
                "patient_group": "fixture", "units": [{"location": "doc", "representation": "text",
                    "spans": [{"start": 4, "end": 8, "surface": "Mira", "kind": "PROTECT"},
                              {"start": 20, "end": 24, "surface": "Mira", "kind": "RELATIVE"}]}]}])
            dump(release / "report.json", {"files": [{"input_sha256": digest,
                "output": "sanitized/note.txt", "status": "sanitized"}]})
            (release / "records.jsonl").write_text("")
            note = release / "sanitized" / "note.txt"
            note.write_text("Dr. [NAME] spoke. S/o Mira")
            result = benchmark.audit(dataset, release)["by_format"]["txt"]
            self.assertEqual(result["protected_preserved"], 0)
            self.assertEqual(result["literal_residuals"], 1)
            note.write_text("Dr. Mira spoke. S/o [NAME]")
            result = benchmark.audit(dataset, release)["by_format"]["txt"]
            self.assertEqual(result["protected_preserved"], 1)
            self.assertEqual(result["identifier_transformed"], 1)
            (release / "sanitized" / "unreported.txt").write_text("fixture")
            with self.assertRaisesRegex(ValueError, "unreported_release_artifact"):
                benchmark.audit(dataset, release)

    def test_indistinguishable_duplicates_remain_unresolved(self):
        from evaluation.release_evidence import OccurrenceAlignment
        alignment = OccurrenceAlignment("Mira Mira", "Mira")
        self.assertEqual(alignment.outcome(0, 4), "unresolved")
        self.assertEqual(alignment.outcome(5, 9), "unresolved")

    def test_index_uses_longest_locator_without_counting_covering_entry_as_exact(self):
        file = "sanitized/a.json"
        parent = {"file": file, "loc": "/visits/1", "out": "/kept/2", "patient": "SYN"}
        fallback = {"file": file, "loc": "doc", "patient": None}
        index = {(file, parent["loc"]): parent, (file, "doc"): fallback}
        self.assertEqual(benchmark.matching_index_entry(index, file, "/visits/1/0"),
                         (parent, "/kept/2/0"))
        self.assertEqual(benchmark.matching_index_entry(index, file, "/visits/10"),
                         (fallback, "/visits/10"))

    def test_one_broad_prediction_cannot_match_two_occurrences(self):
        with TemporaryDirectory() as directory:
            folder = Path(directory)
            (folder / "input").mkdir()
            (folder / "input" / "note.txt").write_text("Ab Cd")
            dump(folder / "manifest.json", {})
            dump(folder / "truth.json", [{
                "file": "note.txt", "loc": "doc", "format": "txt",
                "units": [{"location": "doc", "spans": [
                    {"start": 0, "end": 2, "surface": "Ab", "kind": "NAME"},
                    {"start": 3, "end": 5, "surface": "Cd", "kind": "NAME"},
                ]}],
            }])
            units = list(benchmark.source_units(folder))
            raw = json.dumps(units).encode()
            predictions = {"schema": "phase-a-predictions/1", "input_sha256": sha256(raw).hexdigest(),
                           "units": {unit["id"]: {"status": "complete", "review": [],
                                                  "accepted": [[0, 5, "NAME"]] if unit["channel"] == "content" else []}
                                     for unit in units}}
            result = benchmark.score_spans(folder, raw, predictions)["by_category"]["NAME"]
            self.assertEqual(result["exact_hits"], 0)
            self.assertEqual(result["overlap_hits"], 1)

    def test_incomplete_predictions_are_counted_without_accuracy_or_precision(self):
        with TemporaryDirectory() as directory:
            folder = Path(directory)
            source = folder / "input" / "note.txt"
            source.parent.mkdir()
            source.write_text("Patient: Alira. Pulse: 74.", encoding="utf-8")
            dump(folder / "manifest.json", {})
            dump(folder / "truth.json", [{
                "id": "a", "file": "note.txt", "format": "txt", "loc": "doc",
                "units": [{"location": "doc", "representation": "text", "label": "", "spans": [
                    {"kind": "NAME", "surface": "Alira", "start": 9, "end": 14},
                    {"kind": "PROTECT", "surface": "74", "start": 23, "end": 25},
                ]}],
            }])
            inventory = list(benchmark.source_units(folder))
            units = json.dumps(inventory).encode()
            snapshot = {"schema": "phase-a-predictions/1", "input_sha256": sha256(units).hexdigest(),
                        "units": {unit["id"]: {"status": "input_limit" if unit["text"].startswith("Patient:")
                                              else "complete", "accepted": [], "review": []}
                                  for unit in inventory}}
            result = benchmark.score_spans(folder, units, snapshot)
            self.assertEqual(result["counts"]["incomplete_units"], 1)
            self.assertEqual(result["by_category"]["NAME"]["exact_hits"], 0)
            self.assertEqual(result["by_category"]["NAME"]["incomplete"], 1)
            self.assertNotIn("precision", result)
            with self.assertRaisesRegex(ValueError, "prediction_input_digest"):
                benchmark.score_spans(folder, units + b" ", snapshot)
