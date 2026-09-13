"""Криптостойкий взвешенный выбор победителей без повторений."""
from __future__ import annotations

import random


def pick_winners(
    entries: list[tuple[int, int]],
    count: int,
    seed: int | None = None,
) -> list[int]:
    """Вернуть список идентификаторов победителей.

    entries — список (id, weight). weight <= 0 считается нулевым.
    При count >= числа участников возвращает всех.
    seed задаёт детерминированный выбор (для тестов); иначе SystemRandom.
    """
    if count <= 0:
        return []
    if len(entries) <= count:
        return [entry[0] for entry in entries]

    rng: random.Random
    if seed is not None:
        rng = random.Random(seed)
    else:
        rng = random.SystemRandom()

    pool = [[entry[0], max(0, entry[1])] for entry in entries]
    winners: list[int] = []

    for _ in range(count):
        total = sum(weight for _, weight in pool)
        if total <= 0:
            idx = rng.randrange(len(pool))
        else:
            r = rng.random() * total
            upto = 0
            idx = len(pool) - 1
            for i, (_, weight) in enumerate(pool):
                upto += weight
                if r < upto:
                    idx = i
                    break
        winners.append(pool.pop(idx)[0])

    return winners
