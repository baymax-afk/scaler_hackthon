"""Verify Secret Wards v3 fixture bytes and evaluator truth using only the stdlib."""

import argparse
import csv
import hashlib
import io
import json
import re
import unicodedata
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path


KINDS = ("discharge", "prescription", "nursing")
STYLES = ("latin", "devanagari", "code_switched")
ACTIONS = {"REMOVE", "PRESERVE", "SHIFT", "GENERALIZE"}
IDENTIFIER_ROLES = {"patient_id", "local_id", "mrn", "record_id", "chart_number"}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def decode(data):
    return data.decode("utf-16" if data.startswith((b"\xff\xfe", b"\xfe\xff")) else "utf-8-sig")


def normalize(text):
    return "".join(c for c in unicodedata.normalize("NFKC", text).casefold()
                   if unicodedata.category(c)[0] in "LMN")


def pointer_parts(pointer):
    require(isinstance(pointer, str) and (pointer == "" or pointer.startswith("/")),
            f"Invalid JSON Pointer {pointer!r}")
    require(not re.search(r"~(?![01])", pointer), f"Invalid JSON Pointer escape {pointer}")
    return tuple(part.replace("~1", "/").replace("~0", "~") for part in pointer.split("/")[1:])


def parse_files(payloads, malformed):
    parsed = {}
    for path, data in payloads.items():
        if path in malformed:
            continue
        suffix = Path(path).suffix.lower()
        source = decode(data)
        if suffix == ".json":
            parsed[path] = json.loads(source)
        elif suffix in {".csv", ".tsv"}:
            reader = csv.DictReader(io.StringIO(source, newline=""), delimiter="\t" if suffix == ".tsv" else ",")
            require(reader.fieldnames and len(set(reader.fieldnames)) == len(reader.fieldnames),
                    f"{path}: missing or duplicate table headers")
            parsed[path] = list(reader)
            require(not any(None in row or None in row.values() for row in parsed[path]),
                    f"{path}: irregular row width")
        else:
            parsed[path] = source
    return parsed


def resolve(value, locator, label=False):
    keys = set(locator)
    if keys == {"document"} and not label and locator["document"] is True:
        return value
    if keys == {"pointer"}:
        for part in pointer_parts(locator["pointer"]):
            if isinstance(value, list):
                require(re.fullmatch(r"0|[1-9][0-9]*", part), f"Invalid JSON array index {part!r}")
                value = value[int(part)]
            else:
                value = value[part]
        return value
    if keys == ({"row", "column"} if label else {"row"}):
        require(type(locator["row"]) is int and locator["row"] >= 0, f"Invalid row locator {locator}")
        row = value[locator["row"]]
        return row[locator["column"]] if label else row
    if label and keys == {"start", "end"}:
        start, end = locator["start"], locator["end"]
        require(type(start) is int and type(end) is int and isinstance(value, str)
                and 0 <= start < end <= len(value), f"Invalid Unicode span {locator}")
        return value[start:end]
    raise ValueError(f"Unsupported locator {locator}")


def is_valid_json(data):
    try:
        json.loads(decode(data))
    except (ValueError, UnicodeError, RecursionError):
        return False
    return True


def malformed_signatures(data, path):
    failures = set()
    if not data:
        failures.add("empty")
    try:
        decode(data)
    except UnicodeError:
        failures.add("encoding")
    suffix = Path(path).suffix.lower()
    if suffix == ".json" and not is_valid_json(data):
        failures.add("json")
    if suffix in {".csv", ".tsv"} and "encoding" not in failures:
        try:
            list(csv.reader(io.StringIO(decode(data)), strict=True, delimiter="\t" if suffix == ".tsv" else ","))
        except csv.Error:
            failures.add("table")
    if suffix not in {".txt", ".json", ".csv", ".tsv"}:
        failures.add("unsupported")
    return failures


