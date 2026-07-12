"""Provider-independent deterministic market feature engine."""

from apex.features.contracts import (
    FeatureOutputShape,
    FeatureResult,
    FeatureSpec,
    MissingDataPolicy,
)
from apex.features.moving_averages import (
    exponential_moving_average,
    simple_moving_average,
)
from apex.features.numerical import finite_values, rolling_mean, validate_period
from apex.features.validation import ActiveCandlePolicy, prepare_candles

__all__ = [
    "ActiveCandlePolicy",
    "FeatureOutputShape",
    "FeatureResult",
    "FeatureSpec",
    "MissingDataPolicy",
    "exponential_moving_average",
    "finite_values",
    "prepare_candles",
    "rolling_mean",
    "simple_moving_average",
    "validate_period",
]
