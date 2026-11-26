"""Aggregate Patient Record linkage scores for a fully labeled synthetic cohort.

Pair quality uses adjudicated, eligible pairs. A positive pair with an
abstention is a Missed Link for recall; negative abstentions are unscored.
Partial labels remain visible as support counts.
"""

from collections import Counter, defaultdict


def _ratio(numerator, denominator):
    return numerator / denominator if denominator else None


def score_linkage(records, predictions, pairs):
    """Score opaque record joins and pair labels without returning IDs or tokens.

    ``records`` are manifest-like dictionaries with ``id`` and ``patient_group``.
    ``predictions`` maps every record ID to a Patient Pseudonym or ``None``.
    ``pairs`` contains distinct unordered record pairs with adjudication status.
    """
    if not isinstance(records, list) or not isinstance(predictions, dict) or not isinstance(pairs, list):
        raise ValueError("invalid_linkage_input")

    groups = {}
    for record in records:
        if not isinstance(record, dict):
            raise ValueError("invalid_linkage_record")
        identifier = record.get("id")
        patient_group = record.get("patient_group")
        if not isinstance(identifier, str) or not identifier or \
                not isinstance(patient_group, str) or not patient_group:
            raise ValueError("invalid_linkage_record")
        if identifier in groups:
            raise ValueError("duplicate_record_id")
        groups[identifier] = patient_group

    if predictions.keys() != groups.keys():
        raise ValueError("invalid_prediction_join")
    if any(token is not None and (not isinstance(token, str) or not token)
           for token in predictions.values()):
        raise ValueError("invalid_patient_pseudonym")

    clusters = defaultdict(set)
    predicted_group = {}
    for identifier, token in predictions.items():
        if token is not None:
            clusters[token].add(groups[identifier])
        predicted_group[identifier] = ("linked", token) if token is not None else ("abstained", identifier)
    false_merged_clusters = sum(len(patient_groups) > 1 for patient_groups in clusters.values())
    predicted_sizes = Counter(predicted_group.values())
    true_sizes = Counter(groups.values())
    intersections = Counter((predicted_group[identifier], groups[identifier])
                            for identifier in groups)
    b_cubed_precision = _ratio(sum(intersections[(predicted_group[identifier], groups[identifier])]
                                   / predicted_sizes[predicted_group[identifier]]
                                   for identifier in groups), len(groups))
    b_cubed_recall = _ratio(sum(intersections[(predicted_group[identifier], groups[identifier])]
                                / true_sizes[groups[identifier]]
                                for identifier in groups), len(groups))

    counts = Counter()
    seen_pairs = set()
    for pair in pairs:
        if not isinstance(pair, dict):
            raise ValueError("invalid_pair_label")
        left, right = pair.get("left"), pair.get("right")
        if not isinstance(left, str) or not isinstance(right, str) or \
                left not in groups or right not in groups or left == right:
            raise ValueError("invalid_pair_join")
        key = frozenset((left, right))
        if key in seen_pairs:
            raise ValueError("duplicate_pair_label")
        seen_pairs.add(key)
        same = pair.get("same_patient")
        eligible = pair.get("eligible")
        status = pair.get("annotation_status")
        if type(same) is not bool or type(eligible) is not bool or \
                status not in {"adjudicated", "partial"}:
            raise ValueError("invalid_pair_label")
        counts["input_pairs"] += 1
        if status != "adjudicated":
            counts["partial_pairs"] += 1
            continue
        if same != (groups[left] == groups[right]):
            raise ValueError("inconsistent_patient_group_truth")
        counts["adjudicated_pairs"] += 1
        if not eligible:
            counts["ineligible_pairs"] += 1
            continue
        counts["eligible_pairs"] += 1
        left_token, right_token = predictions[left], predictions[right]
        if left_token is None or right_token is None:
            counts["abstained_eligible_pairs"] += 1
            if same:
                counts["abstained_positive_pairs"] += 1
                counts["fn"] += 1
            else:
                counts["abstained_negative_pairs"] += 1
            continue
        counts["scored_pairs"] += 1
        linked = left_token == right_token
        counts[("tp" if linked else "fn") if same else ("fp" if linked else "tn")] += 1

    tp, fp, fn = (counts[k] for k in ("tp", "fp", "fn"))
    return {
        "counts": {name: counts[name] for name in (
            "input_pairs", "partial_pairs", "adjudicated_pairs", "ineligible_pairs",
            "eligible_pairs", "abstained_eligible_pairs", "abstained_positive_pairs",
            "abstained_negative_pairs", "scored_pairs",
            "tp", "fp", "fn", "tn")},
        "records": len(groups),
        "abstained_records": sum(token is None for token in predictions.values()),
        "predicted_clusters": len(clusters),
        "false_merged_clusters": false_merged_clusters,
        "b_cubed_diagnostic": {"precision": b_cubed_precision,
                                "recall": b_cubed_recall},
        "precision": _ratio(tp, tp + fp),
        "recall": _ratio(tp, tp + fn),
        "f0_5": (_ratio(1.25 * tp, 1.25 * tp + 0.25 * fn + fp)
                 if tp + fn else None),
    }