def verify_malformed(payloads, claims):
    report = Counter()
    names = set()
    for fixture in claims:
        path, reason = fixture["file"], fixture["reason"]
        lowered = reason.casefold()
        require(path not in names, f"Duplicate malformed file {path}")
        observed = malformed_signatures(payloads[path], path)
        expected = ("empty" if "empty" in lowered or "zero" in lowered else
                    "encoding" if any(word in lowered for word in ("utf", "encoding", "byte")) else
                    "table" if "csv" in lowered or "tsv" in lowered else
                    "json" if any(word in lowered for word in ("json", "truncat")) else
                    "unsupported" if "unsupported" in lowered else None)
        require(expected in observed, f"{path}: expected malformed {reason!r}, observed {sorted(observed)}")
        names.add(path)
        report[reason] += 1
    return names, report


def unique_dict(items, key, name):
    result = {item[key]: item for item in items}
    require(len(result) == len(items), f"Duplicate {name}")
    return result


def canonical_value(value):
    if type(value) in (int, float):
        return str(value)
    if not isinstance(value, str):
        return value
    return "".join(str(unicodedata.digit(c)) if c.isdecimal() else c
                   for c in unicodedata.normalize("NFKC", value)).strip()


def check_rendered_fact(observed, canonical, role):
    display, base = canonical_value(observed), canonical_value(canonical)
    if display == base:
        return True
    if role in {"admission_date", "visit_date", "discharge_date", "encounter_date", "birth_date", "dob"}:
        return False
    if role in {"dose", "pulse", "length_of_stay", "blood_pressure", "bp", "lab_value"}:
        number = re.compile(r"\d+(?:\.\d+)?")
        if number.findall(display) != number.findall(base):
            return False
        if role == "dose":
            def unit(value):
                token = normalize(number.sub("", value))
                return {"मिग्रा": "mg", "मिली": "ml"}.get(token, token)
            return unit(display) == unit(base)
    return True


def coverage_and_contrasts(records, labels_by_file, parsed):
    matrix = defaultdict(list)
    contrasts = Counter()
    profiles = []
    for record in records.values():
        if record["kind"] not in KINDS:
            continue
        path, style = record["file"], record["style"]
        source = parsed[path]
        require(style in STYLES and isinstance(source, str), f"{path}: invalid note type or style")
        has_deva = bool(re.search(r"[\u0900-\u097f]", source))
        require(has_deva if style != "latin" else not has_deva, f"{path}: script disagrees with style")
        if style == "code_switched":
            require(any(re.search(r"[\u0900-\u097f]", line) and re.search(r"[A-Za-z]{2,}", line)
                        for line in source.splitlines()), f"{path}: code switch missing within line")
        heading, layout = record["heading"], record["layout"]
        require(heading is None or heading in source.splitlines(), f"{path}: heading absent from rendered note")
        require(isinstance(layout, str) and layout.strip(), f"{path}: missing layout")
        matrix[(record["kind"], style)].append((heading, layout))
        labels = labels_by_file[path]
        removing = [item for item in labels if item["action"] == "REMOVE"]
        keeping = [item for item in labels if item["action"] == "PRESERVE"]
        clean = all(item["action"] == "PRESERVE" for item in labels)
        if record.get("clean") is True:
            require(clean and keeping, f"{path}: clean control contains protected data or lacks probes")
        if clean and keeping:
            contrasts["clean_notes"] += 1
        patients = [item["surface"] for item in removing if item["role"] == "patient_name"]
        clinicians = [item["surface"] for item in keeping if item["role"] == "clinician_name"]
        same_name = bool(set(patients) & set(clinicians))
        if same_name:
            contrasts["same_name_notes"] += 1
        ids = {canonical_value(item["surface"]) for item in removing if item["role"] in IDENTIFIER_ROLES}
        quantities = set()
        for item in keeping:
            if item["role"] != "dose":
                continue
            match = re.search(r"(?<![\d.])(\d+(?:\.\d+)?)(?=\s*[^\W\d_])",
                              canonical_value(item["surface"]))
            if match:
                quantities.add(match.group(1))
        id_dose = bool(ids & quantities)
        if id_dose:
            contrasts["id_dose_notes"] += 1
        related = [item for item in removing if item["role"] in {"relationship_name", "contact_name",
                                                                 "relative_name", "identifying_contact"}]
        clinical = [item for item in keeping if item["role"] in {"complaint", "clinical_complaint"}]
        repeated_shorthand = False
        if re.search(r"\bC/O\b", source, re.I) and related and clinical:
            def with_shorthand(items):
                return any(re.search(r"\bC/O\s*[:=]?\s*$", source[max(0, item["locator"]["start"]-12):
                                                                        item["locator"]["start"]], re.I)
                           or re.match(r"C/O\b", item["surface"], re.I) for item in items)
            repeated_shorthand = with_shorthand(related) and with_shorthand(clinical)
            if repeated_shorthand:
                contrasts["c_o_notes"] += 1
        profiles.append({"path": path, "heading": heading, "layout": layout, "script": style,
                         "has_remove": bool(removing),
                         "contextual_contrast": same_name or id_dose or repeated_shorthand})
    output = {}
    for kind in KINDS:
        for style in STYLES:
            values = matrix[kind, style]
            headings, layouts = {h for h, _ in values}, {p for _, p in values}
            require(len(headings - {None}) >= 2 and len(layouts) >= 2 and None in headings,
                    f"Missing heading/layout variety in {kind}/{style}")
            require(any(len({p for h2, p in values if h2 == h}) > 1 for h in headings)
                    and any(len({h for h, p2 in values if p2 == p}) > 1 for p in layouts),
                    f"Heading and layout are coupled in {kind}/{style}")
            output[f"{kind}/{style}"] = {
                "notes": len(values), "named_headings": len(headings - {None}),
                "headingless": sum(h is None for h, _ in values), "layouts": len(layouts),
                "heading_layout_pairs": len(set(values)),
            }
    return output, contrasts, profiles


