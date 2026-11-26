"""Interpret field roles from source paths without consulting detector rules."""


def structured_label(path, label, resource, contact_system=""):
    if not resource:
        if label.casefold() == "name" and any(
            isinstance(part, str) and part.casefold() in {"doctor", "physician", "provider", "clinician"}
            for part in path
        ):
            return "clinician name"
        return label

    if "identifier" in path and label == "value":
        return "patient identifier"
    if "name" in path:
        if resource in {"Patient", "RelatedPerson"} and label in {"text", "given", "family"}:
            if resource == "RelatedPerson":
                return "related person name"
            return "contact name" if "contact" in path else "patient name"
        if resource == "Practitioner":
            return "clinician name"
    if resource in {"Patient", "RelatedPerson"}:
        if "telecom" in path and label == "value":
            return "email" if contact_system == "email" else "phone"
        if "address" in path and label in {"line", "postalCode", "text", "city"}:
            return "address"
    if "valueQuantity" in path and label == "value":
        return "observation value"
    if label == "name" and isinstance(path[-1], str):
        return ""
    return label


def source_section(label, resource):
    return "fhir" if resource and label in {"contact name", "related person name"} else ""
