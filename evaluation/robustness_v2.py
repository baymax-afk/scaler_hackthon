"""Validate generated robustness_v2 inputs and audit independent Research Releases."""
import argparse
import base64
from collections import Counter, defaultdict
import csv
from functools import lru_cache
from hashlib import sha256
import io
import json
from pathlib import Path
import sys
from xml.etree import ElementTree

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "docs/datasets/robustness_v2")]
from generate import FORMATS, SCENARIOS, VERSION
from evaluation.matching import overlap_matches
from evaluation.release_evidence import OccurrenceAlignment, reconcile
from evaluation.source_inventory import annotated_source_id, source_inventory


LINEAGE = ("id", "patient_group", "template_family", "institution")
R4_SCHEMA_SHA256 = "2230406893b4cf002a4ee1e5e2bbeca22ac5d2d4931b3e9ef7b9594bbc376a01"
IDENTIFIERS = {"NAME", "RELATIVE", "EMAIL", "MRN", "AADHAAR", "ABHA", "PHONE", "INSURANCE_ID"}


def read_json(path):
    return json.loads(path.read_bytes())


def require(condition, code):
    if not condition:
        raise ValueError(code)


def digest(path):
    return sha256(path.read_bytes()).hexdigest()


def dereference(value, locator):
    if locator == "doc":
        return value
    for part in locator.split("/")[1:]:
        part = part.replace("~1", "/").replace("~0", "~")
        value = value[int(part)] if isinstance(value, list) else value[part]
    return value


def read_document(path, fmt):
    stat = path.stat()
    return parsed_document(path, fmt, (stat.st_ino, stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns))


@lru_cache(maxsize=32)
def parsed_document(path, fmt, _file_version):
    if fmt in {"csv", "tsv"}:
        raw = path.read_bytes()
        encoding = "utf-16" if raw.startswith((b"\xff\xfe", b"\xfe\xff")) else "utf-8-sig"
        rows = list(csv.reader(io.StringIO(raw.decode(encoding), newline=""),
                               delimiter="," if fmt == "csv" else "\t", strict=True))
        require(rows and all(len(row) == len(rows[0]) for row in rows), "invalid_table")
        return rows[1:]
    if fmt == "txt":
        return path.read_bytes().decode("utf-8-sig")
    return read_json(path)


def record_value(path, fmt, locator):
    value = read_document(path, fmt)
    if fmt in {"csv", "tsv"}:
        require(locator.startswith("row:"), "invalid_row_locator")
        return value[int(locator[4:])]
    return dereference(value, locator)


def unit_text(value, unit):
    loc = unit["location"]
    value = value[int(loc)] if isinstance(value, list) else dereference(value, loc)
    if unit["representation"] == "base64_utf8":
        return base64.b64decode(value, validate=True).decode("utf-8")
    require(unit["representation"] in {"text", "scalar"}, "unknown_representation")
    return str(value)


def validate_fhir(bundle):
    entries = bundle["entry"]
    require(bundle["resourceType"] == "Bundle" and isinstance(entries, list), "invalid_bundle")
    require(sum(e["resource"]["resourceType"] == "Patient" for e in entries) == 1,
            "fhir_patient_count")
    targets = {e["fullUrl"] for e in entries}
    require(len(entries) == len(targets), "duplicate_fhir_target")
    if bundle["type"] == "document":
        require(bundle.get("timestamp") and set(bundle["identifier"]) >= {"system", "value"}
                and entries[0]["resource"]["resourceType"] == "Composition", "document_header")
    else:
        require(bundle["type"] == "collection", "unsupported_bundle_type")

    def visit(value):
        if isinstance(value, dict):
            if "reference" in value:
                require(value["reference"] in targets, "unresolved_reference")
            if "contentType" in value and "data" in value:
                base64.b64decode(value["data"], validate=True)
            if "div" in value:
                tag = ElementTree.fromstring(value["div"]).tag
                require(tag == "{http://www.w3.org/1999/xhtml}div", "invalid_narrative")
            for nested in value.values():
                visit(nested)
        elif isinstance(value, list):
            for nested in value:
                visit(nested)

    visit(entries)


