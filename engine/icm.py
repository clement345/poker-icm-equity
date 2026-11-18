from __future__ import annotations
from dataclasses import dataclass, field


@dataclass
class TournamentInfo:
    buy_in: float            # buy-in in $
    total_players: int       # starting field
    players_remaining: int   # players still in contention
    paid_spots: int          # paid places

    prize_pool: float | None = None  # if None → computed automatically

    def __post_init__(self) -> None:
        if self.prize_pool is None:
            # ~5% standard rake
            self.prize_pool = self.buy_in * self.total_players * 0.95

    # ── Bubble metrics ────────────────────────────────────────────────────────

    @property
    def bubble_distance(self) -> int:
        """
        +N  = N players still have to be eliminated before the bubble
         0  = next out doesn't get paid → ON THE BUBBLE (max pressure)
        -N  = ITM for N places
        """
        return self.players_remaining - self.paid_spots - 1

    @property
    def is_itm(self) -> bool:
        return self.players_remaining <= self.paid_spots

    @property
    def pressure_weight(self) -> float:
        """
        ICM pressure weight [0.0, 1.0].
        1.0 = bubble (maximum pressure).
        Decays symmetrically before and after the bubble.
        """
        d = self.bubble_distance
        if d == 0:
            return 1.0  # ON the bubble
        if d > 0:
            # Before the bubble: fast decay
            return max(0.0, 1.0 - d * 0.12)
        else:
            # After the bubble: slower decay (pay jumps still matter)
            itm_depth = abs(d)
            # Stays at 0.6 right after the bubble, then declines
            return max(0.0, 0.65 - itm_depth * 0.05)

    @property
    def pressure_label(self) -> str:
        d = self.bubble_distance
        if d > 0:
            # Not ITM yet
            if d == 1:
                return "🔴 Bubble -1"
            elif d <= 3:
                return f"🟠 Bubble -{d}"
            elif d <= 10:
                return "🟡 Approaching Bubble"
            else:
                return "🟢 Early Stage"
        elif d == 0:
            return "🚨 ON THE BUBBLE"
        else:
            # ITM (d < 0)
            if self.players_remaining <= 2:
                return "🏆 Heads-up"
            elif self.players_remaining <= 9:
                return "🎯 Final Table"
            elif abs(d) <= 3:
                return "✅ Just ITM"
            else:
                return "✅ ITM"

    @property
    def next_pay_jump(self) -> float | None:
        """Difference in $ between the current place and the previous paid place (if known)."""
        return None  # computed in recommender when $ payouts are available


# ── ICM core (Malmuth-Harville) ───────────────────────────────────────────────

def calc_icm(stacks: list[float], payouts: list[float]) -> list[float]:
    """
    Malmuth-Harville: returns the fraction of the prize pool
    corresponding to each player (sum ≈ 1).
    """
    n = len(stacks)
    equity = [0.0] * n
    total = sum(stacks)
    if total == 0:
        return equity

    pay = list(payouts[:n])

    def _rec(
        indices: list[int],
        rem_stacks: list[float],
        rem_pay: list[float],
        prob: float,
    ) -> None:
        if not rem_pay or not indices:
            return
        sub = sum(rem_stacks)
        if sub == 0:
            return
        p0 = rem_pay[0]
        for k, (orig, stk) in enumerate(zip(indices, rem_stacks)):
            p = stk / sub
            equity[orig] += prob * p * p0
            _rec(
                indices[:k] + indices[k + 1 :],
                rem_stacks[:k] + rem_stacks[k + 1 :],
                rem_pay[1:],
                prob * p,
            )

    _rec(list(range(n)), list(stacks), pay, 1.0)
    return equity


# ── Bubble Factor ─────────────────────────────────────────────────────────────

