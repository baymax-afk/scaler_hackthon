"""Render the two open robustness_v2 splits. No sealed generator lives here."""
import argparse
import base64
from collections import Counter, defaultdict
import csv
from dataclasses import dataclass
from datetime import date, timedelta
from hashlib import sha256
from pathlib import Path
from random import Random
from uuid import NAMESPACE_URL, uuid5
from xml.sax.saxutils import escape
import json

VERSION = "robustness_v2-open/1"
SEED = 20261127
FORMATS = {
    "development": {"csv": 200, "tsv": 150, "json": 200, "fhir": 200, "txt": 250},
    "validation": {"csv": 80, "tsv": 60, "json": 80, "fhir": 80, "txt": 100},
}
SCENARIOS = {
    "institutions": (150, 60), "multilingual": (125, 50), "ambiguous": (125, 50),
    "messy": (125, 50), "nested": (125, 50), "longitudinal": (125, 50),
    "clinical_negatives": (125, 50), "combined": (100, 40),
}
FAMILIES = {
    "development": {
        "csv": (("rural-register", "rural-clinic"), ("billing-export", "insurer")),
        "tsv": (("bench-results", "diagnostics"), ("ward-transfer", "government")),
        "json": (("video-intake", "telemedicine"), ("pathology-order", "pathology")),
        "fhir": (("visit-collection", "private"), ("lab-collection", "laboratory")),
        "txt": (("triage-card", "emergency"), ("family-dialogue", "outreach"),
                ("prescriber-log", "specialist")),
    },
    "validation": {
        "csv": (("referral-csv", "referral-centre"),),
        "tsv": (("imaging-worklist", "radiology"),),
        "json": (("pediatric-review", "child-health"),),
        "fhir": (("document-archive", "teaching-hospital"),),
        "txt": (("discharge-letter", "rehabilitation"), ("aftercare-call", "home-care")),
    },
}
# Invented names are used as synthetic labels. Contact values cannot be dialed
# or resolved. Local identifiers are visibly namespaced as synthetic.
NAMES = {
    "en": (("Aviren", "Mevani", "Nilaya", "Rinav", "Vasira"),
           ("Nerlath", "Velmora", "Tamren", "Kelath", "Meldur", "Harivar")),
    "hi": (("अविरन", "मेवानी", "निलाया", "रिनव", "वसिरा"),
           ("नेरलथ", "वेलमोरा", "तामरेन", "केलथ", "मेलदुर", "हरिवार")),
    "kn": (("ಅವಿರನ್", "ಮೇವಾನಿ", "ನಿಲಯಾ", "ರಿನವ್", "ವಸಿರಾ"),
           ("ನೆರಲಥ್", "ವೆಲ್ಮೋರಾ", "ತಾಮ್ರೆನ್", "ಕೆಲಥ್", "ಮೆಲ್ದೂರ್", "ಹರಿವಾರ್")),
    "ta": (("அவிரன்", "மேவானி", "நிலயா", "ரினவ்", "வசிரா"),
           ("நெரலத்", "வெல்மோரா", "தாம்ரென்", "கெலத்", "மெல்தூர்", "ஹரிவார்")),
}
LATIN_VARIANTS = ("en", "hi-Latn")
CLINICAL = (
    ("J45.9", "asthma", "salbutamol 100 mcg as needed"),
    ("I10", "hypertension", "amlodipine 5 mg once daily"),
    ("E11.9", "type 2 diabetes", "metformin 500 mg with meals"),
)
TEXT_PREFIX = {
    "en": "Patient",
    "hi": "रोगी",
    "hi-Latn": "Mareez ka naam",
    "kn": "ರೋಗಿಯ ಹೆಸರು",
    "ta": "நோயாளியின் பெயர்",
}


@dataclass(frozen=True)
class Span:
    surface: str
    kind: str


def identifier(surface, kind):
    return Span(surface, kind)


def protected(surface):
    return Span(surface, "PROTECT")


def text(*pieces):
    """Compose a field and record offsets from the emitted original text."""
    value = ""
    labels = []
    for piece in pieces:
        if isinstance(piece, Span):
            labels.append({"start": len(value), "end": len(value) + len(piece.surface),
                           "kind": piece.kind, "surface": piece.surface,
                           "expected": "preserve" if piece.kind == "PROTECT" else
                           "shift_patient_date" if piece.kind == "EVENT_DATE" else
                           "generalize_if_risk" if piece.kind == "AGE" else "transform"})
            value += piece.surface
        else:
            value += str(piece)
    return value, labels


