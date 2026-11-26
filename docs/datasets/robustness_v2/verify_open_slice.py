"""Verify the small, development-only Version 2 corpus without printing source data."""

import argparse
import csv
import hashlib
from io import StringIO
import json
from pathlib import Path
import sys

try:
    from .fhir_smoke import check_fhir_bundle
except ImportError:
    from fhir_smoke import check_fhir_bundle


class InvalidSlice(ValueError):
    """A safe, stable validation error code."""


def require(condition, code):
    if not condition:
        raise InvalidSlice(code)


def read_json(path):
    try:
        return json.loads(path.read_bytes(), parse_constant=reject_constant,
                          object_pairs_hook=unique_object)
    except (OSError, UnicodeError, ValueError) as exc:
        raise InvalidSlice("invalid_json") from exc


def reject_constant(_value):
    raise ValueError("nonfinite_json")


def unique_object(pairs):
    result = dict(pairs)
    if len(result) != len(pairs):
        raise ValueError("duplicate_json_key")
    return result


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def relative_path(value):
    require(isinstance(value, str) and value, "invalid_file_path")
    path = Path(value)
    require(not path.is_absolute() and all(part not in {"", ".", ".."} for part in path.parts)
            and path.as_posix() == value, "invalid_file_path")
    return path


def keyed(items, code):
    require(isinstance(items, list) and all(isinstance(item, dict) and
            isinstance(item.get("id"), str) and item["id"] for item in items), code)
    result = {item["id"]: item for item in items}
    require(len(result) == len(items), code)
    return result


def validate_lineage(records):
    """Reject a split that shares a patient, source family, or institution."""
    seen = {}
    for record in records:
        require(isinstance(record, dict) and record.get("split") in
                {"development", "validation", "sealed"}, "invalid_lineage")
        for field in ("patient_group", "file_family", "template_family", "institution",
                      "near_duplicate_family", "renderer_family"):
            value = record.get(field)
            if value is None and field in {"near_duplicate_family", "renderer_family"}:
                continue
            require(isinstance(value, str) and value, "invalid_lineage")
            key = field, value
            previous = seen.setdefault(key, record["split"])
            require(previous == record["split"], "split_collision")


def parsed_records(data, format_name):
    try:
        text = data.decode("utf-8")
    except UnicodeError as exc:
        raise InvalidSlice("invalid_utf8") from exc
    if format_name == "text":
        return {"doc": text}
    if format_name in {"csv", "tsv"}:
        code = "invalid_" + format_name
        try:
            rows = list(csv.reader(StringIO(text, newline=""),
                                   delimiter="\t" if format_name == "tsv" else ",",
                                   strict=True))
        except csv.Error as exc:
            raise InvalidSlice(code) from exc
        require(len(rows) >= 2 and len(rows[0]) == len(set(rows[0])) and
                all(rows[0]) and all(len(row) == len(rows[0]) for row in rows[1:]),
                code)
        return {f"row:{index}": dict(zip(rows[0], row))
                for index, row in enumerate(rows[1:])}
    if format_name in {"json", "fhir"}:
        def unique(pairs):
            result = dict(pairs)
            require(len(result) == len(pairs), "invalid_json")
            return result
        try:
            value = json.loads(text, object_pairs_hook=unique,
                               parse_constant=reject_constant)
        except ValueError as exc:
            raise InvalidSlice("invalid_json") from exc
        require(isinstance(value, dict), "invalid_json")
        require(format_name != "json" or value.get("resourceType") != "Bundle",
                "fhir_format_mismatch")
        if format_name == "fhir":
            try:
                check_fhir_bundle(value)
            except ValueError as exc:
                raise InvalidSlice(str(exc)) from exc
        return {"doc": value}
    raise InvalidSlice("unsupported_format")


