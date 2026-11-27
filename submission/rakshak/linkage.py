"""Conservative identity linkage from typed table, JSON and text records.

Collect evidence before redaction, retain it only after a record is exportable,
then resolve the batch. The caller must replace the selected already-redacted
identifier with the returned pseudonym and record the same token in records.jsonl.
Raw identifiers, names, DOBs, ages, relative and locality values are never
retained in evidence. Keys and evidence must not be logged.
"""
from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from urllib.parse import urlsplit
import hmac
import itertools
import re
import unicodedata

from .source_context import normalize_label


LABEL_GROUPS = {
    "aadhaar": {"aadhaar", "aadhaar no", "aadhaar number", "aadhr no", "aadhar", "aadhar no", "aadhar number", "आधार", "आधार संख्या"},
    "abha": {"abha", "abha no", "abha number", "आभा नंबर", "आभा संख्या"},
    "mrn": {"mrn", "mrn no", "mrn number", "uhid", "hospital uhid", "patient id", "patientid", "patient identifier",
            "patient ref", "registration no", "registration number", "reg no", "medical record", "medical record no",
            "medical record number", "medical record id", "patient chart no", "patient chart id", "chart id", "chart no"},
    "phone": {"phone", "phone number", "patient phone", "patient mobile", "mobile", "mobile no", "mobile number",
              "contact number", "contact no", "telephone", "tel", "फोन", "फ़ोन", "मोबाइल"},
    "email": {"email", "email address", "e mail", "patient email"},
    "name": {"name", "patient", "patient name", "patient full name", "full name", "patientname", "naam", "नाम",
             "मरीज का नाम", "रोगी का नाम", "मरीज़ का नाम", "mareez ka naam", "beneficiary name", "patient display"},
    "first": {"first name", "firstname", "given name", "patient given name", "patient first name"},
    "last": {"last name", "lastname", "surname", "family name", "patient surname", "patient last name"},
    "dob": {"dob", "date of birth", "birth date", "birthdate", "janm tithi", "janam tithi", "जन्म तिथि", "जन्मतिथि"},
    "relative": {"relative", "relative name", "father name", "mother name", "husband name", "guardian", "guardian name",
                 "pita pati ka naam", "pita ka naam", "पति का नाम", "पिता का नाम", "रिश्तेदार"},
    "age": {"age", "patient age", "age years", "umar", "आयु", "उम्र"},
    "gender": {"gender", "sex", "patient gender", "patient sex", "ling", "लिंग"},
    "age_gender": {"age sex", "age gender", "age and sex", "age and gender"},
    "village": {"village", "village mohalla", "gaon", "गांव", "गाँव", "ग्राम"},
    "issuer": {"hospital", "hospital name", "hospital code", "facility", "facility name", "facility code", "issuer", "issuing authority",
               "assigning authority", "mrn issuer", "uhid issuer", "patient id issuer"},
}
LABELS = {label: kind for kind, labels in LABEL_GROUPS.items() for label in labels}
ID_KINDS = {"aadhaar", "abha", "mrn", "phone", "email"}
GLOBAL = {"aadhaar", "abha"}
WEAK = {"phone", "email"}
GENERIC_PREFIXES = {"mrn", "uhid", "patient", "pat", "reg", "id", "pt", "hospital", "ipd", "opd", "ip", "op",
                    "chart", "record", "registry", "patientid", "patientref", "ref", "case", "caseid", "pid",
                    "hospitalid", "regno", "serial", "legacy", "unknown", "new", "old"}
