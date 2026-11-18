from __future__ import annotations
from dataclasses import dataclass, field
from .game_state import GameState
from .equity_calc import calc_equity, calc_action_evs
from .hand_evaluator import hand_rank_str, evaluate_hand
from .icm import (
    icm_adjustment,
    calc_icm,
    calc_bubble_factor,
    calc_icm_dollar_evs,
)


@dataclass
class Recommendation:
    best_action: str
    best_ev_bb: float
    equity_pct: float
    method: str                        # "exact" | "MC"
    hand_str: str
    all_evs_bb: dict[str, float]
    # ICM / tournament
    icm_factor: float                  # applied multiplier
    bubble_factor: float               # BF for call decision
    pressure_label: str                # "ON THE BUBBLE", "ITM", etc.
    pressure_weight: float             # [0, 1]
    # $ EVs (None if no buy-in)
    current_icm_dollar: float | None
    all_evs_dollar: dict[str, float]   # $ delta per action vs fold
    icm_equity_pct: float | None       # share of the prize pool in %


def recommend(state: GameState, n_simulations: int = 10_000) -> Recommendation:
    equity, method = calc_equity(state, n_simulations)
    chip_evs = calc_action_evs(state, equity)

    pw = state.pressure_weight
    has_icm = bool(state.payouts) and pw > 0

    # ── ICM adjustment ────────────────────────────────────────────────────────
    icm_factor = 1.0
    bubble_factor = 1.0
    icm_equity_pct = None
    current_icm_dollar = None
    evs_dollar: dict[str, float] = {}
    pressure_label = "Cash Game"

    if has_icm:
        all_stacks = state.all_stacks
        icm_factor = icm_adjustment(
            all_stacks, state.payouts, hero_idx=0, pressure_weight=pw
        )
        bubble_factor = calc_bubble_factor(
            all_stacks, state.payouts,
            to_call=state.to_call, pot=state.pot, hero_idx=0,
        )
        icm_equities = calc_icm(all_stacks, state.payouts)
        icm_equity_pct = icm_equities[0] * 100
        pressure_label = (
            state.tournament.pressure_label
            if state.tournament is not None
            else "ITM"
        )

        if state.tournament is not None:
            prize_pool = state.tournament.prize_pool
            dollar_evs = calc_icm_dollar_evs(
                all_stacks=all_stacks,
                payouts=state.payouts,
                prize_pool=prize_pool,
                equity=equity,
                to_call=state.to_call,
                pot=state.pot,
                hero_idx=0,
            )
            current_icm_dollar = dollar_evs["current_usd"]
            call_gain = dollar_evs["call_gain_usd"]
            for action in chip_evs:
                if action == "fold":
                    evs_dollar[action] = 0.0
                elif action in ("call", "check"):
                    evs_dollar[action] = call_gain
                else:
                    # raise: rough approximation (more chips at risk → scale)
                    evs_dollar[action] = call_gain * 1.1  # placeholder

    # ── Apply ICM factor to chip EVs (non-fold actions) ──────────────────────
    adjusted_evs: dict[str, float] = {}
    for action, ev in chip_evs.items():
        if action == "fold":
            adjusted_evs[action] = 0.0
        else:
            adjusted_evs[action] = ev * icm_factor
    # Bubble factor: if BF > 1, penalize the call further
    if bubble_factor > 1.0:
        call_action = "call" if not state.can_check else "check"
        if call_action in adjusted_evs:
            # Reduce the call EV proportionally to the BF above 1
            bf_penalty = min((bubble_factor - 1.0) * 0.5, 0.4)
            adjusted_evs[call_action] *= (1.0 - bf_penalty)

    best_action = max(adjusted_evs, key=lambda a: adjusted_evs[a])
    best_ev = adjusted_evs[best_action]

    hand_str = ""
    if state.board:
        score = evaluate_hand(state.hole_cards, state.board)
        hand_str = hand_rank_str(score)

    return Recommendation(
        best_action=best_action,
        best_ev_bb=best_ev,
        equity_pct=equity * 100,
        method=method,
        hand_str=hand_str,
        all_evs_bb=adjusted_evs,
        icm_factor=icm_factor,
        bubble_factor=bubble_factor,
        pressure_label=pressure_label,
        pressure_weight=pw,
        current_icm_dollar=current_icm_dollar,
        all_evs_dollar=evs_dollar,
        icm_equity_pct=icm_equity_pct,
    )
