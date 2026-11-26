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
            units = json.dumps(list(benchmark.source_units(folder))).encode()
            snapshot = {"schema": "phase-a-predictions/1", "input_sha256": sha256(units).hexdigest(),
                        "units": {"a/0": {"status": "input_limit", "accepted": [], "review": []}}}
            result = benchmark.score_spans(folder, units, snapshot)
            self.assertEqual(result["counts"]["incomplete_units"], 1)
            self.assertEqual(result["by_category"]["NAME"]["exact_hits"], 0)
            self.assertEqual(result["by_category"]["NAME"]["incomplete"], 1)
            self.assertNotIn("precision", result)
            with self.assertRaisesRegex(ValueError, "prediction_input_digest"):
                benchmark.score_spans(folder, units + b" ", snapshot)
