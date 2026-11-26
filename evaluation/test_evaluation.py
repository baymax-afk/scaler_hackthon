import json
import unittest

from evaluate import keyed, predict, score
from splits import split


class EvaluationTest(unittest.TestCase):
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
