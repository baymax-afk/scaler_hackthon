# Synthetic datasets

- [Organizer practice dataset](../../dev/) contains the official development inputs, truth, and attacker auxiliary data.
- [Secret Wards Blind](secret_wards_blind/) contains original synthetic QA fixtures with 2,000 truth records across CSV, TSV, JSON, and plain text. Its four hospital registration exports use CSV twice, TSV once, and JSON once. Plain text is used for clinical notes.
- [Version 2 open annotation example](robustness_v2/open_example/) gives a synthetic Patient Record with original code-point offsets, two roles for the same surface, protected clinical facts, and a deliberately incomplete prediction.
- [Version 2 open development slice](robustness_v2/) generates five synthetic Patient Records across text, CSV, TSV, JSON, and a FHIR document Bundle with hashed inputs, exact annotations, and lineage checks.

Use only the blind dataset's `input/` folder as pipeline input. Keep `truth/` and the [attack QA record](ATTACK_QA.md) with evaluation materials. The manifest records the seed and SHA-256 hashes for 562 input files.

To regenerate the blind fixtures, run this command from the repository root with Python 3.10 or later. The output directory must be new.

```sh
python docs/datasets/generate_secret_wards.py --output ./secret_wards_blind_rebuilt --seed 370319 --count 2000
```