def calc_bubble_factor(
    all_stacks: list[float],
    payouts: list[float],
    to_call: float,
    pot: float,
    hero_idx: int = 0,
) -> float:
    """
    Bubble Factor (BF) for a call decision.

    BF = (min ICM equity) / (min chip-EV equity)

    BF > 1 → requires more equity than pure chip-EV → ICM pushes toward fold
    BF = 1 → no ICM pressure
    BF < 1 → ICM favors the gamble (short stack close to busting anyway)
    """
    if to_call <= 0 or pot <= 0:
        return 1.0

    hero_stack = all_stacks[hero_idx]
    n = len(all_stacks)
    n_villains = n - 1

    # Chip EV break-even equity
    chip_be = to_call / (pot + to_call)

    # Current ICM (fold)
    icm_fold = calc_icm(all_stacks, payouts)[hero_idx]

    # Stacks if hero wins the pot
    stacks_win = list(all_stacks)
    stacks_win[hero_idx] = hero_stack + pot
    if n_villains > 0:
        loss_each = pot / n_villains
        for i in range(n):
            if i != hero_idx:
                stacks_win[i] = max(0.0, all_stacks[i] - loss_each)
    icm_win = calc_icm(stacks_win, payouts)[hero_idx]

    # Stacks if hero loses to_call
    stacks_lose = list(all_stacks)
    stacks_lose[hero_idx] = max(0.0, hero_stack - to_call)
    if n_villains > 0:
        gain_each = to_call / n_villains
        for i in range(n):
            if i != hero_idx:
                stacks_lose[i] = all_stacks[i] + gain_each
    icm_lose = calc_icm(stacks_lose, payouts)[hero_idx]

    if icm_win <= icm_lose or chip_be <= 0:
        return 1.0

    icm_be = (icm_fold - icm_lose) / (icm_win - icm_lose)
    return max(0.2, min(icm_be / chip_be, 6.0))


# ── ICM EV in $ ──────────────────────────────────────────────────────────────

def calc_icm_dollar_evs(
    all_stacks: list[float],
    payouts: list[float],
    prize_pool: float,
    equity: float,
    to_call: float,
    pot: float,
    hero_idx: int = 0,
) -> dict[str, float]:
    """
    ICM EV in $ for fold and call.
    Returns: current_usd, fold_gain_usd, call_gain_usd (relative to fold).
    """
    n = len(all_stacks)
    hero_stack = all_stacks[hero_idx]
    n_villains = n - 1

    icm_eq = calc_icm(all_stacks, payouts)
    current_usd = icm_eq[hero_idx] * prize_pool

    if to_call <= 0:
        return {"current_usd": current_usd, "fold_gain_usd": 0.0, "call_gain_usd": 0.0}

    stacks_win = list(all_stacks)
    stacks_win[hero_idx] = hero_stack + pot
    if n_villains > 0:
        loss_each = pot / n_villains
        for i in range(n):
            if i != hero_idx:
                stacks_win[i] = max(0.0, all_stacks[i] - loss_each)
    win_usd = calc_icm(stacks_win, payouts)[hero_idx] * prize_pool

    stacks_lose = list(all_stacks)
    stacks_lose[hero_idx] = max(0.0, hero_stack - to_call)
    if n_villains > 0:
        gain_each = to_call / n_villains
        for i in range(n):
            if i != hero_idx:
                stacks_lose[i] = all_stacks[i] + gain_each
    lose_usd = calc_icm(stacks_lose, payouts)[hero_idx] * prize_pool

    call_ev_usd = equity * win_usd + (1 - equity) * lose_usd
    return {
        "current_usd": current_usd,
        "fold_gain_usd": 0.0,
        "call_gain_usd": call_ev_usd - current_usd,
    }


# ── ICM adjustment factor (for chip EV → ICM EV) ─────────────────────────────

def icm_adjustment(
    all_stacks: list[float],
    payouts: list[float],
    hero_idx: int = 0,
    pressure_weight: float = 1.0,
) -> float:
    """
    ICM multiplicative factor [0.3, 1.0] applied to chip EV for aggressive actions.
    pressure_weight comes from TournamentInfo.pressure_weight.
    """
    if not payouts or not all_stacks:
        return 1.0
    hero_stack = all_stacks[hero_idx]
    total = sum(all_stacks)
    if total == 0:
        return 1.0

    baseline = calc_icm(all_stacks, payouts)[hero_idx]
    delta = max(hero_stack * 0.1, 1.0)

    s_gain = list(all_stacks)
    s_gain[hero_idx] = min(hero_stack + delta, total)
    s_lose = list(all_stacks)
    s_lose[hero_idx] = max(hero_stack - delta, 0.0)

    g = calc_icm(s_gain, payouts)[hero_idx] - baseline
    l = baseline - calc_icm(s_lose, payouts)[hero_idx]

    if g + l == 0:
        return 1.0

    raw = g / ((g + l) / 2.0)
    # Interpolate with pressure_weight: at 0 pressure → factor 1.0
    factor = 1.0 + pressure_weight * (raw - 1.0)
    return max(0.3, min(factor, 1.0))
