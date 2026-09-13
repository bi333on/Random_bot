"""Тесты рандомайзера."""
from app.services.randomizer import pick_winners


def test_pick_all_when_count_exceeds_participants():
    entries = [(1, 1), (2, 1), (3, 1)]
    assert sorted(pick_winners(entries, 5, seed=1)) == [1, 2, 3]


def test_deterministic_with_seed():
    entries = [(i, i) for i in range(1, 11)]
    assert pick_winners(entries, 3, seed=42) == pick_winners(entries, 3, seed=42)


def test_no_duplicates():
    entries = [(i, 1) for i in range(100)]
    winners = pick_winners(entries, 10, seed=7)
    assert len(winners) == 10
    assert len(set(winners)) == 10


def test_zero_weight_never_wins():
    entries = [(1, 0), (2, 1)]
    winners = pick_winners(entries, 1, seed=5)
    assert winners == [2]


def test_empty_entries():
    assert pick_winners([], 3, seed=1) == []


def test_higher_weight_wins_more_often():
    entries = [(1, 1), (2, 9)]
    counts = {1: 0, 2: 0}
    for seed in range(200):
        winner = pick_winners(entries, 1, seed=seed)[0]
        counts[winner] += 1
    assert counts[2] > counts[1]
