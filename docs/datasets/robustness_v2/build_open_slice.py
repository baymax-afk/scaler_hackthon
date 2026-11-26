"""Build a small deterministic, development-only synthetic corpus."""
import argparse
import csv
import hashlib
from io import StringIO
import json
from pathlib import Path


NOTE = "रोगी: Zevra Qiln\nDr. Zevra Qiln reviewed BP 120/80 and metformin 500 mg.\n"
CSV_NAME = "Luvra Senq"
CSV_OBSERVATION = "BP 118/76, pulse 72"
JSON_NAME = "Zevra Qiln"
JSON_DRUG = "metformin 500 mg"
JSON_BP = "120/80"
TSV_NAME = "Mivra Dosen"
TSV_LAB = "HbA1c 6.8%"
FHIR_NAME = "Cevra Nolin"
FHIR_CLINICIAN = "Dr. Rava Xelen"
FHIR_NOTE = "HbA1c 6.8%"


def fhir_bundle():
    composition = "11111111-1111-4111-8111-111111111111"
    patient = "22222222-2222-4222-8222-222222222222"
    practitioner = "33333333-3333-4333-8333-333333333333"
    observation = "44444444-4444-4444-8444-444444444444"
    url = lambda identifier: "urn:uuid:" + identifier
    return {
        "resourceType": "Bundle", "id": "55555555-5555-4555-8555-555555555555",
        "identifier": {"system": "https://fictional-clinic.invalid/bundles", "value": "open-005"},
        "type": "document", "timestamp": "2026-11-20T09:00:00+05:30",
        "entry": [
            {"fullUrl": url(composition), "resource": {
                "resourceType": "Composition", "id": composition, "status": "final",
                "type": {"coding": [{"system": "http://loinc.org", "code": "34133-9",
                                     "display": "Summary of episode note"}]},
                "subject": {"reference": url(patient)},
                "date": "2026-11-20T09:00:00+05:30",
                "author": [{"reference": url(practitioner)}], "title": "Clinical summary",
                "section": [{"title": "Laboratory", "entry": [{"reference": url(observation)}]}],
            }},
            {"fullUrl": url(patient), "resource": {
                "resourceType": "Patient", "id": patient,
                "name": [{"text": FHIR_NAME, "given": ["Cevra"], "family": "Nolin"}],
                "gender": "female", "birthDate": "1991-02-03",
            }},
            {"fullUrl": url(practitioner), "resource": {
                "resourceType": "Practitioner", "id": practitioner,
                "name": [{"text": FHIR_CLINICIAN}],
            }},
            {"fullUrl": url(observation), "resource": {
                "resourceType": "Observation", "id": observation, "status": "final",
                "code": {"coding": [{"system": "http://loinc.org", "code": "4548-4"}],
                         "text": "HbA1c"},
                "subject": {"reference": url(patient)},
                "effectiveDateTime": "2026-11-20T08:30:00+05:30",
                "valueQuantity": {"value": 6.8, "unit": "%", "system": "http://unitsofmeasure.org",
                                  "code": "%"},
                "note": [{"text": FHIR_NOTE}],
            }},
        ],
    }


def encoded_json(value):
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


def digest(data):
    return hashlib.sha256(data).hexdigest()


def span(text, value, occurrence=0):
    """Return original half-open code-point offsets for a rendered surface."""
    if not value or occurrence < 0:
        raise ValueError("invalid_annotation_surface")
    start = -1
    for _ in range(occurrence + 1):
        start = text.find(value, start + 1)
        if start < 0:
            raise ValueError("missing_annotation_surface")
    return start, start + len(value)


def unit(identifier, record_id, locator, text, label=""):
    return {"id": identifier, "record_id": record_id, "locator": locator,
            "channel": "content", "label": label, "text": text}


def annotation(source_unit, gold, protect, input_digest, **extra):
    return {"id": source_unit["id"], "record_id": source_unit["record_id"],
            "locator": source_unit["locator"], "input_sha256": input_digest,
            "gold": gold, "protect": protect, **extra}


