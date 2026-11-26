"""Validate aggregate Version 2 record allocation without exposing record data."""

import argparse
from collections import Counter
import json
from pathlib import Path
import sys


SPLITS = frozenset({"development", "validation", "sealed"})
FORMATS = frozenset({"csv", "tsv", "json", "fhir", "text"})
LINEAGE_FIELDS = (
    "patient_group",
    "file_family",
    "template_family",
    "institution",
    "near_duplicate_family",
    "renderer_family",
)
TARGET_QUOTAS = {
    "development": {"csv": 200, "tsv": 150, "json": 200, "fhir": 200, "text": 250},
    "validation": {"csv": 80, "tsv": 60, "json": 80, "fhir": 80, "text": 100},
    "sealed": {"csv": 120, "tsv": 90, "json": 120, "fhir": 120, "text": 150},
}


def validate_allocation(records, quotas):
    """Return only split/format counts after checking exact quotas and lineage.

    ``records`` is a list of manifest-like Patient Record dictionaries. ``quotas``
    must supply an integer target, including zero targets, for every split/format
    combination. Metadata-only and malformed-input fixtures belong elsewhere.
    """
    if not isinstance(records, list) or not isinstance(quotas, dict) or set(quotas) != SPLITS:
        raise ValueError("invalid_allocation")
    for split in SPLITS:
        targets = quotas[split]
        if not isinstance(targets, dict) or set(targets) != FORMATS:
            raise ValueError("invalid_quota")
        if any(type(value) is not int or value < 0 for value in targets.values()):
            raise ValueError("invalid_quota")

    ids = set()
    locations = set()
    lineage_splits = {}
    counts = Counter()
    for record in records:
        if not isinstance(record, dict):
            raise ValueError("invalid_record")
        identifier = record.get("id")
        filename = record.get("file")
        locator = record.get("locator")
        if any(not isinstance(value, str) or not value for value in
               (identifier, filename, locator)):
            raise ValueError("invalid_record")
        if identifier in ids:
            raise ValueError("duplicate_record_id")
        ids.add(identifier)
        location = (filename, locator)
        if location in locations:
            raise ValueError("duplicate_record_location")
        locations.add(location)
        split = record.get("split")
        format_name = record.get("format")
        if not isinstance(split, str) or not isinstance(format_name, str) or \
                split not in SPLITS or format_name not in FORMATS:
            raise ValueError("invalid_split_or_format")
        counts[(split, format_name)] += 1
        for field in LINEAGE_FIELDS:
            value = record.get(field)
            if not isinstance(value, str) or not value:
                raise ValueError("missing_lineage")
            key = (field, value)
            previous = lineage_splits.setdefault(key, split)
            if previous != split:
                raise ValueError("split_collision")

    if any(counts[(split, format_name)] != quotas[split][format_name]
           for split in SPLITS for format_name in FORMATS):
        raise ValueError("quota_mismatch")
    return {
        "total_records": len(records),
        "counts": {split: {format_name: counts[(split, format_name)]
                           for format_name in sorted(FORMATS)}
                   for split in sorted(SPLITS)},
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    args = parser.parse_args()
    try:
        manifest = json.loads(args.manifest.read_bytes())
        result = validate_allocation(manifest["records"], TARGET_QUOTAS)
    except (OSError, UnicodeError, ValueError, KeyError, TypeError):
        print("invalid_v2_allocation", file=sys.stderr)
        return 1
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
