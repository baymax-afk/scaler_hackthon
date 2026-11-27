"""Conservative, source-only quasi-identifier transforms for patient records.

Only independently recognizable patient tables and explicitly named fields are
eligible. The caller retains responsibility for direct identifier detection, file
quarantine, and reporting whether a generalized row was actually released.
"""

from __future__ import annotations

import hashlib
import hmac
import re
import unicodedata
from collections.abc import Sequence
from datetime import datetime, timedelta


_AGE = frozenset({
    "age", "age years", "age yrs", "age y", "age in years", "age in yrs",
    "patient age", "patient age years", "patient age yrs", "patient age in years",
    "ageyears", "patientage", "ageyrs", "umar", "umr", "umar years", "umar yrs",
    "age saal", "age sex", "age gender", "age and sex", "age and gender",
    "patient age sex", "patient age gender", "age yrs sex", "age years sex",
    "age sex yrs", "age gender yrs", "उम्र", "आयु", "उम्र वर्ष", "आयु वर्ष",
    "उम्र लिंग", "आयु लिंग",
    "मरीज की उम्र", "मरीज़ की उम्र", "रोगी की आयु", "रोगी की उम्र",
})
_PIN = frozenset({
    "pin", "pin code", "pincode", "zip", "zip code", "postal code", "postalcode",
    "patient pin", "address pin", "patient pin code", "postal pin",
    "पिन", "पिन कोड", "पिनकोड", "डाक कोड",
})
_LOCATION = frozenset({
    "village", "village name", "patient village", "patient locality",
    "locality", "locality name", "mohalla", "gram", "gaon", "village mohalla",
    "गांव", "गाँव", "ग्राम", "मोहल्ला", "मुहल्ला", "ग्राम मोहल्ला", "बस्ती",
})
_DISTRICT = frozenset({
    "district", "district name", "patient district", "address district",
    "jila", "zilla", "जिला", "ज़िला", "ज़िला",
})
_PATIENT = frozenset({
    "patient", "patient name", "patient full name", "patient id", "patientid",
    "patient identifier", "patient ref", "patient display", "patientname",
    "mrn", "uhid", "hospital uhid", "medical record no", "medical record number",
    "medical record id", "patient chart id", "patient chart", "beneficiary name",
    "रोगी का नाम", "मरीज का नाम", "मरीज़ का नाम", "mareez ka naam",
})
_NAME = frozenset({"name", "full name", "naam", "नाम", "first name", "last name"})
_REG = frozenset({
    "reg no", "reg number", "registration no", "registration number", "ipd no",
    "opd no", "admission no", "admission id", "hospital id",
})
_GOV = frozenset({
    "aadhaar", "aadhaar no", "aadhaar number", "aadhar", "aadhar no",
    "abha", "abha no", "abha number", "abha address", "आधार",
})
_CONTACT = frozenset({
    "phone", "phone no", "phone number", "mobile", "mobile no", "mobile number",
    "contact no", "contact number", "email", "email address", "फोन", "मोबाइल",
})
_NON_PATIENT = frozenset({
    "employee", "employee name", "employee id", "staff", "staff name", "staff id",
    "doctor id", "clinician id", "provider id", "specimen id", "sample id",
    "drug code", "product code",
})
_MISSING = frozenset({
    "", "-", "--", "na", "n/a", "none", "null", "unknown", "not known",
    "not available", "not applicable", "redacted", "withheld", "[redacted]",
    "[address]", "[locality]", "[village]", "अज्ञात", "उपलब्ध नहीं", "पता नहीं",
})


def _role(label: str) -> str:
    # Unlike general label normalization, keep words in parentheses. A field
    # called "Age (days)" must never be interpreted as age in years.
    if not isinstance(label, str):
        return ""
    label = unicodedata.normalize("NFKC", label)
    label = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", label).casefold()
    words = (character if character.isalnum() or unicodedata.category(character).startswith("M")
             else " " for character in label)
    return " ".join("".join(words).split())


def _present(value: str) -> bool:
    return isinstance(value, str) and value.strip().casefold() not in _MISSING


def _decimal_digits(value: str) -> str | None:
    source = value.strip()
    if not source or len(source) > 6:
        return None
    try:
        return "".join(str(unicodedata.decimal(ch)) for ch in source)
    except ValueError:
        return None


