"""Phase A evaluation. Generate frozen predictions or score an existing release."""
import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "submission")]
from check_dev import all_text_under, norm, read_text
from evaluation.linkage import score_linkage
from evaluation.matching import overlap_matches
from evaluation.role_metrics import RoleMetrics
from rakshak.detection import SourceUnit, detect

SOURCE_FIELDS = {"text", "label", "channel", "section", "unit_of_measure"}
JOIN_FIELDS = ("record_id", "locator")


def keyed(raw):
    data = json.loads(raw)
    result = {item["id"]: item for item in data}
    if len(data) != len(result):
        raise ValueError("duplicate_unit_id")
    return result


def predict(raw):
    units = {}
    for key, item in keyed(raw).items():
        join = {name: item[name] for name in JOIN_FIELDS if name in item}
        if error := item.get("parse_error"):
            units[key] = {"status": error, "accepted": [], "review": [], **join}
            continue
        unit = SourceUnit(**{name: value for name, value in item.items() if name in SOURCE_FIELDS})
        result = detect(unit)
        units[key] = {
            "status": result.error or "complete",
            "accepted": [(x.start, x.end, x.kind) for x in result.findings],
            "review": [(x.start, x.end, x.kind) for x in result.review],
            "accepted_roles": [(x.start, x.end, x.kind, x.role) for x in result.findings if x.role],
            **join,
        }
    return {"schema": "phase-a-predictions/1", "input_sha256": hashlib.sha256(raw).hexdigest(),
            "variant": "regex", "units": units}


def ratio(n, d):
    return n / d if d else None


