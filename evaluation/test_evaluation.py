import hashlib
import json
from pathlib import Path
import unittest

from evaluate import keyed, predict, score
from splits import split


class EvaluationTest(unittest.TestCase):
    def test_open_v2_example_keeps_roles_and_incomplete_join_explicit(self):
        fixture = Path(__file__).resolve().parents[1] / "docs/datasets/robustness_v2/open_example"
        raw = (fixture / "inputs.json").read_bytes()
        truth = keyed((fixture / "truth.json").read_bytes())
        snapshot = json.loads((fixture / "predictions.incomplete.json").read_bytes())
        item = json.loads(raw)[0]
        annotations = truth[item["id"]]
        text = item["text"]
        self.assertEqual(annotations["input_version"], item["input_version"])
        self.assertEqual(annotations["annotation_schema"], "robustness-v2-open-example-truth/1")
        self.assertEqual(predict(raw)["units"][item["id"]]["locator"], item["locator"])

        patient, clinician = annotations["occurrences"]
        self.assertEqual(text[patient["start"]:patient["end"]],
                         text[clinician["start"]:clinician["end"]])
        self.assertEqual(text[patient["start"]:patient["end"]], patient["surface"])
        self.assertEqual(text[clinician["start"]:clinician["end"]], clinician["surface"])
        self.assertEqual((patient["role"], clinician["role"]), ("patient", "clinician"))
        for fact in annotations["clinical_facts"]:
            self.assertEqual(text[fact["start"]:fact["end"]], fact["text"])
        edit = annotations["expected_edit"]
        released = text[:edit["start"]] + edit["replacement"] + text[edit["end"]:]
        self.assertIn(text[clinician["start"]:clinician["end"]], released)
        for fact in annotations["clinical_facts"]:
            self.assertIn(fact["text"], released)

        result = score(raw, truth, snapshot)
        strict = score(raw, truth, snapshot, strict_v2=True)
        self.assertEqual(strict["counts"], result["counts"])
        self.assertIsNone(strict["precision"])
        self.assertIsNone(strict["fpr"])
        self.assertEqual(strict["metric_support"]["adjudicated_units"], 0)
        self.assertEqual(result["counts"]["tp"], 1)
        self.assertEqual(result["counts"]["protected_overlaps"], 0)
        self.assertEqual(result["counts"]["incomplete_units"], 1)
        self.assertEqual(result["input_incomplete_units"], 1)
        snapshot["units"][item["id"]]["locator"] = "other"
        with self.assertRaisesRegex(ValueError, "invalid_unit_join"):
            score(raw, truth, snapshot)
        annotations["input_sha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "invalid_unit_join"):
            score(raw, truth, predict(raw))

    def test_strict_v2_requires_all_join_fields(self):
        raw = json.dumps([{"id": "a", "text": "No identifiers"}]).encode()
        truth = keyed(b'[{"id":"a","gold":[],"protect":[]}]')
        snapshot = predict(raw)
        self.assertEqual(score(raw, truth, snapshot)["labeled_units"], 1)
        with self.assertRaisesRegex(ValueError, "invalid_unit_join"):
            score(raw, truth, snapshot, strict_v2=True)

    def test_strict_v2_only_scores_adjudicated_negative_universe(self):
        raw = json.dumps([{"id": "a", "record_id": "r1", "locator": "doc",
                           "text": "BP 120/80"}]).encode()
        digest = hashlib.sha256(raw).hexdigest()
        truth = keyed(json.dumps([{"id": "a", "record_id": "r1", "locator": "doc",
                                  "input_sha256": digest, "gold": [], "protect": [[0, 9]],
                                  "annotation_status": "adjudicated",
                                  "negative_scope": "exhaustive"}]).encode())
        result = score(raw, truth, predict(raw), strict_v2=True)
        self.assertEqual(result["metric_support"], {"adjudicated_units": 1,
                                                    "exhaustive_negative_units": 1})
        self.assertEqual(result["fpr"], 0.0)
        truth["a"]["negative_scope"] = "partial"
        result = score(raw, truth, predict(raw), strict_v2=True)
        self.assertIsNone(result["fpr"])
        self.assertIsNone(result["accuracy"])

    def test_strict_does_not_count_unreviewed_predictions_as_false_positives(self):
        raw = json.dumps([{"id": "a", "record_id": "r1", "locator": "doc",
                           "text": "Mira and Alia"}]).encode()
        truth = keyed(json.dumps([{"id": "a", "record_id": "r1", "locator": "doc",
                                  "input_sha256": hashlib.sha256(raw).hexdigest(),
                                  "gold": [[0, 4, "NAME"]], "negative_scope": "partial",
                                  "annotation_status": "adjudicated"}]).encode())
        snapshot = predict(raw)
        snapshot["units"]["a"]["accepted"] = [[0, 4, "NAME"], [9, 13, "NAME"]]
        result = score(raw, truth, snapshot, strict_v2=True)
        self.assertIsNone(result["precision"])
        self.assertEqual(result["known_positive_recall"], 1.0)
        self.assertEqual(result["unjudged_exact_predictions"], 1)

    def test_exact_and_overlap_scores_separate_boundary_errors(self):
        raw = json.dumps([{"id": "a", "record_id": "r1", "locator": "doc",
                           "text": "abcdefghij"}]).encode()
        digest = hashlib.sha256(raw).hexdigest()
        truth = keyed(json.dumps([{"id": "a", "record_id": "r1", "locator": "doc",
                                  "input_sha256": digest, "gold": [[0, 4, "NAME"],
                                                                    [5, 9, "NAME"]],
                                  "protect": [], "annotation_status": "adjudicated",
                                  "negative_scope": "exhaustive"}]).encode())
        snapshot = predict(raw)
        snapshot["units"]["a"]["accepted"] = [[1, 5, "NAME"], [6, 9, "NAME"]]
        result = score(raw, truth, snapshot, strict_v2=True)
        self.assertEqual((result["counts"]["tp"], result["counts"]["fn_units"]), (0, 1))
        self.assertEqual(result["overlap_counts"], {"tp": 2, "fp": 0, "fn": 0})
        self.assertEqual(result["overlap_f1"], 1.0)
        self.assertEqual(result["accuracy"], 0.0)
        snapshot["units"]["a"]["status"] = "input_limit"
        result = score(raw, truth, snapshot, strict_v2=True)
        self.assertEqual(result["input_incomplete_units"], 1)
        self.assertEqual(result["metric_support"]["adjudicated_units"], 0)
        self.assertIsNone(result["overlap_f1"])

    def test_snapshot_joins_on_version_and_truth_is_optional_per_unit(self):
        units = json.dumps([{"id": "a", "text": "Name: Mira"},
                            {"id": "b", "text": "650 mg"},
                            {"id": "c", "text": "C/O uncertain"}]).encode()
        truth = keyed(b'[{"id":"a","gold":[[6,10,"NAME"]]},{"id":"b","gold":[]}]')
        snapshot = predict(units)
        self.assertNotIn("Mira", json.dumps(snapshot))
        result = score(units, truth, snapshot)
        self.assertEqual(result["counts"]["tp"], 1)
        self.assertEqual(result["counts"]["tn_units"], 1)
        self.assertEqual(result["labeled_units"], 2)
        snapshot["units"]["c"]["status"] = "input_limit"
        self.assertEqual(score(units, truth, snapshot)["input_incomplete_units"], 1)
        with self.assertRaisesRegex(ValueError, "input_version_mismatch"):
            score(units + b" ", truth, snapshot)

    def test_linked_lineage_keeps_entire_connected_component_together(self):
        lineage = [
            ("a", "p1", "f1", "t1"), ("b", "p1", "f2", "t2"),
            ("c", "p2", "f3", "t2"), ("d", "p3", "f4", "t3"),
        ]
        rows = [dict(zip(("id", "patient_group", "file_family", "template_family"), row))
                for row in lineage]
        raw = json.dumps(rows).encode()
        result = split(raw, "fixture", 50)
        self.assertEqual(result, split(raw, "fixture", 50))
        self.assertTrue({"a", "b", "c"} <= set(result["development_ids"])
                        or {"a", "b", "c"} <= set(result["holdout_ids"]))
        with self.assertRaisesRegex(ValueError, "need_independent"):
            split(json.dumps(rows[:-1]).encode(), "fixture", 50)

    def test_split_rejects_institution_and_near_duplicate_crossing(self):
        rows = [
            {"id": "a", "patient_group": "p1", "file_family": "f1",
             "template_family": "t1", "institution": "hospital-a",
             "near_duplicate_family": "copy-a"},
            {"id": "b", "patient_group": "p2", "file_family": "f2",
             "template_family": "t2", "institution": "hospital-a",
             "near_duplicate_family": "copy-b"},
            {"id": "c", "patient_group": "p3", "file_family": "f3",
             "template_family": "t3", "institution": "hospital-c",
             "near_duplicate_family": "copy-a"},
        ]
        with self.assertRaisesRegex(ValueError, "need_independent"):
            split(json.dumps(rows).encode(), "fixture", 50)
