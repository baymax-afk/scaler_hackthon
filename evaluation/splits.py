"""Freeze grouped development and evaluation units from a labeled lineage manifest."""
import argparse
from collections import defaultdict
import hashlib
import json
from pathlib import Path

GROUP_FIELDS = ("patient_group", "file_family", "template_family")


def split(raw, seed, holdout_percent):
    if not 0 < holdout_percent < 100:
        raise ValueError("invalid_holdout_percent")
    records = json.loads(raw)
    identifiers = [record["id"] for record in records]
    if len(set(identifiers)) != len(identifiers):
        raise ValueError("duplicate_unit_id")
    parents = list(range(len(records)))
    seen_groups = {}

    def root(index):
        while index != parents[index]:
            parents[index] = parents[parents[index]]
            index = parents[index]
        return index

    for index, record in enumerate(records):
        for field in GROUP_FIELDS:
            if field not in record:
                raise ValueError("missing_lineage")
            value = record[field]
            if not value:
                if field == "patient_group" and record.get("channel") in {"filename", "header", "key", "metadata"}:
                    continue
                raise ValueError("missing_lineage")
            group = field, value
            other = seen_groups.setdefault(group, index)
            parents[root(index)] = root(other)

    groups = defaultdict(list)
    for index, identifier in enumerate(identifiers):
        groups[root(index)].append(identifier)
    if len(groups) < 2:
        raise ValueError("need_independent_patient_file_and_template_groups")

    def group_rank(group):
        key = json.dumps([seed, sorted(group)], separators=(",", ":")).encode()
        return hashlib.sha256(key).digest()

    ordered = sorted(groups.values(), key=group_rank)
    target = len(records) * holdout_percent / 100
    holdout = []
    remaining = 0
    for index, group in enumerate(ordered[:-1]):
        if holdout and abs(len(holdout) - target) <= abs(len(holdout) + len(group) - target):
            break
        holdout.extend(group)
        remaining = index + 1
    development = [key for group in ordered[remaining:] for key in group]
    return {
        "schema": "phase-a-split/1",
        "lineage_sha256": hashlib.sha256(raw).hexdigest(),
        "seed": seed, "independent_groups": len(groups),
        "development_ids": sorted(development), "holdout_ids": sorted(holdout),
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("lineage", type=Path)
    parser.add_argument("--seed", required=True)
    parser.add_argument("--holdout-percent", type=int, default=25)
    args = parser.parse_args()
    print(json.dumps(split(args.lineage.read_bytes(), args.seed, args.holdout_percent), indent=2, sort_keys=True))