def field(values, locator, *pieces, label="", representation="text"):
    value, spans = text(*pieces)
    values.append({"location": locator, "representation": representation,
                   "label": label, "spans": spans})
    return value


def opaque(*parts):
    return sha256(":".join(map(str, parts)).encode()).hexdigest()[:20]


def render_row(family, data, fields):
    p = data
    mapping = {
        "rural-register": ("ward chart", "settlement", "dose adjustment", "callback", "review date"),
        "billing-export": ("beneficiary", "claim member", "benefit code", "renewal mailbox", "admitted"),
        "bench-results": ("sample recipient", "local file", "lab trend", "reply channel", "collected at"),
        "ward-transfer": ("transfer for", "handover label", "ward observations", "home contact", "transfer date"),
        "referral-csv": ("Referred Subject", "Caretaker", "Referral rationale", "Secure reply to", "Review due"),
        "imaging-worklist": ("Subject on requisition", "Accession label", "Reading summary", "Reply channel", "Scheduled"),
    }
    labels = mapping[family]
    secondary = p["relative"] if family == "referral-csv" else p["mrn"]
    result = p["code"] if family == "billing-export" else p["clinical"]
    row = (
        field(fields, "0", p["name"], label=labels[0]),
        field(fields, "1", secondary, label=labels[1]),
        field(fields, "2", protected(result), label=labels[2]),
        field(fields, "3", p["mail"], label=labels[3]),
        field(fields, "4", p["date"], label=labels[4]),
        p["trace"],
    )
    if p["scenario"] in {"messy", "combined"}:
        row = row[:2] + (str(row[2]) + ', "rechecked"\nNo acute change',) + row[3:]
    return (*labels, "encounter token"), row


def render_json(family, p, fields):
    if family == "video-intake":
        return {
            "speakers": {"caller": field(fields, "/speakers/caller", p["name"]),
                         "reachable": field(fields, "/speakers/reachable", p["mail"])},
            "chat": [None, {"message": field(fields, "/chat/1/message", "Review in ",
                        protected("14 days"), " for ", protected(p["clinical"]))}],
            "chartAnchor": field(fields, "/chartAnchor", p["mrn"]),
            "seenOn": field(fields, "/seenOn", p["date"]), "encounterToken": p["trace"],
        }
    if family == "pathology-order":
        return {
            "requisition": {"onBehalfOf": field(fields, "/requisition/onBehalfOf", p["name"]),
                            "accessionOwner": field(fields, "/requisition/accessionOwner", p["mrn"])},
            "reply": {"inbox": field(fields, "/reply/inbox", p["mail"])},
            "microscopy": [{"interpretation": field(fields, "/microscopy/0/interpretation",
                                                     protected("No malignant cells seen"))}],
            "review": field(fields, "/review", p["date"]), "ticket": p["trace"],
        }
    return {
        "reviewedBy": {"guardian": field(fields, "/reviewedBy/guardian", p["relative"])},
        "subject": {"display": field(fields, "/subject/display", p["name"]),
                    "address": field(fields, "/subject/address", p["mail"])},
        "action/plan": {"~next": field(fields, "/action~1plan/~0next",
                                       protected("Reconcile current medicines"))},
        "history": [None, {"reviewDay": field(fields, "/history/1/reviewDay", p["date"])}],
        "reviewToken": p["trace"],
    }


