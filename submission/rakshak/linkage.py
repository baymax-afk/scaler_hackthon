"""Conservative table-only identity linkage from typed source fields.

Collect evidence before redaction, retain it only after a row is exportable,
then resolve the batch. The caller must replace the selected identifier cell
(``RowEvidence.column``) with the returned pseudonym, and record the same token
in records.jsonl. Raw identifiers, names, DOBs, ages, relative and locality
values are never retained in evidence. Keys and evidence must not be logged.
"""
from collections import defaultdict
from dataclasses import dataclass
from datetime import date
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
