"""Build a deterministic fictional Secret Wards holdout and verify its annotations."""

import argparse
from collections import Counter
import csv
from datetime import date, timedelta
from hashlib import sha256
from io import StringIO
import json
from pathlib import Path
from random import Random
from string import Formatter


KINDS = ("discharge", "prescription", "nursing")
STYLES = ("latin", "devanagari", "code_switched")
GIVEN_NAMES = (
    ("Maanvi", "मानवी"), ("Maanika", "मानिका"), ("Raghul", "रघुल"),
    ("Nivaan", "निवान"), ("Ishira", "इशिरा"), ("Tejil", "तेजिल"),
    ("Niral", "निरल"), ("Hiral", "हिरल"), ("Amrita", "अमृता"),
    ("Nishta", "निष्ठा"), ("Vimansh", "विमांश"), ("Yuvan", "युवान"),
    ("Laveen", "लवीन"), ("Anuhya", "अनुह्या"), ("Suhir", "सुहिर"),
    ("Gaurit", "गौरित"), ("Vedish", "वेदिश"), ("Pihuli", "पिहुली"),
)
SURNAMES = (
    ("Pakhrolkar", "पाखरोलकर"), ("Dhavnekot", "धावनेकोट"),
    ("Sirmohre", "सिरमोहरे"), ("Belsarve", "बेलसारवे"),
    ("Kachmurya", "कचमुरिया"), ("Hiranthale", "हिरनथाले"),
    ("Jhunvarim", "झुनवारिम"), ("Tarvangre", "तारवांग्रे"),
    ("Lohavani", "लोहावनी"), ("Sondhral", "सोंध्राल"),
    ("Girvot", "गिरवोट"), ("Mograhel", "मोगराहेल"),
)
FACILITIES = (
    ("Jharpankh Community Infirmary", "झरपंख सामुदायिक चिकित्सालय"),
    ("Koyalbend Ward Centre", "कोयलबेंड वार्ड केंद्र"),
    ("Dhoopgali General Hospital", "धूपगली सामान्य अस्पताल"),
    ("Sonthva Observation Unit", "सोंथवा निगरानी केंद्र"),
)
CLINICIANS = (
    ("Dr. Neel Ovhalek", "डॉ. नील ओवहालेक"),
    ("Dr. Ritu Kanshori", "डॉ. ऋतु कांशोरी"),
    ("Dr. Iman Rathodiya", "डॉ. इमान राठोड़िया"),
    ("Dr. Nila Shonkarvi", "डॉ. नीला शोनकरवी"),
)
LOCALITIES = (
    ("Madhukiran Enclave", "मधुकिरण बस्ती"),
    ("Jaldori Lane", "जलदोरी गली"),
    ("Surpam Court", "सुरपम चौक"),
    ("Indrakund Terrace", "इंद्रकुंड पथ"),
    ("Kanchiloom Colony", "कांचीलूम कॉलोनी"),
)

# Each case provides English and Hindi diagnoses and symptoms, then a coherent order and lab.
CASES = (
    (("tension-type headache", "तनावजन्य सिरदर्द"), ("headache since waking", "सुबह से सिरदर्द"),
     ("paracetamol", "पैरासिटामोल"), "500 mg", ("up to twice daily for 2 days", "दो दिन तक दिन में अधिकतम दो बार"),
     ("Pain score", "4/10", "NRS")),
    (("acute urticaria", "तीव्र पित्ती"), ("itchy raised patches", "उभरे हुए खुजलीदार चकत्ते"),
     ("cetirizine", "सेटिरिज़िन"), "10 mg", ("at night for 3 nights", "तीन रातों तक सोते समय"),
     ("Eosinophils", 3, "%")),
    (("mild dehydration", "हल्का निर्जलीकरण"), ("loose stools and thirst", "दस्त और प्यास"),
     ("oral rehydration solution", "मौखिक पुनर्जलीकरण घोल"), "200 mL",
     ("after each loose stool for 2 days", "दो दिन तक हर दस्त के बाद"),
     ("Serum sodium", 138, "mmol/L")),
    (("iron deficiency anaemia", "लौह की कमी से रक्ताल्पता"), ("tiredness on exertion", "मेहनत करने पर थकान"),
     ("elemental iron", "तत्वीय लौह"), "60 mg", ("once daily for 30 days", "तीस दिन तक रोज़ एक बार"),
     ("Haemoglobin", 10.2, "g/dL")),
    (("reflux oesophagitis", "अम्ल प्रतिवाह से ग्रासनली में सूजन"), ("burning after meals", "खाने के बाद सीने में जलन"),
     ("pantoprazole", "पैंटोप्राज़ोल"), "40 mg", ("before breakfast for 14 days", "चौदह दिन तक नाश्ते से पहले"),
     ("Haemoglobin", 13.6, "g/dL")),
    (("muscle strain", "मांसपेशी में खिंचाव"), ("shoulder pain on lifting", "हाथ उठाते समय कंधे में दर्द"),
     ("paracetamol", "पैरासिटामोल"), "650 mg", ("up to twice daily for 3 days", "तीन दिन तक दिन में अधिकतम दो बार"),
     ("Pain score", "3/10", "NRS")),
)

