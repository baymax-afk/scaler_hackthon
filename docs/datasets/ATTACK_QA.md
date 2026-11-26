# Attack QA record

Attack IDs follow the [Privacy Attack Arena](../ATTACKS.md). The table records coverage and expectations for the original synthetic fixtures. Runtime outcomes are pending.

| Attack | Fixtures and expected protection | Status |
| --- | --- | --- |
| A1 Direct exposure | Text and filename canaries, a JSON key canary, and FHIR narrative and attachments. Direct identifiers should be absent from the release and side channels. | Fixtures available |
| A2/A3 Registry linkage | Age and village outliers are candidates. Use a same-seed synthetic registry with non-patient decoys to measure matches. | Registry needed |
| A4 Profile aggregation | Repeated patients across hospital exports and scripts. Compare the exposure of individual records and combined profiles once a registry is available. | Registry needed |
| A5 Targeted linkage | Age and long-stay outliers. Verify preservation of clinical values and date intervals, then assess disclosure with same-seed known visit facts and decoys. | Known facts needed |
| A6 Pseudonym inversion | Generated identifiers can support keyed pseudonym checks against a sanitized release. | Pipeline runs needed |
| A7 Cross-release linkability | Compare pseudonyms and shifted dates from two runs using different secrets. | Pipeline runs needed |

Log one row per seed, fixture ID, release version, and attack or combination. Record whether the fixture was designed for it, the expected outcome, the observed outcome, and the evidence channel. Use opaque fixture IDs and keep raw identifiers and secrets out of result logs. Test combinations independently and count cases that only succeed when evidence is combined.

Compare attacks over the same eligible cases. Report correct matches, false matches, and case counts. Compare A1–A5 against their raw-input baselines where available.
