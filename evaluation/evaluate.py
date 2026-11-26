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
from rakshak.detection import SourceUnit, detect


def keyed(raw):
    data = json.loads(raw)
    result = {item["id"]: item for item in data}
    if len(data) != len(result):
        raise ValueError("duplicate_unit_id")
    return result


def predict(raw):
    units = {}
    for key, item in keyed(raw).items():
        unit = SourceUnit(**{name: value for name, value in item.items() if name != "id"})
        result = detect(unit)
        units[key] = {
            "status": result.error or "complete",
            "accepted": [(x.start, x.end, x.kind) for x in result.findings],
            "review": [(x.start, x.end, x.kind) for x in result.review],
        }
    return {"schema": "phase-a-predictions/1", "input_sha256": hashlib.sha256(raw).hexdigest(),
            "variant": "regex", "units": units}


def ratio(n, d):
    return n / d if d else None


def score(raw, truth, snapshot):
    inputs = keyed(raw)
    if snapshot["schema"] != "phase-a-predictions/1" or snapshot["input_sha256"] != hashlib.sha256(raw).hexdigest():
        raise ValueError("input_version_mismatch")
    units = snapshot["units"]
    if units.keys() != inputs.keys() or not truth.keys() <= units.keys():
        raise ValueError("invalid_unit_join")
    counts = Counter()
    for key, annotations in truth.items():
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
        unit_class = ("tp" if actual else "fn") if gold else ("fp" if actual else "tn")
        counts[unit_class + "_units"] += 1
        counts.update(tp=len(gold & actual), fp=len(actual - gold), fn=len(gold - actual),
                      review_units=bool(review), review_gold=len(gold & review),
                      incomplete_units=pred["status"] != "complete",
                      protected_overlaps=sum(any(start < right and left < end
                                                 for start, end, _ in actual)
                                             for left, right in protected))
    tp, fp, fn = (counts[key] for key in ("tp", "fp", "fn"))
    utp, ufp, utn, ufn = (counts[f"{key}_units"] for key in ("tp", "fp", "tn", "fn"))
    return {"labeled_units": len(truth), "input_units": len(inputs),
            "counts": dict(counts), "precision": ratio(tp, tp + fp), "recall": ratio(tp, tp + fn),
            "f1": ratio(2 * tp, 2 * tp + fp + fn), "accuracy": ratio(utp + utn, len(truth)),
            "fpr": ratio(ufp, ufp + utn), "fnr": ratio(ufn, ufn + utp)}


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
    for _, file in sorted(gold["files"].items()):
        matches = outputs[file["sha256"]]
        if not matches:
            raise ValueError("input_not_accounted_for")
        result = matches.pop(0)
        totals["required_files"] += file.get("expect") == "sanitize"
        totals["required_files_exported"] += file.get("expect") == "sanitize" and result is not None
        text = export_text(root, result)
        path = norm(result or "")
        for unit in file["units"].values():
            for annotation in unit["entities"]:
                if annotation["type"] == "CANARY":
                    continue
                phrase = norm(annotation["surface"])
                haystack = path if annotation["channel"] == "filename" else text
                visible = bool(phrase) and phrase in haystack
                totals["identifier_mentions"] += 1
                totals["identifier_mentions_exported"] += result is not None
                totals["visible_mentions"] += visible
                by_script[annotation["script"]].update(labeled=1, visible=visible)
            for probe in unit.get("preserve", []):
                totals["input_clinical_probes"] += 1
                totals["exported_clinical_probes"] += result is not None
                totals["preserved_clinical_probes"] += bool(result) and norm(probe["text"]) in text
    if any(outputs.values()):
        raise ValueError("extra_report_entries")
    return {"counts": dict(totals), "report_counts": report["counts"],
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


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    p = commands.add_parser("predict")
    p.add_argument("inputs", type=Path)
    p = commands.add_parser("score")
    for name in ("inputs", "truth", "predictions"):
        p.add_argument(name, type=Path)
    p = commands.add_parser("practice-audit")
    p.add_argument("output", type=Path)
    p.add_argument("--truth", type=Path, default=ROOT / "dev/truth/truth.json")
    p = commands.add_parser("blind-audit")
    for name in ("output", "truth", "manifest"):
        p.add_argument(name, type=Path)
    p = commands.add_parser("verify-corpus")
    p.add_argument("inputs", type=Path)
    p.add_argument("manifest", type=Path)
    args = parser.parse_args()
    if args.command == "predict":
        result = predict(args.inputs.read_bytes())
    elif args.command == "score":
        result = score(args.inputs.read_bytes(), keyed(args.truth.read_bytes()),
                       json.loads(args.predictions.read_bytes()))
    elif args.command == "practice-audit":
        result = practice_audit(args.output, json.loads(args.truth.read_bytes()))
    elif args.command == "blind-audit":
        result = blind_audit(args.output, json.loads(args.truth.read_bytes()),
                             json.loads(args.manifest.read_bytes()))
    else:
        result = verify_corpus(args.inputs, json.loads(args.manifest.read_bytes()))
    print(json.dumps(result, sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
