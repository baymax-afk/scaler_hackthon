"""Generate the development side of the longitudinal Secret Wards fixtures."""

import argparse
import csv
import hashlib
import json
import random
from collections import Counter
from datetime import date, timedelta
from itertools import product
from pathlib import Path
from string import Formatter


STYLES = ("latin", "devanagari", "code_switched")
KINDS = ("discharge", "prescription", "nursing")
FACILITIES = (
    ("Palash Bend Day Hospital", "पलाश मोड़ अस्पताल", "Orchid Bay", "ऑर्किड कक्ष"),
    ("Kesar Tank Community Hospital", "केसर ताल सामुदायिक अस्पताल", "West Annex", "पश्चिम खंड"),
    ("Ratan Weir Medical Unit", "रतन बाँध चिकित्सा इकाई", "Ward Four", "कक्ष चार"),
)
GIVEN = (
    ("Neevati", "नीवती", "Nivati"), ("Avarin", "अवरिन", "Avrin"),
    ("Tavishi", "तविशी", "Tavishee"), ("Veshan", "वेशान", "Veshaan"),
    ("Suheni", "सुहेनी", "Suheyni"), ("Yadvin", "यद्विन", "Yadvinn"),
    ("Puneli", "पुनेली", "Puneyli"), ("Torav", "तोरव", "Toravh"),
    ("Nimaya", "निमाया", "Nimaaya"), ("Anevik", "अनेविक", "Anevick"),
    ("Mehuri", "मेहुरी", "Mehuree"), ("Rivanesh", "रिवनेश", "Rivnesh"),
)
SURNAMES = (
    ("Kelvane", "केलवाने"), ("Ojalekar", "ओजलेकर"), ("Samruli", "समरुली"),
    ("Dhunavre", "धुनावरे"), ("Ritvode", "रितवोदे"), ("Vanerji", "वानेरजी"),
    ("Phalkire", "फालकिरे"), ("Chitvali", "चितवली"), ("Lohkade", "लोहकाड़े"),
)
CLINICAL = (
    ("migraine", "माइग्रेन", "headache", "सिरदर्द", "Paracetamol", "पैरासिटामोल", 500),
    ("viral upper respiratory infection", "ऊपरी श्वसन तंत्र का वायरल संक्रमण",
     "sore throat", "गले में दर्द", "Paracetamol", "पैरासिटामोल", 500),
    ("ankle sprain", "टखने में मोच", "ankle pain", "टखने में दर्द", "Ibuprofen", "आइबुप्रोफेन", 200),
    ("tension-type headache", "तनावजन्य सिरदर्द", "head pressure", "सिर में दबाव",
     "Paracetamol", "पैरासिटामोल", 500),
    ("acute lumbar strain", "कमर की मांसपेशी में खिंचाव", "lower back pain", "कमर दर्द",
     "Ibuprofen", "आइबुप्रोफेन", 400),
)
HEADINGS = {
    "discharge": (("Inpatient closure", "Home plan"), ("अस्पताल से छुट्टी", "घर पर देखभाल"),
                  ("IPD से घर", "घर की advice")),
    "prescription": (("Dispensary order", "Medication slip"), ("दवा लिखत", "औषधि पर्चा"),
                     ("Dispensary की प्रति", "दवा schedule")),
    "nursing": (("Bedside round", "Shift observations"), ("बिस्तर पर जाँच", "पाली की निगरानी"),
                ("सुबह की bedside round", "Night पाली")),
}
CONTEXT = {
    "discharge": (
        ("From {admit} to {discharge}: {diagnosis} improved; comfortable on discharge.",
         "Continue {drug} {dose} orally as needed for pain for up to 3 days. Return if symptoms worsen."),
        ("{admit} को भर्ती। {diagnosis} में आराम के बाद {discharge} को घर भेजा।",
         "दर्द हो तो {drug} {dose} मुँह से लें। अधिकतम ३ दिन। तकलीफ़ बढ़े तो वापस आएँ।"),
        ("{admit} को ward में admit किया; {diagnosis} में आराम, {discharge} को discharged.",
         "घर पर pain हो तो {drug} {dose} oral, अधिकतम 3 दिन. Symptoms बढ़ें तो लौटें."),
    ),
    "prescription": (
        ("Issued {discharge} for {diagnosis}.", "Dispense {drug} {dose} tablets. Take one orally as needed "
         "for pain, at least 8 hours apart, for up to 3 days."),
        ("{discharge} को {diagnosis} के लिए।", "{drug} {dose} की एक गोली मुँह से लें। दर्द होने पर कम से "
         "कम ८ घंटे के अंतर से, अधिकतम ३ दिन।"),
        ("{discharge} को {diagnosis} के लिए Rx जारी।", "{drug} {dose} की one tablet by mouth, सिर्फ दर्द "
         "पर. दो doses के बीच at least 8 घंटे, अधिकतम 3 दिन।"),
    ),
    "nursing": (
        ("{discharge} / 07:40: awake, breathing unlaboured. BP {bp}.", "At 08:00 gave {drug} {dose} PO "
         "per chart. Check pain at next round."),
        ("{discharge} सुबह ०७:४० बजे सचेत, साँस सामान्य। रक्तचाप {bp}।",
         "०८:०० बजे निर्देशानुसार {drug} {dose} मुँह से दी। अगली पाली में दर्द दोबारा पूछें।"),
        ("{discharge} 07:40 पर awake, साँस सहज, BP {bp} recorded।",
         "08:00 पर chart के मुताबिक {drug} {dose} PO दी। Next round में दर्द पूछें।"),
    ),
}
IDENTITY = (
    ("{patient} | local record {mrn}", "Referral contacted at {phone}.", "C/O {contact}", "C/O {complaint}",
     "Reviewed by Dr {clinician}", "{location} · {ward}"),
    ("{patient} | पंजी क्रम {mrn}", "संपर्क {phone}।", "C/O {contact}", "C/O {complaint}",
     "समीक्षक डॉ. {clinician}", "{location} · {ward}"),
    ("{patient} | पर्ची ID {mrn}", "घर का callback {phone} है।", "C/O {contact}", "C/O {complaint}",
     "Seen by डॉ. {clinician}", "{location} का {ward}"),
)
LAYOUTS = {
    "progress": "{place}\n{identity}\n{clinical}\n{observation}\n{treatment}\n{contacts}\n{review}",
    "handover": "{clinical}\n> {treatment}\n> {observation}\n{review}\n---\n{place}\n{identity}\n{contacts}",
    "slip": "{review}\n{place} / {identity}\n\n{contacts}\n{clinical} | {observation}\n{treatment}",
}


