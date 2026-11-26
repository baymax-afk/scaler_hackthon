import unittest

from linkage import score_linkage


RECORDS = [
    {"id": "a", "patient_group": "patient-1"},
    {"id": "b", "patient_group": "patient-1"},
    {"id": "c", "patient_group": "patient-2"},
]


def pair(left, right, same_patient, *, eligible=True, annotation_status="adjudicated"):
    return {"left": left, "right": right, "same_patient": same_patient,
            "eligible": eligible, "annotation_status": annotation_status}


class LinkageTest(unittest.TestCase):
    def test_positive_and_negative_pairs(self):
        result = score_linkage(RECORDS, {"a": "token-1", "b": "token-1", "c": "token-2"},
                               [pair("a", "b", True), pair("a", "c", False),
                                pair("b", "c", False)])
        self.assertEqual((result["counts"]["tp"], result["counts"]["tn"]), (1, 2))
        self.assertEqual((result["precision"], result["recall"], result["f0_5"]),
                         (1.0, 1.0, 1.0))
        self.assertEqual(result["false_merged_clusters"], 0)
        self.assertEqual(result["predicted_clusters"], 2)
        self.assertEqual(result["b_cubed_diagnostic"], {"precision": 1.0, "recall": 1.0})
        self.assertNotIn("token-1", str(result))

    def test_false_merge_and_missed_link(self):
        result = score_linkage(RECORDS, {"a": "token-x", "b": "token-y", "c": "token-x"},
                               [pair("a", "b", True), pair("a", "c", False)])
        self.assertEqual((result["counts"]["fp"], result["counts"]["fn"]), (1, 1))
        self.assertEqual(result["false_merged_clusters"], 1)
        self.assertEqual((result["precision"], result["recall"], result["f0_5"]),
                         (0.0, 0.0, 0.0))
        self.assertAlmostEqual(result["b_cubed_diagnostic"]["precision"], 2 / 3)
        self.assertAlmostEqual(result["b_cubed_diagnostic"]["recall"], 2 / 3)

    def test_unpaired_false_merge_is_diagnostic(self):
        result = score_linkage(RECORDS, {"a": "same", "b": None, "c": "same"}, [])
        self.assertEqual(result["false_merged_clusters"], 1)
        self.assertEqual(result["abstained_records"], 1)
        self.assertEqual(result["counts"]["scored_pairs"], 0)
        self.assertIsNone(result["precision"])
        self.assertIsNone(result["recall"])
        self.assertIsNone(result["f0_5"])

    def test_negative_only_pairs_leave_recall_and_f_score_undefined(self):
        result = score_linkage(RECORDS, {"a": "shared", "b": None, "c": "shared"},
                               [pair("a", "c", False)])
        self.assertEqual(result["counts"]["fp"], 1)
        self.assertEqual(result["precision"], 0.0)
        self.assertIsNone(result["recall"])
        self.assertIsNone(result["f0_5"])

    def test_abstention_and_partial_or_ineligible_truth_excluded(self):
        result = score_linkage(RECORDS, {"a": "token-a", "b": None, "c": "token-c"},
                               [pair("a", "b", True),
                                pair("a", "c", False, annotation_status="partial"),
                                pair("b", "c", False, eligible=False)])
        self.assertEqual(result["counts"]["abstained_eligible_pairs"], 1)
        self.assertEqual(result["counts"]["abstained_positive_pairs"], 1)
        self.assertEqual(result["counts"]["fn"], 1)
        self.assertEqual(result["counts"]["partial_pairs"], 1)
        self.assertEqual(result["counts"]["ineligible_pairs"], 1)
        self.assertEqual(result["counts"]["scored_pairs"], 0)
        self.assertIsNone(result["precision"])
        self.assertEqual(result["recall"], 0.0)
        self.assertEqual(result["f0_5"], 0.0)

    def test_negative_abstention_does_not_raise_false_positive(self):
        result = score_linkage(RECORDS, {"a": "one", "b": "one", "c": None},
                               [pair("a", "b", True), pair("a", "c", False)])
        self.assertEqual(result["counts"]["abstained_negative_pairs"], 1)
        self.assertEqual(result["counts"]["fp"], 0)
        self.assertEqual(result["recall"], 1.0)

    def test_ineligible_positive_pair_is_permitted_but_excluded(self):
        result = score_linkage(RECORDS, {"a": "one", "b": "two", "c": None},
                               [pair("a", "b", True, eligible=False)])
        self.assertEqual(result["counts"]["ineligible_pairs"], 1)
        self.assertEqual(result["counts"]["fn"], 0)

    def test_rejects_invalid_record_or_prediction_join(self):
        with self.assertRaisesRegex(ValueError, "duplicate_record_id"):
            score_linkage(RECORDS + [dict(RECORDS[0])], {"a": None, "b": None, "c": None}, [])
        for predictions in ({"a": None, "b": None},
                            {"a": None, "b": None, "c": None, "d": None}):
            with self.assertRaisesRegex(ValueError, "invalid_prediction_join"):
                score_linkage(RECORDS, predictions, [])
        with self.assertRaisesRegex(ValueError, "invalid_patient_pseudonym"):
            score_linkage(RECORDS, {"a": "", "b": None, "c": None}, [])

    def test_rejects_bad_pairs_and_conflicting_truth(self):
        predictions = {"a": None, "b": None, "c": None}
        with self.assertRaisesRegex(ValueError, "duplicate_pair_label"):
            score_linkage(RECORDS, predictions,
                          [pair("a", "b", True), pair("b", "a", True)])
        with self.assertRaisesRegex(ValueError, "invalid_pair_join"):
            score_linkage(RECORDS, predictions, [pair("a", "missing", False)])
        with self.assertRaisesRegex(ValueError, "invalid_pair_join"):
            score_linkage(RECORDS, predictions, [pair("a", "a", True)])
        with self.assertRaisesRegex(ValueError, "inconsistent_patient_group_truth"):
            score_linkage(RECORDS, predictions, [pair("a", "c", True)])


if __name__ == "__main__":
    unittest.main()