HEADINGS = {
    ("discharge", "latin"): ("Leaving the ward", "Inpatient exit record"),
    ("discharge", "devanagari"): ("छुट्टी के समय का विवरण", "घर जाने से पहले की समीक्षा"),
    ("discharge", "code_switched"): ("Ward से घर वापसी", "Discharge पर आख़िरी review"),
    ("prescription", "latin"): ("Medicines to take at home", "Treatment slip"),
    ("prescription", "devanagari"): ("दवा लेने का पर्चा", "औषधि निर्देश"),
    ("prescription", "code_switched"): ("घर की दवा | Rx", "Review के बाद की prescription"),
    ("nursing", "latin"): ("Shift handover", "Ward observation log"),
    ("nursing", "devanagari"): ("पाली का हस्तांतरण", "बिस्तर पर निगरानी"),
    ("nursing", "code_switched"): ("Night shift की handover", "Bedside पर की गई checks"),
}

NOTES = {
    ("discharge", "latin"): (
        ("{name} came in on {admitted} with {symptom}.",
         "After {stay} under observation, {clinician} approved discharge on {date}.",
         "Working diagnosis: {diagnosis}. Leaving BP {bp}.",
         "At home: {drug} {dose}, {schedule}."),
        ("Assessment at exit: {diagnosis}. Symptoms recorded: {symptom}.",
         "First day in {facility}: {admitted}. Last day: {date}. Stay: {stay}.",
         "BP at final round: {bp}. {clinician} reviewed the chart for {name}.",
         "Discharge medicine is {drug} {dose} {schedule}."),
        ("Observation started {admitted} for {name}. {symptom} prompted the visit.",
         "Checked by {clinician}. Diagnosis: {diagnosis}. BP {bp}.",
         "Home on {date} after {stay}. Plan: {drug} {dose}, {schedule}."),
    ),
    ("discharge", "devanagari"): (
        ("{name} को {symptom} की शिकायत पर {admitted} को भर्ती किया गया।",
         "{stay} की निगरानी के बाद {clinician} ने {date} को छुट्टी दी।",
         "निदान: {diagnosis}। जाते समय रक्तचाप {bp} था।",
         "घर पर {drug} {dose}, {schedule}।"),
        ("जाँच के आधार पर {diagnosis} दर्ज हुआ। आने पर परेशानी थी {symptom}।",
         "{facility} में {admitted} से {date} तक रहे। निगरानी अवधि {stay}।",
         "रक्तचाप {bp} रहा। {name} की समीक्षा {clinician} ने की।",
         "छुट्टी पर {drug} {dose} {schedule} लेने को कहा गया।"),
        ("{name} की निगरानी {admitted} से शुरू हुई। शिकायत: {symptom}।",
         "{clinician} की समीक्षा में {diagnosis} दर्ज हुआ। रक्तचाप {bp} था।",
         "{stay} के बाद {date} को घर भेजा। सलाह: {drug} {dose}, {schedule}।"),
    ),
    ("discharge", "code_switched"): (
        ("{name} को {symptom} था, इसलिए {admitted} को observation में रखा।",
         "{stay} बाद {clinician} ने {date} की discharge मंज़ूर की।",
         "Final impression {diagnosis} है और exit BP {bp} रहा।",
         "घर के लिए {drug} {dose} लिखी है, {schedule}।"),
        ("{symptom} से आए थे। Final diagnosis {diagnosis} दर्ज किया।",
         "{facility} में admission {admitted} को हुआ, discharge {date} को। कुल stay {stay}।",
         "Final round में {name} का BP {bp} था। Review {clinician} ने किया।",
         "Take-home medicine: {drug} {dose}, {schedule}।"),
        ("{name} को {admitted} से observation में रखा था। कारण था {symptom}।",
         "{clinician} के review में {diagnosis} दर्ज किया। BP {bp} था।",
         "{stay} बाद {date} को घर भेजा। घर पर {drug} {dose} लेना है, {schedule}।"),
    ),
    ("prescription", "latin"): (
        ("{date} • Home treatment for {name}.",
         "C/O {symptom}. Impression: {diagnosis}.",
         "{drug} {dose} | {schedule}.",
         "Issued by {clinician}."),
        ("Write on the bag: {drug}, {dose}, {schedule}.",
         "{name} was seen at {facility} on {date} for {symptom}.",
         "Working diagnosis {diagnosis}. Authorised by {clinician}."),
        ("{name} / {date} / {clinician}",
         "{symptom} on review. Rx {drug} {dose}, {schedule} for {diagnosis}."),
    ),
    ("prescription", "devanagari"): (
        ("{date} को {name} के लिए घर की दवा लिखी।",
         "शिकायत: {symptom}। निदान: {diagnosis}।",
         "{drug} {dose} | {schedule}।",
         "लिखने वाले चिकित्सक {clinician}।"),
        ("दवा के लिफाफे पर लिखें: {drug}, {dose}, {schedule}।",
         "{name} को {symptom} की शिकायत पर {date} को {facility} में देखा।",
         "निदान {diagnosis} है। पर्चे पर {clinician} के हस्ताक्षर।"),
        ("{name} / {date} / {clinician}",
         "शिकायत {symptom}। {diagnosis} के लिए {drug} {dose}, {schedule}।"),
    ),
    ("prescription", "code_switched"): (
        ("{date} का home Rx {name} के लिए है।",
         "C/O {symptom}। Working diagnosis {diagnosis} रखा है।",
         "{drug} {dose} लिखी है, {schedule}।",
         "Prescription {clinician} ने जारी की।"),
        ("Packet पर {drug} {dose} और {schedule} लिख दें।",
         "{facility} में {date} को {name} की review हुई। परेशानी {symptom} थी।",
         "Impression {diagnosis} है। {clinician} ने order पूरा किया।"),
        ("{name} / {date} / {clinician}",
         "{symptom} था। {diagnosis} के लिए Rx में {drug} {dose} रखा, {schedule}।"),
    ),
    ("nursing", "latin"): (
        ("{date}, morning round. {name} was awake and answering clearly.",
         "BP {bp}; pulse {pulse}. Chart lists {diagnosis}.",
         "Report handed to {clinician}."),
        ("BP {bp} / pulse {pulse} on {date}. {name} kept under review.",
         "C/O {symptom}. {clinician} updated before shift change."),
        ("At {facility} on {date}, {name} reported {symptom}.",
         "Bedside readings were BP {bp} and pulse {pulse}. {clinician} acknowledged the chart."),
    ),
    ("nursing", "devanagari"): (
        ("{date}, सुबह का चक्कर। {name} जाग रहे थे और बात कर रहे थे।",
         "रक्तचाप {bp}, नाड़ी {pulse}। चार्ट में {diagnosis} दर्ज है।",
         "{clinician} को जानकारी दे दी गई।"),
        ("{date} को रक्तचाप {bp} और नाड़ी {pulse} दर्ज की। {name} निगरानी में रहे।",
         "शिकायत: {symptom}। पाली बदलने से पहले {clinician} को बताया।"),
        ("{facility} में {date} को {name} ने {symptom} की शिकायत बताई।",
         "बिस्तर पर रक्तचाप {bp} और नाड़ी {pulse} मिली। {clinician} ने चार्ट देखा।"),
    ),
    ("nursing", "code_switched"): (
        ("{date} की सुबह {name} जाग रहे थे और जवाब ठीक दे रहे थे।",
         "Bedside BP {bp} और pulse {pulse} था। Chart में {diagnosis} दर्ज है।",
         "{clinician} को shift report दे दी।"),
        ("{date} को BP {bp} और pulse {pulse} chart किया। {name} को observation में रखा।",
         "C/O {symptom}। Handover से पहले {clinician} को बताया।"),
        ("{facility} में {date} को {name} ने {symptom} बताया।",
         "दोबारा check में BP {bp} और pulse {pulse} मिली। {clinician} ने chart देखा।"),
    ),
}

