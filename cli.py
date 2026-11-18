from __future__ import annotations
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

from engine.cards import parse_cards, card_str
from engine.game_state import GameState, VALID_POSITIONS
from engine.recommender import recommend, Recommendation


# ── I/O helpers ───────────────────────────────────────────────────────────────

def _ask(prompt: str, default: str = "") -> str:
    suffix = f" [{default}]" if default else ""
    try:
        val = input(f"  {prompt}{suffix} : ").strip()
    except (EOFError, KeyboardInterrupt):
        print("\nGoodbye.")
        sys.exit(0)
    return val if val else default


def _ask_float(prompt: str, default: float | None = None) -> float:
    default_str = str(default) if default is not None else ""
    while True:
        raw = _ask(prompt, default_str)
        try:
            return float(raw)
        except ValueError:
            print("    → Enter a number (e.g. 12.5)")


def _ask_cards(prompt: str, required: int | None = None) -> list[int]:
    while True:
        raw = _ask(prompt)
        try:
            cards = parse_cards(raw)
            if required and len(cards) != required:
                print(f"    → {required} card(s) required. E.g. 'As Kd'")
                continue
            return cards
        except ValueError as e:
            print(f"    → {e}")


def _ask_payouts() -> list[float]:
    while True:
        raw = _ask("Payouts % (e.g. '50 30 20')")
        try:
            parts = [float(x) for x in raw.split()]
            if not parts:
                continue
            if abs(sum(parts) - 100) > 1:
                print(f"    → Sum ≠ 100% (current: {sum(parts):.0f}%)")
                continue
            return [p / 100 for p in parts]
        except ValueError:
            print("    → Space-separated numbers")


# ── Display ───────────────────────────────────────────────────────────────────

def _display(rec: Recommendation, state: GameState) -> None:
    W = 44
    sep = "═" * W
    hole_str = " ".join(card_str(c) for c in state.hole_cards)
    board_str = " ".join(card_str(c) for c in state.board) if state.board else "—"

    print()
    print(f"╔{sep}╗")
    print(f"║{'RESULT':^{W}}║")
    print(f"╠{sep}╣")
    print(f"║  Hand      : {hole_str:<{W - 14}}║")
    if state.board:
        label = f"{board_str}  ({rec.hand_str})" if rec.hand_str else board_str
        print(f"║  Board     : {label:<{W - 14}}║")
    tag = "exact" if rec.method == "exact" else "MC"
    print(f"║  Equity    : {rec.equity_pct:>5.1f}%  [{tag}]{'':<{W - 22}}║")
    if rec.icm_equity_pct is not None:
        print(f"║  ICM eq.   : {rec.icm_equity_pct:>5.1f}%  (x{rec.icm_factor:.2f}){'':<{W - 32}}║")
    print(f"╠{sep}╣")
    sign = "+" if rec.best_ev >= 0 else ""
    print(f"║  ▶  {rec.best_action.upper():<22}  EV: {sign}{rec.best_ev:+.2f} BB{'':<{W - 41}}║")
    print(f"╠{sep}╣")
    for action, ev in sorted(rec.all_evs.items(), key=lambda x: -x[1]):
        marker = " ◀" if action == rec.best_action else "  "
        s = "+" if ev >= 0 else ""
        print(f"║    {action:<20}{s}{ev:+.2f} BB{marker}{'':<{W - 37}}║")
    print(f"╚{sep}╝")
    print()


# ── Manual entry ──────────────────────────────────────────────────────────────

def _manual(itm: bool, payouts: list[float]) -> GameState | None:
    from engine.game_state import VALID_STREETS

    street_map = {"p": "preflop", "f": "flop", "t": "turn", "r": "river"}

    def ask_street() -> str:
        while True:
            raw = _ask("Street (p=preflop / f=flop / t=turn / r=river)", "p")
            s = street_map.get(raw[0].lower()) if raw else None
            if s:
                return s
            print("    → p / f / t / r")

    street  = ask_street()
    hole    = _ask_cards("Your cards (e.g. 'As Kd')", required=2)
    n_board = {"preflop": 0, "flop": 3, "turn": 4, "river": 5}[street]
    board   = _ask_cards(f"Board ({n_board} cards)", required=n_board) if n_board else []

    num_players = 0
    while not (2 <= num_players <= 9):
        num_players = int(_ask_float("Active players", default=6))

    position  = _ask("Position (BTN/SB/BB/UTG/HJ/CO)", default="BTN").upper()
    if position not in VALID_POSITIONS:
        position = "BTN"

    hero_stack = _ask_float("Your stack (BBs)", default=50.0)
    pot        = _ask_float("Pot (BBs)", default=10.0)
    to_call    = _ask_float("Amount to call (BBs, 0=check)", default=0.0)

    # Villain stacks
    while True:
        raw = _ask(f"Stacks of the {num_players - 1} opponent(s) (e.g. '60 30 25')")
        try:
            parts = [float(x) for x in raw.split()]
            if len(parts) == num_players - 1:
                break
            print(f"    → {num_players - 1} value(s) expected")
        except ValueError:
            print("    → Space-separated numbers")

    try:
        return GameState(
            hole_cards    = hole,
            board         = board,
            street        = street,
            num_players   = num_players,
            position      = position,
            hero_stack    = hero_stack,
            villain_stacks= parts,
            pot           = pot,
            to_call       = to_call,
            in_the_money  = itm,
            payouts       = payouts,
        )
    except ValueError as e:
        print(f"  Error: {e}")
        return None


# ── Main loop ─────────────────────────────────────────────────────────────────

def main() -> None:
    print()
    print("╔══════════════════════════════════════════════╗")
    print("║       POKER ADVISOR — Hold'em Tournament     ║")
    print("╚══════════════════════════════════════════════╝")
    print()

    # ITM + payouts — asked once per session
    itm_raw = _ask("Are you ITM? (y/n)", default="n").lower()
    itm = itm_raw in ("y", "yes")
    payouts: list[float] = _ask_payouts() if itm else []

    print()
    print("  [Enter] = new hand   [q] = quit")

    while True:
        print()
        print("─" * 48)
        cmd = _ask("Action", default="").lower()

        if cmd in ("q", "quit", "quitter", "exit"):
            print("  Goodbye!\n")
            break

        state: GameState | None = None

        state = _manual(itm, payouts)

        if state is None:
            continue

        exact = {"river": True, "turn": state.num_villains == 1}
        use_exact = exact.get(state.street, False)
        n_sims = 10_000

        if use_exact:
            print("  Exact calculation in progress...", end=" ", flush=True)
        else:
            print(f"  Monte Carlo {n_sims:,} simulations...", end=" ", flush=True)

        rec = recommend(state, n_simulations=n_sims)
        print("OK")

        _display(rec, state)

        # Offer to update ITM mid-session
        if _ask("Update ITM? (y/n)", default="n").lower() in ("y", "yes"):
            itm_raw = _ask("ITM now? (y/n)", default="y").lower()
            itm = itm_raw in ("y", "yes")
            payouts = _ask_payouts() if itm else []


if __name__ == "__main__":
    main()
