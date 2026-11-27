# Source-derived role follow-up

This slice adds explicit roles where supported by the source, and role-aware scoring with separate coverage. It retains the two deterministic note fixes from the previous slice. [Earlier implementation and replay](generalization-first-slices.md)

## Runtime and evidence

FHIR `Patient.name`, `Patient.contact.name` and `RelatedPerson.name` supply a patient, contact or related-person role respectively. Equal surfaces at those paths are distinct occurrences. A Practitioner name with the same surface stays intact. A patient contact may be a third party without a family relationship. Record that source role without guessing kinship. Format-derived contact and related-person roles are scoped to FHIR. A generic name label carries no affirmative role. Explicit text cues such as a patient-name label and son-of cue can supply role evidence independently of FHIR. [Patient element definitions](https://hl7.org/fhir/R4/patient-definitions.html#Patient.contact) · [RelatedPerson scope](https://hl7.org/fhir/R4/relatedperson.html#scope)

The optional accepted-role field in prediction snapshots is joined to accepted spans and validated. The scorer reports correct roles, wrong roles at an exact typed boundary, absent roles, one-to-one role overlaps, incomplete targets and support. A legacy prediction remains readable. If some annotated units have role predictions, completed units with an omitted role field remain in the role recall denominator. Precision by entity category retains the independent adjudication requirements. The open generated corpus lacks explicit role annotations, so the evaluator reports role recall as undefined there. Synthetic regression cases verify the metric on role-labeled examples.

The release auditor now reconciles legitimate same-content files when their reported output paths distinguish them. Reused output artifacts are still rejected. If a group of same-hash inputs has several different unidentifiable output dispositions, report ambiguity rather than assigning rows by order.

## Follow-up checks

The [open field-role challenge](../datasets/robustness_v2/role_probe/) compared cue/shape evidence with same-record corroboration. Corroboration avoided the two clinical false positives and flagged both homonyms. It found four of six unfamiliar-label patient targets. The heuristic remains experimental.

The paired replay from `2b5684d` and this follow-up used the same 1,400 open records. Both arms exported every record and returned 2,006 fully visible and 95 partly visible identifier labels out of 4,391. Both preserved all 2,000 checked clinical facts. Organizer practice retained 168/200 exported files and 4,382/4,855 all-input clinical probes. The original 2,000-record historical audit reproduced byte for byte as counts-only JSON. These results qualify the narrow structured-role and scoring changes on the available fixtures. Generalization to unfamiliar layouts and adjudicated role performance remain open.

## Post-review fixes

The runtime uses the same boundaries for note labels and structured name fields. Regression cases cover decimal-comma and parenthesized doses, named medications with explicit evidence, follow-up intervals, tabs inside labels and full-width colons. The inventory and runtime share field interpretation for structured clinician roles, FHIR organization names and FHIR contact-point types. Inventory failures mark malformed, unsupported and oversized files incomplete and preserve the rest of the inventory. FHIR narrative segmentation and canonical equivalence for all note cues remain open.

The auditor excludes suppressed Patient Records from coverage and utility credit and rejects repeated claims on the same output locator. The release-wide diagnostic counts exact normalized surfaces from known Direct Identifier labels in decoded fields, supported attachments, XHTML narratives, paths, the report, the index and logs. Its results can include a legitimate same-surface occurrence in a different role. Use the diagnostic alongside mapped occurrence outcomes. It emits aggregate counts and reports artifacts it could not fully scan. [Release scan](../../evaluation/release_scan.py)

The replay used runtime baseline `a243a45d140d8dd3c703169fe18fa0713e39c37a`, candidate `e5d8a11d0d8ffe3567f7c29725e68064833e675f` and the same evaluator at `811d36bfc19e46f1d069b20386197a2e6754c12f`. The open generator used seed `20261127`. Both runtimes exported all 1,400 records, fully transformed 2,290 of 4,391 labels, left 2,006 fully visible and 95 partly visible, and preserved all 2,000 checked clinical facts. The release scan found 807 unique labeled surfaces in development and 186 in validation in each arm. Organizer practice stayed at 168/200 exported files, 581 literal residual mentions and 4,382/4,855 preserved clinical probes. Both runtimes passed the toolkit validator on all three input groups. Local timing used Python 3.12.3 on Linux x86-64 with ordinary host limits. Development took 1.10 s and 1.18 s for baseline and candidate respectively. Both peaked below 22 MiB RSS on that split. These single runs do not qualify the organizer resource limits.

| Open split | Manifest SHA-256 | Candidate prediction SHA-256 |
| --- | --- | --- |
| Development | `a851dae281ca341910235037e0b9c0340b53ef4cc6efc5eae4b60e3a8cdaf51b` | `e77632d7349aef26012a5111849227347fc26a27c71bfc5c0e54136be9d929b2` |
| Validation | `4e338ce5b494b21cdbb4cfb0f0dea0f716a150ed1b28713e25959f97aa6ca772` | `3537a27c2867236d9318ce708baf482d6fcda7cbccbb8359b57b57af09f8007d` |

On 16 new open examples, compare three policies using the same source fields and compare each outcome with the authored truth afterwards. The shape policy promotes two to four Unicode letter or mark tokens in a record with a diagnosis field. The corroboration policy requires an exact same-record patient-name anchor after NFC, case and whitespace folding. A clinician or diagnosis value that matches the candidate makes it ambiguous.

| Policy | Patient names found | Protected values incorrectly promoted | Ambiguous cases flagged |
| --- | ---: | ---: | ---: |
| Current detector | 0 / 8 | 0 / 5 | 0 / 3 |
| Shape and diagnosis context | 7 / 8 | 4 / 5 | 0 / 3 |
| Patient anchor with conflicting-role check | 5 / 8 | 0 / 5 | 3 / 3 |

The corroboration experiment stays outside the runtime. It requires independent review with more layouts and unanchored cases. The missed names and unchanged corpus scores leave generalization across unfamiliar fields open.