def load_split(folder):
    return read_json(folder / "manifest.json"), read_json(folder / "truth.json")


def validate(root, fhir_schema=None):
    results = {}
    owners = {}
    schema = None
    if fhir_schema is not None:
        from jsonschema import Draft6Validator
        require(digest(fhir_schema) == R4_SCHEMA_SHA256, "unexpected_r4_schema")
        document = read_json(fhir_schema)
        schema = Draft6Validator({**document, "$ref": "#/definitions/Bundle"})
    for split, quotas in FORMATS.items():
        directory = root / split
        manifest, records = load_split(directory)
        source = directory / "input"
        actual_hashes = {path.relative_to(source).as_posix(): digest(path)
                         for path in source.rglob("*") if path.is_file()}
        require(manifest["version"] == VERSION and manifest["split"] == split, "version_or_split")
        require(manifest["files"] == actual_hashes, "file_hash_mismatch")
        require(manifest["truth_sha256"] == digest(directory / "truth.json"), "truth_hash_mismatch")
        require(manifest["linkage_sha256"] == digest(directory / "linkage.json"), "linkage_hash_mismatch")
        require(Counter(r["format"] for r in records) == quotas == manifest["formats"], "format_counts")
        scenarios = {name: counts[split == "validation"] for name, counts in SCENARIOS.items()}
        require(Counter(r["scenario"] for r in records) == scenarios == manifest["scenarios"],
                "scenario_counts")
        require({r["file"] for r in records} == set(actual_hashes), "unaccounted_input_file")
        require(len(set(actual_hashes.values())) == len(actual_hashes), "duplicate_file")
        locators = set()
        by_file = defaultdict(list)
        observed_ids = set()
        counts = Counter()
        patient_records = defaultdict(list)
        for file_hash in actual_hashes.values():
            require(owners.setdefault(("sha256", file_hash), split) == split, "split_collision")
        for record in records:
            for key in LINEAGE:
                value = record[key]
                require(bool(value), "missing_lineage")
                require(owners.setdefault((key, value), split) == split, "split_collision")
            require(record["split"] == split, "wrong_record_split")
            require(record["id"] not in observed_ids, "duplicate_record_id")
            observed_ids.add(record["id"])
            locator = record["file"], record["loc"]
            require(locator not in locators, "duplicate_locator")
            locators.add(locator)
            by_file[record["file"]].append(record)
            value = record_value(source / record["file"], record["format"], record["loc"])
            require(record["patient_group"] not in json.dumps(value), "truth_leakage")
            patient_records[record["patient_group"]].append(record)
            if record["format"] == "fhir":
                validate_fhir(value)
                if schema is not None:
                    require(schema.is_valid(value), "fhir_schema_failure")
            for unit in record["units"]:
                original = unit_text(value, unit)
                last = 0
                for span in unit["spans"]:
                    start, end = span["start"], span["end"]
                    require(last <= start < end <= len(original) and original[start:end] == span["surface"],
                            "invalid_original_span")
                    if span["kind"] == "EMAIL":
                        require(span["surface"].endswith(".invalid"), "unreserved_email")
                    last = end
                    counts[span["kind"]] += 1
        require(all((source / relative).is_file() for relative, _ in locators), "missing_input_file")
        for relative, group in by_file.items():
            fmt = group[0]["format"]
            value = read_document(source / relative, fmt)
            if fmt in {"csv", "tsv"}:
                require(len(value) == len(group), "unannotated_table_row")
            elif fmt == "json":
                array_locators = {r["loc"].rsplit("/", 1)[0] for r in group}
                require(len(array_locators) == 1 and
                        len(dereference(value, array_locators.pop())) == len(group),
                        "unannotated_json_record")
            else:
                require(len(group) == 1, "unexpected_document_count")
        linkage = read_json(directory / "linkage.json")
        by_id = {record["id"]: record for record in records}
        positive_pairs = {frozenset(group) for group in linkage["eligible_same_patient"]}
        require(positive_pairs == {frozenset(r["id"] for r in group)
                                  for group in patient_records.values() if len(group) == 2},
                "linkage_truth_mismatch")
        for a, b in linkage["challenge_different_patient"]:
            require(by_id[a]["patient_group"] != by_id[b]["patient_group"], "invalid_negative_pair")
            names = [{s["surface"] for u in by_id[id]["units"] for s in u["spans"] if s["kind"] == "NAME"}
                     for id in (a, b)]
            require(bool(names[0] & names[1]), "negative_pair_without_name_collision")
        repeat_pairs = 0
        for group in patient_records.values():
            require(len(group) <= 2, "unexpected_patient_cluster_size")
            if len(group) == 2:
                first, second = group
                first_email, second_email = [
                    {s["surface"] for u in r["units"] for s in u["spans"] if s["kind"] == "EMAIL"}
                    for r in group
                ]
                require(first["format"] != second["format"] and first_email == second_email
                        and first_email, "invalid_longitudinal_pair")
                repeat_pairs += 1
        results[split] = {"records": len(records), "formats": quotas, "scenarios": scenarios,
                          "fhir_schema": "hl7_r4_json_schema" if schema else "local_structural_checks",
                          "language": dict(Counter(r["language"] for r in records)),
                          "families": len({r["template_family"] for r in records}),
                          "patients": len(patient_records), "linkable_cross_format_pairs": repeat_pairs,
                          "challenging_negative_pairs": len(linkage["challenge_different_patient"]),
                          "spans": dict(counts), "files": len(actual_hashes),
                          "manifest_sha256": digest(directory / "manifest.json")}
    sidecars = read_json(root / "rejection" / "manifest.json")
    require({p.name for p in (root / "rejection" / "input").iterdir()} == sidecars.keys(),
            "rejection_file_coverage")
    for name, item in sidecars.items():
        require(digest(root / "rejection" / "input" / name) == item["sha256"], "rejection_sha256")
    return {"dataset": VERSION, "open_splits": results, "rejection_fixtures": len(sidecars)}


