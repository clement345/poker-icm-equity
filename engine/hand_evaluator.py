from __future__ import annotations
from treys import Evaluator as TreysEvaluator

_evaluator = TreysEvaluator()


def evaluate_hand(hole: list[int], board: list[int]) -> int:
    """
    Returns treys score for hole cards + board (3-5 community cards).
    Lower score = stronger hand (1 = royal flush, 7462 = worst high card).
    """
    return _evaluator.evaluate(board, hole)


def hand_rank_str(score: int) -> str:
    """Convert treys score to human-readable rank: 'Flush', 'Two Pair', etc."""
    return _evaluator.class_to_string(_evaluator.get_rank_class(score))


def rank_class(score: int) -> int:
    """1 (straight flush) to 9 (high card)."""
    return _evaluator.get_rank_class(score)