def score(raw, truth, snapshot, *, strict_v2=False):
    inputs = keyed(raw)
    input_digest = hashlib.sha256(raw).hexdigest()
    if snapshot["schema"] != "phase-a-predictions/1" or snapshot["input_sha256"] != input_digest:
        raise ValueError("input_version_mismatch")
    units = snapshot["units"]
    if units.keys() != inputs.keys() or not truth.keys() <= units.keys():
        raise ValueError("invalid_unit_join")
    for key, item in inputs.items():
        for name in JOIN_FIELDS:
            if strict_v2 and (name not in item or name not in units[key]):
                raise ValueError("invalid_unit_join")
            if name in item and (not isinstance(item[name], str) or not item[name]):
                raise ValueError("invalid_unit_join")
            if item.get(name) != units[key].get(name):
                raise ValueError("invalid_unit_join")
    counts = Counter()
    overlap_counts = Counter()
    adjudicated = Counter()
    adjudicated_overlap = Counter()
    exhaustive_negative = Counter()
    known_positive = Counter()
    role_metrics = RoleMetrics()
    for key, annotations in truth.items():
        if strict_v2 and ("input_sha256" not in annotations or
                          any(name not in annotations for name in JOIN_FIELDS)):
            raise ValueError("invalid_unit_join")
        if annotations.get("input_sha256", input_digest) != input_digest:
            raise ValueError("invalid_unit_join")
        if "input_version" in annotations and annotations["input_version"] != inputs[key].get("input_version"):
            raise ValueError("invalid_unit_join")
        if any(name in annotations and annotations[name] != inputs[key].get(name)
               for name in JOIN_FIELDS):
            raise ValueError("invalid_unit_join")
        pred = units[key]
        actual = {tuple(item) for item in pred["accepted"]}
        gold = {tuple(item) for item in annotations["gold"]}
        review = {tuple(item[:3]) for item in pred["review"]}
        protected = [tuple(item) for item in annotations.get("protect", [])]
        length = len(inputs[key]["text"])
        if any(not (0 <= start < end <= length) for start, end, _ in actual | gold | review):
            raise ValueError("invalid_span")
        if any(not (0 <= start < end <= length) for start, end in protected):
            raise ValueError("invalid_protected_span")
        explicit_roles = {(item["start"], item["end"], item["type"]): item["role"]
                          for item in annotations.get("occurrences", ())
                          if item.get("role") and (item["start"], item["end"], item["type"]) in gold}
        role_metrics.update(explicit_roles, actual, pred)
        unit_class = ("tp" if gold & actual else "fn") if gold else ("fp" if actual else "tn")
        counts[unit_class + "_units"] += 1
        matches = overlap_matches(gold, actual)
        overlap_counts.update(tp=matches, fp=len(actual) - matches, fn=len(gold) - matches)
        counts.update(tp=len(gold & actual), fp=len(actual - gold), fn=len(gold - actual),
                      review_units=bool(review), review_gold=len(gold & review),
                      incomplete_units=pred["status"] != "complete",
                      protected_overlaps=sum(any(start < right and left < end
                                                 for start, end, _ in actual)
                                             for left, right in protected))
        if pred["status"] != "complete" or annotations.get("annotation_status") != "adjudicated":
            continue
        known_positive.update(tp=len(gold & actual), fn=len(gold - actual))
        if annotations.get("negative_scope") == "exhaustive":
            adjudicated.update(units=1, tp=len(gold & actual), fp=len(actual - gold),
                               fn=len(gold - actual), exact_units=(gold == actual))
            adjudicated_overlap.update(tp=matches, fp=len(actual) - matches,
                                       fn=len(gold) - matches)
            if not gold:
                exhaustive_negative.update(units=1, fp=bool(actual), tn=not actual)
        else:
            known_positive["unjudged_predictions"] += len(actual - gold)

    tp, fp, fn = (counts[key] for key in ("tp", "fp", "fn"))
    otp, ofp, ofn = (overlap_counts[key] for key in ("tp", "fp", "fn"))
    utp, ufp, utn, ufn = (counts[f"{key}_units"] for key in ("tp", "fp", "tn", "fn"))
    result = {"labeled_units": len(truth), "input_units": len(inputs),
            "input_incomplete_units": sum(pred["status"] != "complete" for pred in units.values()),
            "counts": dict(counts), "precision": ratio(tp, tp + fp), "recall": ratio(tp, tp + fn),
            "f1": ratio(2 * tp, 2 * tp + fp + fn), "accuracy": ratio(utp + utn, len(truth)),
            "fpr": ratio(ufp, ufp + utn), "fnr": ratio(ufn, ufn + utp),
            "overlap_counts": dict(overlap_counts), "role_metrics": role_metrics.summary(),
            "overlap_precision": ratio(otp, otp + ofp),
            "overlap_recall": ratio(otp, otp + ofn),
            "overlap_f1": ratio(2 * otp, 2 * otp + ofp + ofn)}
    if strict_v2:
        atp, afp, afn = (adjudicated[key] for key in ("tp", "fp", "fn"))
        aotp, aofp, aofn = (adjudicated_overlap[key] for key in ("tp", "fp", "fn"))
        result.update(precision=ratio(atp, atp + afp), recall=ratio(atp, atp + afn),
                      f1=ratio(2 * atp, 2 * atp + afp + afn),
                      overlap_precision=ratio(aotp, aotp + aofp),
                      overlap_recall=ratio(aotp, aotp + aofn),
                      overlap_f1=ratio(2 * aotp, 2 * aotp + aofp + aofn),
                      accuracy=ratio(adjudicated["exact_units"], adjudicated["units"]),
                      known_positive_recall=ratio(known_positive["tp"],
                                                  known_positive["tp"] + known_positive["fn"]),
                      unjudged_exact_predictions=known_positive["unjudged_predictions"],
                      fpr=ratio(exhaustive_negative["fp"],
                                exhaustive_negative["fp"] + exhaustive_negative["tn"]),
                      fnr=ratio(afn, afn + atp))
        result["metric_support"] = {"adjudicated_units": adjudicated["units"],
                                    "exhaustive_negative_units": exhaustive_negative["units"]}
    return result


def export_text(root, result):
    if result:
        target = (root / result).resolve()
        if not target.is_relative_to((root / "sanitized").resolve()) or not target.is_file():
            raise ValueError("invalid_report_output")
        return norm(read_text(target))
    return ""