def write_json(path, body):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes((json.dumps(body, indent=2, ensure_ascii=False) + "\n").encode("utf-8"))


def file_hashes(root):
    return {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(root.rglob("*")) if p.is_file()}


def manifest(root, counts):
    write_json(root / "manifest.json", {"schema": "secret-wards-fixtures/3",
                                       "counts": counts, "sha256": file_hashes(root)})


def new_patients(size, rng):
    name_pairs = list(product(range(len(GIVEN)), range(len(SURNAMES))))
    rng.shuffle(name_pairs)
    # The selected household pairs share a surname and a given-name initial.
    similar = [(0, 0), (8, 0), (1, 1), (9, 1), (2, 2), (7, 2)]
    names = (similar + [pair for pair in name_pairs if pair not in similar])[:size]
    tickets = rng.sample([n for n in range(110, 990) if n not in {200, 400, 500}], size)
    ticket_order = list(tickets)
    rng.shuffle(ticket_order)
    for i, (given, surname) in enumerate(names):
        latin, hindi, variant = GIVEN[given]
        last, last_hindi = SURNAMES[surname]
        household = i // 2 if i < 6 else i
        # 000 is a non-dialable prefix. The remaining digits are independent of the record number.
        contact_rng = random.Random(84200 + household)
        route = contact_rng.randrange(1000000, 9999999)
        facility = i // 2 if i < 6 else rng.randrange(len(FACILITIES))
        mrn = (str(tickets[i]), f"KT/{tickets[i]}", f"RW-{tickets[i]}-A")[facility]
        yield {
            "id": f"D3-{ticket_order[i]}", "names": [f"{latin} {last}", f"{hindi} {last_hindi}",
                                                       f"{variant} {last}", f"{variant} {last_hindi}"],
            "mrn": mrn, "phone": f"000{route}", "household": f"DHH-{household}",
            "contact": [f"Jivani {last}", f"जीवनी {last_hindi}", f"Jivani {last_hindi}"],
            "birth": date(1958 + rng.randrange(45), 1 + rng.randrange(12), 1 + rng.randrange(28)).isoformat(),
            "locality": ("Baans Spur", "Ner Canal", "Kachri Rise")[i % 3],
            "facility": facility,
        }


