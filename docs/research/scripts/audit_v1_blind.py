"""Replay the original record-level synthetic regression audit from repo root."""
import base64
from collections import Counter, defaultdict
import csv
from datetime import date
from functools import lru_cache
from hashlib import sha256
import io
import json
from pathlib import Path
import re
import sys
import unicodedata

dataset = Path(sys.argv[1])
release = Path(sys.argv[2])
sys.path.insert(0, str(Path.cwd() / "submission"))
from rakshak.formats import decode

truth = json.loads((dataset / "truth/fixtures.json").read_text())
manifest = json.loads((dataset / "manifest.json").read_text())
report = json.loads((release / "report.json").read_text())
inputs = dataset / "input"
reports = defaultdict(list)
for item in report["files"]:
    reports[item["input_sha256"]].append(item)
mapped = {}
for path, digest in sorted(manifest["files"].items()):
    assert sha256((inputs / path).read_bytes()).hexdigest() == digest
    mapped[path] = reports[digest].pop(0)
assert not any(reports.values())


def fold(text):
    folded = unicodedata.normalize("NFKC", text).casefold()
    return " ".join("".join(c for c in folded if unicodedata.category(c) != "Cf").split())


def digits(value):
    return "".join(str(unicodedata.decimal(c)) for c in value if c.isdecimal())


def text_values(value):
    if isinstance(value, str) or type(value) is int:
        yield str(value)
    elif isinstance(value, list):
        for item in value:
            yield from text_values(item)
    elif isinstance(value, dict):
        if "FirstName" in value and "LastName" in value:
            yield value["FirstName"] + " " + value["LastName"]
        for key, item in value.items():
            if key == "data" and value.get("contentType", "").lower().startswith("text/plain"):
                yield base64.b64decode(item, validate=True).decode("utf-8")
            else:
                yield from text_values(item)


@lru_cache
def load(path, loc_kind):
    text = decode(path.read_bytes())
    if loc_kind == "row":
        return list(csv.DictReader(io.StringIO(text, newline=""),
                                   delimiter="\t" if path.suffix == ".tsv" else ","))
    return json.loads(text) if path.suffix == ".json" else text


def unit(path, loc):
    kind = "row" if loc.startswith("row:") else "other"
    item = load(path, kind)
    if kind == "row":
        return item[int(loc.split(":")[1])]
    if loc.startswith("/"):
        for segment in loc[1:].split("/"):
            key = segment.replace("~1", "/").replace("~0", "~")
            item = item[int(key)] if isinstance(item, list) else item[key]
    return item


def visible(kind, label, values):
    if kind in {"phone", "aadhaar"}:
        expected = digits(label)
        # Treat 10-digit, zero-prefixed and Indian-country-code representations as equivalent.
        variants = {expected}
        if kind == "phone" and len(expected) == 12 and expected.startswith("91"):
            variants.add(expected[2:])
        if kind == "phone" and len(expected) == 11 and expected.startswith("0"):
            variants.add(expected[1:])
        for value in values:
            for match in re.finditer(r"\+?\d(?:[ .()\t-]?\d){6,16}", value):
                observed = digits(match[0])
                if observed in variants or (
                    len(observed) == 12 and observed.startswith("91") and observed[2:] in variants
                ) or (len(observed) == 11 and observed.startswith("0") and observed[1:] in variants):
                    return True
        return False
    expected = fold(label)
    return any(expected in fold(value) for value in values)


def dates_of(record, item):
    if isinstance(item, dict) and item.get("resourceType") == "Bundle":
        composition = next(row["resource"] for row in item["entry"]
                           if row["resource"]["resourceType"] == "Composition")
        return {"admission": composition["date"][:10]}
    if isinstance(item, str):
        return {field: re.search(r"(?m)^" + field.title() + r": (\d{4}-\d\d-\d\d)\r?$", item)[1]
                for field in ("admission", "discharge")}
    keys = ("Admission", "Discharge") if "Admission" in item else ("भर्ती", "छुट्टी")
    return dict(zip(("admission", "discharge"), (item[key] for key in keys)))


def equals_date(expected, observed):
    parsed = date.fromisoformat(expected)
    return observed in {parsed.isoformat(), parsed.strftime("%m/%d/%Y"), parsed.strftime("%d/%m/%Y")}


total = Counter()
formats = defaultdict(Counter)
scripts = defaultdict(Counter)
kinds = defaultdict(Counter)
index = {(row["file"], row["loc"]): row["patient"] for row in map(json.loads,
         (release / "records.jsonl").read_text().splitlines())}