def source_units(folder):
    yield from source_inventory(folder / "input")


def score_spans(folder, raw, predictions):
    _, records = load_split(folder)
    require(predictions["schema"] == "phase-a-predictions/1", "prediction_schema")
    require(predictions["input_sha256"] == sha256(raw).hexdigest(), "prediction_input_digest")
    actual_units = json.loads(raw)
    require(actual_units == list(source_units(folder)), "source_units_do_not_match_dataset")
    source = {unit["id"]: unit["text"] for unit in actual_units}
    truth_units = defaultdict(list)
    for record in records:
        for unit in record["units"]:
            truth_units[annotated_source_id(record, unit)].extend(unit["spans"])
    require(source.keys() == predictions["units"].keys() and truth_units.keys() <= source.keys(),
            "prediction_join")
    totals = Counter()
    by_kind = defaultdict(Counter)
    for key, result in predictions["units"].items():
        selected = {tuple(item) for item in result["accepted"]}
        require(all(0 <= s < e <= len(source[key]) for s, e, _ in selected), "invalid_prediction_span")
        incomplete = result["status"] != "complete"
        totals["units"] += 1
        totals["incomplete_units"] += incomplete
        totals["units_with_review_candidates"] += bool(result["review"])
        if key not in truth_units:
            totals["unannotated_units"] += 1
            continue
        gold = defaultdict(set)
        for span in truth_units[key]:
            start, end, kind = span["start"], span["end"], span["kind"]
            require(0 <= start < end <= len(source[key]), "invalid_annotation_span")
            require(source[key][start:end] == span["surface"], "annotation_source_mismatch")
            if kind == "PROTECT":
                totals["protected_spans"] += 1
                totals["protected_overlaps"] += any(s < end and start < e for s, e, _ in selected)
                totals["protected_incomplete"] += incomplete
            elif kind in IDENTIFIERS:
                gold[kind].add((start, end, kind))
        for kind, expected in gold.items():
            observed = {finding for finding in selected if finding[2] == kind}
            bucket = by_kind[kind]
            bucket["annotated"] += len(expected)
            bucket["exact_hits"] += len(expected & observed) if not incomplete else 0
            bucket["overlap_hits"] += overlap_matches(expected, observed) if not incomplete else 0
            bucket["incomplete"] += len(expected) if incomplete else 0
    return {"counts": totals, "by_category": by_kind, "annotation_status": "generated_unreviewed",
            "role_prediction_support": "unavailable_in_phase_a_snapshots",
            "overlap_semantics": "one-to-one typed overlap without precision or FPR"}