def visit(patient, index, start, rng, prior=None):
    admit = start.isoformat()
    discharge = (start + timedelta(days=0 if prior else rng.choice([1, 1, 1, 2, 3]))).isoformat()
    case = CLINICAL[rng.randrange(len(CLINICAL))]
    dx, dx_hi, complaint, complaint_hi, drug, drug_hi, mg = case
    bp = f"{rng.randrange(104, 139)}/{rng.randrange(63, 89)}"
    facts = {
        "admit": admit, "discharge": discharge, "diagnosis": dx, "diagnosis_hi": dx_hi,
        "complaint": complaint, "complaint_hi": complaint_hi, "drug": drug, "drug_hi": drug_hi,
        "dose": f"{mg} mg", "dose_hi": f"{str(mg).translate(str.maketrans('0123456789', '०१२३४५६७८९'))} मि.ग्रा.",
        "bp": f"{bp} mmHg", "bp_hi": f"{bp} मि.मी. पारा", "hb": f"{rng.randrange(104, 152)/10:.1f}",
        "hb_unit": "g/dL",
    }
    if prior:
        for key in ("diagnosis", "diagnosis_hi", "drug", "drug_hi", "dose", "dose_hi"):
            facts[key] = prior["facts"][key]
        facts["prior_discharge"] = prior["facts"]["discharge"]
    return {"id": f"{patient['id']}/E{index}", "patient": patient["id"],
            "workflow": "follow_up" if prior else "inpatient",
            "prior_event": prior and prior["id"], "facts": facts}


class Dataset:
    def __init__(self, root, rng):
        self.root = root
        self.rng = rng
        self.records, self.labels, self.links, self.malformed = [], [], [], []

    def path(self, folder, suffix):
        path = f"{folder}/export-{self.rng.getrandbits(64):016x}.{suffix}"
        (self.root / "input" / path).parent.mkdir(parents=True, exist_ok=True)
        return path

    def record(self, path, locator, kind, patient, event, **metadata):
        rec_id = f"R-{self.rng.getrandbits(64):016x}"
        self.records.append({"id": rec_id, "file": path, "locator": locator, "kind": kind,
                             "patient": patient and patient["id"], "event": event and event["id"], **metadata})
        return rec_id

    def label(self, path, locator, value):
        surface, role, action, *reference = value
        label = {"file": path, "locator": locator, "surface": surface, "role": role, "action": action}
        if reference:
            label.update(event=reference[0], fact=reference[1])
        self.labels.append(label)

    def note(self, template, values, kind, patient=None, event=None, **metadata):
        path = self.path("text", "txt")
        fragments = []
        position = 0
        for literal, key, _, _ in Formatter().parse(template):
            fragments.append(literal)
            position += len(literal)
            if key is not None:
                value = values[key]
                surface = value[0]
                end = position + len(surface)
                self.label(path, {"start": position, "end": end}, value)
                fragments.append(surface)
                position = end
        (self.root / "input" / path).write_bytes("".join(fragments).encode("utf-8"))
        return self.record(path, {"document": True}, kind, patient, event, **metadata)

    def edge(self, left, right, expected, evidence, **metadata):
        self.links.append({"left": left, "right": right, "expected": expected,
                           "evidence": evidence, **metadata})


def clinical(event, key, role=None, action="PRESERVE"):
    return event["facts"][key], role or key, action, event["id"], key


