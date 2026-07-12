"""Provider-independent deterministic market feature engine."""

from apex.features.contracts import (
    FeatureOutputShape,
    FeatureResult,
    FeatureSpec,
    MissingDataPolicy,
)
from apex.features.momentum import (
    MacdResult,
    macd,
    rate_of_change,
    relative_strength_index,
    rsi_slope,
)
from apex.features.moving_averages import (
    exponential_moving_average,
    simple_moving_average,
)
from apex.features.numerical import finite_values, rolling_mean, validate_period
from apex.features.price_location import (
    bollinger_position,
    distance_from_recent_extremes,
    recent_range_position,
    vwap,
)
from apex.features.registry import (
    FeatureAuditEntry,
    FeatureRegistry,
    create_default_feature_registry,
)
from apex.features.trend import (
    EmaRelationshipResult,
    ema_relationship,
    ema_slope,
    price_distance_from_ema,
    trend_persistence,
)
from apex.features.validation import ActiveCandlePolicy, prepare_candles
from apex.features.volatility import (
    BollingerBandsResult,
    WickStatistics,
    atr_percentage,
    average_true_range,
    bollinger_bands,
    candle_range_ratio,
    true_range,
    wick_statistics,
)
from apex.features.volume import (
    VolumePressureResult,
    average_volume,
    relative_volume,
    volume_pressure,
    volume_spike,
)

__all__ = [
    "ActiveCandlePolicy",
    "BollingerBandsResult",
    "EmaRelationshipResult",
    "FeatureAuditEntry",
    "FeatureOutputShape",
    "FeatureRegistry",
    "FeatureResult",
    "FeatureSpec",
    "MacdResult",
    "MissingDataPolicy",
    "VolumePressureResult",
    "WickStatistics",
    "atr_percentage",
    "average_true_range",
    "average_volume",
    "bollinger_bands",
    "bollinger_position",
    "candle_range_ratio",
    "create_default_feature_registry",
    "distance_from_recent_extremes",
    "ema_relationship",
    "ema_slope",
    "exponential_moving_average",
    "finite_values",
    "macd",
    "prepare_candles",
    "price_distance_from_ema",
    "rate_of_change",
    "recent_range_position",
    "relative_strength_index",
    "relative_volume",
    "rolling_mean",
    "rsi_slope",
    "simple_moving_average",
    "trend_persistence",
    "true_range",
    "validate_period",
    "volume_pressure",
    "volume_spike",
    "vwap",
    "wick_statistics",
]
