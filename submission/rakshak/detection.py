"""Deterministic identifier findings in original Unicode code-point coordinates."""
from dataclasses import dataclass
import re
import unicodedata

from .source_context import normalize_label

MAX_UNIT = 524288
LOCALIZED_PATIENT_LABELS = ("mareez ka naam", "ರೋಗಿಯ ಹೆಸರು", "நோயாளியின் பெயர்")

FIELD_GROUPS = {
    "NAME": "name|patient|patient name|patient full name|full name|first name|last name|surname|"
            "patientname|alternate patient name|नाम|मरीज का नाम|रोगी का नाम|मरीज़|मरीज|रोगी|"
            + "|".join(LOCALIZED_PATIENT_LABELS),
    "RELATIVE": "relative|रिश्तेदार|relative name|father name|mother name|husband name|guardian|guardian name|attendant|caregiver",
    "PHONE": "phone|phone number|patient phone|mobile|mobile number|mobile no|contact no|contact number|telephone|tel|फोन|फ़ोन|मोबाइल",
    "EMAIL": "email|email address|e mail",
    "AADHAAR": "aadhaar|aadhaar no|aadhr no|aadhaar number|aadhar|aadhaar masked|masked aadhaar|आधार",
    "ABHA": "abha|abha no|abha number|abha address",
    "MRN": "mrn|patient id|patientid|patient identifier|uhid|ipd no|opd no|registration no|hospital id|admission id|admission no",
    "ADDRESS": "address|patient address|residence|street|house no|village|village mohalla|mohalla|landmark|पता",
    "PIN": "pin|pin code|pincode|zip|postal code",
    "DOB": "dob|date of birth|birth date|birthdate|जन्म तिथि|जन्मतिथि",
    "PAN": "pan|pan no|pan number",
    "INSURANCE_ID": "insurance id|insurance number|policy number|policy no|member id",
    "PATH": "source path|original path|original filename|input path|original file",
}
FHIR_NAME_TYPES = {"contact name": "NAME", "related person name": "RELATIVE"}
EXPLICIT_NAME_ROLES = {
    "patient": "patient", "patient name": "patient", "patient full name": "patient",
    "मरीज का नाम": "patient", "रोगी का नाम": "patient",
    "contact name": "contact", "related person name": "related_person",
    "relative": "relative", "relative name": "relative", "father name": "relative",
    "mother name": "relative", "husband name": "relative", "रिश्तेदार": "relative",
    **dict.fromkeys(LOCALIZED_PATIENT_LABELS, "patient"),
}
FIELDS = {label: kind for kind, labels in FIELD_GROUPS.items() for label in labels.split("|")}
LABELS = "|".join(re.escape(label).replace(r"\ ", r"[ \t_-]{1,8}")
                  for label in sorted(FIELDS, key=len, reverse=True))
LABELED = re.compile(
    r"(?:^|[\n;,|])[ \t]{0,32}(" + LABELS +
    r")(?:[ \t]*[:：=#][ \t]{0,32}|[ \t]{1,8}/[ \t]{1,8})"
    r"((?:[^\r\n;,|]|(?<=\d),(?=\d)){1,160})", re.I,
)
NAME_INITIALS = re.compile(r",[ \t]*(?:[^\W\d_]\.[ \t]*){1,3}(?=$|[\r\n;,|])")
PATIENT_ROLE_FIELD = re.compile(r"(?:patient display|(?:referred|admitted|enrolled) (?:subject|person)|beneficiary)(?: name)?")
CHART_FIELD = re.compile(
    r"(?:medical record|patient (?:chart|record)|chart) (?:no|number|id|identifier|ref|reference)"
)
CHART_VALUE = r"[^\W_]+(?:[-./][^\W_]+)*"
CHART_CUE = re.compile(
    r"(?im)^[ \t]*(?:chart|medical[ \t]+record)[ \t]*(?:\#|"
    r"(?:number|no\.?|id|identifier)[ \t]*[:=#])[ \t]*(" + CHART_VALUE +
    r")(?=$|[\s,;|])"
)
LABEL_SPACES = str.maketrans({"\u00a0": " ", "\u202f": " "})
DOSE = r"\d+(?:[.,]\d+)?[ \t]*(?:mg|mcg|[µμ]g|g|ml|iu|units?)\b"
INLINE_CLINICAL = re.compile(
    r"(?:^|[ \t])(?:\([ \t]*)?(?:"
    r"(?:(?:dose|dosage)(?:[ \t]*[:=][ \t]*|[ \t]+))?" + DOSE
    + r"|(?:(?:medication|rx)[ \t]*[:=][ \t]*[\w-]{1,40}|metformin|amlodipine|salbutamol)[ \t]+" + DOSE
    + r"|follow[ -]up[ \t]+in[ \t]+\d+[ \t]+(?:hours?|days?|weeks?|months?)\b)", re.I,
)
NAME_TOKEN = r"[A-Za-z\u0900-\u097f][A-Za-z\u0900-\u097f.'’\-]{0,29}"
NAME = NAME_TOKEN + r"(?:[ \t]+" + NAME_TOKEN + r"){0,2}"
CALLER = re.compile(r"(?i:\b(?:called by|visitor|attendant)\b[ \t]{0,8}[:=]?[ \t]{1,8})(" +
                    NAME + r")(?=[ \t]{1,8}(?:\+?\d|\()|$|[,;\r\n])")
