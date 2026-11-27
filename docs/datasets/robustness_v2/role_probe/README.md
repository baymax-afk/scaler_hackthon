# Open field-role challenge

These 12 fictional, manually specified cases stress-test role inference. They are development material outside the 1,400 open benchmark records. The fixture contains six patient targets under unfamiliar labels, four protected values and two unresolved homonyms. The expected labels are fixture truth for evaluation. Supply only the label, value and neighboring source fields to a detector.

Compare the existing detector with two experimental policies. The loose policy only promotes values under a subject cue when another field indicates a clinical context and the value resembles a person name. Use two to four tokens composed of Unicode letters and marks. The anchored policy adds two conditions. The same record must independently identify the same value in its explicit patient name field after NFC, whitespace folding and case folding. If an explicit clinician field also carries that value, report unresolved. The experiment groups the source fields as they would appear in one record. It does not establish parsing or runtime behavior for a new format.

| Arm | Patient detections | Protected values incorrectly promoted | Homonyms correctly marked unresolved |
| --- | ---: | ---: | ---: |
| Current generic field recognition | 0/6 | 0/4 | 0/2 |
| Loose subject, context and shape cues | 6/6 | 2/4 | 0/2 |
| Add same-record patient evidence and check role disagreement | 4/6 | 0/4 | 2/2 |

The anchored rule still misses the uncorroborated case and the abbreviation. These are authored examples and do not establish coverage on new clinical formats. Keep both experimental promotions outside the runtime pending independent review and layout variation. [Fixture cases](cases.json)
