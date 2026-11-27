"""Create a deterministic, reconciled de-identification output."""
from collections import Counter
from hashlib import file_digest
import hmac
import json
from pathlib import Path
import resource
import shutil
import sys
import tempfile
import time

from .formats import Rewrite, UnsafeInput, decode, transform
from .detection import SourceUnit, detect
from .linkage import resolve_linkage
import csv

MAX_FILE = 16 * 1024 * 1024
SUPPORTED = {".csv", ".tsv", ".json", ".txt"}


def output_location(relative, secret):
    for component in relative.parts[:-1]:
        result = detect(SourceUnit(component, channel="filename"))
        if result.error or result.review or result.findings:
            raise UnsafeInput("unsafe_directory_name")
    result = detect(SourceUnit(relative.name, channel="filename"))
    if result.error or result.review:
        raise UnsafeInput("ambiguous_filename")
    if not result.findings:
        return relative
    token = hmac.digest(secret, ("file/" + relative.as_posix()).encode(), "sha256").hex()[:24]
    return relative.with_name("file_" + token + relative.suffix.lower())


def apply_pseudonyms(path, changes):
    delimiter = "\t" if path.suffix.lower() == ".tsv" else ","
    # The temporary file never contains raw data and is removed with the stage on failure.
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", newline="",
                                     dir=path.parent, delete=False) as staged:
        with path.open(encoding="utf-8", newline="") as original:
            reader = csv.reader(original, delimiter=delimiter, strict=True)
            writer = csv.writer(staged, delimiter=delimiter, lineterminator="\n")
            writer.writerow(next(reader))
            for index, row in enumerate(reader):
                if index in changes:
                    column, patient = changes[index]
                    row[column] = patient
                writer.writerow(row)
        replacement = Path(staged.name)
    replacement.replace(path)


def build_release(input_path, output, secret):
    started = time.monotonic()
    files = []
    entities = Counter()
    counts = Counter()
    sanitized = output / "sanitized"
    sanitized.mkdir()
    used_files = set()
    used_dirs = set()
    records = {}
    evidence = {}
    for file in sorted(input_path.rglob("*")):
        if file.is_symlink():
            raise UnsafeInput("input_symlink")
        if file.is_dir():
            continue
        if not file.is_file():
            raise UnsafeInput("nonregular_input")
        with file.open("rb") as stream:
            fingerprint = file_digest(stream, "sha256").hexdigest()
            stream.seek(0)
            try:
                suffix = file.suffix.lower()
                if suffix not in SUPPORTED:
                    raise UnsafeInput("unsupported_format")
                raw = stream.read(MAX_FILE + 1)
                if len(raw) > MAX_FILE:
                    raise UnsafeInput("file_limit")
                rewrite = Rewrite(secret)
                destination = output_location(file.relative_to(input_path), secret)
                rendered, locators = transform(decode(raw), suffix, rewrite)
                # Validate UTF-8 before publication, including JSON surrogate escapes.
                rendered_bytes = rendered.encode("utf-8")
                parents = set(destination.parents)
                if destination in used_files or destination in used_dirs or parents & used_files:
                    raise UnsafeInput("output_path_collision")
            except UnsafeInput as exc:
                files.append({"input_sha256": fingerprint, "output": None,
                              "status": "quarantined", "reason": exc.args[0]})
                continue
            except (UnicodeError, ValueError, RecursionError, csv.Error):
                files.append({"input_sha256": fingerprint, "output": None,
                              "status": "quarantined", "reason": "invalid_input"})
                continue
        target = sanitized / destination
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(rendered_bytes)
        used_files.add(destination)
        used_dirs.update(parents)
        path = "sanitized/" + destination.as_posix()
        files.append({"input_sha256": fingerprint, "output": path, "status": "sanitized"})
        for locator in locators:
            key = (path, locator)
            records[key] = locator in rewrite.generalized
            if locator in rewrite.row_evidence:
                evidence[key] = rewrite.row_evidence[locator]
        counts["records_processed"] += len(locators)
        counts["records_generalized"] += len(rewrite.generalized)
        counts["files_sanitized"] += 1
        entities.update(rewrite.entities)
    linked = resolve_linkage(evidence, secret)
    # Rewrite only already-sanitized table cells. No original identifier is reopened.
    by_file = {}
    for key, patient in linked.items():
        path, locator = key
        row = int(locator.split(":", 1)[1])
        by_file.setdefault(path, {})[row] = (evidence[key].column, patient)
    for path, changes in by_file.items():
        apply_pseudonyms(output / path, changes)
    counts["records_linked"] = len(linked)
    with (output / "records.jsonl").open("w", encoding="utf-8") as stream:
        for (path, locator), generalized in records.items():
            entry = {"file": path, "loc": locator, "patient": linked.get((path, locator))}
            if generalized:
                entry["status"] = "generalized"
            stream.write(json.dumps(entry, ensure_ascii=True, sort_keys=True) + "\n")
    report = {
        "schema": "raksha-report/1",
        "files": files,
        "counts": {
            "files_total": len(files),
            "files_sanitized": counts["files_sanitized"],
            "files_quarantined": len(files) - counts["files_sanitized"],
            "records_processed": counts["records_processed"],
            "identifiers_detected": sum(entities.values()),
            "records_linked": counts["records_linked"],
            "records_generalized": counts["records_generalized"],
            "records_suppressed": 0,
            "records_quarantined": 0,
        },
        "entities": entities,
        "timing": {"seconds": round(time.monotonic() - started, 3)},
        "resources": {"peak_rss_mb": round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss /
                                          (1048576 if sys.platform == "darwin" else 1024), 2)},
    }
    (output / "report.json").write_text(json.dumps(report, sort_keys=True) + "\n", encoding="utf-8")
    return report["counts"]


def publish_release(input_path, output_path, secret):
    if not input_path.is_dir():
        raise UnsafeInput("missing_input")
    if output_path.is_symlink():
        raise UnsafeInput("output_symlink")
    input_path, output_path = input_path.resolve(), output_path.resolve()
    if output_path.is_relative_to(input_path) or input_path.is_relative_to(output_path):
        raise UnsafeInput("overlapping_paths")
    if output_path.exists() and (not output_path.is_dir() or any(output_path.iterdir())):
        raise UnsafeInput("nonempty_output")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix=".rakshak-", dir=output_path.parent))
    try:
        counts = build_release(input_path, stage, secret)
        stage.rename(output_path)
        return counts
    finally:
        if stage.exists():
            shutil.rmtree(stage)