IDENTITY = {
    "latin": (
        ("MRN {mrn}; DOB {birth}.", "DOB {birth} / record no. {mrn}", "Filed under MRN {mrn} (born {birth})."),
        "Age {age}. Home: {street}, {locality} {postcode}. C/O {guardian} for home contact.",
        "Chart checked: {name}.",
    ),
    "devanagari": (
        ("अभिलेख सं. {mrn}, जन्म {birth}।", "जन्म तिथि {birth} / मरीज़ क्रमांक {mrn}", "पंजीकरण सं. {mrn} (जन्म {birth})।"),
        "उम्र {age} वर्ष। पता {street}, {locality} {postcode}। देखरेख के लिए C/O {guardian}।",
        "चार्ट पर मरीज़ का नाम {name} दोबारा जाँचा।",
    ),
    "code_switched": (
        ("MRN {mrn} है, जन्म {birth}।", "DOB {birth} / फ़ाइल MRN {mrn}", "Chart {mrn} (जन्म {birth}) में दर्ज।"),
        "Age {age} है। घर का पता {street}, {locality} {postcode}। Home contact के लिए C/O {guardian}।",
        "Chart पर {name} का नाम फिर check किया।",
    ),
}

DIGITS = str.maketrans("0123456789", "०१२३४५६७८९")
ROLE_ACTION = {
    "name": ("patient_name", "REMOVE"), "mrn": ("patient_id", "REMOVE"),
    "birth": ("dob", "REMOVE"), "age": ("age", "GENERALIZE"),
    "street": ("address", "REMOVE"), "locality": ("locality", "GENERALIZE"),
    "postcode": ("pincode", "GENERALIZE"), "guardian": ("relationship_name", "REMOVE"),
    "clinician": ("clinician_name", "PRESERVE"), "facility": ("facility", "PRESERVE"),
    "admitted": ("admission_date", "SHIFT"), "date": ("visit_date", "SHIFT"),
    "stay": ("length_of_stay", "PRESERVE"), "symptom": ("complaint", "PRESERVE"),
    "diagnosis": ("diagnosis", "PRESERVE"), "bp": ("blood_pressure", "PRESERVE"),
    "pulse": ("pulse", "PRESERVE"), "drug": ("medication", "PRESERVE"),
    "dose": ("dose", "PRESERVE"), "schedule": ("schedule", "PRESERVE"),
    "lab_test": ("lab_test", "PRESERVE"), "lab_value": ("lab_value", "PRESERVE"),
    "lab_unit": ("unit", "PRESERVE"),
}
EVENT_FIELDS = {"admitted", "date", "stay", "symptom", "diagnosis", "bp", "pulse",
                "drug", "dose", "schedule", "lab_test", "lab_value", "lab_unit"}