_EXACT_AGE = re.compile(
    r"(?P<prefix>[ \t]*)(?P<digits>\d{1,3})"
    r"(?P<suffix>(?:[ \t]*(?:years?|yrs?|y|saal|varsh|वर्ष|साल))?"
    r"(?:[ \t]*[/,][ \t]*(?:male|female|m|f|पुरुष|महिला|स्त्री))?)"
    r"(?P<trailing>[ \t]*)", re.I
)


def _age_band(value: str) -> str | None:
    match = _EXACT_AGE.fullmatch(value)
    if not match:
        return None
    digits = _decimal_digits(match["digits"])
    if digits is None or int(digits) > 125:
        return None
    low = int(digits) // 5 * 5
    return f'{match["prefix"]}{low}-{low+4}{match["suffix"]}{match["trailing"]}'


def _location(value: str) -> str | None:
    if not _present(value):
        return None
    cleaned = value.strip()
    if len(cleaned) > 128 or not any(ch.isalpha() for ch in cleaned):
        return None
    if any(unicodedata.category(ch).startswith("C") for ch in cleaned):
        return None
    return cleaned


def _district(value: str) -> str | None:
    cleaned = _location(value)
    # The field must be a single, plain district name, not a free-form address.
    # Some genuine district labels have digits; conservatively abstain from
    # duplicating their names instead of guessing how to parse them.
    if cleaned and all(unicodedata.category(ch)[0] in "LM" or ch in " .-'’"
                       for ch in cleaned):
        return cleaned
    return None


def _patient_row(roles: list[str], row: Sequence[str]) -> bool:
    present = {role for role, value in zip(roles, row) if _present(value)}
    if _PATIENT & present:
        return True
    # Localized registration schemas may use only generic names and numbered
    # registration fields. Require all three independent identity-role groups.
    return not (_NON_PATIENT & present) and bool(
        _NAME & present and _REG & present and _GOV & present and _CONTACT & present
    )


def generalize_row(header: Sequence[str], row: Sequence[str]) -> dict[int, str]:
    """Return only changed existing-cell index/value pairs, without mutating input.

    Age is generalized to an inclusive, truthful five-year band only when the
    source is an exact age of 0..125 years (optionally with year/sex suffix). PINs become a truthful three-digit
    prefix plus "***". A locality may use the explicitly supplied district from
    the same row only when exactly one plausible district field exists.

    CSV/TSV cell strings remain strings. Do not apply this adapter to JSON, FHIR,
    free-text notes, or unproven field roles. A district role is source-structural
    evidence, not independently validated geographic truth.
    """
    if isinstance(header, str) or isinstance(row, str) or len(header) != len(row):
        return {}
    if not all(isinstance(value, str) for value in row):
        return {}
    roles = [_role(label) for label in header]
    if not _patient_row(roles, row):
        return {}

    district_indices = [i for i, role in enumerate(roles) if role in _DISTRICT]
    district = _district(row[district_indices[0]]) if len(district_indices) == 1 else None
    # Do not duplicate a same-row personal name disguised as a district.
    if district and any(role in (_PATIENT | _NAME) and district.casefold() == value.strip().casefold()
                        for role, value in zip(roles, row)):
        district = None

    return {i: replacement
            for i, (role, value) in enumerate(zip(roles, row))
            if (replacement := _transform(role, value, district)) is not None}


def _transform(role: str, value: str, district: str | None) -> str | None:
    if role in _AGE:
        return _age_band(value)
    if role in _PIN:
        digits = _decimal_digits(value)
        if digits is not None and len(digits) == 6 and digits[0] != "0":
            return digits[:3] + "***"
    if role in _LOCATION and district is not None and value != district and _location(value):
        return district
    return None


_JSON_PATIENT_GROUPS = frozenset({
    "patient", "patient details", "patient information", "patient info",
    "beneficiary", "patient demographics",
})
_JSON_NESTED_GROUPS = frozenset({
    "address", "patient address", "residence", "demographics", "demographic",
    "personal details", "address details", "demographic details",
})
_JSON_ADDRESS_LISTS = frozenset({"addresses", "patient addresses"})


def _fhir(node: dict) -> bool:
    # FHIR primitives and native numbers must keep their exact typed shape.
    return any(_role(key) == "resource type" for key in node)


