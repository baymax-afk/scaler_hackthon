"""Score explicit source-derived roles independently of category matching."""
from dataclasses import dataclass

from evaluation.matching import overlap_matches


def accepted_roles(result, accepted):
    assignments = {}
    for start, end, kind, role in result.get("accepted_roles", ()):
        span = start, end, kind
        if span not in accepted or span in assignments or not isinstance(role, str) or not role:
            raise ValueError("invalid_prediction_role")
        assignments[span] = role
    return assignments


@dataclass
class RoleMetrics:
    known_role_targets: int = 0
    incomplete_targets: int = 0
    role_pass_units: int = 0
    targets_in_role_pass_units: int = 0
    correct_exact: int = 0
    wrong_role_exact: int = 0
    exact_missing_role: int = 0
    one_to_one_role_overlaps: int = 0

    def update(self, expected, accepted, result):
        roles = accepted_roles(result, accepted)
        self.known_role_targets += len(expected)
        if result["status"] != "complete":
            self.incomplete_targets += len(expected)
            return
        if "accepted_roles" in result:
            self.role_pass_units += 1
            self.targets_in_role_pass_units += len(expected)
        if not expected:
            return
        gold = {(start, end, (kind, role)) for (start, end, kind), role in expected.items()}
        actual = {(start, end, (kind, role)) for (start, end, kind), role in roles.items()}
        self.one_to_one_role_overlaps += overlap_matches(gold, actual)
        for span in expected.keys() & accepted:
            if span not in roles:
                self.exact_missing_role += 1
            elif roles[span] == expected[span]:
                self.correct_exact += 1
            else:
                self.wrong_role_exact += 1

    def summary(self):
        complete = self.known_role_targets - self.incomplete_targets
        return {
            **vars(self),
            "role_target_coverage": self.targets_in_role_pass_units / complete if complete else None,
            "known_role_recall": self.correct_exact / complete if self.targets_in_role_pass_units else None,
        }