def majority(values):
    return Counter(values).most_common(1)[0][0]


def shortcut_scores(profiles, target):
    def filename_features(row):
        path = row["path"]
        name = Path(path)
        return name.parent.as_posix(), re.sub(r"[0-9a-fA-F]{6,}|\d+", "#", name.name)

    keys = {"filename_shape": filename_features,
            "heading_only": lambda row: row["heading"],
            "layout_only": lambda row: row["layout"],
            "script_only": lambda row: row["script"]}
    # Split by a hash of the path, then fit majority lookup tables on four folds.
    results = {}
    for name, feature in keys.items():
        correct = true_positive = true_negative = positives = negatives = unseen = total = 0
        for fold in range(5):
            train, test = [], []
            for row in profiles:
                part = int(digest(row["path"].encode())[:8], 16) % 5
                (test if part == fold else train).append(row)
            fallback = majority(row[target] for row in train)
            labels = defaultdict(list)
            for row in train:
                labels[feature(row)].append(row[target])
            for row in test:
                key = feature(row)
                expected = row[target]
                prediction = majority(labels[key]) if key in labels else fallback
                unseen += key not in labels
                positives += expected
                negatives += not expected
                true_positive += prediction and expected
                true_negative += not prediction and not expected
                correct += prediction == expected
                total += 1
        results[name] = {"correct": correct, "tested": total,
                         "balanced_accuracy": round((true_positive/positives + true_negative/negatives)/2, 4)
                         if positives and negatives else None,
                         "majority_baseline_correct": max(positives, negatives), "unseen_features": unseen}
    return results


def row_order_score(records):
    reg, lab = defaultdict(dict), defaultdict(dict)
    for record in records.values():
        if record["kind"] not in {"registration", "lab"} or not record["patient"]:
            continue
        locator = record["locator"]
        idx = locator.get("row")
        if "pointer" in locator:
            tail = pointer_parts(locator["pointer"])[-1:]
            if tail and tail[0].isdigit():
                idx = int(tail[0])
        if idx is not None:
            bucket = reg if record["kind"] == "registration" else lab
            require(idx not in bucket[record["file"]], f"Duplicate physical ordinal in {record['file']}")
            bucket[record["file"]][idx] = record["patient"]
    correct = predicted = actual = 0
    for registrations in reg.values():
        for labs in lab.values():
            actual += sum(Counter(registrations.values())[patient] for patient in labs.values())
            for rank in registrations.keys() & labs.keys():
                predicted += 1
                correct += registrations[rank] == labs[rank]
    return {"correct": correct, "predicted_same_ordinal_pairs": predicted, "actual_patient_pairs": actual,
            "precision": round(correct/predicted, 4) if predicted else None,
            "recall": round(correct/actual, 4) if actual else None}