VISITOR = re.compile(r"(?m)^\d{1,2}:\d{2}[ \t]+-[ \t]+(" + NAME +
                     r")[ \t]+\((?i:attendant|visitor|guardian)\b")
RELATIVE = re.compile(r"\b([SDWC]/o)[ \t]+(" + NAME + r")(?=$|[\r\n;,|])", re.I)
RELATIONSHIP_LINE = re.compile(r"(?:^|[\n;,|])[ \t]*[SDW]/o[ \t]+([^\r\n;,|]{1,160})(?=$|[\r\n;,|])", re.I)
HONORIFIC = re.compile(r"(?im)^[ \t]{0,16}(" + NAME + r")[ \t]+(?:ji|sahab|didi)[ \t]+(?:aaye|aayi|ka|ki)\b")
INLINE_PHONE = re.compile(r"(?i)\b(?:phone|mob|mobile)[ \t]{1,8}((?:\+91[ -]?)?\d{5}[ -]?\d{5})(?!\d)")
INLINE_RELATIVE = re.compile(r"(?i)\b([SDW]/o)[ \t]+(" + NAME + r")\.(?=[ \t]+(?:Phone|Mob|Mobile)\b)")
COMPLAINT = re.compile(r"(?:^|[ \t])(?:fever|cough|pain|vomiting|weakness|headache|dizziness|chakkar|"
                       r"bukhar|khansi|बुखार|खांसी|चक्कर)(?=$|[\s.])", re.I)
CONTACT_CUE = re.compile(r"(?im)(?:^|\n)[ \t]*(?:patient|patient name|नाम)[ \t]*:[^\r\n]{1,160}\r?\n[ \t]*$")
CARE_OF_FIELD = re.compile(r"(?i)(?:^|\n)[ \t]*(?:address|contact|attendant)(?:[ \t]*\(attendant\))?[ \t]*:[ \t]*$")
CLINICAL = re.compile(r"\b(?:dose|dosage|lab result|observation value|vital|specimen)\b")
MEASUREMENT = re.compile(r"\s*(?:mg(?:/dL)?|mmHg|mmol/L|mL|mcg|µg)\b", re.I)
ADMIN = re.compile(r"\b(?:tracking|batch|specimen|ward|product) (?:code|id|number)\b")
NULLS = {"", "-", "n/a", "na", "none", "unknown", "null", "not available", "redacted", "withheld"}

