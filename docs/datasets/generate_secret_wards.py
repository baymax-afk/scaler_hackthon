import argparse
import base64
import csv
import hashlib
import json
import random
import uuid
from collections import Counter
from datetime import date, timedelta
from pathlib import Path


GIVEN = [
    ("Aaravi", "आरवी"), ("Mihiran", "मिहिरन"), ("Nayuli", "नायुली"),
    ("Reyansh", "रेयांश"), ("Nivika", "निविका"), ("Ishaan", "ईशान"),
    ("Zarveen", "ज़रवीन"), ("Faridan", "फ़रीदान"), ("Tanvika", "तन्विका"),
    ("Aviraj", "अविराज"), ("Meher", "मेहर"), ("Ritavan", "ऋतवन"),
]
SURNAME = [
    ("Verma", "वर्मा"), ("Khan", "ख़ान"), ("Rathore", "राठौर"),
    ("Sen", "सेन"), ("Ansari", "अंसारी"), ("Joshi", "जोशी"),
    ("Saha", "साहा"), ("Naik", "नाइक"), ("Bisht", "बिष्ट"),
]
CLINICAL = [
    ("Hypertension", "I10", "BP 152/94 mmHg", "Amlodipine 5 mg OD"),
    ("Type 2 diabetes", "E11.9", "HbA1c 8.4 %", "Metformin 500 mg 1-0-1"),
    ("Iron deficiency anemia", "D50.9", "Hb 9.8 g/dL", "Ferrous sulfate 60 mg OD"),
    ("Acute pharyngitis", "J02.9", "Temperature 38.5 °C", "Paracetamol 500 mg PRN"),
    ("Parkinson disease", "G20", "Pulse 62 bpm", "Levodopa 100 mg 1-0-1"),
]


def make_person(index, namespace, rng):
    first, first_hi = GIVEN[index % len(GIVEN)]
    last, last_hi = SURNAME[index // len(GIVEN) % len(SURNAME)]
    relative, relative_hi = GIVEN[(index * 7 + 3) % len(GIVEN)]
    return {
        "id": f"{namespace}-P{index:04d}",
        "first": first, "last": last, "name": f"{first} {last}",
        "name_hi": f"{first_hi} {last_hi}",
        "relative": f"{relative} {last}", "relative_hi": f"{relative_hi} {last_hi}",
        "phone": f"000{namespace[:3]}{index:04d}",
        "email": f"{namespace}.p{index:04d}@example.invalid",
        "aadhaar": int(f"1{namespace[:5]}{index:06d}"),
        "village": f"Nivarpur-{index % 29:02d}",
        "age": rng.randint(18, 86),
    }


def make_record(index, person, rng, script, anomaly):
    name = person["name_hi"] if script == "deva" else person["name"]
    relative = person["relative_hi"] if script == "deva" else person["relative"]
    clinic = rng.choice(CLINICAL)
    admit = date(2025, 1, 1) + timedelta(days=rng.randrange(365))
    stay = rng.randint(1, 9)
    age = person["age"]
    phone = person["phone"]
    email = person["email"]
    if anomaly == 1:
        clinic = ("Observation only", "Z03.9", "Pulse 245 bpm", clinic[3])
    elif anomaly == 2:
        clinic = ("Hyponatremia", "E87.1", "Sodium 109 mmol/L", clinic[3])
    elif anomaly == 3:
        age = 104
        stay = 41
    elif anomaly == 4:
        phone = ""
        email = ""
    elif anomaly == 5:
        name = "  ".join(name.split()[::-1])

    diagnosis, code, result, medication = clinic
    doctor = f"Dr. {person['first']}" if index % 13 == 0 else "Dr. K. Rao"
    clinical = f"{diagnosis} ({code}); {result}; {medication}; {doctor}"
    contact = f"+91 {phone[:5]}-{phone[5:]}" if phone and index % 3 == 0 else phone
    if script == "deva":
        note = f"मरीज़: {name}\nरिश्तेदार: {relative}\nफ़ोन: {contact}\nशिकायत: चक्कर\n{clinical}"
    elif script == "hinglish":
        note = f"{name} ji aaye, W/o {relative}. Phone {contact}. C/O chakkar.\n{clinical}"
    else:
        note = f"Patient: {name}\nC/O {relative}\nC/O fever\nPhone: {contact}\n{clinical}"
    return {
        "name": name, "relative": relative, "phone": contact, "email": email,
        "age": age, "village": person["village"], "patient": person["id"],
        "aadhaar": person["aadhaar"], "script": script, "clinical": clinical,
        "preserve": [diagnosis, code, result, medication, doctor],
        "admit": admit, "discharge": admit + timedelta(days=stay), "note": note,
    }


def save_json(path, payload, *, escaped=False):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=escaped, indent=2) + "\n", encoding="utf-8")