def released_by_input(folder, release):
    source = folder / "input"
    files = read_json(folder / "manifest.json")["files"]
    actual = {path.relative_to(source).as_posix(): digest(path)
              for path in source.rglob("*") if path.is_file()}
    require(files == actual, "audit_input_manifest_mismatch")
    return reconcile(release, files)


def matching_index_entry(index, output, loc):
    if output is None:
        return None, loc
    ancestors = [loc]
    if loc.startswith("/"):
        parent = loc.rsplit("/", 1)[0]
        while parent:
            ancestors.append(parent)
            parent = parent.rsplit("/", 1)[0]
    if loc != "doc":
        ancestors.append("doc")
    for ancestor in ancestors:
        row = index.get((output, ancestor))
        if row:
            destination = row.get("out", ancestor)
            suffix = loc if ancestor == "doc" and loc.startswith("/") else loc[len(ancestor):]
            if ancestor != loc:
                if ancestor == "doc" and loc.startswith("row:"):
                    return row, loc
                if destination.startswith("/") or destination == "doc":
                    destination = ("" if destination == "doc" else destination) + suffix
            return row, destination
    return None, loc


def audit(folder, release):
    _, truth = load_split(folder)
    destinations = released_by_input(folder, release)
    index = {}
    for row in map(json.loads, (release / "records.jsonl").read_text().splitlines()):
        key = row["file"], row["loc"]
        require(all(isinstance(value, str) and value for value in (*key, row.get("out", key[1]))),
                "invalid_release_locator")
        require(row.get("patient") is None or isinstance(row["patient"], str), "invalid_pseudonym")
        require(key not in index, "duplicate_release_locator")
        index[key] = row
    counters = defaultdict(Counter)
    matched = set()
    predicted_by_id = {}
    predicted_groups = defaultdict(list)
    for record in truth:
        original = record_value(folder / "input" / record["file"], record["format"], record["loc"])
        output = destinations[record["file"]]["output"]
        by_format = counters[record["format"]]
        by_format["records"] += 1
        by_format["records_in_exported_file"] += bool(output)
        key = output, record["loc"]
        row, destination = matching_index_entry(index, output, record["loc"])
        if key in index:
            by_format["indexed"] += 1
        predicted = row.get("patient") if row else None
        if row:
            matched.add((row["file"], row["loc"]))
        try:
            after = record_value(release / output, record["format"], destination) if output else None
        except (OSError, KeyError, IndexError, TypeError, UnicodeError, csv.Error, ValueError):
            after = None
        by_format["records_locatable"] += after is not None
        if predicted is not None:
            if after is None or predicted not in json.dumps(after, ensure_ascii=False):
                by_format["pseudonyms_missing_from_records"] += 1
                predicted = None
            else:
                predicted_groups[predicted].append(record["patient_group"])
        if "id" in record:
            predicted_by_id[record["id"]] = predicted
        for unit in record["units"]:
            source = unit_text(original, unit)
            rendered = None
            if after is not None:
                try:
                    rendered = unit_text(after, unit)
                except (KeyError, IndexError, TypeError, UnicodeError, ValueError):
                    pass
            coverage = "unexported" if output is None else "unresolved"
            mapping = OccurrenceAlignment(source, rendered)
            for span in unit["spans"]:
                start, end, kind = span["start"], span["end"], span["kind"]
                require(0 <= start < end <= len(source) and source[start:end] == span["surface"],
                        "invalid_original_span")
                outcome = mapping.outcome(start, end) if rendered is not None else coverage
                if kind == "PROTECT":
                    by_format["protected_spans"] += 1
                    by_format["protected_preserved"] += outcome == "visible"
                    by_format["protected_damaged"] += outcome in {"partial", "transformed"}
                    by_format["protected_unresolved"] += outcome == "unresolved"
                    by_format["protected_unexported"] += outcome == "unexported"
                elif kind in IDENTIFIERS:
                    by_format["identifier_labels"] += 1
                    by_format["identifier_labels_in_locatable_units"] += rendered is not None
                    by_format["literal_residuals"] += outcome == "visible"
                    by_format["identifier_partial"] += outcome == "partial"
                    by_format["identifier_transformed"] += outcome == "transformed"
                    by_format["identifier_unresolved"] += outcome == "unresolved"
                    by_format["identifier_unexported"] += outcome == "unexported"
    linkage_path = folder / "linkage.json"
    eligible = read_json(linkage_path)["eligible_same_patient"] if linkage_path.is_file() else []
    pairs = len(eligible)
    true_links = sum(predicted_by_id[left] is not None and predicted_by_id[left] == predicted_by_id[right]
                     for left, right in eligible)
    def count_pairs(n):
        return n * (n - 1) // 2

    false_links = sum(count_pairs(len(group)) - sum(count_pairs(n) for n in Counter(group).values())
                      for group in predicted_groups.values())
    return {"by_format": counters, "extra_index_entries": len(index.keys() - matched),
            "files": Counter(row["status"] for row in destinations.values()),
            "linkage_truth_available": linkage_path.is_file(),
            "linkage": {"eligible_pairs": pairs, "true_pairs": true_links, "false_pairs": false_links,
                        "pair_precision": true_links / (true_links + false_links) if true_links + false_links else None,
                        "pair_recall": true_links / pairs if pairs else None},
            "scope": "conservative original-occurrence alignment within mapped output units"}