SHAPES = (
    ("EMAIL", re.compile(r"(?<![\w.+-])[\w.+-]{1,64}@[\w-]{1,63}(?:\.[\w-]{1,63}){1,4}(?![\w.-])", re.I)),
    ("PAN", re.compile(r"(?<![a-z0-9])[A-Z]{5}[0-9]{4}[A-Z](?![a-z0-9])", re.I)),
    ("MRN", re.compile(r"(?<![a-z0-9])(?:UHID|MRN|IPD|OPD|SNJ|JJH|ADM|DHH)[- /]?[0-9]{3,12}(?:[-/][0-9]{3,12})?(?![a-z0-9])", re.I)),
    ("ABHA", re.compile(r"(?<![a-z0-9])[0-9]{2}[ -]?[0-9]{4}[ -]?[0-9]{4}[ -]?[0-9]{4}(?![a-z0-9])", re.I)),
    ("AADHAAR", re.compile(r"(?<![a-z0-9])(?:[0-9]{4}[ -]?[0-9]{4}|[xX*]{4}[ -]?[xX*]{4})[ -]?[0-9]{4}(?![a-z0-9])", re.I)),
    ("PHONE", re.compile(r"(?<![a-z0-9])(?:\+91[ -]?|0)?[6-9][0-9]{4}[ -]?[0-9]{5}(?![a-z0-9])", re.I)),
)
NUMERIC = {"PHONE", "AADHAAR", "ABHA"}
OPAQUE_KEY = re.compile(r"[A-Za-z]{3,40}[0-9]{6,16}")
FILE_NAME = re.compile(r"(?i)^(?:discharge_summary|patient|prescription|report)[_-](?:[a-z]{2,30}[_ -])+[a-z]{2,30}(?=[_-](?:[A-Z]{2,8}[-_]?)?[0-9])")


@dataclass(frozen=True)
class SourceUnit:
    text: str
    label: str = ""
    channel: str = "content"
    section: str = ""
    unit_of_measure: str = ""


@dataclass(frozen=True)
class Finding:
    start: int
    end: int
    kind: str
    score: float
    reason: str
    role: str | None = None


@dataclass(frozen=True)
class DetectionResult:
    findings: tuple[Finding, ...] = ()
    review: tuple[Finding, ...] = ()
    error: str | None = None


def comparison_view(text):
    characters = []
    positions = []
    for i, character in enumerate(text):
        if (character == "\u200b" and 0 < i < len(text) - 1
                and text[i - 1].isdecimal() and text[i + 1].isdecimal()):
            continue
        characters.append(str(unicodedata.decimal(character, character)))
        positions.append(i)
    return "".join(characters), positions


def identifier_prefix(value, kind):
    if kind in {"NAME", "RELATIVE"}:
        clinical = INLINE_CLINICAL.search(value)
        if clinical:
            value = value[:clinical.start()]
    return value.rstrip()


def name_word(token):
    return bool(token) and token[0].isalpha() and all(
        char.isalpha() or unicodedata.category(char).startswith("M") or char in ".'’-"
        for char in token
    )


def person_name(value):
    surname, comma, initials = value.partition(",")
    if comma:
        return name_word(surname.strip()) and bool(NAME_INITIALS.fullmatch(comma + initials))
    words = value.split()
    return 2 <= len(words) <= 5 and all(map(name_word, words))


def chart_number(value):
    return 3 <= len(value) <= 64 and any(char.isdecimal() for char in value)