def portable_fields(record, date_format):
    return {
        "Name": record["name"], "Relative": record["relative"], "Mobile": record["phone"],
        "Email": record["email"], "Age": record["age"], "Village": record["village"],
        "Admission": record["admit"].strftime(date_format),
        "Discharge": record["discharge"].strftime(date_format),
        "ClinicalNote": record["clinical"],
    }


def write_table(root, rel, records, system):
    encoding, delimiter, date_format = {
        "sanjeevani": ("utf-8-sig", ",", "%d/%m/%Y"),
        "jeevan": ("utf-16", "\t", "%d/%m/%Y"),
        "arogya": ("cp1252", ",", "%m/%d/%Y"),
    }[system]
    rows = []
    for record in records:
        row = portable_fields(record, date_format)
        if system == "arogya":
            row["FirstName"], _, row["LastName"] = row.pop("Name").partition(" ")
            row["ClinicalNote"] = record["note"].replace("C/O chakkar.", "C/O dizziness.")
        elif system == "jeevan":
            labels = ["मरीज़", "रिश्तेदार", "फ़ोन", "ईमेल", "उम्र", "गाँव",
                      "भर्ती", "छुट्टी", "चिकित्सा नोट"]
            row = dict(zip(labels, row.values()))
        else:
            row["Aadhaar"] = record["aadhaar"]
        rows.append(row)

    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding=encoding, newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]), delimiter=delimiter)
        writer.writeheader()
        writer.writerows(rows)


def write_bundle(path, record, serial):
    patient = f"urn:uuid:{uuid.uuid5(uuid.NAMESPACE_URL, record['patient'] + '/patient')}"
    doc = f"urn:uuid:{uuid.uuid5(uuid.NAMESPACE_URL, record['patient'] + '/' + str(serial))}"
    attachment = f"urn:uuid:{uuid.uuid5(uuid.NAMESPACE_URL, doc + '/attachment')}"
    clinical_note = (
        f"Patient: {record['name']}\nRelative: {record['relative']}\n"
        f"Phone: {record['phone']}\n{record['clinical']}"
    )
    save_json(path, {
        "resourceType": "Bundle", "type": "document",
        "identifier": {"system": "https://example.invalid/bundles", "value": str(serial)},
        "timestamp": f"{record['admit']}T09:00:00Z",
        "entry": [
            {"fullUrl": doc, "resource": {
                "resourceType": "Composition", "status": "final", "type": {"text": "Discharge summary"},
                "date": f"{record['admit']}T09:00:00Z", "subject": {"reference": patient},
                "author": [{"display": record["preserve"][-1]}], "title": "Clinical summary",
                "section": [{"entry": [{"reference": attachment}]}],
            }},
            {"fullUrl": patient, "resource": {
                "resourceType": "Patient", "name": [{"text": record["name"]}],
                "telecom": [{"system": "phone", "value": record["phone"]}] if record["phone"] else [],
                "address": [{"city": record["village"]}],
            }},
            {"fullUrl": attachment, "resource": {
                "resourceType": "DocumentReference", "status": "current",
                "subject": {"reference": patient},
                "content": [{"attachment": {"contentType": "text/plain",
                    "data": base64.b64encode(clinical_note.encode("utf-8")).decode("ascii")}}],
            }},
        ],
    })


def truth_entry(rel, loc, record):
    return {
        "file": rel, "loc": loc, "patient": record["patient"], "script": record["script"],
        "preserve": record["preserve"],
        "dates": {"admission": str(record["admit"]), "discharge": str(record["discharge"])},
        "identifiers": {field: record[field] for field in ("name", "relative", "phone", "email")
                        if record[field]},
    }