def render_note(data, patient, event, kind, style, heading_idx, layout, index, stress, clean=False):
    local = style == 1
    name = patient["names"][style]
    if style == 2 and index % 2:
        name = patient["names"][3]
    location = FACILITIES[patient["facility"]]
    clinician = name if "same_name" in stress else ("रुचा देवले" if local else "Rucha Devale")
    values = {
        "patient": (name, "patient_name", "REMOVE"),
        "mrn": (patient["mrn"], "patient_id", "REMOVE"),
        "phone": (patient["phone"], "phone", "REMOVE"),
        "contact": (patient["contact"][style], "relationship_name", "REMOVE"),
        "clinician": (clinician, "clinician_name", "PRESERVE"),
        "location": (location[int(local)], "facility", "PRESERVE"),
        "ward": (location[2 + int(local)], "ward", "PRESERVE"),
    }
    for role in ("diagnosis", "complaint", "drug", "dose", "bp"):
        hindi = local or (style == 2 and role in {"complaint", "diagnosis"})
        values[role] = clinical(event, f"{role}_hi" if hindi else role, role)
    for key in ("admit", "discharge"):
        values[key] = clinical(event, key, "encounter_date", "SHIFT")
    values["eponym"] = ("Babinski sign" if not local else "बाबिन्स्की चिह्न", "eponym", "PRESERVE")
    identity, phone, contact, complaint, review, place = IDENTITY[style]
    body, treatment = CONTEXT[kind][style]
    contacts = " / ".join(x for x in (
        contact if "c_o" in stress else phone if index % 3 == 0 else "",
        complaint if "c_o" in stress else "",
    ) if x)
    if "id_dose" in stress:
        values["chart"] = (values["dose"][0].split()[0], "patient_id", "REMOVE")
        identity += (" · chart suffix {chart} / {dose}", " · चार्ट क्रम {chart} / {dose}",
                     " · chart क्रम {chart} / {dose}")[style]
    if "copy_forward" in stress:
        review += ("\nCopied from same stay: {diagnosis}." if not local
                   else "\nइसी भर्ती से दोहराया: {diagnosis}।")
    observation = (("BP on chart {bp}.", "दर्ज रक्तचाप {bp}।", "Chart में BP {bp} दर्ज है।")[style]
                   if kind != "nursing" and index % 3 else "")
    if kind == "discharge" and index % 2:
        values["hb"] = clinical(event, "hb", "lab_value")
        values["unit"] = clinical(event, "hb_unit", "lab_unit")
        observation += (" Admission Hb {hb} {unit}.", " भर्ती पर हीमोग्लोबिन {hb} {unit}।",
                        " Admission का Hb {hb} {unit} था।")[style]
    if clean:
        identity = contacts = ""
        body = body.replace("{admit}", ("Day 1", "पहला दिन", "Day 1")[style])
        body = body.replace("{discharge}", ("Day 2", "दूसरा दिन", "Day 2")[style])
        if kind in {"nursing", "discharge"}:
            observation += (" {eponym} absent.", " {eponym} नहीं मिला।", " {eponym} absent रहा।")[style]
        else:
            observation += (" Ward formulary copy.", " कक्ष की औषधि सूची की प्रति।", " Ward की formulary copy।")[style]
        values = {k: v[:3] for k, v in values.items()}
    heading = None if heading_idx == 2 else HEADINGS[kind][style][heading_idx]
    template = LAYOUTS[layout].format(place=place, identity=identity, clinical=body, observation=observation,
                                      treatment=treatment, contacts=contacts, review=review)
    text = "\n".join(line.strip() for line in template.splitlines() if line.strip(" |>/"))
    if heading:
        text = heading + "\n" + text
    return data.note(text + "\n", values, kind, None if clean else patient, None if clean else event,
                     style=STYLES[style], heading=heading, layout=layout, stress=stress, clean=clean)


def registration(data, patients, visits):
    result = {}
    for facility, people in enumerate(patients):
        people = list(people)
        data.rng.shuffle(people)
        path = data.path("intake", ("csv", "json", "tsv")[facility])
        table = []
        fields = ("desk_no", "client", "callback", "birth_date", "catchment", "opened")
        if facility == 2:
            fields = ("opened", "catchment", "client", "callback", "desk_no", "birth_date")
        for index, patient in enumerate(people):
            first = visits[patient["id"]][0]
            values = {"desk_no": (patient["mrn"], "patient_id", "REMOVE"),
                      "client": (patient["names"][facility], "patient_name", "REMOVE"),
                      "birth_date": (patient["birth"], "birth_date", "REMOVE"),
                      "catchment": (patient["locality"], "locality", "GENERALIZE"),
                      "opened": clinical(first, "admit", "encounter_date", "SHIFT")}
            if index % 7 or patient["household"] in {f"DHH-{i}" for i in range(3)}:
                values["callback"] = (patient["phone"], "phone", "REMOVE")
            loc = {"pointer": f"/intake/cards/{index}"} if facility == 1 else {"row": index}
            result[patient["id"]] = data.record(path, loc, "registration", patient, first,
                                                style=STYLES[facility])
            row = {}
            for col, value in values.items():
                locator = {"pointer": loc["pointer"] + "/" + col} if facility == 1 else {**loc, "column": col}
                data.label(path, locator, value)
                row[col] = value[0]
            table.append(row)
        target = data.root / "input" / path
        if facility == 1:
            write_json(target, {"intake": {"cards": table}, "desk": FACILITIES[facility][0]})
        else:
            with target.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fields, delimiter="\t" if facility == 2 else ",", lineterminator="\n")
                writer.writeheader()
                writer.writerows(table)
    return result