def practice_audit(root, gold):
    report = json.loads((root / "report.json").read_text())
    outputs = defaultdict(list)
    for metadata in report["files"]:
        outputs[metadata["input_sha256"]].append(metadata["output"])
    totals = Counter()
    by_script = defaultdict(Counter)
    file_exposure = Counter(exported=0, patient_name_visible=0, patient_name_and_geography_visible=0)
    geography = {"HOUSE", "LOCALITY", "VILLAGE", "LANDMARK", "PIN"}
    for _, file in sorted(gold["files"].items()):
        matches = outputs[file["sha256"]]
        if not matches:
            raise ValueError("input_not_accounted_for")
        result = matches.pop(0)
        totals["required_files"] += file.get("expect") == "sanitize"
        totals["required_files_exported"] += file.get("expect") == "sanitize" and result is not None
        text = export_text(root, result)
        path = norm(result or "")
        visible_types = set()
        for unit in file["units"].values():
            for annotation in unit["entities"]:
                if annotation["type"] == "CANARY":
                    continue
                phrase = norm(annotation["surface"])
                haystack = path if annotation["channel"] == "filename" else text
                visible = bool(phrase) and phrase in haystack
                if visible:
                    visible_types.add(annotation["type"])
                totals["identifier_mentions"] += 1
                totals["identifier_mentions_exported"] += result is not None
                totals["visible_mentions"] += visible
                by_script[annotation["script"]].update(labeled=1, visible=visible)
            for probe in unit.get("preserve", []):
                totals["input_clinical_probes"] += 1
                totals["exported_clinical_probes"] += result is not None
                totals["preserved_clinical_probes"] += bool(result) and norm(probe["text"]) in text
        if result is not None:
            file_exposure["exported"] += 1
            if "PATIENT_NAME" in visible_types:
                file_exposure["patient_name_visible"] += 1
                file_exposure["patient_name_and_geography_visible"] += bool(geography & visible_types)
    if any(outputs.values()):
        raise ValueError("extra_report_entries")
    return {"counts": dict(totals), "file_exposure": dict(file_exposure), "report_counts": report["counts"],
            "by_script": {key: dict(value) for key, value in by_script.items()},
            "quarantine_reasons": dict(Counter(file["reason"] for file in report["files"] if file["output"] is None))}


def blind_audit(root, gold, manifest):
    report = json.loads((root / "report.json").read_text())
    by_hash = defaultdict(list)
    for entry in report["files"]:
        by_hash[entry["input_sha256"]].append(entry["output"])
    outputs = {}
    for relative, fingerprint in sorted(manifest["files"].items()):
        if not by_hash[fingerprint]:
            raise ValueError("input_not_accounted_for")
        outputs[relative] = by_hash[fingerprint].pop(0)
    if any(by_hash.values()):
        raise ValueError("extra_report_entries")
    rendered = {relative: export_text(root, output) for relative, output in outputs.items()}
    counts = Counter()
    scripts = defaultdict(Counter)
    for record in gold["records"]:
        relative = record["file"]
        text = rendered[relative]
        counts["records"] += 1
        counts["records_in_exported_file"] += outputs[relative] is not None
        for probe in record["preserve"]:
            counts["input_clinical_probes"] += 1
            counts["preserved_clinical_probes"] += bool(norm(probe)) and norm(probe) in text
        for identifier in record["identifiers"].values():
            phrase = norm(identifier)
            if phrase:
                visible = phrase in text or phrase in norm(outputs[relative] or "")
                counts["identifier_mentions"] += 1
                counts["visible_mentions"] += visible
                scripts[record["script"]].update(labeled=1, visible=visible)
    combined = all_text_under(root)
    canaries = [norm(value) for value in gold["canaries"] if norm(value)]
    counts["canaries"] = len(canaries)
    counts["canaries_visible"] = sum(phrase in combined for phrase in canaries)
    return {"counts": dict(counts), "report_counts": report["counts"],
            "by_script": {key: dict(value) for key, value in scripts.items()},
            "quarantine_reasons": dict(Counter(file["reason"] for file in report["files"] if file["output"] is None))}