MRN = re.compile(r"([a-z]{2,16})(?:[-/. ]?)[0-9]{2,14}(?:[-/. ][0-9]{1,14}){0,3}\Z")
EMAIL_LOCAL = re.compile(r"[A-Za-z0-9!#$%&'*+/=?^_`{|}~.-]{1,64}\Z")
DNS_LABEL = re.compile(r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?\Z")
AGE = re.compile(r"([0-9]{1,3})(?:[ ]*(?:y|years?|yrs?\.?|वर्ष|साल))?\Z", re.I)
AGE_SEX = re.compile(r"([0-9]{1,3})(?:[ ]*(?:y|years?|yrs?\.?|वर्ष|साल))?[ ]*/[ ]*([^/]{1,20})\Z", re.I)
GENDER = {"m": "m", "male": "m", "पुरुष": "m", "f": "f", "female": "f", "महिला": "f", "स्त्री": "f"}
NULLS = {"", "-", "n/a", "na", "none", "unknown", "null", "not available", "not known", "redacted", "withheld"}
MAX_GROUP = 256
DOMAIN = b"rakshak/table-linkage/evidence/v1\0"
PSEUDONYM_DOMAIN = b"rakshak/table-linkage/pseudonym/v1\0"


def _secret(secret):
    if isinstance(secret, str):
        secret = secret.encode("utf-8")
    if not isinstance(secret, bytes) or not secret:
        raise ValueError("missing_linkage_secret")
    return secret


def _token(secret, kind, value):
    return hmac.digest(secret, DOMAIN + kind.encode("ascii") + b"\0" + value.encode("utf-8"), "sha256")


def _normalized(value):
    if not isinstance(value, str) or len(value) > 256:
        return ""
    value = unicodedata.normalize("NFKC", value).strip()
    return "".join(str(unicodedata.decimal(c, c)) for c in value)


def _words(value):
    return " ".join(_normalized(value).casefold().split())


def _name(value, *, split=False):
    value = _words(value)
    if value in NULLS:
        return None
    words = value.split()
    if not (1 if split else 2) <= len(words) <= 6:
        return None
    if words[0] in {"dr", "doctor", "mr", "mrs", "ms", "patient", "unknown", "not"}:
        return None
    if any(sum(c.isalpha() for c in word) < 2 or any(not (c.isalpha() or unicodedata.category(c)[0] == "M" or c in "-'’") for c in word)
           for word in words):
        return None
    if len(words) > 1 and len(set(words)) == 1:
        return None
    return value


def _location(value):
    value = _words(value)
    if value in NULLS or len(value) < 3 or not any(c.isalpha() for c in value):
        return None
    if not all(c.isalnum() or unicodedata.category(c)[0] == "M" or c in " -.'’" for c in value):
        return None
    return value


def _exact_digits(value, width):
    value = _normalized(value)
    if not re.fullmatch(r"[0-9][0-9 -]*[0-9]", value):
        return None
    digits = re.sub(r"[ -]", "", value)
    return digits if len(digits) == width and len(set(digits)) >= 2 else None


def _phone(value):
    value = _normalized(value)
    if not re.fullmatch(r"\+?[0-9() -]+", value):
        return None
    plus = value.startswith("+")
    digits = re.sub(r"[^0-9]", "", value)
    if plus:
        if len(digits) != 12 or not digits.startswith("91"):
            return None
        digits = digits[2:]
    elif len(digits) == 14 and digits.startswith("0091"):
        digits = digits[4:]
    elif len(digits) == 12 and digits.startswith("91"):
        digits = digits[2:]
    elif len(digits) == 11 and digits.startswith("0"):
        digits = digits[1:]
    if len(digits) == 10 and digits[0] in "6789" and len(set(digits)) > 1:
        return "+91" + digits
    return None


def _email(value):
    if not isinstance(value, str):
        return None
    value = value.strip()
    if len(value) > 254 or value.count("@") != 1:
        return None
    local, domain = value.split("@")
    labels = domain.split(".")
    if not EMAIL_LOCAL.fullmatch(local) or local.startswith(".") or local.endswith(".") or ".." in local:
        return None
    return local + "@" + domain.casefold() if len(labels) > 1 and all(DNS_LABEL.fullmatch(label) for label in labels) else None


def _dob(value, label):
    value = _normalized(value)
    match = re.fullmatch(r"([0-9]{4})([-/.])([0-9]{1,2})\2([0-9]{1,2})", value)
    if match:
        y, m, d = map(int, (match[1], match[3], match[4]))
    else:
        match = re.fullmatch(r"([0-9]{1,2})([-/.])([0-9]{1,2})\2([0-9]{4})", value)
        if not match:
            return None
        x, z, y = map(int, (match[1], match[3], match[4]))
        hint = label.casefold()
        if re.search(r"mm\s*[/.-]\s*dd", hint):
            m, d = x, z
        elif re.search(r"dd\s*[/.-]\s*mm", hint):
            d, m = x, z
        elif z > 12:
            m, d = x, z
        elif x > 12:
            d, m = x, z
        else:
            return None  # no ungrounded day/month interpretation
    try:
        return date(y, m, d).isoformat()
    except ValueError:
        return None


def _age(value):
    match = AGE.fullmatch(_words(value))
    return str(int(match[1])) if match is not None and 0 <= int(match[1]) <= 125 else None


def _age_gender(value):
    match = AGE_SEX.fullmatch(_words(value))
    if not match:
        return None, None
    return _age(match[1]), GENDER.get(match[2])


@dataclass(frozen=True, repr=False)
class Anchor:
    kind: str
    token: bytes
    scope: bytes | None = None
    generic: bool = False


@dataclass(frozen=True, repr=False)
class RowEvidence:
    """Opaque keyed evidence, plus zero-based identifier-cell column."""
    column: int
    anchors: tuple[Anchor, ...]
    name: bytes | None
    dob: bytes | None
    age: bytes | None
    gender: bytes | None
    relative: bytes | None
    village: bytes | None

    def __repr__(self):
        return "<RowEvidence>"


def row_evidence(header, row, secret):
    """Return RowEvidence for a typed identifier-bearing row, or None.

    Only recognized identity labels are consulted; never parse identifiers from
    notes, medical values or arbitrary numbers. For MRN accept only exact
    letter+digit identifiers: slash, dot, hyphen and space variants remain
    distinct; an explicitly supplied issuer scopes the token. A valid global
    ID or contact may provide independent evidence, and matching names/clues
    are keyed separately. Conflicting same-kind fields abstain rather than
    choose a convenient value. Prefer the existing MRN cell for pseudonym
    insertion, then Aadhaar, ABHA, mobile or email. The caller verifies that
    this cell was actually redacted by its detector before retaining evidence.
    """
    key = _secret(secret)
    if len(header) != len(row):
        return None
    clue_values = defaultdict(set)
    ids = defaultdict(list)
    mrns = []
    for column, (label, value) in enumerate(zip(header, row)):
        kind = LABELS.get(normalize_label(label))
        if kind == "mrn":
            canonical = _words(value)
            if MRN.fullmatch(canonical) and len(canonical) <= 64:
                mrns.append((column, canonical))
        elif kind in ID_KINDS:
            normalized = (_exact_digits(value, 12) if kind == "aadhaar" else
                          _exact_digits(value, 14) if kind == "abha" else
                          _phone(value) if kind == "phone" else _email(value))
            if normalized is not None:
                ids[kind].append((column, normalized))
        elif kind == "age_gender":
            age, gender = _age_gender(value)
            if age is not None:
                clue_values["age"].add(age)
            if gender is not None:
                clue_values["gender"].add(gender)
        elif kind:
            normalized = (_name(value, split=kind in {"first", "last"}) if kind in {"first", "last", "name", "relative"} else
                          _dob(value, label) if kind == "dob" else
                          _age(value) if kind == "age" else
                          GENDER.get(_words(value)) if kind == "gender" else _location(value))
            if normalized is not None:
                clue_values[kind].add(normalized)
    if any(len(values) > 1 for values in clue_values.values()):
        return None
    if clue_values["first"] and clue_values["last"]:
        combined = next(iter(clue_values["first"])) + " " + next(iter(clue_values["last"]))
        clue_values["name"].add(combined)
    if len(clue_values["name"]) > 1 or len({value for _, value in mrns}) > 1:
        return None
    if any(len({value for _, value in values}) > 1 for values in ids.values()):
        return None
    anchors = []
    order = ("mrn", "aadhaar", "abha", "phone", "email")
    columns = {}
    if mrns:
        column, value = min(mrns)
        prefix = MRN.fullmatch(value)[1]
        explicit_issuer = next(iter(clue_values["issuer"]), None)
        generic = not explicit_issuer and prefix in GENERIC_PREFIXES
        scope = _token(key, "mrn-issuer", explicit_issuer or prefix) if not generic else None
        # Use distinct domains for explicitly scoped and prefix-inferred MRNs.
        canonical = ("issuer:" + explicit_issuer + "\0" if explicit_issuer else "prefix:\0") + value
        anchors.append(Anchor("mrn", _token(key, "mrn", canonical), scope, generic))
        columns["mrn"] = column
    for kind, values in ids.items():
        if values:
            column, value = min(values)
            anchors.append(Anchor(kind, _token(key, kind, value)))
            columns[kind] = column
    if not anchors:
        return None
    column = next(columns[kind] for kind in order if kind in columns)
    clues = [_token(key, kind, next(iter(clue_values[kind]))) if clue_values[kind] else None
             for kind in ("name", "dob", "age", "gender", "relative", "village")]
    return RowEvidence(column, tuple(sorted(anchors, key=lambda a: a.kind)), *clues)


def _shared(a, b, field):
    value = getattr(a, field)
    return value is not None and value == getattr(b, field)


def _conflict(a, b):
    for field in ("name", "dob", "age", "gender", "relative", "village"):
        x, y = getattr(a, field), getattr(b, field)
        if x is not None and y is not None and x != y:
            return True
    left, right = {anchor.kind: anchor for anchor in a.anchors}, {anchor.kind: anchor for anchor in b.anchors}
    for kind in GLOBAL:
        if kind in left and kind in right and left[kind].token != right[kind].token:
            return True
    if "mrn" in left and "mrn" in right:
        x, y = left["mrn"], right["mrn"]
        # Different institutions' MRNs are expected. Conflicting IDs within
        # a known issuer/prefix are unsafe to cluster automatically.
        if x.scope is not None and x.scope == y.scope and x.token != y.token:
            return True
    return False


def _eligible(a, b, allowed):
    if _conflict(a, b):
        return False
    common = set(a.anchors).intersection(b.anchors, allowed)
    kinds = {anchor.kind for anchor in common}
    name = _shared(a, b, "name")
    globals_count = len(kinds & GLOBAL)
    if globals_count and (name or globals_count >= 2):
        return True
    if not name:
        return False
    corroborated = _shared(a, b, "dob") or _shared(a, b, "relative") or (_shared(a, b, "age") and _shared(a, b, "gender"))
    if "mrn" in kinds and (corroborated or any(anchor.kind == "mrn" and not anchor.generic for anchor in common)):
        return True
    contact_corroborated = (_shared(a, b, "dob") or _shared(a, b, "relative") or
                            (_shared(a, b, "village") and _shared(a, b, "age") and _shared(a, b, "gender")))
    return bool(kinds & WEAK and contact_corroborated)


def _fingerprint(record):
    anchor_parts = [a.kind.encode("ascii") + b":" + a.token.hex().encode("ascii") for a in record.anchors]
    clues = [field.encode("ascii") + b":" + (value.hex().encode("ascii") if value else b"")
             for field in ("name", "dob", "age", "gender", "relative", "village") for value in (getattr(record, field),)]
    return b"|".join(anchor_parts + clues)


def resolve_linkage(records, secret):
    """Map only positively linked stable record keys to same-release PSN IDs.

    Strong global identifiers need a matching full name or a second global
    identifier. Non-generic issuer-prefixed MRNs need matching names; generic
    MRNs additionally need exact corroboration (DOB, relative, or age+gender).
    Contact anchors need a matching name plus an independent corroborator.
    A repeated anchor with conflicting evidence or too many records is ignored.
    A component that is not a clique is rejected in full, preventing a chain
    of otherwise plausible pair links from merging incompatible identities.
    Pseudonyms are order-independent and use a separate HMAC domain. They are
    stable for the same evidence batch with the same secret, and rotate across
    secret changes. Nothing is emitted for singleton or ambiguous records.
    """
    key = _secret(secret)
    evidence = list(records.values())
    keys = list(records.keys())
    buckets = defaultdict(list)
    for i, record in enumerate(evidence):
        for anchor in record.anchors:
            buckets[anchor].append(i)
    allowed = {anchor for anchor, indices in buckets.items()
               if 2 <= len(indices) <= MAX_GROUP and all(not _conflict(evidence[i], evidence[j]) for i, j in itertools.combinations(indices, 2))}
    edges = [set() for _ in evidence]
    for anchor in allowed:
        for i, j in itertools.combinations(buckets[anchor], 2):
            if j not in edges[i] and _eligible(evidence[i], evidence[j], allowed):
                edges[i].add(j)
                edges[j].add(i)
    output = {}
    visited = set()
    for i, neighbours in enumerate(edges):
        if i in visited or not neighbours:
            continue
        group, stack = {i}, [i]
        while stack:
            new = edges[stack.pop()] - group
            group.update(new)
            stack.extend(new)
        visited.update(group)
        if any(len(edges[j]) != len(group) - 1 for j in group):
            continue
        payload = PSEUDONYM_DOMAIN + b"\0".join(sorted({_fingerprint(evidence[j]) for j in group}))
        pseudonym = "PSN-" + hmac.digest(key, payload, "sha256").hex()[:24].upper()
        for j in sorted(group):
            output[keys[j]] = pseudonym
    return output


# A record locator is output metadata; never derive it from arbitrary object
# keys that might contain identifiers. Only known record-collection names and
# canonical zero-based indices are accepted here, matching the safe interface.
_JSON_COLLECTIONS = {'patients', 'visits', 'encounters', 'registrations', 'results', 'records',
                     'patient records', 'clinical records', 'consultations', 'appointments'}
_JSON_PATIENT_OBJECTS = {'patient', 'beneficiary'}
_JSON_ID_OBJECTS = {'ids', 'identifiers', 'patient identifiers'}
_JSON_CONTACT_OBJECTS = {'contact', 'patient contact'}
_JSON_RELATIVE_OBJECTS = {'guardian', 'relative', 'related person'}
_JSON_ADDRESS_OBJECTS = {'address', 'patient address'}
_TEXT_LINE = re.compile(r"^[ \t]*([^\r\n:=#：]{1,64}?)[ \t]*[:：=#][ \t]*(.*?)[ \t]*$")
_TEXT_CONTACT_LABELS = {'patient phone', 'patient mobile', 'patient email', 'mobile', 'mobile no', 'mobile number',
                        'phone', 'phone number', 'फोन', 'फ़ोन', 'मोबाइल'}


def _json_record(document, locator):
    if isinstance(document, dict) and document.get('resourceType') == 'Bundle':
        return None  # Handled by the separately validated FHIR adapter.
    if locator == 'doc':
        return (document, ()) if isinstance(document, dict) else None
    if not isinstance(locator, str) or not locator.startswith('/'):
        return None
    parts = locator[1:].split('/')
    if len(parts) == 1 and isinstance(document, list):
        records, path, index = document, (), parts[0]
    elif len(parts) == 2 and isinstance(document, dict):
        key = parts[0].replace('~1', '/').replace('~0', '~')
        if normalize_label(key) not in _JSON_COLLECTIONS:
            return None
        records, path, index = document.get(key), (key,), parts[1]
    else:
        return None
    if not isinstance(records, list) or not re.fullmatch(r'0|[1-9][0-9]{0,8}', index):
        return None
    i = int(index)
    if i >= len(records) or not isinstance(records[i], dict):
        return None
    return records[i], (*path, i)


def json_evidence(document, locator, secret):
    """Extract keyed evidence and an exact string replacement path from JSON.

    Supports one FHIR Patient with an explicitly HL7-typed MR identifier, and
    explicit fields of non-FHIR object records, known arrays, and
    a single explicit patient object (with typed ID/contact/address/guardian
    subobjects). Unknown containers, clinicians, notes, metadata, mixed
    arrays and arbitrary keys are never searched. Only string identifiers can
    be chosen for replacement; a numeric age can corroborate without changing
    its original representation. The consumer MUST check the returned path
    exists in the sanitized document and contains exactly a typed placeholder.
    """
    if isinstance(document, dict) and document.get('resourceType') == 'Bundle':
        return _fhir_patient_evidence(document, secret) if locator == 'doc' else None
    selected = _json_record(document, locator)
    if selected is None:
        return None
    record, base = selected
    labels, values, paths = [], [], []

    def add(label, value, path):
        kind = LABELS.get(normalize_label(label))
        if kind is None:
            return
        # Numeric identity fields cannot carry a string pseudonym safely.
        # Use a numeric age solely as a keyed clue; preserve the number on disk.
        if kind == 'age' and type(value) is int:
            value = str(value)
        if not isinstance(value, str):
            return
        labels.append(label)
        values.append(value)
        paths.append(path)

    def add_direct(obj, path, kinds=None):
        for key, value in obj.items():
            kind = LABELS.get(normalize_label(key))
            if kind is not None and (kinds is None or kind in kinds):
                add(key, value, (*path, key))

    def patient_fields(obj, path):
        add_direct(obj, path)
        for key, value in obj.items():
            if not isinstance(value, dict):
                continue
            label = normalize_label(key)
            subpath = (*path, key)
            if label in _JSON_ID_OBJECTS:
                add_direct(value, subpath, ID_KINDS)
            elif label in _JSON_CONTACT_OBJECTS:
                add_direct(value, subpath, WEAK)
            elif label in _JSON_ADDRESS_OBJECTS:
                add_direct(value, subpath, {'village'})
            elif label in _JSON_RELATIVE_OBJECTS:
                for child, item in value.items():
                    if LABELS.get(normalize_label(child)) in {'name', 'relative'}:
                        add('relative name', item, (*subpath, child))

    patient_fields(record, base)
    patient_objects = [(key, value) for key, value in record.items()
                       if normalize_label(key) in _JSON_PATIENT_OBJECTS and isinstance(value, dict)]
    if len(patient_objects) > 1:
        return None
    if patient_objects:
        key, obj = patient_objects[0]
        patient_fields(obj, (*base, key))
    evidence = row_evidence(labels, values, secret)
    return (evidence, paths[evidence.column]) if evidence is not None else None


def text_evidence(text, secret):
    """Extract identity only from separate, explicit label/value lines.

    Return (RowEvidence, zero-based line index, expected redaction kind), or
    None. The whole-field value must satisfy the typed parser. No unlabelled
    prose, free-text names, encounter IDs, or identifiers next to a clinical
    number are parsed. Multiple conflicting same-kind fields already abstain
    via row_evidence; additionally require the selected anchor line to be the
    only line of its label kind to avoid ambiguous insertion.
    """
    labels, values, line_numbers = [], [], []
    for index, line in enumerate(text.splitlines()):
        match = _TEXT_LINE.fullmatch(line)
        if not match:
            continue
        label = match[1].strip()
        normalized = normalize_label(label)
        kind = LABELS.get(normalized)
        if kind is None or (kind in WEAK and normalized not in _TEXT_CONTACT_LABELS):
            continue
        if not match[2] or len(match[2]) > 256:
            continue
        labels.append(label)
        values.append(match[2])
        line_numbers.append(index)
    evidence = row_evidence(labels, values, secret)
    if evidence is None:
        return None
    kind = LABELS[normalize_label(labels[evidence.column])]
    if sum(LABELS.get(normalize_label(label)) == kind for label in labels) != 1:
        return None
    return evidence, line_numbers[evidence.column], kind.upper()


def text_target(cleaned_text, line_index, kind):
    """Safely locate a sanitized exact typed placeholder on the original line.

    Returns a code-point (start, end) span only if the typed line still has the
    expected label role and exact placeholder as its whole value. No raw input
    or source identifier is used. The caller must replace this validated span.
    """
    if type(line_index) is not int or line_index < 0 or kind.casefold() not in ID_KINDS:
        return None
    position = 0
    for index, line in enumerate(cleaned_text.splitlines(keepends=True)):
        if index == line_index:
            match = _TEXT_LINE.fullmatch(line.rstrip('\r\n'))
            expected = '[' + kind.upper() + ']'
            if (match and LABELS.get(normalize_label(match[1].strip())) == kind.casefold()
                    and match[2] == expected):
                return position + match.start(2), position + match.end(2)
            return None
        position += len(line)
    return None


def _fhir_patient_evidence(bundle, secret):
    """Only a unique Patient's HL7 MR identifier value; no resource IDs/refs."""
    entries = bundle.get('entry')
    if not isinstance(entries, list):
        return None
    patients = [(i, e['resource']) for i, e in enumerate(entries)
                if isinstance(e, dict) and isinstance(e.get('resource'), dict)
                and e['resource'].get('resourceType') == 'Patient']
    if len(patients) != 1:
        return None
    index, patient = patients[0]
    identifiers = patient.get('identifier')
    if not isinstance(identifiers, list):
        return None
    labels, values, paths = [], [], []
    base = ('entry', index, 'resource')
    for i, identifier in enumerate(identifiers):
        if not isinstance(identifier, dict) or not isinstance(identifier.get('value'), str):
            continue
        system = identifier.get('system')
        if not isinstance(system, str) or len(system) > 256:
            continue
        try:
            parsed = urlsplit(system)
        except ValueError:
            continue
        if (parsed.scheme not in {'http', 'https'} or not parsed.netloc or parsed.query or parsed.fragment
                or parsed.path.rstrip('/').rsplit('/', 1)[-1].casefold() not in {'uhid', 'mrn'}):
            continue
        kind = identifier.get('type', {})
        coding = kind.get('coding') if isinstance(kind, dict) else None
        if not isinstance(coding, list):
            continue
        typed = [c.get('code') for c in coding if isinstance(c, dict)
                 and c.get('system') == 'http://terminology.hl7.org/CodeSystem/v2-0203']
        if typed != ['MR']:
            continue
        labels.append('mrn'); values.append(identifier['value']); paths.append((*base, 'identifier', i, 'value'))
    if len(labels) != 1:
        return None
    # An identifier-valued reference elsewhere could depend on the old value.
    # Abstain instead of editing the resource identifier without coordinating
    # its reference. Ignore Bundle.identifier (it describes the Bundle itself).
    pending = [(entries, 0)]
    while pending:
        value, depth = pending.pop()
        if depth > 80:
            return None
        if isinstance(value, dict):
            if isinstance(value.get('identifier'), dict):
                return None
            pending.extend((v, depth + 1) for v in value.values() if isinstance(v, (dict, list)))
        elif isinstance(value, list):
            pending.extend((v, depth + 1) for v in value if isinstance(v, (dict, list)))
    names = patient.get('name')
    if isinstance(names, list):
        for name in names:
            if not isinstance(name, dict):
                continue
            if isinstance(name.get('text'), str):
                labels.append('patient name'); values.append(name['text']); paths.append(())
            given, family = name.get('given'), name.get('family')
            if isinstance(given, list) and given and all(isinstance(v, str) for v in given) and isinstance(family, str):
                labels.append('patient name'); values.append(' '.join([*given, family])); paths.append(())
    for key, label in (('birthDate', 'dob'), ('gender', 'gender')):
        if isinstance(patient.get(key), str):
            labels.append(label); values.append(patient[key]); paths.append(())
    evidence = row_evidence(labels, values, secret)
    if evidence is None or not paths[evidence.column]:
        return None
    return evidence, paths[evidence.column]
