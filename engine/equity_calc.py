from __future__ import annotations
from itertools import combinations
import numpy as np
from .cards import ALL_CARDS
from .hand_evaluator import evaluate_hand
from .game_state import GameState


def _outcome(hero_score: int, villain_scores: list[int]) -> float:
    """1.0 = hero wins, 0.5 = split, 0.0 = hero loses. (treys: lower score = stronger)"""
    best_villain = min(villain_scores)
    if best_villain > hero_score:
        return 1.0
    if best_villain == hero_score:
        return 0.5
    return 0.0


def _equity_river_exact(hole: list[int], board: list[int], available: list[int]) -> float:
    """Exact equity on river (1 villain). 990 combos, ~18ms."""
    hero_score = evaluate_hand(hole, board)
    wins = 0.0
    total = 0
    for vh in combinations(available, 2):
        total += 1
        wins += _outcome(hero_score, [evaluate_hand(list(vh), board)])
    return wins / total if total else 0.0


def _equity_turn_exact(hole: list[int], board: list[int], available: list[int]) -> float:
    """Exact equity on turn (1 villain). ~45k combos, ~750ms."""
    wins = 0.0
    total = 0
    n = len(available)
    for i in range(n):
        river_card = available[i]
        full_board = board + [river_card]
        hero_score = evaluate_hand(hole, full_board)
        rem = available[:i] + available[i + 1 :]
        for vh in combinations(rem, 2):
            total += 1
            wins += _outcome(hero_score, [evaluate_hand(list(vh), full_board)])
    return wins / total if total else 0.0


def _equity_montecarlo(
    hole: list[int],
    board: list[int],
    available: list[int],
    num_villains: int,
    n_simulations: int,
) -> float:
    """Monte Carlo equity estimation."""
    avail_np = np.array(available, dtype=np.int64)
    board_needed = 5 - len(board)
    cards_per_sim = board_needed + 2 * num_villains
    rng = np.random.default_rng()
    wins = 0.0

    for _ in range(n_simulations):
        idx = rng.choice(len(avail_np), size=cards_per_sim, replace=False)
        sampled = avail_np[idx]

        sim_board = board + sampled[:board_needed].tolist()
        hero_score = evaluate_hand(hole, sim_board)

        villain_scores = [
            evaluate_hand(sampled[board_needed + i * 2 : board_needed + i * 2 + 2].tolist(), sim_board)
            for i in range(num_villains)
        ]
        wins += _outcome(hero_score, villain_scores)

    return wins / n_simulations


def calc_equity(state: GameState, n_simulations: int = 10_000) -> tuple[float, str]:
    """
    Compute hero equity. Returns (equity_fraction, method_label).
    Dispatches to exact exhaustive on river (1v) and turn (1v), Monte Carlo otherwise.
    """
    known = set(state.hole_cards + state.board)
    available = [c for c in ALL_CARDS if c not in known]
    hole = state.hole_cards
    board = state.board
    nv = state.num_villains

    if state.street == "river" and nv == 1:
        return _equity_river_exact(hole, board, available), "exact"

    if state.street == "turn" and nv == 1:
        return _equity_turn_exact(hole, board, available), "exact"

    return _equity_montecarlo(hole, board, available, nv, n_simulations), "MC"


def _ev_call(equity: float, pot: float, to_call: float) -> float:
    return equity * pot - (1 - equity) * to_call


def _ev_raise(equity: float, pot: float, to_call: float, raise_extra: float, fold_equity: float) -> float:
    immediate_gain = fold_equity * pot
    contested_ev = (1 - fold_equity) * (equity * (pot + to_call + raise_extra) - (to_call + raise_extra))
    return immediate_gain + contested_ev


def calc_action_evs(state: GameState, equity: float) -> dict[str, float]:
    """EV in BBs for each action, relative to fold (fold = 0)."""
    pot = state.pot
    to_call = state.to_call
    evs: dict[str, float] = {"fold": 0.0}

    if state.can_check:
        evs["check"] = equity * pot
    else:
        evs["call"] = _ev_call(equity, pot, to_call)

    for multiplier in state.bet_sizes:
        raise_extra = round(multiplier * pot, 1)
        if to_call + raise_extra >= state.hero_stack:
            label = "all-in"
            raise_extra = max(state.hero_stack - to_call, 0)
        else:
            label = f"raise {multiplier}x"

        if label not in evs:
            fold_eq = min(0.20 + 0.05 * multiplier, 0.45)
            evs[label] = _ev_raise(equity, pot, to_call, raise_extra, fold_eq)

    return evs