class Corpus:
    def __init__(self, output):
        self.output = output
        self.files = {}
        self.rng = Random(874220)
        self.names_rng = Random(295208)
        self.event_facts = {}
        self.truth = {key: [] for key in ("patients", "records", "labels", "events", "links", "malformed")}

    def filename(self, extension):
        name = f"q{self.names_rng.getrandbits(64):016x}.{extension}"
        if name in self.files:
            raise ValueError(f"Duplicate generated filename {name}")
        return name

    def record(self, file, locator, patient=None, event=None, **properties):
        record_id = f"HR-{len(self.truth['records']) + 1:05d}"
        self.truth["records"].append(dict(
            id=record_id, file=file, locator=locator, patient=patient, event=event, **properties))
        return record_id

    def mark(self, file, locator, field, surface, event=None):
        role, action = ROLE_ACTION[field]
        label = dict(file=file, locator=locator, surface=surface, role=role, action=action)
        if event and field in EVENT_FIELDS:
            label.update(event=event, fact=field)
            canonical = self.event_facts[event][field]
            if surface != canonical:
                label["canonical"] = canonical
        self.truth["labels"].append(label)

    def text(self, pattern, values, **record):
        file = self.filename("txt")
        parts = []
        offset = 0
        for literal, field, _, _ in Formatter().parse(pattern):
            parts.append(literal)
            offset += len(literal)
            if field is not None:
                surface = str(values[field])
                self.mark(file, {"start": offset, "end": offset + len(surface)},
                          field, surface, record.get("event"))
                parts.append(surface)
                offset += len(surface)
        self.files[file] = "".join(parts).encode("utf-8")
        return self.record(file, {"document": True}, **record)

    def link(self, left, right, expected, evidence, cross_script=False):
        self.truth["links"].append(dict(left=left, right=right, expected=expected,
                                        evidence=evidence, cross_script=cross_script))

    def write(self):
        if self.output.exists() and any(self.output.iterdir()):
            raise ValueError(f"Output directory must be empty: {self.output}")
        inputs = self.output / "input"
        truth = self.output / "truth"
        inputs.mkdir(parents=True)
        truth.mkdir()
        for name, payload in sorted(self.files.items()):
            (inputs / name).write_bytes(payload)
        fixtures = json_bytes(self.truth)
        (truth / "fixtures.json").write_bytes(fixtures)
        manifest = {
            "schema": "secret-wards-fixtures-v3",
            "counts": dict(input_files=len(self.files), **{key: len(value) for key, value in self.truth.items()}),
            "sha256": {**{f"input/{name}": sha256(payload).hexdigest() for name, payload in sorted(self.files.items())},
                       "truth/fixtures.json": sha256(fixtures).hexdigest()},
        }
        (self.output / "manifest.json").write_bytes(json_bytes(manifest))
        return manifest