def lab_exports(data, patients, visits):
    rows = [(p, e) for p in patients for e in visits[p["id"]]]
    data.rng.shuffle(rows)
    file = data.path("diagnostics", "json")
    packets, ids = [], {}
    for index, (patient, event) in enumerate(rows):
        loc = f"/packets/{index}"
        ids[event["id"]] = data.record(file, {"pointer": loc}, "lab", patient, event, style="latin")
        fields = {
            "/ticket/person": (patient["names"][2], "patient_name", "REMOVE"),
            "/ticket/desk": (patient["mrn"], "patient_id", "REMOVE"),
            "/collected": clinical(event, "admit", "encounter_date", "SHIFT"),
            "/results/0/test": ("Haemoglobin", "test_name", "PRESERVE"),
            "/results/0/read": clinical(event, "hb", "lab_value"),
            "/results/0/units": clinical(event, "hb_unit", "lab_unit"),
        }
        for key, value in fields.items():
            data.label(file, {"pointer": loc + key}, value)
        packets.append({
            "ticket": {"person": fields["/ticket/person"][0], "desk": patient["mrn"]},
            "collected": event["facts"]["admit"],
            "results": [{"test": "Haemoglobin", "read": event["facts"]["hb"], "units": event["facts"]["hb_unit"]}],
        })
    write_json(data.root / "input" / file, {"bench": "Sandglass Pathology", "packets": packets})
    return ids


def render_followup(data, patient, event, prior):
    values = {
        "patient": (patient["names"][3], "patient_name", "REMOVE"),
        "mrn": (patient["mrn"], "patient_id", "REMOVE"),
        "prior": clinical(prior, "discharge", "encounter_date", "SHIFT"),
        "date": clinical(event, "admit", "encounter_date", "SHIFT"),
        "condition": clinical(event, "diagnosis_hi", "diagnosis"),
        "bp": clinical(event, "bp", "bp"),
    }
    return data.note(
        "{date} / {patient} (desk {mrn})\n{prior} की छुट्टी के बाद पहली review. "
        "{condition} बेहतर है। आज का BP {bp}। Return if pain recurs.\n",
        values, "follow_up", patient, event, style="code_switched", stress=[],
    )