def detect(unit: SourceUnit) -> DetectionResult:
    source = unit.text
    if len(source) > MAX_UNIT:
        return DetectionResult(error="input_limit")
    if not source.strip() or source.strip().casefold() in NULLS:
        return DetectionResult()
    label = normalize_label(unit.label)
    typed = FIELDS.get(label)
    if unit.section == "fhir":
        typed = FHIR_NAME_TYPES.get(label, typed)
    accepted = []
    if not typed and unit.channel == "content":
        value = source.strip()
        start = len(source) - len(source.lstrip())
        if PATIENT_ROLE_FIELD.fullmatch(label) and person_name(value):
            return DetectionResult((Finding(start, start + len(value), "NAME", .94,
                                            "patient_field_context", "patient"),))
        if CHART_FIELD.fullmatch(label) and chart_number(value) and re.fullmatch(CHART_VALUE, value):
            return DetectionResult((Finding(start, start + len(value), "MRN", .94, "chart_context"),))
    if typed and unit.channel in {"content", "metadata"}:
        value = source.strip()
        start = len(source) - len(source.lstrip())
        prefix = identifier_prefix(value.translate(LABEL_SPACES), typed)
        if prefix:
            location = Finding(start, start + len(prefix), typed, .98, "typed_field",
                               EXPLICIT_NAME_ROLES.get(label))
            if len(prefix) == len(value):
                return DetectionResult((location,))
            accepted.append(location)

    review = []
    # These cue-space substitutions are one-to-one in code points.
    label_view = source.translate(LABEL_SPACES) if "\u00a0" in source or "\u202f" in source else source
    for match in LABELED.finditer(label_view):
        inline_label = normalize_label(match[1])
        kind = FIELDS.get(inline_label)
        value = identifier_prefix(match[2], kind)
        if kind in {"NAME", "RELATIVE"} and value == match[2].rstrip() and name_word(value):
            if initials := NAME_INITIALS.match(label_view, match.end(2)):
                value = label_view[match.start(2):initials.end()].rstrip()
        if "/" in label_view[match.end(1):match.start(2)] and (
                kind not in {"NAME", "RELATIVE"} or not person_name(value)):
            continue
        if kind and value.casefold() not in NULLS:
            accepted.append(Finding(match.start(2), match.start(2) + len(value), kind, .94,
                                    "local_label", EXPLICIT_NAME_ROLES.get(inline_label)))
    for pattern, kind in ((HONORIFIC, "NAME"), (INLINE_PHONE, "PHONE")):
        for match in pattern.finditer(source):
            accepted.append(Finding(*match.span(1), kind, .90, "local_role"))
    for match in CHART_CUE.finditer(label_view):
        if chart_number(match[1]):
            accepted.append(Finding(*match.span(1), "MRN", .94, "chart_context"))
    for pattern in (CALLER, VISITOR):
        for match in pattern.finditer(source):
            accepted.append(Finding(*match.span(1), "RELATIVE", .90, "local_role"))
    for match in INLINE_RELATIVE.finditer(source):
        accepted.append(Finding(*match.span(2), "RELATIVE", .89, "relationship", "relative"))
    for match in RELATIONSHIP_LINE.finditer(label_view):
        value = identifier_prefix(match[1], "RELATIVE")
        if person_name(value):
            accepted.append(Finding(match.start(1), match.start(1) + len(value),
                                    "RELATIVE", .87, "relationship", "relative"))
    for match in RELATIVE.finditer(source):
        start, end = match.span(2)
        role = "contact" if match[1].casefold() == "c/o" else "relative"
        finding = Finding(start, end, "RELATIVE", .85, "relationship", role)
        prefix = source[max(0, match.start() - 3):match.start()].casefold()
        if prefix.endswith(("k/", "h/")):
            continue
        if match[1].casefold() != "c/o":
            accepted.append(finding)
        elif not COMPLAINT.search(match[2]):
            context = source[max(0, match.start() - 200):match.start()]
            name_like = match[2].istitle() and len(match[2].split()) >= 2
            if (unit.section == "contact" or CARE_OF_FIELD.search(context)
                    or (name_like and CONTACT_CUE.search(context))):
                accepted.append(finding)
            else:
                review.append(finding)
    if unit.channel in {"filename", "key", "header"}:
        stem = source.rsplit(".", 1)[0] if unit.channel == "filename" else source
        if OPAQUE_KEY.fullmatch(stem):
            accepted.append(Finding(0, len(stem), "IDENTIFIER", .85, "opaque_label"))
    if unit.channel == "filename":
        match = FILE_NAME.match(source)
        if match:
            accepted.append(Finding(*match.span(), "NAME", .90, "filename_template"))

    if any(character.isdecimal() for character in source) or "@" in source:
        view, positions = comparison_view(source)
        clinical = CLINICAL.search(label) is not None
        has_unit = MEASUREMENT.fullmatch(unit.unit_of_measure) is not None
        for kind, rule in SHAPES:
            for match in rule.finditer(view):
                start, end = positions[match.start()], positions[match.end() - 1] + 1
                finding = Finding(start, end, kind, .75, "identifier_shape")
                if kind in NUMERIC and (has_unit or MEASUREMENT.match(source[end:end + 20])):
                    continue
                if kind in NUMERIC and (clinical or ADMIN.search(label)):
                    review.append(finding)
                else:
                    accepted.append(finding)

    occupied = bytearray(len(source))
    selected = []
    for result in sorted(accepted, key=lambda f: (-f.score, -(f.end-f.start), f.start, f.kind)):
        if not any(occupied[result.start:result.end]):
            occupied[result.start:result.end] = b"\1" * (result.end - result.start)
            selected.append(result)
    unresolved = (finding for finding in review if not all(occupied[finding.start:finding.end]))
    by_location = lambda f: (f.start, f.end, f.kind)
    return DetectionResult(tuple(sorted(selected, key=by_location)),
                           tuple(sorted(set(unresolved), key=by_location)))