def generate(output, seed, count):
    rng = random.Random(seed)
    namespace = f"{seed % 1000000:06d}"
    root = output / "input"
    batch = count // 4
    people = [make_person(index, namespace, rng) for index in range(batch * 2)]
    anomalies = {index: rng.randrange(1, 6) for index in rng.sample(range(count), count // 20)}
    truth = []
    canaries = []
    for format_index, extension in enumerate(("csv", "tsv", "json", "txt")):
        records = []
        people_indexes = rng.sample(range(len(people)), batch)
        for offset, person_index in enumerate(people_indexes):
            index = format_index * batch + offset
            script = ("latin", "deva", "hinglish")[offset % 3]
            if extension == "csv":
                script = ("latin", "hinglish")[offset % 2]
            record = make_record(index, people[person_index], rng, script, anomalies.get(index))
            records.append(record)

        if extension == "csv":
            halfway = batch // 2
            for system, subset in (("sanjeevani", records[:halfway]), ("arogya", records[halfway:])):
                rel = f"registration/{system}.csv"
                write_table(root, rel, subset, system)
                truth.extend(truth_entry(rel, f"row:{idx}", item) for idx, item in enumerate(subset))
        elif extension == "tsv":
            rel = "registration/jeevan.tsv"
            write_table(root, rel, records, "jeevan")
            truth.extend(truth_entry(rel, f"row:{idx}", item) for idx, item in enumerate(records))
        elif extension == "json":
            fhir_count = max(1, batch // 10)
            count_plain = batch - fhir_count
            cut = count_plain // 2
            for rel, key, subset in (
                ("registration/hardoi.json", "patients", records[:cut]),
                ("opd/hardoi.json", "visits", records[cut:count_plain]),
            ):
                save_json(root / rel, {"export": {"facility": "Hardoi"}, key: [
                    portable_fields(item, "%Y-%m-%d") | {"AadhrNo": item["aadhaar"]}
                    for item in subset
                ]}, escaped=True)
                truth.extend(truth_entry(rel, f"/{key}/{idx}", item) for idx, item in enumerate(subset))
            for idx, record in enumerate(records[count_plain:]):
                rel = f"fhir/bundle_{idx:04d}.json"
                write_bundle(root / rel, record, idx)
                truth.append(truth_entry(rel, "doc", record))
        else:
            for idx, record in enumerate(records):
                folder = ("discharge", "notes", "prescriptions")[idx % 3]
                if idx < 6:
                    token = f"Veyruna{namespace}{idx:02d}"
                    canaries.append(token)
                    rel = f"{folder}/{token}.txt" if idx % 2 == 0 else f"{folder}/note_{idx:04d}.txt"
                    record["note"] += f"\nAlternate patient name: {token}"
                else:
                    rel = f"{folder}/note_{idx:04d}.txt"
                target = root / rel
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(
                    f"{record['note']}\nEmail: {record['email']}\nVillage: {record['village']}\n"
                    f"Age: {record['age']}\nAdmission: {record['admit']}\nDischarge: {record['discharge']}\n",
                    encoding="utf-8",
                )
                truth.append(truth_entry(rel, "doc", record))

    misc = root / "misc"
    misc.mkdir()
    for name, payload in {
        "truncated.json": b'{"visits": [',
        "invalid_utf8.txt": b'\xffpayload\xfe',
        "zero_bytes.txt": b'',
        "unsupported.xml": b'<export/>',
        "deep.json": b'[' * 1500 + b'null' + b']' * 1500,
    }.items():
        (misc / name).write_bytes(payload)
    key_canary = f"Veyruna{namespace}06"
    canaries.append(key_canary)
    save_json(misc / "export_metadata.json", {"export": {key_canary: "batch 12"}}, escaped=True)
    clean = root / "clean"
    clean.mkdir()
    (clean / "ward_protocol.txt").write_text(
        "Ward B. Inventory review: 12 monitors, 24 thermometers. Routine inspection complete.\n",
        encoding="utf-8",
    )
    save_json(output / "truth" / "fixtures.json", {"records": truth, "canaries": canaries})
    save_json(output / "manifest.json", {
        "seed": seed, "patient_records": len(truth),
        "by_extension": dict(Counter(Path(item["file"]).suffix for item in truth)),
        "by_script": dict(Counter(item["script"] for item in truth)),
        "distinct_patients": len({item["patient"] for item in truth}),
        "files": {path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
                  for path in sorted(root.rglob("*")) if path.is_file()},
    })


def main():
    parser = argparse.ArgumentParser(description="Generate standalone synthetic Secret Wards test fixtures.")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=370319)
    parser.add_argument("--count", type=int, default=2000)
    args = parser.parse_args()
    if not 40 <= args.count <= 2000 or args.count % 4:
        parser.error("--count must be a multiple of 4 between 40 and 2000")
    if args.output.exists():
        parser.error("--output must be a new directory")
    generate(args.output, args.seed, args.count)


if __name__ == "__main__":
    main()