def _patient_keys(node: dict) -> bool:
    fields = [(key, value) for key, value in node.items() if isinstance(key, str)]
    roles = [_role(key) for key, _ in fields]
    values = [value if isinstance(value, str) else str(value) if type(value) is int else ""
              for _, value in fields]
    return _patient_row(roles, values)


def _source_json_fields(node: dict, prefix: tuple, result: list, depth: int = 0) -> None:
    """Enumerate strings only in explicit patient-field subcontainers."""
    if depth > 4 or _fhir(node):
        return
    for key, value in node.items():
        if not isinstance(key, str):
            continue
        role = _role(key)
        path = (*prefix, key)
        if isinstance(value, str):
            result.append((path, role, value))
        elif isinstance(value, dict) and role in _JSON_NESTED_GROUPS:
            _source_json_fields(value, path, result, depth + 1)
        elif isinstance(value, list) and role in _JSON_ADDRESS_LISTS:
            for index, item in enumerate(value):
                if isinstance(item, dict):
                    _source_json_fields(item, (*path, index), result, depth + 1)


def generalize_json_record(record: object) -> dict[tuple[str | int, ...], str]:
    """Return changes for textual quasi-identifiers relative to a patient record.

    Root patient identity roles or a single explicitly patient-named object are
    required. Recognized nested address/demographic objects are supported; arbitrary
    descendants, FHIR resources, free text, clinical/staff objects, and numeric
    values are not transformed. Do not call this on a collection wrapper: invoke
    per record, after source-derived record locators have been established.
    """
    if not isinstance(record, dict) or _fhir(record):
        return {}
    patient_groups = [(key, value) for key, value in record.items()
                      if _role(key) in _JSON_PATIENT_GROUPS and isinstance(value, dict)]
    if len(patient_groups) > 1:
        return {}
    fields = []
    if _patient_keys(record):
        _source_json_fields(record, (), fields)
    if patient_groups:
        key, node = patient_groups[0]
        _source_json_fields(node, (key,), fields)
    if not fields:
        return {}
    district_values = [value for _, role, value in fields if role in _DISTRICT]
    district = _district(district_values[0]) if len(district_values) == 1 else None
    if district and any(role in (_PATIENT | _NAME) and district.casefold() == value.strip().casefold()
                        for _, role, value in fields):
        district = None
    return {path: replacement for path, role, value in fields
            if (replacement := _transform(role, value, district)) is not None}


# Date shifts are deliberately separate from field transforms. Their caller must
# establish an unambiguous Patient Pseudonym and apply one offset to ALL dates of
# that patient, not merely the direct dates in a single record.
_DATE_FORMATS = frozenset({
    "%Y-%m-%d", "%Y/%m/%d", "%d/%m/%Y", "%m/%d/%Y", "%d-%m-%Y", "%m-%d-%Y"
})


def patient_day_shift(secret: str | bytes, patient_token: str | bytes) -> int:
    """Derive one nonzero, release-keyed day offset for a confirmed patient.

    The opaque Patient token must be shared across every record of that patient.
    Offset range is [-365,-1] U [1,365]; finite-range collisions across patients
    or secrets remain possible. Never use a raw name or ambiguous linkage clue.
    """
    key = secret.encode("utf-8") if isinstance(secret, str) else secret
    token = patient_token.encode("utf-8") if isinstance(patient_token, str) else patient_token
    if not isinstance(key, bytes) or not key or not isinstance(token, bytes) or not token:
        raise ValueError("missing_shift_key_or_patient_token")
    digest = hmac.new(key, b"raksha-date-shift-v1\0" + token, hashlib.sha256).digest()
    index = int.from_bytes(digest[:8], "big") % 730
    return index - 365 if index < 365 else index - 364


def shift_patient_date(value: str, days: int, *, date_format: str) -> str | None:
    """Shift an exact calendar date in the explicitly established input format.

    No ambiguous format guessing, timestamps, partial dates, or coercion. Return
    None for an unsupported date; the caller owns abstention/quarantine policy.
    """
    if (type(value) is not str or type(days) is not int or not days
            or abs(days) > 365 or date_format not in _DATE_FORMATS):
        return None
    try:
        parsed = datetime.strptime(value, date_format)
        if parsed.strftime(date_format) != value:
            return None
        shifted = parsed + timedelta(days=days)
        return shifted.strftime(date_format)
    except (ValueError, OverflowError):
        return None
