"""Deterministic identifier findings in original Unicode code-point coordinates."""
from dataclasses import dataclass
import re
import unicodedata

from .source_context import normalize_label

MAX_UNIT = 524288
LOCALIZED_PATIENT_LABELS = ("मरीज़ का नाम", "मरीज़ का नाम", "mareez ka naam", "ರೋಗಿಯ ಹೆಸರು", "நோயாளியின் பெயர்")

FIELD_GROUPS = {
    "NAME": "name|patient|patient name|patient full name|full name|first name|last name|surname|"
            "patientname|alternate patient name|नाम|मरीज का नाम|रोगी का नाम|मरीज़|मरीज|रोगी|"
            + "|".join(LOCALIZED_PATIENT_LABELS),
    "RELATIVE": "relative|रिश्तेदार|relative name|father name|mother name|husband name|guardian|guardian name|attendant|caregiver|पिता का नाम|माता का नाम|पति का नाम|पत्नी का नाम|pita pati ka naam",
    "PHONE": "phone|phone number|patient phone|mobile|mobile number|mobile no|contact no|contact number|telephone|tel|फोन|फ़ोन|मोबाइल",
    "EMAIL": "email|email address|e mail",
    "AADHAAR": "aadhaar|aadhaar no|aadhr no|aadhaar number|aadhar|aadhaar masked|masked aadhaar|आधार",
    "ABHA": "abha|abha no|abha number|abha address",
    "MRN": "mrn|patient id|patientid|patient identifier|patient ref|uhid|hospital uhid|ipd no|opd no|registration no|hospital id|admission id|admission no",
    "ADDRESS": "address|patient address|residence|street|house no|village|village mohalla|mohalla|landmark|pata|gaon|पता|ग्राम|गाँव|गांव|मोहल्ला|city",
    "PIN": "pin|pin code|pincode|zip|postal code",
    "DOB": "dob|date of birth|birth date|birthdate|janm tithi|janam tithi|जन्म तिथि|जन्मतिथि",
    "PAN": "pan|pan no|pan number",
    "INSURANCE_ID": "insurance id|insurance number|policy number|policy no|member id|pmjay id",
    "PATH": "source path|original path|original filename|input path|original file",
}
FHIR_NAME_TYPES = {"contact name": "NAME", "related person name": "RELATIVE"}
EXPLICIT_NAME_ROLES = {
    "patient": "patient", "patient name": "patient", "patient full name": "patient",
    "मरीज का नाम": "patient", "रोगी का नाम": "patient",
    "contact name": "contact", "related person name": "related_person",
    "relative": "relative", "relative name": "relative", "father name": "relative",
    "mother name": "relative", "husband name": "relative", "रिश्तेदार": "relative",
    "पिता का नाम": "relative", "माता का नाम": "relative", "पति का नाम": "relative", "पत्नी का नाम": "relative",
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
PATIENT_ROLE_FIELD = re.compile(
    r"(?:patient display|(?:referred|admitted|enrolled) (?:subject|person)|beneficiary"
    r"|(?:sample|referral|transfer|admission|service) recipient|(?:transfer|referral|admission) for"
    r"|ward chart|on behalf of)(?: name)?"
)
CONTACT_ROLE_FIELD = re.compile(r"(?:caller|contact person|family speaker|guardian speaker)(?: name)?")
CHART_FIELD = re.compile(
    r"(?:medical record|patient (?:chart|record)|chart) (?:no|number|id|identifier|ref|reference)"
)
CHART_ALIAS_FIELD = re.compile(
    r"(?:chart (?:anchor|key)|(?:claim|policy|insurance) member(?: (?:id|no|number))?"
    r"|accession owner|local file|(?:handover|transfer) label|settlement)"
)
CHART_VALUE = r"[^\W_]+(?:[-./][^\W_]+)*"
# Weak administrative aliases require the shape of a scoped record identifier,
# not a solitary number, a short diagnosis code, or arbitrary prose.
OPAQUE_CHART_VALUE = re.compile(r"[A-Za-z]{2,16}[-/][A-Za-z0-9]{4,32}(?:[-/][A-Za-z0-9]{1,16}){0,2}")
CHART_CUE = re.compile(
    r"(?im)(?:^[ \t]*(?:chart|medical[ \t]+record)|\breg(?:istration)?)[ \t]*(?:\#|"
    r"(?:number|no\.?|id|identifier)[ \t]*[:=#])[ \t]*(" + CHART_VALUE +
    r")(?=$|[\s,;|])"
)
LABEL_SPACES = str.maketrans({"\u00a0": " ", "\u202f": " "})
DOSE = r"\d+(?:[.,]\d+)?[ \t]*(?:mg|mcg|[µμ]g|g|ml|iu|units?)\b"
INLINE_CLINICAL = re.compile(
    r"(?:^|[ \t])(?:\([ \t]*)?(?:"
    r"(?:आयु|उम्र)[ \t]*[:：=][ \t]*\d|(?:(?:dose|dosage)(?:[ \t]*[:=][ \t]*|[ \t]+))?" + DOSE
    + r"|(?:(?:medication|rx)[ \t]*[:=][ \t]*[\w-]{1,40}|metformin|amlodipine|salbutamol)[ \t]+" + DOSE
    + r"|follow[ -]up[ \t]+in[ \t]+\d+[ \t]+(?:hours?|days?|weeks?|months?)\b)", re.I,
)
NAME_TOKEN = r"[A-Za-z\u0900-\u097f][A-Za-z\u0900-\u097f.'’\-]{0,29}"
NAME = NAME_TOKEN + r"(?:[ \t]+" + NAME_TOKEN + r"){0,2}"
# A capitalized first token and mixed-case following tokens are restricted to
# explicit narrative role cues (transliterated surnames may be lowercase).
LATIN_TOKEN = r"(?:(?:Mr|Mrs|Ms|Shri|Smt|Mohd|[A-Z])\.|[A-Z][a-zA-Z’'-]{0,29})"
HONORIFIC_SUFFIX = r"(?:[ \t]+(?i:ji|sahab|didi|behenji|babu|amma))?"
LATIN_FOLLOW = r"(?!(?i:ji|sahab|didi|behenji|babu|amma)\b)[A-Za-z][a-zA-Z’'-]{0,29}"
LATIN_NAME = LATIN_TOKEN + r"(?:[ \t]+" + LATIN_FOLLOW + r"){0,3}"
TIME_PREFIX = r"(?:\d{1,2}[:.]\d{2}[ \t]*[-–][ \t]*)?"
CALLER = re.compile(r"(?i:\b(?:called by|visitor|attendant)\b[ \t]{0,8}[:=]?[ \t]{1,8})(" +
                    NAME + r")(?=[ \t]{1,8}(?:\+?\d|\()|$|[,;\r\n])")
VISITOR = re.compile(r"(?m)^\d{1,2}:\d{2}[ \t]+-[ \t]+(" + NAME +
                     r")[ \t]+\((?i:attendant|visitor|guardian)\b")
RELATIVE = re.compile(r"\b([SDWC]/o)[ \t]+(" + NAME + r")(?=$|[\r\n;,|])", re.I)
RELATIONSHIP_LINE = re.compile(r"(?:^|[\n;,|])[ \t]*[SDW]/o[ \t]+([^\r\n;,|]{1,160})(?=$|[\r\n;,|])", re.I)
DEV_NAME_TOKEN = r"[\u0904-\u0939][\u0900-\u097f]{0,29}"
DEV_NAME = DEV_NAME_TOKEN + r"(?:[ \t]+" + DEV_NAME_TOKEN + r"){0,2}"
HONORIFIC = re.compile(r"(?m)^[ \t]{0,16}(" + LATIN_NAME + "|" + DEV_NAME +
                      r")[ \t]+(?i:ji|sahab|didi|behenji)[ \t]+(?i:aaye|aayi|ka|ki)\b")
# Line-initial named subject plus a possessive and a measured vital.
VITAL_SUBJECT = re.compile(
    r"(?m)^[ \t]*(?:(?:\d{1,4}[-/.]\d{1,2}[-/.]\d{1,4})[ \t]+)?"
    + TIME_PREFIX + r"(" + LATIN_NAME + r")"
    + HONORIFIC_SUFFIX +
    r"[ \t]+(?i:ka|ki)[ \t]+(?i:BP|blood pressure)[ \t]*[:=]?[ \t]*"
    r"\d{2,3}[ \t]*/[ \t]*\d{2,3}(?!\d)"
)
VITAL_NONPERSON = {"dr", "doctor", "nurse", "prof", "left", "right", "arm", "leg", "patient",
                   "ward", "blood", "supine", "standing", "sitting", "upper", "lower"}
NARRATIVE_PATIENT = (
    # A report's subject is distinct from a clinician mentioned elsewhere.
    re.compile(r"(?m)^[ \t]*(?i:report of)[ \t]+(" + LATIN_NAME + r")" + HONORIFIC_SUFFIX +
               r"[ \t]+\d{1,3}[ \t]*(?i:y|yrs?|years?)[ \t]*/[ \t]*(?i:[mfx])\b"),
    # Restrict the possessive cue to a named person's attendant.
    re.compile(r"(?i:\b(?:sample received from|received from))[ \t]+(" +
               LATIN_NAME + r")[’']s[ \t]+(?i:attendant|guardian)\b"),
    # Preserve diagnosis and the relationship clause, not just the name.
    re.compile(r"(?m)^[ \t]*" + TIME_PREFIX + r"(" + LATIN_NAME +
               r")[ \t]*[-–][ \t]*(?i:k/c/o)\b"),
    re.compile(r"(?m)^[ \t]*(" + LATIN_NAME +
               r"),[ \t]*(?i:[sdw]/o)[ \t]+[^\n\r,;]{1,160},[ \t]*(?i:discharged|admitted)\b"),
    re.compile(r"(?:(?<=\.)[ \t]+|(?m:^[ \t]*))(" + LATIN_NAME + r")" + HONORIFIC_SUFFIX +
               r"[ \t]+(?i:ki|ka)[ \t]+(?i:condition)[ \t]+(?i:ab|is|was)\b"),
    re.compile(r"(?i:\b(?:opd|patient|clinical)[ \t]+note for)[ \t]+(" +
               LATIN_NAME + r")(?=[.;,\r\n])"),
)
HINDI_SYMPTOM_SUBJECT = re.compile(
    r"(?m)^[ \t]*([\u0904-\u0939][\u0900-\u097f]{0,29}(?:[ \t]+"
    r"[\u0904-\u0939][\u0900-\u097f]{0,29}){1,3})[ \t]+को[ \t]+"
    r"\d{1,3}[ \t]+(?:दिन|सप्ताह|घंटे|महीने)[ \t]+से(?=$|[ \t])"
)
PAREN_RELATIVE = re.compile(r"\([ \t]*(?i:[sdw]/o)[ \t]+(" + NAME + r")[ \t]*\)")
CHAT_SPEAKER = re.compile(
    r"(?m)^[ \t]*\[\d{1,4}[-/.]\d{1,2}[-/.]\d{1,4},[ \t]*"
    r"\d{1,2}:\d{2}(?::\d{2})?(?:[ \t]*(?i:am|pm))?\][ \t]+("
    + LATIN_NAME + r"):[ \t]*(?=\S)"
)
LOCAL_MRN_CUE = re.compile(
    r"(?i)(?:पंजीकरण|रजिस्ट्रेशन|आईपीडी|ओपीडी)[ \t]+(?:सं\.?|नंबर|क्रमांक)[ \t]*[:：=][ \t]*("
    + CHART_VALUE + r")(?=$|[\s,;|])"
)
BED_CHART_CUE = re.compile(
    r"(?im)^[^\n\r]{0,120}\bbed[ \t]+\d{1,3}[ \t]*[-–][ \t]*(IP[-/]\d{2}[-/]\d{3,12})(?=$|[\s,;|])"
)
ADDRESS_LINE = re.compile(
    r"(?im)(?:^|[\n;|])[ \t]{0,32}(?:address|पता|pata)[ \t]*[:：=][ \t]*([^\r\n;|]{1,350})"
)
DISTRICT_CUE = re.compile(r"(?i)^(?:district|distt?\.?|tehsil|tahsil|तहसील|जिला|ज़िला|jila)\s")
ADDRESS_GEO_CUE = re.compile(r"(?i)(?:\b(?:district|distt?\.?|tehsil|tahsil|ward|mohalla|village|vill\.?|gram)\b|तहसील|जिला|ग्राम|मोहल्ला)")
ADDRESS_PIN = re.compile(r"(?<!\d)\d{6}(?!\d)[ \t]*$")
CARE_ADDRESS_TAIL = re.compile(
    r"(?im)^[ \t]*address[ \t]*\(attendant\)[ \t]*:[ \t]*c/o[ \t]+[^,;\r\n]{1,160},[ \t]*([^,;\r\n]{1,160})"
)
FAMILY_INTRODUCTION = re.compile(
    r"(?im)^[ \t]*(?:family|relative|guardian|caregiver)[ \t]*:[ \t]*I[ \t]+am[ \t]+"
    r"([^\r\n]{1,140}?)\.[ \t]*I[ \t]+(?:came[ \t]+with|accompanied|brought)[ \t]+"
    r"([^\r\n]{1,140}?)\.?[ \t]*(?=\r?$)"
)
SUBJECT_CUE = re.compile(r"(?im)^[ \t]*subject[ \t]*[:=][ \t]*([^\r\n]{1,140})")
PATIENT_REVIEW_CONTEXT = re.compile(
    r"(?im)^[ \t]*(?:prescription|medication|clinical|patient)[ \t]+(?:review|encounter|intake|record|note)[ \t]*(?=\r?$)"
)
CONTACT_CONTEXT = re.compile(r"(?im)^[ \t]*(?:reply[ -]to|patient[ \t]+contact|return[ \t]+contact)[ \t]*[:=]?[ \t]+\S")
INLINE_JSON_PATIENT = re.compile(
    r'(?i)"(?:patient|patient_name|patient name)"\s*:\s*"([^"\r\n]{1,160})"'
)
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
    ("MRN", re.compile(r"(?<![a-z0-9])(?:UHID|MRN|IPD|OPD|SNJ|JJH|ADM|DHH)[- /]?"
                       r"(?:[0-9]{2}[-/][0-9]{3,12}|[0-9]{3,12}(?:[-/][0-9]{3,12})?)(?![a-z0-9])", re.I)),
    ("ABHA", re.compile(r"(?<![a-z0-9])[0-9]{2}[ -]?[0-9]{4}[ -]?[0-9]{4}[ -]?[0-9]{4}(?![a-z0-9])", re.I)),
    ("AADHAAR", re.compile(r"(?<![a-z0-9])(?:[0-9]{4}[ -]?[0-9]{4}|[xX*]{4}[ -]?[xX*]{4})[ -]?[0-9]{4}(?![a-z0-9])", re.I)),
    ("PHONE", re.compile(r"(?<![^\W_])(?:\+91[ -]?)?[6-9][0-9][x*]{6}[0-9]{2}(?![^\W_])", re.I)),
    ("PHONE", re.compile(r"(?<![a-z0-9])(?:\+91[ -]?|0)?[6-9][0-9]{4}[ -]?[0-9]{5}(?![a-z0-9])", re.I)),
)
NUMERIC = {"PHONE", "AADHAAR", "ABHA"}
MRN_NAME_HEADER = re.compile(
    r"(?i:(?:UHID|MRN|IPD|OPD|SNJ|JJH|ADM|DHH)[- /]?\d{3,12}(?:[-/]\d{3,12})?)"
    r"[ \t]+([A-Z][a-z’'-]{1,29})"
)
OPAQUE_KEY = re.compile(r"[A-Za-z]{3,40}[0-9]{6,16}")
FILE_NAME = re.compile(r"(?i)^(?:discharge_summary|patient|prescription|report)[_-](?:[a-z]{2,30}[_ -])+[a-z]{2,30}(?=[_-](?:[A-Z]{2,8}[-_]?)?[0-9])")
FILENAME_IP = re.compile(r"(?i)(?<![A-Za-z0-9])IP-[0-9]{2}-[0-9]{5}(?![A-Za-z0-9])")


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


