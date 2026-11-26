"""One-to-one matching for independent occurrence scoring."""
from collections import deque


def overlap_matches(gold, actual):
    """Maximum one-to-one same-kind matches with any code-point overlap."""
    wanted = sorted(gold)
    found = sorted(actual)
    neighbors = [[index for index, (left, right, kind) in enumerate(found)
                  if kind == expected_kind and start < right and left < end]
                 for start, end, expected_kind in wanted]
    assigned_actual = {}
    assigned_gold = {}
    for start in range(len(wanted)):
        queue = deque([start])
        visited_gold = {start}
        parent_actual = {}
        free_actual = None
        while queue and free_actual is None:
            gold_index = queue.popleft()
            for actual_index in neighbors[gold_index]:
                if actual_index in parent_actual:
                    continue
                parent_actual[actual_index] = gold_index
                if actual_index not in assigned_actual:
                    free_actual = actual_index
                    break
                next_gold = assigned_actual[actual_index]
                if next_gold not in visited_gold:
                    visited_gold.add(next_gold)
                    queue.append(next_gold)
        while free_actual is not None:
            gold_index = parent_actual[free_actual]
            previous_actual = assigned_gold.get(gold_index)
            assigned_actual[free_actual] = gold_index
            assigned_gold[gold_index] = free_actual
            free_actual = previous_actual
    return len(assigned_actual)
