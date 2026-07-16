"""Legacy futures scanner-mode contract retained for persisted compatibility."""

from enum import StrEnum


class ScannerMode(StrEnum):
    """Legacy futures scanner modes used by preserved setup-segment records."""

    NORMAL = "normal"
    GAINERS = "gainers"
    ALL = "all"