def generate(root, pilot):
    root.mkdir(parents=True, exist_ok=True)
    if any(root.iterdir()):
        raise SystemExit(f"Output directory must be empty: {root}")
    rng = random.Random(7280043)
    data = Dataset(root, rng)
    patients = list(new_patients(27 if pilot else 54, rng))
    visits = {}
    for i, patient in enumerate(patients):
        start = date(2025, 8, 1) + timedelta(days=rng.randrange(93))
        visits[patient["id"]] = [visit(patient, 1, start, rng)]
        if i % 8 == 0:
            visits[patient["id"]].append(visit(patient, 2, start + timedelta(days=rng.randint(22, 44)),
                                               rng, prior=visits[patient["id"]][0]))
    registrants = [[p for p in patients if p["facility"] == i] for i in range(len(FACILITIES))]
    entries = registration(data, registrants, visits)
    labs = lab_exports(data, patients, visits)
    profiles = {}
    for kind, style in product(KINDS, range(3)):
        profiles[kind, style] = list(product(range(3), LAYOUTS)) * (1 if pilot else 2)
        rng.shuffle(profiles[kind, style])
    rotations = [i % 3 for i in range(len(patients))]
    rng.shuffle(rotations)
    stress_indices = rng.sample(range(len(patients) * 3), 15 if pilot else 27)
    stress_tags = ("same_name", "id_dose", "c_o")
    stress = {number: stress_tags[i % len(stress_tags)] for i, number in enumerate(stress_indices)}
    for index, patient in enumerate(patients):
        event = visits[patient["id"]][0]
        reg = entries[patient["id"]]
        lab = labs[event["id"]]
        data.edge(reg, lab, "LINK", "Facility-local number and compatible patient-name forms.")
        note_ids = {}
        for offset, kind in enumerate(KINDS):
            style = (offset + rotations[index]) % 3
            heading, layout = profiles[kind, style].pop()
            condition = stress.get(index * 3 + offset)
            flags = [condition] if condition else (["copy_forward"] if (index + offset) % 11 == 0 else [])
            note = render_note(data, patient, event, kind, style, heading, layout, index, flags)
            note_ids[style] = note
            data.edge(lab, note, "LINK", "Matching local record number and same visit; name or variant supports it.")
        latin, hindi = note_ids[0], note_ids[1]
        data.edge(latin, hindi, "LINK", "Same visible local record number and transliterable complete name.",
                  cross_script=True)
        if len(visits[patient["id"]]) > 1:
            follow_up = visits[patient["id"]][1]
            followup_id = render_followup(data, patient, follow_up, event)
            data.edge(latin, followup_id, "LINK", "Same desk number and compatible Romanized/mixed-script name.",
                      cross_script=True)
            data.edge(labs[follow_up["id"]], followup_id, "LINK", "Same desk number and follow-up date.")
        for episode in visits[patient["id"]]:
            if index % 3:
                continue
            vals = {
                "patient": (patient["names"][2], "patient_name", "REMOVE"),
                "mrn": (patient["mrn"], "patient_id", "REMOVE"),
                "date": clinical(episode, "admit", "encounter_date", "SHIFT"),
                "hb": clinical(episode, "hb", "lab_value"),
                "unit": clinical(episode, "hb_unit", "lab_unit"),
            }
            forward = data.note(rng.choice((
                "Lab ने भेजा · {date}\n{patient} / token {mrn}\nHb {hb} {unit} है। Report received.\n",
                "[{date}] OPD desk का संदेश: {patient} (परची {mrn})\nHb वापस आया, {hb} {unit}।\n",
            )), vals, "lab_forward", patient, episode, style="code_switched", stress=[])
            data.edge(labs[episode["id"]], forward, "LINK",
                      "The copied lab result, case token and collection date agree.")
            if episode is not event:
                data.edge(reg, forward, "LINK", "Same facility record number and Romanized name at a later encounter.")
    for kind, style in product(KINDS, range(3)):
        for repeat in range(2 if pilot else 3):
            patient = rng.choice(patients)
            render_note(data, patient, visits[patient["id"]][0], kind, style, repeat,
                        rng.choice(list(LAYOUTS)), rng.randrange(10), [], clean=True)
    for index in range(0, 6, 2):
        a, b = patients[index:index + 2]
        data.edge(entries[a["id"]], entries[b["id"]], "NON_LINK",
                  "Same surname, first initial and household callback; different full names, birth dates and desk numbers.")
        partial = a["names"][0][0] + ". " + a["names"][0].split()[-1]
        fragment = data.note(rng.choice((
            "Message for desk · {patient} called from {phone}. Card not available.\n",
            "{phone} / {patient}\nAttendant requested a copy; paper slip missing.\n",
        )), {"patient": (partial, "patient_name", "REMOVE"), "phone": (a["phone"], "phone", "REMOVE")},
            "fragment", stress=["ambiguous"], style="latin")
        # The fragment has two plausible household members and no known identity.
        for candidate in (a, b):
            data.edge(fragment, entries[candidate["id"]], "ABSTAIN",
                      "Surname, initial and shared household phone cannot distinguish the candidates.")
    for ext, body, reason in (("json", b'{"packets":[', "truncated_json"),
                              ("txt", b"", "empty_file"), ("txt", b"\xff\x80record", "invalid_utf8")):
        path = data.path("intake", ext)
        (root / "input" / path).write_bytes(body)
        data.malformed.append({"file": path, "reason": reason})
    events = [event for history in visits.values() for event in history]
    truth = {"schema": "secret-wards-fixtures/3", "patients": patients,
             "events": events, "records": data.records, "labels": data.labels,
             "links": data.links, "malformed": data.malformed}
    write_json(root / "truth" / "fixtures.json", truth)
    counts = {key: len(truth[key]) for key in ("patients", "events", "records", "labels", "links", "malformed")}
    counts["input_files"] = len(file_hashes(root / "input"))
    counts["records_by_kind"] = dict(sorted(Counter(record["kind"] for record in data.records).items()))
    counts["links_by_expectation"] = dict(Counter(link["expected"] for link in data.links))
    manifest(root, counts)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("--pilot", action="store_true")
    args = parser.parse_args()
    generate(args.output, args.pilot)


if __name__ == "__main__":
    main()
