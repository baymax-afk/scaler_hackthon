# Source-derived role follow-up

This slice adds explicit roles where supported by the source, and role-aware scoring with separate coverage. It retains the two deterministic note fixes from the previous slice. [Earlier implementation and replay](generalization-first-slices.md)

## Runtime and evidence

FHIR `Patient.name`, `Patient.contact.name` and `RelatedPerson.name` supply a patient, contact or related-person role respectively. Equal surfaces at those paths are distinct occurrences. A Practitioner name with the same surface stays intact. A patient contact may be a third party without a family relationship. Record that source role without guessing kinship. Format-derived contact and related-person roles are scoped to FHIR. A generic name label carries no affirmative role. Explicit text cues such as a patient-name label and son-of cue can supply role evidence independently of FHIR. [Patient element definitions](https://hl7.org/fhir/R4/patient-definitions.html#Patient.contact) · [RelatedPerson scope](https://hl7.org/fhir/R4/relatedperson.html#scope)

The optional accepted-role field in prediction snapshots is joined to accepted spans and validated. The scorer reports correct roles, wrong roles at an exact typed boundary, absent roles, one-to-one role overlaps, incomplete targets and support. A legacy prediction remains readable. If some annotated units have role predictions, completed units with an omitted role field remain in the role recall denominator. Precision by entity category retains the independent adjudication requirements. The open generated corpus lacks explicit role annotations, so the evaluator reports role recall as undefined there. Synthetic regression cases verify the metric on role-labeled examples.

The release auditor now reconciles legitimate same-content files when their reported output paths distinguish them. Reused output artifacts are still rejected. If a group of same-hash inputs has several different unidentifiable output dispositions, report ambiguity rather than assigning rows by order.

## Follow-up checks

The [open field-role challenge](../datasets/robustness_v2/role_probe/) compared cue/shape evidence with same-record corroboration. Corroboration avoided the two clinical false positives and flagged both homonyms. It found four of six unfamiliar-label patient targets. The heuristic remains experimental.

The paired replay from `2b5684d` and this follow-up used the same 1,400 open records. Both arms exported every record and returned 2,006 fully visible and 95 partly visible identifier labels out of 4,391. Both preserved all 2,000 checked clinical facts. Organizer practice retained 168/200 exported files and 4,382/4,855 all-input clinical probes. The original 2,000-record historical audit reproduced byte for byte as counts-only JSON. These results qualify the narrow structured-role and scoring changes on the available fixtures. Generalization to unfamiliar layouts and adjudicated role performance remain open.