def verify_split(root):
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8-sig"))
    actual = {path.relative_to(root).as_posix(): path.read_bytes()
              for path in root.rglob("*") if path.is_file() and path != root / "manifest.json"}
    require(manifest["sha256"] == {path: digest(data) for path, data in actual.items()},
            f"{root}: manifest file inventory or hash mismatch")
    truth = json.loads(decode(actual["truth/fixtures.json"]))
    payloads = {path.removeprefix("input/"): data for path, data in actual.items() if path.startswith("input/")}
    malformed, malformed_counts = verify_malformed(payloads, truth["malformed"])
    parsed = parse_files(payloads, malformed)
    patients = unique_dict(truth["patients"], "id", "patient")
    records = unique_dict(truth["records"], "id", "record")
    events = unique_dict(truth["events"], "id", "event")
    allowed_names = {patient: {normalize(value) for value in entry["names"]}
                     for patient, entry in patients.items()}
    all_names = set().union(*allowed_names.values())
    chronology = 0
    for event in events.values():
        require(event["patient"] in patients, f"Unknown patient on {event['id']}")
        dates = event["facts"]
        admission, discharge = dates.get("admit", dates.get("admitted")), dates.get("discharge", dates.get("date"))
        if admission is not None and discharge is not None:
            length = (date.fromisoformat(discharge) - date.fromisoformat(admission)).days
            require(length >= 0 and ("stay" not in dates or dates["stay"] == length),
                    f"Reversed or inconsistent visit dates on {event['id']}")
            chronology += 1
        for role in ("dose", "bp"):
            if role in dates and role + "_hi" in dates:
                require(check_rendered_fact(dates[role + "_hi"], dates[role], role),
                        f"Cross-script clinical quantity/unit mismatch on {event['id']} / {role}")
        if event.get("prior_event") is not None:
            prior = events[event["prior_event"]]
            prior_discharge = prior["facts"]["discharge"]
            require(prior["patient"] == event["patient"] and prior_discharge == dates["prior_discharge"]
                    and date.fromisoformat(prior_discharge) < date.fromisoformat(dates["admit"]),
                    f"Inconsistent follow-up chronology on {event['id']}")
            chronology += 1
    by_file = defaultdict(list)
    record_locations = set()
    for rec in records.values():
        path = rec["file"]
        resolve(parsed[path], rec["locator"])
        location = path, json.dumps(rec["locator"], sort_keys=True)
        require(location not in record_locations, f"Duplicate record locator {location}")
        record_locations.add(location)
        require(rec["patient"] is None or rec["patient"] in patients, f"Unknown patient on {rec['id']}")
        require(rec["event"] is None or events[rec["event"]]["patient"] == rec["patient"],
                f"Wrong-event patient on {rec['id']}")
        by_file[path].append(rec)
    require(set(by_file) == set(parsed), f"Files without records: {sorted(set(parsed)-set(by_file))}")
    labels_by_file = defaultdict(list)
    labels_by_record = defaultdict(list)
    checked_facts = defaultdict(set)
    structured = defaultdict(set)
    verified_fact_labels = 0
    spans = defaultdict(list)
    actions = Counter()
    for label in truth["labels"]:
        path, loc, expected = label["file"], label["locator"], label["surface"]
        observed = resolve(parsed[path], loc, label=True)
        require(type(expected) is type(observed) and expected == observed and expected not in ("", None),
                f"{path}: stale or empty label at {loc}")
        require(label["action"] in ACTIONS and label["role"], f"{path}: invalid action or role")
        actions[label["action"]] += 1
        if "start" in loc:
            spans[path].append((loc["start"], loc["end"]))
            owner = by_file[path]
        else:
            if "pointer" in loc:
                parts = pointer_parts(loc["pointer"])
                key = ("pointer", *parts)
                owner = [rec for rec in by_file[path]
                         if rec["locator"] == {"document": True}
                         or ("pointer" in rec["locator"] and
                             parts[:len(pointer_parts(rec["locator"]["pointer"]))] ==
                             pointer_parts(rec["locator"]["pointer"]))]
            else:
                key = ("row", loc["row"], loc["column"])
                owner = [rec for rec in by_file[path] if rec["locator"].get("row") == loc["row"]]
            require(key not in structured[path], f"{path}: duplicate structured locator {loc}")
            structured[path].add(key)
        require(len(owner) == 1, f"{path}: label at {loc} maps to {len(owner)} records")
        if label["role"] == "patient_name" and label["action"] == "REMOVE":
            name = normalize(expected)
            all_names.add(name)
            if owner[0]["patient"] is not None:
                require(name in allowed_names[owner[0]["patient"]], f"{path}: patient name absent from alias inventory")
        require(("fact" in label) == ("event" in label), f"{path}: incomplete event fact backreference")
        if "fact" in label:
            event = events[label["event"]]
            fact = label["fact"]
            current = events.get(owner[0]["event"], {})
            require(event["id"] in (current.get("id"), current.get("prior_event")) and
                    event["patient"] == owner[0]["patient"], f"{path}: label references an unrelated event")
            canonical = label.get("canonical", observed)
            require(canonical_value(event["facts"][fact]) == canonical_value(canonical),
                    f"{path}: clinical or date value differs from event {event['id']} / {fact}")
            require(check_rendered_fact(observed, canonical, label["role"]),
                    f"{path}: displayed date or number disagrees with canonical {fact}")
            verified_fact_labels += 1
            checked_facts[event["id"], fact].add(path)
        labels_by_file[path].append(label)
        labels_by_record[owner[0]["id"]].append(label)
    for path, intervals in spans.items():
        ordered = sorted(intervals)
        require(all(prior[1] <= current[0] for prior, current in zip(ordered, ordered[1:])),
                f"{path}: overlapping UTF-8 spans")
    for path, locs in structured.items():
        for loc in locs:
            require(not any(loc[:i] in locs for i in range(1, len(loc))),
                    f"{path}: ancestor/descendant structured labels overlap")
    require(set(labels_by_file) == set(parsed), f"Unlabeled supported inputs: {sorted(set(parsed)-set(labels_by_file))}")
    link_counts, seen_pairs = Counter(), set()
    corroborated = Counter()
    ambiguous = set()
    for edge in truth["links"]:
        left, right = records[edge["left"]], records[edge["right"]]
        pair = frozenset((left["id"], right["id"]))
        require(len(pair) == 2 and pair not in seen_pairs and edge["evidence"].strip(), "Invalid or duplicate link pair")
        seen_pairs.add(pair)
        a, b = left["patient"], right["patient"]
        expected = edge["expected"]
        if expected == "LINK":
            require(a is not None and a == b, f"Positive edge between different identities: {edge}")
            def visible(record, roles):
                return {canonical_value(item.get("canonical", item["surface"]))
                        for item in labels_by_record[record["id"]] if item["role"] in roles}
            roles = IDENTIFIER_ROLES | {"phone", "birth_date", "dob"}
            shared_anchor = bool(visible(left, roles) & visible(right, roles))
            named_both = bool(visible(left, {"patient_name"}) and visible(right, {"patient_name"}))
            timing = {"encounter_date", "visit_date", "admission_date", "discharge_date"}
            shared_date = bool(visible(left, timing) & visible(right, timing))
            corroborated["link_with_shared_identifier_contact_or_dob"] += shared_anchor
            corroborated["link_with_name_on_both_and_shared_date"] += named_both and shared_date
            if edge.get("cross_script"):
                corroborated["cross_script_with_visible_name_and_shared_anchor_or_date"] += (
                    named_both and (shared_anchor or shared_date))
        elif expected == "NON_LINK":
            require(a is not None and b is not None and a != b, f"Negative edge without distinct identities: {edge}")
        elif expected == "ABSTAIN":
            candidates = [record["id"] for record in (left, right) if record["patient"] is None
                          or any("ambig" in flag or "fragment" in flag for flag in record.get("stress", []))]
            require(candidates, f"Abstention edge lacks ambiguous or unidentified record: {edge}")
            ambiguous.update(candidates)
        else:
            raise ValueError(f"Unknown linkage expectation {expected!r}")
        link_counts[expected] += 1
        if edge.get("cross_script") and expected == "LINK":
            require(left.get("style") and right.get("style") and left["style"] != right["style"],
                    f"Invalid true cross-script edge: {edge}")
            link_counts["cross_script_true_links"] += 1
    for must_exist in ("LINK", "NON_LINK", "ABSTAIN", "cross_script_true_links"):
        require(link_counts[must_exist], f"Missing expected link coverage: {must_exist}")
    matrix, contrasts, profiles = coverage_and_contrasts(records, labels_by_file, parsed)
    for contrast in ("same_name_notes", "id_dose_notes", "c_o_notes", "clean_notes"):
        require(contrasts[contrast], f"Missing visible contrast or control: {contrast}")
    measured = {"input_files": len(payloads), "patients": len(patients), "events": len(events),
                "records": len(records), "labels": len(truth["labels"]), "links": len(truth["links"]),
                "malformed": len(malformed)}
    for key, value in measured.items():
        if key in manifest["counts"]:
            require(manifest["counts"][key] == value, f"Wrong manifest count for {key}")
    stress = Counter(flag for record in records.values() for flag in record.get("stress", []))
    report = {"split": root.name, **measured, "coverage": matrix, "visible_contrasts": dict(contrasts),
              "stress_flags": dict(stress), "label_actions": dict(actions),
              "span_errors": 0, "overlapping_labels": 0,
              "linkage": dict(link_counts), "ambiguous_records": len(ambiguous),
              "visible_link_corroboration": dict(corroborated),
              "verified_event_fact_labels": verified_fact_labels,
              "facts_in_multiple_documents": sum(len(paths) > 1 for paths in checked_facts.values()),
              "event_date_order_checks": chronology, "malformed_counts": dict(malformed_counts),
              "document_remove_shortcuts": shortcut_scores(profiles, "has_remove"),
              "contextual_contrast_shortcuts": shortcut_scores(profiles, "contextual_contrast"),
              "structured_row_order": row_order_score(records)}
    note_hashes = {digest(payloads[rec["file"]]) for rec in records.values()
                   if rec["locator"] == {"document": True} and Path(rec["file"]).suffix.lower() == ".txt"}
    return report, (set(patients), all_names, note_hashes)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("roots", nargs="+", type=Path)
    parser.add_argument("--json", action="store_true", help="emit a machine-readable report")
    args = parser.parse_args()
    if len(args.roots) > 2:
        parser.error("provide one or two split roots")
    try:
        results = [verify_split(root) for root in args.roots]
        report = {"splits": [result[0] for result in results]}
        if len(results) == 2:
            metrics = ("patient_ids", "normalized_patient_name_surfaces", "duplicate_note_hashes")
            overlap = {metric: len(a & b) for metric, a, b in zip(metrics, results[0][1], results[1][1])}
            require(not any(overlap.values()), f"Split overlap detected: {overlap}")
            report["split_overlap"] = overlap
    except (KeyError, IndexError, TypeError, ValueError, OSError) as exc:
        parser.exit(1, f"Verification failed: {exc}\n")
    if args.json:
        print(json.dumps(report, ensure_ascii=True, indent=2))
    else:
        for split in report["splits"]:
            print(f"{split['split']}: verified {split['input_files']} inputs, {split['records']} records, "
                  f"{split['labels']} exact labels, {split['links']} linkage pairs")
        if "split_overlap" in report:
            print("Cross-split patient IDs, normalized name surfaces, duplicate notes: 0")


if __name__ == "__main__":
    main()