expected_index = set()
exceptions = []
for record in truth["records"]:
    name, loc = record["file"], record["loc"]
    source = unit(inputs / name, loc)
    mapping = mapped[name]["output"]
    if mapping is None:
        raise AssertionError("record from quarantined file")
    target = unit(release / mapping, loc)
    source_values = list(text_values(source))
    target_values = list(text_values(target))
    label = "FHIR" if name.startswith("fhir/") else Path(name).suffix.removeprefix(".").upper()
    buckets = [total, formats[label], scripts[record["script"]]]
    expected_index.add((mapping, loc))
    changes = 0
    leaks = 0
    for kind, value in record["identifiers"].items():
        source_contains = visible(kind, value, source_values)
        output_contains = visible(kind, value, target_values + [mapping])
        for bucket in [*buckets, kinds[kind]]:
            bucket.update(identifier_labels=1, source_present=source_contains, output_visible=output_contains)
        leaks += output_contains
        if not source_contains or output_contains:
            exceptions.append((label, record["script"], kind, source_contains, output_contains))
    for probe in record["preserve"]:
        source_contains = any(probe in value for value in source_values)
        output_contains = any(probe in value for value in target_values)
        for bucket in buckets:
            bucket.update(clinical_probes=1, source_clinical=source_contains,
                          output_clinical=output_contains)
        changes += not output_contains
        if not source_contains or not output_contains:
            exceptions.append((label, record["script"], "clinical", source_contains, output_contains))
    source_dates = dates_of(record, source)
    target_dates = dates_of(record, target)
    for key, observed in source_dates.items():
        assert equals_date(record["dates"][key], observed)
        for bucket in buckets:
            bucket.update(observed_date_fields=1, date_fields_unchanged=target_dates[key] == observed)
    for bucket in buckets:
        bucket.update(records=1, clinical_clean_records=not changes, identifier_clean_records=not leaks,
                      both_clean=not changes and not leaks, index_present=(mapping, loc) in index,
                      records_linked=index.get((mapping, loc)) is not None)
    if isinstance(source, dict) and label in {"CSV", "TSV", "JSON"}:
        old_id_key = next((key for key in ("Aadhaar", "AadhrNo") if key in source), None)
        if old_id_key and source[old_id_key]:
            total.update(structured_aadhaar_fields=1,
                         structured_aadhaar_removed=not visible("aadhaar", str(source[old_id_key]), target_values))
    if label != "FHIR":
        age_key = "Age" if isinstance(source, dict) and "Age" in source else "उम्र"
        original_age = source[age_key] if isinstance(source, dict) else re.search(r"(?m)^Age: ([0-9]+)", source)[1]
        released_age = target.get(age_key) if isinstance(target, dict) else re.search(r"(?m)^Age: ([0-9]+)", target)[1]
        total.update(age_fields=1, age_unchanged=original_age == released_age)
    if label in {"CSV", "TSV", "JSON"} and "phone" not in record["identifiers"]:
        keys = ("Mobile", "Email") if "Mobile" in target else ("फ़ोन", "ईमेल")
        total.update(empty_contact_fields=2, empty_contacts_kept=sum(target[key] == "" for key in keys))

all_output = "\n".join(
    path.relative_to(release).as_posix() + "\n" + path.read_text()
    for path in release.rglob("*") if path.is_file()
)
all_output += "\n" + "\n".join(
    item for (name, loc) in expected_index for item in
    (text_values(unit(release / name, loc)) if name.startswith("sanitized/fhir/") else [])
)
patient_counts = Counter(item["patient"] for item in truth["records"])
same_patient_pairs = sum(n * (n - 1) // 2 for n in patient_counts.values())
linked_groups = Counter()
for record in truth["records"]:
    prediction = index.get((mapped[record["file"]]["output"], record["loc"]))
    if prediction is not None:
        linked_groups[(record["patient"], prediction)] += 1
linked_pairs = sum(n * (n - 1) // 2 for n in linked_groups.values())
print(json.dumps({
    "linkage": {"synthetic_patients": len(patient_counts),
                "patients_with_multiple_records": sum(n > 1 for n in patient_counts.values()),
                "same_patient_pairs": same_patient_pairs, "linked_pairs": linked_pairs},
    "extra_index_output_types": [name.split("/")[1] for name, _ in index.keys() - expected_index],
    "totals": total, "formats": formats, "scripts": scripts, "kinds": kinds,
    "exceptions": dict((str(k), v) for k,v in Counter(exceptions).items()),
    "canaries_visible": sum(fold(c) in fold(all_output) for c in truth["canaries"]),
    "canaries": len(truth["canaries"]),
    "unlabeled_misc": {name: item.get("reason", item["status"])
                       for name, item in mapped.items() if name.startswith(("misc/", "clean/"))},
    "extra_index_entries": len(index.keys() - expected_index),
    "clean_control_byte_equal": (inputs / "clean/ward_protocol.txt").read_bytes() ==
        (release / mapped["clean/ward_protocol.txt"]["output"]).read_bytes(),
}, indent=2, ensure_ascii=False, sort_keys=True))
