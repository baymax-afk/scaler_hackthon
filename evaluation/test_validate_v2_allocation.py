"""Synthetic-only checks for exact three-way Version 2 allocation."""

import unittest

from validate_v2_allocation import (FORMATS, LINEAGE_FIELDS, SPLITS, TARGET_QUOTAS,
                                    validate_allocation)


def quotas():
    result = {split: {format_name: 0 for format_name in FORMATS} for split in SPLITS}
    result["development"]["text"] = 1
    result["validation"]["csv"] = 1
    result["sealed"]["fhir"] = 1
    return result


def records():
    result = []
    for index, (split, format_name) in enumerate(
            (("development", "text"), ("validation", "csv"), ("sealed", "fhir"))):
        record = {"id": f"record-{index}", "file": f"file-{index}",
                  "locator": "doc", "split": split, "format": format_name}
        record.update({field: f"{field}-{index}" for field in LINEAGE_FIELDS})
        result.append(record)
    return result


class ValidateV2AllocationTest(unittest.TestCase):
    def test_target_quotas_match_handoff(self):
        self.assertEqual({split: sum(targets.values()) for split, targets in
                          TARGET_QUOTAS.items()},
                         {"development": 1000, "validation": 400, "sealed": 600})
        self.assertEqual({format_name: sum(targets[format_name] for targets in
                                       TARGET_QUOTAS.values()) for format_name in FORMATS},
                         {"csv": 400, "tsv": 300, "json": 400, "fhir": 400, "text": 500})

    def test_valid_exact_allocation_returns_only_aggregates(self):
        result = validate_allocation(records(), quotas())
        self.assertEqual(result["total_records"], 3)
        self.assertEqual(result["counts"], quotas())
        self.assertNotIn("record-", repr(result))
        self.assertNotIn("file-", repr(result))

    def test_count_mismatch_and_extra_record_are_rejected(self):
        target = quotas()
        target["development"]["text"] = 2
        with self.assertRaisesRegex(ValueError, "quota_mismatch"):
            validate_allocation(records(), target)
        extra = records()
        extra.append(dict(extra[0], id="extra", file="extra-file",
                          patient_group="extra-patient"))
        with self.assertRaisesRegex(ValueError, "quota_mismatch"):
            validate_allocation(extra, quotas())

    def test_every_lineage_field_blocks_cross_split_collision(self):
        for field in LINEAGE_FIELDS:
            with self.subTest(field=field):
                sample = records()
                sample[1][field] = sample[0][field]
                with self.assertRaisesRegex(ValueError, "split_collision"):
                    validate_allocation(sample, quotas())

    def test_missing_lineage_is_rejected(self):
        for field in LINEAGE_FIELDS:
            with self.subTest(field=field):
                sample = records()
                del sample[0][field]
                with self.assertRaisesRegex(ValueError, "missing_lineage"):
                    validate_allocation(sample, quotas())

    def test_duplicate_ids_and_file_locators_are_rejected(self):
        sample = records()
        sample[1]["id"] = sample[0]["id"]
        with self.assertRaisesRegex(ValueError, "duplicate_record_id"):
            validate_allocation(sample, quotas())
        sample = records()
        sample[1]["file"] = sample[0]["file"]
        with self.assertRaisesRegex(ValueError, "duplicate_record_location"):
            validate_allocation(sample, quotas())

    def test_unsupported_format_and_split_are_rejected(self):
        for field, value in (("format", "xml"), ("split", "holdout")):
            with self.subTest(field=field):
                sample = records()
                sample[0][field] = value
                with self.assertRaisesRegex(ValueError, "invalid_split_or_format"):
                    validate_allocation(sample, quotas())

    def test_quota_axes_and_values_must_be_exact(self):
        target = quotas()
        del target["sealed"]
        with self.assertRaisesRegex(ValueError, "invalid_allocation"):
            validate_allocation(records(), target)
        target = quotas()
        del target["sealed"]["tsv"]
        with self.assertRaisesRegex(ValueError, "invalid_quota"):
            validate_allocation(records(), target)
        target = quotas()
        target["sealed"]["tsv"] = True
        with self.assertRaisesRegex(ValueError, "invalid_quota"):
            validate_allocation(records(), target)
        target = quotas()
        target["sealed"]["tsv"] = -1
        with self.assertRaisesRegex(ValueError, "invalid_quota"):
            validate_allocation(records(), target)


if __name__ == "__main__":
    unittest.main()