def audit_rejection(folder, release):
    expected = read_json(folder / "manifest.json")
    observed = reconcile(release, {name: item["sha256"] for name, item in expected.items()})
    index = {json.loads(line)["file"] for line in (release / "records.jsonl").read_text().splitlines()}
    mismatches = {}
    for name, item in expected.items():
        entry = observed[name]
        if item["expected_disposition"] != entry["status"]:
            mismatches[name] = {"expected": item["expected_disposition"], "observed": entry["status"]}
        elif item["reason"] == "metadata_zero_records" and entry["output"] in index:
            mismatches[name] = {"expected": "metadata_zero_records", "observed": "metadata_index_entry"}
    return {"fixtures": len(expected), "mismatches": mismatches}


def vocabulary_audit(root):
    def surfaces(folder):
        _, records = load_split(folder)
        groups = defaultdict(Counter)
        for record in records:
            for field in record["units"]:
                for span in field["spans"]:
                    if span["kind"] in IDENTIFIERS or span["kind"] == "PROTECT":
                        groups[span["kind"]][span["surface"]] += 1
        groups["source_labels"].update(item["label"] for item in source_units(folder)
                                       if item.get("label"))
        return groups

    dev = surfaces(root / "development")
    validation = surfaces(root / "validation")
    return {
        kind: {"validation_occurrences": sum(group.values()),
               "validation_occurrences_seen_in_development": sum(
                    n for value, n in group.items() if value in dev[kind]),
               "validation_unique": len(group),
               "validation_unique_seen_in_development": len(group.keys() & dev[kind].keys())}
        for kind, group in sorted(validation.items())
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    for command in ("validate", "units", "score", "release", "rejection", "vocabulary"):
        sub = commands.add_parser(command)
        sub.add_argument("dataset", type=Path)
        if command == "validate":
            sub.add_argument("--fhir-schema", type=Path)
        elif command in {"release", "rejection"}:
            sub.add_argument("release", type=Path)
        elif command == "score":
            sub.add_argument("units", type=Path)
            sub.add_argument("predictions", type=Path)
    args = parser.parse_args()
    if args.command == "validate":
        result = validate(args.dataset, args.fhir_schema)
    elif args.command == "units":
        result = list(source_units(args.dataset))
    elif args.command == "score":
        result = score_spans(args.dataset, args.units.read_bytes(), read_json(args.predictions))
    elif args.command == "release":
        result = audit(args.dataset, args.release)
    elif args.command == "vocabulary":
        result = vocabulary_audit(args.dataset)
    else:
        result = audit_rejection(args.dataset, args.release)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
