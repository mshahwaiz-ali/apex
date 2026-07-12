"""Deterministic swing-high and swing-low detection."""

from __future__ import annotations

from collections.abc import Sequence

from apex.domain.models import Candle
from apex.features.validation import ActiveCandlePolicy, prepare_candles
from apex.structure.contracts import ComparisonPolicy, PivotStatus, SwingPoint, SwingType


def detect_swings(
    candles: Sequence[Candle],
    *,
    left_window: int = 2,
    right_window: int = 2,
    comparison_policy: ComparisonPolicy = ComparisonPolicy.STRICT,
    active_candle_policy: ActiveCandlePolicy = ActiveCandlePolicy.DROP_FINAL,
    include_developing: bool = False,
) -> tuple[SwingPoint, ...]:
    """Return stable chronological pivots without lookahead leakage.

    Confirmed pivots require a complete right-side window made entirely of
    closed candles. Developing pivots are optional and never masquerade as
    confirmed when the active candle participates in their right-side window.
    """

    if left_window < 1 or right_window < 1:
        raise ValueError("left_window and right_window must be at least 1")

    usable = prepare_candles(
        candles,
        minimum_candles=left_window + 1,
        active_candle_policy=active_candle_policy,
    )
    results: list[SwingPoint] = []

    for index in range(left_window, len(usable)):
        available_right = len(usable) - index - 1
        right_size = min(right_window, available_right)
        left = usable[index - left_window : index]
        right = usable[index + 1 : index + 1 + right_size]
        has_complete_right_window = available_right >= right_window
        has_only_closed_confirmation = all(candle.is_closed for candle in right)
        confirmed = has_complete_right_window and has_only_closed_confirmation
        if not confirmed and not include_developing:
            continue
        if right_size == 0 and not include_developing:
            continue

        candidate = usable[index]
        status = PivotStatus.CONFIRMED if confirmed else PivotStatus.DEVELOPING
        right_highs = tuple(item.high for item in right)
        right_lows = tuple(item.low for item in right)
        left_highs = tuple(item.high for item in left)
        left_lows = tuple(item.low for item in left)

        if _is_extreme(
            candidate.high,
            left_highs,
            right_highs,
            True,
            comparison_policy,
        ):
            results.append(
                SwingPoint(
                    index=index,
                    time=candidate.open_time,
                    price=candidate.high,
                    kind=SwingType.HIGH,
                    status=status,
                    left_window=left_window,
                    right_window=right_window,
                )
            )

        if _is_extreme(
            candidate.low,
            left_lows,
            right_lows,
            False,
            comparison_policy,
        ):
            results.append(
                SwingPoint(
                    index=index,
                    time=candidate.open_time,
                    price=candidate.low,
                    kind=SwingType.LOW,
                    status=status,
                    left_window=left_window,
                    right_window=right_window,
                )
            )

    return tuple(sorted(results, key=lambda item: (item.index, item.kind.value)))


def _is_extreme(
    candidate: float,
    left: tuple[float, ...],
    right: tuple[float, ...],
    is_high: bool,
    policy: ComparisonPolicy,
) -> bool:
    neighbours = left + right
    if not neighbours:
        return False

    if policy is ComparisonPolicy.STRICT:
        comparator = (
            (lambda value: candidate > value)
            if is_high
            else (lambda value: candidate < value)
        )
        return all(comparator(value) for value in neighbours)

    comparator = (
        (lambda value: candidate >= value)
        if is_high
        else (lambda value: candidate <= value)
    )
    if not all(comparator(value) for value in neighbours):
        return False

    # Deterministic tie-breaking: the earliest equal extreme wins.
    return all(candidate != value for value in left)