def pointer_value(value, pointer):
    require(pointer.startswith("/") and pointer != "/", "invalid_locator")
    current = value
    for encoded in pointer[1:].split("/"):
        part = encoded.replace("~1", "/").replace("~0", "~")
        require(part.replace("~", "~0").replace("/", "~1") == encoded,
                "invalid_locator")
        if isinstance(current, dict):
            require(part in current, "invalid_locator")
            current = current[part]
        elif isinstance(current, list):
            require(part.isdigit() and str(int(part)) == part and
                    int(part) < len(current), "invalid_locator")
            current = current[int(part)]
        else:
            raise InvalidSlice("invalid_locator")
    return current


def source_value(record, unit):
    location = unit.get("locator")
    value = record["value"]
    if record["format"] == "text":
        require(location == "doc", "invalid_locator")
        require(unit.get("label") == "", "source_label_mismatch")
        return value
    if record["format"] in {"csv", "tsv"}:
        prefix = record["locator"] + "/"
        require(isinstance(location, str) and location.startswith(prefix), "invalid_locator")
        field = location[len(prefix):]
        require(field in value, "invalid_locator")
        require(unit.get("label") == field, "source_label_mismatch")
        return value[field]
    require(isinstance(location, str), "invalid_locator")
    field = location.rsplit("/", 1)[-1].replace("~1", "/").replace("~0", "~")
    require(unit.get("label") == field, "source_label_mismatch")
    return pointer_value(value, location)


def span(text, start, end):
    require(type(start) is int and type(end) is int and
            0 <= start < end <= len(text), "invalid_span")
    return text[start:end]


def validate_annotation(unit, truth):
    text = unit["text"]
    require(isinstance(text, str), "invalid_source_unit")
    gold = truth.get("gold")
    protected = truth.get("protect")
    require(isinstance(gold, list) and isinstance(protected, list), "invalid_annotation")
    gold_ranges = set()
    for item in gold:
        require(isinstance(item, list) and len(item) == 3 and
                isinstance(item[2], str) and item[2], "invalid_annotation")
        span(text, item[0], item[1])
        gold_ranges.add(tuple(item))
    protected_ranges = set()
    for item in protected:
        require(isinstance(item, list) and len(item) == 2, "invalid_annotation")
        span(text, item[0], item[1])
        protected_ranges.add(tuple(item))
    occurrences = truth.get("occurrences", [])
    require(isinstance(occurrences, list), "invalid_annotation")
    patient_targets = set()
    for occurrence in occurrences:
        require(isinstance(occurrence, dict) and
                occurrence.get("role") in {"patient", "clinician"} and
                isinstance(occurrence.get("type"), str), "invalid_annotation")
        start, end = occurrence.get("start"), occurrence.get("end")
        surface = span(text, start, end)
        require(occurrence.get("surface") == surface, "occurrence_surface_mismatch")
        if occurrence["role"] == "patient":
            patient_targets.add((start, end, occurrence["type"]))
        else:
            require(any(left <= start and end <= right for left, right in protected_ranges),
                    "invalid_annotation")
    require(gold_ranges == patient_targets, "gold_occurrence_mismatch")
    require(all(not (left < end and start < right)
                for start, end, _ in gold_ranges for left, right in protected_ranges),
            "annotation_overlap")
    facts = truth.get("clinical_facts", [])
    require(isinstance(facts, list), "invalid_annotation")
    for fact in facts:
        require(isinstance(fact, dict) and isinstance(fact.get("text"), str),
                "invalid_annotation")
        start, end = fact.get("start"), fact.get("end")
        require(span(text, start, end) == fact["text"] and
                any(left <= start and end <= right for left, right in protected_ranges),
                "invalid_clinical_fact")