def render_note(family, p, fields):
    name, relative = p["name"], p["relative"]
    mail, mrn = p["mail"], p["mrn"]
    prefix = TEXT_PREFIX[p["language"]]
    if p["scenario"] in {"messy", "combined"}:
        prefix += "\u00a0"
    date_span = p["date"]
    clinical = protected(p["clinical"])
    follow_up = protected("follow-up in 14 days")
    if family == "triage-card":
        pieces = ("Emergency triage card\n", prefix, " / ", name, "\nChart #", mrn,
                  "\nReviewed ", date_span, "\nClinical handover: ", clinical,
                  "\nReturn contact ", mail)
    elif family == "family-dialogue":
        pieces = ("Handover transcript\nFamily: I am ", relative, ". I came with ", name,
                  ".\nClinician: confirm ", clinical, ".\nSafe reply: ", mail)
    elif family == "prescriber-log":
        pieces = ("Prescription review\nSubject = ", name, "\nCode ", protected(p["code"]),
                  "\nContinue ", protected(p["drug"]), "; ", follow_up,
                  "\nReply-to ", mail)
    elif family == "discharge-letter":
        pieces = ("Discharge summary\nTo the receiving clinician,\n",
                  "Please review ", name, " on ", date_span, ".\nContinue ",
                  protected(p["drug"]), "; ", follow_up, ".\nReply via ", mail)
    else:
        pieces = ("Telephone follow-up\nDate of call: ", date_span, "\n", prefix, ": ", name,
                  "\nNo new red flags. Confirm ", follow_up, ".\nCallback ", mail)
    if p["scenario"] in {"ambiguous", "clinical_negatives", "combined"}:
        pieces += ("\nRelative: ", name, "\nDr. ", protected(name.surface),
                   " confirmed ", protected("BP 128/76 mmHg"), " and ",
                   protected("vitamin B12 1000 mcg"), ".")
    return field(fields, "doc", *pieces, "\nEncounter token: ", p["trace"], "\n")


def reference_url(trace, resource):
    return "urn:uuid:" + str(uuid5(NAMESPACE_URL, trace + "/" + resource))


def render_fhir(family, p, fields):
    token = p["trace"]
    resources = []

    def add(kind, **data):
        url = reference_url(token, kind)
        if kind != "Composition":
            resources.append({"fullUrl": url, "resource": {"resourceType": kind, **data}})
        else:
            resources.insert(0, {"fullUrl": url, "resource": {"resourceType": kind, **data}})
        return {"reference": url}

    patient_path = "/entry/1/resource" if family == "document-archive" else "/entry/0/resource"
    patient = add("Patient",
        name=[{"text": field(fields, patient_path + "/name/0/text", p["name"], label="patient name")}],
        telecom=[{"system": "email", "value": field(fields, patient_path + "/telecom/0/value",
                                                    p["mail"], label="email")}],
        identifier=[{"system": "https://charts.example.invalid",
                     "value": field(fields, patient_path + "/identifier/0/value",
                                    p["mrn"], label="patient identifier")}],
    )
    time = p["date"].surface + "T10:00:00+05:30"
    organization = add("Organization", name="Fictional " + family)
    practitioner = add("Practitioner", name=[{"text": "Dr. Elarin"}])
    if family == "lab-collection":
        observation = add("Observation", status="final", code={"text": "Pulse"},
                          subject=patient, effectiveDateTime=time,
                          valueQuantity={"value": p["pulse"], "unit": "beats/min"})
        add("DiagnosticReport", status="final", code={"text": "Clinical observations"},
            subject=patient, performer=[organization], result=[observation])
    else:
        add("Encounter", status="finished", subject=patient,
            **{"class": {"system": "http://terminology.hl7.org/CodeSystem/v3-ActCode", "code": "AMB"}},
            period={"start": time})
        if family == "visit-collection":
            related_index = len(resources)
            add("RelatedPerson", patient=patient,
                name=[{"text": field(fields, f"/entry/{related_index}/resource/name/0/text",
                                     p["relative"], label="relative name")}])
        else:
            report_index = len(resources) + 1
            attachment = field(fields, f"/entry/{report_index}/resource/content/0/attachment/data",
                               "Contact in archived note: ", p["mail"], "\nPlan: ",
                               protected(p["drug"]), representation="base64_utf8")
            document = add("DocumentReference", status="current", subject=patient,
                           author=[practitioner], content=[{"attachment": {
                               "contentType": "text/plain",
                               "data": base64.b64encode(attachment.encode()).decode(),
                           }}])
            add("Composition", status="final", type={"text": "Clinical review"},
                subject=patient, date=time, author=[practitioner], title="Clinical review",
                section=[{"title": "Review", "entry": [document]}])
    output = {"resourceType": "Bundle", "type": "collection", "entry": resources}
    if family == "document-archive":
        output.update(type="document", timestamp=time, identifier={
            "system": "https://bundles.example.invalid", "value": token})
    if p["scenario"] in {"nested", "combined"}:
        narrative = '<div xmlns="http://www.w3.org/1999/xhtml"><p>' + escape(p["name"].surface) + '</p></div>'
        resources[int(family == "document-archive")]["resource"]["text"] = {
            "status": "generated", "div": narrative,
        }
        start = narrative.index(escape(p["name"].surface))
        fields.append({"location": patient_path + "/text/div", "representation": "text",
                       "label": "", "spans": [{"start": start, "end": start + len(p["name"].surface),
                           "kind": "NAME", "surface": p["name"].surface, "expected": "transform"}]})
    if family == "lab-collection":
        field(fields, "/entry/3/resource/valueQuantity/value", protected(str(p["pulse"])),
              label="pulse", representation="scalar")
    return output