def json_bytes(value):
    return (json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n").encode("utf-8")


def create_patients(corpus, count):
    combinations = [(given, surname) for given in GIVEN_NAMES for surname in SURNAMES]
    neighbours = [(GIVEN_NAMES[0], SURNAMES[0]), (GIVEN_NAMES[1], SURNAMES[0])]
    combinations = [pair for pair in combinations if pair not in neighbours]
    corpus.rng.shuffle(combinations)
    patients = []
    for index, (given, surname) in enumerate((neighbours + combinations)[:count]):
        mrn = str(corpus.rng.randrange(480000, 739999))
        if index in (2, 3):
            mrn = ("500", "650")[index - 2]
        while any(patient["mrn"] == mrn for patient in patients):
            mrn = str(corpus.rng.randrange(480000, 739999))
        household = 0 if index < 2 else index - 1
        locality = LOCALITIES[household % len(LOCALITIES)]
        guardian = GIVEN_NAMES[(household + 12) % len(GIVEN_NAMES)]
        street = (f"Flat {household + 11}, Copper Weir Road",
                  f"कॉपर वीयर मार्ग, मकान {household + 11}")
        birth = date(1947 + corpus.rng.randrange(57), corpus.rng.randint(1, 12), corpus.rng.randint(1, 28))
        patient = {
            "id": f"H3-{index + 1:04d}", "names": [f"{given[i]} {surname[i]}" for i in range(2)],
            "mrn": mrn, "birth": birth.isoformat(), "household": f"HH-{household:03d}",
            "street": street, "locality": locality, "postcode": str(890000 + household // 3),
            "guardian": [f"{guardian[i]} {surname[i]}" for i in range(2)],
            "facility": index % len(FACILITIES) if index > 1 else 0,
        }
        patients.append(patient)
        corpus.truth["patients"].append({key: patient[key] for key in ("id", "names", "household")})
    return patients


def create_encounter(corpus, patient, index, followup=False):
    case_index = {2: 0, 3: 5}.get(index, corpus.rng.randrange(len(CASES)))
    diagnosis, symptom, drug, dose, schedule, lab = CASES[case_index]
    stay_days = 1 if followup else corpus.rng.choice((1, 1, 2, 3))
    end = date(2025, 1, 12) + timedelta(days=corpus.rng.randrange(295) + (365 if followup else 0))
    begin = end - timedelta(days=stay_days)
    birth = date.fromisoformat(patient["birth"])
    age = end.year - birth.year - ((end.month, end.day) < (birth.month, birth.day))
    bp = f"{corpus.rng.randrange(105, 139)}/{corpus.rng.randrange(64, 89)}"
    pulse = corpus.rng.randrange(62, 97)
    facts = {
        "admitted": begin.isoformat(), "date": end.isoformat(), "stay": stay_days, "bp": bp,
        "pulse": pulse, "diagnosis": diagnosis[0], "symptom": symptom[0], "drug": drug[0],
        "dose": dose, "schedule": schedule[0], "lab_test": lab[0], "lab_value": lab[1], "lab_unit": lab[2],
    }
    event = f"HE-{len(corpus.truth['events']) + 1:04d}"
    corpus.truth["events"].append(dict(id=event, patient=patient["id"], facts=facts))
    corpus.event_facts[event] = facts
    return {
        "patient": patient, "event": event, "facts": facts, "age": age, "diagnosis": diagnosis,
        "symptom": symptom, "drug": drug, "schedule": schedule,
        "clinician": CLINICIANS[corpus.rng.randrange(len(CLINICIANS))],
    }


def render_values(encounter, style, layout):
    patient = encounter["patient"]
    localized = int(style != "latin")
    hindi = style == "devanagari"
    facts = encounter["facts"]
    values = dict(facts)
    for field in ("diagnosis", "drug"):
        values[field] = encounter[field][int(hindi)]
    for field in ("symptom", "schedule"):
        values[field] = encounter[field][localized]
    values.update(
        name=patient["names"][localized], mrn=patient["mrn"], guardian=patient["guardian"][localized],
        birth=patient["birth"], age=encounter["age"], facility=FACILITIES[patient["facility"]][int(hindi)],
        street=patient["street"][localized], locality=patient["locality"][localized],
        postcode=patient["postcode"], clinician=encounter["clinician"][int(hindi)],
        stay=f"{facts['stay']} दिन" if hindi else f"{facts['stay']} {'day' if facts['stay'] == 1 else 'days'}",
        pulse=f"{facts['pulse']} प्रति मिनट" if hindi else f"{facts['pulse']} bpm",
    )
    if hindi:
        if layout == 1:
            for field in ("admitted", "date", "bp", "age", "stay", "pulse"):
                values[field] = str(values[field]).translate(DIGITS)
        values["dose"] = values["dose"].replace("mg", "मि.ग्रा.").replace("mL", "मि.ली.")
    return values


LAYOUTS = ("progression", "bulleted", "compact_sections")


def note_body(lines, layout, heading):
    if layout == 1:
        lines = ["• " + line for line in lines]
    body = ("\n", "\n", "\n\n")[layout].join(lines)
    return f"{heading}\n\n{body}\n" if heading else f"{body}\n"


def render_note(corpus, encounter, kind, style, layout, heading_index, flags=()):
    value = render_values(encounter, style, layout)
    heading = None if heading_index == 0 else HEADINGS[kind, style][heading_index - 1]
    identity, household, repeat = IDENTITY[style]
    lines = list(NOTES[kind, style][layout])
    lines.insert((0, len(lines), 1)[layout], identity[layout])
    if "relationship_and_complaint" in flags:
        lines.extend((household, "C/O {symptom}"))
    if "same_digits_different_role" in flags:
        lines.append("MRN {mrn} | दवा {dose}" if style != "latin" else "MRN {mrn} | medication {dose}")
    if "repeated_patient_name" in flags:
        lines.append(repeat)
    if "same_name_different_role" in flags:
        value["clinician"] = value["name"]
        title = "डॉ. " if style == "devanagari" else "Dr. "
        lines = [line.replace("{clinician}", title + "{clinician}") for line in lines]
    pattern = note_body(lines, layout, heading)
    return corpus.text(pattern, value, patient=encounter["patient"]["id"], event=encounter["event"],
                       kind=kind, style=style, heading=heading,
                       layout=LAYOUTS[layout], stress=list(flags))


def write_registration(corpus, encounters):
    indexes = list(range(len(encounters)))
    corpus.rng.shuffle(indexes)
    result = {}
    fields = ("mrn", "name", "birth", "age", "street", "locality", "postcode", "guardian", "facility")
    columns = ("MRN", "Registered name", "Birth date", "Age on file", "Street", "Locality", "Postal sector",
               "Home contact", "Registration site")
    for start in range(0, len(indexes), 11):
        file = corpus.filename("csv")
        stream = StringIO(newline="")
        writer = csv.writer(stream, lineterminator="\r\n")
        writer.writerow(columns)
        for row, encounter_index in enumerate(indexes[start:start + 11]):
            encounter = encounters[encounter_index]
            style = "devanagari" if encounter_index % 4 == 3 else "latin"
            values = render_values(encounter, style, 0)
            record = corpus.record(file, {"row": row}, encounter["patient"]["id"], kind="registration",
                                   style=style, heading=None, layout="register", stress=[])
            writer.writerow([values[field] for field in fields])
            for column, field in zip(columns, fields):
                corpus.mark(file, {"row": row, "column": column}, field, str(values[field]))
            result[encounter_index] = record
        corpus.files[file] = stream.getvalue().encode("utf-8")
    return result


def write_lab(corpus, encounters):
    indexes = list(range(len(encounters)))
    corpus.rng.shuffle(indexes)
    result = {}
    for start in range(0, len(indexes), 5):
        file = corpus.filename("json")
        samples = []
        for encounter_index in indexes[start:start + 5]:
            encounter = encounters[encounter_index]
            patient, event, facts = (encounter[key] for key in ("patient", "event", "facts"))
            style = "devanagari" if encounter_index % 4 in (1, 2) else "latin"
            values = render_values(encounter, style, 0)
            pointer = f"/samples/{len(samples)}"
            fields = (
                ("subject/mrn", "mrn"), ("subject/name", "name"), ("subject/birthDate", "birth"),
                ("collectionDate", "date"), ("requestedBy", "clinician"), ("observations/0/analyte", "lab_test"),
                ("observations/0/result", "lab_value"), ("observations/0/unit", "lab_unit"),
            )
            for key, field in fields:
                corpus.mark(file, {"pointer": f"{pointer}/{key}"}, field, values[field], event)
            samples.append({
                "subject": {"mrn": values["mrn"], "name": values["name"], "birthDate": values["birth"]},
                "collectionDate": facts["date"], "requestedBy": values["clinician"],
                "observations": [{"analyte": facts["lab_test"], "result": facts["lab_value"], "unit": facts["lab_unit"]}],
            })
            result[encounter_index] = corpus.record(
                file, {"pointer": pointer}, patient["id"], event, kind="lab", style=style,
                heading=None, layout="nested_samples", stress=[])
        corpus.files[file] = json_bytes({"samples": samples})
    return result


CLEAN_NOTES = {
    ("discharge", "latin"): (
        ("Observed for {stay} before leaving the ward.", "Exit BP {bp}. Home instructions reviewed by {clinician}.",
         "The discharge copy went in the take-home envelope."),
        ("Final round complete. Reviewed by {clinician}.", "BP at exit: {bp}. Total stay: {stay}.",
         "Walking without assistance at time of discharge."),
        ("Decision: home after {stay} of observation.", "Discharge BP: {bp}.",
         "{clinician} signed the instructions at the ward desk."),
    ),
    ("discharge", "devanagari"): (
        ("{stay} तक निगरानी के बाद घर जाने की अनुमति दी।", "जाते समय रक्तचाप {bp} था।",
         "{clinician} ने घर पर देखभाल के निर्देश समझाए।"),
        ("आख़िरी जाँच में रक्तचाप {bp} मिला।", "कुल निगरानी {stay} की रही।",
         "छुट्टी के काग़ज़ पर {clinician} ने हस्ताक्षर किए।"),
        ("छुट्टी की समीक्षा {clinician} ने की।", "घर जाते वक्त रक्तचाप {bp} दर्ज हुआ।",
         "{stay} की निगरानी समाप्त हुई।"),
    ),
    ("discharge", "code_switched"): (
        ("{stay} observation के बाद घर भेजा।", "Exit BP {bp} था और walking में दिक्कत नहीं थी।",
         "Discharge instructions {clinician} ने समझाए।"),
        ("Last round में BP {bp} था।", "Total stay {stay}। Ward से निकलने की अनुमति मिली।",
         "Take-home copy पर {clinician} ने sign किया।"),
        ("{clinician} की final review पूरी हुई।", "Exit chart में BP {bp} लिखा है।",
         "{stay} बाद discharge कर दिया।"),
    ),
    ("prescription", "latin"): (
        ("Home order prepared after review.", "Take {drug} {dose}, {schedule}.",
         "Signed by {clinician}."),
        ("Bag label: {drug} {dose}.", "Directions: {schedule}.",
         "Pharmacy copy signed by {clinician}."),
        ("Authorised by {clinician} after review.", "Continue {drug} {dose}, {schedule}.",
         "Directions printed on the medicine pack."),
    ),
    ("prescription", "devanagari"): (
        ("घर पर लेने के लिए दवा लिख दी गई।", "{drug} {dose}, {schedule}।",
         "पर्चे पर {clinician} के हस्ताक्षर हैं।"),
        ("लिफ़ाफ़े पर दवा का नाम और मात्रा: {drug} {dose}।", "समय: {schedule}।",
         "दवा की पुष्टि {clinician} ने की।"),
        ("{clinician} ने दवा की सूची की समीक्षा की।", "{drug} {dose} {schedule} लें।",
         "निर्देश दवा के पैकेट पर लिखे हैं।"),
    ),
    ("prescription", "code_switched"): (
        ("Review के बाद home Rx लिख दिया।", "{drug} {dose} लेना है, {schedule}।",
         "Order {clinician} ने sign किया।"),
        ("Bag label पर {drug} {dose} लिखा है।", "Timing: {schedule}।",
         "Pharmacy copy {clinician} ने देख ली।"),
        ("{clinician} ने medicines review कीं।", "{drug} {dose} जारी रखें, {schedule}।",
         "Instructions packet पर लिखे हैं।"),
    ),
    ("nursing", "latin"): (
        ("Awake and answering clearly on the morning round.", "Bedside BP {bp}; pulse {pulse}.",
         "Shift update passed to {clinician}."),
        ("Observations: BP {bp}; pulse {pulse}.", "Walked to the chair and back without help.",
         "Report sent to {clinician} before the round finished."),
        ("After a rest, readings were BP {bp} and pulse {pulse}.", "No dizziness while seated.",
         "Updated {clinician} during handover."),
    ),
    ("nursing", "devanagari"): (
        ("सुबह के चक्कर में जाग रहे थे और बात कर रहे थे।", "रक्तचाप {bp}, नाड़ी {pulse}।",
         "पाली का विवरण {clinician} को दिया।"),
        ("बिस्तर पर रक्तचाप {bp} और नाड़ी {pulse} दर्ज हुई।", "बिना सहारे कुर्सी तक गए।",
         "पाली बदलते समय {clinician} को बताया।"),
        ("कुछ देर आराम के बाद रक्तचाप {bp}, नाड़ी {pulse} मिली।", "बैठे हुए चक्कर नहीं आया।",
         "चार्ट {clinician} ने देखा।"),
    ),
    ("nursing", "code_switched"): (
        ("Morning round में जाग रहे थे और जवाब साफ़ था।", "Bedside BP {bp} और pulse {pulse} chart किया।",
         "{clinician} को shift report भेजी।"),
        ("Vitals check: BP {bp}, pulse {pulse}।", "बिना help के कुर्सी तक गए।",
         "Handover से पहले {clinician} को update दिया।"),
        ("Rest के बाद BP {bp} और pulse {pulse} मिला।", "बैठे हुए dizziness नहीं थी।",
         "{clinician} ने chart की readings देखीं।"),
    ),
}


def write_controls(corpus):
    for (kind, style), layouts in CLEAN_NOTES.items():
        hindi = style == "devanagari"
        for layout, lines in enumerate(layouts):
            for heading in (None, *HEADINGS[kind, style]):
                _, _, drug, dose, schedule, _ = corpus.rng.choice(CASES)
                stay = corpus.rng.randrange(1, 4)
                pulse = corpus.rng.randrange(62, 97)
                values = {
                    "clinician": corpus.rng.choice(CLINICIANS)[int(hindi)],
                    "bp": f"{corpus.rng.randrange(105, 139)}/{corpus.rng.randrange(64, 89)}",
                    "pulse": f"{pulse} प्रति मिनट" if hindi else f"{pulse} bpm",
                    "stay": f"{stay} दिन" if hindi else f"{stay} {'day' if stay == 1 else 'days'}",
                    "drug": drug[int(hindi)], "schedule": schedule[int(style != "latin")], "dose": dose,
                }
                if hindi:
                    values["dose"] = dose.replace("mg", "मि.ग्रा.").replace("mL", "मि.ली.")
                    if layout == 1:
                        for field in ("bp", "pulse", "stay"):
                            values[field] = values[field].translate(DIGITS)
                corpus.text(note_body(lines, layout, heading), values, kind=kind, style=style, heading=heading,
                            layout=LAYOUTS[layout], stress=["clean_control"])


def write_fragments_and_malformed(corpus, patients, registration):
    first = patients[0]
    values = {
        "name": "M. Pakhrolkar", "guardian": first["guardian"][0], "locality": first["locality"][0],
    }
    fragment = corpus.text(
        "Forwarded to desk: {name} का envelope आया है।\nC/O {guardian}, {locality}.\n"
        "किस chart में लगाना है? The sheet was torn above the number.\n",
        values, kind="chat", style="code_switched", heading=None, layout="forwarded_fragment",
        stress=["abstain", "shared_household", "name_fragment"],
    )
    for index in (0, 1):
        corpus.link(fragment, registration[index], "ABSTAIN",
                    "Shared surname initial, contact and locality fit both registrations. No MRN or birth date survives.")
    corpus.link(registration[0], registration[1], "NON_LINK",
                "Similar given names and identical home address and contact, but different MRNs and dates of birth.")
    malformed = (
        ("json", b'{"samples":[{"subject":{"name":"unfinished"}}', "invalid_json"),
        ("csv", b'MRN,Registered name\n004,"unterminated\n', "invalid_csv"),
        ("txt", b'\x81\x8d\x8f\x90\x9d\x00\x00truncated', "invalid_encoding"),
    )
    for extension, payload, reason in malformed:
        file = corpus.filename(extension)
        corpus.files[file] = payload
        corpus.truth["malformed"].append({"file": file, "reason": reason})


def build(output, pilot):
    corpus = Corpus(output)
    repetitions = 1 if pilot else 2
    patients = create_patients(corpus, 27 * repetitions)
    encounters = [create_encounter(corpus, patient, index) for index, patient in enumerate(patients)]
    design = {}
    for kind in KINDS:
        for style in STYLES:
            pairs = [(layout, heading) for layout in range(3) for heading in range(3)] * repetitions
            corpus.rng.shuffle(pairs)
            design[kind, style] = pairs
    main_records = []
    for index, encounter in enumerate(encounters):
        notes = {}
        for kind_index, kind in enumerate(KINDS):
            style = STYLES[(index // 9 + kind_index + 2) % len(STYLES)]
            layout, heading = design[kind, style].pop()
            flags = []
            if (index < 2 or index % 11 == 6) and kind == "nursing":
                flags.append("relationship_and_complaint")
            if index in (2, 3) and kind == "prescription":
                flags.append("same_digits_different_role")
            if index in (4, 13, 22) and kind == "prescription":
                flags.extend(("repeated_patient_name", "same_name_different_role"))
            notes[style] = render_note(corpus, encounter, kind, style, layout, heading, flags)
        main_records.append(notes)
    registration = write_registration(corpus, encounters)
    repeat_indexes = (0, 5, 11) if pilot else (0, 5, 11, 29, 41, 48)
    followups = [create_encounter(corpus, patients[index], index, followup=True) for index in repeat_indexes]
    labs = write_lab(corpus, encounters + followups)
    for index, notes in enumerate(main_records):
        for style in ("devanagari", "code_switched"):
            corpus.link(notes["latin"], notes[style], "LINK",
                        "Transliterated full name, same facility MRN and same ISO birth date.", cross_script=True)
        registration_style = "devanagari" if index % 4 == 3 else "latin"
        target_style = "latin" if registration_style == "devanagari" else "devanagari"
        corpus.link(registration[index], notes[target_style], "LINK",
                    "Register and narrative agree on birth date and MRN; the full name is rendered in two scripts.",
                    cross_script=True)
        lab_style = "devanagari" if index % 4 in (1, 2) else "latin"
        corpus.link(notes[lab_style], labs[index], "LINK",
                    "Laboratory subject MRN, full name, birth date and collection day match the clinical note.")
    corpus.link(main_records[0]["latin"], main_records[1]["devanagari"], "NON_LINK",
                "Shared home-contact evidence and close transliterated names must not override different MRNs and birth dates.",
                cross_script=True)
    for followup_index, original_index in enumerate(repeat_indexes, start=len(encounters)):
        cross_script = ((followup_index % 4 in (1, 2)) != (original_index % 4 in (1, 2)))
        corpus.link(labs[original_index], labs[followup_index], "LINK",
                    "A separate later collection date with the same subject MRN and birth date.",
                    cross_script=cross_script)
    write_controls(corpus)
    write_fragments_and_malformed(corpus, patients, registration)
    manifest = corpus.write()
    verify(output, repetitions)
    return manifest


def read_pointer(document, pointer):
    for part in pointer.split("/")[1:]:
        key = part.replace("~1", "/").replace("~0", "~")
        document = document[int(key) if isinstance(document, list) else key]
    return document


def read_locator(document, locator):
    if "start" in locator:
        start, end = locator["start"], locator["end"]
        assert 0 <= start < end <= len(document)
        return document[start:end]
    if "row" in locator:
        row = document[locator["row"]]
        return row[locator["column"]] if "column" in locator else row
    if "pointer" in locator:
        return read_pointer(document, locator["pointer"])
    assert locator == {"document": True} and isinstance(document, str)
    return document


def verify(output, repetitions):
    manifest = json.loads((output / "manifest.json").read_bytes())
    for file, checksum in manifest["sha256"].items():
        assert sha256((output / file).read_bytes()).hexdigest() == checksum, file
    fixtures = json.loads((output / "truth" / "fixtures.json").read_bytes())
    assert manifest["counts"] == dict(
        input_files=len(list((output / "input").iterdir())), **{key: len(rows) for key, rows in fixtures.items()})
    malformed = {row["file"]: row["reason"] for row in fixtures["malformed"]}
    documents = {}
    for path in (output / "input").iterdir():
        payload = path.read_bytes()
        try:
            contents = payload.decode("utf-8")
            if path.suffix == ".csv":
                contents = list(csv.DictReader(StringIO(contents, newline=""), strict=True))
            elif path.suffix == ".json":
                contents = json.loads(contents)
        except (UnicodeDecodeError, json.JSONDecodeError, csv.Error) as error:
            expected = {UnicodeDecodeError: "invalid_encoding", json.JSONDecodeError: "invalid_json",
                        csv.Error: "invalid_csv"}
            assert malformed[path.name] == expected[type(error)], path.name
            continue
        assert path.name not in malformed, path.name
        documents[path.name] = contents

    patients = {patient["id"]: patient for patient in fixtures["patients"]}
    events = {event["id"]: event for event in fixtures["events"]}
    records = {record["id"]: record for record in fixtures["records"]}
    assert len(records) == len(fixtures["records"])
    roles_by_file = {}
    labels_by_file = {}
    for row in fixtures["labels"]:
        file = row["file"]
        actual = read_locator(documents[file], row["locator"])
        assert actual == row["surface"] and type(actual) is type(row["surface"]), row
        roles_by_file.setdefault(file, set()).add(row["role"])
        labels_by_file.setdefault(file, []).append(row)
        if "event" in row:
            expected = events[row["event"]]["facts"][row["fact"]]
            assert row.get("canonical", row["surface"]) == expected, row
    for labels in labels_by_file.values():
        end = 0
        for row in labels:
            if "start" in row["locator"]:
                assert end <= row["locator"]["start"], row
                end = row["locator"]["end"]
    crossing = Counter()
    clean_crossing = Counter()
    note_count = 0
    for record in records.values():
        file = record["file"]
        read_locator(documents[file], record["locator"])
        if record["patient"]:
            assert record["patient"] in patients, record
        if record["event"]:
            assert events[record["event"]]["patient"] == record["patient"], record
        if record["kind"] not in KINDS:
            continue
        kind, style = record["kind"], record["style"]
        labels = labels_by_file[file]
        if "clean_control" in record["stress"]:
            clean_crossing[kind, style, record["heading"], record["layout"]] += 1
            assert record["patient"] is None and record["event"] is None, record
            assert all(label["action"] == "PRESERVE" for label in labels), record
            continue
        crossing[kind, style, record["heading"], record["layout"]] += 1
        note_count += 1
        assert {"patient_name", "clinician_name", "patient_id", "dob", "visit_date"} <= roles_by_file[file], record
        if "same_digits_different_role" in record["stress"]:
            mrn = next(label["surface"] for label in labels if label["role"] == "patient_id")
            dose = next(label["surface"] for label in labels if label["role"] == "dose")
            assert dose == (mrn + " mg") and f"MRN {mrn} | medication {dose}" in documents[file], record
        if "same_name_different_role" in record["stress"]:
            assert Counter(label["surface"] for label in labels if label["role"] == "patient_name") == {
                next(label["surface"] for label in labels if label["role"] == "clinician_name"): 2
            }, record
    assert note_count == 81 * repetitions
    for kind, style in HEADINGS:
        for heading in (None, *HEADINGS[kind, style]):
            for layout in LAYOUTS:
                assert crossing[kind, style, heading, layout] == repetitions, (kind, style, heading, layout)
                assert clean_crossing[kind, style, heading, layout] == 1, (kind, style, heading, layout)

    assert len({record["file"] for record in records.values()}) == len(documents)
    for link in fixtures["links"]:
        left = records[link["left"]]["patient"]
        right = records[link["right"]]["patient"]
        if link["expected"] == "LINK":
            assert left and left == right, link
        elif link["expected"] == "NON_LINK":
            assert left and right and left != right, link
        else:
            assert link["expected"] == "ABSTAIN" and (not left or not right), link


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path, help="Empty directory for input, truth and manifest")
    parser.add_argument("--pilot", action="store_true", help="Generate one example per heading and layout crossing")
    options = parser.parse_args()
    manifest = build(options.output, options.pilot)
    print(json.dumps(manifest["counts"], sort_keys=True))


if __name__ == "__main__":
    main()