NONPERSON_NAME_WORDS = VITAL_NONPERSON | {
    "sample", "specimen", "laboratory", "lab", "chart", "dose", "dosage", "medicine",
    "medication", "prescription", "review", "diagnosis", "pressure", "pulse", "blood",
    "glucose", "temperature", "vital", "vitals", "signs", "status", "result", "test",
    "function", "normal", "clinical", "assessment", "record", "count", "monitoring",
    "report", "followup", "follow-up",
}


def contextual_name(value):
    """Require name shape as well as a role; do not claim lexical identity."""
    words = {word.strip(".,").casefold() for word in value.split()}
    return person_name(value.translate(LABEL_SPACES)) and not words.intersection(NONPERSON_NAME_WORDS)


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
        if label == "naam" and person_name(value):
            return DetectionResult((Finding(start, start + len(value), "NAME", .94, "name_field"),))
        if PATIENT_ROLE_FIELD.fullmatch(label) and contextual_name(value):
            return DetectionResult((Finding(start, start + len(value), "NAME", .94,
                                            "patient_field_context", "patient"),))
        if CONTACT_ROLE_FIELD.fullmatch(label) and contextual_name(value):
            return DetectionResult((Finding(start, start + len(value), "NAME", .92,
                                            "contact_field_context", "contact"),))
        if CHART_FIELD.fullmatch(label) and chart_number(value) and re.fullmatch(CHART_VALUE, value):
            return DetectionResult((Finding(start, start + len(value), "MRN", .94, "chart_context"),))
        if CHART_ALIAS_FIELD.fullmatch(label) and chart_number(value) and OPAQUE_CHART_VALUE.fullmatch(value):
            return DetectionResult((Finding(start, start + len(value), "MRN", .92, "chart_alias_context"),))
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
            if kind == "NAME" and VITAL_NONPERSON.intersection(match[1].casefold().replace(".", "").split()):
                continue
            accepted.append(Finding(*match.span(1), kind, .90, "local_role"))
    for pattern in (VITAL_SUBJECT, *NARRATIVE_PATIENT):
        for match in pattern.finditer(label_view):
            if not VITAL_NONPERSON.intersection(match[1].casefold().replace(".", "").split()):
                accepted.append(Finding(*match.span(1), "NAME", .88, "narrative_subject", "patient"))
    # A repeated Devanagari subject needs corroboration: the same document has
    # already identified that surface via an explicit name field.
    known_names = {" ".join(label_view[f.start:f.end].casefold().split()) for f in accepted
                   if f.kind == "NAME" and f.reason in {"typed_field", "local_label"}}
    for match in HINDI_SYMPTOM_SUBJECT.finditer(label_view):
        if " ".join(match[1].casefold().split()) in known_names:
            accepted.append(Finding(*match.span(1), "NAME", .91, "corroborated_subject", "patient"))
    for match in PAREN_RELATIVE.finditer(label_view):
        accepted.append(Finding(*match.span(1), "RELATIVE", .92, "relationship", "relative"))
    for match in FAMILY_INTRODUCTION.finditer(label_view):
        for index, kind, role in ((1, "RELATIVE", "relative"), (2, "NAME", "patient")):
            value = match[index].rstrip()
            if contextual_name(value):
                accepted.append(Finding(match.start(index), match.start(index) + len(value),
                                        kind, .92, "family_introduction", role))
    # Subject is ambiguous by itself (clinical topic, specimen, etc.). Require
    # both patient-document context and a return-contact cue.
    if PATIENT_REVIEW_CONTEXT.search(label_view) and CONTACT_CONTEXT.search(label_view):
        for match in SUBJECT_CUE.finditer(label_view):
            value = identifier_prefix(match[1], "NAME")
            if contextual_name(value):
                accepted.append(Finding(match.start(1), match.start(1) + len(value),
                                        "NAME", .91, "subject_context", "patient"))
    for match in INLINE_JSON_PATIENT.finditer(label_view):
        if person_name(match[1]):
            accepted.append(Finding(*match.span(1), "NAME", .90, "embedded_patient_field", "patient"))
    for match in CHAT_SPEAKER.finditer(label_view):
        # A timestamped chat sender can be a clinician; only handle the
        # personal sender of a forwarded patient report in this bounded form.
        if re.match(r"<attachment:[^\r\n>]{1,120}>[ \t]*\r?\n[ \t]*(?i:forwarded)\b",
                    label_view[match.end():match.end() + 180]) and not (
                        VITAL_NONPERSON.intersection(match[1].casefold().split())):
            accepted.append(Finding(*match.span(1), "RELATIVE", .88, "chat_sender", "contact"))
    for pattern in (LOCAL_MRN_CUE, BED_CHART_CUE):
        for match in pattern.finditer(label_view):
            if chart_number(match[1]):
                accepted.append(Finding(*match.span(1), "MRN", .96, "local_chart_context"))
    for match in CARE_ADDRESS_TAIL.finditer(label_view):
        value = match[1].rstrip()
        if value and not INLINE_CLINICAL.search(value):
            accepted.append(Finding(match.start(1), match.start(1) + len(value), "ADDRESS",
                                    .94, "address_component"))
    for match in ADDRESS_LINE.finditer(label_view):
        address = match[1]
        # A structured multi-component residential address is different from
        # unrelated inline clinical clauses. Retain coarse geography and remove
        # the fine-grained components, including a terminal postal identifier.
        if not ADDRESS_GEO_CUE.search(address):
            continue
        coarse_geography_seen = False
        for part in re.finditer(r"[^,]+", address):
            value = part[0].strip()
            start = match.start(1) + part.start() + len(part[0]) - len(part[0].lstrip())
            if not value:
                continue
            if DISTRICT_CUE.match(value):
                coarse_geography_seen = True
                if pin := ADDRESS_PIN.search(value):
                    accepted.append(Finding(start + pin.start(), start + pin.end(), "PIN", .96,
                                            "address_postal_context"))
            elif not coarse_geography_seen and part.start() and not re.match(r"(?i)(?:dose|medication|rx|BP|pulse|temperature|"
                                               r"diagnosis|consultant|mobile|phone)\b", value):
                accepted.append(Finding(start, start + len(value), "ADDRESS", .94, "address_component"))
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
    if unit.channel == "header":
        if match := MRN_NAME_HEADER.fullmatch(label_view):
            word = match[1].casefold()
            if word not in VITAL_NONPERSON | {"bp", "pulse", "temp", "temperature", "dose",
                                             "result", "glucose", "reading", "sugar", "weight",
                                             "status", "date", "time", "height", "rate"}:
                accepted.append(Finding(*match.span(1), "NAME", .90, "patient_header", "patient"))
    if unit.channel == "filename":
        match = FILE_NAME.match(source)
        if match:
            accepted.append(Finding(*match.span(), "NAME", .90, "filename_template"))
        for match in FILENAME_IP.finditer(source):
            accepted.append(Finding(*match.span(), "MRN", .90, "filename_ip_id"))

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