def verify_corpus(tree, manifest):
    expected = manifest["files"]
    actual = {}
    for item in tree.rglob("*"):
        if item.is_file():
            with item.open("rb") as stream:
                actual[item.relative_to(tree).as_posix()] = hashlib.file_digest(stream, "sha256").hexdigest()
    if actual != expected:
        raise ValueError("corpus_manifest_mismatch")
    return {"verified_files": len(actual),
            "manifest_sha256": hashlib.sha256(json.dumps(expected, sort_keys=True).encode()).hexdigest()}


def open_slice_audit(dataset, release):
    from docs.datasets.robustness_v2.verify_open_slice import parsed_records, source_value, verify

    verify(dataset)
    manifest = json.loads((dataset / "manifest.json").read_bytes())
    units = keyed((dataset / "source_units.json").read_bytes())
    truth = keyed((dataset / "truth" / "annotations.json").read_bytes())
    report = json.loads((release / "report.json").read_bytes())
    fingerprints = manifest["files"]
    formats = {record["file"]: record["format"] for record in manifest["records"]}
    if len(set(fingerprints.values())) != len(fingerprints):
        raise ValueError("ambiguous_input_digest")
    entries = report["files"]
    if Counter(entry["input_sha256"] for entry in entries) != Counter(fingerprints.values()):
        raise ValueError("invalid_release_ledger")
    by_hash = {entry["input_sha256"]: entry for entry in entries}
    output_records = {}
    output_paths = {}
    used_outputs = set()
    sanitized = 0
    for relative, fingerprint in fingerprints.items():
        entry = by_hash[fingerprint]
        output = entry["output"]
        if output is None:
            if entry["status"] != "quarantined":
                raise ValueError("invalid_release_ledger")
            continue
        if entry["status"] != "sanitized" or not isinstance(output, str):
            raise ValueError("invalid_release_ledger")
        if not output.startswith("sanitized/") or Path(output).is_absolute() or \
                any(part in {"", ".", ".."} for part in output.split("/")):
            raise ValueError("invalid_release_path")
        target = (release / output).resolve()
        if not target.is_relative_to((release / "sanitized").resolve()) or not target.is_file():
            raise ValueError("invalid_report_output")
        if target in used_outputs:
            raise ValueError("invalid_release_ledger")
        used_outputs.add(target)
        suffix = Path(relative).suffix.lower()
        if target.suffix.lower() != suffix:
            raise ValueError("invalid_release_ledger")
        format_name = formats[relative]
        output_records[relative] = parsed_records(target.read_bytes(), format_name)
        output_paths[relative] = output
        sanitized += 1
    sanitized_root = release / "sanitized"
    if not sanitized_root.is_dir() or sanitized_root.is_symlink():
        raise ValueError("invalid_release_ledger")
    actual_outputs = set()
    for target in sanitized_root.rglob("*"):
        if target.is_symlink():
            raise ValueError("invalid_release_ledger")
        if target.is_file():
            actual_outputs.add(target.resolve())
    if actual_outputs != used_outputs:
        raise ValueError("invalid_release_ledger")
    records = {record["id"]: record for record in manifest["records"]}
    if len(records) != len(manifest["records"]):
        raise ValueError("invalid_record_join")
    expected_index = {(output_paths[record['file']], record["locator"])
                      for record in records.values() if record["file"] in output_records}
    record_by_index = {(output_paths[record['file']], record["locator"]): record["id"]
                       for record in records.values() if record["file"] in output_records}
    original_by_output = {output: original for original, output in output_paths.items()}
    if len(record_by_index) != len(expected_index):
        raise ValueError("invalid_record_join")
    pseudonyms = {identifier: None for identifier in records}
    observed_index = set()
    try:
        record_lines = (release / "records.jsonl").read_text(encoding="utf-8").splitlines()
        for line in record_lines:
            entry = json.loads(line)
            key = entry["file"], entry["loc"]
            if key not in expected_index or key in observed_index:
                raise ValueError("invalid_record_index")
            observed_index.add(key)
            patient = entry["patient"]
            if patient is not None:
                if not isinstance(patient, str) or not patient or \
                        patient not in json.dumps(output_records[original_by_output[key[0]]][key[1]],
                                                  ensure_ascii=False):
                    raise ValueError("invalid_record_index")
            pseudonyms[record_by_index[key]] = patient
    except (OSError, UnicodeError, KeyError, TypeError, json.JSONDecodeError) as exc:
        raise ValueError("invalid_record_index") from exc
    if observed_index != expected_index:
        raise ValueError("invalid_record_index")
    clinical_facts = 0
    preserved_facts = 0
    for identifier, unit in units.items():
        facts = truth[identifier].get("clinical_facts", [])
        clinical_facts += len(facts)
        record = records[unit["record_id"]]
        values = output_records.get(record["file"])
        if values is None:
            continue
        locator = record["locator"]
        if locator not in values:
            raise ValueError("invalid_output_locator")
        rendered = source_value({"format": record["format"], "locator": locator,
                                 "value": values[locator]}, unit)
        preserved_facts += sum(fact["text"] in rendered for fact in facts)
    if report["counts"]["files_total"] != len(fingerprints) or \
            report["counts"]["files_sanitized"] != sanitized or \
            report["counts"]["files_quarantined"] != len(fingerprints) - sanitized:
        raise ValueError("invalid_release_ledger")
    linkage = score_linkage(manifest["records"], pseudonyms, [])
    return {"input_files": len(fingerprints), "sanitized_files": sanitized,
            "quarantined_files": len(fingerprints) - sanitized,
            "input_clinical_facts": clinical_facts,
            "preserved_clinical_facts": preserved_facts,
            "linkage_diagnostic": {"false_merged_clusters": linkage["false_merged_clusters"],
                                   "abstained_records": linkage["abstained_records"],
                                   "predicted_clusters": linkage["predicted_clusters"],
                                   "b_cubed": linkage["b_cubed_diagnostic"]}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    p = commands.add_parser("predict")
    p.add_argument("inputs", type=Path)
    p = commands.add_parser("score")
    for name in ("inputs", "truth", "predictions"):
        p.add_argument(name, type=Path)
    p.add_argument("--strict-v2", action="store_true",
                   help="require joins and withhold precision/FPR without adjudicated truth")
    p = commands.add_parser("practice-audit")
    p.add_argument("output", type=Path)
    p.add_argument("--truth", type=Path, default=ROOT / "dev/truth/truth.json")
    p = commands.add_parser("blind-audit")
    for name in ("output", "truth", "manifest"):
        p.add_argument(name, type=Path)
    p = commands.add_parser("verify-corpus")
    p.add_argument("inputs", type=Path)
    p.add_argument("manifest", type=Path)
    p = commands.add_parser("open-slice-audit")
    p.add_argument("dataset", type=Path)
    p.add_argument("release", type=Path)
    p = commands.add_parser("linkage-score")
    p.add_argument("manifest", type=Path)
    p.add_argument("predictions", type=Path)
    p.add_argument("pairs", type=Path)
    args = parser.parse_args()
    if args.command == "predict":
        result = predict(args.inputs.read_bytes())
    elif args.command == "score":
        result = score(args.inputs.read_bytes(), keyed(args.truth.read_bytes()),
                       json.loads(args.predictions.read_bytes()), strict_v2=args.strict_v2)
    elif args.command == "practice-audit":
        result = practice_audit(args.output, json.loads(args.truth.read_bytes()))
    elif args.command == "blind-audit":
        result = blind_audit(args.output, json.loads(args.truth.read_bytes()),
                             json.loads(args.manifest.read_bytes()))
    elif args.command == "open-slice-audit":
        result = open_slice_audit(args.dataset, args.release)
    elif args.command == "linkage-score":
        result = score_linkage(json.loads(args.manifest.read_bytes())["records"],
                               json.loads(args.predictions.read_bytes()),
                               json.loads(args.pairs.read_bytes()))
    else:
        result = verify_corpus(args.inputs, json.loads(args.manifest.read_bytes()))
    print(json.dumps(result, sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