def plan(split, rng):
    scenarios = [scenario for scenario, counts in SCENARIOS.items()
                 for _ in range(counts[split == "validation"])]
    rng.shuffle(scenarios)
    rows = []
    for fmt, count in FORMATS[split].items():
        families = FAMILIES[split][fmt]
        for index in range(count):
            family, institution = families[index % len(families)]
            rows.append((fmt, family, institution, scenarios.pop()))
    # Build cross-format same-patient pairs by pairing across the shuffled
    # cohort only. Assign independent synthetic group IDs in the manifest.
    longitudinal = [index for index, row in enumerate(rows) if row[-1] == "longitudinal"]
    groups = {}
    while longitudinal:
        first = longitudinal.pop(0)
        different_format = next((i for i, other in enumerate(longitudinal)
                                 if rows[other][0] != rows[first][0]), None)
        if different_format is not None:
            groups[longitudinal.pop(different_format)] = first
    return rows, groups


def make_case(split, index, patient, scenario, fmt, rng):
    # Patient-derived attributes stay stable across linked encounters even as
    # scripts, encounter date, institution and chart IDs vary.
    patient_rng = Random(opaque(split, patient))
    languages = list(TEXT_PREFIX)
    language = rng.choice(languages if scenario in {"multilingual", "combined"} else languages[:3])
    variants = NAMES["en" if language in LATIN_VARIANTS else language]
    first, surname = (patient_rng.choice(options) for options in variants)
    name = surname + ", " + first[0] + "." if scenario in {"ambiguous", "combined"} else first + " " + surname
    if scenario == "messy":
        name = name.replace(" ", " \u200b" if fmt == "fhir" else "\u00a0")
    trace = opaque("encounter", split, index)
    address = opaque("contact", split, patient)[:10] + "@patient.example.invalid"
    code, clinical, drug = patient_rng.choice(CLINICAL)
    visit = date(2024, 1, 3) + timedelta(days=patient_rng.randrange(330) + (index != patient) * 14)
    return {"trace": trace, "scenario": scenario, "language": language,
            "name": identifier(name, "NAME"), "mrn": identifier("SYN-" + trace[:10], "MRN"),
            "relative": identifier(patient_rng.choice(variants[0]) + " " + surname, "RELATIVE"),
            "mail": identifier(address, "EMAIL"), "date": identifier(visit.isoformat(), "EVENT_DATE"),
            "code": code, "clinical": clinical, "drug": drug, "pulse": rng.randint(62, 98)}


def linkage_truth(records):
    by_patient = defaultdict(list)
    by_name = defaultdict(dict)
    for record in records:
        patient = record["patient_group"]
        by_patient[patient].append(record["id"])
        name = next(s["surface"] for u in record["units"] for s in u["spans"] if s["kind"] == "NAME")
        by_name[name].setdefault(patient, record["id"])
    return {
        "eligible_same_patient": [group for group in by_patient.values() if len(group) == 2],
        "challenge_different_patient": [
            list(identifiers.values())[:2] for identifiers in by_name.values() if len(identifiers) > 1
        ],
    }