def build(output):
    output.mkdir(parents=True, exist_ok=False)
    files = {
        "notes/note-0001.txt": NOTE.encode("utf-8"),
        "opd/visit-0003.json": encoded_json({"patient_name": JSON_NAME,
                                               "blood_pressure": JSON_BP, "drug": JSON_DRUG}),
        "fhir/bundle-0005.json": encoded_json(fhir_bundle()),
    }
    csv_buffer = StringIO(newline="")
    writer = csv.writer(csv_buffer, lineterminator="\n")
    writer.writerow(["patient_name", "observation"])
    writer.writerow([CSV_NAME, CSV_OBSERVATION])
    files["registration/row-0002.csv"] = csv_buffer.getvalue().encode("utf-8")
    tsv_buffer = StringIO(newline="")
    writer = csv.writer(tsv_buffer, delimiter="\t", lineterminator="\n")
    writer.writerow(["patient_name", "lab_result"])
    writer.writerow([TSV_NAME, TSV_LAB])
    files["labs/row-0004.tsv"] = tsv_buffer.getvalue().encode("utf-8")
    for relative, data in sorted(files.items()):
        target = output / "input" / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)

    units = [
        unit("unit-open-001", "record-open-001", "doc", NOTE),
        unit("unit-open-002-name", "record-open-002", "row:0/patient_name", CSV_NAME, "patient_name"),
        unit("unit-open-002-observation", "record-open-002", "row:0/observation", CSV_OBSERVATION, "observation"),
        unit("unit-open-003-name", "record-open-003", "/patient_name", JSON_NAME, "patient_name"),
        unit("unit-open-003-bp", "record-open-003", "/blood_pressure", JSON_BP, "blood_pressure"),
        unit("unit-open-003-drug", "record-open-003", "/drug", JSON_DRUG, "drug"),
        unit("unit-open-004-name", "record-open-004", "row:0/patient_name", TSV_NAME, "patient_name"),
        unit("unit-open-004-lab", "record-open-004", "row:0/lab_result", TSV_LAB, "lab_result"),
        unit("unit-open-005-name", "record-open-005", "/entry/1/resource/name/0/text",
             FHIR_NAME, "text"),
        unit("unit-open-005-clinician", "record-open-005", "/entry/2/resource/name/0/text",
             FHIR_CLINICIAN, "text"),
        unit("unit-open-005-note", "record-open-005", "/entry/3/resource/note/0/text",
             FHIR_NOTE, "text"),
    ]
    units_data = encoded_json(units)
    (output / "source_units.json").write_bytes(units_data)
    input_digest = digest(units_data)
    patient_name = span(NOTE, JSON_NAME)
    clinician_name = span(NOTE, JSON_NAME, 1)
    note_bp = span(NOTE, "BP 120/80")
    note_drug = span(NOTE, JSON_DRUG)
    truth = [
        annotation(units[0], [[*patient_name, "NAME"]],
                   [list(clinician_name), list(note_bp), list(note_drug)], input_digest,
                   occurrences=[{"start": patient_name[0], "end": patient_name[1],
                                 "type": "NAME", "role": "patient", "surface": JSON_NAME},
                                {"start": clinician_name[0], "end": clinician_name[1],
                                 "type": "NAME", "role": "clinician", "surface": JSON_NAME}],
                   clinical_facts=[{"start": note_bp[0], "end": note_bp[1], "text": "BP 120/80"},
                                   {"start": note_drug[0], "end": note_drug[1], "text": JSON_DRUG}]),
        annotation(units[1], [[0, len(CSV_NAME), "NAME"]], [], input_digest,
                   occurrences=[{"start": 0, "end": len(CSV_NAME), "type": "NAME",
                                 "role": "patient", "surface": CSV_NAME}]),
        annotation(units[2], [], [[0, len(CSV_OBSERVATION)]], input_digest,
                   clinical_facts=[{"start": 0, "end": len(CSV_OBSERVATION), "text": CSV_OBSERVATION}]),
        annotation(units[3], [[0, len(JSON_NAME), "NAME"]], [], input_digest,
                   occurrences=[{"start": 0, "end": len(JSON_NAME), "type": "NAME",
                                 "role": "patient", "surface": JSON_NAME}]),
        annotation(units[4], [], [[0, len(JSON_BP)]], input_digest,
                   clinical_facts=[{"start": 0, "end": len(JSON_BP), "text": JSON_BP}]),
        annotation(units[5], [], [[0, len(JSON_DRUG)]], input_digest,
                   clinical_facts=[{"start": 0, "end": len(JSON_DRUG), "text": JSON_DRUG}]),
        annotation(units[6], [[0, len(TSV_NAME), "NAME"]], [], input_digest,
                   occurrences=[{"start": 0, "end": len(TSV_NAME), "type": "NAME",
                                 "role": "patient", "surface": TSV_NAME}]),
        annotation(units[7], [], [[0, len(TSV_LAB)]], input_digest,
                   clinical_facts=[{"start": 0, "end": len(TSV_LAB), "text": TSV_LAB}]),
        annotation(units[8], [[0, len(FHIR_NAME), "NAME"]], [], input_digest,
                   occurrences=[{"start": 0, "end": len(FHIR_NAME), "type": "NAME",
                                 "role": "patient", "surface": FHIR_NAME}]),
        annotation(units[9], [], [[0, len(FHIR_CLINICIAN)]], input_digest),
        annotation(units[10], [], [[0, len(FHIR_NOTE)]], input_digest,
                   clinical_facts=[{"start": 0, "end": len(FHIR_NOTE), "text": FHIR_NOTE}]),
    ]
    truth_data = encoded_json(truth)
    (output / "truth").mkdir()
    (output / "truth" / "annotations.json").write_bytes(truth_data)
    records = [
        {"id": "record-open-001", "file": "notes/note-0001.txt", "locator": "doc",
         "format": "text", "patient_group": "patient-open-a", "file_family": "note-a",
         "template_family": "note-homonym-a", "renderer_family": "note-renderer-a",
         "near_duplicate_family": "note-variant-a", "institution": "fictional-facility-a",
         "split": "development"},
        {"id": "record-open-002", "file": "registration/row-0002.csv", "locator": "row:0",
         "format": "csv", "patient_group": "patient-open-b", "file_family": "registration-b",
         "template_family": "registration-b", "renderer_family": "csv-renderer-b",
         "near_duplicate_family": "registration-variant-b", "institution": "fictional-facility-b",
         "split": "development"},
        {"id": "record-open-003", "file": "opd/visit-0003.json", "locator": "doc",
         "format": "json", "patient_group": "patient-open-a", "file_family": "visit-a",
         "template_family": "visit-a", "renderer_family": "json-renderer-a",
         "near_duplicate_family": "visit-variant-a", "institution": "fictional-facility-a",
         "split": "development"},
        {"id": "record-open-004", "file": "labs/row-0004.tsv", "locator": "row:0",
         "format": "tsv", "patient_group": "patient-open-c", "file_family": "lab-c",
         "template_family": "lab-c", "renderer_family": "tsv-renderer-c",
         "near_duplicate_family": "lab-variant-c", "institution": "fictional-facility-c",
         "split": "development"},
        {"id": "record-open-005", "file": "fhir/bundle-0005.json", "locator": "doc",
         "format": "fhir", "patient_group": "patient-open-d", "file_family": "bundle-d",
         "template_family": "bundle-d", "renderer_family": "fhir-renderer-d",
         "near_duplicate_family": "bundle-variant-d", "institution": "fictional-facility-d",
         "split": "development"},
    ]
    manifest = {"schema": "robustness-v2-open-slice/1", "split": "development",
                "generator_revision": "build_open_slice/1", "seed": 0,
                "provenance": "manually authored synthetic templates",
                "files": {path: digest(data) for path, data in sorted(files.items())},
                "records": records, "source_units_sha256": input_digest,
                "truth_sha256": digest(truth_data)}
    (output / "manifest.json").write_bytes(encoded_json(manifest))
    return {"files": len(files), "records": len(records), "units": len(units)}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(build(args.output), sort_keys=True))
