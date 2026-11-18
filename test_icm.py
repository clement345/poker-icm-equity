from engine.cards import parse_card
from engine.icm import TournamentInfo, calc_bubble_factor, calc_icm_dollar_evs
from engine.game_state import GameState
from engine.recommender import recommend

payouts = [0.20, 0.12, 0.08, 0.06, 0.045, 0.035, 0.03, 0.025, 0.02, 0.018]

# Test 1: ON THE BUBBLE
ti_bubble = TournamentInfo(buy_in=10, total_players=500, players_remaining=64, paid_spots=63)
print(f"Bulle : dist={ti_bubble.bubble_distance}  pw={ti_bubble.pressure_weight:.2f}  {ti_bubble.pressure_label}")

# Test 2: ITM
ti_itm = TournamentInfo(buy_in=10, total_players=500, players_remaining=20, paid_spots=63)
print(f"ITM   : dist={ti_itm.bubble_distance}  pw={ti_itm.pressure_weight:.2f}  {ti_itm.pressure_label}")

# Test 3: Approaching bubble
ti_near = TournamentInfo(buy_in=10, total_players=500, players_remaining=70, paid_spots=63)
print(f"Near  : dist={ti_near.bubble_distance}  pw={ti_near.pressure_weight:.2f}  {ti_near.pressure_label}")

# Test 4: Full recommend on bubble
state = GameState(
    hole_cards=[parse_card('As'), parse_card('Kd')],
    board=[],
    street='preflop',
    num_players=4,
    position='BTN',
    hero_stack=20.0,
    villain_stacks=[80.0, 50.0, 30.0],
    pot=3.0,
    to_call=2.0,
    tournament=ti_bubble,
    payouts=payouts,
)
rec = recommend(state, n_simulations=3000)
print(f"\nAKo preflop ON BUBBLE -> {rec.best_action}  EV={rec.best_ev_bb:+.2f}BB  BF={rec.bubble_factor:.2f}x")
print(f"  equity={rec.equity_pct:.1f}%  ICM$={rec.current_icm_dollar}  pressure={rec.pressure_weight:.2f}")
print(f"  EVs: {rec.all_evs_bb}")

# Test 5: 72o on bubble (should fold)
state2 = GameState(
    hole_cards=[parse_card('7h'), parse_card('2d')],
    board=[],
    street='preflop',
    num_players=4,
    position='BB',
    hero_stack=12.0,
    villain_stacks=[80.0, 50.0, 30.0],
    pot=3.0,
    to_call=12.0,
    tournament=ti_bubble,
    payouts=payouts,
)
rec2 = recommend(state2, n_simulations=2000)
print(f"\n72o quasi-allin ON BUBBLE -> {rec2.best_action}  EV={rec2.best_ev_bb:+.2f}BB  BF={rec2.bubble_factor:.2f}x")
print(f"  equity={rec2.equity_pct:.1f}%")