def dump(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def generate(root, seed):
    root.mkdir(parents=True, exist_ok=False)
    for split in FORMATS:
        rng = Random(f"{seed}:{split}")
        rows, groups = plan(split, rng)
        tables, collections = defaultdict(list), defaultdict(list)
        headers = {}
        records = []
        for index, (fmt, family, institution, scenario) in enumerate(rows):
            patient = groups.get(index, index)
            item = make_case(split, index, patient, scenario, fmt, rng)
            labels = []
            if fmt in ("csv", "tsv"):
                headers[family], row = render_row(family, item, labels)
                relative = f"{fmt}/{family}.{fmt}"
                loc = f"row:{len(tables[relative])}"
                tables[relative].append(row)
            elif fmt == "json":
                relative = f"json/{family}.json"
                collection = "clinic/queue" if split == "development" else "round~two"
                pointer = collection.replace("~", "~0").replace("/", "~1")
                loc = f"/{pointer}/{len(collections[relative])}"
                collections[relative].append(render_json(family, item, labels))
            elif fmt == "fhir":
                relative, loc = f"fhir/{family}/{item['trace']}.json", "doc"
                dump(root / split / "input" / relative, render_fhir(family, item, labels))
            else:
                relative, loc = f"txt/{family}/{item['trace']}.txt", "doc"
                path = root / split / "input" / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(render_note(family, item, labels), encoding="utf-8")
            records.append({"id": opaque("unit", split, index), "patient_group": opaque("patient", split, patient),
                            "file": relative, "loc": loc, "split": split, "format": fmt,
                            "template_family": family, "institution": institution,
                            "scenario": scenario, "language": item["language"],
                            "secondary_tags": [family, item["language"], fmt],
                            "expected_disposition": "sanitize", "annotation_status": "generated_unreviewed",
                            "units": labels})
        for relative, table in tables.items():
            path = root / split / "input" / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            encoding = ("utf-16" if split == "validation" and path.suffix == ".tsv" else "utf-8")
            with path.open("w", encoding=encoding, newline="") as stream:
                writer = csv.writer(stream, delimiter="\t" if path.suffix == ".tsv" else ",",
                                    lineterminator="\n")
                writer.writerow(headers[path.stem])
                writer.writerows(table)
        for relative, items in collections.items():
            collection = "clinic/queue" if split == "development" else "round~two"
            dump(root / split / "input" / relative, {collection: items, "status": "synthetic export"})
        base = root / split / "input"
        files = {path.relative_to(base).as_posix(): sha256(path.read_bytes()).hexdigest()
                 for path in sorted(base.rglob("*")) if path.is_file()}
        dump(root / split / "truth.json", records)
        dump(root / split / "linkage.json", linkage_truth(records))
        dump(root / split / "manifest.json", {"version": VERSION, "seed": seed, "split": split, "files": files,
                                             "formats": dict(Counter(r["format"] for r in records)),
                                             "scenarios": dict(Counter(r["scenario"] for r in records)),
                                             "truth_sha256": sha256((root / split / "truth.json").read_bytes()).hexdigest(),
                                             "linkage_sha256": sha256((root / split / "linkage.json").read_bytes()).hexdigest()})
    generate_rejections(root / "rejection")


def generate_rejections(directory):
    base = directory / "input"
    base.mkdir(parents=True)
    fixtures = {
        "invalid-utf8.txt": (b"\xffpayload\xfe", "quarantined", "utf8_declared"),
        "unsupported-encoding.txt": (b"\x00\x00\xfe\xff\x00\x00\x00\x61", "quarantined", "utf32"),
        "truncated.json": (b'{"encounters":[', "quarantined", "json_truncated"),
        "ragged.csv": (b"Patient,Dose\na,5 mg,unclosed\n", "quarantined", "table_width"),
        "invalid-bundle.json": (b'{"resourceType":"Bundle","type":"collection","entry":[{}]}',
                                "quarantined", "invalid_fhir"),
        "unsupported.xml": (b"<synthetic/>", "quarantined", "unsupported_format"),
        "oversized.txt": (b" " * (16 * 1024 * 1024 + 1), "quarantined", "file_size"),
        "metadata.json": (b'{"original_path":"fictional/administration"}', "sanitized", "metadata_zero_records"),
        "unsupported-attachment.json": (json.dumps({"resourceType": "Bundle", "type": "collection",
             "entry": [{"resource": {"resourceType": "DocumentReference", "status": "current",
             "content": [{"attachment": {"data": "AAAA", "contentType": "application/pdf"}}]}}]}).encode(),
             "quarantined", "unsupported_attachment"),
    }
    manifest = {}
    for filename, (raw, disposition, reason) in fixtures.items():
        (base / filename).write_bytes(raw)
        manifest[filename] = {"expected_disposition": disposition, "reason": reason,
                              "sha256": sha256(raw).hexdigest()}
    dump(directory / "manifest.json", manifest)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("destination", type=Path)
    parser.add_argument("--seed", type=int, default=SEED)
    args = parser.parse_args()
    generate(args.destination, args.seed)


if __name__ == "__main__":
    main()