def verify(root):
    root = Path(root)
    manifest = read_json(root / "manifest.json")
    require(isinstance(manifest, dict) and
            manifest.get("schema") == "robustness-v2-open-slice/1" and
            manifest.get("split") == "development", "invalid_manifest")
    expected = manifest.get("files")
    require(isinstance(expected, dict) and expected, "invalid_manifest")
    declared_formats = {}
    for record in manifest.get("records", []):
        require(isinstance(record, dict) and isinstance(record.get("file"), str) and
                isinstance(record.get("format"), str), "invalid_manifest")
        filename = record["file"]
        require(filename not in declared_formats or
                declared_formats[filename] == record["format"], "invalid_manifest")
        declared_formats[filename] = record["format"]
    input_root = root / "input"
    require(input_root.is_dir() and not input_root.is_symlink(), "invalid_input_tree")
    actual = {}
    for path in input_root.rglob("*"):
        require(not path.is_symlink(), "invalid_input_tree")
        if path.is_file():
            actual[path.relative_to(input_root).as_posix()] = path
    require(set(actual) == set(expected), "input_file_set_mismatch")
    parsed = {}
    for name, expected_hash in expected.items():
        relative_path(name)
        require(isinstance(expected_hash, str) and len(expected_hash) == 64,
                "invalid_manifest")
        data = actual[name].read_bytes()
        require(sha256(data) == expected_hash, "input_digest_mismatch")
        suffix = actual[name].suffix.lower()
        format_name = declared_formats.get(name)
        allowed = {".txt": {"text"}, ".csv": {"csv"}, ".tsv": {"tsv"},
                   ".json": {"json", "fhir"}}.get(suffix, set())
        require(format_name in allowed, "unsupported_format")
        parsed[name] = (format_name, parsed_records(data, format_name))

    source_path = root / "source_units.json"
    truth_path = root / "truth" / "annotations.json"
    require(source_path.is_file() and truth_path.is_file() and
            not source_path.is_symlink() and not truth_path.is_symlink(),
            "invalid_evaluation_tree")
    source_bytes, truth_bytes = source_path.read_bytes(), truth_path.read_bytes()
    require(sha256(source_bytes) == manifest.get("source_units_sha256") and
            sha256(truth_bytes) == manifest.get("truth_sha256"),
            "evaluation_digest_mismatch")
    units = keyed(read_json(source_path), "invalid_source_units")
    truth = keyed(read_json(truth_path), "invalid_truth")
    require(units.keys() == truth.keys(), "unit_truth_mismatch")
    records = keyed(manifest.get("records"), "invalid_records")
    validate_lineage(list(records.values()))
    require(all(item["split"] == manifest["split"] for item in records.values()),
            "invalid_split")
    record_values = {}
    grouped = {}
    for record_id, record in records.items():
        filename = record.get("file")
        relative_path(filename)
        require(filename in parsed and record.get("format") == parsed[filename][0],
                "invalid_record_file")
        locator = record.get("locator")
        require(isinstance(locator, str) and locator in parsed[filename][1],
                "invalid_record_locator")
        key = filename, locator
        require(key not in grouped, "duplicate_record_locator")
        grouped[key] = record_id
        record_values[record_id] = {"format": record["format"], "locator": locator,
                                    "value": parsed[filename][1][locator]}
    require(grouped.keys() == {(name, locator) for name, (_, values) in parsed.items()
                               for locator in values}, "record_coverage_mismatch")
    covered_records = set()
    covered_locations = set()
    for identifier, unit in units.items():
        record_id = unit.get("record_id")
        require(isinstance(record_id, str) and record_id in record_values,
                "invalid_unit_record_join")
        location = record_id, unit.get("locator")
        require(location not in covered_locations, "duplicate_source_locator")
        covered_locations.add(location)
        covered_records.add(record_id)
        require(unit.get("channel") == "content" and
                isinstance(unit.get("text"), str) and
                source_value(record_values[record_id], unit) == unit["text"],
                "source_value_mismatch")
        annotation = truth[identifier]
        require(annotation.get("record_id") == record_id and
                annotation.get("locator") == unit.get("locator") and
                annotation.get("input_sha256") == manifest["source_units_sha256"],
                "invalid_truth_join")
        validate_annotation(unit, annotation)
    require(covered_records == records.keys(), "record_coverage_mismatch")
    return {"files": len(actual), "records": len(records), "units": len(units),
            "split": manifest["split"], "status": "verified"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    args = parser.parse_args()
    try:
        result = verify(args.root)
    except InvalidSlice as exc:
        print(str(exc), file=sys.stderr)
        return 1
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print("invalid_slice", file=sys.stderr)
        return 1
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
